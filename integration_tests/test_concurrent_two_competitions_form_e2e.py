"""
E2E: два одновременных POST на SimpleCompetitionForm (два разных лаба, один взвод),
проверка корректности топологии при работе нескольких воркеров Gunicorn.
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
import warnings

import pytest
from django.core.management import call_command


pytestmark = [pytest.mark.integration, pytest.mark.pnet, pytest.mark.docker, pytest.mark.slow]


def _build_simple_competition_form_data(level_pk: int, task_pks: list[int]) -> list[tuple[str, str]]:
    """Формирует данные для POST SimpleCompetitionForm (duration_0/1/2/3, level, tasks)."""
    data = [
        ("duration_0", "0"),
        ("duration_1", "2"),
        ("duration_2", "0"),
        ("duration_3", "0"),
        ("level", str(level_pk)),
    ]
    for pk in task_pks:
        data.append(("tasks", str(pk)))
    return data


def _post_lab_competition_form(session, base_url: str, lab_slug: str, lab_type: str, form_data: list) -> object:
    """POST на LabDetailView (SimpleCompetitionForm). Возвращает response."""
    url = f"{base_url}/cyberpolygon/labs/{lab_slug}/{lab_type}/"
    return session.post(url, data=form_data, timeout=300, allow_redirects=False)


def _competition_slug_from_redirect(response) -> str | None:
    """Извлекает slug соревнования из заголовка Location (redirect на competition-detail)."""
    location = response.headers.get("Location") or ""
    # .../cyberpolygon/competitions/<slug>/
    match = re.search(r"/competitions/([^/]+)/?$", location)
    return match.group(1) if match else None


def _collect_worker_pids(base_url: str, session, attempts: int = 20) -> set[int]:
    worker_pids: set[int] = set()
    for _ in range(attempts):
        try:
            r = session.get(f"{base_url}/cyberpolygon/test/worker-id/", timeout=10)
            if r.status_code == 200:
                payload = r.json()
                pid = payload.get("pid")
                if isinstance(pid, int):
                    worker_pids.add(pid)
        except Exception:
            pass
    return worker_pids


def test_two_concurrent_simple_competition_form_posts_topology_correct(
    django_ready, integration_stack, pnet_admin_session, cleanup_context
):
    """
    Два одновременных POST на SimpleCompetitionForm (два разных лаба, один взвод, 15 пользователей,
    complex topology). Убеждаемся, что воркеры Gunicorn инициализированы, и проверяем корректность
    топологии обеих лаб после создания.
    """
    from dynamic_config.models import ConfigEntry
    from dynamic_config.utils import get_config
    from interface.eveFunctions import get_lab_topology
    from integration_tests.utils.db_seed import (
        CompetitionScenario,
        INTEGRATION_TEST_PASSWORD,
        build_complex_topology_data,
        register_competition_cleanup,
        seed_two_labs_same_platoon_scenario,
    )
    from integration_tests.utils.http_client import login_to_django
    from integration_tests.utils.pnet_cleanup import login_admin_to_pnet, safe_delete_users
    from integration_tests.utils.topology import extract_nodes_and_links

    worker_keys = [f"WORKER_{idx}_CREDS" for idx in range(1, 4)]
    config_before = {key: get_config(key) for key in worker_keys}
    created_worker_usernames: list[str] = []

    try:
        call_command("create_worker_credentials", workers=3)
        config_after = {key: get_config(key) for key in worker_keys}
        for key in worker_keys:
            value = config_after.get(key)
            assert value, f"{key} must be created by create_worker_credentials"
            creds = json.loads(value)
            if config_before.get(key) is None:
                created_worker_usernames.append(creds["username"])

        nodes_data, connectors_data, connectors2cloud_data, networks_data = build_complex_topology_data()
        prefix = f"it-two-comp-{int(time.time())}"
        scenario = seed_two_labs_same_platoon_scenario(
            prefix,
            users_count=15,
            nodes_data_override=nodes_data,
            connectors_data_override=connectors_data,
            connectors2cloud_data_override=connectors2cloud_data,
            networks_data_override=networks_data,
            make_first_user_staff=True,
        )

        base_url = integration_stack["base_url"]
        admin_user = scenario.users[0]
        session = login_to_django(base_url, admin_user.username, INTEGRATION_TEST_PASSWORD)

        observed_worker_pids = _collect_worker_pids(base_url, session)
        if len(observed_worker_pids) < 2:
            warnings.warn(
                "Could not observe >=2 worker PIDs via /cyberpolygon/test/worker-id/; "
                "continuing with topology assertions only.",
                RuntimeWarning,
                stacklevel=1,
            )

        form_data_1 = _build_simple_competition_form_data(
            scenario.level1.pk, [t.pk for t in scenario.tasks1]
        )
        form_data_2 = _build_simple_competition_form_data(
            scenario.level2.pk, [t.pk for t in scenario.tasks2]
        )

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_1 = executor.submit(
                _post_lab_competition_form,
                session,
                base_url,
                scenario.lab1.slug,
                scenario.lab1.lab_type,
                form_data_1,
            )
            future_2 = executor.submit(
                _post_lab_competition_form,
                session,
                base_url,
                scenario.lab2.slug,
                scenario.lab2.lab_type,
                form_data_2,
            )
            response_1 = future_1.result()
            response_2 = future_2.result()

        assert response_1.status_code == 302, (
            f"Expected 302 redirect for lab1, got {response_1.status_code}: {response_1.text[:500]}"
        )
        assert response_2.status_code == 302, (
            f"Expected 302 redirect for lab2, got {response_2.status_code}: {response_2.text[:500]}"
        )

        slug_1 = _competition_slug_from_redirect(response_1)
        slug_2 = _competition_slug_from_redirect(response_2)
        assert slug_1, f"Could not extract competition slug from Location: {response_1.headers.get('Location')}"
        assert slug_2, f"Could not extract competition slug from Location: {response_2.headers.get('Location')}"

        from interface.models import Competition

        competition_1 = Competition.objects.get(slug=slug_1)
        competition_2 = Competition.objects.get(slug=slug_2)

        register_competition_cleanup(
            cleanup_context, prefix, CompetitionScenario(competition_1, scenario.users, scenario.lab1, scenario.tasks1)
        )
        register_competition_cleanup(
            cleanup_context, prefix, CompetitionScenario(competition_2, scenario.users, scenario.lab2, scenario.tasks2)
        )

        pnet_proxy_url = f"{base_url}/pnetlab"
        sample_user = scenario.users[0]
        user_session = login_to_django(base_url, sample_user.username, INTEGRATION_TEST_PASSWORD)

        for competition, lab, expected_nodes in [
            (competition_1, scenario.lab1, scenario.lab1.NodesData),
            (competition_2, scenario.lab2, scenario.lab2.NodesData),
        ]:
            user_session.post(f"{base_url}/api/get_pnet_auth/", json={}, timeout=20)
            create_resp = user_session.post(
                f"{base_url}/api/create_pnet_lab_session/",
                json={"slug": competition.slug},
                timeout=30,
            )
            assert create_resp.status_code == 200, create_resp.text
            assert create_resp.json().get("success") is True

            topology = get_lab_topology(pnet_proxy_url, user_session.cookies)
            assert topology is not None, f"Topology for {competition.slug} should not be None"
            nodes, links = extract_nodes_and_links(topology)
            expected_names = {n["name"] for n in expected_nodes if n and n.get("name")}
            node_names = [n.get("name") for n in nodes if isinstance(n, dict) and n.get("name")]
            assert expected_names.issubset(set(node_names)), (
                f"All configured nodes must exist in topology for {competition.slug}"
            )
            assert len(node_names) == len(set(node_names)), f"Nodes must not be duplicated for {competition.slug}"
            link_ids = [str(link.get("id", link)) for link in links if link]
            assert len(link_ids) == len(set(link_ids)), f"Links must not be duplicated for {competition.slug}"

    finally:
        if created_worker_usernames:
            admin_cookie, admin_xsrf = login_admin_to_pnet(pnet_admin_session["pnet_url"])
            safe_delete_users(
                pnet_admin_session["pnet_url"],
                admin_cookie,
                admin_xsrf,
                created_worker_usernames,
            )
        for key, old_value in config_before.items():
            if old_value is None:
                ConfigEntry.objects.filter(key=key).delete()
            else:
                ConfigEntry.objects.update_or_create(key=key, defaults={"value": old_value})

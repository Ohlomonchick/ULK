import json
import time
from concurrent.futures import ThreadPoolExecutor
import warnings

import pytest
from django.core.management import call_command


pytestmark = [pytest.mark.integration, pytest.mark.pnet, pytest.mark.docker, pytest.mark.slow]


def _collect_worker_pids(base_url: str, sessions: list, attempts: int = 20) -> set[int]:
    worker_pids: set[int] = set()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for idx in range(attempts):
            session = sessions[idx % len(sessions)]
            futures.append(
                executor.submit(session.get, f"{base_url}/cyberpolygon/test/worker-id/", timeout=10)
            )
        for future in futures:
            response = future.result()
            if response.status_code != 200:
                continue
            try:
                payload = response.json()
            except ValueError:
                continue
            pid = payload.get("pid")
            if isinstance(pid, int):
                worker_pids.add(pid)
    return worker_pids


def _create_lab_session(web_session, base_url: str, slug: str):
    return web_session.post(
        f"{base_url}/api/create_pnet_lab_session/",
        json={"slug": slug},
        timeout=30,
    )


def test_concurrent_lab_creation_uses_worker_credentials_and_keeps_topology_consistent(
    django_ready, integration_stack, pnet_admin_session, cleanup_context
):
    from dynamic_config.models import ConfigEntry
    from dynamic_config.utils import get_config
    from interface.eveFunctions import get_lab_topology
    from integration_tests.utils.db_seed import (
        INTEGRATION_TEST_PASSWORD,
        build_complex_topology_data,
        register_competition_cleanup,
        seed_competition_scenario,
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
        prefix = f"it-concurrent-{int(time.time())}"
        scenario = seed_competition_scenario(
            prefix,
            users_count=2,
            nodes_data_override=nodes_data,
            connectors_data_override=connectors_data,
            connectors2cloud_data_override=connectors2cloud_data,
            networks_data_override=networks_data,
        )
        register_competition_cleanup(cleanup_context, prefix, scenario)

        base_url = integration_stack["base_url"]
        pnet_proxy_url = f"{base_url}/pnetlab"
        user_a, user_b = scenario.users
        session_a = login_to_django(base_url, user_a.username, INTEGRATION_TEST_PASSWORD)
        session_b = login_to_django(base_url, user_b.username, INTEGRATION_TEST_PASSWORD)

        for session in (session_a, session_b):
            auth_response = session.post(f"{base_url}/api/get_pnet_auth/", json={}, timeout=20)
            assert auth_response.status_code == 200, auth_response.text

        observed_worker_pids = _collect_worker_pids(base_url, [session_a, session_b])
        if len(observed_worker_pids) < 2:
            warnings.warn(
                "Could not reliably observe >=2 worker pids via /cyberpolygon/test/worker-id/; "
                "continuing with concurrent create-session assertions only.",
                RuntimeWarning,
                stacklevel=1,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(_create_lab_session, session_a, base_url, scenario.competition.slug)
            future_b = executor.submit(_create_lab_session, session_b, base_url, scenario.competition.slug)
            response_a = future_a.result()
            response_b = future_b.result()

        assert response_a.status_code == 200, response_a.text
        assert response_b.status_code == 200, response_b.text
        assert response_a.json().get("success") is True
        assert response_b.json().get("success") is True

        expected_names = {node["name"] for node in scenario.lab.NodesData if node and node.get("name")}

        for session in (session_a, session_b):
            topology = get_lab_topology(pnet_proxy_url, session.cookies)
            assert topology is not None
            nodes, links = extract_nodes_and_links(topology)
            node_names = [node.get("name") for node in nodes if isinstance(node, dict) and node.get("name")]
            assert expected_names.issubset(set(node_names)), "All configured nodes must exist in topology"
            assert len(node_names) == len(set(node_names)), "Nodes must not be duplicated"
            link_ids = [str(link.get("id", link)) for link in links if link]
            assert len(link_ids) == len(set(link_ids)), "Links must not be duplicated"
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

"""
E2E-тест развёртывания флагов на SSH-ноду лабы (конфигурация SSHNodes) и проверка
наличия файла с флагами на ноде для нескольких случайных пользователей мероприятия.
Используется лаба с Docker-нодой pnetlab/ubuntu_sv:latest (образ можно скачать в PNET в один клик).
"""

import logging
import random
import time

import pytest

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.pnet, pytest.mark.docker, pytest.mark.slow]


def _check_flag_file_via_ssh(pnet_host: str, port: int, login: str, password: str) -> bool:
    """Проверяет наличие файла checker_conf.json на ноде через SSH (путь /etc/configs или $HOME/configs)."""
    from fabric import Connection

    full_host = f"{pnet_host}:{port}"
    try:
        conn = Connection(
            host=full_host,
            user=login,
            connect_kwargs={"password": password},
            connect_timeout=15,
        )
        with conn:
            # Файл размещается в /etc/configs (root/sudo) или $HOME/configs (не-root, напр. /home/admin/configs)
            r = conn.run(
                "test -f /etc/configs/checker_conf.json || test -f /root/configs/checker_conf.json || test -f /home/admin/configs/checker_conf.json",
                warn=True,
                hide=True,
            )
            return r.ok
    except Exception as e:
        logger.warning("SSH check failed for %s: %s", full_host, e)
        return False


def test_flag_file_present_on_ssh_node_for_random_users(
    django_ready, integration_stack, integration_env, cleanup_context
):
    """
    Раскатка флагов на ноду (SSHNodes в конфигурации лабы) и проверка наличия файла
    checker_conf.json на ноде для нескольких случайных пользователей мероприятия.
    Лаба с одной Docker SSH-нодой (pnetlab/ubuntu_sv:latest).
    """
    from interface.eveFunctions import get_lab_topology, turn_on_node
    from interface.flag_deployment import wait_for_node_ready
    from interface.lab_topology import LabTopology

    from integration_tests.utils.db_seed import (
        FLAG_DEPLOYMENT_SSH_NODE_NAME,
        INTEGRATION_TEST_PASSWORD,
        register_competition_cleanup,
        seed_competition_scenario_with_ssh_flags,
    )
    from integration_tests.utils.http_client import login_to_django

    prefix = f"it-flag-{int(time.time())}"
    users_count = 5
    scenario = seed_competition_scenario_with_ssh_flags(prefix, users_count=users_count)
    register_competition_cleanup(cleanup_context, prefix, scenario)

    base_url = integration_stack["base_url"]
    pnet_proxy_url = f"{base_url}/pnetlab"
    pnet_host = integration_env["PNET_IP"]

    lab_node = scenario.lab.nodes.filter(node_name=FLAG_DEPLOYMENT_SSH_NODE_NAME).first()
    assert lab_node is not None, "LabNode for flag deployment must exist"

    sample_size = min(3, len(scenario.users))
    sampled_users = random.Random(42).sample(scenario.users, sample_size)

    for user in sampled_users:
        web_session = login_to_django(base_url, user.username, INTEGRATION_TEST_PASSWORD)
        web_session.post(f"{base_url}/api/get_pnet_auth/", json={}, timeout=15)
        create_resp = web_session.post(
            f"{base_url}/api/create_pnet_lab_session/",
            json={"slug": scenario.competition.slug},
            timeout=20,
        )
        assert create_resp.status_code == 200, create_resp.text
        assert create_resp.json().get("success") is True

        topo_resp = web_session.get(
            f"{pnet_proxy_url}/api/labs/session/topology",
            timeout=15,
        )
        assert topo_resp.status_code == 200, topo_resp.text
        topology = LabTopology(topo_resp.json())
        ssh_nodes = topology.get_ssh_nodes()
        assert ssh_nodes, "Lab must have at least one SSH node"

        node_id = ssh_nodes[0]["id"]
        port = ssh_nodes[0]["port"]
        turn_on_node(pnet_proxy_url, node_id, web_session.cookies)
        ready = wait_for_node_ready(
            pnet_proxy_url, node_id, web_session.cookies, max_wait_time=30
        )
        assert ready, f"SSH node {node_id} did not become ready for user {user.username}"

        found = _check_flag_file_via_ssh(
            pnet_host, port, lab_node.login, lab_node.password
        )
        assert found, (
            f"checker_conf.json not found on SSH node for user {user.username} "
            f"(host={pnet_host}, port={port})"
        )
        logger.info("Flag file present on node for user %s", user.username)


def test_flag_file_present_on_ssh_node_for_team_members(
    django_ready, integration_stack, integration_env, cleanup_context
):
    """
    Раскатка флагов на ноду для командного соревнования (TeamCompetition) и проверка
    наличия файла checker_conf.json на ноде для участников команды.
    Лаба с одной Docker SSH-нодой (pnetlab/ubuntu_sv:latest).
    Используется тот же сетап сессии, что и в test_team_shared_session_e2e: первый
    участник создаёт сессию напрямую через PNET API (factory/create), второй присоединяется (join).
    """
    from interface.api import get_lab_path
    from interface.eveFunctions import (
        create_pnet_lab_session_common,
        get_lab_topology,
        get_session_id,
        join_session,
        turn_on_node,
    )
    from interface.flag_deployment import wait_for_node_ready
    from interface.lab_topology import LabTopology

    from integration_tests.utils.db_seed import (
        FLAG_DEPLOYMENT_SSH_NODE_NAME,
        INTEGRATION_TEST_PASSWORD,
        register_team_competition_cleanup,
        seed_team_competition_scenario_with_ssh_flags,
    )
    from integration_tests.utils.http_client import login_to_django

    prefix = f"it-flag-team-{int(time.time())}"
    team_size = 3
    scenario = seed_team_competition_scenario_with_ssh_flags(prefix, team_size=team_size)
    register_team_competition_cleanup(cleanup_context, prefix, scenario)

    base_url = integration_stack["base_url"]
    pnet_proxy_url = f"{base_url}/pnetlab"
    pnet_host = integration_env["PNET_IP"]
    lab_path = get_lab_path(scenario.competition, scenario.team_users[0])

    lab_node = scenario.lab.nodes.filter(node_name=FLAG_DEPLOYMENT_SSH_NODE_NAME).first()
    assert lab_node is not None, "LabNode for flag deployment must exist"

    # Проверяем для двух участников команды (как в test_team_shared_session_e2e)
    user_a, user_b = scenario.team_users[0], scenario.team_users[1]
    session_a = login_to_django(base_url, user_a.username, INTEGRATION_TEST_PASSWORD)
    session_b = login_to_django(base_url, user_b.username, INTEGRATION_TEST_PASSWORD)
    session_a.post(f"{base_url}/api/get_pnet_auth/", json={}, timeout=15)
    session_b.post(f"{base_url}/api/get_pnet_auth/", json={}, timeout=15)
    cookies_a = dict(session_a.cookies)
    cookies_b = dict(session_b.cookies)

    # User A создаёт сессию лабы напрямую через PNET API (без Django create_pnet_lab_session)
    success, msg, _ = create_pnet_lab_session_common(
        pnet_proxy_url, user_a.pnet_login, lab_path, cookies_a
    )
    assert success, f"User A create session failed: {msg}"
    session_id = get_session_id(pnet_proxy_url, cookies_a)
    assert session_id, "Session ID must be available after User A created the session"

    # User B присоединяется к сессии (как в test_team_shared_session_e2e)
    join_resp = join_session(pnet_proxy_url, session_id, cookies_b)
    assert join_resp.status_code in range(200, 400), f"User B join failed: {join_resp.text}"

    def _check_member_session(web_session, cookies, member_label: str):
        topo_resp = web_session.get(f"{pnet_proxy_url}/api/labs/session/topology", timeout=15)
        assert topo_resp.status_code == 200, topo_resp.text
        topology = LabTopology(topo_resp.json())
        ssh_nodes = topology.get_ssh_nodes()
        assert ssh_nodes, f"Lab must have at least one SSH node for {member_label}"
        node_id = ssh_nodes[0]["id"]
        port = ssh_nodes[0]["port"]
        turn_on_node(pnet_proxy_url, node_id, cookies)
        ready = wait_for_node_ready(pnet_proxy_url, node_id, cookies, max_wait_time=30)
        assert ready, f"SSH node did not become ready for {member_label}"
        found = _check_flag_file_via_ssh(pnet_host, port, lab_node.login, lab_node.password)
        assert found, f"checker_conf.json not found on SSH node for {member_label}"
        logger.info("Flag file present on node for %s", member_label)

    _check_member_session(session_a, cookies_a, "user A")
    _check_member_session(session_b, cookies_b, "user B")

import logging
import time

import pytest

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.pnet, pytest.mark.docker, pytest.mark.slow]


def _pnet_auth(web_session, base_url: str, log_label: str = ""):
    """Authenticate user with PNET via Django get_pnet_auth; returns PNET cookies as dict."""
    cookies_before = list(web_session.cookies.keys())
    resp = web_session.post(f"{base_url}/api/get_pnet_auth/", json={}, timeout=20)
    cookies_after = list(web_session.cookies.keys())
    logger.info(
        "%s get_pnet_auth: status=%s cookies_before=%s cookies_after=%s",
        log_label, resp.status_code, cookies_before, cookies_after,
    )
    assert resp.status_code == 200, f"{log_label} get_pnet_auth failed: {resp.text}"
    return {c.name: c.value for c in web_session.cookies}


def _create_pnet_session(pnet_proxy_url: str, pnet_login: str, lab_path: str, cookies: dict, log_label: str = ""):
    """Create PNET lab session directly via PNET API (factory/create through nginx proxy)."""
    from interface.eveFunctions import create_pnet_lab_session_common

    logger.info("%s creating PNET session: lab_path=%s pnet_login=%s", log_label, lab_path, pnet_login)
    success, message, pnet_code = create_pnet_lab_session_common(
        pnet_proxy_url, pnet_login, lab_path, cookies
    )
    logger.info("%s create_pnet_lab_session_common: success=%s message=%s", log_label, success, message)
    return success, message


def _get_pnet_session_id(pnet_proxy_url: str, cookies: dict, log_label: str = ""):
    """Get active PNET lab session ID via /api/auth."""
    from interface.eveFunctions import get_session_id

    session_id = get_session_id(pnet_proxy_url, cookies)
    logger.info("%s session_id=%s", log_label, session_id)
    return session_id


def _join_pnet_session(pnet_proxy_url: str, session_id, cookies: dict, log_label: str = ""):
    """Join an existing PNET lab session via factory/join."""
    from interface.eveFunctions import join_session

    resp = join_session(pnet_proxy_url, session_id, cookies)
    logger.info("%s join_session: status=%s", log_label, resp.status_code)
    assert resp.status_code in range(200, 400), f"{log_label} join_session failed: {resp.text}"
    return resp


def test_team_shared_session_propagates_node_state_between_users(
    django_ready, integration_stack, cleanup_context
):
    from interface.api import get_lab_path
    from interface.eveFunctions import get_lab_topology, get_node_status, turn_on_node
    from integration_tests.utils.db_seed import (
        INTEGRATION_TEST_PASSWORD,
        build_team_shared_session_nodes_data,
        register_team_competition_cleanup,
        seed_team_competition_scenario,
    )
    from integration_tests.utils.http_client import login_to_django
    from integration_tests.utils.topology import extract_nodes_and_links

    prefix = f"it-team-shared-{int(time.time())}"
    scenario = seed_team_competition_scenario(
        prefix, team_size=2, nodes_data_override=build_team_shared_session_nodes_data()
    )
    register_team_competition_cleanup(cleanup_context, prefix, scenario)

    user_a, user_b = scenario.team_users
    base_url = integration_stack["base_url"]
    pnet_proxy_url = f"{base_url}/pnetlab"
    lab_path = get_lab_path(scenario.competition, user_a)

    # --- Login both users to Django (admin form, since usernames are prefix-student-N) ---
    session_a = login_to_django(base_url, user_a.username, INTEGRATION_TEST_PASSWORD)
    session_b = login_to_django(base_url, user_b.username, INTEGRATION_TEST_PASSWORD)

    # --- Authenticate both with PNET (sets _session / token cookies) ---
    cookies_a = _pnet_auth(session_a, base_url, log_label="User A")
    cookies_b = _pnet_auth(session_b, base_url, log_label="User B")

    # --- User A creates the team lab session directly via PNET API ---
    success_a, msg_a = _create_pnet_session(
        pnet_proxy_url, user_a.pnet_login, lab_path, cookies_a, log_label="User A"
    )
    assert success_a, f"User A create session failed: {msg_a}"

    # --- Retrieve session ID from User A's perspective ---
    session_id = _get_pnet_session_id(pnet_proxy_url, cookies_a, log_label="User A")
    assert session_id, "Session ID must be available after User A created the session"

    # --- User B joins User A's session ---
    _join_pnet_session(pnet_proxy_url, session_id, cookies_b, log_label="User B")

    # --- User B loads topology so PNET binds their session to the shared lab ---
    topology_b_after_join = get_lab_topology(pnet_proxy_url, cookies_b)
    assert topology_b_after_join is not None, "User B must see topology after join"
    nodes_b_after_join, _ = extract_nodes_and_links(topology_b_after_join)
    assert nodes_b_after_join, "User B must see nodes in shared session after join"

    # --- Verify User A sees the topology ---
    topology_a = get_lab_topology(pnet_proxy_url, cookies_a)
    assert topology_a is not None
    nodes_a, _ = extract_nodes_and_links(topology_a)
    assert nodes_a, "Team topology must contain nodes"

    target_node = next(
        (node for node in nodes_a if isinstance(node, dict) and node.get("name") == "node-a"),
        nodes_a[0],
    )
    target_node_id = target_node.get("id")
    assert target_node_id is not None, "Target node id must exist in team topology"

    # --- User A starts a node ---
    node_start_success, node_start_message = turn_on_node(pnet_proxy_url, target_node_id, cookies_a)
    assert node_start_success, node_start_message

    status_a = None
    for _ in range(15):
        time.sleep(1)
        status_a = get_node_status(pnet_proxy_url, target_node_id, cookies_a)
        if status_a in (1, 2):
            break
    assert status_a in (1, 2), f"Node started by user A must show running for A: got {status_a}"

    # --- User B should see the node running (shared state) ---
    status_b = None
    deadline = time.time() + 35
    while time.time() < deadline:
        status_b = get_node_status(pnet_proxy_url, target_node_id, cookies_b)
        if status_b in (1, 2):
            break
        time.sleep(1)
    # --- User B sees the same topology (shared session) ---
    topology_b = get_lab_topology(pnet_proxy_url, cookies_b)
    assert topology_b is not None, "User B must get topology in shared session"
    nodes_b, _ = extract_nodes_and_links(topology_b)
    node_ids_b = {str(node.get("id")) for node in nodes_b if isinstance(node, dict) and node.get("id") is not None}
    assert str(target_node_id) in node_ids_b, "User B must see the same nodes in shared team session"

    assert status_b in (1, 2), (
        f"Node started by user A must be running in user B shared team session: status_b={status_b}"
    )

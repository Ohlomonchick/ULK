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


def _assert_create_session_ok(resp, log_label: str, get_web_container_logs) -> None:
    """Assert POST /api/create_pnet_lab_session/ returned 200; on 500 append web container logs."""
    if resp.status_code == 500 and get_web_container_logs is not None:
        web_logs = get_web_container_logs(tail=500)
        msg = (
            f"{log_label} create_pnet_lab_session returned 500. "
            f"response={resp.text[:500]}. Web container logs:\n{web_logs}"
        )
        pytest.fail(msg)
    assert resp.status_code == 200, (
        f"{log_label} create_pnet_lab_session failed: status={resp.status_code} body={resp.text[:500]}"
    )
    data = resp.json()
    assert data.get("success") is True, f"{log_label} response success not True: {data}"
    assert "lab_path" in data or "redirect_url" in data, f"{log_label} expected lab_path/redirect_url: {data}"


def test_team_shared_session_propagates_node_state_between_users(
    django_ready, integration_stack, cleanup_context, get_web_container_logs
):
    """Team shared session: both users use POST /api/create_pnet_lab_session/; API creates/joins session."""
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
    slug = scenario.competition.slug

    # --- Login both users to Django ---
    session_a = login_to_django(base_url, user_a.username, INTEGRATION_TEST_PASSWORD)
    session_b = login_to_django(base_url, user_b.username, INTEGRATION_TEST_PASSWORD)

    # --- PNET auth for both ---
    _pnet_auth(session_a, base_url, log_label="User A")
    _pnet_auth(session_b, base_url, log_label="User B")

    # --- User A: create team lab session via API (master create or join) ---
    resp_a = session_a.post(
        f"{base_url}/api/create_pnet_lab_session/",
        json={"slug": slug},
        timeout=20,
    )
    _assert_create_session_ok(resp_a, "User A", get_web_container_logs)

    # --- User B: join team session via same API ---
    resp_b = session_b.post(
        f"{base_url}/api/create_pnet_lab_session/",
        json={"slug": slug},
        timeout=20,
    )
    _assert_create_session_ok(resp_b, "User B", get_web_container_logs)

    # --- User B loads topology (PNET binds their session to the shared lab) ---
    topology_b_after_join = get_lab_topology(pnet_proxy_url, session_b.cookies)
    assert topology_b_after_join is not None, "User B must see topology after join"
    nodes_b_after_join, _ = extract_nodes_and_links(topology_b_after_join)
    assert nodes_b_after_join, "User B must see nodes in shared session after join"

    # --- Verify User A sees the topology ---
    topology_a = get_lab_topology(pnet_proxy_url, session_a.cookies)
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
    node_start_success, node_start_message = turn_on_node(pnet_proxy_url, target_node_id, session_a.cookies)
    assert node_start_success, node_start_message

    status_a = None
    for _ in range(15):
        time.sleep(1)
        status_a = get_node_status(pnet_proxy_url, target_node_id, session_a.cookies)
        if status_a in (1, 2):
            break
    assert status_a in (1, 2), f"Node started by user A must show running for A: got {status_a}"

    # --- User B should see the node running (shared state) ---
    status_b = None
    deadline = time.time() + 35
    while time.time() < deadline:
        status_b = get_node_status(pnet_proxy_url, target_node_id, session_b.cookies)
        if status_b in (1, 2):
            break
        time.sleep(1)
    # --- User B sees the same topology (shared session) ---
    topology_b = get_lab_topology(pnet_proxy_url, session_b.cookies)
    assert topology_b is not None, "User B must get topology in shared session"
    nodes_b, _ = extract_nodes_and_links(topology_b)
    node_ids_b = {str(node.get("id")) for node in nodes_b if isinstance(node, dict) and node.get("id") is not None}
    assert str(target_node_id) in node_ids_b, "User B must see the same nodes in shared team session"

    assert status_b in (1, 2), (
        f"Node started by user A must be running in user B shared team session: status_b={status_b}"
    )

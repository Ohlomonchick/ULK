import time

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.pnet, pytest.mark.docker, pytest.mark.slow]


def _create_team_session_with_reauth(web_session, base_url: str, slug: str, retries: int = 2):
    last_response = None
    for _ in range(retries + 1):
        response = web_session.post(
            f"{base_url}/api/create_pnet_lab_session/",
            json={"slug": slug},
            timeout=30,
        )
        last_response = response
        if response.status_code == 200:
            return response

        body = (response.text or "").lower()
        if "unauthorized" in body or "session timed out" in body or response.status_code in (401, 412, 500):
            reauth = web_session.post(f"{base_url}/api/get_pnet_auth/", json={}, timeout=20)
            assert reauth.status_code == 200, reauth.text
            time.sleep(1)
            continue
        break
    return last_response


def test_team_shared_session_propagates_node_state_between_users(
    django_ready, integration_stack, cleanup_context
):
    from interface.eveFunctions import get_lab_topology, get_node_status, turn_on_node
    from integration_tests.utils.db_seed import (
        INTEGRATION_TEST_PASSWORD,
        register_team_competition_cleanup,
        seed_team_competition_scenario,
    )
    from integration_tests.utils.http_client import login_to_django
    from integration_tests.utils.topology import extract_nodes_and_links

    prefix = f"it-team-shared-{int(time.time())}"
    scenario = seed_team_competition_scenario(prefix, team_size=2)
    register_team_competition_cleanup(cleanup_context, prefix, scenario)

    user_a, user_b = scenario.team_users
    base_url = integration_stack["base_url"]
    pnet_proxy_url = f"{base_url}/pnetlab"

    session_a = login_to_django(base_url, user_a.username, INTEGRATION_TEST_PASSWORD)
    session_b = login_to_django(base_url, user_b.username, INTEGRATION_TEST_PASSWORD)

    for session in (session_a, session_b):
        auth_response = session.post(f"{base_url}/api/get_pnet_auth/", json={}, timeout=20)
        assert auth_response.status_code == 200, auth_response.text

    create_a = _create_team_session_with_reauth(session_a, base_url, scenario.competition.slug)
    assert create_a.status_code == 200, create_a.text
    assert create_a.json().get("success") is True

    create_b = _create_team_session_with_reauth(session_b, base_url, scenario.competition.slug)
    assert create_b.status_code == 200, create_b.text
    assert create_b.json().get("success") is True

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

    node_start_success, node_start_message = turn_on_node(pnet_proxy_url, target_node_id, session_a.cookies)
    assert node_start_success, node_start_message

    status_b = None
    deadline = time.time() + 40
    while time.time() < deadline:
        status_b = get_node_status(pnet_proxy_url, target_node_id, session_b.cookies)
        if status_b in (1, 2):
            break
        time.sleep(1)
    assert status_b in (1, 2), "Node started by user A must be running in user B shared team session"

    topology_b = get_lab_topology(pnet_proxy_url, session_b.cookies)
    assert topology_b is not None
    nodes_b, _ = extract_nodes_and_links(topology_b)
    node_ids_b = {str(node.get("id")) for node in nodes_b if isinstance(node, dict) and node.get("id") is not None}
    assert str(target_node_id) in node_ids_b

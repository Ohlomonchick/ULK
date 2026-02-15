import time

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.pnet, pytest.mark.docker, pytest.mark.slow]


def test_created_lab_topology_matches_config_and_has_no_duplicates(
    django_ready, integration_stack, integration_env, pnet_admin_session, cleanup_context
):
    from interface.eveFunctions import get_lab_topology
    from integration_tests.utils.db_seed import (
        INTEGRATION_TEST_PASSWORD,
        build_complex_topology_data,
        register_competition_cleanup,
        seed_competition_scenario,
    )
    from integration_tests.utils.http_client import login_to_django
    from integration_tests.utils.topology import extract_nodes_and_links

    prefix = f"it-topology-{int(time.time())}"
    nodes_data, connectors_data, connectors2cloud_data, networks_data = build_complex_topology_data()
    scenario = seed_competition_scenario(
        prefix,
        users_count=1,
        nodes_data_override=nodes_data,
        connectors_data_override=connectors_data,
        connectors2cloud_data_override=connectors2cloud_data,
        networks_data_override=networks_data,
    )
    register_competition_cleanup(cleanup_context, prefix, scenario)

    user = scenario.users[0]
    base_url = integration_stack["base_url"]
    pnet_proxy_url = f"{base_url}/pnetlab"
    web_session = login_to_django(base_url, user.username, INTEGRATION_TEST_PASSWORD)

    auth_response = web_session.post(f"{base_url}/api/get_pnet_auth/", json={}, timeout=15)
    assert auth_response.status_code == 200, auth_response.text

    create_response = web_session.post(
        f"{base_url}/api/create_pnet_lab_session/",
        json={"slug": scenario.competition.slug},
        timeout=20,
    )
    assert create_response.status_code == 200, create_response.text

    topology = get_lab_topology(pnet_proxy_url, web_session.cookies)
    assert topology is not None
    nodes, links = extract_nodes_and_links(topology)

    expected_nodes = [node["name"] for node in scenario.lab.NodesData if node]
    assert len(nodes) >= len(expected_nodes), "Topology must contain configured nodes"

    node_names = [node.get("name") for node in nodes if isinstance(node, dict)]
    node_names = [name for name in node_names if name]
    assert len(node_names) == len(set(node_names)), "Nodes must not be duplicated"

    link_ids = [str(link.get("id", link)) for link in links if link]
    assert len(link_ids) == len(set(link_ids)), "Links must not be duplicated"

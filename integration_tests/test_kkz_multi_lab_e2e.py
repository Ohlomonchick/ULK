import random
import time

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.pnet, pytest.mark.docker, pytest.mark.slow]


def test_kkz_creates_multiple_labs_per_user_with_topology_checks(
    django_ready, integration_stack, integration_env, pnet_admin_session, cleanup_context
):
    from interface.eveFunctions import get_lab_topology
    from interface.utils import get_pnet_lab_name
    from integration_tests.utils.db_seed import (
        INTEGRATION_TEST_PASSWORD,
        build_complex_topology_data,
        register_kkz_cleanup,
        seed_kkz_scenario,
    )
    from integration_tests.utils.pnet_cleanup import folder_contains_lab_file, login_admin_to_pnet
    from integration_tests.utils.http_client import login_to_django

    prefix = f"it-kkz-{int(time.time())}"
    nodes_data, connectors_data, connectors2cloud_data, networks_data = build_complex_topology_data()
    scenario = seed_kkz_scenario(
        prefix,
        users_count=3,
        labs_count=2,
        nodes_data_override=nodes_data,
        connectors_data_override=connectors_data,
        connectors2cloud_data_override=connectors2cloud_data,
        networks_data_override=networks_data,
    )
    register_kkz_cleanup(cleanup_context, prefix, scenario)

    competitions = list(scenario.kkz.competitions.all())
    pnet_url = pnet_admin_session["pnet_url"]
    base_dir = integration_env["PNET_BASE_DIR"]

    for competition in competitions:
        pnet_lab_name = get_pnet_lab_name(competition)
        for user in scenario.users:
            cookie, _ = login_admin_to_pnet(pnet_url)
            user_path = f"{base_dir}/{user.pnet_login}"
            assert folder_contains_lab_file(pnet_url, cookie, user_path, pnet_lab_name), (
                f"Expected KKZ lab file {pnet_lab_name}.unl for user {user.pnet_login}"
            )

    sampled_competition = random.choice(competitions)
    sampled_user = random.choice(scenario.users)

    base_url = integration_stack["base_url"]
    pnet_proxy_url = f"{base_url}/pnetlab"
    web_session = login_to_django(base_url, sampled_user.username, INTEGRATION_TEST_PASSWORD)

    auth_response = web_session.post(f"{base_url}/api/get_pnet_auth/", json={}, timeout=15)
    assert auth_response.status_code == 200, auth_response.text

    create_response = web_session.post(
        f"{base_url}/api/create_pnet_lab_session/",
        json={"slug": sampled_competition.slug},
        timeout=20,
    )
    assert create_response.status_code == 200, create_response.text

    topology = get_lab_topology(pnet_proxy_url, web_session.cookies)
    assert topology is not None

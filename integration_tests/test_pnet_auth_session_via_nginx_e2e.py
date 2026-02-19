import time

import pytest

from integration_tests.utils.http_client import login_to_django


pytestmark = [pytest.mark.integration, pytest.mark.pnet, pytest.mark.docker, pytest.mark.slow]


def test_pnet_auth_and_lab_session_via_nginx(
    django_ready, integration_stack, cleanup_context
):
    from interface.eveFunctions import get_session_id, get_session_id_by_filter
    from integration_tests.utils.db_seed import (
        INTEGRATION_TEST_PASSWORD,
        register_competition_cleanup,
        seed_competition_scenario,
    )

    prefix = f"it-auth-{int(time.time())}"
    scenario = seed_competition_scenario(prefix, users_count=1)
    register_competition_cleanup(cleanup_context, prefix, scenario)

    user = scenario.users[0]
    base_url = integration_stack["base_url"]
    pnet_proxy_url = f"{base_url}/pnetlab"
    web_session = login_to_django(base_url, user.username, INTEGRATION_TEST_PASSWORD)

    auth_response = web_session.post(f"{base_url}/api/get_pnet_auth/", json={}, timeout=15)
    assert auth_response.status_code == 200, auth_response.text
    auth_payload = auth_response.json()
    assert auth_payload.get("success") is True
    assert "cookies" in auth_payload

    whoami_response = web_session.get(f"{pnet_proxy_url}/api/auth", timeout=15)
    assert whoami_response.status_code == 200, whoami_response.text
    assert whoami_response.json().get("code") == 200

    create_session_response = web_session.post(
        f"{base_url}/api/create_pnet_lab_session/",
        json={"slug": scenario.competition.slug},
        timeout=20,
    )
    assert create_session_response.status_code == 200, create_session_response.text
    create_payload = create_session_response.json()
    assert create_payload.get("success") is True
    assert create_payload.get("lab_path")

    xsrf_token = web_session.cookies.get("XSRF-TOKEN", "")
    session_id_by_filter, error = get_session_id_by_filter(
        pnet_proxy_url, web_session.cookies, xsrf_token, create_payload["lab_path"]
    )
    assert session_id_by_filter is not None, error

    session_id_from_auth = get_session_id(pnet_proxy_url, web_session.cookies)
    assert session_id_from_auth is not None and session_id_by_filter is not None
    assert int(session_id_from_auth) == int(session_id_by_filter)

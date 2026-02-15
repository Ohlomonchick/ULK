import time

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.pnet, pytest.mark.docker, pytest.mark.slow]


def test_user_create_password_change_and_workspace_dirs(
    django_ready, integration_stack, integration_env, pnet_admin_session, cleanup_context
):
    """Create user via CustomUserCreationForm (service); form creates PNET dir and user. Then change password and assert workspace."""
    from interface.forms import CustomUserCreationForm
    from interface.models import Platoon
    from interface.eveFunctions import (
        change_user_password,
        get_folders,
        get_user_params,
        login_user_to_pnet,
    )
    from interface.pnet_session_manager import reset_admin_pnet_session
    from integration_tests.utils.pnet_cleanup import login_admin_to_pnet
    from integration_tests.utils.db_seed import INTEGRATION_TEST_PASSWORD

    prefix = f"it-user-{int(time.time())}"
    username = prefix
    old_password = INTEGRATION_TEST_PASSWORD
    new_password = "Passw0rd!456"

    pnet_url = pnet_admin_session["pnet_url"]
    base_dir = integration_env["PNET_BASE_DIR"]

    reset_admin_pnet_session()
    platoon = Platoon.objects.get_or_create(number=0)[0]
    form_data = {
        "username": username,
        "first_name": "Test",
        "last_name": "User",
        "platoon": platoon.pk,
        "password1": old_password,
        "password2": old_password,
    }
    form = CustomUserCreationForm(data=form_data)
    assert form.is_valid(), f"CustomUserCreationForm errors: {form.errors}"
    user = form.save()
    assert user.pnet_login, "Form must set pnet_login (slugify username)"

    full_workspace = f"{base_dir.rstrip('/')}/{user.pnet_login}"
    cleanup_context["users"].add(user.pnet_login)
    cleanup_context["folders"].add(full_workspace)

    admin_cookie, xsrf = login_admin_to_pnet(pnet_url)
    password_response = change_user_password(
        pnet_url, admin_cookie, xsrf, user.pnet_login, new_password
    )
    assert password_response is not None, "Password change response must not be None"
    assert password_response.status_code in range(200, 400), password_response.text

    user_session, _ = login_user_to_pnet(pnet_url, user.pnet_login, new_password)
    assert user_session is not None, "User must be able to login with new password"

    admin_cookie, xsrf = login_admin_to_pnet(pnet_url)
    user_params = get_user_params(pnet_url, admin_cookie, xsrf, user.pnet_login)
    assert user_params is not None, "PNET user params must be returned"
    assert user_params.get("user_workspace"), "User workspace must be configured"
    assert user_params["user_workspace"].rstrip("/").endswith(user.pnet_login)

    workspace_response = get_folders(pnet_url, full_workspace, admin_cookie)
    assert workspace_response.status_code != 404, (
        f"Workspace folder '{full_workspace}' is not found (form must create it via create_directory): {workspace_response.text}"
    )

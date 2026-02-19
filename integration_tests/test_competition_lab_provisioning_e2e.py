import time

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.pnet, pytest.mark.docker, pytest.mark.slow]


def test_competition_form_creates_lab_for_each_user(
    django_ready, integration_stack, integration_env, pnet_admin_session, cleanup_context
):
    from interface.utils import get_pnet_lab_name
    from integration_tests.utils.db_seed import (
        register_competition_cleanup,
        seed_competition_scenario,
    )
    from integration_tests.utils.pnet_cleanup import folder_contains_lab_file

    prefix = f"it-comp-{int(time.time())}"
    scenario = seed_competition_scenario(prefix, users_count=3)
    register_competition_cleanup(cleanup_context, prefix, scenario)

    pnet_url = pnet_admin_session["pnet_url"]
    cookie = pnet_admin_session["cookie"]
    base_dir = integration_env["PNET_BASE_DIR"]
    pnet_lab_name = get_pnet_lab_name(scenario.competition)

    for user in scenario.users:
        user_path = f"{base_dir}/{user.pnet_login}"
        assert folder_contains_lab_file(pnet_url, cookie, user_path, pnet_lab_name), (
            f"Expected lab file under {user_path}"
        )


def test_team_workspace_switch_and_restore_on_delete(
    django_ready, integration_stack, integration_env, pnet_admin_session, cleanup_context
):
    from interface.eveFunctions import get_user_workspace_relative_path
    from integration_tests.utils.db_seed import (
        register_team_competition_cleanup,
        seed_team_competition_scenario,
    )
    from integration_tests.utils.pnet_cleanup import get_user_workspace, login_admin_to_pnet

    prefix = f"it-team-{int(time.time())}"
    scenario = seed_team_competition_scenario(prefix, team_size=2)
    register_team_competition_cleanup(cleanup_context, prefix, scenario)

    pnet_url = pnet_admin_session["pnet_url"]
    base_relative_path = get_user_workspace_relative_path().rstrip("/")
    base_dir = integration_env["PNET_BASE_DIR"]
    for user in scenario.team_users:
        cookie, xsrf = login_admin_to_pnet(pnet_url)
        current_workspace = get_user_workspace(
            pnet_url, cookie, xsrf, user.pnet_login, base_dir=base_dir
        )
        assert current_workspace is not None, (
            f"get_user_workspace returned None for {user.pnet_login}; ensure user exists in PNET"
        )
        assert current_workspace.endswith(f"/{scenario.team.slug}")

    scenario.competition.delete()

    for user in scenario.team_users:
        cookie, xsrf = login_admin_to_pnet(pnet_url)
        current_workspace = get_user_workspace(
            pnet_url, cookie, xsrf, user.pnet_login, base_dir=base_dir
        )
        assert current_workspace is not None, (
            f"After competition delete: get_user_workspace returned None for {user.pnet_login}"
        )
        assert current_workspace.endswith(f"/{user.pnet_login}")
        assert base_relative_path in current_workspace

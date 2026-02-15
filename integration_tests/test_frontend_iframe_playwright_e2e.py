import time

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.pnet, pytest.mark.docker, pytest.mark.slow]


def _launch_browser_or_skip():
    playwright = pytest.importorskip("playwright.sync_api")
    pw = None
    try:
        pw = playwright.sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        return pw, browser
    except Exception as exc:  # noqa: BLE001
        if pw is not None:
            pw.stop()
        pytest.skip(f"Playwright chromium is not available: {exc}")


def _login_in_ui(page, base_url: str, username: str, password: str) -> None:
    page.goto(f"{base_url}/accounts/login/", wait_until="domcontentloaded")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"], input[type="submit"]')
    page.wait_for_load_state("networkidle")


def _activate_competition_now(competition) -> None:
    from datetime import timedelta
    from django.utils import timezone

    competition.start = timezone.now() - timedelta(minutes=1)
    competition.finish = timezone.now() + timedelta(hours=2)
    competition.save(update_fields=["start", "finish"])


def _wait_for_iframe_src(page, expected_substring: str, timeout_ms: int = 120000) -> str:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        src = page.eval_on_selector("#pnetFrame", "el => el.getAttribute('src') || ''")
        if expected_substring in src:
            return src
        page.wait_for_timeout(500)
    raise AssertionError(f"iframe src does not contain '{expected_substring}' within timeout")


def test_pnet_frontend_loads_topology_iframe_for_regular_user(
    django_ready, integration_stack, cleanup_context
):
    from integration_tests.utils.db_seed import (
        INTEGRATION_TEST_PASSWORD,
        register_competition_cleanup,
        seed_competition_scenario,
    )

    prefix = f"it-pw-pn-{int(time.time())}"
    scenario = seed_competition_scenario(prefix, users_count=1)
    _activate_competition_now(scenario.competition)
    register_competition_cleanup(cleanup_context, prefix, scenario)

    user = scenario.users[0]
    base_url = integration_stack["base_url"]

    pw, browser = _launch_browser_or_skip()
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    try:
        _login_in_ui(page, base_url, user.username, INTEGRATION_TEST_PASSWORD)

        page.goto(
            f"{base_url}/cyberpolygon/competitions/{scenario.competition.slug}/",
            wait_until="domcontentloaded",
        )
        page.wait_for_selector("#pnetFrame", timeout=120000)

        page.wait_for_response(
            lambda r: r.url.endswith("/api/create_pnet_lab_session/") and r.status == 200,
            timeout=120000,
        )
        iframe_src = _wait_for_iframe_src(page, "/pnetlab/")
        assert "/pnetlab/" in iframe_src
    finally:
        context.close()
        browser.close()
        pw.stop()


def test_cmd_frontend_loads_guacamole_iframe_for_regular_user(
    django_ready, integration_stack, cleanup_context
):
    from interface.models import Lab
    from integration_tests.utils.db_seed import (
        INTEGRATION_TEST_PASSWORD,
        register_competition_cleanup,
        seed_competition_scenario,
    )

    prefix = f"it-pw-cmd-{int(time.time())}"
    scenario = seed_competition_scenario(prefix, users_count=1, platform="CMD")
    _activate_competition_now(scenario.competition)
    # Явно задаем SSH ноду для CMD flow.
    Lab.objects.filter(pk=scenario.lab.pk).update(PnetSSHNodeName="node-a")
    register_competition_cleanup(cleanup_context, prefix, scenario)

    user = scenario.users[0]
    base_url = integration_stack["base_url"]

    pw, browser = _launch_browser_or_skip()
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    try:
        _login_in_ui(page, base_url, user.username, INTEGRATION_TEST_PASSWORD)

        page.goto(
            f"{base_url}/cyberpolygon/competitions/{scenario.competition.slug}/",
            wait_until="domcontentloaded",
        )
        page.wait_for_selector("#pnetFrame", timeout=120000)

        page.wait_for_response(
            lambda r: r.url.endswith("/api/create_pnet_lab_session_with_console/") and r.status == 200,
            timeout=120000,
        )
        iframe_src = _wait_for_iframe_src(page, "guacamole")
        assert "guacamole" in iframe_src
    finally:
        context.close()
        browser.close()
        pw.stop()


def test_pz_admin_sees_pnet_iframe_and_topology_session_flow(
    django_ready, integration_stack, cleanup_context
):
    from integration_tests.utils.db_seed import (
        INTEGRATION_TEST_PASSWORD,
        register_competition_cleanup,
        seed_competition_scenario,
    )

    prefix = f"it-pw-pz-admin-{int(time.time())}"
    scenario = seed_competition_scenario(prefix, users_count=1, lab_type="PZ", platform="PN")
    _activate_competition_now(scenario.competition)
    register_competition_cleanup(cleanup_context, prefix, scenario)

    admin_user = scenario.users[0]
    admin_user.is_superuser = True
    admin_user.is_staff = True
    admin_user.save(update_fields=["is_superuser", "is_staff"])

    base_url = integration_stack["base_url"]

    pw, browser = _launch_browser_or_skip()
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    try:
        _login_in_ui(page, base_url, admin_user.username, INTEGRATION_TEST_PASSWORD)

        page.goto(
            f"{base_url}/cyberpolygon/competitions/{scenario.competition.slug}/",
            wait_until="domcontentloaded",
        )
        page.wait_for_selector("#pnetFrame", timeout=120000)

        page.wait_for_response(
            lambda r: r.url.endswith("/api/create_pnet_lab_session/") and r.status == 200,
            timeout=120000,
        )
        iframe_src = _wait_for_iframe_src(page, "/pnetlab/")
        assert "/pnetlab/" in iframe_src
    finally:
        context.close()
        browser.close()
        pw.stop()

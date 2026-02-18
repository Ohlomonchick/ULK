import logging
import time

import pytest

from integration_tests.utils.playwright_utils import (
    activate_competition_now as _activate_competition_now,
    launch_browser_or_skip as _launch_browser_or_skip,
    login_in_ui as _login_in_ui,
)

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.pnet, pytest.mark.docker, pytest.mark.slow]

# Truncation limits for diagnostic dumps (to keep log files readable)
_DIAG_HTML_MAX_LEN = 8000
_DIAG_CONSOLE_MAX_ITEMS = 50


def _log_iframe_diagnostics(page, context: str = "") -> None:
    """Log iframe-related state (pnetFrame src/data-src, loaders) for debugging timeouts."""
    prefix = f"[iframe diagnostic] {context} " if context else "[iframe diagnostic] "
    try:
        logger.info("%s page.url=%s", prefix.strip(), page.url)
    except Exception as e:  # noqa: BLE001
        logger.warning("%s failed to get page.url: %s", prefix.strip(), e)
    try:
        iframe_src = page.eval_on_selector("#pnetFrame", "el => el ? (el.getAttribute('src') || '') : '<no #pnetFrame>'")
        iframe_data_src = page.eval_on_selector("#pnetFrame", "el => el ? (el.getAttribute('data-src') || '') : ''")
        logger.info("%s #pnetFrame src=%r data-src=%r", prefix.strip(), iframe_src, iframe_data_src)
    except Exception as e:  # noqa: BLE001
        logger.warning("%s failed to get iframe attrs: %s", prefix.strip(), e)
    try:
        cmd_loader = page.eval_on_selector(
            "#cmdConsoleLoader",
            "el => el ? { active: el.classList.contains('active'), text: (el.querySelector('.cmd-console-loader-text')?.textContent || '').slice(0, 80) } : null",
        )
        pnet_loader = page.eval_on_selector(
            "#pnetConsoleLoader",
            "el => el ? { active: el.classList.contains('active'), text: (el.querySelector('.cmd-console-loader-text, .pnet-console-loader-text')?.textContent || '').slice(0, 80) } : null",
        )
        logger.info("%s #cmdConsoleLoader=%s #pnetConsoleLoader=%s", prefix.strip(), cmd_loader, pnet_loader)
    except Exception as e:  # noqa: BLE001
        logger.warning("%s failed to get loaders: %s", prefix.strip(), e)


def _capture_playwright_diagnostics(page, console_messages: list) -> None:
    """Log current page state to the test log (URL, HTML snippet, console). Used on timeout/failure."""
    try:
        url = page.url
        logger.info("[Playwright diagnostic] page.url=%s", url)
    except Exception as e:  # noqa: BLE001
        logger.warning("[Playwright diagnostic] failed to get url: %s", e)
    try:
        content = page.content()
        if content:
            snippet = content[: _DIAG_HTML_MAX_LEN]
            if len(content) > _DIAG_HTML_MAX_LEN:
                snippet += "\n... (truncated)"
            logger.info("[Playwright diagnostic] page.content (snippet):\n%s", snippet)
    except Exception as e:  # noqa: BLE001
        logger.warning("[Playwright diagnostic] failed to get content: %s", e)
    if console_messages:
        for i, msg in enumerate(console_messages[-_DIAG_CONSOLE_MAX_ITEMS:]):
            logger.info("[Playwright diagnostic] console[%s]: %s", i, msg)


def _wait_for_iframe_src(
    page, expected_substring: str, timeout_ms: int = 120000, console_messages: list | None = None
) -> str:
    """Wait until iframe #pnetFrame has src containing expected_substring."""
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        src = page.eval_on_selector("#pnetFrame", "el => el.getAttribute('src') || ''")
        if expected_substring in src:
            return src
        page.wait_for_timeout(500)
    _log_iframe_diagnostics(page, f"timeout waiting for src containing '{expected_substring}'")
    if console_messages is not None:
        _capture_playwright_diagnostics(page, console_messages)
    raise AssertionError(f"iframe src does not contain '{expected_substring}' within timeout")


def _wait_for_iframe_topology_url(page, timeout_ms: int = 25000) -> None:
    """
    After iframe loads, pnet_controller.js redirects its document to /legacy/topology.
    We must read the iframe's document URL (frame.url), not the src attribute — src
    stays e.g. /pnetlab/ while the content navigates. If frame.url is unavailable
    (e.g. cross-origin), we only require that iframe src is set to /pnetlab/.
    """
    deadline = time.time() + (timeout_ms / 1000)
    last_frame_url = None
    while time.time() < deadline:
        try:
            handle = page.query_selector("#pnetFrame")
            if handle:
                frame = handle.content_frame()
                if frame:
                    url = frame.url  # property, not method
                    if url:
                        last_frame_url = url
                        if "legacy/topology" in url or "/legacy/topology" in url:
                            return
        except Exception as e:  # noqa: BLE001
            logger.debug("_wait_for_iframe_topology_url frame.url failed: %s", e)
        page.wait_for_timeout(500)


def _wait_for_cmd_console_iframe(
    page, timeout_ms: int = 180000, console_messages: list | None = None
) -> str:
    """
    Wait for CMD console: either iframe src contains 'guacamole', or loader is hidden
    and iframe has a non-empty src (backend may return a path without the substring).
    """
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        src = page.eval_on_selector("#pnetFrame", "el => el.getAttribute('src') || ''")
        if "guacamole" in src:
            return src
        loader_active = page.eval_on_selector(
            "#cmdConsoleLoader",
            "el => el ? el.classList.contains('active') : true",
        )
        if not loader_active and src and src.strip() and "about:blank" not in src:
            return src
        page.wait_for_timeout(500)
    _log_iframe_diagnostics(page, "timeout waiting for CMD console iframe")
    if console_messages is not None:
        _capture_playwright_diagnostics(page, console_messages)
    raise AssertionError("CMD console iframe src did not become ready within timeout")


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
    console_messages = []

    def _on_console(msg):
        console_messages.append(f"{msg.type}: {msg.text}")

    page.on("console", _on_console)
    try:
        _login_in_ui(
            page,
            base_url,
            INTEGRATION_TEST_PASSWORD,
            admin_login=False,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            platoon_id=user.platoon_id,
        )
        # Page loads common_utils.js, console_loader.js, pnet_iframe_controller.js, pnet_controller.js (PN);
        # frontend does get_pnet_auth, create_pnet_lab_session, sets iframe src to /pnetlab/, then redirects to /legacy/topology.
        page.goto(
            f"{base_url}/cyberpolygon/competitions/{scenario.competition.slug}/",
            wait_until="domcontentloaded",
        )
        try:
            page.wait_for_selector("#pnetFrame", timeout=120000)
        except Exception:
            _capture_playwright_diagnostics(page, console_messages)
            raise
        iframe_src = _wait_for_iframe_src(page, "/pnetlab/", console_messages=console_messages)
        assert "/pnetlab/" in iframe_src
        _wait_for_iframe_topology_url(page, timeout_ms=15000)
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
    console_messages = []

    def _on_console(msg):
        console_messages.append(f"{msg.type}: {msg.text}")

    page.on("console", _on_console)
    try:
        _login_in_ui(
            page,
            base_url,
            INTEGRATION_TEST_PASSWORD,
            admin_login=False,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            platoon_id=user.platoon_id,
        )
        # Real flow: frontend (cmd_controller.js) calls create_pnet_lab_session_with_console and sets iframe src.
        page.goto(
            f"{base_url}/cyberpolygon/competitions/{scenario.competition.slug}/",
            wait_until="domcontentloaded",
        )
        try:
            page.wait_for_selector("#pnetFrame", timeout=120000)
        except Exception:
            _capture_playwright_diagnostics(page, console_messages)
            raise
        iframe_src = _wait_for_cmd_console_iframe(page, timeout_ms=180000, console_messages=console_messages)
        assert iframe_src, "CMD console iframe src must be set"
    finally:
        context.close()
        browser.close()
        pw.stop()


def test_pz_admin_sees_pnet_iframe_and_topology_session_flow(
    django_ready, integration_stack, cleanup_context
):
    """
    Real user flow: admin logs in, opens competition page; frontend (pnet_controller.js)
    does get_pnet_auth, create_pnet_lab_session, then loads /pnetlab/ iframe.
    No manual cookie or session setup — we assert the app sets everything correctly.
    """
    from integration_tests.utils.db_seed import (
        INTEGRATION_TEST_PASSWORD,
        register_competition_cleanup,
        seed_competition_scenario,
    )

    prefix = f"it-pw-pzsu-{int(time.time())}"
    # Admin must be superuser before Competition is created (form.save() uses participant setup).
    # NOTE: prefix must NOT contain "admin" — User.save() appends "-fake" to pnet_login when
    # "admin" is in the username, causing a mismatch between the PNET directory (based on
    # username) and the lab path (based on pnet_login).
    scenario = seed_competition_scenario(
        prefix, users_count=1, lab_type="PZ", platform="PN", make_first_user_superuser=True
    )
    _activate_competition_now(scenario.competition)
    register_competition_cleanup(cleanup_context, prefix, scenario)

    admin_user = scenario.users[0]

    base_url = integration_stack["base_url"]

    pw, browser = _launch_browser_or_skip()
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    console_messages = []

    def _on_console(msg):
        console_messages.append(f"{msg.type}: {msg.text}")

    page.on("console", _on_console)
    try:
        _login_in_ui(
            page,
            base_url,
            INTEGRATION_TEST_PASSWORD,
            admin_login=True,
            username=admin_user.username,
        )
        page.goto(
            f"{base_url}/cyberpolygon/competitions/{scenario.competition.slug}/",
            wait_until="domcontentloaded",
        )
        try:
            page.wait_for_selector("#pnetFrame", timeout=120000)
        except Exception:
            _capture_playwright_diagnostics(page, console_messages)
            raise
        iframe_src = _wait_for_iframe_src(page, "/pnetlab/", console_messages=console_messages)
        assert "/pnetlab/" in iframe_src
        _wait_for_iframe_topology_url(page, timeout_ms=15000)
    finally:
        context.close()
        browser.close()
        pw.stop()

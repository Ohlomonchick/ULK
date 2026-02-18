"""Общие хелперы для e2e-тестов с Playwright (браузер, логин, активация соревнования)."""

from __future__ import annotations

import logging
import os

import pytest

logger = logging.getLogger(__name__)


def launch_browser_or_skip():
    """Запускает Chromium через Playwright или пропускает тест, если недоступен."""
    playwright = pytest.importorskip("playwright.sync_api")
    pw = None
    headless = os.environ.get("E2E_OPEN_BROWSER") != "1"
    try:
        pw = playwright.sync_playwright().start()
        browser = pw.chromium.launch(headless=headless)
        return pw, browser
    except Exception as exc:  # noqa: BLE001
        if pw is not None:
            pw.stop()
        pytest.skip(f"Playwright chromium is not available: {exc}")


def login_in_ui(
    page,
    base_url: str,
    password: str,
    *,
    admin_login: bool = False,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    platoon_id: int | None = None,
) -> None:
    """
    Выполняет вход в UI: либо форма логина в браузере, либо fallback через requests
    (cookie подставляются в контекст страницы).
    """
    login_url = f"{base_url}/accounts/login/" if admin_login else f"{base_url}/"
    page.goto(login_url, wait_until="domcontentloaded")
    if admin_login:
        if not username:
            raise AssertionError("username is required for admin login")
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', password)
    else:
        if not first_name or not last_name:
            raise AssertionError("first_name/last_name are required for student login")
        page.fill('input[name="first_name"]', first_name)
        page.fill('input[name="last_name"]', last_name)
        page.fill('input[name="password"]', password)
        if platoon_id is not None:
            page.select_option('select[name="platoon"]', str(platoon_id))

    page.click('button[type="submit"], input[type="submit"]')
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:  # noqa: BLE001
        pass
    page.wait_for_timeout(500)

    current_url = page.url
    has_session_cookie = any(cookie.get("name") == "sessionid" for cookie in page.context.cookies())
    student_stuck = (not admin_login) and current_url.rstrip("/") == base_url.rstrip("/")
    admin_stuck = admin_login and "/accounts/login/" in current_url
    if student_stuck or admin_stuck or not has_session_cookie:
        from integration_tests.utils.http_client import login_to_django

        if not username:
            raise AssertionError("username is required for login fallback")
        logger.warning(
            "UI login fallback triggered for user %s (admin=%s, url=%s)",
            username,
            admin_login,
            page.url,
        )
        # Fallback через /accounts/login/ работает для любого пользователя
        # (не только staff): использует настоящий username, минуя student-форму ("/"),
        # которая ищет по last_name + "_" + first_name — это не совпадает
        # с тестовыми пользователями, у которых username задан явно через db_seed.
        web_session = login_to_django(base_url, username, password)
        cookies = [
            {"name": c.name, "value": c.value, "url": base_url}
            for c in web_session.cookies
            if c.name in {"sessionid", "csrftoken"}
        ]
        if not cookies:
            raise AssertionError(
                f"Login did not succeed and no auth cookies were obtained (url={page.url})"
            )
        page.context.add_cookies(cookies)
        page.goto(f"{base_url}/cyberpolygon/labs/", wait_until="domcontentloaded")
        if "/accounts/login/" in page.url:
            raise AssertionError(f"Login did not succeed after fallback (url={page.url})")


def activate_competition_now(competition) -> None:
    """Переводит соревнование в активное состояние (start в прошлом, finish в будущем)."""
    from datetime import timedelta

    from django.utils import timezone

    competition.start = timezone.now() - timedelta(minutes=1)
    competition.finish = timezone.now() + timedelta(hours=2)
    competition.save(update_fields=["start", "finish"])

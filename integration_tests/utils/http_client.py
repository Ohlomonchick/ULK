"""HTTP helpers for integration e2e tests."""

from __future__ import annotations

import requests


def login_to_django(base_url: str, username: str, password: str) -> requests.Session:
    session = requests.Session()
    login_page = session.get(f"{base_url}/accounts/login/", timeout=10)
    login_page.raise_for_status()
    csrf_token = session.cookies.get("csrftoken", "")

    response = session.post(
        f"{base_url}/accounts/login/",
        data={
            "csrfmiddlewaretoken": csrf_token,
            "username": username,
            "password": password,
            "next": "/cyberpolygon/labs/",
        },
        headers={
            "Referer": f"{base_url}/accounts/login/",
            "X-CSRFToken": csrf_token,
        },
        timeout=10,
        allow_redirects=False,
    )
    if response.status_code not in (302, 303):
        raise AssertionError(f"Django login failed: {response.status_code} {response.text}")
    # Use CSRF token from cookie so subsequent API POSTs succeed (Django expects X-CSRFToken header).
    token = session.cookies.get("csrftoken") or csrf_token
    session.headers.setdefault("X-CSRFToken", token)
    session.headers.setdefault("Referer", f"{base_url}/")
    return session

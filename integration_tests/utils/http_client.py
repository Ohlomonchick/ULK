"""HTTP helpers for integration e2e tests."""

from __future__ import annotations

import re
import requests


def login_to_django(base_url: str, username: str, password: str) -> requests.Session:
    """
    Login via Django admin form (POST /accounts/login/ with username + password).
    Use only for staff/superuser. For students use login_to_django_as_student.
    """
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
    redirect_to = response.headers.get("Location", "")
    if "/accounts/login/" in redirect_to:
        raise AssertionError(
            f"Django login rejected credentials for '{username}': redirected back to login ({redirect_to})"
        )
    # Use CSRF token from cookie so subsequent API POSTs succeed (Django expects X-CSRFToken header).
    token = session.cookies.get("csrftoken") or csrf_token
    session.headers.setdefault("X-CSRFToken", token)
    session.headers.setdefault("Referer", f"{base_url}/")
    return session


def login_to_django_as_student(
    base_url: str,
    first_name: str,
    last_name: str,
    password: str,
    platoon_id: int | None = None,
) -> requests.Session:
    """
    Login via student form (POST / with first_name, last_name, password, platoon).
    Use for regular/team users. Server expects form fields as on the root page.
    """
    session = requests.Session()
    login_page = session.get(base_url.rstrip("/") + "/", timeout=10)
    login_page.raise_for_status()
    csrf_token = session.cookies.get("csrftoken", "")
    match = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', login_page.text)
    if match:
        csrf_token = match.group(1)

    data = {
        "csrfmiddlewaretoken": csrf_token,
        "first_name": first_name,
        "last_name": last_name,
        "password": password,
    }
    if platoon_id is not None:
        data["platoon"] = str(platoon_id)

    response = session.post(
        base_url.rstrip("/") + "/",
        data=data,
        headers={
            "Referer": f"{base_url}/",
            "X-CSRFToken": csrf_token,
        },
        timeout=10,
        allow_redirects=False,
    )
    if response.status_code not in (302, 303):
        raise AssertionError(
            f"Django student login failed: {response.status_code} {response.text}"
        )
    redirect_to = response.headers.get("Location", "")
    if redirect_to and "/accounts/login/" in redirect_to:
        raise AssertionError(
            f"Django rejected student credentials (redirect: {redirect_to})"
        )
    token = session.cookies.get("csrftoken") or csrf_token
    session.headers.setdefault("X-CSRFToken", token)
    session.headers.setdefault("Referer", f"{base_url}/")
    return session

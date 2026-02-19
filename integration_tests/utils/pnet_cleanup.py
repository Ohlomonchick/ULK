"""PNET cleanup/assert helpers for integration tests."""

from __future__ import annotations

import logging
import os
from typing import Iterable

from interface.eveFunctions import (
    delete_folder,
    delete_lab_with_session_destroy,
    delete_user,
    get_folders,
    get_session_id_by_filter,
    get_user_params,
    pf_login,
)


def login_admin_to_pnet(pnet_url: str):
    login = os.environ.get("PNET_ADMIN_LOGIN", "pnet_scripts")
    password = os.environ.get("PNET_ADMIN_PASSWORD", "eve")
    return pf_login(pnet_url, login, password)


def _is_auth_failure_response(response) -> bool:
    if response is None:
        return True
    if response.status_code in (302, 401, 403, 412):
        return True
    content_type = (response.headers.get("content-type") or "").lower()
    if "text/html" in content_type:
        return True
    body = (response.text or "").lower()
    return "login/offline" in body or "not authenticated" in body


def safe_delete_users(pnet_url: str, cookie, xsrf: str, users: Iterable[str]) -> None:
    log = logging.getLogger(__name__)
    current_cookie, current_xsrf = cookie, xsrf
    for username in users:
        if not username:
            continue
        try:
            response = delete_user(pnet_url, current_cookie, current_xsrf, username)
            if response is not None and _is_auth_failure_response(response):
                current_cookie, current_xsrf = login_admin_to_pnet(pnet_url)
                response = delete_user(pnet_url, current_cookie, current_xsrf, username)
            if response is not None and response.status_code not in range(200, 400):
                log.warning("Cleanup: delete_user(%s) failed: %s %s", username, response.status_code, response.text)
        except Exception as exc:
            log.warning("Cleanup: delete_user(%s) exception: %s", username, exc)


def safe_delete_labs(pnet_url: str, cookie, xsrf: str, base_dir: str, pairs: Iterable[tuple[str, str]]) -> None:
    log = logging.getLogger(__name__)
    current_cookie, current_xsrf = cookie, xsrf
    for lab_name, username_or_team in pairs:
        if not lab_name or not username_or_team:
            continue
        try:
            delete_lab_with_session_destroy(
                pnet_url,
                lab_name,
                base_dir,
                current_cookie,
                current_xsrf,
                username_or_team,
            )
        except (Exception, TypeError) as exc:
            try:
                current_cookie, current_xsrf = login_admin_to_pnet(pnet_url)
                delete_lab_with_session_destroy(
                    pnet_url,
                    lab_name,
                    base_dir,
                    current_cookie,
                    current_xsrf,
                    username_or_team,
                )
            except (Exception, TypeError) as exc2:
                log.warning(
                    "Cleanup: delete_lab(%s, %s) failed: %s; retry: %s",
                    lab_name,
                    username_or_team,
                    exc,
                    exc2,
                )


def safe_delete_folders(pnet_url: str, cookie, folders: Iterable[str]) -> None:
    log = logging.getLogger(__name__)
    current_cookie = cookie
    for folder_path in folders:
        if not folder_path or not isinstance(folder_path, str):
            continue
        try:
            response = delete_folder(pnet_url, folder_path, current_cookie)
            if _is_auth_failure_response(response):
                current_cookie, _ = login_admin_to_pnet(pnet_url)
                response = delete_folder(pnet_url, folder_path, current_cookie)
            if response is not None and response.status_code not in range(200, 400):
                log.warning("Cleanup: delete_folder(%s) failed: %s %s", folder_path, response.status_code, response.text)
        except Exception as exc:
            log.warning("Cleanup: delete_folder(%s) exception: %s", folder_path, exc)


def folder_contains_lab_file(pnet_url: str, cookie, path: str, lab_pnet_slug: str) -> bool:
    norm_path = _normalize_path(path)
    response = get_folders(pnet_url, norm_path, cookie)
    if _is_auth_failure_response(response):
        fresh_cookie, _ = login_admin_to_pnet(pnet_url)
        response = get_folders(pnet_url, norm_path, fresh_cookie)
    if response is None or response.status_code != 200:
        return False
    try:
        body = response.json()
    except (ValueError, TypeError):
        return False
    if not isinstance(body, dict):
        return False
    payload = body.get("data", {}) or {}
    expected_name = f"{lab_pnet_slug}.unl"
    files = payload.get("files", []) or []
    if any(isinstance(item, dict) and item.get("name") == expected_name for item in files):
        return True
    # PNET may return .unl files under "labs" with "file" key (e.g. {"file": "lab.unl"}).
    labs = payload.get("labs", []) or []
    return any(
        isinstance(item, dict) and (item.get("file") == expected_name or item.get("name") == expected_name)
        for item in labs
    )


def _normalize_path(path: str) -> str:
    p = ("/" + (path or "").strip()).strip("/")
    return "/" + p if p else "/"


def get_user_workspace(
    pnet_url: str,
    cookie,
    xsrf: str,
    pnet_login: str,
    *,
    base_dir: str | None = None,
) -> str | None:
    try:
        data = get_user_params(pnet_url, cookie, xsrf, pnet_login)
    except Exception:
        fresh_cookie, fresh_xsrf = login_admin_to_pnet(pnet_url)
        try:
            data = get_user_params(pnet_url, fresh_cookie, fresh_xsrf, pnet_login)
        except Exception:
            data = None
    if not data or not isinstance(data, dict):
        return None
    workspace = data.get("user_workspace")
    if not workspace or not isinstance(workspace, str):
        return None
    workspace = _normalize_path(workspace)
    if base_dir:
        base = _normalize_path(base_dir).rstrip("/")
        if base and not workspace.startswith(base):
            workspace = f"{base}/{workspace.lstrip('/')}"
    return workspace


def resolve_session_id_for_lab(pnet_url: str, cookie, xsrf: str, lab_path: str):
    session_id, _ = get_session_id_by_filter(pnet_url, cookie, xsrf, lab_path)
    return session_id

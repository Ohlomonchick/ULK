"""Helpers for deterministic directory provisioning in PNET."""

from __future__ import annotations

import time

from interface.eveFunctions import get_folders


class PnetDirectoryProvisionError(RuntimeError):
    """Raised when directory cannot be created or validated in PNET."""


def _normalize_path(path: str) -> str:
    normalized = "/" + path.strip("/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized


def _join_path(parent_path: str, segment: str) -> str:
    parent = _normalize_path(parent_path)
    clean_segment = segment.strip("/")
    if parent == "/":
        return f"/{clean_segment}"
    return f"{parent}/{clean_segment}"


def _list_folder_names(pnet_url: str, cookie, parent_path: str) -> list[str]:
    normalized_parent = _normalize_path(parent_path)
    response = get_folders(pnet_url, normalized_parent, cookie)
    if response.status_code != 200:
        raise PnetDirectoryProvisionError(
            f"Cannot list folders for '{normalized_parent}'. "
            f"HTTP {response.status_code}: {response.text}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise PnetDirectoryProvisionError(
            f"Cannot parse folders response for '{normalized_parent}': {response.text}"
        ) from exc

    folders = payload.get("data", {}).get("folders", []) or []
    return [item.get("name") for item in folders if item.get("name")]


def _create_child_directory(pnet_url: str, cookie, parent_path: str, dir_name: str):
    import requests

    response = requests.post(
        f"{pnet_url}/api/folders/add",
        json={"path": _normalize_path(parent_path), "name": dir_name},
        headers={"content-type": "application/json"},
        cookies=cookie,
        verify=False,
        timeout=10,
    )
    return response


def ensure_directory_path(
    pnet_url: str,
    cookie,
    directory_path: str,
    *,
    verification_attempts: int = 10,
    verification_delay: float = 0.5,
) -> None:
    """
    Ensures that absolute directory path exists in PNET.

    Creates path recursively and verifies each segment after creation.
    """
    target = _normalize_path(directory_path)
    if target == "/":
        return

    current_parent = "/"
    for segment in [part for part in target.strip("/").split("/") if part]:
        if segment not in _list_folder_names(pnet_url, cookie, current_parent):
            create_response = _create_child_directory(pnet_url, cookie, current_parent, segment)
            if create_response.status_code not in range(200, 400):
                raise PnetDirectoryProvisionError(
                    f"Failed to create '{segment}' under '{current_parent}'. "
                    f"HTTP {create_response.status_code}: {create_response.text}"
                )

        for _ in range(verification_attempts):
            if segment in _list_folder_names(pnet_url, cookie, current_parent):
                break
            time.sleep(verification_delay)
        else:
            raise PnetDirectoryProvisionError(
                f"Directory '{segment}' is not visible under '{current_parent}' "
                "after create/check sequence."
            )

        current_parent = _join_path(current_parent, segment)

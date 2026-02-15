"""Helpers for PNET lab topology assertions in integration tests."""

from __future__ import annotations


def extract_nodes_and_links(topology_payload: dict) -> tuple[list, list]:
    """
    Извлекает узлы и связи из ответа PNET topology API.
    Поддерживает оба варианта: data.nodes/links и data.lab.nodes/links.
    """
    data = topology_payload.get("data", topology_payload)
    nodes = data.get("nodes", [])
    links = data.get("links", [])

    if not nodes and isinstance(data.get("lab"), dict):
        nodes = data["lab"].get("nodes", [])
        links = data["lab"].get("links", links)

    return nodes or [], links or []

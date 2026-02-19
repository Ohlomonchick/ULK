"""Helpers for PNET lab topology assertions in integration tests."""

from __future__ import annotations


def extract_nodes_and_links(topology_payload: dict) -> tuple[list, list]:
    """
    Извлекает узлы и связи из ответа PNET topology API.
    Поддерживает data.nodes/links и data.lab.nodes/links.
    nodes/links могут быть списком или словарём (id -> объект); приводятся к списку.
    """
    data = topology_payload.get("data", topology_payload)
    nodes = data.get("nodes", [])
    links = data.get("links", [])

    if not nodes and isinstance(data.get("lab"), dict):
        nodes = data["lab"].get("nodes", [])
        links = data["lab"].get("links", links)

    if isinstance(nodes, dict):
        raw_nodes = nodes
        nodes = []
        for nid, n in raw_nodes.items():
            if isinstance(n, dict) and "id" not in n:
                try:
                    n = {**n, "id": int(nid)}
                except (TypeError, ValueError):
                    pass
            nodes.append(n)
    if isinstance(links, dict):
        links = list(links.values())
    if not isinstance(nodes, list):
        nodes = []
    if not isinstance(links, list):
        links = []

    return nodes or [], links or []

"""Shared diagram ancestry and sibling order for public reads and rendering."""

from collections.abc import Iterable
from xml.etree.ElementTree import Element


def ordered_nodes(
    node_ids: list[str], connections: Iterable[Element]
) -> tuple[list[str], dict[str, str]]:
    """Apply parOf srcOrd within sibling slots, retaining the flat point sequence.

    The document point is not a visible parent. Missing or tied srcOrd values
    retain point order; connections of other types never affect ancestry/order.
    """
    visible = set(node_ids)
    parents: dict[str, str] = {}
    orders: dict[str, int] = {}
    for connection in connections:
        if connection.get("type", "parOf") != "parOf":
            continue
        child = connection.get("destId")
        if child not in visible:
            continue
        parent = connection.get("srcId")
        if parent in visible:
            parents[child] = parent
        else:
            parents.pop(child, None)
        orders[child] = int(connection.get("srcOrd", "0"))
    siblings: dict[str | None, list[str]] = {}
    for node_id in node_ids:
        siblings.setdefault(parents.get(node_id), []).append(node_id)
    ordered = {
        parent: iter(sorted(children, key=lambda child: orders.get(child, 0)))
        for parent, children in siblings.items()
    }
    return [next(ordered[parents.get(node_id)]) for node_id in node_ids], parents

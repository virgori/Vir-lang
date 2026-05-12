"""
Static Subtree Hoisting — Mark/hoist static subtrees for one-time rendering.
=============================================================================
A subtree is "static" if:
  - It contains no STATE_GET, COMPUTED, EFFECT, EVENT_BIND, CONDITIONAL, or LIST
  - All children are also static

Static subtrees can be rendered once at mount time instead of on every update,
eliminating unnecessary VDOM diffing.  We mark them by setting a flag on the
root element of each static subtree (via a tag in the node name: ":static").
"""

from __future__ import annotations

from dataclasses import replace

from src.wir.module import WIRGraph
from src.wir.opcodes import WIRHOp

# Ops that make a node or its subtree "dynamic"
_DYNAMIC_OPS = frozenset({
    WIRHOp.STATE_GET,
    WIRHOp.STATE_SET,
    WIRHOp.COMPUTED,
    WIRHOp.EFFECT,
    WIRHOp.EVENT_BIND,
    WIRHOp.CONDITIONAL,
    WIRHOp.LIST,
    WIRHOp.FORM_BIND,
    WIRHOp.FORM_VALIDATE,
    WIRHOp.ROUTE_NAVIGATE,
    WIRHOp.STYLE_DYNAMIC,
})


def optimize_static_hoist(graph: WIRGraph) -> WIRGraph:
    """Mark static subtrees for one-time rendering."""

    # Build parent→children map from ELEMENT.children_ids
    children_map: dict[int, tuple[int, ...]] = {}
    for nid, h in graph.h_nodes.items():
        if h.op == WIRHOp.ELEMENT:
            children_map[nid] = h.children_ids

    # Collect nodes that are inherently dynamic
    dynamic_nodes: set[int] = set()
    for nid, h in graph.h_nodes.items():
        if h.op in _DYNAMIC_OPS:
            dynamic_nodes.add(nid)
        # Event bindings make their target element dynamic
        if h.op == WIRHOp.EVENT_BIND and h.input_ids:
            dynamic_nodes.add(h.input_ids[0])

    # Propagate dynamism upward: if any child is dynamic, parent is too
    changed = True
    while changed:
        changed = False
        for parent_id, child_ids in children_map.items():
            if parent_id in dynamic_nodes:
                continue
            for cid in child_ids:
                if cid in dynamic_nodes:
                    dynamic_nodes.add(parent_id)
                    changed = True
                    break

    # Mark static element nodes
    for nid, h in list(graph.h_nodes.items()):
        if h.op == WIRHOp.ELEMENT and nid not in dynamic_nodes:
            if h.name and ":static" not in h.name:
                graph.h_nodes[nid] = replace(h, name=h.name + ":static")

    return graph

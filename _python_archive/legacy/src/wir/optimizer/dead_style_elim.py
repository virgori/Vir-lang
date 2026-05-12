"""
Dead Style Elimination — Remove VSS class references not bound to any element.
===============================================================================
Walks all H-nodes to collect referenced VSS classes, then removes STYLE_BIND
and STYLE_DYNAMIC H-nodes whose vss_class is never referenced by an ELEMENT.
Also cleans up component metadata.
"""

from __future__ import annotations

from src.wir.module import WIRGraph
from src.wir.opcodes import WIRHOp


def optimize_dead_styles(graph: WIRGraph) -> WIRGraph:
    """Remove unreferenced style bindings from the H-graph."""

    # Step 1: Collect VSS classes actually used by ELEMENT nodes
    used_classes: set[str] = set()
    for h in graph.h_nodes.values():
        if h.op == WIRHOp.ELEMENT and h.vss_class:
            used_classes.add(h.vss_class)

    # Step 2: Find style-binding nodes whose class is NOT used
    dead_ids: list[int] = []
    for nid, h in graph.h_nodes.items():
        if h.op in (WIRHOp.STYLE_BIND, WIRHOp.STYLE_DYNAMIC, WIRHOp.STYLE_SCOPED):
            if h.vss_class and h.vss_class not in used_classes:
                dead_ids.append(nid)

    # Step 3: Remove dead nodes
    for nid in dead_ids:
        del graph.h_nodes[nid]

    # Step 4: Clean block references
    for blk in graph.blocks:
        blk.node_ids = [nid for nid in blk.node_ids if nid not in dead_ids]

    # Step 5: Prune component vss_classes lists
    for comp in graph.components.values():
        comp.vss_classes = [c for c in comp.vss_classes if c in used_classes]

    return graph

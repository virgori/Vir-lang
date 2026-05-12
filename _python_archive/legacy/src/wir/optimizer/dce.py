"""
Dead Code Elimination (DCE) — Remove H-nodes not reachable from any root.
==========================================================================
Starting from component root_node_ids and entry_node_ids, transitively mark
reachable nodes via children_ids, input_ids, deps, condition_id, items_id,
then_ids, and else_ids.  Unreachable nodes are removed.
"""

from __future__ import annotations

from src.wir.module import WIRGraph
from src.wir.opcodes import WIRHOp


def optimize_dce(graph: WIRGraph) -> WIRGraph:
    """Remove H-nodes unreachable from component roots and entry points."""

    # Collect all root node IDs
    roots: set[int] = set(graph.entry_node_ids)
    for comp in graph.components.values():
        if comp.root_node_id:
            roots.add(comp.root_node_id)
        roots.add(comp.component_id)

    # Also treat route definitions as roots
    roots.update(graph.routes)

    # If no roots, nothing to eliminate
    if not roots:
        return graph

    # BFS/DFS reachability
    reachable: set[int] = set()
    worklist = list(roots)

    while worklist:
        nid = worklist.pop()
        if nid in reachable:
            continue
        reachable.add(nid)

        h = graph.h_nodes.get(nid)
        if h is None:
            continue

        # Follow all reference edges
        for ref in h.input_ids:
            if ref and ref not in reachable:
                worklist.append(ref)
        for ref in h.output_ids:
            if ref and ref not in reachable:
                worklist.append(ref)
        for ref in h.children_ids:
            if ref and ref not in reachable:
                worklist.append(ref)
        for ref in h.deps:
            if ref and ref not in reachable:
                worklist.append(ref)
        for ref in h.then_ids:
            if ref and ref not in reachable:
                worklist.append(ref)
        for ref in h.else_ids:
            if ref and ref not in reachable:
                worklist.append(ref)
        if h.condition_id and h.condition_id not in reachable:
            worklist.append(h.condition_id)
        if h.items_id and h.items_id not in reachable:
            worklist.append(h.items_id)

    # Remove unreachable nodes
    dead = set(graph.h_nodes.keys()) - reachable
    if not dead:
        return graph

    for nid in dead:
        del graph.h_nodes[nid]

    # Clean blocks
    for blk in graph.blocks:
        blk.node_ids = [nid for nid in blk.node_ids if nid not in dead]

    return graph

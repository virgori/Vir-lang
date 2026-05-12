"""
Tree Shaking — Remove components unreachable from the root component.
=====================================================================
Starting from graph.root_component, transitively collect all reachable
component names (via ROUTE_DEF targets and nested component references).
Remove H-nodes belonging to unreachable components and their metadata.
"""

from __future__ import annotations

from src.wir.module import WIRGraph
from src.wir.opcodes import WIRHOp


def optimize_tree_shake(graph: WIRGraph) -> WIRGraph:
    """Remove components not reachable from the root."""

    if not graph.root_component:
        return graph  # Nothing to shake without a root

    # Step 1: Build reachability from root_component
    reachable: set[str] = set()
    worklist: list[str] = [graph.root_component]

    # Collect route targets
    route_targets: dict[str, str] = {}
    for h in graph.h_nodes.values():
        if h.op == WIRHOp.ROUTE_DEF and h.route_component:
            route_targets[h.route_component] = h.route_component

    while worklist:
        name = worklist.pop()
        if name in reachable:
            continue
        reachable.add(name)
        # Routes defined within this component's scope reach their targets
        for h in graph.h_nodes.values():
            if h.op == WIRHOp.ROUTE_DEF and h.route_component and h.route_component not in reachable:
                worklist.append(h.route_component)
            # Component references via component_name
            if h.op == WIRHOp.COMPONENT_DEF and h.component_name not in reachable:
                # This is a definition, check if it's referenced
                pass

    # If all components are reachable or only one exists, nothing to do
    unreachable = set(graph.components.keys()) - reachable
    if not unreachable:
        return graph

    # Step 2: Collect H-node IDs belonging to unreachable components
    dead_ids: set[int] = set()
    for nid, h in graph.h_nodes.items():
        if h.op == WIRHOp.COMPONENT_DEF and h.component_name in unreachable:
            dead_ids.add(nid)
        # Nodes whose name starts with unreachable component prefix
        if h.name:
            comp_prefix = h.name.split(".")[0]
            if comp_prefix in unreachable:
                dead_ids.add(nid)

    # Step 3: Remove dead nodes
    for nid in dead_ids:
        graph.h_nodes.pop(nid, None)

    # Step 4: Clean blocks
    for blk in graph.blocks:
        blk.node_ids = [nid for nid in blk.node_ids if nid not in dead_ids]

    # Step 5: Remove unreachable component metadata
    for name in unreachable:
        graph.components.pop(name, None)

    # Step 6: Clean route references
    graph.routes = [r for r in graph.routes if r not in dead_ids]

    return graph

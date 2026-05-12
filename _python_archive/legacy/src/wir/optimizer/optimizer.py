"""
WIR Optimizer — Multi-pass optimization pipeline for WIR-H graphs.
===================================================================
Applies web-specific optimization passes on the WIR-H level before
lowering to M/L.  Each pass is idempotent and may be run independently.

Passes (in recommended order):
  1. dead_style_elim  — Remove VSS classes not referenced by any element
  2. tree_shaking     — Remove components unreachable from root
  3. static_hoist     — Hoist static (no-state, no-event) subtrees
  4. dce              — Dead code elimination (unused nodes)
"""

from __future__ import annotations

from src.wir.module import WIRGraph
from src.wir.optimizer.dead_style_elim import optimize_dead_styles
from src.wir.optimizer.tree_shaking import optimize_tree_shake
from src.wir.optimizer.static_hoist import optimize_static_hoist
from src.wir.optimizer.dce import optimize_dce


def optimize(graph: WIRGraph, *, passes: tuple[str, ...] | None = None) -> WIRGraph:
    """Run the full WIR optimization pipeline (or selected passes).

    Args:
        graph: A WIRGraph populated with H-nodes.
        passes: Optional tuple of pass names to run. If None, run all.

    Returns:
        The same graph, mutated in place.
    """
    all_passes: tuple[tuple[str, object], ...] = (
        ("dead_style_elim", optimize_dead_styles),
        ("tree_shaking", optimize_tree_shake),
        ("static_hoist", optimize_static_hoist),
        ("dce", optimize_dce),
    )

    for name, fn in all_passes:
        if passes is None or name in passes:
            fn(graph)

    return graph

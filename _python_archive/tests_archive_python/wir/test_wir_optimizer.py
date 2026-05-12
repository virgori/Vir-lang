"""Tests for WIR optimizer passes."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.wir.module import WIRGraph
from src.wir.builder.dom_builder import DOMBuilder
from src.wir.opcodes import WIRHOp
from src.wir.optimizer.dead_style_elim import optimize_dead_styles
from src.wir.optimizer.tree_shaking import optimize_tree_shake
from src.wir.optimizer.static_hoist import optimize_static_hoist
from src.wir.optimizer.dce import optimize_dce
from src.wir.optimizer.optimizer import optimize


# ═══════════════════════════════════════════════════════════
#  Dead Style Elimination
# ═══════════════════════════════════════════════════════════


def test_dead_style_removes_unused_binding():
    """STYLE_BIND with a class not on any ELEMENT is removed."""
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div", vss_class="used")
        # This style binding references a class NOT on any element
        app.style(div_id, "orphan_class")
        app.root(div_id)

    before = b.graph.h_node_count
    optimize_dead_styles(b.graph)
    # "orphan_class" is not used as vss_class on any ELEMENT
    # whereas "used" IS on the div element
    style_nodes = [h for h in b.graph.h_nodes.values()
                   if h.op == WIRHOp.STYLE_BIND and h.vss_class == "orphan_class"]
    assert len(style_nodes) == 0


def test_dead_style_keeps_used_classes():
    """STYLE_BIND whose class matches an ELEMENT's vss_class survives."""
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div", vss_class="card")
        app.style(div_id, "card")
        app.root(div_id)

    optimize_dead_styles(b.graph)
    style_nodes = [h for h in b.graph.h_nodes.values()
                   if h.op == WIRHOp.STYLE_BIND and h.vss_class == "card"]
    assert len(style_nodes) == 1


def test_dead_style_cleans_component_metadata():
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        app.style(div_id, "dead_cls")
        app.root(div_id)

    optimize_dead_styles(b.graph)
    assert "dead_cls" not in b.graph.components["App"].vss_classes


# ═══════════════════════════════════════════════════════════
#  Tree Shaking
# ═══════════════════════════════════════════════════════════


def test_tree_shake_keeps_root():
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        app.root(div_id)

    before = b.graph.h_node_count
    optimize_tree_shake(b.graph)
    assert "App" in b.graph.components
    assert b.graph.h_node_count == before  # Nothing removed


def test_tree_shake_removes_unreachable():
    """A component not reachable from root gets removed."""
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        app.root(div_id)
    with b.component("Orphan") as orphan:
        orphan.element("span")

    assert "Orphan" in b.graph.components
    optimize_tree_shake(b.graph)
    assert "Orphan" not in b.graph.components


def test_tree_shake_noop_without_root():
    b = DOMBuilder()
    with b.component("A") as a:
        a.element("div")
    # No root set → no shaking
    before = b.graph.h_node_count
    optimize_tree_shake(b.graph)
    assert b.graph.h_node_count == before


# ═══════════════════════════════════════════════════════════
#  Static Subtree Hoisting
# ═══════════════════════════════════════════════════════════


def test_static_hoist_marks_pure_element():
    """An element with no events, no state, no conditions is static."""
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        h1_id = app.element("h1")
        app.text("Title", parent=h1_id)
        app.child(div_id, h1_id)
        app.root(div_id)

    optimize_static_hoist(b.graph)
    div_node = b.graph.get_h_node(div_id)
    assert ":static" in div_node.name


def test_static_hoist_dynamic_element_not_marked():
    """An element with an event binding is NOT static."""
    b = DOMBuilder()
    with b.component("App") as app:
        btn_id = app.element("button")
        app.event(btn_id, "click", "handler")
        app.root(btn_id)

    optimize_static_hoist(b.graph)
    btn_node = b.graph.get_h_node(btn_id)
    assert ":static" not in (btn_node.name or "")


def test_static_hoist_parent_dynamic_if_child_dynamic():
    """If a child is dynamic, the parent is also dynamic."""
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        btn_id = app.element("button")
        app.event(btn_id, "click", "handler")
        app.child(div_id, btn_id)
        app.root(div_id)

    optimize_static_hoist(b.graph)
    div_node = b.graph.get_h_node(div_id)
    assert ":static" not in (div_node.name or "")


# ═══════════════════════════════════════════════════════════
#  DCE
# ═══════════════════════════════════════════════════════════


def test_dce_keeps_reachable():
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        app.text("hi", parent=div_id)
        app.root(div_id)

    before = b.graph.h_node_count
    optimize_dce(b.graph)
    # All nodes are reachable from the root, so nothing removed
    assert b.graph.h_node_count == before


def test_dce_removes_orphan_nodes():
    """Nodes not reachable from any root are removed."""
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        app.root(div_id)

    # Manually inject an orphan H-node
    orphan_id = b.graph.add_h_node(WIRHOp.TEXT, text_content="orphan", name="orphan")

    before = b.graph.h_node_count
    optimize_dce(b.graph)
    assert b.graph.h_node_count < before
    assert b.graph.get_h_node(orphan_id) is None


# ═══════════════════════════════════════════════════════════
#  Full Pipeline
# ═══════════════════════════════════════════════════════════


def test_optimize_all_passes():
    """Run the full optimizer and verify it doesn't crash."""
    b = DOMBuilder()
    with b.component("App") as app:
        app.state("count", "int", "0")
        div_id = app.element("div", vss_class="wrap")
        h1_id = app.element("h1")
        app.text("Title", parent=h1_id)
        app.child(div_id, h1_id)
        btn_id = app.element("button")
        app.event(btn_id, "click", "inc")
        app.child(div_id, btn_id)
        app.root(div_id)

    optimize(b.graph)
    assert b.graph.h_node_count > 0
    assert "App" in b.graph.components


def test_optimize_selected_passes():
    """Run only selected passes."""
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        app.root(div_id)

    optimize(b.graph, passes=("dce",))
    assert b.graph.h_node_count > 0


def test_optimize_idempotent():
    """Running optimizer twice yields same result."""
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div", vss_class="card")
        app.style(div_id, "card")
        app.root(div_id)

    optimize(b.graph)
    count_after_first = b.graph.h_node_count
    optimize(b.graph)
    assert b.graph.h_node_count == count_after_first

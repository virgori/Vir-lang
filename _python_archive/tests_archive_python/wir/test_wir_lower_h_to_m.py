"""Tests for WIR H→M lowering pass."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.wir.module import WIRGraph
from src.wir.builder.dom_builder import DOMBuilder
from src.wir.lower.h_to_m import lower_h_to_m
from src.wir.opcodes import WIRHOp, WIRMOp


def _m_ops(graph: WIRGraph) -> list[WIRMOp]:
    return [n.op for n in sorted(graph.m_nodes.values(), key=lambda n: n.node_id)]


# ── Element lowering ────────────────────────────────────────


def test_element_creates_m_nodes():
    b = DOMBuilder()
    with b.component("App") as app:
        app.element("div")
    lower_h_to_m(b.graph)
    ops = _m_ops(b.graph)
    assert WIRMOp.CREATE_ELEMENT in ops


def test_element_attrs_produce_set_attr():
    b = DOMBuilder()
    with b.component("App") as app:
        app.element("div", attrs=(("id", "main"),))
    lower_h_to_m(b.graph)
    ops = _m_ops(b.graph)
    assert WIRMOp.SET_ATTR in ops


def test_element_children_produce_append_child():
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        span_id = app.element("span")
        app.child(div_id, span_id)
    lower_h_to_m(b.graph)
    ops = _m_ops(b.graph)
    assert WIRMOp.APPEND_CHILD in ops


def test_element_vss_class_produces_resolve_and_apply():
    b = DOMBuilder()
    with b.component("App") as app:
        app.element("div", vss_class="card")
    lower_h_to_m(b.graph)
    ops = _m_ops(b.graph)
    assert WIRMOp.RESOLVE_CLASS in ops
    assert WIRMOp.APPLY_STYLE in ops


# ── Text lowering ───────────────────────────────────────────


def test_text_creates_m_node():
    b = DOMBuilder()
    with b.component("App") as app:
        app.text("Hello")
    lower_h_to_m(b.graph)
    ops = _m_ops(b.graph)
    assert WIRMOp.CREATE_TEXT in ops


def test_text_m_node_preserves_content():
    b = DOMBuilder()
    with b.component("App") as app:
        app.text("World")
    lower_h_to_m(b.graph)
    text_nodes = [n for n in b.graph.m_nodes.values() if n.op == WIRMOp.CREATE_TEXT]
    assert len(text_nodes) == 1
    assert text_nodes[0].text_content == "World"


# ── Event lowering ──────────────────────────────────────────


def test_event_bind_creates_add_listener():
    b = DOMBuilder()
    with b.component("App") as app:
        btn_id = app.element("button")
        app.event(btn_id, "click", "handler")
    lower_h_to_m(b.graph)
    ops = _m_ops(b.graph)
    assert WIRMOp.ADD_LISTENER in ops
    listener_nodes = [n for n in b.graph.m_nodes.values() if n.op == WIRMOp.ADD_LISTENER]
    assert listener_nodes[0].event_type == "click"


# ── State lowering ──────────────────────────────────────────


def test_state_def_creates_alloc():
    b = DOMBuilder()
    with b.component("App") as app:
        app.state("count", "int", "0")
    lower_h_to_m(b.graph)
    ops = _m_ops(b.graph)
    assert WIRMOp.ALLOC_STATE in ops


def test_computed_creates_subscribe_and_load():
    b = DOMBuilder()
    with b.component("App") as app:
        sid = app.state("x")
        app.computed("dx", deps=(sid,), fn="x*2")
    lower_h_to_m(b.graph)
    ops = _m_ops(b.graph)
    assert WIRMOp.SUBSCRIBE in ops
    assert WIRMOp.LOAD_STATE in ops


def test_effect_creates_subscribe():
    b = DOMBuilder()
    with b.component("App") as app:
        sid = app.state("x")
        app.effect(deps=(sid,), fn="log(x)")
    lower_h_to_m(b.graph)
    ops = _m_ops(b.graph)
    assert WIRMOp.SUBSCRIBE in ops


# ── Style lowering ──────────────────────────────────────────


def test_style_bind_creates_resolve_apply():
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        app.style(div_id, "card")
    lower_h_to_m(b.graph)
    ops = _m_ops(b.graph)
    resolve_count = sum(1 for o in ops if o == WIRMOp.RESOLVE_CLASS)
    apply_count = sum(1 for o in ops if o == WIRMOp.APPLY_STYLE)
    assert resolve_count >= 1
    assert apply_count >= 1


# ── Control flow lowering ───────────────────────────────────


def test_conditional_creates_diff_markers():
    b = DOMBuilder()
    with b.component("App") as app:
        cond_id = app.state("flag")
        div_id = app.element("div")
        app.conditional(cond_id, then_ids=(div_id,))
    lower_h_to_m(b.graph)
    ops = _m_ops(b.graph)
    assert WIRMOp.DIFF_START in ops
    assert WIRMOp.DIFF_COMMIT in ops


def test_list_creates_diff_markers():
    b = DOMBuilder()
    with b.component("App") as app:
        items_id = app.state("items")
        app.list_render(items_id, key_fn="id", render_fn="render_item")
    lower_h_to_m(b.graph)
    ops = _m_ops(b.graph)
    assert WIRMOp.DIFF_START in ops
    assert WIRMOp.DIFF_COMMIT in ops


# ── Route lowering ──────────────────────────────────────────


def test_route_def_creates_alloc():
    b = DOMBuilder()
    b.route("/home", "Home")
    lower_h_to_m(b.graph)
    ops = _m_ops(b.graph)
    assert WIRMOp.ALLOC_STATE in ops


# ── Lifecycle no-ops ────────────────────────────────────────


def test_lifecycle_hooks_produce_no_m_nodes():
    b = DOMBuilder()
    with b.component("App") as app:
        app.on_mount("setup")
        app.on_unmount("teardown")
    lower_h_to_m(b.graph)
    # lifecycle hooks should not produce M-ops themselves
    lifecycle_m = [n for n in b.graph.m_nodes.values()
                   if n.source_h_id in [nid for nid, h in b.graph.h_nodes.items()
                                         if h.op in (WIRHOp.ON_MOUNT, WIRHOp.ON_UNMOUNT)]]
    assert len(lifecycle_m) == 0


# ── Source tracing ──────────────────────────────────────────


def test_m_nodes_trace_back_to_h():
    b = DOMBuilder()
    with b.component("App") as app:
        app.element("div")
        app.text("hi")
    lower_h_to_m(b.graph)
    for m_node in b.graph.m_nodes.values():
        assert m_node.source_h_id in b.graph.h_nodes or m_node.source_h_id == 0


# ── Integration ─────────────────────────────────────────────


def test_full_lower_h_to_m():
    """End-to-end: build a component, lower, verify M-node population."""
    b = DOMBuilder()
    with b.component("App") as app:
        app.state("count", "int", "0")
        div_id = app.element("div", vss_class="wrap")
        btn_id = app.element("button")
        app.text("Click", parent=btn_id)
        app.child(div_id, btn_id)
        app.event(btn_id, "click", "inc")
        app.root(div_id)

    assert b.graph.m_node_count == 0
    lower_h_to_m(b.graph)
    assert b.graph.m_node_count > 0

    ops = _m_ops(b.graph)
    assert WIRMOp.CREATE_ELEMENT in ops
    assert WIRMOp.CREATE_TEXT in ops
    assert WIRMOp.ADD_LISTENER in ops
    assert WIRMOp.ALLOC_STATE in ops

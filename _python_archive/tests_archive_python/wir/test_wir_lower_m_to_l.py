"""Tests for WIR M→L lowering pass."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.wir.module import WIRGraph
from src.wir.builder.dom_builder import DOMBuilder
from src.wir.lower.h_to_m import lower_h_to_m
from src.wir.lower.m_to_l import lower_m_to_l
from src.wir.opcodes import WIRLOp, WIRMOp


def _l_ops(graph: WIRGraph) -> list[WIRLOp]:
    return [n.op for n in sorted(graph.l_nodes.values(), key=lambda n: n.node_id)]


def _build_and_lower_hm() -> DOMBuilder:
    """Helper: build a typical component graph and lower H→M."""
    b = DOMBuilder()
    with b.component("App") as app:
        app.state("count", "int", "0")
        div_id = app.element("div", vss_class="wrap")
        btn_id = app.element("button")
        app.text("Click", parent=btn_id)
        app.child(div_id, btn_id)
        app.event(btn_id, "click", "inc")
        app.root(div_id)
    lower_h_to_m(b.graph)
    return b


# ── DOM lowering ────────────────────────────────────────────


def test_create_element_produces_js_call():
    b = _build_and_lower_hm()
    lower_m_to_l(b.graph)
    ops = _l_ops(b.graph)
    assert WIRLOp.JS_CREATE_ELEMENT in ops


def test_create_text_produces_js_call():
    b = _build_and_lower_hm()
    lower_m_to_l(b.graph)
    ops = _l_ops(b.graph)
    assert WIRLOp.JS_CREATE_TEXT in ops


def test_append_child_produces_js_call():
    b = _build_and_lower_hm()
    lower_m_to_l(b.graph)
    ops = _l_ops(b.graph)
    assert WIRLOp.JS_APPEND_CHILD in ops


# ── Event lowering ──────────────────────────────────────────


def test_add_listener_produces_js_add_event():
    b = _build_and_lower_hm()
    lower_m_to_l(b.graph)
    ops = _l_ops(b.graph)
    assert WIRLOp.JS_ADD_EVENT in ops
    event_nodes = [n for n in b.graph.l_nodes.values() if n.op == WIRLOp.JS_ADD_EVENT]
    assert event_nodes[0].js_module == "event"
    assert event_nodes[0].js_func == "addEventListener"


# ── State lowering ──────────────────────────────────────────


def test_alloc_state_produces_data_alloc():
    b = _build_and_lower_hm()
    lower_m_to_l(b.graph)
    ops = _l_ops(b.graph)
    assert WIRLOp.DATA_ALLOC in ops


def test_alloc_state_str_produces_string_alloc():
    """Route creates a str-typed state alloc."""
    b = DOMBuilder()
    b.route("/home", "Home")
    lower_h_to_m(b.graph)
    lower_m_to_l(b.graph)
    ops = _l_ops(b.graph)
    assert WIRLOp.STRING_ALLOC in ops


# ── Style lowering ──────────────────────────────────────────


def test_resolve_class_produces_css_rule():
    b = _build_and_lower_hm()
    lower_m_to_l(b.graph)
    ops = _l_ops(b.graph)
    assert WIRLOp.EMIT_CSS_RULE in ops
    rule_nodes = [n for n in b.graph.l_nodes.values() if n.op == WIRLOp.EMIT_CSS_RULE]
    assert rule_nodes[0].css_selector.startswith(".")


def test_apply_style_produces_set_attribute():
    b = _build_and_lower_hm()
    lower_m_to_l(b.graph)
    # APPLY_STYLE without css_properties falls back to class-based setAttribute
    attr_nodes = [n for n in b.graph.l_nodes.values()
                  if n.op == WIRLOp.JS_SET_ATTRIBUTE]
    assert len(attr_nodes) >= 1


# ── Source tracing ──────────────────────────────────────────


def test_l_nodes_trace_to_m():
    b = _build_and_lower_hm()
    lower_m_to_l(b.graph)
    for l_node in b.graph.l_nodes.values():
        assert l_node.source_mid_id in b.graph.m_nodes or l_node.source_mid_id == 0


# ── JS module assignment ────────────────────────────────────


def test_dom_ops_use_dom_module():
    b = _build_and_lower_hm()
    lower_m_to_l(b.graph)
    create_nodes = [n for n in b.graph.l_nodes.values()
                    if n.op == WIRLOp.JS_CREATE_ELEMENT]
    for n in create_nodes:
        assert n.js_module == "dom"


def test_state_ops_use_state_module():
    b = DOMBuilder()
    with b.component("App") as app:
        sid = app.state("x")
        app.computed("dx", deps=(sid,), fn="x*2")
    lower_h_to_m(b.graph)
    lower_m_to_l(b.graph)
    call_nodes = [n for n in b.graph.l_nodes.values()
                  if n.op == WIRLOp.CALL_JS and n.js_module == "state"]
    assert len(call_nodes) >= 1


# ── Integration ─────────────────────────────────────────────


def test_full_pipeline_h_m_l():
    """Full pipeline: builder → H→M → M→L. Verify L-nodes present."""
    b = DOMBuilder()
    with b.component("Counter") as c:
        c.state("count", "int", "0")
        div_id = c.element("div", vss_class="wrapper")
        h1_id = c.element("h1")
        c.text("Counter", parent=h1_id)
        c.child(div_id, h1_id)
        btn_id = c.element("button")
        c.text("+1", parent=btn_id)
        c.child(div_id, btn_id)
        c.event(btn_id, "click", "increment")
        c.style(div_id, "wrapper")
        c.on_mount("init")
        c.root(div_id)

    assert b.graph.l_node_count == 0

    lower_h_to_m(b.graph)
    assert b.graph.m_node_count > 0

    lower_m_to_l(b.graph)
    assert b.graph.l_node_count > 0

    ops = _l_ops(b.graph)
    assert WIRLOp.JS_CREATE_ELEMENT in ops
    assert WIRLOp.JS_CREATE_TEXT in ops
    assert WIRLOp.JS_ADD_EVENT in ops
    assert WIRLOp.EMIT_CSS_RULE in ops
    assert WIRLOp.DATA_ALLOC in ops

    # Node counts should form a pyramid: few H → more M → most L
    assert b.graph.h_node_count > 0
    assert b.graph.m_node_count >= b.graph.h_node_count

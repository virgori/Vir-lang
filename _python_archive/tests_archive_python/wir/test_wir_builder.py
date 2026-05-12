"""Tests for DOMBuilder — verify fluent API produces correct WIR-H graphs."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.wir.module import WIRGraph
from src.wir.builder.dom_builder import DOMBuilder, ComponentScope
from src.wir.opcodes import WIRHOp


# ── Graph construction basics ───────────────────────────────


def test_empty_builder():
    b = DOMBuilder()
    assert b.graph.h_node_count == 0
    assert b.graph.m_node_count == 0
    assert b.graph.l_node_count == 0


def test_component_creates_def_node():
    b = DOMBuilder()
    with b.component("App") as app:
        pass
    # Should have the COMPONENT_DEF h-node
    assert b.graph.h_node_count >= 1
    assert "App" in b.graph.components


# ── Element construction ────────────────────────────────────


def test_element_basic():
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
    node = b.graph.get_h_node(div_id)
    assert node is not None
    assert node.op == WIRHOp.ELEMENT
    assert node.tag == "div"


def test_element_with_attrs():
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div", attrs=(("id", "main"), ("class", "wrap")))
    node = b.graph.get_h_node(div_id)
    assert node.attrs == (("id", "main"), ("class", "wrap"))


def test_element_with_vss_class():
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div", vss_class="container")
    node = b.graph.get_h_node(div_id)
    assert node.vss_class == "container"


# ── Text and fragment ───────────────────────────────────────


def test_text_node():
    b = DOMBuilder()
    with b.component("App") as app:
        tid = app.text("Hello")
    node = b.graph.get_h_node(tid)
    assert node.op == WIRHOp.TEXT
    assert node.text_content == "Hello"


def test_text_with_parent():
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        tid = app.text("child", parent=div_id)
    parent = b.graph.get_h_node(div_id)
    assert tid in parent.children_ids


def test_fragment():
    b = DOMBuilder()
    with b.component("App") as app:
        fid = app.fragment(children=(1, 2, 3))
    node = b.graph.get_h_node(fid)
    assert node.op == WIRHOp.FRAGMENT


# ── Tree assembly ───────────────────────────────────────────


def test_child_appends():
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        span_id = app.element("span")
        app.child(div_id, span_id)
    parent = b.graph.get_h_node(div_id)
    assert span_id in parent.children_ids


def test_root_sets_component_root():
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        app.root(div_id)
    comp = b.graph.components["App"]
    assert comp.root_node_id == div_id


def test_root_sets_graph_root_component():
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        app.root(div_id)
    assert b.graph.root_component == "App"


# ── State ───────────────────────────────────────────────────


def test_state_def():
    b = DOMBuilder()
    with b.component("App") as app:
        sid = app.state("count", "int", "0")
    node = b.graph.get_h_node(sid)
    assert node.op == WIRHOp.STATE_DEF
    assert node.state_name == "count"
    assert "count" in b.graph.components["App"].state_names


def test_computed():
    b = DOMBuilder()
    with b.component("App") as app:
        sid = app.state("x")
        cid = app.computed("double_x", deps=(sid,), fn="x * 2")
    node = b.graph.get_h_node(cid)
    assert node.op == WIRHOp.COMPUTED
    assert node.compute_fn == "x * 2"


def test_effect():
    b = DOMBuilder()
    with b.component("App") as app:
        sid = app.state("x")
        eid = app.effect(deps=(sid,), fn="log(x)")
    node = b.graph.get_h_node(eid)
    assert node.op == WIRHOp.EFFECT


# ── Events ──────────────────────────────────────────────────


def test_event_bind():
    b = DOMBuilder()
    with b.component("App") as app:
        btn_id = app.element("button")
        eid = app.event(btn_id, "click", "on_click")
    node = b.graph.get_h_node(eid)
    assert node.op == WIRHOp.EVENT_BIND
    assert node.event_type == "click"
    assert node.handler_fn == "on_click"
    assert "on_click" in b.graph.components["App"].event_handlers


# ── Style ───────────────────────────────────────────────────


def test_style_bind():
    b = DOMBuilder()
    with b.component("App") as app:
        div_id = app.element("div")
        sid = app.style(div_id, "card")
    node = b.graph.get_h_node(sid)
    assert node.op == WIRHOp.STYLE_BIND
    assert "card" in b.graph.components["App"].vss_classes


# ── Control flow ────────────────────────────────────────────


def test_conditional():
    b = DOMBuilder()
    with b.component("App") as app:
        cond_id = app.state("flag")
        div_id = app.element("div")
        cid = app.conditional(cond_id, then_ids=(div_id,))
    node = b.graph.get_h_node(cid)
    assert node.op == WIRHOp.CONDITIONAL


def test_list_render():
    b = DOMBuilder()
    with b.component("App") as app:
        items_id = app.state("items")
        lid = app.list_render(items_id, key_fn="id", render_fn="render_item")
    node = b.graph.get_h_node(lid)
    assert node.op == WIRHOp.LIST
    assert node.key_fn == "id"


# ── Lifecycle hooks ─────────────────────────────────────────


def test_on_mount():
    b = DOMBuilder()
    with b.component("App") as app:
        mid = app.on_mount("setup")
    node = b.graph.get_h_node(mid)
    assert node.op == WIRHOp.ON_MOUNT
    assert b.graph.components["App"].mount_fn == "setup"


def test_on_unmount():
    b = DOMBuilder()
    with b.component("App") as app:
        uid = app.on_unmount("cleanup")
    node = b.graph.get_h_node(uid)
    assert node.op == WIRHOp.ON_UNMOUNT
    assert b.graph.components["App"].unmount_fn == "cleanup"


# ── Routing ─────────────────────────────────────────────────


def test_route():
    b = DOMBuilder()
    rid = b.route("/home", "HomePage")
    node = b.graph.get_h_node(rid)
    assert node.op == WIRHOp.ROUTE_DEF
    assert node.route_path == "/home"
    assert node.route_component == "HomePage"
    assert rid in b.graph.routes


# ── Integration: full component ─────────────────────────────


def test_full_component_graph():
    """Build a realistic component and verify the graph shape."""
    b = DOMBuilder()
    with b.component("Counter") as c:
        c.state("count", "int", "0")
        div_id = c.element("div", vss_class="wrapper")
        h1_id = c.element("h1")
        c.text("Counter App", parent=h1_id)
        c.child(div_id, h1_id)
        btn_id = c.element("button")
        c.text("+1", parent=btn_id)
        c.child(div_id, btn_id)
        c.event(btn_id, "click", "increment")
        c.style(div_id, "wrapper")
        c.on_mount("init_counter")
        c.root(div_id)

    g = b.graph
    # At least: COMPONENT_DEF + STATE_DEF + 3 ELEMENT + 2 TEXT + EVENT_BIND + STYLE_BIND + ON_MOUNT
    assert g.h_node_count >= 10
    assert g.root_component == "Counter"
    comp = g.components["Counter"]
    assert comp.root_node_id == div_id
    assert "count" in comp.state_names
    assert "increment" in comp.event_handlers

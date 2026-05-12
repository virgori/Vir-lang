"""
Test suite for the W-IR pipeline: DOMBuilder → H→M lowering → M→L lowering.
"""

import pytest

from src.wir.module import WIRGraph
from src.wir.opcodes import WIRHOp, WIRMOp, WIRLOp
from src.wir.schema import WIRHNode, WIRMNode, WIRLNode
from src.wir.builder.dom_builder import DOMBuilder
from src.wir.lower.h_to_m import lower_h_to_m
from src.wir.lower.m_to_l import lower_m_to_l


# =============================================================================
#  WIRGraph basics
# =============================================================================

class TestWIRGraph:
    def test_add_h_node(self):
        g = WIRGraph()
        g.add_block("main")
        nid = g.add_h_node(WIRHOp.ELEMENT, tag="div")
        assert nid in g.h_nodes
        assert g.h_nodes[nid].tag == "div"

    def test_add_element(self):
        g = WIRGraph()
        g.add_block("main")
        nid = g.add_element("span", attrs=(("class", "x"),))
        node = g.h_nodes[nid]
        assert node.op == WIRHOp.ELEMENT
        assert node.tag == "span"
        assert ("class", "x") in node.attrs

    def test_add_text(self):
        g = WIRGraph()
        g.add_block("main")
        nid = g.add_text("Hello")
        assert g.h_nodes[nid].text_content == "Hello"

    def test_add_component_def(self):
        g = WIRGraph()
        g.add_block("main")
        nid = g.add_component_def("App", props=(("title", "str"),))
        assert "App" in g.components
        assert g.components["App"].prop_names == ["title"]

    def test_topo_order(self):
        g = WIRGraph()
        g.add_block("main")
        child = g.add_element("span")
        parent = g.add_element("div", children_ids=(child,))
        order = g.topo_order_h()
        assert order.index(child) < order.index(parent)

    def test_dump(self):
        g = WIRGraph(name="test")
        g.add_block("main")
        g.add_element("div")
        text = g.dump()
        assert "WIRGraph" in text
        assert "H-nodes: 1" in text


# =============================================================================
#  DOMBuilder tests
# =============================================================================

class TestDOMBuilder:
    def test_component_builder(self):
        builder = DOMBuilder()
        with builder.component("App") as app:
            div = app.element("div")
            txt = app.text("Hello!", parent=div)
            app.root(div)
        g = builder.graph
        assert "App" in g.components
        assert g.components["App"].root_node_id == div
        assert g.root_component == "App"

    def test_state_and_event(self):
        builder = DOMBuilder()
        with builder.component("Counter") as c:
            c.state("count", "int", "0")
            btn = c.element("button")
            c.text("Click", parent=btn)
            c.event(btn, "click", "increment")
            c.root(btn)
        comp = builder.graph.components["Counter"]
        assert "count" in comp.state_names
        assert "increment" in comp.event_handlers

    def test_style_binding(self):
        builder = DOMBuilder()
        with builder.component("Card") as c:
            div = c.element("div")
            c.style(div, "card_style")
            c.root(div)
        comp = builder.graph.components["Card"]
        assert "card_style" in comp.vss_classes

    def test_conditional(self):
        builder = DOMBuilder()
        with builder.component("App") as app:
            cond = app.state("show", "bool", "true")
            a = app.element("div")
            b = app.element("span")
            node = app.conditional(cond, then_ids=(a,), else_ids=(b,))
            app.root(node)
        g = builder.graph
        h = g.h_nodes[node]
        assert h.op == WIRHOp.CONDITIONAL
        assert h.then_ids == (a,)
        assert h.else_ids == (b,)

    def test_lifecycle_hooks(self):
        builder = DOMBuilder()
        with builder.component("App") as app:
            app.on_mount("setup")
            app.on_unmount("cleanup")
            div = app.element("div")
            app.root(div)
        comp = builder.graph.components["App"]
        assert comp.mount_fn == "setup"
        assert comp.unmount_fn == "cleanup"

    def test_route_definition(self):
        builder = DOMBuilder()
        with builder.component("App") as app:
            div = app.element("div")
            app.root(div)
        builder.route("/", "App")
        builder.route("/about", "About")
        assert len(builder.graph.routes) == 2

    def test_child_assembly(self):
        builder = DOMBuilder()
        with builder.component("App") as app:
            parent = app.element("div")
            c1 = app.element("span")
            c2 = app.element("p")
            app.child(parent, c1)
            app.child(parent, c2)
            app.root(parent)
        p_node = builder.graph.h_nodes[parent]
        assert c1 in p_node.children_ids
        assert c2 in p_node.children_ids


# =============================================================================
#  H→M Lowering tests
# =============================================================================

class TestHtoMLowering:
    def _build_simple_graph(self) -> WIRGraph:
        builder = DOMBuilder()
        with builder.component("App") as app:
            div = app.element("div", attrs=(("id", "app"),), vss_class="container")
            txt = app.text("Hello")
            app.child(div, txt)
            btn = app.element("button")
            app.event(btn, "click", "handle")
            app.child(div, btn)
            app.root(div)
        return builder.graph

    def test_lowering_produces_m_nodes(self):
        g = self._build_simple_graph()
        assert g.m_node_count == 0
        lower_h_to_m(g)
        assert g.m_node_count > 0

    def test_element_creates_dom_ops(self):
        g = self._build_simple_graph()
        lower_h_to_m(g)
        ops = [n.op for n in g.m_nodes.values()]
        assert WIRMOp.CREATE_ELEMENT in ops
        assert WIRMOp.SET_ATTR in ops
        assert WIRMOp.APPEND_CHILD in ops

    def test_text_creates_text_node(self):
        g = self._build_simple_graph()
        lower_h_to_m(g)
        ops = [n.op for n in g.m_nodes.values()]
        assert WIRMOp.CREATE_TEXT in ops

    def test_event_creates_listener(self):
        g = self._build_simple_graph()
        lower_h_to_m(g)
        ops = [n.op for n in g.m_nodes.values()]
        assert WIRMOp.ADD_LISTENER in ops
        listeners = [n for n in g.m_nodes.values() if n.op == WIRMOp.ADD_LISTENER]
        assert any(l.event_type == "click" for l in listeners)

    def test_style_creates_resolve_and_apply(self):
        g = self._build_simple_graph()
        lower_h_to_m(g)
        ops = [n.op for n in g.m_nodes.values()]
        assert WIRMOp.RESOLVE_CLASS in ops
        assert WIRMOp.APPLY_STYLE in ops

    def test_state_creates_alloc(self):
        builder = DOMBuilder()
        with builder.component("C") as c:
            c.state("x", "int", "0")
            div = c.element("div")
            c.root(div)
        lower_h_to_m(builder.graph)
        ops = [n.op for n in builder.graph.m_nodes.values()]
        assert WIRMOp.ALLOC_STATE in ops


# =============================================================================
#  M→L Lowering tests
# =============================================================================

class TestMtoLLowering:
    def _build_and_lower_h(self) -> WIRGraph:
        builder = DOMBuilder()
        with builder.component("App") as app:
            div = app.element("div", attrs=(("id", "root"),))
            txt = app.text("Hello W-IR")
            app.child(div, txt)
            btn = app.element("button")
            app.event(btn, "click", "on_click")
            app.child(div, btn)
            app.root(div)
        lower_h_to_m(builder.graph)
        return builder.graph

    def test_lowering_produces_l_nodes(self):
        g = self._build_and_lower_h()
        assert g.l_node_count == 0
        lower_m_to_l(g)
        assert g.l_node_count > 0

    def test_create_element_becomes_js_call(self):
        g = self._build_and_lower_h()
        lower_m_to_l(g)
        ops = [n.op for n in g.l_nodes.values()]
        assert WIRLOp.JS_CREATE_ELEMENT in ops
        js_create = [n for n in g.l_nodes.values() if n.op == WIRLOp.JS_CREATE_ELEMENT]
        assert all(n.js_func == "createElement" for n in js_create)

    def test_set_attr_becomes_js_set_attribute(self):
        g = self._build_and_lower_h()
        lower_m_to_l(g)
        ops = [n.op for n in g.l_nodes.values()]
        assert WIRLOp.JS_SET_ATTRIBUTE in ops

    def test_add_listener_becomes_js_add_event(self):
        g = self._build_and_lower_h()
        lower_m_to_l(g)
        ops = [n.op for n in g.l_nodes.values()]
        assert WIRLOp.JS_ADD_EVENT in ops
        events = [n for n in g.l_nodes.values() if n.op == WIRLOp.JS_ADD_EVENT]
        assert any("click" in n.string_data for n in events)

    def test_text_becomes_js_create_text(self):
        g = self._build_and_lower_h()
        lower_m_to_l(g)
        ops = [n.op for n in g.l_nodes.values()]
        assert WIRLOp.JS_CREATE_TEXT in ops

    def test_append_becomes_js_append_child(self):
        g = self._build_and_lower_h()
        lower_m_to_l(g)
        ops = [n.op for n in g.l_nodes.values()]
        assert WIRLOp.JS_APPEND_CHILD in ops


# =============================================================================
#  Full pipeline test
# =============================================================================

class TestFullWIRPipeline:
    def test_h_to_m_to_l(self):
        """Build H-nodes, lower to M, lower to L, verify all 3 levels populated."""
        builder = DOMBuilder()
        with builder.component("App") as app:
            div = app.element("div", vss_class="app")
            h1 = app.element("h1")
            app.text("Vir Web App", parent=h1)
            app.child(div, h1)
            app.state("count", "int", "0")
            btn = app.element("button")
            app.text("Click", parent=btn)
            app.event(btn, "click", "increment")
            app.style(btn, "primary_btn")
            app.child(div, btn)
            app.root(div)

        g = builder.graph
        assert g.h_node_count > 0
        assert g.m_node_count == 0
        assert g.l_node_count == 0

        lower_h_to_m(g)
        assert g.m_node_count > 0
        assert g.l_node_count == 0

        lower_m_to_l(g)
        assert g.l_node_count > 0

        # Verify key ops exist at each level
        h_ops = {n.op for n in g.h_nodes.values()}
        m_ops = {n.op for n in g.m_nodes.values()}
        l_ops = {n.op for n in g.l_nodes.values()}

        assert WIRHOp.ELEMENT in h_ops
        assert WIRHOp.TEXT in h_ops
        assert WIRHOp.EVENT_BIND in h_ops
        assert WIRHOp.STATE_DEF in h_ops

        assert WIRMOp.CREATE_ELEMENT in m_ops
        assert WIRMOp.CREATE_TEXT in m_ops
        assert WIRMOp.ADD_LISTENER in m_ops
        assert WIRMOp.ALLOC_STATE in m_ops

        assert WIRLOp.JS_CREATE_ELEMENT in l_ops
        assert WIRLOp.JS_CREATE_TEXT in l_ops
        assert WIRLOp.JS_ADD_EVENT in l_ops

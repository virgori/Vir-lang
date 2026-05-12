"""
WIR H→M Lowering — Lower WIR-H (component-semantic) to WIR-M (canonical DOM ops).
====================================================================================
Converts high-level component/element/event/style abstractions into concrete
DOM mutations, event listener setup, and state management operations.

Lowering rules:
  - ELEMENT        → CREATE_ELEMENT + SET_ATTR (per attr) + APPEND_CHILD (per child)
  - TEXT           → CREATE_TEXT
  - FRAGMENT       → children emitted inline
  - EVENT_BIND     → ADD_LISTENER
  - STATE_DEF      → ALLOC_STATE
  - STATE_GET      → LOAD_STATE
  - STATE_SET      → STORE_STATE
  - COMPUTED       → LOAD_STATE + SUBSCRIBE deps
  - STYLE_BIND     → RESOLVE_CLASS + APPLY_STYLE
  - CONDITIONAL    → (kept as paired M-ops with DIFF markers)
  - LIST           → DIFF_START + CREATE_ELEMENT per item + DIFF_COMMIT
  - COMPONENT_DEF  → expanded into child H-ops (already done by builder)
  - ROUTE_DEF      → state-based navigation M-ops
"""

from __future__ import annotations

from src.wir.module import WIRGraph
from src.wir.opcodes import WIRHOp, WIRMOp
from src.wir.schema import WIRHNode, WIRMNode, DOMAttrType


def lower_h_to_m(graph: WIRGraph) -> WIRGraph:
    """Lower all WIR-H nodes to WIR-M nodes. Returns the same graph, mutated."""
    _next_m_id = max(graph.h_nodes.keys(), default=0) + 1000

    def alloc() -> int:
        nonlocal _next_m_id
        mid = _next_m_id
        _next_m_id += 1
        return mid

    def add_m(op: WIRMOp, source_h: int, **kw: object) -> int:
        mid = alloc()
        node = WIRMNode(node_id=mid, op=op, source_h_id=source_h, **kw)
        graph.m_nodes[mid] = node
        return mid

    # Process H-nodes in topological order
    for h_id in graph.topo_order_h():
        h = graph.h_nodes[h_id]
        _lower_h_node(h, add_m, graph)

    return graph


def _lower_h_node(
    h: WIRHNode,
    add_m: object,
    graph: WIRGraph,
) -> None:
    """Dispatch a single H-node into one or more M-nodes."""
    op = h.op

    # ── ELEMENT → CREATE_ELEMENT + SET_ATTR* + APPEND_CHILD* ─
    if op == WIRHOp.ELEMENT:
        elem_id = add_m(WIRMOp.CREATE_ELEMENT, h.node_id, tag=h.tag)
        for attr_name, attr_value in h.attrs:
            add_m(WIRMOp.SET_ATTR, h.node_id,
                   parent_id=elem_id, attr_name=attr_name, attr_value=attr_value)
        for child_h_id in h.children_ids:
            add_m(WIRMOp.APPEND_CHILD, h.node_id,
                   parent_id=elem_id, child_id=child_h_id)
        # Style binding if present
        if h.vss_class:
            add_m(WIRMOp.RESOLVE_CLASS, h.node_id,
                   parent_id=elem_id, css_class=h.vss_class)
            add_m(WIRMOp.APPLY_STYLE, h.node_id,
                   parent_id=elem_id, css_class=h.vss_class)

    # ── TEXT → CREATE_TEXT ─────────────────────────────────────
    elif op == WIRHOp.TEXT:
        add_m(WIRMOp.CREATE_TEXT, h.node_id, text_content=h.text_content)

    # ── FRAGMENT → children emitted already, no wrapper node ──
    elif op == WIRHOp.FRAGMENT:
        for child_h_id in h.children_ids:
            # Just ensure children get appended to their parent context
            pass  # Children processed individually in topo order

    # ── EVENT_BIND → ADD_LISTENER ─────────────────────────────
    elif op == WIRHOp.EVENT_BIND:
        target = h.input_ids[0] if h.input_ids else 0
        add_m(WIRMOp.ADD_LISTENER, h.node_id,
               parent_id=target, event_type=h.event_type, handler_id=h.node_id)

    # ── EVENT_UNBIND → REMOVE_LISTENER ────────────────────────
    elif op == WIRHOp.EVENT_UNBIND:
        target = h.input_ids[0] if h.input_ids else 0
        add_m(WIRMOp.REMOVE_LISTENER, h.node_id,
               parent_id=target, event_type=h.event_type, handler_id=h.node_id)

    # ── STATE_DEF → ALLOC_STATE ───────────────────────────────
    elif op == WIRHOp.STATE_DEF:
        stype = h.state_fields[0][1] if h.state_fields else "int"
        add_m(WIRMOp.ALLOC_STATE, h.node_id,
               state_type=stype, state_size=_type_size(stype))

    # ── STATE_GET → LOAD_STATE ────────────────────────────────
    elif op == WIRHOp.STATE_GET:
        add_m(WIRMOp.LOAD_STATE, h.node_id)

    # ── STATE_SET → STORE_STATE ───────────────────────────────
    elif op == WIRHOp.STATE_SET:
        add_m(WIRMOp.STORE_STATE, h.node_id)

    # ── COMPUTED → LOAD_STATE + SUBSCRIBE per dep ─────────────
    elif op == WIRHOp.COMPUTED:
        for dep_id in h.deps:
            add_m(WIRMOp.SUBSCRIBE, h.node_id, callback_id=dep_id)
        add_m(WIRMOp.LOAD_STATE, h.node_id)

    # ── EFFECT → SUBSCRIBE per dep ────────────────────────────
    elif op == WIRHOp.EFFECT:
        for dep_id in h.deps:
            add_m(WIRMOp.SUBSCRIBE, h.node_id, callback_id=dep_id)

    # ── STYLE_BIND / STYLE_DYNAMIC / STYLE_SCOPED ────────────
    elif op in (WIRHOp.STYLE_BIND, WIRHOp.STYLE_DYNAMIC, WIRHOp.STYLE_SCOPED):
        target = h.input_ids[0] if h.input_ids else 0
        add_m(WIRMOp.RESOLVE_CLASS, h.node_id,
               parent_id=target, css_class=h.vss_class)
        add_m(WIRMOp.APPLY_STYLE, h.node_id,
               parent_id=target, css_class=h.vss_class)

    # ── CONDITIONAL → DIFF markers ────────────────────────────
    elif op == WIRHOp.CONDITIONAL:
        add_m(WIRMOp.DIFF_START, h.node_id)
        add_m(WIRMOp.DIFF_COMMIT, h.node_id)

    # ── LIST → DIFF markers ──────────────────────────────────
    elif op == WIRHOp.LIST:
        add_m(WIRMOp.DIFF_START, h.node_id)
        add_m(WIRMOp.DIFF_COMMIT, h.node_id)

    # ── COMPONENT_DEF → no M-op (metadata node) ─────────────
    elif op == WIRHOp.COMPONENT_DEF:
        pass

    # ── ROUTE_DEF → state-based navigation ───────────────────
    elif op == WIRHOp.ROUTE_DEF:
        add_m(WIRMOp.ALLOC_STATE, h.node_id, state_type="str")

    # ── Lifecycle hooks → noop at M-level (handled by runtime)
    elif op in (WIRHOp.ON_MOUNT, WIRHOp.ON_UNMOUNT, WIRHOp.ON_UPDATE,
                WIRHOp.COMPONENT_MOUNT, WIRHOp.COMPONENT_UPDATE,
                WIRHOp.COMPONENT_UNMOUNT):
        pass

    # ── FORM_BIND → SET_PROP + ADD_LISTENER ──────────────────
    elif op == WIRHOp.FORM_BIND:
        target = h.input_ids[0] if h.input_ids else 0
        add_m(WIRMOp.SET_PROP, h.node_id,
               parent_id=target, attr_name="value", attr_type=DOMAttrType.PROPERTY)
        add_m(WIRMOp.ADD_LISTENER, h.node_id,
               parent_id=target, event_type="input")

    # ── FORM_VALIDATE → noop (application logic) ─────────────
    elif op == WIRHOp.FORM_VALIDATE:
        pass

    # ── SLOT → placeholder pass-through ──────────────────────
    elif op == WIRHOp.SLOT:
        pass

    # ── ROUTE_NAVIGATE → STORE_STATE (route state) ──────────
    elif op == WIRHOp.ROUTE_NAVIGATE:
        add_m(WIRMOp.STORE_STATE, h.node_id)

    # ── EVENT_EMIT → DISPATCH_EVENT ──────────────────────────
    elif op == WIRHOp.EVENT_EMIT:
        add_m(WIRMOp.DISPATCH_EVENT, h.node_id, event_type=h.event_type)


def _type_size(stype: str) -> int:
    """Return byte size for common types."""
    sizes = {"int": 4, "i32": 4, "i64": 8, "f32": 4, "f64": 8, "bool": 1, "str": 4}
    return sizes.get(stype, 4)

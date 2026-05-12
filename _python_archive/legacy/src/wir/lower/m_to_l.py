"""
WIR M→L Lowering — Lower WIR-M (canonical DOM ops) to WIR-L (WASM + JS bridge).
==================================================================================
Each WIR-M node maps to one or more WIR-L nodes that model concrete JS import
calls, CSS emission directives, or linear-memory operations.  These WIR-L nodes
become the input to the final WASM code-gen stage.

Lowering rules:
  - CREATE_ELEMENT   → JS_CREATE_ELEMENT
  - CREATE_TEXT      → JS_CREATE_TEXT
  - SET_ATTR         → JS_SET_ATTRIBUTE
  - REMOVE_ATTR      → JS_REMOVE_ATTRIBUTE
  - SET_PROP         → JS_SET_PROPERTY
  - APPEND_CHILD     → JS_APPEND_CHILD
  - INSERT_BEFORE    → JS_INSERT_BEFORE
  - REMOVE_CHILD     → JS_REMOVE_CHILD
  - REPLACE_CHILD    → JS_REPLACE_CHILD
  - SET_TEXT          → JS_SET_TEXT
  - ADD_LISTENER     → JS_ADD_EVENT
  - REMOVE_LISTENER  → JS_REMOVE_EVENT
  - APPLY_STYLE      → JS_SET_STYLE (per declaration) or EMIT_CSS_RULE
  - RESOLVE_CLASS    → EMIT_CSS_RULE
  - ALLOC_STATE      → STRING_ALLOC / DATA_ALLOC
  - LOAD_STATE       → CALL_JS (state load bridge)
  - STORE_STATE      → CALL_JS (state store bridge)
  - SUBSCRIBE        → CALL_JS (subscription bridge)
  - DIFF_START/COMMIT→ REQUEST_FRAME markers
  - DISPATCH_EVENT   → CALL_JS
  - BATCH_SET_ATTRS  → JS_SET_ATTRIBUTE (per attr)
"""

from __future__ import annotations

from src.wir.module import WIRGraph
from src.wir.opcodes import WIRMOp, WIRLOp
from src.wir.schema import WIRMNode, WIRLNode


def lower_m_to_l(graph: WIRGraph) -> WIRGraph:
    """Lower all WIR-M nodes to WIR-L nodes. Returns same graph, mutated."""
    _next_l_id = max(
        max(graph.m_nodes.keys(), default=0),
        max(graph.l_nodes.keys(), default=0),
    ) + 2000

    def alloc() -> int:
        nonlocal _next_l_id
        lid = _next_l_id
        _next_l_id += 1
        return lid

    def add_l(op: WIRLOp, source_m: int, **kw: object) -> int:
        lid = alloc()
        node = WIRLNode(node_id=lid, op=op, source_mid_id=source_m, **kw)
        graph.l_nodes[lid] = node
        return lid

    for mid in sorted(graph.m_nodes):
        m = graph.m_nodes[mid]
        _lower_m_node(m, add_l)

    return graph


# ── Dispatch ─────────────────────────────────────────────────

_DOM_MODULE = "dom"
_STATE_MODULE = "state"
_EVENT_MODULE = "event"


def _lower_m_node(
    m: WIRMNode,
    add_l: object,
) -> None:
    """Convert a single M-node into WIR-L node(s)."""
    op = m.op

    # ── DOM mutation ─────────────────────────────────────────

    if op == WIRMOp.CREATE_ELEMENT:
        add_l(WIRLOp.JS_CREATE_ELEMENT, m.node_id,
              js_module=_DOM_MODULE, js_func="createElement",
              wasm_param_types=("i32",), wasm_result_type="i32")

    elif op == WIRMOp.CREATE_TEXT:
        add_l(WIRLOp.JS_CREATE_TEXT, m.node_id,
              js_module=_DOM_MODULE, js_func="createTextNode",
              string_data=m.text_content,
              wasm_param_types=("i32", "i32"), wasm_result_type="i32")

    elif op == WIRMOp.SET_ATTR:
        add_l(WIRLOp.JS_SET_ATTRIBUTE, m.node_id,
              js_module=_DOM_MODULE, js_func="setAttribute",
              wasm_param_types=("i32", "i32", "i32", "i32"))

    elif op == WIRMOp.REMOVE_ATTR:
        add_l(WIRLOp.JS_REMOVE_ATTRIBUTE, m.node_id,
              js_module=_DOM_MODULE, js_func="removeAttribute",
              wasm_param_types=("i32", "i32", "i32"))

    elif op == WIRMOp.SET_PROP:
        add_l(WIRLOp.JS_SET_PROPERTY, m.node_id,
              js_module=_DOM_MODULE, js_func="setProperty",
              wasm_param_types=("i32", "i32", "i32", "i32"))

    elif op == WIRMOp.APPEND_CHILD:
        add_l(WIRLOp.JS_APPEND_CHILD, m.node_id,
              js_module=_DOM_MODULE, js_func="appendChild",
              wasm_param_types=("i32", "i32"))

    elif op == WIRMOp.INSERT_BEFORE:
        add_l(WIRLOp.JS_INSERT_BEFORE, m.node_id,
              js_module=_DOM_MODULE, js_func="insertBefore",
              wasm_param_types=("i32", "i32", "i32"))

    elif op == WIRMOp.REMOVE_CHILD:
        add_l(WIRLOp.JS_REMOVE_CHILD, m.node_id,
              js_module=_DOM_MODULE, js_func="removeChild",
              wasm_param_types=("i32", "i32"))

    elif op == WIRMOp.REPLACE_CHILD:
        add_l(WIRLOp.JS_REPLACE_CHILD, m.node_id,
              js_module=_DOM_MODULE, js_func="replaceChild",
              wasm_param_types=("i32", "i32", "i32"))

    elif op == WIRMOp.SET_TEXT:
        add_l(WIRLOp.JS_SET_TEXT, m.node_id,
              js_module=_DOM_MODULE, js_func="setTextContent",
              wasm_param_types=("i32", "i32", "i32"))

    elif op == WIRMOp.SET_INNER_HTML:
        # Sanitized via pre-pass — emitted as setText fallback
        add_l(WIRLOp.JS_SET_TEXT, m.node_id,
              js_module=_DOM_MODULE, js_func="setInnerHTML",
              wasm_param_types=("i32", "i32", "i32"))

    # ── Style resolution ─────────────────────────────────────

    elif op == WIRMOp.RESOLVE_CLASS:
        if m.css_class:
            add_l(WIRLOp.EMIT_CSS_RULE, m.node_id,
                  css_selector=f".{m.css_class}",
                  css_declarations=m.css_properties)

    elif op == WIRMOp.RESOLVE_DYNAMIC:
        add_l(WIRLOp.EMIT_CSS_VAR, m.node_id,
              css_var_name=m.attr_name, css_var_value=m.attr_value)

    elif op == WIRMOp.APPLY_STYLE:
        if m.css_properties:
            for prop, val in m.css_properties:
                add_l(WIRLOp.JS_SET_STYLE, m.node_id,
                      js_module=_DOM_MODULE, js_func="setStyle",
                      string_data=f"{prop}:{val}",
                      wasm_param_types=("i32", "i32", "i32", "i32"))
        else:
            # Class-based: set className
            add_l(WIRLOp.JS_SET_ATTRIBUTE, m.node_id,
                  js_module=_DOM_MODULE, js_func="setAttribute",
                  string_data=f"class={m.css_class}",
                  wasm_param_types=("i32", "i32", "i32", "i32"))

    # ── Events ───────────────────────────────────────────────

    elif op == WIRMOp.ADD_LISTENER:
        add_l(WIRLOp.JS_ADD_EVENT, m.node_id,
              js_module=_EVENT_MODULE, js_func="addEventListener",
              string_data=m.event_type,
              wasm_param_types=("i32", "i32", "i32", "i32"))

    elif op == WIRMOp.REMOVE_LISTENER:
        add_l(WIRLOp.JS_REMOVE_EVENT, m.node_id,
              js_module=_EVENT_MODULE, js_func="removeEventListener",
              string_data=m.event_type,
              wasm_param_types=("i32", "i32", "i32"))

    elif op == WIRMOp.DISPATCH_EVENT:
        add_l(WIRLOp.CALL_JS, m.node_id,
              js_module=_EVENT_MODULE, js_func="dispatchEvent",
              string_data=m.event_type,
              wasm_param_types=("i32", "i32"))

    # ── State management ─────────────────────────────────────

    elif op == WIRMOp.ALLOC_STATE:
        if m.state_type == "str":
            add_l(WIRLOp.STRING_ALLOC, m.node_id,
                  alloc_size=256)
        else:
            add_l(WIRLOp.DATA_ALLOC, m.node_id,
                  alloc_size=m.state_size if m.state_size else 4)

    elif op == WIRMOp.LOAD_STATE:
        add_l(WIRLOp.CALL_JS, m.node_id,
              js_module=_STATE_MODULE, js_func="load",
              wasm_param_types=("i32",), wasm_result_type="i32")

    elif op == WIRMOp.STORE_STATE:
        add_l(WIRLOp.CALL_JS, m.node_id,
              js_module=_STATE_MODULE, js_func="store",
              wasm_param_types=("i32", "i32"))

    elif op == WIRMOp.SUBSCRIBE:
        add_l(WIRLOp.CALL_JS, m.node_id,
              js_module=_STATE_MODULE, js_func="subscribe",
              wasm_param_types=("i32", "i32"))

    # ── Diff / Batch ─────────────────────────────────────────

    elif op == WIRMOp.DIFF_START:
        add_l(WIRLOp.REQUEST_FRAME, m.node_id,
              js_module=_DOM_MODULE, js_func="requestAnimationFrame",
              wasm_param_types=("i32",))

    elif op == WIRMOp.DIFF_PATCH:
        add_l(WIRLOp.CALL_JS, m.node_id,
              js_module=_DOM_MODULE, js_func="patchDOM",
              wasm_param_types=("i32", "i32"))

    elif op == WIRMOp.DIFF_COMMIT:
        add_l(WIRLOp.CALL_JS, m.node_id,
              js_module=_DOM_MODULE, js_func="commitDOM")

    elif op == WIRMOp.BATCH_SET_ATTRS:
        for attr_name, attr_value in m.batch_attrs:
            add_l(WIRLOp.JS_SET_ATTRIBUTE, m.node_id,
                  js_module=_DOM_MODULE, js_func="setAttribute",
                  string_data=f"{attr_name}={attr_value}",
                  wasm_param_types=("i32", "i32", "i32", "i32"))

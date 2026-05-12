"""
WIR Opcodes — Web operation codes for all three IR levels.
============================================================
Namespace separate from the tensor QIR opcodes and language-VM Q-IR opcodes.
These are DOM/event/component/style-semantic operations for the web compiler spine.
"""

from __future__ import annotations

from enum import Enum, auto


# =============================================================================
#  WIR-H Opcodes (High-level, component-semantic)
# =============================================================================

class WIRHOp(Enum):
    """High-level web ops preserving component semantics."""

    # ── Component lifecycle ─────────────────────────────────
    COMPONENT_DEF = auto()
    COMPONENT_MOUNT = auto()
    COMPONENT_UPDATE = auto()
    COMPONENT_UNMOUNT = auto()

    # ── Routing ─────────────────────────────────────────────
    ROUTE_DEF = auto()
    ROUTE_NAVIGATE = auto()
    ROUTE_PARAM = auto()

    # ── Event binding ───────────────────────────────────────
    EVENT_BIND = auto()
    EVENT_UNBIND = auto()
    EVENT_EMIT = auto()

    # ── Reactive state ──────────────────────────────────────
    STATE_DEF = auto()
    STATE_GET = auto()
    STATE_SET = auto()
    COMPUTED = auto()
    EFFECT = auto()

    # ── DOM declaration (virtual tree) ──────────────────────
    ELEMENT = auto()
    TEXT = auto()
    FRAGMENT = auto()
    CONDITIONAL = auto()
    LIST = auto()
    SLOT = auto()

    # ── Style binding ───────────────────────────────────────
    STYLE_BIND = auto()
    STYLE_DYNAMIC = auto()
    STYLE_SCOPED = auto()

    # ── Form ────────────────────────────────────────────────
    FORM_BIND = auto()
    FORM_VALIDATE = auto()

    # ── Lifecycle hooks ─────────────────────────────────────
    ON_MOUNT = auto()
    ON_UNMOUNT = auto()
    ON_UPDATE = auto()


# =============================================================================
#  WIR-M Opcodes (Mid-level, canonical DOM operations)
# =============================================================================

class WIRMOp(Enum):
    """Canonical DOM operations after component lowering."""

    # ── DOM mutation ────────────────────────────────────────
    CREATE_ELEMENT = auto()
    CREATE_TEXT = auto()
    SET_ATTR = auto()
    REMOVE_ATTR = auto()
    SET_PROP = auto()
    APPEND_CHILD = auto()
    INSERT_BEFORE = auto()
    REMOVE_CHILD = auto()
    REPLACE_CHILD = auto()
    SET_TEXT = auto()
    SET_INNER_HTML = auto()       # sanitized only

    # ── VDOM diff ───────────────────────────────────────────
    DIFF_START = auto()
    DIFF_PATCH = auto()
    DIFF_COMMIT = auto()

    # ── Style resolution ────────────────────────────────────
    RESOLVE_CLASS = auto()
    RESOLVE_DYNAMIC = auto()
    APPLY_STYLE = auto()

    # ── Events (canonical) ──────────────────────────────────
    ADD_LISTENER = auto()
    REMOVE_LISTENER = auto()
    DISPATCH_EVENT = auto()

    # ── State (canonical) ───────────────────────────────────
    ALLOC_STATE = auto()
    LOAD_STATE = auto()
    STORE_STATE = auto()
    SUBSCRIBE = auto()

    # ── Attribute batching ──────────────────────────────────
    BATCH_SET_ATTRS = auto()


# =============================================================================
#  WIR-L Opcodes (Low-level, WASM + JS bridge emission)
# =============================================================================

class WIRLOp(Enum):
    """Low-level ops mapping to WASM imports and JS interop calls."""

    # ── JS interop ──────────────────────────────────────────
    IMPORT_JS = auto()
    CALL_JS = auto()
    EXPORT_WASM = auto()

    # ── DOM API (via JS imports) ────────────────────────────
    JS_CREATE_ELEMENT = auto()
    JS_CREATE_TEXT = auto()
    JS_SET_ATTRIBUTE = auto()
    JS_REMOVE_ATTRIBUTE = auto()
    JS_APPEND_CHILD = auto()
    JS_INSERT_BEFORE = auto()
    JS_REMOVE_CHILD = auto()
    JS_REPLACE_CHILD = auto()
    JS_ADD_EVENT = auto()
    JS_REMOVE_EVENT = auto()
    JS_SET_TEXT = auto()
    JS_SET_STYLE = auto()
    JS_SET_PROPERTY = auto()
    JS_QUERY_SELECTOR = auto()

    # ── CSS emission ────────────────────────────────────────
    EMIT_CSS_RULE = auto()
    EMIT_CSS_MEDIA = auto()
    EMIT_CSS_KEYFRAME = auto()
    EMIT_CSS_VAR = auto()

    # ── Linear memory (string/data management) ──────────────
    STRING_ALLOC = auto()
    STRING_WRITE = auto()
    STRING_FREE = auto()
    DATA_ALLOC = auto()

    # ── Scheduling ──────────────────────────────────────────
    REQUEST_FRAME = auto()
    SET_TIMEOUT = auto()
    SET_INTERVAL = auto()
    CLEAR_TIMEOUT = auto()
    MICROTASK = auto()

    # ── History / Navigation ────────────────────────────────
    PUSH_STATE = auto()
    REPLACE_STATE = auto()
    POP_STATE_LISTEN = auto()

"""
WIR Schema — Node definitions for all three web IR levels.
============================================================
Immutable nodes with DOM/component/style semantics.

Design principles:
  - frozen dataclasses for immutability (matches QIR schema style)
  - DOM-aware metadata per node (tag, attrs, event type, style refs)
  - Source tracing between levels for debugging
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from src.wir.opcodes import WIRHOp, WIRMOp, WIRLOp


# =============================================================================
#  Supporting Enums
# =============================================================================

class EventKind(Enum):
    """DOM event categories for type-safe event binding."""
    CLICK = auto()
    DBLCLICK = auto()
    MOUSEDOWN = auto()
    MOUSEUP = auto()
    MOUSEMOVE = auto()
    MOUSEENTER = auto()
    MOUSELEAVE = auto()
    KEYDOWN = auto()
    KEYUP = auto()
    KEYPRESS = auto()
    INPUT = auto()
    CHANGE = auto()
    SUBMIT = auto()
    FOCUS = auto()
    BLUR = auto()
    SCROLL = auto()
    RESIZE = auto()
    LOAD = auto()
    UNLOAD = auto()
    CUSTOM = auto()


class DOMAttrType(Enum):
    """Attribute vs property distinction for correct DOM API calls."""
    ATTRIBUTE = auto()     # setAttribute / removeAttribute
    PROPERTY = auto()      # direct property assignment (checked, value, etc.)
    STYLE = auto()         # style property
    CLASS = auto()         # className / classList
    DATA = auto()          # data-* attributes
    EVENT = auto()         # event handler


# =============================================================================
#  WIR-H Node — High-level component-semantic IR
# =============================================================================

@dataclass(frozen=True)
class WIRHNode:
    """High-level IR node preserving component semantics.

    Represents:
      - Component definitions and lifecycle events
      - Virtual DOM tree declarations (elements, text, fragments)
      - Reactive state and computed values
      - Event bindings and style bindings
      - Route definitions
    """
    # Identity
    node_id: int
    op: WIRHOp
    input_ids: tuple[int, ...] = ()
    output_ids: tuple[int, ...] = ()
    name: str = ""

    # Component metadata
    component_name: str = ""
    props: tuple[tuple[str, str], ...] = ()         # (name, type) pairs
    state_fields: tuple[tuple[str, str, str], ...] = ()  # (name, type, initial_expr)

    # DOM metadata
    tag: str = ""
    attrs: tuple[tuple[str, str], ...] = ()         # (attr_name, attr_value)
    children_ids: tuple[int, ...] = ()
    text_content: str = ""

    # Style metadata
    vss_class: str = ""                   # Bound VSS style block name
    dynamic_styles: tuple[tuple[str, int], ...] = ()  # (css_prop, expr_node_id)

    # Event metadata
    event_kind: EventKind | None = None
    event_type: str = ""                  # Raw event string for CUSTOM
    handler_fn: str = ""                  # Function name for handler

    # Reactive metadata
    state_name: str = ""
    deps: tuple[int, ...] = ()            # Dependency node IDs for computed/effect
    compute_fn: str = ""

    # Routing metadata
    route_path: str = ""
    route_component: str = ""
    route_guards: tuple[str, ...] = ()

    # Conditional / List metadata
    condition_id: int = 0                 # Node ID of condition expression
    then_ids: tuple[int, ...] = ()
    else_ids: tuple[int, ...] = ()
    items_id: int = 0                     # Node ID of list source
    key_fn: str = ""
    render_fn: str = ""

    # Source info
    source_line: int = 0


# =============================================================================
#  WIR-M Node — Mid-level canonical DOM operations
# =============================================================================

@dataclass(frozen=True)
class WIRMNode:
    """Mid-level IR node with canonical DOM operations.

    All high-level component abstractions have been lowered to
    concrete DOM mutation, event, and state operations.
    """
    node_id: int
    op: WIRMOp
    input_ids: tuple[int, ...] = ()
    output_ids: tuple[int, ...] = ()

    # DOM op details
    tag: str = ""
    attr_name: str = ""
    attr_value: str = ""
    attr_type: DOMAttrType = DOMAttrType.ATTRIBUTE
    text_content: str = ""
    parent_id: int = 0
    child_id: int = 0
    ref_id: int = 0                       # For INSERT_BEFORE

    # Style resolution
    css_class: str = ""                   # Mangled class name
    css_properties: tuple[tuple[str, str], ...] = ()  # (prop, value) pairs

    # Event details
    event_type: str = ""
    handler_id: int = 0
    event_options: tuple[tuple[str, bool], ...] = ()  # (capture, passive, once)

    # State details
    state_size: int = 0
    state_type: str = ""
    callback_id: int = 0

    # Batch attrs
    batch_attrs: tuple[tuple[str, str], ...] = ()

    # Source tracing
    source_h_id: int = 0


# =============================================================================
#  WIR-L Node — Low-level WASM + JS bridge calls
# =============================================================================

@dataclass(frozen=True)
class WIRLNode:
    """Low-level IR node with WASM/JS bridge call metadata.

    Each node maps directly to a WASM import call or CSS emission.
    """
    node_id: int
    op: WIRLOp
    input_ids: tuple[int, ...] = ()
    output_ids: tuple[int, ...] = ()

    # JS call metadata
    js_module: str = ""                   # "env", "dom", custom
    js_func: str = ""                     # "js_create_element", etc.
    js_args: tuple[int, ...] = ()         # Node IDs of arguments
    wasm_param_types: tuple[str, ...] = ()   # ("i32", "i32", ...)
    wasm_result_type: str = ""            # "i32", "void", etc.

    # CSS emission
    css_selector: str = ""
    css_declarations: tuple[tuple[str, str], ...] = ()  # (prop, value)
    css_media_query: str = ""
    css_keyframe_name: str = ""
    css_keyframe_steps: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = ()
    css_var_name: str = ""
    css_var_value: str = ""

    # Memory
    string_data: str = ""
    alloc_size: int = 0

    # Scheduling
    delay_ms: int = 0
    callback_id: int = 0

    # Navigation
    url: str = ""
    state_data: str = ""

    # Source tracing
    source_mid_id: int = 0

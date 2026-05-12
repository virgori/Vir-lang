"""Tests for WIR opcodes — validate enum coverage and no accidental duplicates."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.wir.opcodes import WIRHOp, WIRMOp, WIRLOp


# ── WIR-H opcode tests ─────────────────────────────────────


def test_wirh_has_component_lifecycle():
    for name in ("COMPONENT_DEF", "COMPONENT_MOUNT", "COMPONENT_UPDATE", "COMPONENT_UNMOUNT"):
        assert hasattr(WIRHOp, name), f"WIRHOp missing {name}"


def test_wirh_has_dom_declaration():
    for name in ("ELEMENT", "TEXT", "FRAGMENT", "CONDITIONAL", "LIST", "SLOT"):
        assert hasattr(WIRHOp, name)


def test_wirh_has_reactive_state():
    for name in ("STATE_DEF", "STATE_GET", "STATE_SET", "COMPUTED", "EFFECT"):
        assert hasattr(WIRHOp, name)


def test_wirh_has_events():
    for name in ("EVENT_BIND", "EVENT_UNBIND", "EVENT_EMIT"):
        assert hasattr(WIRHOp, name)


def test_wirh_has_routing():
    for name in ("ROUTE_DEF", "ROUTE_NAVIGATE", "ROUTE_PARAM"):
        assert hasattr(WIRHOp, name)


def test_wirh_no_duplicate_values():
    values = [m.value for m in WIRHOp]
    assert len(values) == len(set(values)), "WIRHOp has duplicate enum values"


# ── WIR-M opcode tests ─────────────────────────────────────


def test_wirm_has_dom_mutations():
    for name in ("CREATE_ELEMENT", "CREATE_TEXT", "SET_ATTR", "REMOVE_ATTR",
                  "APPEND_CHILD", "REMOVE_CHILD", "REPLACE_CHILD", "SET_TEXT"):
        assert hasattr(WIRMOp, name)


def test_wirm_has_diff_ops():
    for name in ("DIFF_START", "DIFF_PATCH", "DIFF_COMMIT"):
        assert hasattr(WIRMOp, name)


def test_wirm_has_state_ops():
    for name in ("ALLOC_STATE", "LOAD_STATE", "STORE_STATE", "SUBSCRIBE"):
        assert hasattr(WIRMOp, name)


def test_wirm_no_duplicate_values():
    values = [m.value for m in WIRMOp]
    assert len(values) == len(set(values))


# ── WIR-L opcode tests ─────────────────────────────────────


def test_wirl_has_js_dom_calls():
    for name in ("JS_CREATE_ELEMENT", "JS_CREATE_TEXT", "JS_SET_ATTRIBUTE",
                  "JS_APPEND_CHILD", "JS_ADD_EVENT", "JS_SET_TEXT"):
        assert hasattr(WIRLOp, name)


def test_wirl_has_css_emission():
    for name in ("EMIT_CSS_RULE", "EMIT_CSS_MEDIA", "EMIT_CSS_KEYFRAME", "EMIT_CSS_VAR"):
        assert hasattr(WIRLOp, name)


def test_wirl_has_memory_ops():
    for name in ("STRING_ALLOC", "STRING_WRITE", "STRING_FREE", "DATA_ALLOC"):
        assert hasattr(WIRLOp, name)


def test_wirl_has_scheduling():
    for name in ("REQUEST_FRAME", "SET_TIMEOUT", "SET_INTERVAL", "MICROTASK"):
        assert hasattr(WIRLOp, name)


def test_wirl_no_duplicate_values():
    values = [m.value for m in WIRLOp]
    assert len(values) == len(set(values))


# ── Cross-level disjointness ───────────────────────────────


def test_opcode_names_disjoint():
    h_names = {m.name for m in WIRHOp}
    m_names = {m.name for m in WIRMOp}
    l_names = {m.name for m in WIRLOp}
    assert not (h_names & m_names), "H and M share opcode names"
    assert not (h_names & l_names), "H and L share opcode names"
    assert not (m_names & l_names), "M and L share opcode names"

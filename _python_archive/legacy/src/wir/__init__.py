"""
WIR — Web Intermediate Representation for Vir
===============================================
Three-level IR spine for web targets (parallel to QIR for tensors):
  WIR-H (High): Component lifecycle, routing, events, reactive state, DOM declaration
  WIR-M (Mid):  Canonical DOM ops, VDOM diff, style resolution
  WIR-L (Low):  WASM imports, JS interop calls, CSS emission, scheduling
"""

from src.wir.opcodes import WIRHOp, WIRMOp, WIRLOp
from src.wir.schema import WIRHNode, WIRMNode, WIRLNode, EventKind, DOMAttrType
from src.wir.module import WIRGraph, WIRBlock, WIRComponent
from src.wir.builder import DOMBuilder
from src.wir.lower import lower_h_to_m, lower_m_to_l

__all__ = [
    "WIRHOp", "WIRMOp", "WIRLOp",
    "WIRHNode", "WIRMNode", "WIRLNode",
    "EventKind", "DOMAttrType",
    "WIRGraph", "WIRBlock", "WIRComponent",
    "DOMBuilder",
    "lower_h_to_m", "lower_m_to_l",
]

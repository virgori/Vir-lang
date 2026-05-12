"""
C ABI Bridge — Generate C-compatible function signatures for Vir kernels.
==========================================================================
Produces ctypes-loadable wrappers and C header declarations for
exporting Vir-compiled kernels across the FFI boundary.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class CABIType(Enum):
    """C ABI compatible types for FFI bridge."""
    VOID = "void"
    INT32 = "int32_t"
    INT64 = "int64_t"
    FLOAT32 = "float"
    FLOAT64 = "double"
    PTR_FLOAT = "float*"
    PTR_DOUBLE = "double*"
    PTR_INT32 = "int32_t*"
    PTR_VOID = "void*"
    SIZE_T = "size_t"


@dataclass(frozen=True)
class CABIParam:
    """A single C ABI function parameter."""
    name: str
    ctype: CABIType
    is_output: bool = False


@dataclass(frozen=True)
class CABISignature:
    """Complete C ABI function signature."""
    name: str
    params: tuple[CABIParam, ...]
    return_type: CABIType = CABIType.VOID

    def c_declaration(self) -> str:
        """Generate C function declaration."""
        params_str = ", ".join(
            f"{p.ctype.value} {p.name}" for p in self.params
        )
        return f"{self.return_type.value} {self.name}({params_str});"

    def c_header_guard(self, guard_name: str) -> str:
        """Generate complete C header with guard."""
        return (
            f"#ifndef {guard_name}\n"
            f"#define {guard_name}\n\n"
            f"#include <stdint.h>\n"
            f"#include <stddef.h>\n\n"
            f"{self.c_declaration()}\n\n"
            f"#endif /* {guard_name} */\n"
        )


# =============================================================================
#  Standard kernel signatures
# =============================================================================

def gemm_signature(prefix: str = "vir") -> CABISignature:
    """Standard GEMM C ABI signature: C = A @ B."""
    return CABISignature(
        name=f"{prefix}_gemm_f32",
        params=(
            CABIParam("a", CABIType.PTR_FLOAT),
            CABIParam("b", CABIType.PTR_FLOAT),
            CABIParam("c", CABIType.PTR_FLOAT, is_output=True),
            CABIParam("m", CABIType.SIZE_T),
            CABIParam("k", CABIType.SIZE_T),
            CABIParam("n", CABIType.SIZE_T),
        ),
    )


def elementwise_binary_signature(
    op_name: str, prefix: str = "vir",
) -> CABISignature:
    """Binary elementwise C ABI: out[i] = op(a[i], b[i])."""
    return CABISignature(
        name=f"{prefix}_{op_name}_f32",
        params=(
            CABIParam("a", CABIType.PTR_FLOAT),
            CABIParam("b", CABIType.PTR_FLOAT),
            CABIParam("out", CABIType.PTR_FLOAT, is_output=True),
            CABIParam("n", CABIType.SIZE_T),
        ),
    )


def elementwise_unary_signature(
    op_name: str, prefix: str = "vir",
) -> CABISignature:
    """Unary elementwise C ABI: out[i] = op(a[i])."""
    return CABISignature(
        name=f"{prefix}_{op_name}_f32",
        params=(
            CABIParam("a", CABIType.PTR_FLOAT),
            CABIParam("out", CABIType.PTR_FLOAT, is_output=True),
            CABIParam("n", CABIType.SIZE_T),
        ),
    )


def reduce_signature(
    op_name: str, prefix: str = "vir",
) -> CABISignature:
    """Reduction C ABI: result = reduce_op(a, n)."""
    return CABISignature(
        name=f"{prefix}_{op_name}_f32",
        params=(
            CABIParam("a", CABIType.PTR_FLOAT),
            CABIParam("n", CABIType.SIZE_T),
        ),
        return_type=CABIType.FLOAT32,
    )


# =============================================================================
#  Header generator
# =============================================================================

def generate_vir_kernel_header(ops: list[str] | None = None) -> str:
    """Generate a complete C header for standard Vir kernel exports.

    Args:
        ops: List of op names. If None, generates all standard ops.
    """
    if ops is None:
        ops = [
            "gemm", "add", "sub", "mul", "div",
            "neg", "abs", "relu", "sigmoid", "tanh", "exp", "log",
            "reduce_sum", "reduce_mean", "reduce_max",
        ]

    lines = [
        "#ifndef VIR_KERNELS_H",
        "#define VIR_KERNELS_H",
        "",
        "#include <stdint.h>",
        "#include <stddef.h>",
        "",
        "#ifdef __cplusplus",
        'extern "C" {',
        "#endif",
        "",
    ]

    binary_ops = {"add", "sub", "mul", "div"}
    unary_ops = {"neg", "abs", "relu", "sigmoid", "tanh", "exp", "log",
                 "sqrt", "rsqrt", "gelu", "silu"}
    reduce_ops = {"reduce_sum", "reduce_mean", "reduce_max"}

    for op in ops:
        if op == "gemm":
            sig = gemm_signature()
        elif op in binary_ops:
            sig = elementwise_binary_signature(op)
        elif op in unary_ops:
            sig = elementwise_unary_signature(op)
        elif op in reduce_ops:
            sig = reduce_signature(op)
        else:
            continue
        lines.append(sig.c_declaration())

    lines.extend([
        "",
        "#ifdef __cplusplus",
        "}",
        "#endif",
        "",
        "#endif /* VIR_KERNELS_H */",
    ])
    return "\n".join(lines)

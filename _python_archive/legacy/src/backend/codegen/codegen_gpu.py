"""
codegen_gpu.py – GPU Code Generator: Q-IR → PTX / MSL
=======================================================
Spec §D4 – GPU Kernel Library

Lowers Q-IR vector instructions to either NVIDIA PTX (CUDA)
or Apple MSL (Metal) depending on detected platform.

Features
--------
- Prebuilt kernel template loading from data/gpu/
- Dynamic kernel generation from Q-IR vector blocks
- Kernel fusion: collapses chains of element-wise ops into one kernel
- Launch config computation (thread/threadgroup sizing)
- Platform auto-detection (macOS → Metal, Linux/CUDA → PTX)
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from src.ir.instructions.q_ir import (
    Immediate, Label, Opcode, QFunction, QInstruction, QModule, VReg,
)

# ── GPU Target ─────────────────────────────────────────────

class GPUTarget(Enum):
    CUDA = "cuda"
    METAL = "metal"


# ── Kernel Descriptor ──────────────────────────────────────

@dataclass
class GPUKernel:
    """A GPU kernel ready for dispatch."""
    name: str
    target: GPUTarget
    source: str              # PTX or MSL source text
    block_size: tuple[int, int, int] = (256, 1, 1)
    shared_mem_bytes: int = 0
    num_buffers: int = 0
    num_scalars: int = 0


@dataclass
class FusedChain:
    """A chain of element-wise ops that can be fused into one kernel."""
    ops: list[QInstruction]
    input_regs: list[VReg]
    output_reg: VReg
    length_reg: VReg | Immediate | None = None


# ── Opcode → GPU Mapping ──────────────────────────────────

# Element-wise ops that can be fused
_ELEMENTWISE_OPS: set[Opcode] = {
    Opcode.Q_VADD, Opcode.Q_VSUB, Opcode.Q_VMUL, Opcode.Q_VDIV,
    Opcode.Q_VMIN, Opcode.Q_VMAX, Opcode.Q_VFMA,
    Opcode.Q_FADD, Opcode.Q_FSUB, Opcode.Q_FMUL, Opcode.Q_FDIV,
}

_PTX_OPMAP: dict[Opcode, str] = {
    Opcode.Q_VADD: "add.f32",   Opcode.Q_VSUB: "sub.f32",
    Opcode.Q_VMUL: "mul.f32",   Opcode.Q_VDIV: "div.approx.f32",
    Opcode.Q_VMIN: "min.f32",   Opcode.Q_VMAX: "max.f32",
    Opcode.Q_VFMA: "fma.rn.f32",
    Opcode.Q_FADD: "add.f32",   Opcode.Q_FSUB: "sub.f32",
    Opcode.Q_FMUL: "mul.f32",   Opcode.Q_FDIV: "div.approx.f32",
}

_MSL_OPMAP: dict[Opcode, str] = {
    Opcode.Q_VADD: "+",   Opcode.Q_VSUB: "-",
    Opcode.Q_VMUL: "*",   Opcode.Q_VDIV: "/",
    Opcode.Q_VMIN: "min", Opcode.Q_VMAX: "max",
    Opcode.Q_VFMA: "fma",
    Opcode.Q_FADD: "+",   Opcode.Q_FSUB: "-",
    Opcode.Q_FMUL: "*",   Opcode.Q_FDIV: "/",
}


# ── Template Loader ────────────────────────────────────────

def _project_root() -> Path:
    """Walk up from this file to find the Vir project root."""
    p = Path(__file__).resolve()
    while p.parent != p:
        if (p / "core" / "include").is_dir():
            return p
        p = p.parent
    return Path(__file__).resolve().parent.parent.parent


_TEMPLATE_DIR: Path = _project_root() / "data" / "gpu"

# Template registry: name → (ptx_file, msl_file, kernel_entry, block, buffers, scalars)
_BUILTIN_KERNELS: dict[str, dict] = {
    "vadd_f32": {
        "ptx": "ptx_templates/vadd_f32.ptx",
        "msl": "msl_templates/vadd_f32.metal",
        "entry": "vir_vadd_f32",
        "block": (256, 1, 1), "buffers": 3, "scalars": 1,
    },
    "gemm_f32": {
        "ptx": "ptx_templates/gemm_f32.ptx",
        "msl": "msl_templates/gemm_f32.metal",
        "entry": "vir_gemm_f32",
        "block": (32, 32, 1), "buffers": 3, "scalars": 3,
    },
    "relu_f32": {
        "ptx": "ptx_templates/relu_f32.ptx",
        "msl": "msl_templates/relu_f32.metal",
        "entry": "vir_relu_f32",
        "block": (256, 1, 1), "buffers": 2, "scalars": 1,
    },
    "fused_relu_add_f32": {
        "ptx": "ptx_templates/fused_relu_add_f32.ptx",
        "msl": "msl_templates/fused_relu_add_f32.metal",
        "entry": "vir_fused_relu_add_f32",
        "block": (256, 1, 1), "buffers": 3, "scalars": 1,
    },
    "softmax_f32": {
        "ptx": "ptx_templates/softmax_f32.ptx",
        "msl": "msl_templates/softmax_f32.metal",
        "entry": "vir_softmax_f32",
        "block": (256, 1, 1), "buffers": 2, "scalars": 1,
    },
}


def load_builtin_kernel(name: str, target: GPUTarget) -> GPUKernel:
    """Load a prebuilt kernel template by name."""
    if name not in _BUILTIN_KERNELS:
        raise ValueError(f"Unknown builtin kernel: {name!r}. "
                         f"Available: {list(_BUILTIN_KERNELS)}")
    info = _BUILTIN_KERNELS[name]
    key = "ptx" if target == GPUTarget.CUDA else "msl"
    path = _TEMPLATE_DIR / info[key]
    source = path.read_text(encoding="utf-8")
    return GPUKernel(
        name=info["entry"],
        target=target,
        source=source,
        block_size=info["block"],
        num_buffers=info["buffers"],
        num_scalars=info["scalars"],
    )


def list_builtin_kernels() -> list[str]:
    """Return names of all registered prebuilt kernels."""
    return list(_BUILTIN_KERNELS)


# ── Platform Detection ─────────────────────────────────────

def detect_gpu_target() -> GPUTarget:
    """Auto-detect GPU target based on platform."""
    if platform.system() == "Darwin":
        return GPUTarget.METAL
    return GPUTarget.CUDA


# ── Kernel Fusion Analysis ─────────────────────────────────

def detect_fuseable_chains(instrs: list[QInstruction]) -> list[FusedChain]:
    """
    Scan a Q-IR instruction sequence for chains of element-wise ops
    that can be fused into a single GPU kernel (no intermediate stores).
    """
    chains: list[FusedChain] = []
    current_ops: list[QInstruction] = []
    live_regs: dict[int, bool] = {}  # vreg index → produced by chain

    for instr in instrs:
        if instr.opcode in _ELEMENTWISE_OPS:
            current_ops.append(instr)
            if isinstance(instr.dest, VReg):
                live_regs[instr.dest.index] = True
        else:
            if len(current_ops) >= 2:
                chains.append(_build_chain(current_ops))
            current_ops = []
            live_regs = {}

    # Flush trailing chain
    if len(current_ops) >= 2:
        chains.append(_build_chain(current_ops))

    return chains


def _build_chain(ops: list[QInstruction]) -> FusedChain:
    """Build a FusedChain from a sequence of element-wise ops."""
    produced: set[int] = set()
    inputs: list[VReg] = []

    for op in ops:
        if isinstance(op.dest, VReg):
            produced.add(op.dest.index)
        for src in (op.src1, op.src2):
            if isinstance(src, VReg) and src.index not in produced:
                if src not in inputs:
                    inputs.append(src)

    output = ops[-1].dest if isinstance(ops[-1].dest, VReg) else VReg(0)
    return FusedChain(ops=list(ops), input_regs=inputs, output_reg=output)


# ── PTX Code Generation ───────────────────────────────────

def _gen_ptx_kernel(name: str, chain: FusedChain) -> GPUKernel:
    """Generate a fused PTX kernel from a chain of element-wise ops."""
    n_inputs = len(chain.input_regs)
    lines: list[str] = []

    lines.append(".version 7.8")
    lines.append(".target sm_70")
    lines.append(".address_size 64")
    lines.append("")

    # Kernel signature
    params = []
    for i in range(n_inputs):
        params.append(f"    .param .u64 param_in{i}")
    params.append("    .param .u64 param_out")
    params.append("    .param .u32 param_N")
    lines.append(f".visible .entry {name}(")
    lines.append(",\n".join(params))
    lines.append(") {")

    # Register declarations
    lines.append("    .reg .u32   %tid, %n;")
    lines.append("    .reg .u64   %off;")
    lines.append("    .reg .pred  %p;")
    for i in range(n_inputs):
        lines.append(f"    .reg .u64   %addr_in{i};")
        lines.append(f"    .reg .f32   %v_in{i};")
    # Temporaries for intermediate results
    n_temps = max(len(chain.ops), 1)
    for i in range(n_temps):
        lines.append(f"    .reg .f32   %t{i};")
    lines.append("    .reg .u64   %addr_out;")
    lines.append("")

    # Thread index
    lines.append("    mov.u32     %tid, %ctaid.x;")
    lines.append("    mul.lo.u32  %tid, %tid, %ntid.x;")
    lines.append("    mov.u32     %n, %tid.x;")
    lines.append("    add.u32     %tid, %tid, %n;")
    lines.append("")

    # Bounds check
    lines.append("    ld.param.u32 %n, [param_N];")
    lines.append("    setp.ge.u32  %p, %tid, %n;")
    lines.append("    @%p bra      $L_exit;")
    lines.append("")

    # Byte offset
    lines.append("    cvt.u64.u32  %off, %tid;")
    lines.append("    shl.b64      %off, %off, 2;")
    lines.append("")

    # Load inputs
    for i in range(n_inputs):
        lines.append(f"    ld.param.u64 %addr_in{i}, [param_in{i}];")
        lines.append(f"    add.u64      %addr_in{i}, %addr_in{i}, %off;")
        lines.append(f"    ld.global.f32 %v_in{i}, [%addr_in{i}];")
    lines.append("")

    # Map VReg → PTX register name
    reg_map: dict[int, str] = {}
    for i, vreg in enumerate(chain.input_regs):
        reg_map[vreg.index] = f"%v_in{i}"

    # Emit fused ops
    for idx, op in enumerate(chain.ops):
        ptx_op = _PTX_OPMAP.get(op.opcode)
        if ptx_op is None:
            continue
        dest_name = f"%t{idx}"
        if isinstance(op.dest, VReg):
            reg_map[op.dest.index] = dest_name

        src1_name = _ptx_operand(op.src1, reg_map)
        src2_name = _ptx_operand(op.src2, reg_map)

        if op.opcode == Opcode.Q_VFMA:
            # fma.rn.f32 dest, src1, src2, <accumulator from previous>
            lines.append(f"    {ptx_op}  {dest_name}, {src1_name}, {src2_name}, {dest_name};")
        elif op.opcode in (Opcode.Q_VMIN, Opcode.Q_VMAX):
            lines.append(f"    {ptx_op}      {dest_name}, {src1_name}, {src2_name};")
        else:
            lines.append(f"    {ptx_op}      {dest_name}, {src1_name}, {src2_name};")
    lines.append("")

    # Store output
    final_reg = reg_map.get(
        chain.output_reg.index, f"%t{len(chain.ops) - 1}"
    )
    lines.append("    ld.param.u64 %addr_out, [param_out];")
    lines.append("    add.u64      %addr_out, %addr_out, %off;")
    lines.append(f"    st.global.f32 [%addr_out], {final_reg};")
    lines.append("")
    lines.append("$L_exit:")
    lines.append("    ret;")
    lines.append("}")

    return GPUKernel(
        name=name,
        target=GPUTarget.CUDA,
        source="\n".join(lines),
        block_size=(256, 1, 1),
        num_buffers=n_inputs + 1,
        num_scalars=1,
    )


def _ptx_operand(op, reg_map: dict[int, str]) -> str:
    if isinstance(op, VReg):
        return reg_map.get(op.index, f"%v_in0")
    if isinstance(op, Immediate):
        # PTX float immediate
        import struct as _st
        bits = _st.pack("<f", float(op.value))
        hex_val = "".join(f"{b:02X}" for b in reversed(bits))
        return f"0f{hex_val}"
    return "%v_in0"


# ── MSL Code Generation ───────────────────────────────────

def _gen_msl_kernel(name: str, chain: FusedChain) -> GPUKernel:
    """Generate a fused MSL kernel from a chain of element-wise ops."""
    n_inputs = len(chain.input_regs)
    lines: list[str] = []

    lines.append("#include <metal_stdlib>")
    lines.append("using namespace metal;")
    lines.append("")

    # Signature
    params = []
    for i in range(n_inputs):
        params.append(f"    device const float* in{i} [[buffer({i})]]")
    params.append(f"    device float*       out  [[buffer({n_inputs})]]")
    params.append(f"    constant uint&      N    [[buffer({n_inputs + 1})]]")
    params.append("    uint tid [[thread_position_in_grid]]")

    lines.append(f"kernel void {name}(")
    lines.append(",\n".join(params))
    lines.append(") {")
    lines.append("    if (tid >= N) return;")
    lines.append("")

    # Load inputs
    for i in range(n_inputs):
        lines.append(f"    float v{i} = in{i}[tid];")
    lines.append("")

    # Map VReg → MSL variable name
    reg_map: dict[int, str] = {}
    for i, vreg in enumerate(chain.input_regs):
        reg_map[vreg.index] = f"v{i}"

    # Emit fused ops
    for idx, op in enumerate(chain.ops):
        dest_name = f"t{idx}"
        if isinstance(op.dest, VReg):
            reg_map[op.dest.index] = dest_name

        src1 = _msl_operand(op.src1, reg_map)
        src2 = _msl_operand(op.src2, reg_map)
        msl_op = _MSL_OPMAP.get(op.opcode, "+")

        if op.opcode in (Opcode.Q_VMIN, Opcode.Q_VMAX, Opcode.Q_VFMA):
            if op.opcode == Opcode.Q_VFMA:
                lines.append(f"    float {dest_name} = fma({src1}, {src2}, {src1});")
            else:
                lines.append(f"    float {dest_name} = {msl_op}({src1}, {src2});")
        else:
            lines.append(f"    float {dest_name} = {src1} {msl_op} {src2};")
    lines.append("")

    # Store
    final_var = reg_map.get(
        chain.output_reg.index, f"t{len(chain.ops) - 1}"
    )
    lines.append(f"    out[tid] = {final_var};")
    lines.append("}")

    return GPUKernel(
        name=name,
        target=GPUTarget.METAL,
        source="\n".join(lines),
        block_size=(256, 1, 1),
        num_buffers=n_inputs + 1,
        num_scalars=1,
    )


def _msl_operand(op, reg_map: dict[int, str]) -> str:
    if isinstance(op, VReg):
        return reg_map.get(op.index, "v0")
    if isinstance(op, Immediate):
        return f"{float(op.value):.6f}f"
    return "v0"


# ── Launch Config ──────────────────────────────────────────

@dataclass
class LaunchConfig:
    """GPU launch configuration."""
    grid: tuple[int, int, int]
    block: tuple[int, int, int]
    shared_mem: int = 0


def compute_launch_config(
    n_elements: int,
    kernel: GPUKernel,
) -> LaunchConfig:
    """Compute grid/block dimensions for a kernel launch."""
    bx, by, bz = kernel.block_size
    block_total = bx * by * bz

    if by == 1 and bz == 1:
        # 1D kernel
        grid_x = (n_elements + bx - 1) // bx
        return LaunchConfig(
            grid=(grid_x, 1, 1),
            block=kernel.block_size,
            shared_mem=kernel.shared_mem_bytes,
        )
    else:
        # 2D kernel (e.g., GEMM)
        grid_x = (n_elements + bx - 1) // bx
        grid_y = (n_elements + by - 1) // by
        return LaunchConfig(
            grid=(grid_x, grid_y, 1),
            block=kernel.block_size,
            shared_mem=kernel.shared_mem_bytes,
        )


# ── High-Level API ─────────────────────────────────────────

class GPUCodeGenerator:
    """
    Generates GPU kernels from Q-IR modules.

    Usage::

        gen = GPUCodeGenerator()
        kernels = gen.compile_function(qfunc)
        for k in kernels:
            print(k.source)
    """

    def __init__(self, target: GPUTarget | None = None):
        self.target = target or detect_gpu_target()
        self._kernel_counter = 0

    def compile_function(self, func: QFunction) -> list[GPUKernel]:
        """
        Analyze a Q-IR function for GPU-offloadable regions and
        generate kernels for each.
        """
        chains = detect_fuseable_chains(func.body)
        kernels: list[GPUKernel] = []

        for chain in chains:
            name = f"vir_{func.name}_fused_{self._kernel_counter}"
            self._kernel_counter += 1

            if self.target == GPUTarget.CUDA:
                kernels.append(_gen_ptx_kernel(name, chain))
            else:
                kernels.append(_gen_msl_kernel(name, chain))

        return kernels

    def compile_module(self, module: QModule) -> list[GPUKernel]:
        """Generate GPU kernels for all functions in a Q-IR module."""
        kernels: list[GPUKernel] = []
        for func in module.functions:
            kernels.extend(self.compile_function(func))
        return kernels

    def get_builtin(self, name: str) -> GPUKernel:
        """Load a prebuilt kernel template."""
        return load_builtin_kernel(name, self.target)

    def list_builtins(self) -> list[str]:
        """List available prebuilt kernels."""
        return list_builtin_kernels()

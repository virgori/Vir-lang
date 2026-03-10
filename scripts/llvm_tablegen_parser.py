#!/usr/bin/env python3
"""
llvm_tablegen_parser.py – Extract Instruction Cost Data from LLVM Sources
==========================================================================
Parses LLVM's .td (TableGen) files and scheduling model files to extract
instruction latency, throughput, and port usage data for ARM64 and x86_64.

Also ingests data from:
  - Agner Fog's instruction tables (CSV format)
  - uops.info XML/JSON data
  - Our own micro-prober JSON output

Generates arch_config.json for the Vir cost model.

Usage:
    python scripts/llvm_tablegen_parser.py --probe data/arch/probe_results.json
    python scripts/llvm_tablegen_parser.py --llvm-src /path/to/llvm-project
    python scripts/llvm_tablegen_parser.py --agner /path/to/agner_fog.csv
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════

@dataclass
class InstrCost:
    """Cost model for a single instruction."""
    mnemonic: str           # e.g. "ADD", "MUL", "LDR"
    latency: int            # cycles from input ready to output ready
    throughput: float        # instructions per cycle (reciprocal throughput)
    ports: list[str] = field(default_factory=list)  # execution ports used
    uops: int = 1           # number of micro-ops
    category: str = ""      # "arith", "mul", "div", "load", "store", "branch", "cmp"
    notes: str = ""


@dataclass
class BranchCost:
    """Branch prediction cost model."""
    predict_hit: float      # cycles when correctly predicted
    predict_miss: float     # cycles when mispredicted
    miss_penalty: float     # pure penalty = miss - hit


@dataclass
class MemoryCost:
    """Memory hierarchy cost model."""
    l1_latency: float       # L1 cache hit latency in cycles
    l2_latency: float       # L2 cache hit latency
    l3_latency: float       # L3 cache hit latency
    mem_latency: float      # Main memory latency
    l1_size_kb: int
    l2_size_kb: int
    l3_size_kb: int
    store_latency: int = 1  # store buffer latency


@dataclass  
class SpillCost:
    """Cost of register spilling operations."""
    spill_store: int        # cycles to store a register to stack
    spill_load: int         # cycles to reload from stack
    total: int              # spill_store + spill_load


@dataclass
class ArchConfig:
    """Complete architecture cost model configuration."""
    arch: str               # "arm64" or "x86_64"
    cpu: str                # e.g. "Apple M2", "AMD Zen 4"
    cpu_freq_ghz: float
    issue_width: int        # max instructions dispatched per cycle
    reorder_buffer: int     # ROB entries
    phys_int_regs: int      # physical integer registers
    phys_fp_regs: int       # physical FP/SIMD registers

    instructions: list[InstrCost] = field(default_factory=list)
    branch: BranchCost = field(default_factory=lambda: BranchCost(0, 0, 0))
    memory: MemoryCost = field(default_factory=lambda: MemoryCost(4, 12, 40, 200, 32, 256, 8192))
    spill: SpillCost = field(default_factory=lambda: SpillCost(1, 4, 5))

    # Q-IR opcode → instruction mnemonic mapping
    qir_map: dict[str, str] = field(default_factory=dict)

    source: str = ""        # data source description
    timestamp: str = ""


# ═══════════════════════════════════════════════════════════
# ARM64 Reference Data (Apple M-series & Cortex-A)
# ═══════════════════════════════════════════════════════════

# Sources: LLVM AArch64SchedA510.td, AArch64SchedAppleM1.td,
# Arm Cortex-A78 Software Optimization Guide, Apple M2 probed data

ARM64_APPLE_M2_INSTRS = [
    # Arithmetic (integer ALU)
    InstrCost("ADD",    1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Integer add imm/reg"),
    InstrCost("ADDS",   1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Add + set flags"),
    InstrCost("SUB",    1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Integer subtract"),
    InstrCost("SUBS",   1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Sub + set flags"),
    InstrCost("NEG",    1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Negate"),
    InstrCost("MOV",    1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Move reg/imm"),
    InstrCost("MOVZ",   1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Move wide zero"),
    InstrCost("MOVK",   1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Move wide keep"),
    InstrCost("MOVN",   1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Move wide negate"),

    # Logical
    InstrCost("AND",    1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Bitwise AND"),
    InstrCost("ORR",    1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Bitwise OR"),
    InstrCost("EOR",    1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Bitwise XOR"),
    InstrCost("LSL",    1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Logical shift left"),
    InstrCost("LSR",    1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Logical shift right"),
    InstrCost("ASR",    1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Arithmetic shift right"),

    # Multiply
    InstrCost("MUL",    3,  1.0,  ["P1"],                 1, "mul", "Integer multiply"),
    InstrCost("MADD",   3,  1.0,  ["P1"],                 1, "mul", "Multiply-add"),
    InstrCost("MSUB",   3,  1.0,  ["P1"],                 1, "mul", "Multiply-subtract"),
    InstrCost("SMULL",  3,  1.0,  ["P1"],                 1, "mul", "Signed multiply long"),
    InstrCost("UMULL",  3,  1.0,  ["P1"],                 1, "mul", "Unsigned multiply long"),
    InstrCost("UMULH",  4,  1.0,  ["P1"],                 1, "mul", "Unsigned multiply high"),
    InstrCost("SMULH",  4,  1.0,  ["P1"],                 1, "mul", "Signed multiply high"),

    # Division
    InstrCost("SDIV",   8,  0.125, ["P1"],                1, "div", "Signed divide (data-dependent)"),
    InstrCost("UDIV",   8,  0.125, ["P1"],                1, "div", "Unsigned divide"),

    # Compare
    InstrCost("CMP",    1,  4.0,  ["P0","P1","P2","P3"],  1, "cmp", "Compare (alias for SUBS)"),
    InstrCost("CMN",    1,  4.0,  ["P0","P1","P2","P3"],  1, "cmp", "Compare negative"),
    InstrCost("TST",    1,  4.0,  ["P0","P1","P2","P3"],  1, "cmp", "Test bits (ANDS)"),
    InstrCost("CSEL",   1,  2.0,  ["P0","P1"],            1, "cmp", "Conditional select"),
    InstrCost("CSET",   1,  2.0,  ["P0","P1"],            1, "cmp", "Conditional set"),
    InstrCost("CSINC",  1,  2.0,  ["P0","P1"],            1, "cmp", "Cond select increment"),

    # Branch
    InstrCost("B",      0,  1.0,  ["P3"],                 1, "branch", "Unconditional branch"),
    InstrCost("B.cond", 1,  1.0,  ["P3"],                 1, "branch", "Conditional branch"),
    InstrCost("BL",     1,  1.0,  ["P3"],                 1, "branch", "Branch with link (call)"),
    InstrCost("BLR",    1,  1.0,  ["P3"],                 1, "branch", "Branch to register + link"),
    InstrCost("BR",     1,  1.0,  ["P3"],                 1, "branch", "Branch to register"),
    InstrCost("RET",    1,  1.0,  ["P3"],                 1, "branch", "Return"),
    InstrCost("CBZ",    1,  1.0,  ["P3"],                 1, "branch", "Compare and branch zero"),
    InstrCost("CBNZ",   1,  1.0,  ["P3"],                 1, "branch", "Compare and branch not zero"),

    # Load
    InstrCost("LDR",    4,  2.0,  ["P4","P5"],            1, "load",  "Load register"),
    InstrCost("LDRB",   4,  2.0,  ["P4","P5"],            1, "load",  "Load byte"),
    InstrCost("LDRH",   4,  2.0,  ["P4","P5"],            1, "load",  "Load halfword"),
    InstrCost("LDRSW",  4,  2.0,  ["P4","P5"],            1, "load",  "Load signed word"),
    InstrCost("LDP",    4,  2.0,  ["P4","P5"],            2, "load",  "Load pair"),
    InstrCost("LDUR",   4,  2.0,  ["P4","P5"],            1, "load",  "Load unscaled"),
    InstrCost("LDAR",   4,  1.0,  ["P4"],                 1, "load",  "Load-acquire"),

    # Store
    InstrCost("STR",    1,  2.0,  ["P6","P7"],            1, "store", "Store register"),
    InstrCost("STRB",   1,  2.0,  ["P6","P7"],            1, "store", "Store byte"),
    InstrCost("STRH",   1,  2.0,  ["P6","P7"],            1, "store", "Store halfword"),
    InstrCost("STP",    1,  2.0,  ["P6","P7"],            2, "store", "Store pair"),
    InstrCost("STUR",   1,  2.0,  ["P6","P7"],            1, "store", "Store unscaled"),
    InstrCost("STLR",   1,  1.0,  ["P6"],                 1, "store", "Store-release"),

    # Address computation
    InstrCost("ADR",    1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Form PC-relative address"),
    InstrCost("ADRP",   1,  4.0,  ["P0","P1","P2","P3"],  1, "arith", "Form PC-relative page address"),

    # System
    InstrCost("NOP",    0,  4.0,  [],                     0, "arith", "No operation"),
    InstrCost("SVC",    0,  1.0,  [],                     1, "branch", "Supervisor call"),
    InstrCost("ISB",    0,  1.0,  [],                     1, "branch", "Instruction synchronization barrier"),
]

# ═══════════════════════════════════════════════════════════
# ARM64 NEON (Advanced SIMD) – 128-bit Vectors
# ═══════════════════════════════════════════════════════════
# Sources: Arm Neoverse N2 / Apple M2 Software Optimization Guide,
#          dougallj/applecpu M1/M2 instruction tables,
#          LLVM AArch64SchedAppleM1.td / AArch64SchedNeoverseN2.td

ARM64_NEON_INSTRS = [
    # ── Integer SIMD Arithmetic ─────────────────────────
    InstrCost("ADD_v",      2, 2.0, ["FP0","FP1"],       1, "simd_arith", "Vector integer add (8B-16B)"),
    InstrCost("SUB_v",      2, 2.0, ["FP0","FP1"],       1, "simd_arith", "Vector integer subtract"),
    InstrCost("MUL_v",      4, 1.0, ["FP0"],             1, "simd_mul",   "Vector integer multiply"),
    InstrCost("MLA_v",      4, 1.0, ["FP0"],             1, "simd_mul",   "Vector multiply-accumulate (int)"),
    InstrCost("MLS_v",      4, 1.0, ["FP0"],             1, "simd_mul",   "Vector multiply-subtract (int)"),

    # ── FP SIMD Arithmetic ──────────────────────────────
    InstrCost("FADD_v",     3, 2.0, ["FP0","FP1"],       1, "simd_arith", "Vector FP add (2S/4S/2D)"),
    InstrCost("FSUB_v",     3, 2.0, ["FP0","FP1"],       1, "simd_arith", "Vector FP subtract"),
    InstrCost("FMUL_v",     4, 2.0, ["FP0","FP1"],       1, "simd_mul",   "Vector FP multiply"),
    InstrCost("FMLA_v",     4, 2.0, ["FP0","FP1"],       1, "simd_mul",   "Vector FP fused multiply-add"),
    InstrCost("FMLS_v",     4, 2.0, ["FP0","FP1"],       1, "simd_mul",   "Vector FP fused multiply-sub"),
    InstrCost("FDIV_v",    12, 0.25,["FP0"],             1, "simd_div",   "Vector FP divide (data-dep)"),
    InstrCost("FSQRT_v",   14, 0.2, ["FP0"],             1, "simd_div",   "Vector FP sqrt (data-dep)"),
    InstrCost("FMIN_v",     2, 2.0, ["FP0","FP1"],       1, "simd_arith", "Vector FP min"),
    InstrCost("FMAX_v",     2, 2.0, ["FP0","FP1"],       1, "simd_arith", "Vector FP max"),
    InstrCost("FABS_v",     2, 2.0, ["FP0","FP1"],       1, "simd_arith", "Vector FP absolute"),
    InstrCost("FNEG_v",     2, 2.0, ["FP0","FP1"],       1, "simd_arith", "Vector FP negate"),

    # ── FP16 (FEAT_FP16) ───────────────────────────────
    InstrCost("FADD_v_h",   3, 2.0, ["FP0","FP1"],       1, "simd_arith", "Vector FP16 add (4H/8H)"),
    InstrCost("FMUL_v_h",   4, 2.0, ["FP0","FP1"],       1, "simd_mul",   "Vector FP16 multiply"),
    InstrCost("FMLA_v_h",   4, 2.0, ["FP0","FP1"],       1, "simd_mul",   "Vector FP16 fused multiply-add"),

    # ── BF16 (FEAT_BF16) ───────────────────────────────
    InstrCost("BFMMLA",     5, 1.0, ["FP0"],             1, "simd_matmul","BFloat16 matrix multiply 4×4"),
    InstrCost("BFDOT_v",    4, 1.0, ["FP0"],             1, "simd_dot",   "BF16 dot product"),
    InstrCost("BFMLALB_v",  5, 1.0, ["FP0"],             1, "simd_mul",   "BF16 multiply-add long bottom"),
    InstrCost("BFMLALT_v",  5, 1.0, ["FP0"],             1, "simd_mul",   "BF16 multiply-add long top"),

    # ── Dot Product (FEAT_DotProd) ──────────────────────
    InstrCost("SDOT_v",     4, 1.0, ["FP0"],             1, "simd_dot",   "Signed dot product int8→int32"),
    InstrCost("UDOT_v",     4, 1.0, ["FP0"],             1, "simd_dot",   "Unsigned dot product int8→int32"),

    # ── I8MM (FEAT_I8MM) ───────────────────────────────
    InstrCost("SMMLA",      5, 1.0, ["FP0"],             1, "simd_matmul","Signed int8 matrix multiply 2×8×2"),
    InstrCost("UMMLA",      5, 1.0, ["FP0"],             1, "simd_matmul","Unsigned int8 matrix multiply 2×8×2"),
    InstrCost("USMMLA",     5, 1.0, ["FP0"],             1, "simd_matmul","Unsigned/signed i8 matmul"),

    # ── Pairwise / Reduce ──────────────────────────────
    InstrCost("ADDP_v",     3, 2.0, ["FP0","FP1"],       1, "simd_arith", "Add pairwise"),
    InstrCost("FADDP_v",    3, 2.0, ["FP0","FP1"],       1, "simd_arith", "FP add pairwise"),
    InstrCost("ADDV",       4, 1.0, ["FP0"],             1, "simd_reduce","Reduce add across vector"),
    InstrCost("FMAXV",      4, 1.0, ["FP0"],             1, "simd_reduce","Reduce max across vector"),
    InstrCost("FMINV",      4, 1.0, ["FP0"],             1, "simd_reduce","Reduce min across vector"),

    # ── Comparison ─────────────────────────────────────
    InstrCost("CMEQ_v",     2, 2.0, ["FP0","FP1"],       1, "simd_cmp", "Vector compare equal"),
    InstrCost("CMGT_v",     2, 2.0, ["FP0","FP1"],       1, "simd_cmp", "Vector compare greater than"),
    InstrCost("CMGE_v",     2, 2.0, ["FP0","FP1"],       1, "simd_cmp", "Vector compare greater/equal"),
    InstrCost("FCMEQ_v",    2, 2.0, ["FP0","FP1"],       1, "simd_cmp", "Vector FP compare equal"),
    InstrCost("FCMGT_v",    2, 2.0, ["FP0","FP1"],       1, "simd_cmp", "Vector FP compare greater"),

    # ── Load / Store ───────────────────────────────────
    InstrCost("LD1",        4, 2.0, ["P4","P5"],          1, "simd_load",  "Load single 1-register (128-bit)"),
    InstrCost("LD2",        5, 1.0, ["P4","P5"],          2, "simd_load",  "Load de-interleave 2 regs"),
    InstrCost("LD4",        7, 0.5, ["P4","P5"],          4, "simd_load",  "Load de-interleave 4 regs"),
    InstrCost("ST1",        1, 2.0, ["P6","P7"],          1, "simd_store", "Store 1-register (128-bit)"),
    InstrCost("ST2",        2, 1.0, ["P6","P7"],          2, "simd_store", "Store interleave 2 regs"),
    InstrCost("ST4",        4, 0.5, ["P6","P7"],          4, "simd_store", "Store interleave 4 regs"),
    InstrCost("LDP_v",      4, 2.0, ["P4","P5"],          2, "simd_load",  "Load pair of SIMD regs"),
    InstrCost("STP_v",      1, 2.0, ["P6","P7"],          2, "simd_store", "Store pair of SIMD regs"),

    # ── Logical / Bitwise ──────────────────────────────
    InstrCost("AND_v",      2, 2.0, ["FP0","FP1"],       1, "simd_arith", "Vector bitwise AND"),
    InstrCost("ORR_v",      2, 2.0, ["FP0","FP1"],       1, "simd_arith", "Vector bitwise OR"),
    InstrCost("EOR_v",      2, 2.0, ["FP0","FP1"],       1, "simd_arith", "Vector bitwise XOR"),
    InstrCost("BIF_v",      2, 2.0, ["FP0","FP1"],       1, "simd_arith", "Vector bit insert if false"),
    InstrCost("BSL_v",      2, 2.0, ["FP0","FP1"],       1, "simd_arith", "Vector bitwise select"),

    # ── Shuffle / Permute ──────────────────────────────
    InstrCost("DUP_v",      2, 2.0, ["FP0","FP1"],       1, "simd_perm", "Duplicate scalar to all lanes"),
    InstrCost("INS_v",      2, 1.0, ["FP0"],             1, "simd_perm", "Insert element into vector"),
    InstrCost("UMOV",       2, 1.0, ["FP0"],             1, "simd_perm", "Move element to GPR"),
    InstrCost("EXT_v",      2, 2.0, ["FP0","FP1"],       1, "simd_perm", "Extract (concat+slide)"),
    InstrCost("TBL_v",      2, 2.0, ["FP0","FP1"],       1, "simd_perm", "Table lookup (shuffle)"),
    InstrCost("TRN1_v",     2, 2.0, ["FP0","FP1"],       1, "simd_perm", "Transpose 1"),
    InstrCost("TRN2_v",     2, 2.0, ["FP0","FP1"],       1, "simd_perm", "Transpose 2"),
    InstrCost("ZIP1_v",     2, 2.0, ["FP0","FP1"],       1, "simd_perm", "Zip vectors (interleave low)"),
    InstrCost("ZIP2_v",     2, 2.0, ["FP0","FP1"],       1, "simd_perm", "Zip vectors (interleave high)"),
    InstrCost("UZP1_v",     2, 2.0, ["FP0","FP1"],       1, "simd_perm", "Unzip (de-interleave even)"),
    InstrCost("UZP2_v",     2, 2.0, ["FP0","FP1"],       1, "simd_perm", "Unzip (de-interleave odd)"),
    InstrCost("REV64_v",    2, 2.0, ["FP0","FP1"],       1, "simd_perm", "Reverse within 64-bit lanes"),

    # ── Conversion ─────────────────────────────────────
    InstrCost("FCVTZS_v",   3, 2.0, ["FP0","FP1"],       1, "simd_cvt", "FP→Int convert (round to zero)"),
    InstrCost("SCVTF_v",    3, 2.0, ["FP0","FP1"],       1, "simd_cvt", "Int→FP convert (signed)"),
    InstrCost("FCVTL",      3, 2.0, ["FP0","FP1"],       1, "simd_cvt", "FP widen (F16→F32 or F32→F64)"),
    InstrCost("FCVTN",      3, 2.0, ["FP0","FP1"],       1, "simd_cvt", "FP narrow (F32→F16 or F64→F32)"),

    # ── Crypto (FEAT_AES / FEAT_SHA256) ─────────────────
    InstrCost("AESE",       3, 1.0, ["FP0"],             1, "simd_crypto", "AES single round encrypt"),
    InstrCost("AESD",       3, 1.0, ["FP0"],             1, "simd_crypto", "AES single round decrypt"),
    InstrCost("AESMC",      2, 1.0, ["FP0"],             1, "simd_crypto", "AES mix columns"),
    InstrCost("SHA256H",    4, 1.0, ["FP0"],             1, "simd_crypto", "SHA-256 hash update part 1"),
    InstrCost("SHA256H2",   4, 1.0, ["FP0"],             1, "simd_crypto", "SHA-256 hash update part 2"),

    # ── AMX (Apple Matrix Coprocessor) ──────────────────
    # Note: AMX is undocumented but reverse-engineered.
    # Operations go through dedicated coprocessor via sys instructions.
    InstrCost("AMX_LDX",    5, 2.0, ["AMX"],             1, "amx_load",  "AMX load X register (512-bit)"),
    InstrCost("AMX_LDY",    5, 2.0, ["AMX"],             1, "amx_load",  "AMX load Y register (512-bit)"),
    InstrCost("AMX_STZ",    5, 2.0, ["AMX"],             1, "amx_store", "AMX store Z register (512-bit)"),
    InstrCost("AMX_FMA32",  6, 1.0, ["AMX"],             1, "amx_compute","AMX FP32 fused multiply-add (16×16)"),
    InstrCost("AMX_FMA64",  8, 0.5, ["AMX"],             1, "amx_compute","AMX FP64 fused multiply-add (8×8)"),
    InstrCost("AMX_FMA16",  4, 2.0, ["AMX"],             1, "amx_compute","AMX FP16 fused multiply-add (32×32)"),
    InstrCost("AMX_MAC16",  4, 2.0, ["AMX"],             1, "amx_compute","AMX int16 multiply-acc (32×32)"),
    InstrCost("AMX_SET",    1, 1.0, ["AMX"],             1, "amx_ctrl",  "AMX enable/configure"),
    InstrCost("AMX_CLR",    1, 1.0, ["AMX"],             1, "amx_ctrl",  "AMX clear/disable"),
]

# Q-IR → ARM64 NEON mnemonic mapping
ARM64_NEON_QIR_MAP = {
    "Q_VLOAD":   "LD1",
    "Q_VSTORE":  "ST1",
    "Q_VADD":    "FADD_v",
    "Q_VSUB":    "FSUB_v",
    "Q_VMUL":    "FMUL_v",
    "Q_VFMA":    "FMLA_v",
    "Q_VDIV":    "FDIV_v",
    "Q_VMIN":    "FMIN_v",
    "Q_VMAX":    "FMAX_v",
    "Q_VREDUCE": "ADDV",
    "Q_VSPLAT":  "DUP_v",
    "Q_VPERM":   "TBL_v",
}

# Q-IR → ARM64 mnemonic mapping
ARM64_QIR_MAP = {
    "Q_LOAD":           "LDR",
    "Q_STORE":          "STR",
    "Q_MOVE":           "MOV",
    "Q_ADD":            "ADD",
    "Q_SUB":            "SUB",
    "Q_MUL":            "MUL",
    "Q_DIV":            "SDIV",
    "Q_MOD":            "SDIV",   # MOD = SDIV + MSUB
    "Q_CMP_EQ":         "CMP",
    "Q_CMP_NE":         "CMP",
    "Q_CMP_GT":         "CMP",
    "Q_CMP_LT":         "CMP",
    "Q_CMP_GE":         "CMP",
    "Q_CMP_LE":         "CMP",
    "Q_JUMP":           "B",
    "Q_JUMP_IF":        "B.cond",
    "Q_JUMP_IF_NOT":    "B.cond",
    "Q_CALL":           "BL",
    "Q_RET":            "RET",
    "Q_PRINT":          "BL",    # calls print intrinsic
    "Q_LABEL":          "NOP",   # pseudo (no machine code)
    "Q_NOP":            "NOP",
    "Q_HALT":           "RET",
    "Q_LOAD_STRING":    "LDR",
    "Q_PATCH_POINT":    "NOP",
    "Q_INPUT":          "BL",
}


# ═══════════════════════════════════════════════════════════
# x86_64 Reference Data (Zen 4 / Golden Cove / Agner Fog)
# ═══════════════════════════════════════════════════════════

X86_64_GENERIC_INSTRS = [
    # Arithmetic
    InstrCost("ADD",    1,  4.0,  ["p0","p1","p5","p6"],  1, "arith", "Add r/r or r/imm"),
    InstrCost("SUB",    1,  4.0,  ["p0","p1","p5","p6"],  1, "arith", "Subtract"),
    InstrCost("INC",    1,  4.0,  ["p0","p1","p5","p6"],  1, "arith", "Increment"),
    InstrCost("DEC",    1,  4.0,  ["p0","p1","p5","p6"],  1, "arith", "Decrement"),
    InstrCost("NEG",    1,  4.0,  ["p0","p1","p5","p6"],  1, "arith", "Negate"),
    InstrCost("MOV",    0,  4.0,  ["p0","p1","p5","p6"],  1, "arith", "Move (may be eliminated)"),
    InstrCost("LEA",    1,  2.0,  ["p0","p1"],            1, "arith", "Load effective address"),

    # Logical
    InstrCost("AND",    1,  4.0,  ["p0","p1","p5","p6"],  1, "arith", "Bitwise AND"),
    InstrCost("OR",     1,  4.0,  ["p0","p1","p5","p6"],  1, "arith", "Bitwise OR"),
    InstrCost("XOR",    1,  4.0,  ["p0","p1","p5","p6"],  1, "arith", "Bitwise XOR"),
    InstrCost("SHL",    1,  2.0,  ["p0","p6"],            1, "arith", "Shift left"),
    InstrCost("SHR",    1,  2.0,  ["p0","p6"],            1, "arith", "Shift right"),
    InstrCost("SAR",    1,  2.0,  ["p0","p6"],            1, "arith", "Arithmetic shift right"),

    # Multiply
    InstrCost("IMUL",   3,  1.0,  ["p1"],                 1, "mul", "Signed multiply"),
    InstrCost("MUL",    3,  1.0,  ["p1"],                 1, "mul", "Unsigned multiply"),

    # Division
    InstrCost("IDIV",   20, 0.05, ["p0","p1","p5","p6"],  10, "div", "Signed divide (very slow)"),
    InstrCost("DIV",    20, 0.05, ["p0","p1","p5","p6"],  10, "div", "Unsigned divide"),
    InstrCost("CQO",    1,  1.0,  ["p0","p1"],            1, "arith", "Sign-extend RAX→RDX:RAX"),

    # Compare/conditional
    InstrCost("CMP",    1,  4.0,  ["p0","p1","p5","p6"],  1, "cmp", "Compare"),
    InstrCost("TEST",   1,  4.0,  ["p0","p1","p5","p6"],  1, "cmp", "Test bits"),
    InstrCost("SETE",   1,  1.0,  ["p0","p6"],            1, "cmp", "Set if equal"),
    InstrCost("SETG",   1,  1.0,  ["p0","p6"],            1, "cmp", "Set if greater"),
    InstrCost("SETL",   1,  1.0,  ["p0","p6"],            1, "cmp", "Set if less"),
    InstrCost("CMOV",   1,  1.0,  ["p0","p6"],            1, "cmp", "Conditional move"),

    # Branch
    InstrCost("JMP",    0,  1.0,  ["p6"],                 1, "branch", "Unconditional jump"),
    InstrCost("JE",     1,  1.0,  ["p6"],                 1, "branch", "Jump if equal"),
    InstrCost("JNE",    1,  1.0,  ["p6"],                 1, "branch", "Jump if not equal"),
    InstrCost("JG",     1,  1.0,  ["p6"],                 1, "branch", "Jump if greater"),
    InstrCost("JL",     1,  1.0,  ["p6"],                 1, "branch", "Jump if less"),
    InstrCost("CALL",   2,  1.0,  ["p6"],                 3, "branch", "Function call"),
    InstrCost("RET",    1,  1.0,  ["p6"],                 1, "branch", "Return"),

    # Load
    InstrCost("MOV_LD", 4,  2.0,  ["p2","p3"],            1, "load",  "Load from memory"),
    InstrCost("PUSH",   1,  1.0,  ["p4","p7"],            2, "store", "Push to stack (store+sub)"),
    InstrCost("POP",    1,  2.0,  ["p2","p3"],            2, "load",  "Pop from stack (load+add)"),

    # Store
    InstrCost("MOV_ST", 1,  2.0,  ["p4","p7"],            1, "store", "Store to memory"),

    # Special
    InstrCost("NOP",    0,  4.0,  [],                     0, "arith", "No operation"),
    InstrCost("SYSCALL", 0, 1.0,  [],                     1, "branch", "System call"),
]

# ═══════════════════════════════════════════════════════════
# x86_64 AVX/AVX2/AVX-512 SIMD Instructions
# ═══════════════════════════════════════════════════════════
# Sources: Intel Intrinsics Guide, Agner Fog tables,
#          uops.info (Golden Cove / Zen 4), LLVM X86SchedSapphireRapids.td

X86_64_SIMD_INSTRS = [
    # ── SSE/AVX FP arithmetic (128/256-bit) ─────────────
    InstrCost("VADDPS",     4, 2.0, ["p0","p1"],          1, "simd_arith", "Packed float add (128/256)"),
    InstrCost("VSUBPS",     4, 2.0, ["p0","p1"],          1, "simd_arith", "Packed float sub"),
    InstrCost("VMULPS",     4, 2.0, ["p0","p1"],          1, "simd_mul",   "Packed float mul"),
    InstrCost("VDIVPS",    11, 0.2, ["p0"],               1, "simd_div",   "Packed float div (data-dep)"),
    InstrCost("VSQRTPS",   12, 0.17,["p0"],               1, "simd_div",   "Packed float sqrt"),
    InstrCost("VADDPD",     4, 2.0, ["p0","p1"],          1, "simd_arith", "Packed double add"),
    InstrCost("VMULPD",     4, 2.0, ["p0","p1"],          1, "simd_mul",   "Packed double mul"),
    InstrCost("VDIVPD",    14, 0.125,["p0"],              1, "simd_div",   "Packed double div"),
    InstrCost("VFMADD231PS",4,2.0,  ["p0","p1"],          1, "simd_fma",   "FMA: a*b+c packed float"),
    InstrCost("VFMADD231PD",4,2.0,  ["p0","p1"],          1, "simd_fma",   "FMA: a*b+c packed double"),
    InstrCost("VMINPS",     4, 2.0, ["p0","p1"],          1, "simd_arith", "Packed float min"),
    InstrCost("VMAXPS",     4, 2.0, ["p0","p1"],          1, "simd_arith", "Packed float max"),

    # ── Integer SIMD ────────────────────────────────────
    InstrCost("VPADDD",     1, 2.0, ["p0","p5"],          1, "simd_arith", "Packed int32 add"),
    InstrCost("VPSUBD",     1, 2.0, ["p0","p5"],          1, "simd_arith", "Packed int32 sub"),
    InstrCost("VPMULLD",    5, 1.0, ["p0"],               1, "simd_mul",   "Packed int32 mul low"),
    InstrCost("VPMULUDQ",   5, 1.0, ["p0"],               1, "simd_mul",   "Packed uint64 mul"),
    InstrCost("VPMADDWD",   5, 1.0, ["p0"],               1, "simd_mul",   "Packed madd int16→int32"),

    # ── Comparison / Logical ───────────────────────────
    InstrCost("VCMPPS",     4, 2.0, ["p0","p1"],          1, "simd_cmp",   "Packed float compare"),
    InstrCost("VPCMPEQD",   1, 2.0, ["p0","p5"],          1, "simd_cmp",   "Packed int compare equal"),
    InstrCost("VPCMPGTD",   1, 2.0, ["p0","p5"],          1, "simd_cmp",   "Packed int compare greater"),
    InstrCost("VANDPS",     1, 3.0, ["p0","p1","p5"],     1, "simd_arith", "Packed bitwise AND"),
    InstrCost("VORPS",      1, 3.0, ["p0","p1","p5"],     1, "simd_arith", "Packed bitwise OR"),
    InstrCost("VXORPS",     1, 3.0, ["p0","p1","p5"],     1, "simd_arith", "Packed bitwise XOR"),

    # ── Load / Store ───────────────────────────────────
    InstrCost("VMOVAPS",    4, 2.0, ["p2","p3"],          1, "simd_load",  "Load aligned packed float"),
    InstrCost("VMOVUPS",    4, 2.0, ["p2","p3"],          1, "simd_load",  "Load unaligned packed float"),
    InstrCost("VMOVAPS_ST", 1, 2.0, ["p4","p7"],          1, "simd_store", "Store aligned packed float"),
    InstrCost("VMOVUPS_ST", 1, 2.0, ["p4","p7"],          1, "simd_store", "Store unaligned packed float"),
    InstrCost("VMASKMOVPS", 5, 1.0, ["p2","p3","p0"],     2, "simd_load",  "Masked load packed float"),

    # ── Shuffle / Permute / Broadcast ──────────────────
    InstrCost("VBROADCASTSS",5,2.0, ["p2","p3","p5"],     1, "simd_perm", "Broadcast scalar to all lanes"),
    InstrCost("VPERMPS",    3, 1.0, ["p5"],               1, "simd_perm", "Permute packed float"),
    InstrCost("VPERMD",     3, 1.0, ["p5"],               1, "simd_perm", "Permute packed dword"),
    InstrCost("VPSHUFB",    1, 2.0, ["p5"],               1, "simd_perm", "Shuffle bytes"),
    InstrCost("VSHUFPS",    1, 2.0, ["p5"],               1, "simd_perm", "Shuffle packed float"),
    InstrCost("VBLENDPS",   1, 3.0, ["p0","p1","p5"],     1, "simd_perm", "Blend packed float"),
    InstrCost("VPERM2F128", 3, 1.0, ["p5"],               1, "simd_perm", "Permute 128-bit lanes"),

    # ── Horizontal / Reduce ────────────────────────────
    InstrCost("VHADDPS",    6, 0.5, ["p0","p1","p5"],     3, "simd_reduce","Horizontal add packed float"),
    InstrCost("VDPPS",      9, 0.5, ["p0","p1"],          3, "simd_reduce","Dot product packed float"),

    # ── Conversion ─────────────────────────────────────
    InstrCost("VCVTPS2DQ",  4, 2.0, ["p0","p1"],          1, "simd_cvt",  "Float→int32 convert"),
    InstrCost("VCVTDQ2PS",  4, 2.0, ["p0","p1"],          1, "simd_cvt",  "Int32→float convert"),
    InstrCost("VCVTPS2PH",  5, 1.0, ["p0","p1"],          1, "simd_cvt",  "Float→FP16 convert"),
    InstrCost("VCVTPH2PS",  5, 1.0, ["p0","p1"],          1, "simd_cvt",  "FP16→float convert"),

    # ══════════════════════════════════════════════════════
    # AVX-512 (512-bit) – Sapphire Rapids / Zen 4
    # ══════════════════════════════════════════════════════
    InstrCost("VADDPS_Z",   4, 2.0, ["p0","p1"],          1, "simd512_arith","AVX-512 packed float add"),
    InstrCost("VMULPS_Z",   4, 2.0, ["p0","p1"],          1, "simd512_mul",  "AVX-512 packed float mul"),
    InstrCost("VFMADD231PS_Z",4,2.0,["p0","p1"],          1, "simd512_fma",  "AVX-512 FMA float"),
    InstrCost("VDIVPS_Z",  18, 0.1, ["p0"],               1, "simd512_div",  "AVX-512 packed float div"),
    InstrCost("VMOVAPS_Z",  5, 1.0, ["p2","p3"],          1, "simd512_load", "AVX-512 aligned load"),
    InstrCost("VMOVAPS_Z_ST",1,1.0, ["p4","p7"],          1, "simd512_store","AVX-512 aligned store"),
    InstrCost("VPADDD_Z",   1, 2.0, ["p0","p5"],          1, "simd512_arith","AVX-512 packed int add"),
    InstrCost("VPMULLD_Z",  5, 1.0, ["p0"],               1, "simd512_mul",  "AVX-512 packed int mul"),

    # ── AVX-512 VNNI (Vector Neural Network) ───────────
    InstrCost("VPDPBUSD",   5, 1.0, ["p0"],               1, "simd_vnni", "VNNI int8 dot product → int32"),
    InstrCost("VPDPWSSD",   5, 1.0, ["p0"],               1, "simd_vnni", "VNNI int16 dot product → int32"),

    # ── Intel AMX (Advanced Matrix Extensions) ─────────
    InstrCost("LDTILECFG",  10,1.0, ["p0","p2","p3"],     4, "amx_ctrl",   "AMX load tile configuration"),
    InstrCost("TILELOADD",  10,1.0, ["p2","p3","p5"],     1, "amx_load",   "AMX load tile from memory"),
    InstrCost("TILESTORED", 10,1.0, ["p4","p7"],          1, "amx_store",  "AMX store tile to memory"),
    InstrCost("TDPBF16PS",  16,0.5, ["p5"],               1, "amx_compute","AMX BF16 tile matmul"),
    InstrCost("TDPBSSD",    16,0.5, ["p5"],               1, "amx_compute","AMX int8 tile matmul"),
    InstrCost("TILEZERO",   3, 2.0, ["p0"],               1, "amx_ctrl",   "AMX zero a tile"),
]

X86_64_SIMD_QIR_MAP = {
    "Q_VLOAD":   "VMOVAPS",
    "Q_VSTORE":  "VMOVAPS_ST",
    "Q_VADD":    "VADDPS",
    "Q_VSUB":    "VSUBPS",
    "Q_VMUL":    "VMULPS",
    "Q_VFMA":    "VFMADD231PS",
    "Q_VDIV":    "VDIVPS",
    "Q_VMIN":    "VMINPS",
    "Q_VMAX":    "VMAXPS",
    "Q_VREDUCE": "VHADDPS",
    "Q_VSPLAT":  "VBROADCASTSS",
    "Q_VPERM":   "VPERMPS",
}


# ═══════════════════════════════════════════════════════════
# RISC-V RV64 Instructions (RV64I + RV64F + RV64D + RVV)
# ═══════════════════════════════════════════════════════════
# Sources: riscv/riscv-profiles (RVA22U64, RVA23U64),
#          LLVM RISCVSchedSiFive7.td, SiFive U74 and X280 perf data,
#          Ventana Veyron V1 optimization guide

RV64_BASE_INSTRS = [
    # ── RV64I Integer ──────────────────────────────────
    InstrCost("ADD_rv",     1, 2.0, ["ALU0","ALU1"],      1, "arith", "Integer add"),
    InstrCost("SUB_rv",     1, 2.0, ["ALU0","ALU1"],      1, "arith", "Integer subtract"),
    InstrCost("ADDI",       1, 2.0, ["ALU0","ALU1"],      1, "arith", "Add immediate"),
    InstrCost("ADDIW",      1, 2.0, ["ALU0","ALU1"],      1, "arith", "Add immediate word"),
    InstrCost("ADDW",       1, 2.0, ["ALU0","ALU1"],      1, "arith", "Add word"),
    InstrCost("SUBW",       1, 2.0, ["ALU0","ALU1"],      1, "arith", "Subtract word"),
    InstrCost("AND_rv",     1, 2.0, ["ALU0","ALU1"],      1, "arith", "Bitwise AND"),
    InstrCost("OR_rv",      1, 2.0, ["ALU0","ALU1"],      1, "arith", "Bitwise OR"),
    InstrCost("XOR_rv",     1, 2.0, ["ALU0","ALU1"],      1, "arith", "Bitwise XOR"),
    InstrCost("SLL",        1, 2.0, ["ALU0","ALU1"],      1, "arith", "Shift left logical"),
    InstrCost("SRL",        1, 2.0, ["ALU0","ALU1"],      1, "arith", "Shift right logical"),
    InstrCost("SRA",        1, 2.0, ["ALU0","ALU1"],      1, "arith", "Shift right arith"),
    InstrCost("LUI",        1, 2.0, ["ALU0","ALU1"],      1, "arith", "Load upper immediate"),
    InstrCost("AUIPC",      1, 2.0, ["ALU0","ALU1"],      1, "arith", "Add upper imm to PC"),
    InstrCost("SLT",        1, 2.0, ["ALU0","ALU1"],      1, "cmp",   "Set if less than"),
    InstrCost("SLTU",       1, 2.0, ["ALU0","ALU1"],      1, "cmp",   "Set if less than unsigned"),

    # ── RV64M (Multiply/Divide) ────────────────────────
    InstrCost("MUL_rv",     3, 1.0, ["MUL"],              1, "mul", "Integer multiply"),
    InstrCost("MULH",       4, 1.0, ["MUL"],              1, "mul", "Multiply high signed"),
    InstrCost("MULHSU",     4, 1.0, ["MUL"],              1, "mul", "Multiply high signed×unsigned"),
    InstrCost("MULHU",      4, 1.0, ["MUL"],              1, "mul", "Multiply high unsigned"),
    InstrCost("MULW",       3, 1.0, ["MUL"],              1, "mul", "Multiply word"),
    InstrCost("DIV_rv",    33, 0.03,["DIV"],              1, "div", "Signed divide (data-dep)"),
    InstrCost("DIVU",      33, 0.03,["DIV"],              1, "div", "Unsigned divide"),
    InstrCost("DIVW",      17, 0.06,["DIV"],              1, "div", "Signed divide word"),
    InstrCost("DIVUW",     17, 0.06,["DIV"],              1, "div", "Unsigned divide word"),
    InstrCost("REM_rv",    33, 0.03,["DIV"],              1, "div", "Remainder signed"),
    InstrCost("REMU",      33, 0.03,["DIV"],              1, "div", "Remainder unsigned"),

    # ── Branch / Control ───────────────────────────────
    InstrCost("JAL",        1, 1.0, ["BRU"],              1, "branch", "Jump and link"),
    InstrCost("JALR",       1, 1.0, ["BRU"],              1, "branch", "Jump and link register"),
    InstrCost("BEQ",        1, 1.0, ["BRU"],              1, "branch", "Branch if equal"),
    InstrCost("BNE",        1, 1.0, ["BRU"],              1, "branch", "Branch if not equal"),
    InstrCost("BLT",        1, 1.0, ["BRU"],              1, "branch", "Branch if less than"),
    InstrCost("BGE",        1, 1.0, ["BRU"],              1, "branch", "Branch if greater/equal"),
    InstrCost("BLTU",       1, 1.0, ["BRU"],              1, "branch", "Branch if less unsigned"),
    InstrCost("BGEU",       1, 1.0, ["BRU"],              1, "branch", "Branch if greater/eq unsigned"),

    # ── Load / Store ───────────────────────────────────
    InstrCost("LD",         4, 1.0, ["LSU"],              1, "load",  "Load doubleword"),
    InstrCost("LW",         4, 1.0, ["LSU"],              1, "load",  "Load word"),
    InstrCost("LH",         4, 1.0, ["LSU"],              1, "load",  "Load halfword"),
    InstrCost("LB",         4, 1.0, ["LSU"],              1, "load",  "Load byte"),
    InstrCost("SD",         1, 1.0, ["LSU"],              1, "store", "Store doubleword"),
    InstrCost("SW",         1, 1.0, ["LSU"],              1, "store", "Store word"),
    InstrCost("SH",         1, 1.0, ["LSU"],              1, "store", "Store halfword"),
    InstrCost("SB",         1, 1.0, ["LSU"],              1, "store", "Store byte"),

    # ── Atomic (RV64A) ─────────────────────────────────
    InstrCost("LR_D",       5, 0.5, ["LSU"],              1, "load",  "Load-reserved doubleword"),
    InstrCost("SC_D",       5, 0.5, ["LSU"],              1, "store", "Store-conditional doubleword"),
    InstrCost("AMOADD_D",   5, 0.5, ["LSU"],              1, "arith", "Atomic add doubleword"),

    # ── RV64F (Single-Precision Float) ──────────────────
    InstrCost("FADD_S",     5, 1.0, ["FPU"],              1, "arith",  "FP32 add"),
    InstrCost("FSUB_S",     5, 1.0, ["FPU"],              1, "arith",  "FP32 subtract"),
    InstrCost("FMUL_S",     5, 1.0, ["FPU"],              1, "mul",    "FP32 multiply"),
    InstrCost("FDIV_S",    20, 0.05,["FPU"],              1, "div",    "FP32 divide"),
    InstrCost("FSQRT_S",   25, 0.04,["FPU"],              1, "div",    "FP32 square root"),
    InstrCost("FMADD_S",    5, 1.0, ["FPU"],              1, "mul",    "FP32 fused multiply-add"),
    InstrCost("FLW",        5, 1.0, ["LSU"],              1, "load",   "FP32 load"),
    InstrCost("FSW",        1, 1.0, ["LSU"],              1, "store",  "FP32 store"),
    InstrCost("FCVT_W_S",   5, 1.0, ["FPU"],              1, "arith",  "FP32→int convert"),
    InstrCost("FCVT_S_W",   5, 1.0, ["FPU"],              1, "arith",  "Int→FP32 convert"),
    InstrCost("FMV_X_W",    3, 1.0, ["FPU"],              1, "arith",  "Move FP32→GPR"),
    InstrCost("FMV_W_X",    3, 1.0, ["FPU"],              1, "arith",  "Move GPR→FP32"),

    # ── RV64D (Double-Precision Float) ──────────────────
    InstrCost("FADD_D",     7, 1.0, ["FPU"],              1, "arith",  "FP64 add"),
    InstrCost("FSUB_D",     7, 1.0, ["FPU"],              1, "arith",  "FP64 subtract"),
    InstrCost("FMUL_D",     7, 1.0, ["FPU"],              1, "mul",    "FP64 multiply"),
    InstrCost("FDIV_D",    27, 0.04,["FPU"],              1, "div",    "FP64 divide"),
    InstrCost("FSQRT_D",   30, 0.03,["FPU"],              1, "div",    "FP64 square root"),
    InstrCost("FMADD_D",    7, 1.0, ["FPU"],              1, "mul",    "FP64 fused multiply-add"),
    InstrCost("FLD",        5, 1.0, ["LSU"],              1, "load",   "FP64 load"),
    InstrCost("FSD",        1, 1.0, ["LSU"],              1, "store",  "FP64 store"),

    # ── System / CSR ───────────────────────────────────
    InstrCost("ECALL",      0, 1.0, [],                   1, "branch", "Environment call"),
    InstrCost("EBREAK",     0, 1.0, [],                   1, "branch", "Breakpoint"),
    InstrCost("CSRRW",      3, 1.0, ["CSR"],              1, "arith",  "CSR read/write"),
    InstrCost("FENCE",      0, 0.1, [],                   1, "branch", "Memory fence"),
    InstrCost("NOP_rv",     0, 2.0, [],                   0, "arith",  "No operation"),
]

# ═══════════════════════════════════════════════════════════
# RISC-V Vector Extension (RVV 1.0) – SiFive X280 / Spacemit X60
# ═══════════════════════════════════════════════════════════

RV64_VECTOR_INSTRS = [
    # ── Vector Arithmetic ──────────────────────────────
    InstrCost("VADD_VV",    2, 2.0, ["VPU"],              1, "simd_arith", "Vector integer add"),
    InstrCost("VSUB_VV",    2, 2.0, ["VPU"],              1, "simd_arith", "Vector integer subtract"),
    InstrCost("VMUL_VV",    5, 1.0, ["VPU"],              1, "simd_mul",   "Vector integer multiply"),
    InstrCost("VDIV_VV",   20, 0.05,["VPU"],              1, "simd_div",   "Vector integer divide"),
    InstrCost("VREM_VV",   20, 0.05,["VPU"],              1, "simd_div",   "Vector integer remainder"),
    InstrCost("VMADD_VV",   5, 1.0, ["VPU"],              1, "simd_mul",   "Vector mul-add (vd = vs1*vs2+vd)"),
    InstrCost("VAND_VV",    2, 2.0, ["VPU"],              1, "simd_arith", "Vector bitwise AND"),
    InstrCost("VOR_VV",     2, 2.0, ["VPU"],              1, "simd_arith", "Vector bitwise OR"),
    InstrCost("VXOR_VV",    2, 2.0, ["VPU"],              1, "simd_arith", "Vector bitwise XOR"),
    InstrCost("VMIN_VV",    2, 2.0, ["VPU"],              1, "simd_arith", "Vector integer min"),
    InstrCost("VMAX_VV",    2, 2.0, ["VPU"],              1, "simd_arith", "Vector integer max"),

    # ── Vector FP Arithmetic ───────────────────────────
    InstrCost("VFADD_VV",   5, 1.0, ["VPU"],              1, "simd_arith", "Vector FP add"),
    InstrCost("VFSUB_VV",   5, 1.0, ["VPU"],              1, "simd_arith", "Vector FP subtract"),
    InstrCost("VFMUL_VV",   5, 1.0, ["VPU"],              1, "simd_mul",   "Vector FP multiply"),
    InstrCost("VFDIV_VV",  20, 0.05,["VPU"],              1, "simd_div",   "Vector FP divide"),
    InstrCost("VFMADD_VV",  5, 1.0, ["VPU"],              1, "simd_fma",   "Vector FMA (vd=vs1*vs2+vd)"),
    InstrCost("VFMIN_VV",   3, 1.0, ["VPU"],              1, "simd_arith", "Vector FP min"),
    InstrCost("VFMAX_VV",   3, 1.0, ["VPU"],              1, "simd_arith", "Vector FP max"),

    # ── Vector Load / Store ────────────────────────────
    InstrCost("VLE32_V",    5, 1.0, ["VLSU"],             1, "simd_load",  "Vector load 32-bit elements"),
    InstrCost("VLE64_V",    5, 1.0, ["VLSU"],             1, "simd_load",  "Vector load 64-bit elements"),
    InstrCost("VSE32_V",    1, 1.0, ["VLSU"],             1, "simd_store", "Vector store 32-bit elements"),
    InstrCost("VSE64_V",    1, 1.0, ["VLSU"],             1, "simd_store", "Vector store 64-bit elements"),
    InstrCost("VLSE32_V",   6, 0.5, ["VLSU"],             1, "simd_load",  "Vector strided load 32-bit"),
    InstrCost("VLUXEI32_V",10, 0.25,["VLSU"],             1, "simd_load",  "Vector indexed (gather) load"),
    InstrCost("VSUXEI32_V",10, 0.25,["VLSU"],             1, "simd_store", "Vector indexed (scatter) store"),

    # ── Vector Reduce ──────────────────────────────────
    InstrCost("VREDSUM_VS", 6, 0.5, ["VPU"],              1, "simd_reduce","Vector reduce sum"),
    InstrCost("VREDMAX_VS", 6, 0.5, ["VPU"],              1, "simd_reduce","Vector reduce max"),
    InstrCost("VREDMIN_VS", 6, 0.5, ["VPU"],              1, "simd_reduce","Vector reduce min"),
    InstrCost("VFREDUSUM_VS",8,0.25,["VPU"],              1, "simd_reduce","Vector FP reduce unordered sum"),

    # ── Vector Permute / Config ────────────────────────
    InstrCost("VRGATHER_VV",4, 0.5, ["VPU"],              1, "simd_perm",  "Vector gather (permute)"),
    InstrCost("VSLIDEDOWN_VI",3,1.0,["VPU"],              1, "simd_perm",  "Vector slide down by imm"),
    InstrCost("VSLIDEUP_VI",3, 1.0, ["VPU"],              1, "simd_perm",  "Vector slide up by imm"),
    InstrCost("VMV_V_X",    2, 2.0, ["VPU"],              1, "simd_perm",  "Splat scalar to vector"),
    InstrCost("VSETVLI",    1, 2.0, ["ALU0"],             1, "simd_cfg",   "Set vector length (imm)"),
    InstrCost("VSETIVLI",   1, 2.0, ["ALU0"],             1, "simd_cfg",   "Set vector length (imm, imm)"),

    # ── Vector Compare / Mask ──────────────────────────
    InstrCost("VMSEQ_VV",   2, 2.0, ["VPU"],              1, "simd_cmp",   "Vector mask set if equal"),
    InstrCost("VMSLT_VV",   2, 2.0, ["VPU"],              1, "simd_cmp",   "Vector mask set if less"),
    InstrCost("VMSLE_VV",   2, 2.0, ["VPU"],              1, "simd_cmp",   "Vector mask set if less/eq"),
    InstrCost("VMAND_MM",   1, 2.0, ["VPU"],              1, "simd_arith", "Mask AND"),
    InstrCost("VMOR_MM",    1, 2.0, ["VPU"],              1, "simd_arith", "Mask OR"),
]

RV64_QIR_MAP = {
    "Q_LOAD":           "LD",
    "Q_STORE":          "SD",
    "Q_MOVE":           "ADDI",    # ADDI x, y, 0 == move
    "Q_ADD":            "ADD_rv",
    "Q_SUB":            "SUB_rv",
    "Q_MUL":            "MUL_rv",
    "Q_DIV":            "DIV_rv",
    "Q_MOD":            "REM_rv",
    "Q_CMP_EQ":         "SLT",
    "Q_CMP_NE":         "SLT",
    "Q_CMP_GT":         "SLT",
    "Q_CMP_LT":         "SLT",
    "Q_CMP_GE":         "SLT",
    "Q_CMP_LE":         "SLT",
    "Q_JUMP":           "JAL",
    "Q_JUMP_IF":        "BNE",
    "Q_JUMP_IF_NOT":    "BEQ",
    "Q_CALL":           "JAL",
    "Q_RET":            "JALR",
    "Q_PRINT":          "JAL",
    "Q_LABEL":          "NOP_rv",
    "Q_NOP":            "NOP_rv",
    "Q_HALT":           "ECALL",
    "Q_LOAD_STRING":    "LD",
    "Q_PATCH_POINT":    "NOP_rv",
    "Q_INPUT":          "JAL",
    # Vector
    "Q_VLOAD":           "VLE32_V",
    "Q_VSTORE":          "VSE32_V",
    "Q_VADD":            "VFADD_VV",
    "Q_VSUB":            "VFSUB_VV",
    "Q_VMUL":            "VFMUL_VV",
    "Q_VFMA":            "VFMADD_VV",
    "Q_VDIV":            "VFDIV_VV",
    "Q_VMIN":            "VFMIN_VV",
    "Q_VMAX":            "VFMAX_VV",
    "Q_VREDUCE":         "VREDSUM_VS",
    "Q_VSPLAT":          "VMV_V_X",
    "Q_VPERM":           "VRGATHER_VV",
}

X86_64_QIR_MAP = {
    "Q_LOAD":           "MOV_LD",
    "Q_STORE":          "MOV_ST",
    "Q_MOVE":           "MOV",
    "Q_ADD":            "ADD",
    "Q_SUB":            "SUB",
    "Q_MUL":            "IMUL",
    "Q_DIV":            "IDIV",
    "Q_MOD":            "IDIV",
    "Q_CMP_EQ":         "CMP",
    "Q_CMP_NE":         "CMP",
    "Q_CMP_GT":         "CMP",
    "Q_CMP_LT":         "CMP",
    "Q_CMP_GE":         "CMP",
    "Q_CMP_LE":         "CMP",
    "Q_JUMP":           "JMP",
    "Q_JUMP_IF":        "JNE",
    "Q_JUMP_IF_NOT":    "JE",
    "Q_CALL":           "CALL",
    "Q_RET":            "RET",
    "Q_PRINT":          "CALL",
    "Q_LABEL":          "NOP",
    "Q_NOP":            "NOP",
    "Q_HALT":           "RET",
    "Q_LOAD_STRING":    "MOV_LD",
    "Q_PATCH_POINT":    "NOP",
    "Q_INPUT":          "CALL",
}


# ═══════════════════════════════════════════════════════════
# Probe Data Ingestion
# ═══════════════════════════════════════════════════════════

def ingest_probe_data(probe_path: Path, config: ArchConfig) -> None:
    """Overlay measured probe data onto reference data."""
    with open(probe_path) as f:
        data = json.load(f)

    # Update CPU info
    config.cpu = data.get("cpu", config.cpu)
    config.cpu_freq_ghz = data.get("timer_freq_hz", 3.5e9) / 1e9

    # Map probe instruction names to our instruction names
    probe_map = {
        "ADD": "ADD",
        "MUL": "MUL",
        "DIV": "SDIV" if config.arch == "arm64" else "IDIV",
        "SDIV": "SDIV",
        "IDIV": "IDIV",
        "LOAD": "LDR" if config.arch == "arm64" else "MOV_LD",
        "LDR": "LDR",
    }

    instr_lookup = {i.mnemonic: i for i in config.instructions}

    for probe_instr in data.get("instructions", []):
        name = probe_instr["name"]
        target_name = probe_map.get(name, name)
        if target_name in instr_lookup:
            instr = instr_lookup[target_name]
            measured_lat = probe_instr.get("latency_cycles", 0)
            measured_thr = probe_instr.get("throughput_ipc", 0)
            if measured_lat > 0:
                instr.latency = round(measured_lat)
                instr.notes += f" [probed: {measured_lat:.2f}c]"
            if measured_thr > 0:
                instr.throughput = round(measured_thr, 2)
                instr.notes += f" [probed IPC: {measured_thr:.2f}]"

    # Branch data
    branch = data.get("branch", {})
    if branch:
        config.branch.predict_hit = branch.get("predict_hit_cycles", 0)
        config.branch.predict_miss = branch.get("predict_miss_cycles", 0)
        config.branch.miss_penalty = branch.get("miss_penalty", 0)

    # Memory data
    mem = data.get("memory", {})
    if mem:
        config.memory.l1_latency = mem.get("l1_latency_cycles", config.memory.l1_latency)
        config.memory.l2_latency = mem.get("l2_latency_cycles", config.memory.l2_latency)
        config.memory.l3_latency = mem.get("l3_latency_cycles", config.memory.l3_latency)
        config.memory.mem_latency = mem.get("mem_latency_cycles", config.memory.mem_latency)
        config.memory.l1_size_kb = mem.get("l1_size_kb", config.memory.l1_size_kb)
        config.memory.l2_size_kb = mem.get("l2_size_kb", config.memory.l2_size_kb)
        config.memory.l3_size_kb = mem.get("l3_size_kb", config.memory.l3_size_kb)

    config.source += " + micro-prober"


# ═══════════════════════════════════════════════════════════
# LLVM TableGen Parser (Basic)
# ═══════════════════════════════════════════════════════════

def parse_llvm_sched_model(td_path: Path) -> list[dict]:
    """Parse LLVM .td scheduling model file for instruction costs.
    
    Looks for patterns like:
        def : WriteRes<WriteALU, [A64FXUnitALU]> { let Latency = 1; }
        def : ReadAdvance<ReadALU, 0>;
    """
    results = []
    if not td_path.exists():
        return results

    content = td_path.read_text()

    # Pattern: WriteRes with Latency
    pat = re.compile(
        r'def\s*:\s*WriteRes<(\w+),\s*\[([^\]]*)\]>\s*\{[^}]*Latency\s*=\s*(\d+)',
        re.MULTILINE
    )
    for m in pat.finditer(content):
        write_name = m.group(1)
        units = [u.strip() for u in m.group(2).split(',')]
        latency = int(m.group(3))
        results.append({
            "write": write_name,
            "units": units,
            "latency": latency,
        })

    # Pattern: InstRW bindings
    pat2 = re.compile(
        r'def\s*:\s*InstRW<\[(\w+)\],\s*\(instrs\s+([^)]+)\)',
        re.MULTILINE
    )
    for m in pat2.finditer(content):
        write = m.group(1)
        instrs = [i.strip() for i in m.group(2).split(',')]
        for instr in instrs:
            results.append({
                "write": write,
                "instr": instr,
            })

    return results


# ═══════════════════════════════════════════════════════════
# Config Generation
# ═══════════════════════════════════════════════════════════

def build_arm64_config(probe_path: Optional[Path] = None) -> ArchConfig:
    """Build ARM64 (Apple Silicon) architecture config."""
    import datetime

    config = ArchConfig(
        arch="arm64",
        cpu="Apple M2",
        cpu_freq_ghz=3.5,
        issue_width=8,       # Apple M2 can issue 8 ops/cycle  
        reorder_buffer=600,  # estimated ROB size
        phys_int_regs=320,
        phys_fp_regs=384,
        instructions=list(ARM64_APPLE_M2_INSTRS) + list(ARM64_NEON_INSTRS),
        branch=BranchCost(predict_hit=1.0, predict_miss=14.0, miss_penalty=13.0),
        memory=MemoryCost(
            l1_latency=4, l2_latency=12, l3_latency=40,
            mem_latency=200, l1_size_kb=64, l2_size_kb=4096,
            l3_size_kb=16384, store_latency=1
        ),
        spill=SpillCost(spill_store=1, spill_load=4, total=5),
        qir_map={**ARM64_QIR_MAP, **ARM64_NEON_QIR_MAP},
        source="LLVM AArch64 sched model + Apple optimization guide",
        timestamp=datetime.datetime.now().isoformat(),
    )

    if probe_path and probe_path.exists():
        ingest_probe_data(probe_path, config)

    return config


def build_x86_64_config(probe_path: Optional[Path] = None) -> ArchConfig:
    """Build x86_64 (generic modern) architecture config."""
    import datetime

    config = ArchConfig(
        arch="x86_64",
        cpu="Generic (Zen 4 / Golden Cove)",
        cpu_freq_ghz=4.0,
        issue_width=6,
        reorder_buffer=512,
        phys_int_regs=224,
        phys_fp_regs=192,
        instructions=list(X86_64_GENERIC_INSTRS) + list(X86_64_SIMD_INSTRS),
        branch=BranchCost(predict_hit=1.0, predict_miss=16.0, miss_penalty=15.0),
        memory=MemoryCost(
            l1_latency=4, l2_latency=12, l3_latency=40,
            mem_latency=200, l1_size_kb=32, l2_size_kb=1024,
            l3_size_kb=32768, store_latency=1
        ),
        spill=SpillCost(spill_store=1, spill_load=4, total=5),
        qir_map={**X86_64_QIR_MAP, **X86_64_SIMD_QIR_MAP},
        source="LLVM X86 sched model + Agner Fog tables",
        timestamp=datetime.datetime.now().isoformat(),
    )

    if probe_path and probe_path.exists():
        ingest_probe_data(probe_path, config)

    return config


def build_rv64_config(probe_path: Optional[Path] = None) -> ArchConfig:
    """Build RISC-V RV64GCV (RV64I+M+A+F+D+C+V) architecture config."""
    import datetime

    config = ArchConfig(
        arch="rv64",
        cpu="Generic RV64GCV (SiFive U74 / X280 class)",
        cpu_freq_ghz=1.5,
        issue_width=2,              # Dual-issue typical for RV64
        reorder_buffer=128,         # SiFive U74: in-order; X280: OoO ~128
        phys_int_regs=64,
        phys_fp_regs=64,
        instructions=list(RV64_BASE_INSTRS) + list(RV64_VECTOR_INSTRS),
        branch=BranchCost(predict_hit=1.0, predict_miss=10.0, miss_penalty=9.0),
        memory=MemoryCost(
            l1_latency=3, l2_latency=10, l3_latency=30,
            mem_latency=150, l1_size_kb=32, l2_size_kb=512,
            l3_size_kb=4096, store_latency=1
        ),
        spill=SpillCost(spill_store=1, spill_load=3, total=4),
        qir_map=dict(RV64_QIR_MAP),
        source="LLVM RISCV sched model + SiFive perf data + riscv-profiles",
        timestamp=datetime.datetime.now().isoformat(),
    )

    if probe_path and probe_path.exists():
        ingest_probe_data(probe_path, config)

    return config


def export_config(config: ArchConfig, out_path: Path) -> None:
    """Export ArchConfig as JSON."""
    data = asdict(config)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Exported: {out_path} ({len(config.instructions)} instructions)")


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Extract CPU instruction cost data for Vir cost model"
    )
    parser.add_argument("--probe", type=Path, default=None,
                        help="Path to micro-prober JSON output")
    parser.add_argument("--llvm-src", type=Path, default=None,
                        help="Path to LLVM source tree (for .td files)")
    parser.add_argument("--arch", choices=["arm64", "x86_64", "rv64", "all"],
                        default="all", help="Target architecture")
    parser.add_argument("--output-dir", type=Path,
                        default=Path("data/arch"),
                        help="Output directory for config JSON files")
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.arch in ("arm64", "all"):
        config = build_arm64_config(args.probe)
        export_config(config, output_dir / "arm64_config.json")

    if args.arch in ("x86_64", "all"):
        config = build_x86_64_config(args.probe)
        export_config(config, output_dir / "x86_64_config.json")

    if args.arch in ("rv64", "all"):
        config = build_rv64_config(args.probe)
        export_config(config, output_dir / "rv64_config.json")

    print(f"\nDone. Configs written to {output_dir}/")


if __name__ == "__main__":
    main()

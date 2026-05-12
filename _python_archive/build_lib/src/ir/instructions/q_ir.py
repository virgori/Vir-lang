"""
q_ir.py – Tập lệnh Q-IR (Quizz Intermediate Representation)
==============================================================
Spec §2.1 – Instruction set kiểu SSA tối giản.

Mỗi instruction là immutable, sử dụng thanh ghi ảo (Virtual Registers) không giới hạn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class Opcode(Enum):
    """Các mã lệnh Q-IR."""

    # ── Data movement ──────────────────────────────────────
    Q_LOAD = auto()          # Q_LOAD  <dest>, <src|imm>
    Q_STORE = auto()         # Q_STORE <addr>, <src>
    Q_MOVE = auto()          # Q_MOVE  <dest>, <src>

    # ── Arithmetic ─────────────────────────────────────────
    Q_ADD = auto()           # Q_OP ADD, <dest>, <src1>, <src2>
    Q_SUB = auto()
    Q_MUL = auto()
    Q_DIV = auto()
    Q_MOD = auto()

    # ── Comparison ─────────────────────────────────────────
    Q_CMP_EQ = auto()
    Q_CMP_NE = auto()
    Q_CMP_GT = auto()
    Q_CMP_LT = auto()
    Q_CMP_GE = auto()
    Q_CMP_LE = auto()

    # ── Control flow ───────────────────────────────────────
    Q_JUMP = auto()          # Unconditional jump
    Q_JUMP_IF = auto()       # Conditional: jump if <cond> != 0
    Q_JUMP_IF_NOT = auto()   # Conditional: jump if <cond> == 0
    Q_CALL = auto()          # Function call
    Q_RET = auto()           # Return

    # ── I/O ────────────────────────────────────────────────
    Q_PRINT = auto()
    Q_INPUT = auto()

    # ── Self-patching (spec §2.1) ──────────────────────────
    Q_PATCH_POINT = auto()   # Lỗ hổng cho tầng Backend tự vá mã

    # ── Label (pseudo) ─────────────────────────────────────
    Q_LABEL = auto()

    # ── String ─────────────────────────────────────────────
    Q_LOAD_STRING = auto()   # Q_LOAD_STRING <dest>, <string_idx>

    # ── No-op ──────────────────────────────────────────────
    Q_NOP = auto()
    Q_HALT = auto()

    # ── SIMD / Vector ──────────────────────────────────────
    Q_VLOAD = auto()         # Q_VLOAD  <vdest>, <addr>     ; load 128/256/512-bit vector
    Q_VSTORE = auto()        # Q_VSTORE <addr>, <vsrc>      ; store vector
    Q_VADD = auto()          # Q_VADD   <vd>, <vs1>, <vs2>  ; element-wise add
    Q_VSUB = auto()          # Q_VSUB   <vd>, <vs1>, <vs2>  ; element-wise sub
    Q_VMUL = auto()          # Q_VMUL   <vd>, <vs1>, <vs2>  ; element-wise mul
    Q_VFMA = auto()          # Q_VFMA   <vd>, <vs1>, <vs2>  ; fused multiply-add (vd += vs1*vs2)
    Q_VDIV = auto()          # Q_VDIV   <vd>, <vs1>, <vs2>  ; element-wise div
    Q_VMIN = auto()          # Q_VMIN   <vd>, <vs1>, <vs2>  ; element-wise min
    Q_VMAX = auto()          # Q_VMAX   <vd>, <vs1>, <vs2>  ; element-wise max
    Q_VREDUCE = auto()       # Q_VREDUCE <dest>, <vsrc>     ; horizontal reduce (sum)
    Q_VSPLAT = auto()        # Q_VSPLAT <vd>, <scalar>      ; broadcast scalar to all lanes
    Q_VPERM = auto()         # Q_VPERM  <vd>, <vs1>, <mask> ; permute / shuffle

    # ── Memory Safety ──────────────────────────────────────
    Q_BOUNDS_CHECK = auto()  # Q_BOUNDS_CHECK <idx>, <len>    ; trap if idx >= len
    Q_ALLOC = auto()         # Q_ALLOC  <dest>, <size>        ; heap allocation
    Q_FREE = auto()          # Q_FREE   <ptr>                 ; deterministic free
    Q_STACK_ALLOC = auto()   # Q_STACK_ALLOC <dest>, <size>   ; stack-promoted allocation

    # ── Floating-Point Scalar ──────────────────────────────
    Q_FLOAD = auto()         # Q_FLOAD  <fdest>, <imm|addr>  ; load float into FP reg
    Q_FSTORE = auto()        # Q_FSTORE <addr>, <fsrc>       ; store FP reg to memory
    Q_FMOVE = auto()         # Q_FMOVE  <fdest>, <fsrc>      ; FP register move
    Q_FADD = auto()          # Q_FADD   <fd>, <fs1>, <fs2>   ; floating-point add
    Q_FSUB = auto()          # Q_FSUB   <fd>, <fs1>, <fs2>   ; floating-point sub
    Q_FMUL = auto()          # Q_FMUL   <fd>, <fs1>, <fs2>   ; floating-point mul
    Q_FDIV = auto()          # Q_FDIV   <fd>, <fs1>, <fs2>   ; floating-point div
    Q_FCMP_EQ = auto()       # Q_FCMP_EQ <dest>, <fs1>, <fs2> ; FP compare ==
    Q_FCMP_LT = auto()       # Q_FCMP_LT <dest>, <fs1>, <fs2> ; FP compare <
    Q_FCMP_GT = auto()       # Q_FCMP_GT <dest>, <fs1>, <fs2> ; FP compare >
    Q_FCVT_I2F = auto()      # Q_FCVT_I2F <fd>, <src>         ; int → float
    Q_FCVT_F2I = auto()      # Q_FCVT_F2I <dest>, <fsrc>      ; float → int (truncate)


@dataclass(frozen=True)
class VReg:
    """Thanh ghi ảo – §2.2 Virtual Registers (R0, R1, …, Rn)."""
    index: int

    def __repr__(self) -> str:
        return f"R{self.index}"


@dataclass(frozen=True)
class Immediate:
    """Giá trị trực tiếp (literal / constant)."""
    value: float

    def __repr__(self) -> str:
        return f"#{self.value}"


@dataclass(frozen=True)
class Label:
    """Nhãn – mục tiêu nhảy."""
    name: str

    def __repr__(self) -> str:
        return f"@{self.name}"


# Kiểu Operand hợp nhất
Operand = VReg | Immediate | Label | None


@dataclass(frozen=True)
class QInstruction:
    """
    Một instruction Q-IR.

    Dạng tổng quát:
        opcode  dest, src1, src2
    Trong đó src1, src2, dest là VReg | Immediate | Label | None.
    """

    opcode: Opcode
    dest: Operand = None
    src1: Operand = None
    src2: Operand = None
    comment: str = ""       # annotation tùy chọn
    patch_id: str = ""      # Chỉ dùng cho Q_PATCH_POINT
    string_value: str = ""  # For Q_LOAD_STRING

    def __repr__(self) -> str:
        parts = [self.opcode.name]
        for op in (self.dest, self.src1, self.src2):
            if op is not None:
                parts.append(str(op))
        if self.comment:
            parts.append(f"; {self.comment}")
        return " ".join(parts)


@dataclass
class QFunction:
    """Hàm Q-IR – một chuỗi instructions."""
    name: str
    params: list[VReg] = field(default_factory=list)
    body: list[QInstruction] = field(default_factory=list)

    def append(self, instr: QInstruction) -> None:
        self.body.append(instr)

    def __repr__(self) -> str:
        header = f"func @{self.name}({', '.join(str(p) for p in self.params)}):"
        lines = [header]
        for instr in self.body:
            lines.append(f"  {instr}")
        return "\n".join(lines)


@dataclass
class QModule:
    """Module Q-IR – chứa nhiều hàm."""
    name: str = "main"
    functions: list[QFunction] = field(default_factory=list)
    strings: list[str] = field(default_factory=list)

    def add_function(self, func: QFunction) -> None:
        self.functions.append(func)

    def add_string(self, s: str) -> int:
        """Add a string literal, return its index."""
        if s in self.strings:
            return self.strings.index(s)
        self.strings.append(s)
        return len(self.strings) - 1

    def dump(self) -> str:
        """In toàn bộ module dưới dạng textual IR."""
        sections = [f"; module {self.name}"]
        for func in self.functions:
            sections.append("")
            sections.append(str(func))
        return "\n".join(sections)

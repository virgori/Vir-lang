"""
codegen_wasm.py – Q-IR → WebAssembly Binary (.wasm)
====================================================
Phase V – WASM target for Vir compiler.

Emits WebAssembly binary format (MVP) with:
- Module header (magic + version)
- Type section (function signatures)
- Function section (type indices)
- Export section (exported functions)
- Code section (function bodies with WASM bytecode)

WASM spec: https://webassembly.github.io/spec/core/

Uses the stack-machine model:
  Q-IR register ops → WASM local.get/local.set + stack ops
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from src.ir.instructions.q_ir import (
    Immediate,
    Label,
    Opcode,
    QFunction,
    QInstruction,
    QModule,
    VReg,
)


# ═══════════════════════════════════════════════════════════
# WASM Binary Constants
# ═══════════════════════════════════════════════════════════

WASM_MAGIC = b"\x00asm"
WASM_VERSION = b"\x01\x00\x00\x00"

# Section IDs
SEC_TYPE     = 0x01
SEC_IMPORT   = 0x02
SEC_FUNCTION = 0x03
SEC_MEMORY   = 0x05
SEC_EXPORT   = 0x06
SEC_CODE     = 0x0A

# Value types
I32 = 0x7F
I64 = 0x7E
F32 = 0x7D
F64 = 0x7C

# Export kinds
EXPORT_FUNC   = 0x00
EXPORT_TABLE  = 0x01
EXPORT_MEMORY = 0x02
EXPORT_GLOBAL = 0x03

# Opcodes
OP_UNREACHABLE   = 0x00
OP_NOP           = 0x01
OP_BLOCK         = 0x02
OP_LOOP          = 0x03
OP_IF            = 0x04
OP_ELSE          = 0x05
OP_END           = 0x0B
OP_BR            = 0x0C
OP_BR_IF         = 0x0D
OP_RETURN        = 0x0F
OP_CALL          = 0x10
OP_DROP          = 0x1A
OP_LOCAL_GET     = 0x20
OP_LOCAL_SET     = 0x21
OP_LOCAL_TEE     = 0x22
OP_I32_LOAD      = 0x28
OP_I64_LOAD      = 0x29
OP_I32_STORE     = 0x36
OP_I64_STORE     = 0x37
OP_I64_CONST     = 0x42
OP_I64_ADD       = 0x7C
OP_I64_SUB       = 0x7D
OP_I64_MUL       = 0x7E
OP_I64_DIV_S     = 0x7F
OP_I64_REM_S     = 0x81
OP_I64_EQ        = 0x51
OP_I64_NE        = 0x52
OP_I64_LT_S      = 0x53
OP_I64_GT_S      = 0x55
OP_I64_LE_S      = 0x57
OP_I64_GE_S      = 0x59
OP_I64_EQZ       = 0x50
OP_I32_CONST     = 0x41
OP_I64_EXTEND_I32_S = 0xAC
OP_F64_CONST     = 0x44
OP_F64_ADD       = 0xA0
OP_F64_SUB       = 0xA1
OP_F64_MUL       = 0xA2
OP_F64_DIV       = 0xA3
OP_F64_EQ        = 0x61
OP_F64_LT        = 0x63
OP_F64_GT        = 0x64
OP_I64_TRUNC_F64_S = 0xB0
OP_F64_CONVERT_I64_S = 0xB9


# ═══════════════════════════════════════════════════════════
# LEB128 Encoding
# ═══════════════════════════════════════════════════════════

def _uleb128(value: int) -> bytes:
    """Encode unsigned integer as ULEB128."""
    result = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            byte |= 0x80
        result.append(byte)
        if not value:
            break
    return bytes(result)


def _sleb128(value: int) -> bytes:
    """Encode signed integer as SLEB128."""
    result = bytearray()
    more = True
    while more:
        byte = value & 0x7F
        value >>= 7
        if (value == 0 and (byte & 0x40) == 0) or (value == -1 and (byte & 0x40)):
            more = False
        else:
            byte |= 0x80
        result.append(byte)
    return bytes(result)


def _encode_string(s: str) -> bytes:
    """Encode string as length-prefixed UTF-8."""
    encoded = s.encode("utf-8")
    return _uleb128(len(encoded)) + encoded


def _section(section_id: int, content: bytes) -> bytes:
    """Encode a WASM section: id + size + content."""
    return bytes([section_id]) + _uleb128(len(content)) + content


# ═══════════════════════════════════════════════════════════
# WASM Function Builder
# ═══════════════════════════════════════════════════════════

@dataclass
class WasmFunc:
    """A single WASM function being built."""
    name: str
    param_count: int = 0
    local_count: int = 0       # Extra locals beyond params
    has_result: bool = True     # Returns i64
    body: bytearray = field(default_factory=bytearray)
    label_stack: list[int] = field(default_factory=list)

    def emit(self, *opcodes: int) -> None:
        for op in opcodes:
            self.body.append(op)

    def emit_bytes(self, data: bytes) -> None:
        self.body.extend(data)

    def emit_i64_const(self, value: int) -> None:
        self.body.append(OP_I64_CONST)
        self.body.extend(_sleb128(value))

    def emit_local_get(self, idx: int) -> None:
        self.body.append(OP_LOCAL_GET)
        self.body.extend(_uleb128(idx))

    def emit_local_set(self, idx: int) -> None:
        self.body.append(OP_LOCAL_SET)
        self.body.extend(_uleb128(idx))

    def emit_call(self, func_idx: int) -> None:
        self.body.append(OP_CALL)
        self.body.extend(_uleb128(func_idx))

    def encode_body(self) -> bytes:
        """Encode function body: locals declaration + body + end."""
        body = bytearray()

        # Locals declaration
        if self.local_count > 0:
            body.extend(_uleb128(1))        # 1 local declaration entry
            body.extend(_uleb128(self.local_count))  # count
            body.append(I64)                 # type: i64
        else:
            body.extend(_uleb128(0))        # 0 local entries

        body.extend(self.body)
        body.append(OP_END)

        # Wrap with size prefix
        return _uleb128(len(body)) + bytes(body)


# ═══════════════════════════════════════════════════════════
# WASM Code Generator
# ═══════════════════════════════════════════════════════════

class WasmCodegen:
    """
    Compile Q-IR Module → WASM binary (.wasm).

    Strategy: Map VRegs to WASM locals.
    Q-IR operations → push operands from locals, operate on stack, pop to dest local.
    """

    def __init__(self) -> None:
        self.functions: list[WasmFunc] = []
        self.func_names: dict[str, int] = {}  # name → index (offset by imports)
        self.import_count: int = 0
        self.strings: list[str] = []

    def compile_module(self, module: QModule) -> bytes:
        """Compile entire Q-IR module to WASM binary."""
        self.strings = list(module.strings)

        # Build import section for print/input (host functions)
        # Import: env.print(i64) → void,  env.input() → i64
        imports = [
            ("env", "print", [I64], []),       # func 0
            ("env", "input", [], [I64]),        # func 1
        ]
        self.import_count = len(imports)

        # Compile each Q-IR function
        for qfunc in module.functions:
            idx = self.import_count + len(self.functions)
            self.func_names[qfunc.name] = idx
            wfunc = self._compile_function(qfunc)
            self.functions.append(wfunc)

        return self._emit_binary(imports)

    def _compile_function(self, qfunc: QFunction) -> WasmFunc:
        """Compile one Q-IR function to WASM."""
        wfunc = WasmFunc(
            name=qfunc.name,
            param_count=len(qfunc.params),
        )

        # Count max VReg index used → allocate locals
        max_reg = len(qfunc.params) - 1
        for instr in qfunc.body:
            for op in (instr.dest, instr.src1, instr.src2):
                if isinstance(op, VReg):
                    max_reg = max(max_reg, op.index)

        wfunc.local_count = max(0, max_reg + 1 - len(qfunc.params))

        # Label tracking for branches
        labels: dict[int, int] = {}     # label_id → block depth
        block_depth = 0

        # Compile each instruction
        for instr in qfunc.body:
            self._compile_instruction(instr, wfunc, labels, block_depth)

        return wfunc

    def _compile_instruction(
        self, instr: QInstruction, wfunc: WasmFunc,
        labels: dict, block_depth: int,
    ) -> None:
        """Compile one Q-IR instruction to WASM opcodes."""
        op = instr.opcode

        # ── Data movement ──────────────────────────────────
        if op == Opcode.Q_LOAD:
            if isinstance(instr.src1, Immediate):
                wfunc.emit_i64_const(int(instr.src1.value))
            elif isinstance(instr.src1, VReg):
                wfunc.emit_local_get(instr.src1.index)
            if isinstance(instr.dest, VReg):
                wfunc.emit_local_set(instr.dest.index)

        elif op == Opcode.Q_MOVE:
            if isinstance(instr.src1, VReg):
                wfunc.emit_local_get(instr.src1.index)
            elif isinstance(instr.src1, Immediate):
                wfunc.emit_i64_const(int(instr.src1.value))
            if isinstance(instr.dest, VReg):
                wfunc.emit_local_set(instr.dest.index)

        elif op == Opcode.Q_LOAD_STRING:
            # Strings stored as i64 index for simplicity
            if isinstance(instr.dest, VReg):
                idx = 0
                if instr.string_value in self.strings:
                    idx = self.strings.index(instr.string_value)
                wfunc.emit_i64_const(idx)
                wfunc.emit_local_set(instr.dest.index)

        # ── Arithmetic ─────────────────────────────────────
        elif op in (Opcode.Q_ADD, Opcode.Q_SUB, Opcode.Q_MUL,
                    Opcode.Q_DIV, Opcode.Q_MOD):
            self._emit_binop(instr, wfunc, {
                Opcode.Q_ADD: OP_I64_ADD,
                Opcode.Q_SUB: OP_I64_SUB,
                Opcode.Q_MUL: OP_I64_MUL,
                Opcode.Q_DIV: OP_I64_DIV_S,
                Opcode.Q_MOD: OP_I64_REM_S,
            }[op])

        # ── Comparison ─────────────────────────────────────
        elif op in (Opcode.Q_CMP_EQ, Opcode.Q_CMP_NE, Opcode.Q_CMP_GT,
                    Opcode.Q_CMP_LT, Opcode.Q_CMP_GE, Opcode.Q_CMP_LE):
            cmp_ops = {
                Opcode.Q_CMP_EQ: OP_I64_EQ,
                Opcode.Q_CMP_NE: OP_I64_NE,
                Opcode.Q_CMP_GT: OP_I64_GT_S,
                Opcode.Q_CMP_LT: OP_I64_LT_S,
                Opcode.Q_CMP_GE: OP_I64_GE_S,
                Opcode.Q_CMP_LE: OP_I64_LE_S,
            }
            self._emit_binop(instr, wfunc, cmp_ops[op])
            # Extend i32 result to i64
            if isinstance(instr.dest, VReg):
                wfunc.emit_local_get(instr.dest.index)
                wfunc.emit(OP_I64_EXTEND_I32_S)
                wfunc.emit_local_set(instr.dest.index)

        # ── Floating-point ─────────────────────────────────
        elif op in (Opcode.Q_FADD, Opcode.Q_FSUB, Opcode.Q_FMUL, Opcode.Q_FDIV):
            fp_ops = {
                Opcode.Q_FADD: OP_F64_ADD,
                Opcode.Q_FSUB: OP_F64_SUB,
                Opcode.Q_FMUL: OP_F64_MUL,
                Opcode.Q_FDIV: OP_F64_DIV,
            }
            self._emit_fp_binop(instr, wfunc, fp_ops[op])

        elif op == Opcode.Q_FCVT_I2F:
            if isinstance(instr.src1, VReg):
                wfunc.emit_local_get(instr.src1.index)
            wfunc.emit(OP_F64_CONVERT_I64_S)
            if isinstance(instr.dest, VReg):
                wfunc.emit_local_set(instr.dest.index)

        elif op == Opcode.Q_FCVT_F2I:
            if isinstance(instr.src1, VReg):
                wfunc.emit_local_get(instr.src1.index)
            wfunc.emit(OP_I64_TRUNC_F64_S)
            if isinstance(instr.dest, VReg):
                wfunc.emit_local_set(instr.dest.index)

        # ── Control flow ───────────────────────────────────
        elif op == Opcode.Q_LABEL:
            pass  # Labels are handled via block structure

        elif op == Opcode.Q_JUMP:
            wfunc.emit(OP_BR)
            wfunc.emit_bytes(_uleb128(0))  # Branch to enclosing block

        elif op == Opcode.Q_JUMP_IF:
            if isinstance(instr.src1, VReg):
                wfunc.emit_local_get(instr.src1.index)
            elif isinstance(instr.src1, Immediate):
                wfunc.emit_i64_const(int(instr.src1.value))
            wfunc.emit(OP_I64_EQZ)  # i64 → i32
            wfunc.emit(OP_I64_EQZ)  # invert (double eqz = not zero check via i32)
            wfunc.emit(OP_BR_IF)
            wfunc.emit_bytes(_uleb128(0))

        elif op == Opcode.Q_JUMP_IF_NOT:
            if isinstance(instr.src1, VReg):
                wfunc.emit_local_get(instr.src1.index)
            elif isinstance(instr.src1, Immediate):
                wfunc.emit_i64_const(int(instr.src1.value))
            wfunc.emit(OP_I64_EQZ)
            wfunc.emit(OP_BR_IF)
            wfunc.emit_bytes(_uleb128(0))

        elif op == Opcode.Q_CALL:
            # Push args from src1, src2 etc
            if isinstance(instr.src1, VReg):
                wfunc.emit_local_get(instr.src1.index)
            elif isinstance(instr.src1, Immediate):
                wfunc.emit_i64_const(int(instr.src1.value))
            # Look up func index by label name
            if isinstance(instr.dest, Label):
                func_idx = self.func_names.get(instr.dest.name, 0)
                wfunc.emit_call(func_idx)

        elif op == Opcode.Q_RET:
            if isinstance(instr.src1, VReg):
                wfunc.emit_local_get(instr.src1.index)
            elif isinstance(instr.src1, Immediate):
                wfunc.emit_i64_const(int(instr.src1.value))
            wfunc.emit(OP_RETURN)

        # ── I/O ────────────────────────────────────────────
        elif op == Opcode.Q_PRINT:
            if isinstance(instr.src1, VReg):
                wfunc.emit_local_get(instr.src1.index)
            elif isinstance(instr.src1, Immediate):
                wfunc.emit_i64_const(int(instr.src1.value))
            wfunc.emit_call(0)  # import[0] = env.print

        elif op == Opcode.Q_INPUT:
            wfunc.emit_call(1)  # import[1] = env.input
            if isinstance(instr.dest, VReg):
                wfunc.emit_local_set(instr.dest.index)

        # ── NOP / HALT ─────────────────────────────────────
        elif op == Opcode.Q_NOP:
            wfunc.emit(OP_NOP)

        elif op == Opcode.Q_HALT:
            wfunc.emit(OP_UNREACHABLE)

    def _emit_binop(self, instr: QInstruction, wfunc: WasmFunc, wasm_op: int) -> None:
        """Emit a binary operation: dest = src1 OP src2."""
        if isinstance(instr.src1, VReg):
            wfunc.emit_local_get(instr.src1.index)
        elif isinstance(instr.src1, Immediate):
            wfunc.emit_i64_const(int(instr.src1.value))

        if isinstance(instr.src2, VReg):
            wfunc.emit_local_get(instr.src2.index)
        elif isinstance(instr.src2, Immediate):
            wfunc.emit_i64_const(int(instr.src2.value))

        wfunc.emit(wasm_op)

        if isinstance(instr.dest, VReg):
            wfunc.emit_local_set(instr.dest.index)

    def _emit_fp_binop(self, instr: QInstruction, wfunc: WasmFunc, wasm_op: int) -> None:
        """Emit a floating-point binary operation."""
        if isinstance(instr.src1, VReg):
            wfunc.emit_local_get(instr.src1.index)
        elif isinstance(instr.src1, Immediate):
            wfunc.emit(OP_F64_CONST)
            wfunc.emit_bytes(struct.pack("<d", instr.src1.value))

        if isinstance(instr.src2, VReg):
            wfunc.emit_local_get(instr.src2.index)
        elif isinstance(instr.src2, Immediate):
            wfunc.emit(OP_F64_CONST)
            wfunc.emit_bytes(struct.pack("<d", instr.src2.value))

        wfunc.emit(wasm_op)

        if isinstance(instr.dest, VReg):
            wfunc.emit_local_set(instr.dest.index)

    # ═══════════════════════════════════════════════════════
    # Binary Module Emitter
    # ═══════════════════════════════════════════════════════

    def _emit_binary(self, imports: list[tuple[str, str, list[int], list[int]]]) -> bytes:
        """Emit complete WASM binary module."""
        out = bytearray()
        out.extend(WASM_MAGIC)
        out.extend(WASM_VERSION)

        # ── Type section ───────────────────────────────────
        type_entries = bytearray()
        type_sigs: list[tuple[tuple[int, ...], tuple[int, ...]]] = []

        # Import function types
        for _, _, params, results in imports:
            sig = (tuple(params), tuple(results))
            if sig not in type_sigs:
                type_sigs.append(sig)

        # User function types (all: i64^N → i64)
        for wfunc in self.functions:
            params = tuple(I64 for _ in range(wfunc.param_count))
            results = (I64,) if wfunc.has_result else ()
            sig = (params, results)
            if sig not in type_sigs:
                type_sigs.append(sig)

        type_entries.extend(_uleb128(len(type_sigs)))
        for params, results in type_sigs:
            type_entries.append(0x60)  # functype
            type_entries.extend(_uleb128(len(params)))
            for p in params:
                type_entries.append(p)
            type_entries.extend(_uleb128(len(results)))
            for r in results:
                type_entries.append(r)

        out.extend(_section(SEC_TYPE, bytes(type_entries)))

        # ── Import section ─────────────────────────────────
        import_entries = bytearray()
        import_entries.extend(_uleb128(len(imports)))
        for mod, name, params, results in imports:
            import_entries.extend(_encode_string(mod))
            import_entries.extend(_encode_string(name))
            import_entries.append(0x00)  # functype
            sig = (tuple(params), tuple(results))
            type_idx = type_sigs.index(sig)
            import_entries.extend(_uleb128(type_idx))

        out.extend(_section(SEC_IMPORT, bytes(import_entries)))

        # ── Function section ───────────────────────────────
        func_entries = bytearray()
        func_entries.extend(_uleb128(len(self.functions)))
        for wfunc in self.functions:
            params = tuple(I64 for _ in range(wfunc.param_count))
            results = (I64,) if wfunc.has_result else ()
            sig = (params, results)
            type_idx = type_sigs.index(sig)
            func_entries.extend(_uleb128(type_idx))

        out.extend(_section(SEC_FUNCTION, bytes(func_entries)))

        # ── Memory section (1 page = 64KB) ─────────────────
        mem_entries = bytearray()
        mem_entries.extend(_uleb128(1))   # 1 memory
        mem_entries.append(0x00)           # no max
        mem_entries.extend(_uleb128(1))   # initial: 1 page
        out.extend(_section(SEC_MEMORY, bytes(mem_entries)))

        # ── Export section ─────────────────────────────────
        export_entries = bytearray()
        # Export all user functions
        export_list = list(self.func_names.items())
        # Also export memory
        export_entries.extend(_uleb128(len(export_list) + 1))
        for name, idx in export_list:
            export_entries.extend(_encode_string(name))
            export_entries.append(EXPORT_FUNC)
            export_entries.extend(_uleb128(idx))
        # Export memory
        export_entries.extend(_encode_string("memory"))
        export_entries.append(EXPORT_MEMORY)
        export_entries.extend(_uleb128(0))

        out.extend(_section(SEC_EXPORT, bytes(export_entries)))

        # ── Code section ───────────────────────────────────
        code_entries = bytearray()
        code_entries.extend(_uleb128(len(self.functions)))
        for wfunc in self.functions:
            code_entries.extend(wfunc.encode_body())

        out.extend(_section(SEC_CODE, bytes(code_entries)))

        return bytes(out)


# ═══════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════

def compile_to_wasm(module: QModule) -> bytes:
    """Compile Q-IR module to WASM binary bytes."""
    codegen = WasmCodegen()
    return codegen.compile_module(module)


def write_wasm(module: QModule, path: str) -> None:
    """Compile Q-IR module and write to .wasm file."""
    wasm_bytes = compile_to_wasm(module)
    with open(path, "wb") as f:
        f.write(wasm_bytes)

# InterVir — x86_64 LIR Codegen Implementation Brief

> **Date:** 2026-08-28  
> **Audience:** Implementer (AI or human)  
> **Goal:** Add `emit_lir_module_x86_64` to the soft `virc` LIR pipeline  
> **Canonical path:** `AST → HIR → MIR → LIR → RA → Codegen → ELF/Mach-O`  
> **SoT (ARM64 reference):** `stdlib/vir/compiler/lir_codegen.vri`  
> **SoT (encoding reference):** `core/src/codegen.c`, `MUST_READ_CONTEXT/COMPLETE/03_Codegen_Matrix.md`

**Do not touch:** `virc_stage1.vri` (bootstrap stays ARM64 Mach-O). x86 ships via soft `virc.vri` first.

---

## 0. Current State

| Layer | ARM64 | x86_64 |
|-------|-------|--------|
| `lir_codegen.vri` | ✅ ~1,260 LOC, AAPCS64 | ❌ |
| `codegen.vri` emitters | ✅ `arm64_*` | ❌ stub `lir_emit_module` |
| `lir_regalloc_color.vri` | ✅ X19–X27 pool | ❌ hardcoded ARM64 |
| `virc.vri --target x86_64` | — | ❌ empty code buffer |
| `elf.vri` / `macho.vri` | ✅ | ✅ CPU types ready |
| C engine `codegen.c` | ✅ | ✅ (Q-IR, not LIR) |
| `stdlib/vir/codegen/x86_64.vri` | — | AT&T text only, not wired |

**First target:** Linux **ELF** x86_64 (`--target x86_64 --format elf`). macOS x86_64 is Phase 2.

---

## 1. Architecture

### 1.1 File layout (new)

```text
stdlib/vir/compiler/
  codegen.vri           # shared CodeBuf, TargetArch (unchanged)
  codegen_x86.vri       # NEW — binary x86_64 instruction emitters
  lir_codegen.vri       # ARM64 only (unchanged name, no split yet)
  lir_codegen_x86.vri   # NEW — LIR → x86_64, emit_lir_module_x86_64
```

### 1.2 Dispatch (`virc.vri`)

```vir
if target_arch == TargetArch.ARM64 do
    code = emit_lir_module_arm64(lir_funcs)
eif target_arch == TargetArch.X86_64 do
    code = emit_lir_module_x86_64(lir_funcs)
else
    code = lir_emit_module(lir_funcs, target_arch)  # wasm / fallback
end
```

### 1.3 Pipeline target hook (`pipeline.vri`)

Register allocation must know target **before** coloring. State lives in `target.vri`:

```vir
# stdlib/vir/compiler/target.vri
set_codegen_target(target_arch)   # virc.vri, before compile_pipeline
get_codegen_target()              # lir_regalloc_color.vri
```

---

## 2. x86_64 ABI (System V AMD64)

### 2.1 Integer registers (match `codegen.h`)

| ID | Reg | Role |
|----|-----|------|
| 0 | RAX | Return value, div/idiv, syscall |
| 1 | RCX | Arg 4, scratch |
| 2 | RDX | Arg 3, scratch |
| 3 | RBX | **Callee-saved** |
| 4 | RSP | Stack pointer |
| 5 | RBP | Frame pointer (callee-saved) |
| 6 | RSI | Arg 2 |
| 7 | RDI | Arg 1 |
| 8–9 | R8–R9 | Arg 5–6 |
| 10–11 | R10–R11 | Scratch |
| 12–15 | R12–R15 | **Callee-saved** |

### 2.2 Calling convention (mirror ARM64 SetArg/Call)

| ARM64 | x86_64 |
|-------|--------|
| SetArg 0..7 → MOV X0..X7 | SetArg 0..5 → MOV RDI, RSI, RDX, RCX, R8, R9 |
| SetArg ≥8 → stack 16-byte slots | SetArg ≥6 → stack right-to-left, 16-byte align before `call` |
| Call → BL rel26 | Call → `call rel32` |
| Return in X0 | Return in RAX |
| BL patch to func / RT stub | `call rel32` patch |

### 2.3 RA color pool (callee-saved)

| Color | ARM64 | x86_64 |
|-------|-------|--------|
| 0 | X19 | RBX (3) |
| 1 | X20 | R12 (12) |
| 2 | X21 | R13 (13) |
| 3 | X22 | R14 (14) |
| 4 | X23 | R15 (15) — **reserve for heap arena** (like X28) |
| K | 9 (X19–X27, X28 heap) | 4 (RBX, R12–R14; R15 = heap) |

Implement in `lir_regalloc_color.vri`:

```vir
func color_to_phys(color: i64):
    if g_pipeline_target == 1 do   # X86_64
        if color == 0 do out 3 end   # RBX
        if color == 1 do out 12 end  # R12
        if color == 2 do out 13 end  # R13
        if color == 3 do out 14 end  # R14
        out 3
    end
    out 19 + color   # ARM64 X19..
end.
```

Adjust `K` per target (4 for x86, 9 for ARM64).

---

## 3. LIR → x86 lowering map

Mirror `lir_codegen.vri` instruction dispatch. Reference `03_Codegen_Matrix.md` and C `codegen.c`.

| LIR op | x86_64 sequence |
|--------|-----------------|
| Add | `mov rax, src1` / `add rax, src2` / `mov dst, rax` or `lea dst, [a+b]` |
| Sub | `sub` |
| Mul | `imul dst, src` |
| Div | `cqo` / `idiv` / result in RAX |
| Mov | `mov rr` or `mov reg, imm64` |
| Cmp + branch | `cmp` + `je/jne/jg/jl` rel32 |
| Cmp + set | `cmp` + `sete/setne/setg/setl` + `movzx` |
| Load/Store i64 | `mov [base+idx*8]` or RIP-relative |
| Load/Store i8 | `movzx` / `mov` byte |
| Ret | `pop rbp` / `ret` |
| SetArg | `mov` to arg reg or `push` |
| Call | `call rel32` + patch |
| Intrinsic RT | `call` to stub table |

### 3.1 Branches

ARM64 uses fixed 19/26-bit encodings. x86 uses **rel32** for `jmp`, `je`, `jne`, etc.

Reuse fixup list pattern from `lir_codegen.vri` (`lir_fixup_new`, patch at end).

### 3.2 `_start` (Linux ELF)

```text
_start:
  # Save argc/argv from stack (kernel entry)
  # mmap heap (syscall: rax=9, rdi=0, rsi=size, rdx=PROT, r10=MAP, r8=-1, r9=0)
  # Store heap base in R15 (global arena)
  # call main
  # exit(0): rax=60, rdi=0, syscall
```

Page size: **4096** on Linux x86_64 (not 16KB macOS ARM).

---

## 4. RT stub table

Port `emit_lir_rt_stubs` from ARM64. Minimum for bootstrap tests:

| Stub | x86_64 implementation |
|------|----------------------|
| `_rt_print` | `write(1, buf, len)` syscall loop for digits |
| `_rt_print_str` | `write(1, ...)` |
| `_rt_alloc` | bump pointer in R15 arena |
| Atomics | `lock xadd`, `cmpxchg`, `mfence` (not LDAR/STLR) |
| Barriers | `mfence` / `lfence` / `sfence` |

Stub layout: same `LIR_RT_*` indices as `lir.vri`; only machine code differs.

---

## 5. Implementation phases

| Phase | Deliverable | Exit test |
|-------|-------------|-----------|
| **A** | `codegen_x86.vri` core emitters | Unit: encode known bytes |
| **B** | `target.vri` + arch-aware RA | RA assigns RBX/R12–R14 on x86 |
| **C** | `emit_lir_module_x86_64` skeleton + `_start` | Empty main exits 0 on Linux |
| **D** | Integer ALU + mov + ret | `cg_arith.vri` ELF |
| **E** | SetArg + Call + func patch | `cg_call.vri` |
| **F** | Branches + cmp | `cg_when.vri` |
| **G** | RT stubs (print, alloc) | `cg_stdlib_io.vri` subset |
| **H** | StackMem spill emission | RA spill slots work |
| **I** | macOS x86_64 Mach-O `_start` | Optional |

**Do not** implement SIMD/float/atomics in Phase D–F unless tests require them.

---

## 6. Shared gaps (both arches)

From `REGISTER_ALLOCATION_ARCHITECTURE.md`:

- **StackMem** operands assigned by RA but **not emitted** in codegen — blocks correct spill/reload
- **George–Appel coalesce** after coloring — TODO in pipeline
- **lir_clean** pass before RA — TODO

Fix StackMem in ARM64 and x86 together when touching operand lowering.

---

## 7. Testing

### 7.1 Smoke (extend `tests/bootstrap_codegen/`)

```bash
# Soft compiler on C-VM
virc tests/bootstrap_codegen/cg_arith.vri --target x86_64 --format elf -o /tmp/cg_arith
chmod +x /tmp/cg_arith
/tmp/cg_arith   # on Linux x86_64 host or qemu-x86_64
```

### 7.2 Fix stale tests

`stdlib/vir/test/codegen_vtest.vri` imports `x86_64_emit_*` APIs that do not exist — update to `codegen_x86.vri` names.

### 7.3 Assertions

- Portless/native: N/A for codegen
- No localhost loopback in codegen path
- `emit_lir_module_x86_64` must not call `emit_lir_module_arm64`

---

## 8. What NOT to do

- Do not wrap Nginx or duplicate HTTP stack (wrong project)
- Do not port full `lir_codegen.vri` in one PR — phased
- Do not change MIR/LIR opcodes for x86 convenience
- Do not break ARM64 bootstrap (`bin/virc` self-host)
- Do not use AT&T string emitter (`x86_64.vri`) on hot path — binary only
- Do not invent new Vir syntax for codegen internals

---

## 9. Reference reading order

1. `stdlib/vir/compiler/lir_codegen.vri` — structure to mirror
2. `core/src/codegen.c` lines 116–300 — x86 binary encoding
3. `MUST_READ_CONTEXT/COMPLETE/03_Codegen_Matrix.md` — opcode matrix
4. `docs/vir_language_spec_v2.0_en.md` §15.4 — calling conventions
5. `stdlib/vir/rt/elf.vri` — `elf_new(1)` for x86_64

---

## 10. Scaffold status (2026-08-28)

| File | Status |
|------|--------|
| `codegen_x86.vri` | Core binary emitters (Phase A) |
| `lir_codegen_x86.vri` | `emit_lir_module_x86_64` skeleton (Phase C) |
| `target.vri` | `set_codegen_target` / `get_codegen_target` |
| `pipeline.vri` | unchanged (no target state) |
| `lir_regalloc_color.vri` | Arch-aware `color_to_phys` |
| `virc.vri` | Dispatch to x86 module |

Next implementation step: **Phase D** — wire LIR Add/Sub/Mul/Mov/Ret in `lir_codegen_x86.vri`.

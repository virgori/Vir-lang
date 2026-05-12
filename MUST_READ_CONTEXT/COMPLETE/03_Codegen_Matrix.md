# VIR Codegen Matrix — Q-IR → Native Instructions

> **Mục đích:** Cross-reference mỗi Q-IR opcode với x86_64 và ARM64 instruction sequences
> **Ngày tạo:** 22/03/2026
> **Phiên bản:** 2.0 — Updated 2026-04-11
> **Source (C engine):** `core/src/codegen.c`
> **Source (virc self-hosted):** `stdlib/vir/compiler/main.vri` (ARM64), `stdlib/vir/compiler/codegen.vri` (emitters)
>
> ⚠️ **CẬP NHẬT 2026-04-11:**
> - Self-hosted compiler virc dùng **82 canonical QOp opcodes** (xem `ir_optimizer.vri` QOp enum)
> - virc ARM64 codegen (`main.vri`, 1,953 LOC) bao gồm:
>   - Full integer arithmetic/comparison/control flow: Add–Xor, CmpEq–CmpLe, Jump/JumpIfNot/JumpIf/Label/Call/Ret
>   - Memory: Alloc, LoadByte/StoreByte, LoadWord/StoreWord, LoadGlobal/StoreGlobal
>   - Array/String: ArrNew–ArrLen, StrCat/StrLenOp, PrintStr
>   - SIMD (NEON): VLoad–VPerm (12 ops) → calls neon_* emitters from codegen.vri
>   - Fused: FusedMulAdd (MADD/MSUB), FusedBiasRelu (ADD+CMP+CSEL), FusedBiasGelu
>   - Float: FAdd (FADD Dd), FSub (FSUB Dd), FMul (FMUL Dd), FDiv (FDIV Dd), FCvtI2F (SCVTF), FCvtF2I (FCVTZS)
>   - Function pointers: LoadFuncAddr (ADR), CallFunc (BLR X16)
>   - Stack spilling: vreg >= 16 → LDR/STR via X8/X16 scratch
> - Tài liệu dưới đây mô tả C engine codegen (legacy) — virc codegen xem `main.vri` trực tiếp

---

## Mục lục

1. [Register Conventions](#1-register-conventions)
2. [Arithmetic Operations](#2-arithmetic-operations)
3. [Float Operations](#3-float-operations)
4. [Comparison & Branching](#4-comparison--branching)
5. [Memory Operations](#5-memory-operations)
6. [Function Calls](#6-function-calls)
7. [String Operations](#7-string-operations)
8. [Array Operations](#8-array-operations)
9. [SIMD/Vector Operations](#9-simdvector-operations)
10. [System Calls](#10-system-calls)

---

## 1. Register Conventions

### x86_64 (System V AMD64 ABI)

| Register | Purpose | Callee-saved |
|----------|---------|--------------|
| `RAX` | Return value, scratch | No |
| `RBX` | General purpose | **Yes** |
| `RCX` | Arg 4, scratch | No |
| `RDX` | Arg 3, scratch | No |
| `RSI` | Arg 2, scratch | No |
| `RDI` | Arg 1, scratch | No |
| `RBP` | Frame pointer | **Yes** |
| `RSP` | Stack pointer | **Yes** |
| `R8-R9` | Arg 5-6, scratch | No |
| `R10-R11` | Scratch | No |
| `R12-R15` | General purpose | **Yes** |
| `XMM0-XMM7` | Float args/return | No |
| `XMM8-XMM15` | Float scratch | No |

### ARM64 (AAPCS64)

| Register | Purpose | Callee-saved |
|----------|---------|--------------|
| `X0-X7` | Args 1-8, scratch | No |
| `X0` | Return value | No |
| `X8` | Indirect result | No |
| `X9-X15` | Scratch | No |
| `X16-X17` | IP0/IP1 (linker) | No |
| `X18` | Platform reserved | - |
| `X19-X28` | General purpose | **Yes** |
| `X29` | Frame pointer (FP) | **Yes** |
| `X30` | Link register (LR) | **Yes** |
| `SP` | Stack pointer | **Yes** |
| `V0-V7` | Float args/return | No |
| `V8-V15` | Float (low 64 saved) | **Partial** |
| `V16-V31` | Scratch | No |

---

## 2. Arithmetic Operations

### Q_ADD

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MOV rax, src1` → `ADD rax, src2` → `MOV dest, rax` |
| **x86_64 (optimized)** | `LEA dest, [src1 + src2]` (if dest ≠ src1,src2) |
| **ARM64** | `ADD Xd, Xn, Xm` |
| **ARM64 (imm)** | `ADD Xd, Xn, #imm12` |

```c
// codegen.c
case Q_ADD:
    #ifdef TARGET_X86_64
    x86_emit_mov(dest, src1);
    x86_emit_add_rr(dest, src2);
    #elif TARGET_ARM64
    arm64_emit_add_rrr(dest, src1, src2);
    #endif
```

---

### Q_SUB

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MOV rax, src1` → `SUB rax, src2` → `MOV dest, rax` |
| **ARM64** | `SUB Xd, Xn, Xm` |

---

### Q_MUL

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MOV rax, src1` → `IMUL rax, src2` → `MOV dest, rax` |
| **x86_64 (const)** | `IMUL dest, src1, imm32` |
| **ARM64** | `MUL Xd, Xn, Xm` |

---

### Q_DIV

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MOV rax, src1` → `CQO` → `IDIV src2` → `MOV dest, rax` |
| **ARM64** | `SDIV Xd, Xn, Xm` |

**Notes:**
- x86_64 requires `RDX:RAX` for dividend (CQO sign-extends RAX to RDX)
- Division by zero check must be emitted before IDIV

---

### Q_MOD

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MOV rax, src1` → `CQO` → `IDIV src2` → `MOV dest, rdx` |
| **ARM64** | `SDIV Xt, Xn, Xm` → `MSUB Xd, Xt, Xm, Xn` |

**ARM64 Note:** No dedicated modulo instruction. Use `MSUB Xd, Xq, Xm, Xn` = Xn - Xq*Xm

---

### Q_NEG

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MOV dest, src` → `NEG dest` |
| **ARM64** | `NEG Xd, Xn` (alias for `SUB Xd, XZR, Xn`) |

---

### Q_ABS

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MOV rax, src` → `MOV rdx, src` → `SAR rdx, 63` → `XOR rax, rdx` → `SUB rax, rdx` |
| **ARM64** | `CMP Xn, #0` → `CNEG Xd, Xn, LT` |

---

## 3. Float Operations

### Q_FADD

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64 (SSE)** | `MOVSD xmm0, src1` → `ADDSD xmm0, src2` → `MOVSD dest, xmm0` |
| **x86_64 (AVX)** | `VADDSD dest, src1, src2` |
| **ARM64** | `FADD Dd, Dn, Dm` |

---

### Q_FSUB

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `SUBSD dest, src2` |
| **ARM64** | `FSUB Dd, Dn, Dm` |

---

### Q_FMUL

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MULSD dest, src2` |
| **ARM64** | `FMUL Dd, Dn, Dm` |

---

### Q_FDIV

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `DIVSD dest, src2` |
| **ARM64** | `FDIV Dd, Dn, Dm` |

---

### Q_SQRT

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `SQRTSD dest, src` |
| **ARM64** | `FSQRT Dd, Dn` |

---

### Q_SIN / Q_COS / Q_TAN

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | Call to libm: `CALL sin@PLT` |
| **ARM64** | Call to libm: `BL sin` |

**Notes:** These are not native instructions, require function call.

---

### Q_POW

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `CALL pow@PLT` |
| **ARM64** | `BL pow` |

---

## 4. Comparison & Branching

### Q_CMP_EQ

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `CMP src1, src2` → `SETE dest_low` → `MOVZX dest, dest_low` |
| **ARM64** | `CMP Xn, Xm` → `CSET Xd, EQ` |

---

### Q_CMP_LT

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `CMP src1, src2` → `SETL dest_low` → `MOVZX dest, dest_low` |
| **ARM64** | `CMP Xn, Xm` → `CSET Xd, LT` |

---

### Q_CMP_GT

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `CMP src1, src2` → `SETG dest_low` → `MOVZX dest, dest_low` |
| **ARM64** | `CMP Xn, Xm` → `CSET Xd, GT` |

---

### Q_JUMP

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `JMP label` |
| **ARM64** | `B label` |

---

### Q_JUMP_IF

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `TEST cond, cond` → `JNZ label` |
| **ARM64** | `CBNZ cond, label` |

---

### Q_JUMP_IF_NOT

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `TEST cond, cond` → `JZ label` |
| **ARM64** | `CBZ cond, label` |

---

## 5. Memory Operations

### Q_LOAD (register/immediate)

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64 (imm)** | `MOV dest, imm64` (or `LEA` for RIP-relative) |
| **x86_64 (reg)** | `MOV dest, [src]` |
| **ARM64 (imm)** | `MOV Xd, #imm16` (or `MOVZ`+`MOVK` for large) |
| **ARM64 (reg)** | `LDR Xd, [Xn]` |

---

### Q_STORE

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MOV [addr], value` |
| **ARM64** | `STR Xd, [Xn]` |

---

### Q_LOAD_BYTE

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MOVZX dest, BYTE PTR [addr]` |
| **ARM64** | `LDRB Wd, [Xn]` |

---

### Q_STORE_BYTE

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MOV BYTE PTR [addr], value` |
| **ARM64** | `STRB Wd, [Xn]` |

---

### Q_ALLOC

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MOV rdi, size` → `CALL malloc@PLT` → `MOV dest, rax` |
| **ARM64** | `MOV X0, size` → `BL malloc` → `MOV dest, X0` |

---

### Q_FREE

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MOV rdi, ptr` → `CALL free@PLT` |
| **ARM64** | `MOV X0, ptr` → `BL free` |

---

## 6. Function Calls

### Q_CALL

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | Setup args (RDI, RSI, RDX, RCX, R8, R9) → `CALL func` |
| **ARM64** | Setup args (X0-X7) → `BL func` |

**x86_64 Calling Convention:**
```asm
; foo(a, b, c, d, e, f)
MOV  RDI, a
MOV  RSI, b
MOV  RDX, c
MOV  RCX, d
MOV  R8,  e
MOV  R9,  f
CALL foo
; Return in RAX
```

**ARM64 Calling Convention:**
```asm
; foo(a, b, c, d, e, f)
MOV  X0, a
MOV  X1, b
MOV  X2, c
MOV  X3, d
MOV  X4, e
MOV  X5, f
BL   foo
; Return in X0
```

---

### Q_RET

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MOV rax, ret_val` → `RET` |
| **ARM64** | `MOV X0, ret_val` → `RET` |

---

## 7. String Operations

### Q_STR_LEN

| Architecture | Implementation |
|--------------|----------------|
| **x86_64** | Call runtime: `strlen_vir(str)` |
| **ARM64** | Call runtime: `strlen_vir(str)` |

**Optimized inline (SIMD):**
```asm
; x86_64 - find null terminator using SSE
PXOR    xmm0, xmm0          ; Zero vector
.loop:
MOVDQU  xmm1, [rsi + rax]   ; Load 16 bytes
PCMPEQB xmm1, xmm0          ; Compare with zero
PMOVMSKB ecx, xmm1          ; Get mask
TEST    ecx, ecx
JNZ     .found
ADD     rax, 16
JMP     .loop
.found:
BSF     ecx, ecx            ; Find first zero
ADD     rax, rcx
```

---

### Q_STR_CAT

| Architecture | Implementation |
|--------------|----------------|
| **Both** | Call runtime: `str_concat(str1, str2)` |

**Runtime implementation allocates new string.**

---

### Q_STR_EQ

| Architecture | Implementation |
|--------------|----------------|
| **Both** | Call runtime: `str_eq(str1, str2)` |

**Optimized inline (short strings):**
```asm
; x86_64 - compare up to 8 bytes at once
MOV rax, [str1]
CMP rax, [str2]
SETE al
MOVZX eax, al
```

---

## 8. Array Operations

### Q_ARR_NEW

| Architecture | Implementation |
|--------------|----------------|
| **Both** | Call runtime: `arr_new()` |

---

### Q_ARR_GET

| Architecture | Implementation |
|--------------|----------------|
| **x86_64** | `MOV rax, [arr + header_size]` → `MOV dest, [rax + idx*8]` |
| **ARM64** | `LDR X0, [arr, #header_offset]` → `LDR dest, [X0, idx, LSL #3]` |

---

### Q_ARR_SET

| Architecture | Implementation |
|--------------|----------------|
| **x86_64** | `MOV rax, [arr + header_size]` → `MOV [rax + idx*8], value` |
| **ARM64** | `LDR X0, [arr, #header_offset]` → `STR value, [X0, idx, LSL #3]` |

---

### Q_ARR_LEN

| Architecture | Implementation |
|--------------|----------------|
| **x86_64** | `MOV dest, [arr + len_offset]` |
| **ARM64** | `LDR dest, [arr, #len_offset]` |

---

### Q_ARR_PUSH / Q_ARR_POP

| Architecture | Implementation |
|--------------|----------------|
| **Both** | Call runtime: `arr_push(arr, value)` / `arr_pop(arr)` |

**May trigger reallocation if capacity exceeded.**

---

## 9. SIMD/Vector Operations

### Q_VLOAD

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64 (aligned)** | `MOVDQA xmm0, [addr]` |
| **x86_64 (unaligned)** | `MOVDQU xmm0, [addr]` |
| **ARM64** | `LD1 {V0.4S}, [Xn]` |

---

### Q_VSTORE

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64 (aligned)** | `MOVDQA [addr], xmm0` |
| **x86_64 (unaligned)** | `MOVDQU [addr], xmm0` |
| **ARM64** | `ST1 {V0.4S}, [Xn]` |

---

### Q_VADD (i32x4)

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64 (SSE)** | `PADDD xmm_dest, xmm_src` |
| **x86_64 (AVX)** | `VPADDD ymm_dest, ymm_src1, ymm_src2` |
| **ARM64** | `ADD V0.4S, V1.4S, V2.4S` |

---

### Q_VMUL (f32x4)

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64 (SSE)** | `MULPS xmm_dest, xmm_src` |
| **x86_64 (AVX)** | `VMULPS ymm_dest, ymm_src1, ymm_src2` |
| **ARM64** | `FMUL V0.4S, V1.4S, V2.4S` |

---

### Q_VFMA (fused multiply-add)

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64 (FMA3)** | `VFMADD231PS ymm_dest, ymm_a, ymm_b` |
| **ARM64** | `FMLA V0.4S, V1.4S, V2.4S` |

---

### Q_VREDUCE (horizontal sum)

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64 (SSE)** | `HADDPS xmm0, xmm0` → `HADDPS xmm0, xmm0` |
| **ARM64** | `FADDP V0.4S, V0.4S, V0.4S` → `FADDP V0.2S, V0.2S, V0.2S` |

---

## 10. System Calls

### Q_SYSCALL (Linux)

| Architecture | Instruction Sequence |
|--------------|---------------------|
| **x86_64** | `MOV rax, syscall_num` → `SYSCALL` |
| **ARM64** | `MOV X8, syscall_num` → `SVC #0` |

**x86_64 Syscall Convention:**
```asm
; syscall(num, arg1, arg2, arg3, arg4, arg5, arg6)
MOV RAX, num
MOV RDI, arg1
MOV RSI, arg2
MOV RDX, arg3
MOV R10, arg4    ; Note: NOT RCX!
MOV R8,  arg5
MOV R9,  arg6
SYSCALL
; Return in RAX
```

**ARM64 Syscall Convention:**
```asm
; syscall(num, arg1, arg2, arg3, arg4, arg5, arg6)
MOV X8, num
MOV X0, arg1
MOV X1, arg2
MOV X2, arg3
MOV X3, arg4
MOV X4, arg5
MOV X5, arg6
SVC #0
; Return in X0
```

---

## Quick Reference: Opcode → Instruction

| Q-IR | x86_64 | ARM64 |
|------|--------|-------|
| `Q_ADD` | `ADD r, r` | `ADD Xd, Xn, Xm` |
| `Q_SUB` | `SUB r, r` | `SUB Xd, Xn, Xm` |
| `Q_MUL` | `IMUL r, r` | `MUL Xd, Xn, Xm` |
| `Q_DIV` | `CQO` + `IDIV r` | `SDIV Xd, Xn, Xm` |
| `Q_MOD` | `CQO` + `IDIV r` (rdx) | `SDIV` + `MSUB` |
| `Q_NEG` | `NEG r` | `NEG Xd, Xn` |
| `Q_FADD` | `ADDSD xmm, xmm` | `FADD Dd, Dn, Dm` |
| `Q_FSUB` | `SUBSD xmm, xmm` | `FSUB Dd, Dn, Dm` |
| `Q_FMUL` | `MULSD xmm, xmm` | `FMUL Dd, Dn, Dm` |
| `Q_FDIV` | `DIVSD xmm, xmm` | `FDIV Dd, Dn, Dm` |
| `Q_SQRT` | `SQRTSD xmm, xmm` | `FSQRT Dd, Dn` |
| `Q_AND` | `AND r, r` | `AND Xd, Xn, Xm` |
| `Q_OR` | `OR r, r` | `ORR Xd, Xn, Xm` |
| `Q_XOR` | `XOR r, r` | `EOR Xd, Xn, Xm` |
| `Q_NOT` | `NOT r` | `MVN Xd, Xn` |
| `Q_SHL` | `SHL r, cl` | `LSL Xd, Xn, Xm` |
| `Q_SHR` | `SAR r, cl` | `ASR Xd, Xn, Xm` |
| `Q_CMP_EQ` | `CMP` + `SETE` | `CMP` + `CSET EQ` |
| `Q_CMP_LT` | `CMP` + `SETL` | `CMP` + `CSET LT` |
| `Q_CMP_GT` | `CMP` + `SETG` | `CMP` + `CSET GT` |
| `Q_JUMP` | `JMP label` | `B label` |
| `Q_JUMP_IF` | `TEST` + `JNZ` | `CBNZ Xn, label` |
| `Q_JUMP_IF_NOT` | `TEST` + `JZ` | `CBZ Xn, label` |
| `Q_CALL` | `CALL func` | `BL func` |
| `Q_RET` | `RET` | `RET` |
| `Q_LOAD` | `MOV r, [m]` | `LDR Xd, [Xn]` |
| `Q_STORE` | `MOV [m], r` | `STR Xd, [Xn]` |
| `Q_SYSCALL` | `SYSCALL` | `SVC #0` |
| `Q_VLOAD` | `MOVDQA xmm, [m]` | `LD1 {Vd.4S}, [Xn]` |
| `Q_VSTORE` | `MOVDQA [m], xmm` | `ST1 {Vd.4S}, [Xn]` |
| `Q_VADD` | `PADDD xmm, xmm` | `ADD Vd.4S, Vn.4S, Vm.4S` |
| `Q_VMUL` | `MULPS xmm, xmm` | `FMUL Vd.4S, Vn.4S, Vm.4S` |
| `Q_VFMA` | `VFMADD231PS` | `FMLA Vd.4S, Vn.4S, Vm.4S` |

---

## Architecture-Specific Notes

### x86_64

1. **Division quirks:** `IDIV` uses `RDX:RAX` as dividend. Must `CQO` first.
2. **Shift counts:** Only `CL` register for variable shifts.
3. **SIMD alignment:** `MOVDQA` requires 16-byte alignment, use `MOVDQU` for unaligned.
4. **Syscall clobbers:** `SYSCALL` clobbers `RCX` and `R11`.
5. **Stack alignment:** Must be 16-byte aligned before `CALL`.

### ARM64

1. **Zero register:** `XZR/WZR` reads as 0, writes are discarded.
2. **Condition flags:** Set by `CMP`, consumed by conditional ops.
3. **PC-relative addressing:** `ADR`/`ADRP` for nearby/far addresses.
4. **No flags from ALU:** Most arithmetic ops don't set flags unless `*S` variant.
5. **Link register:** `BL` stores return address in `X30`, `RET` jumps to `X30`.

---

## Code Generation Tips for Vir→Vir Replacement

### Must Preserve:

1. **Calling convention compatibility** — x86_64 and ARM64 have different arg registers
2. **Stack frame layout** — Callee-saved registers, local variables
3. **SIMD lane semantics** — Element order differs between SSE and NEON
4. **Syscall numbers** — Different between Linux/macOS/FreeBSD

### Simplification Opportunities:

1. **Unified register allocator** — Abstract over physical register differences
2. **Pattern matching** — Combine `CMP` + branch into single instruction on ARM64
3. **Peephole optimization** — `MOV R, R` → delete, `ADD R, 0` → delete

---

*Document generated for Stage 4 "Kill C" preparation — 22/03/2026*

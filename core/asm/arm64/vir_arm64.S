// ═══════════════════════════════════════════════════════════════════
// vir_arm64.S – Vir Engine ARM64 (AArch64) Assembly Hot Paths
// ═══════════════════════════════════════════════════════════════════
// Spec §3.2 – Bản B (Fast Register-Direct) hand-tuned routines.
//
// Calling convention: AAPCS64
//   args: x0-x7
//   return: x0
//   callee-saved: x19-x28, x29(FP), x30(LR)
// ═══════════════════════════════════════════════════════════════════

// ── Platform-specific section/export directives ──────────
#ifdef __APPLE__
  .section __TEXT,__text,regular,pure_instructions
  .build_version macos, 14, 0
  #define FUNC(name) _##name
#else
  .section .text
  #define FUNC(name) name
#endif

// ═══════════════════════════════════════════════════════
// 1. Integer Arithmetic (64-bit signed)
// ═══════════════════════════════════════════════════════

// int64_t vir_asm_add(int64_t a, int64_t b)
.globl FUNC(vir_asm_add)
.p2align 4
FUNC(vir_asm_add):
    add     x0, x0, x1
    ret

// int64_t vir_asm_sub(int64_t a, int64_t b)
.globl FUNC(vir_asm_sub)
.p2align 4
FUNC(vir_asm_sub):
    sub     x0, x0, x1
    ret

// int64_t vir_asm_mul(int64_t a, int64_t b)
.globl FUNC(vir_asm_mul)
.p2align 4
FUNC(vir_asm_mul):
    mul     x0, x0, x1
    ret

// int64_t vir_asm_div(int64_t a, int64_t b)
.globl FUNC(vir_asm_div)
.p2align 4
FUNC(vir_asm_div):
    sdiv    x0, x0, x1
    ret

// int64_t vir_asm_mod(int64_t a, int64_t b)
.globl FUNC(vir_asm_mod)
.p2align 4
FUNC(vir_asm_mod):
    sdiv    x2, x0, x1         // x2 = a / b
    msub    x0, x2, x1, x0     // x0 = a - (a/b)*b = a % b
    ret

// ═══════════════════════════════════════════════════════
// 2. Bitwise Operations
// ═══════════════════════════════════════════════════════

// int64_t vir_asm_and(int64_t a, int64_t b)
.globl FUNC(vir_asm_and)
.p2align 4
FUNC(vir_asm_and):
    and     x0, x0, x1
    ret

// int64_t vir_asm_or(int64_t a, int64_t b)
.globl FUNC(vir_asm_or)
.p2align 4
FUNC(vir_asm_or):
    orr     x0, x0, x1
    ret

// int64_t vir_asm_xor(int64_t a, int64_t b)
.globl FUNC(vir_asm_xor)
.p2align 4
FUNC(vir_asm_xor):
    eor     x0, x0, x1
    ret

// int64_t vir_asm_shl(int64_t a, int64_t shift)
.globl FUNC(vir_asm_shl)
.p2align 4
FUNC(vir_asm_shl):
    lsl     x0, x0, x1
    ret

// int64_t vir_asm_shr(int64_t a, int64_t shift)
.globl FUNC(vir_asm_shr)
.p2align 4
FUNC(vir_asm_shr):
    asr     x0, x0, x1         // arithmetic shift right
    ret

// ═══════════════════════════════════════════════════════
// 3. Comparisons (return 1/0)
// ═══════════════════════════════════════════════════════

// int64_t vir_asm_cmp_eq(int64_t a, int64_t b)
.globl FUNC(vir_asm_cmp_eq)
.p2align 4
FUNC(vir_asm_cmp_eq):
    cmp     x0, x1
    cset    x0, eq
    ret

// int64_t vir_asm_cmp_gt(int64_t a, int64_t b)
.globl FUNC(vir_asm_cmp_gt)
.p2align 4
FUNC(vir_asm_cmp_gt):
    cmp     x0, x1
    cset    x0, gt
    ret

// int64_t vir_asm_cmp_lt(int64_t a, int64_t b)
.globl FUNC(vir_asm_cmp_lt)
.p2align 4
FUNC(vir_asm_cmp_lt):
    cmp     x0, x1
    cset    x0, lt
    ret

// int64_t vir_asm_cmp_ge(int64_t a, int64_t b)
.globl FUNC(vir_asm_cmp_ge)
.p2align 4
FUNC(vir_asm_cmp_ge):
    cmp     x0, x1
    cset    x0, ge
    ret

// int64_t vir_asm_cmp_le(int64_t a, int64_t b)
.globl FUNC(vir_asm_cmp_le)
.p2align 4
FUNC(vir_asm_cmp_le):
    cmp     x0, x1
    cset    x0, le
    ret

// ═══════════════════════════════════════════════════════
// 4. Jump Table Trampoline
// ═══════════════════════════════════════════════════════
//
// void vir_asm_jump_table_dispatch(void **table, uint64_t index)
//   table → x0, index → x1

.globl FUNC(vir_asm_jump_table_dispatch)
.p2align 4
FUNC(vir_asm_jump_table_dispatch):
    ldr     x2, [x0, x1, lsl #3]   // x2 = table[index]
    br      x2                       // tail branch

// ═══════════════════════════════════════════════════════
// 5. Binary Patch Routine (ARM64)
// ═══════════════════════════════════════════════════════
//
// On ARM64, patching a branch: overwrite the B instruction.
// void vir_asm_patch_branch(uint32_t *branch_site, void *new_target)
//   branch_site → x0 (points at the B instruction)
//   new_target → x1
//
// B imm26: opcode = 0x14000000 | (imm26 & 0x03FFFFFF)
// imm26 = (new_target - branch_site) >> 2

.globl FUNC(vir_asm_patch_branch)
.p2align 4
FUNC(vir_asm_patch_branch):
    sub     x2, x1, x0             // offset = new_target - branch_site
    asr     x2, x2, #2             // divide by 4 (instruction granularity)
    and     x2, x2, #0x03FFFFFF    // mask to 26 bits
    mov     w3, #0x14000000         // B opcode base
    orr     w2, w3, w2              // combine
    str     w2, [x0]               // write patched instruction
    // Data synchronization + instruction cache invalidation
    dsb     ish
    dc      cvau, x0               // clean data cache
    dsb     ish
    ic      ivau, x0               // invalidate instruction cache
    dsb     ish
    isb                             // instruction synchronization barrier
    ret

// ═══════════════════════════════════════════════════════
// 6. Memory Copy (for code injection)
// ═══════════════════════════════════════════════════════
//
// void vir_asm_memcpy64(void *dst, const void *src, uint64_t n_bytes)

.globl FUNC(vir_asm_memcpy64)
.p2align 4
FUNC(vir_asm_memcpy64):
    cbz     x2, .Lmemcpy_done
.Lmemcpy_loop:
    ldrb    w3, [x1], #1
    strb    w3, [x0], #1
    subs    x2, x2, #1
    b.ne    .Lmemcpy_loop
.Lmemcpy_done:
    ret

// ═══════════════════════════════════════════════════════
// 7. Register Spill/Restore for Context Switch
// ═══════════════════════════════════════════════════════
//
// void vir_asm_save_regs(int64_t *save_area)

.globl FUNC(vir_asm_save_regs)
.p2align 4
FUNC(vir_asm_save_regs):
    stp     x19, x20, [x0, #0]
    stp     x21, x22, [x0, #16]
    stp     x23, x24, [x0, #32]
    stp     x25, x26, [x0, #48]
    stp     x27, x28, [x0, #64]
    stp     x29, x30, [x0, #80]    // FP + LR
    mov     x1, sp
    str     x1, [x0, #96]          // SP
    ret

// void vir_asm_restore_regs(const int64_t *save_area)
.globl FUNC(vir_asm_restore_regs)
.p2align 4
FUNC(vir_asm_restore_regs):
    ldp     x19, x20, [x0, #0]
    ldp     x21, x22, [x0, #16]
    ldp     x23, x24, [x0, #32]
    ldp     x25, x26, [x0, #48]
    ldp     x27, x28, [x0, #64]
    ldp     x29, x30, [x0, #80]
    ldr     x1, [x0, #96]
    mov     sp, x1
    ret

// ═══════════════════════════════════════════════════════
// 8. Atomic Compare-And-Swap (for lock-free patcher)
// ═══════════════════════════════════════════════════════
//
// int vir_asm_cas64(int64_t *ptr, int64_t expected, int64_t desired)

.globl FUNC(vir_asm_cas64)
.p2align 4
FUNC(vir_asm_cas64):
#ifdef __ARM_FEATURE_ATOMICS
    // LSE atomics (ARMv8.1+)
    mov     x3, x1                  // expected
    cas     x3, x2, [x0]            // atomic CAS
    cmp     x3, x1                  // did it match?
    cset    x0, eq
    ret
#else
    // LL/SC fallback
.Lcas_retry:
    ldaxr   x3, [x0]               // load-acquire exclusive
    cmp     x3, x1                  // compare with expected
    b.ne    .Lcas_fail
    stlxr   w4, x2, [x0]           // store-release exclusive
    cbnz    w4, .Lcas_retry         // retry if store failed
    mov     x0, #1                  // success
    ret
.Lcas_fail:
    clrex                           // clear exclusive monitor
    mov     x0, #0                  // failure
    ret
#endif

// ═══════════════════════════════════════════════════════
// 9. Fast VM Register Access
// ═══════════════════════════════════════════════════════
//
// int64_t vir_asm_reg_read(const int64_t *regs, uint32_t idx)
.globl FUNC(vir_asm_reg_read)
.p2align 4
FUNC(vir_asm_reg_read):
    ldr     x0, [x0, x1, lsl #3]
    ret

// void vir_asm_reg_write(int64_t *regs, uint32_t idx, int64_t val)
.globl FUNC(vir_asm_reg_write)
.p2align 4
FUNC(vir_asm_reg_write):
    str     x2, [x0, x1, lsl #3]
    ret

// ═══════════════════════════════════════════════════════
// 10. macOS JIT Write Protection Toggle
// ═══════════════════════════════════════════════════════
//
// ARM64 macOS (Apple Silicon) requires toggling JIT write protection.
// void vir_asm_jit_write_protect(int enable)
//   enable=0 → allow writes, enable=1 → protect (execute only)
//
// Uses pthread_jit_write_protect_np from libpthread.

#ifdef __APPLE__
.globl FUNC(vir_asm_jit_write_protect)
.p2align 4
FUNC(vir_asm_jit_write_protect):
    // x0 already has the enable flag
    // Tail-call to pthread_jit_write_protect_np
    b       _pthread_jit_write_protect_np
#endif

// ═══════════════════════════════════════════════════════
// 11. Cache Maintenance for JIT
// ═══════════════════════════════════════════════════════
//
// void vir_asm_flush_icache(void *addr, uint64_t size)
//   Flush instruction cache for JIT code region.

.globl FUNC(vir_asm_flush_icache)
.p2align 4
FUNC(vir_asm_flush_icache):
    // Clean data cache and invalidate instruction cache
    // for the range [addr, addr+size)
    add     x1, x0, x1             // x1 = end address
.Lflush_loop:
    dc      cvau, x0               // clean data cache by VA to PoU
    add     x0, x0, #64            // next cache line (64 bytes)
    cmp     x0, x1
    b.lo    .Lflush_loop
    dsb     ish                     // ensure completion
    // Now invalidate instruction cache
    sub     x0, x0, x1
    sub     x0, x1, x0             // back to start (approximate)
.Lflush_ic_loop:
    ic      ivau, x0
    add     x0, x0, #64
    cmp     x0, x1
    b.lo    .Lflush_ic_loop
    dsb     ish
    isb
    ret

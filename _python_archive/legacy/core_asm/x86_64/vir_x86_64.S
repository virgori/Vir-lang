; ═══════════════════════════════════════════════════════════════════
; vir_x86_64.S – Vir Engine x86-64 Assembly Hot Paths
; ═══════════════════════════════════════════════════════════════════
; Spec §3.2 – Bản B (Fast Register-Direct) hand-tuned routines.
;
; These are the inner-loop hot functions that the C codegen can
; call directly for maximum performance.
;
; Calling convention: System V AMD64 ABI
;   args: rdi, rsi, rdx, rcx, r8, r9
;   return: rax
;   callee-saved: rbx, rbp, r12-r15
; ═══════════════════════════════════════════════════════════════════

.intel_syntax noprefix

; ── Platform-specific section/export directives ──────────
#ifdef __APPLE__
  .section __TEXT,__text,regular,pure_instructions
  #define GLOBAL(name) .globl _##name ; _##name
  #define FUNC(name)   _##name
#else
  .section .text
  #define GLOBAL(name) .globl name ; .type name, @function ; name
  #define FUNC(name)   name
#endif

; ═══════════════════════════════════════════════════════
; 1. Integer Arithmetic (64-bit signed)
; ═══════════════════════════════════════════════════════

; int64_t vir_asm_add(int64_t a, int64_t b)
.globl FUNC(vir_asm_add)
.p2align 4
FUNC(vir_asm_add):
    mov     rax, rdi
    add     rax, rsi
    ret

; int64_t vir_asm_sub(int64_t a, int64_t b)
.globl FUNC(vir_asm_sub)
.p2align 4
FUNC(vir_asm_sub):
    mov     rax, rdi
    sub     rax, rsi
    ret

; int64_t vir_asm_mul(int64_t a, int64_t b)
.globl FUNC(vir_asm_mul)
.p2align 4
FUNC(vir_asm_mul):
    mov     rax, rdi
    imul    rax, rsi
    ret

; int64_t vir_asm_div(int64_t a, int64_t b)
.globl FUNC(vir_asm_div)
.p2align 4
FUNC(vir_asm_div):
    mov     rax, rdi
    cqo                     ; sign-extend RAX → RDX:RAX
    idiv    rsi             ; RAX = quotient, RDX = remainder
    ret

; int64_t vir_asm_mod(int64_t a, int64_t b)
.globl FUNC(vir_asm_mod)
.p2align 4
FUNC(vir_asm_mod):
    mov     rax, rdi
    cqo
    idiv    rsi
    mov     rax, rdx        ; remainder
    ret

; ═══════════════════════════════════════════════════════
; 2. Bitwise Operations
; ═══════════════════════════════════════════════════════

; int64_t vir_asm_and(int64_t a, int64_t b)
.globl FUNC(vir_asm_and)
.p2align 4
FUNC(vir_asm_and):
    mov     rax, rdi
    and     rax, rsi
    ret

; int64_t vir_asm_or(int64_t a, int64_t b)
.globl FUNC(vir_asm_or)
.p2align 4
FUNC(vir_asm_or):
    mov     rax, rdi
    or      rax, rsi
    ret

; int64_t vir_asm_xor(int64_t a, int64_t b)
.globl FUNC(vir_asm_xor)
.p2align 4
FUNC(vir_asm_xor):
    mov     rax, rdi
    xor     rax, rsi
    ret

; int64_t vir_asm_shl(int64_t a, int64_t shift)
.globl FUNC(vir_asm_shl)
.p2align 4
FUNC(vir_asm_shl):
    mov     rax, rdi
    mov     rcx, rsi
    shl     rax, cl
    ret

; int64_t vir_asm_shr(int64_t a, int64_t shift)
.globl FUNC(vir_asm_shr)
.p2align 4
FUNC(vir_asm_shr):
    mov     rax, rdi
    mov     rcx, rsi
    sar     rax, cl         ; arithmetic shift right (preserve sign)
    ret

; ═══════════════════════════════════════════════════════
; 3. Comparisons (return 1/0)
; ═══════════════════════════════════════════════════════

; int64_t vir_asm_cmp_eq(int64_t a, int64_t b)
.globl FUNC(vir_asm_cmp_eq)
.p2align 4
FUNC(vir_asm_cmp_eq):
    xor     eax, eax
    cmp     rdi, rsi
    sete    al
    ret

; int64_t vir_asm_cmp_gt(int64_t a, int64_t b)
.globl FUNC(vir_asm_cmp_gt)
.p2align 4
FUNC(vir_asm_cmp_gt):
    xor     eax, eax
    cmp     rdi, rsi
    setg    al
    ret

; int64_t vir_asm_cmp_lt(int64_t a, int64_t b)
.globl FUNC(vir_asm_cmp_lt)
.p2align 4
FUNC(vir_asm_cmp_lt):
    xor     eax, eax
    cmp     rdi, rsi
    setl    al
    ret

; int64_t vir_asm_cmp_ge(int64_t a, int64_t b)
.globl FUNC(vir_asm_cmp_ge)
.p2align 4
FUNC(vir_asm_cmp_ge):
    xor     eax, eax
    cmp     rdi, rsi
    setge   al
    ret

; int64_t vir_asm_cmp_le(int64_t a, int64_t b)
.globl FUNC(vir_asm_cmp_le)
.p2align 4
FUNC(vir_asm_cmp_le):
    xor     eax, eax
    cmp     rdi, rsi
    setle   al
    ret

; ═══════════════════════════════════════════════════════
; 4. Jump Table Trampoline
; ═══════════════════════════════════════════════════════
;
; Spec §3.2.3 – Each PATCH_POINT compiles to a JMP [table+idx*8]
; This trampoline loads the target address from a table and jumps.
;
; void vir_asm_jump_table_dispatch(void **table, uint64_t index)
;   table → rdi, index → rsi

.globl FUNC(vir_asm_jump_table_dispatch)
.p2align 4
FUNC(vir_asm_jump_table_dispatch):
    mov     rax, [rdi + rsi*8]  ; load target fn pointer
    jmp     rax                  ; tail-call dispatch

; ═══════════════════════════════════════════════════════
; 5. Binary Patch Routine
; ═══════════════════════════════════════════════════════
;
; void vir_asm_patch_jmp(void *jmp_site, void *new_target)
;   Patch a JMP rel32 instruction at jmp_site to point to new_target.
;   jmp_site → rdi (points at the E9 opcode byte)
;   new_target → rsi
;
; The JMP rel32 is: E9 [32-bit offset]
; offset = new_target - (jmp_site + 5)

.globl FUNC(vir_asm_patch_jmp)
.p2align 4
FUNC(vir_asm_patch_jmp):
    lea     rax, [rdi + 5]      ; address after the JMP instruction
    sub     rsi, rax             ; offset = new_target - (jmp_site + 5)
    mov     [rdi + 1], esi       ; write 32-bit offset (little-endian)
    ; Memory barrier for cross-core visibility
    mfence
    ret

; ═══════════════════════════════════════════════════════
; 6. Memory Copy (for code injection)
; ═══════════════════════════════════════════════════════
;
; void vir_asm_memcpy64(void *dst, const void *src, uint64_t n_bytes)
;   Fast copy using REP MOVSB (modern CPUs have ERMS)

.globl FUNC(vir_asm_memcpy64)
.p2align 4
FUNC(vir_asm_memcpy64):
    ; rdi = dst (already correct for MOVSB)
    ; rsi = src (already correct for MOVSB)
    mov     rcx, rdx            ; count
    rep     movsb
    ret

; ═══════════════════════════════════════════════════════
; 7. Register Spill/Restore for Context Switch
; ═══════════════════════════════════════════════════════
;
; void vir_asm_save_regs(int64_t *save_area)
;   Save all callee-saved registers + important state.
;   save_area → rdi (must have space for 8 * 8 = 64 bytes)

.globl FUNC(vir_asm_save_regs)
.p2align 4
FUNC(vir_asm_save_regs):
    mov     [rdi +  0], rbx
    mov     [rdi +  8], rbp
    mov     [rdi + 16], r12
    mov     [rdi + 24], r13
    mov     [rdi + 32], r14
    mov     [rdi + 40], r15
    mov     [rdi + 48], rsp
    ; Save flags
    pushfq
    pop     rax
    mov     [rdi + 56], rax
    ret

; void vir_asm_restore_regs(const int64_t *save_area)
.globl FUNC(vir_asm_restore_regs)
.p2align 4
FUNC(vir_asm_restore_regs):
    mov     rbx, [rdi +  0]
    mov     rbp, [rdi +  8]
    mov     r12, [rdi + 16]
    mov     r13, [rdi + 24]
    mov     r14, [rdi + 32]
    mov     r15, [rdi + 40]
    mov     rsp, [rdi + 48]
    ; Restore flags
    push    qword ptr [rdi + 56]
    popfq
    ret

; ═══════════════════════════════════════════════════════
; 8. CPU Feature Detection (CPUID)
; ═══════════════════════════════════════════════════════
;
; uint64_t vir_asm_cpuid_features(void)
;   Returns ECX:EDX feature bits from CPUID leaf 1.
;   Return: (ECX << 32) | EDX

.globl FUNC(vir_asm_cpuid_features)
.p2align 4
FUNC(vir_asm_cpuid_features):
    push    rbx
    mov     eax, 1
    cpuid
    mov     eax, edx            ; EDX features (SSE, etc.)
    shl     rcx, 32             ; shift ECX to high 32 bits
    or      rax, rcx            ; combine
    pop     rbx
    ret

; ═══════════════════════════════════════════════════════
; 9. Atomic Compare-And-Swap (for lock-free patcher)
; ═══════════════════════════════════════════════════════
;
; int vir_asm_cas64(int64_t *ptr, int64_t expected, int64_t desired)
;   Returns 1 on success, 0 on failure.
;   ptr → rdi, expected → rsi, desired → rdx

.globl FUNC(vir_asm_cas64)
.p2align 4
FUNC(vir_asm_cas64):
    mov     rax, rsi            ; expected value into RAX
    lock cmpxchg [rdi], rdx    ; atomic CAS
    sete    al
    movzx   eax, al
    ret

; ═══════════════════════════════════════════════════════
; 10. Fast VM Register Access (64-bit array operations)
; ═══════════════════════════════════════════════════════
;
; int64_t vir_asm_reg_read(const int64_t *regs, uint32_t idx)
.globl FUNC(vir_asm_reg_read)
.p2align 4
FUNC(vir_asm_reg_read):
    mov     eax, esi
    mov     rax, [rdi + rax*8]
    ret

; void vir_asm_reg_write(int64_t *regs, uint32_t idx, int64_t val)
.globl FUNC(vir_asm_reg_write)
.p2align 4
FUNC(vir_asm_reg_write):
    mov     eax, esi
    mov     [rdi + rax*8], rdx
    ret

/*
 * codegen.h – Machine Code Generator
 * ===================================
 * Spec §3.2 – Tạo 2 biến thể (multi-versioning):
 *   Bản A (Safe):  Stack-based
 *   Bản B (Fast):  Register-direct (native assembly)
 *
 * Hỗ trợ: x86_64, ARM64 (AArch64)
 */

#ifndef VIR_CODEGEN_H
#define VIR_CODEGEN_H

#include "q_ir.h"
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * Target Architecture
 * ═══════════════════════════════════════════════════════ */
typedef enum {
    ARCH_X86_64  = 0,
    ARCH_ARM64   = 1,
    ARCH_UNKNOWN = 99,
} target_arch_t;

target_arch_t codegen_detect_arch(void);

/* ═══════════════════════════════════════════════════════
 * Machine Code Buffer
 * ═══════════════════════════════════════════════════════ */
#define CODEBUF_INIT_CAP 256

typedef struct {
    uint8_t      *data;
    size_t        len;
    size_t        cap;
    target_arch_t arch;
} codebuf_t;

int    codebuf_init(codebuf_t *cb, target_arch_t arch);
int    codebuf_emit(codebuf_t *cb, const void *bytes, size_t n);
int    codebuf_emit_byte(codebuf_t *cb, uint8_t byte);
int    codebuf_emit_u32(codebuf_t *cb, uint32_t val);
int    codebuf_emit_u64(codebuf_t *cb, uint64_t val);
int    codebuf_emit_i32(codebuf_t *cb, int32_t val);
size_t codebuf_offset(const codebuf_t *cb);
void   codebuf_patch_i32(codebuf_t *cb, size_t offset, int32_t val);
void   codebuf_free(codebuf_t *cb);
void   codebuf_hexdump(const codebuf_t *cb, char *out, size_t out_size);

/* ═══════════════════════════════════════════════════════
 * Code Variant (§3.2 Multi-versioning)
 * ═══════════════════════════════════════════════════════ */
typedef struct {
    uint32_t  patch_id;
    codebuf_t safe_code;  /* Bản A – Stack-based (chậm, ổn định) */
    codebuf_t fast_code;  /* Bản B – Register-direct (thần tốc)  */
} code_variant_t;

#define MAX_VARIANTS 256

typedef struct {
    code_variant_t variants[MAX_VARIANTS];
    uint32_t       count;
    target_arch_t  arch;
} codegen_result_t;

/* ═══════════════════════════════════════════════════════
 * x86_64 Native Code Emission (implemented in ASM + C)
 * ═══════════════════════════════════════════════════════ */

/* Register encoding for x86_64 */
typedef enum {
    X86_RAX = 0, X86_RCX = 1, X86_RDX = 2, X86_RBX = 3,
    X86_RSP = 4, X86_RBP = 5, X86_RSI = 6, X86_RDI = 7,
    X86_R8  = 8, X86_R9  = 9, X86_R10 = 10, X86_R11 = 11,
    X86_R12 = 12, X86_R13 = 13, X86_R14 = 14, X86_R15 = 15,
} x86_reg_t;

/* x86_64 instruction emitters */
void x86_emit_add_rr(codebuf_t *cb, x86_reg_t dst, x86_reg_t src);
void x86_emit_sub_rr(codebuf_t *cb, x86_reg_t dst, x86_reg_t src);
void x86_emit_imul_rr(codebuf_t *cb, x86_reg_t dst, x86_reg_t src);
void x86_emit_mov_reg_imm64(codebuf_t *cb, x86_reg_t dst, int64_t imm);
void x86_emit_mov_reg_imm32(codebuf_t *cb, x86_reg_t dst, int32_t imm);
void x86_emit_mov_rr(codebuf_t *cb, x86_reg_t dst, x86_reg_t src);
void x86_emit_push(codebuf_t *cb, x86_reg_t reg);
void x86_emit_pop(codebuf_t *cb, x86_reg_t reg);
void x86_emit_ret(codebuf_t *cb);
void x86_emit_nop(codebuf_t *cb);
void x86_emit_jmp_rel32(codebuf_t *cb, int32_t offset);
void x86_emit_call_rel32(codebuf_t *cb, int32_t offset);
void x86_emit_cmp_rr(codebuf_t *cb, x86_reg_t a, x86_reg_t b);
void x86_emit_sete(codebuf_t *cb, x86_reg_t dst);
void x86_emit_setg(codebuf_t *cb, x86_reg_t dst);
void x86_emit_setl(codebuf_t *cb, x86_reg_t dst);
void x86_emit_je_rel32(codebuf_t *cb, int32_t offset);
void x86_emit_jne_rel32(codebuf_t *cb, int32_t offset);
void x86_emit_xor_rr(codebuf_t *cb, x86_reg_t dst, x86_reg_t src);
void x86_emit_idiv(codebuf_t *cb, x86_reg_t divisor);
void x86_emit_cqo(codebuf_t *cb);   /* sign extend RAX → RDX:RAX */
void x86_emit_syscall(codebuf_t *cb);

/* ═══════════════════════════════════════════════════════
 * ARM64 Native Code Emission (implemented in ASM + C)
 * ═══════════════════════════════════════════════════════ */

typedef enum {
    ARM_X0  = 0,  ARM_X1  = 1,  ARM_X2  = 2,  ARM_X3  = 3,
    ARM_X4  = 4,  ARM_X5  = 5,  ARM_X6  = 6,  ARM_X7  = 7,
    ARM_X8  = 8,  ARM_X9  = 9,  ARM_X10 = 10, ARM_X11 = 11,
    ARM_X12 = 12, ARM_X13 = 13, ARM_X14 = 14, ARM_X15 = 15,
    ARM_X16 = 16, ARM_X17 = 17, ARM_X18 = 18, ARM_X19 = 19,
    ARM_X20 = 20, ARM_X21 = 21, ARM_X22 = 22, ARM_X23 = 23,
    ARM_X24 = 24, ARM_X25 = 25, ARM_X26 = 26, ARM_X27 = 27,
    ARM_X28 = 28, ARM_FP  = 29, ARM_LR  = 30, ARM_SP  = 31,
} arm_reg_t;

void arm64_emit_add_rrr(codebuf_t *cb, arm_reg_t rd, arm_reg_t rn, arm_reg_t rm);
void arm64_emit_sub_rrr(codebuf_t *cb, arm_reg_t rd, arm_reg_t rn, arm_reg_t rm);
void arm64_emit_mul_rrr(codebuf_t *cb, arm_reg_t rd, arm_reg_t rn, arm_reg_t rm);
void arm64_emit_sdiv_rrr(codebuf_t *cb, arm_reg_t rd, arm_reg_t rn, arm_reg_t rm);
void arm64_emit_mov_imm16(codebuf_t *cb, arm_reg_t rd, uint16_t imm);
void arm64_emit_movz_imm64(codebuf_t *cb, arm_reg_t rd, int64_t imm);
void arm64_emit_mov_rr(codebuf_t *cb, arm_reg_t rd, arm_reg_t rm);
void arm64_emit_cmp_rr(codebuf_t *cb, arm_reg_t rn, arm_reg_t rm);
void arm64_emit_cset_eq(codebuf_t *cb, arm_reg_t rd);
void arm64_emit_cset_gt(codebuf_t *cb, arm_reg_t rd);
void arm64_emit_cset_lt(codebuf_t *cb, arm_reg_t rd);
void arm64_emit_b_imm26(codebuf_t *cb, int32_t offset);
void arm64_emit_beq_imm19(codebuf_t *cb, int32_t offset);
void arm64_emit_bne_imm19(codebuf_t *cb, int32_t offset);
void arm64_emit_bl_imm26(codebuf_t *cb, int32_t offset);
void arm64_emit_ret(codebuf_t *cb);
void arm64_emit_nop(codebuf_t *cb);
void arm64_emit_stp_pre(codebuf_t *cb, arm_reg_t rt, arm_reg_t rt2, arm_reg_t rn, int imm);
void arm64_emit_ldp_post(codebuf_t *cb, arm_reg_t rt, arm_reg_t rt2, arm_reg_t rn, int imm);
void arm64_emit_str_pre(codebuf_t *cb, arm_reg_t rt, arm_reg_t rn, int imm);
void arm64_emit_ldr_post(codebuf_t *cb, arm_reg_t rt, arm_reg_t rn, int imm);
void arm64_emit_svc(codebuf_t *cb, uint16_t imm);

/* ═══════════════════════════════════════════════════════
 * High-level Code Generator
 * ═══════════════════════════════════════════════════════ */

int codegen_init(codegen_result_t *result, target_arch_t arch);
int codegen_generate(codegen_result_t *result, const q_module_t *mod);
int codegen_emit_safe(codebuf_t *cb, const q_instruction_t *instrs, uint32_t count, target_arch_t arch, void *print_addr);
int codegen_emit_fast(codebuf_t *cb, const q_instruction_t *instrs, uint32_t count, target_arch_t arch, void *print_addr);
void codegen_free(codegen_result_t *result);

/* ═══════════════════════════════════════════════════════
 * Full Code Generator with Label Resolution
 * ═══════════════════════════════════════════════════════
 * Handles control flow (JUMP/JUMP_IF/JUMP_IF_NOT),
 * comparisons, function calls, and PRINT/INPUT intrinsics
 * with proper back-patching for branch offsets.
 *
 * `print_addr` is the resolved address of vir_builtin_print_i64.
 * Pass NULL to emit NOP for PRINT instead.
 */

int codegen_emit_full(codebuf_t *cb, const q_instruction_t *instrs,
                      uint32_t count, target_arch_t arch,
                      void *print_addr);

/* ═══════════════════════════════════════════════════════
 * Phase 1: Full Codegen with Runtime Context
 * ═══════════════════════════════════════════════════════
 * codegen_emit_full2 handles ALL Q-IR opcodes including:
 *   - Bitwise (AND, OR, XOR, SHL, SHR)
 *   - Memory (STORE, LOAD_BYTE/WORD, STORE_BYTE/WORD)
 *   - Globals (LOAD_GLOBAL, STORE_GLOBAL)
 *   - String (STR_LEN, STR_GET, STR_CAT, STR_EQ)
 *   - File I/O (FILE_OPEN/READ/WRITE/CLOSE/WRITE_BYTE)
 *   - Array (ARR_NEW/LEN/GET/SET/PUSH)
 *   - System (EXIT, I_TO_STR, STR_TO_I, PRINT_STR,
 *             GET_ARG, ARG_COUNT, CALL_FUNC)
 *
 * `rt` provides function pointers for all intrinsics.
 * Use codegen_rt_init() to populate from the intrinsic table.
 */

#define CG_RT_MAX_FUNCS 8192

typedef struct {
    /* Intrinsic function addresses (indexed by intrinsic_id_t) */
    void *intrinsic_addrs[32];

    /* Global variables storage (passed to JIT code) */
    int64_t *globals;
    uint32_t global_cap;

    /* Program arguments */
    const char **args;
    int          arg_count;

    /* Module (for CALL_FUNC resolution) */
    const q_module_t *module;

    /* Function entry points (filled by codegen for CALL_FUNC) */
    size_t func_offsets[CG_RT_MAX_FUNCS];
    uint32_t func_count;

    /* Patches for Q_CALL_FUNC */
    size_t call_patch_offsets[65536];
    uint32_t call_target_funcs[65536];
    uint32_t call_patch_count;
} codegen_rt_t;

/* Initialize runtime from intrinsic table */
void codegen_rt_init(codegen_rt_t *rt);

/* Full code generator with runtime context */
int codegen_emit_full2(codebuf_t *cb, const q_instruction_t *instrs,
                       uint32_t count, target_arch_t arch,
                       const codegen_rt_t *rt);

/* §15.3 WASM target — compile Q-IR module to WebAssembly MVP binary.
 * Allocates *out_buf (caller must free) and sets *out_len.
 * Returns 0 on success, nonzero on error. */
int codegen_emit_wasm(const q_module_t *module,
                      uint8_t **out_buf, size_t *out_len);

#ifdef __cplusplus
}
#endif

#endif /* VIR_CODEGEN_H */

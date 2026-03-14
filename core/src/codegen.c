/*
 * codegen.c – Machine Code Generator (C + inline assembly references)
 * ====================================================================
 * Spec §3.2 – Multi-versioning code generation.
 * 
 * This file implements the codebuf utilities and high-level codegen.
 * Architecture-specific emitters call into x86_64 / arm64 modules.
 */

#include "codegen.h"
#include "intrinsics.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ═══════════════════════════════════════════════════════
 * Architecture Detection
 * ═══════════════════════════════════════════════════════ */

target_arch_t codegen_detect_arch(void)
{
#if defined(__x86_64__) || defined(_M_X64)
    return ARCH_X86_64;
#elif defined(__aarch64__) || defined(_M_ARM64)
    return ARCH_ARM64;
#else
    return ARCH_UNKNOWN;
#endif
}

/* ═══════════════════════════════════════════════════════
 * Code Buffer
 * ═══════════════════════════════════════════════════════ */

int codebuf_init(codebuf_t *cb, target_arch_t arch)
{
    cb->data = (uint8_t *)malloc(CODEBUF_INIT_CAP);
    if (!cb->data) return -1;
    cb->len  = 0;
    cb->cap  = CODEBUF_INIT_CAP;
    cb->arch = arch;
    return 0;
}

static int codebuf_ensure(codebuf_t *cb, size_t need)
{
    if (cb->len + need <= cb->cap) return 0;
    size_t new_cap = cb->cap * 2;
    while (new_cap < cb->len + need) new_cap *= 2;
    uint8_t *new_data = (uint8_t *)realloc(cb->data, new_cap);
    if (!new_data) return -1;
    cb->data = new_data;
    cb->cap  = new_cap;
    return 0;
}

int codebuf_emit(codebuf_t *cb, const void *bytes, size_t n)
{
    if (codebuf_ensure(cb, n) != 0) return -1;
    memcpy(cb->data + cb->len, bytes, n);
    cb->len += n;
    return 0;
}

int codebuf_emit_byte(codebuf_t *cb, uint8_t byte)
{
    return codebuf_emit(cb, &byte, 1);
}

int codebuf_emit_u32(codebuf_t *cb, uint32_t val)
{
    return codebuf_emit(cb, &val, 4);
}

int codebuf_emit_u64(codebuf_t *cb, uint64_t val)
{
    return codebuf_emit(cb, &val, 8);
}

int codebuf_emit_i32(codebuf_t *cb, int32_t val)
{
    return codebuf_emit(cb, &val, 4);
}

size_t codebuf_offset(const codebuf_t *cb)
{
    return cb->len;
}

void codebuf_patch_i32(codebuf_t *cb, size_t offset, int32_t val)
{
    if (offset + 4 <= cb->len) {
        memcpy(cb->data + offset, &val, 4);
    }
}

void codebuf_free(codebuf_t *cb)
{
    if (cb->data) {
        free(cb->data);
        cb->data = NULL;
    }
    cb->len = 0;
    cb->cap = 0;
}

void codebuf_hexdump(const codebuf_t *cb, char *out, size_t out_size)
{
    size_t pos = 0;
    for (size_t i = 0; i < cb->len && pos + 3 < out_size; i++) {
        pos += snprintf(out + pos, out_size - pos, "%02X ", cb->data[i]);
    }
    if (pos > 0) out[pos - 1] = '\0';  /* trim trailing space */
}

/* ═══════════════════════════════════════════════════════
 * x86_64 Instruction Emitters
 * ═══════════════════════════════════════════════════════
 * Mã máy thực – hand-coded byte sequences.
 */

/* REX prefix cho 64-bit operations */
static inline uint8_t rex_w(x86_reg_t r, x86_reg_t rm)
{
    uint8_t rex = 0x48;
    if (r  >= X86_R8) rex |= 0x04;  /* REX.R */
    if (rm >= X86_R8) rex |= 0x01;  /* REX.B */
    return rex;
}

static inline uint8_t modrm(uint8_t mod, uint8_t reg, uint8_t rm)
{
    return (mod << 6) | ((reg & 7) << 3) | (rm & 7);
}

void x86_emit_add_rr(codebuf_t *cb, x86_reg_t dst, x86_reg_t src)
{
    /* ADD dst, src → REX.W 01 /r (src→dst) */
    codebuf_emit_byte(cb, rex_w(src, dst));
    codebuf_emit_byte(cb, 0x01);
    codebuf_emit_byte(cb, modrm(0x03, src, dst));
}

void x86_emit_sub_rr(codebuf_t *cb, x86_reg_t dst, x86_reg_t src)
{
    /* SUB dst, src → REX.W 29 /r */
    codebuf_emit_byte(cb, rex_w(src, dst));
    codebuf_emit_byte(cb, 0x29);
    codebuf_emit_byte(cb, modrm(0x03, src, dst));
}

void x86_emit_imul_rr(codebuf_t *cb, x86_reg_t dst, x86_reg_t src)
{
    /* IMUL dst, src → REX.W 0F AF /r */
    codebuf_emit_byte(cb, rex_w(dst, src));
    codebuf_emit_byte(cb, 0x0F);
    codebuf_emit_byte(cb, 0xAF);
    codebuf_emit_byte(cb, modrm(0x03, dst, src));
}

void x86_emit_mov_reg_imm64(codebuf_t *cb, x86_reg_t dst, int64_t imm)
{
    /* MOV dst, imm64 → REX.W B8+rd [8 bytes] */
    uint8_t rex = 0x48;
    if (dst >= X86_R8) rex |= 0x01;
    codebuf_emit_byte(cb, rex);
    codebuf_emit_byte(cb, 0xB8 + (dst & 7));
    codebuf_emit_u64(cb, (uint64_t)imm);
}

void x86_emit_mov_reg_imm32(codebuf_t *cb, x86_reg_t dst, int32_t imm)
{
    /* MOV dst, imm32 → REX.W C7 /0 [4 bytes] */
    uint8_t rex = 0x48;
    if (dst >= X86_R8) rex |= 0x01;
    codebuf_emit_byte(cb, rex);
    codebuf_emit_byte(cb, 0xC7);
    codebuf_emit_byte(cb, modrm(0x03, 0, dst));
    codebuf_emit_i32(cb, imm);
}

void x86_emit_mov_rr(codebuf_t *cb, x86_reg_t dst, x86_reg_t src)
{
    /* MOV dst, src → REX.W 89 /r */
    codebuf_emit_byte(cb, rex_w(src, dst));
    codebuf_emit_byte(cb, 0x89);
    codebuf_emit_byte(cb, modrm(0x03, src, dst));
}

void x86_emit_push(codebuf_t *cb, x86_reg_t reg)
{
    if (reg >= X86_R8) codebuf_emit_byte(cb, 0x41);
    codebuf_emit_byte(cb, 0x50 + (reg & 7));
}

void x86_emit_pop(codebuf_t *cb, x86_reg_t reg)
{
    if (reg >= X86_R8) codebuf_emit_byte(cb, 0x41);
    codebuf_emit_byte(cb, 0x58 + (reg & 7));
}

void x86_emit_ret(codebuf_t *cb)
{
    codebuf_emit_byte(cb, 0xC3);
}

void x86_emit_nop(codebuf_t *cb)
{
    codebuf_emit_byte(cb, 0x90);
}

void x86_emit_jmp_rel32(codebuf_t *cb, int32_t offset)
{
    codebuf_emit_byte(cb, 0xE9);
    codebuf_emit_i32(cb, offset);
}

void x86_emit_call_rel32(codebuf_t *cb, int32_t offset)
{
    codebuf_emit_byte(cb, 0xE8);
    codebuf_emit_i32(cb, offset);
}

void x86_emit_cmp_rr(codebuf_t *cb, x86_reg_t a, x86_reg_t b)
{
    /* CMP a, b → REX.W 39 /r */
    codebuf_emit_byte(cb, rex_w(b, a));
    codebuf_emit_byte(cb, 0x39);
    codebuf_emit_byte(cb, modrm(0x03, b, a));
}

void x86_emit_sete(codebuf_t *cb, x86_reg_t dst)
{
    /* SETE dst → 0F 94 /r */
    if (dst >= X86_R8) codebuf_emit_byte(cb, 0x41);
    codebuf_emit_byte(cb, 0x0F);
    codebuf_emit_byte(cb, 0x94);
    codebuf_emit_byte(cb, modrm(0x03, 0, dst));
}

void x86_emit_setg(codebuf_t *cb, x86_reg_t dst)
{
    if (dst >= X86_R8) codebuf_emit_byte(cb, 0x41);
    codebuf_emit_byte(cb, 0x0F);
    codebuf_emit_byte(cb, 0x9F);
    codebuf_emit_byte(cb, modrm(0x03, 0, dst));
}

void x86_emit_setl(codebuf_t *cb, x86_reg_t dst)
{
    if (dst >= X86_R8) codebuf_emit_byte(cb, 0x41);
    codebuf_emit_byte(cb, 0x0F);
    codebuf_emit_byte(cb, 0x9C);
    codebuf_emit_byte(cb, modrm(0x03, 0, dst));
}

void x86_emit_je_rel32(codebuf_t *cb, int32_t offset)
{
    codebuf_emit_byte(cb, 0x0F);
    codebuf_emit_byte(cb, 0x84);
    codebuf_emit_i32(cb, offset);
}

void x86_emit_jne_rel32(codebuf_t *cb, int32_t offset)
{
    codebuf_emit_byte(cb, 0x0F);
    codebuf_emit_byte(cb, 0x85);
    codebuf_emit_i32(cb, offset);
}

void x86_emit_xor_rr(codebuf_t *cb, x86_reg_t dst, x86_reg_t src)
{
    codebuf_emit_byte(cb, rex_w(src, dst));
    codebuf_emit_byte(cb, 0x31);
    codebuf_emit_byte(cb, modrm(0x03, src, dst));
}

void x86_emit_idiv(codebuf_t *cb, x86_reg_t divisor)
{
    /* IDIV divisor → REX.W F7 /7 */
    uint8_t rex = 0x48;
    if (divisor >= X86_R8) rex |= 0x01;
    codebuf_emit_byte(cb, rex);
    codebuf_emit_byte(cb, 0xF7);
    codebuf_emit_byte(cb, modrm(0x03, 7, divisor));
}

void x86_emit_cqo(codebuf_t *cb)
{
    /* CQO → 48 99 */
    codebuf_emit_byte(cb, 0x48);
    codebuf_emit_byte(cb, 0x99);
}

void x86_emit_syscall(codebuf_t *cb)
{
    codebuf_emit_byte(cb, 0x0F);
    codebuf_emit_byte(cb, 0x05);
}

/* ═══════════════════════════════════════════════════════
 * ARM64 Instruction Emitters
 * ═══════════════════════════════════════════════════════
 * Mã máy thực ARM64 – 32-bit fixed-width instructions.
 */

void arm64_emit_add_rrr(codebuf_t *cb, arm_reg_t rd, arm_reg_t rn, arm_reg_t rm)
{
    /* ADD Xd, Xn, Xm → 1000_1011_000 Rm 000000 Rn Rd */
    uint32_t instr = 0x8B000000 | ((rm & 0x1F) << 16) | ((rn & 0x1F) << 5) | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);
}

void arm64_emit_sub_rrr(codebuf_t *cb, arm_reg_t rd, arm_reg_t rn, arm_reg_t rm)
{
    /* SUB Xd, Xn, Xm → 1100_1011_000 Rm 000000 Rn Rd */
    uint32_t instr = 0xCB000000 | ((rm & 0x1F) << 16) | ((rn & 0x1F) << 5) | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);
}

void arm64_emit_mul_rrr(codebuf_t *cb, arm_reg_t rd, arm_reg_t rn, arm_reg_t rm)
{
    /* MUL Xd, Xn, Xm → MADD Xd, Xn, Xm, XZR → 1001_1011_000 Rm 0 11111 Rn Rd */
    uint32_t instr = 0x9B007C00 | ((rm & 0x1F) << 16) | ((rn & 0x1F) << 5) | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);
}

void arm64_emit_sdiv_rrr(codebuf_t *cb, arm_reg_t rd, arm_reg_t rn, arm_reg_t rm)
{
    /* SDIV Xd, Xn, Xm → 1001_1010_1100_0000 Rm 00001 1 Rn Rd */
    uint32_t instr = 0x9AC00C00 | ((rm & 0x1F) << 16) | ((rn & 0x1F) << 5) | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);
}

void arm64_emit_mov_imm16(codebuf_t *cb, arm_reg_t rd, uint16_t imm)
{
    /* MOVZ Xd, #imm16 → 1101_0010_100 imm16 Rd */
    uint32_t instr = 0xD2800000 | ((uint32_t)imm << 5) | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);
}

void arm64_emit_movz_imm64(codebuf_t *cb, arm_reg_t rd, int64_t imm)
{
    /* Full 64-bit load: MOVZ + up to 3 MOVK */
    uint64_t uimm = (uint64_t)imm;

    /* MOVZ Xd, #imm16, LSL #0 */
    uint32_t instr = 0xD2800000 | (((uint32_t)(uimm & 0xFFFF)) << 5) | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);

    /* MOVK for bits [31:16] */
    if (uimm >> 16) {
        instr = 0xF2A00000 | (((uint32_t)((uimm >> 16) & 0xFFFF)) << 5) | (rd & 0x1F);
        codebuf_emit_u32(cb, instr);
    }
    /* MOVK for bits [47:32] */
    if (uimm >> 32) {
        instr = 0xF2C00000 | (((uint32_t)((uimm >> 32) & 0xFFFF)) << 5) | (rd & 0x1F);
        codebuf_emit_u32(cb, instr);
    }
    /* MOVK for bits [63:48] */
    if (uimm >> 48) {
        instr = 0xF2E00000 | (((uint32_t)((uimm >> 48) & 0xFFFF)) << 5) | (rd & 0x1F);
        codebuf_emit_u32(cb, instr);
    }
}

void arm64_emit_mov_rr(codebuf_t *cb, arm_reg_t rd, arm_reg_t rm)
{
    /* MOV Xd, Xm = ORR Xd, XZR, Xm */
    uint32_t instr = 0xAA0003E0 | ((rm & 0x1F) << 16) | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);
}

void arm64_emit_cmp_rr(codebuf_t *cb, arm_reg_t rn, arm_reg_t rm)
{
    /* CMP Xn, Xm = SUBS XZR, Xn, Xm */
    uint32_t instr = 0xEB00001F | ((rm & 0x1F) << 16) | ((rn & 0x1F) << 5);
    codebuf_emit_u32(cb, instr);
}

void arm64_emit_cset_eq(codebuf_t *cb, arm_reg_t rd)
{
    /* CSET Xd, EQ = CSINC Xd, XZR, XZR, NE(1) */
    uint32_t instr = 0x9A9F17E0 | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);
}

void arm64_emit_cset_gt(codebuf_t *cb, arm_reg_t rd)
{
    /* CSET Xd, GT = CSINC Xd, XZR, XZR, LE(0xD) */
    uint32_t instr = 0x9A9FD7E0 | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);
}

void arm64_emit_cset_lt(codebuf_t *cb, arm_reg_t rd)
{
    /* CSET Xd, LT = CSINC Xd, XZR, XZR, GE(0xA) */
    uint32_t instr = 0x9A9FA7E0 | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);
}

void arm64_emit_b_imm26(codebuf_t *cb, int32_t offset)
{
    /* B offset → 0001_01 imm26 */
    uint32_t imm26 = ((uint32_t)(offset >> 2)) & 0x03FFFFFF;
    codebuf_emit_u32(cb, 0x14000000 | imm26);
}

void arm64_emit_beq_imm19(codebuf_t *cb, int32_t offset)
{
    /* B.EQ offset → 0101_0100 imm19 0 0000 */
    uint32_t imm19 = ((uint32_t)(offset >> 2)) & 0x7FFFF;
    codebuf_emit_u32(cb, 0x54000000 | (imm19 << 5));
}

void arm64_emit_bne_imm19(codebuf_t *cb, int32_t offset)
{
    /* B.NE offset → 0101_0100 imm19 0 0001 */
    uint32_t imm19 = ((uint32_t)(offset >> 2)) & 0x7FFFF;
    codebuf_emit_u32(cb, 0x54000001 | (imm19 << 5));
}

void arm64_emit_bl_imm26(codebuf_t *cb, int32_t offset)
{
    uint32_t imm26 = ((uint32_t)(offset >> 2)) & 0x03FFFFFF;
    codebuf_emit_u32(cb, 0x94000000 | imm26);
}

void arm64_emit_ret(codebuf_t *cb)
{
    /* RET (X30) → D65F03C0 */
    codebuf_emit_u32(cb, 0xD65F03C0);
}

void arm64_emit_nop(codebuf_t *cb)
{
    codebuf_emit_u32(cb, 0xD503201F);
}

void arm64_emit_stp_pre(codebuf_t *cb, arm_reg_t rt, arm_reg_t rt2,
                        arm_reg_t rn, int imm)
{
    /* STP Xt, Xt2, [Xn, #imm]! → pre-index */
    int32_t simm7 = (imm / 8) & 0x7F;
    uint32_t instr = 0xA9800000 | ((uint32_t)simm7 << 15) |
                     ((rt2 & 0x1F) << 10) | ((rn & 0x1F) << 5) | (rt & 0x1F);
    codebuf_emit_u32(cb, instr);
}

void arm64_emit_ldp_post(codebuf_t *cb, arm_reg_t rt, arm_reg_t rt2,
                         arm_reg_t rn, int imm)
{
    /* LDP Xt, Xt2, [Xn], #imm → post-index */
    int32_t simm7 = (imm / 8) & 0x7F;
    uint32_t instr = 0xA8C00000 | ((uint32_t)simm7 << 15) |
                     ((rt2 & 0x1F) << 10) | ((rn & 0x1F) << 5) | (rt & 0x1F);
    codebuf_emit_u32(cb, instr);
}

void arm64_emit_str_pre(codebuf_t *cb, arm_reg_t rt, arm_reg_t rn, int imm)
{
    /* STR Xt, [Xn, #imm]! */
    int32_t simm9 = imm & 0x1FF;
    uint32_t instr = 0xF8000C00 | ((uint32_t)simm9 << 12) |
                     ((rn & 0x1F) << 5) | (rt & 0x1F);
    codebuf_emit_u32(cb, instr);
}

void arm64_emit_ldr_post(codebuf_t *cb, arm_reg_t rt, arm_reg_t rn, int imm)
{
    /* LDR Xt, [Xn], #imm */
    int32_t simm9 = imm & 0x1FF;
    uint32_t instr = 0xF8400400 | ((uint32_t)simm9 << 12) |
                     ((rn & 0x1F) << 5) | (rt & 0x1F);
    codebuf_emit_u32(cb, instr);
}

void arm64_emit_svc(codebuf_t *cb, uint16_t imm)
{
    /* SVC #imm16 */
    codebuf_emit_u32(cb, 0xD4000001 | ((uint32_t)imm << 5));
}

/* ═══════════════════════════════════════════════════════
 * High-Level Code Generator
 * ═══════════════════════════════════════════════════════ */

int codegen_init(codegen_result_t *result, target_arch_t arch)
{
    memset(result, 0, sizeof(*result));
    result->arch = arch;
    return 0;
}

/* Virtual register → physical register mapping (simplified) */
static x86_reg_t vreg_to_x86(uint32_t vreg)
{
    /* Map virtual regs to caller-saved GPRs: RAX, RCX, RDX, RSI, RDI, R8-R11 */
    static const x86_reg_t map[] = {
        X86_RAX, X86_RCX, X86_RDX, X86_RSI, X86_RDI,
        X86_R8,  X86_R9,  X86_R10, X86_R11, X86_RBX,
        X86_R12, X86_R13, X86_R14, X86_R15
    };
    if (vreg < sizeof(map)/sizeof(map[0])) return map[vreg];
    return X86_RAX;  /* spill to RAX */
}

static arm_reg_t vreg_to_arm(uint32_t vreg)
{
    /* Map virtual regs to X0-X15 (caller-saved) */
    if (vreg < 16) return (arm_reg_t)vreg;
    return ARM_X0;
}

/* ── Back-patching infrastructure (used by safe, fast, full) ── */
#define CG_MAX_LABELS 1024
#define CG_MAX_FIXUPS 4096
typedef struct { uint32_t label_id; size_t offset; } cg_label_t;
typedef struct { size_t patch_offset; uint32_t target_label; int is_cond; } cg_fixup_t;

/* ── Safe code (Bản A): Stack-based ────────────────────── */
int codegen_emit_safe(codebuf_t *cb, const q_instruction_t *instrs,
                      uint32_t count, target_arch_t arch,
                      void *print_addr)
{
    cg_label_t labels[CG_MAX_LABELS];
    cg_fixup_t fixups[CG_MAX_FIXUPS];
    uint32_t label_count = 0;
    uint32_t fixup_count = 0;

    for (uint32_t i = 0; i < count; i++) {
        const q_instruction_t *instr = &instrs[i];

        if (arch == ARCH_X86_64) {
            switch (instr->opcode) {
            case Q_LOAD:
                if (instr->src1.type == OPERAND_IMM) {
                    x86_emit_mov_reg_imm64(cb, X86_RAX, instr->src1.imm);
                    x86_emit_push(cb, X86_RAX);
                }
                break;
            case Q_STORE:
            case Q_MOVE:
                /* Pop from src, push to dest (re-push for stack machine) */
                x86_emit_nop(cb);
                break;
            case Q_ADD:
                x86_emit_pop(cb, X86_RBX);
                x86_emit_pop(cb, X86_RAX);
                x86_emit_add_rr(cb, X86_RAX, X86_RBX);
                x86_emit_push(cb, X86_RAX);
                break;
            case Q_SUB:
                x86_emit_pop(cb, X86_RBX);
                x86_emit_pop(cb, X86_RAX);
                x86_emit_sub_rr(cb, X86_RAX, X86_RBX);
                x86_emit_push(cb, X86_RAX);
                break;
            case Q_MUL:
                x86_emit_pop(cb, X86_RBX);
                x86_emit_pop(cb, X86_RAX);
                x86_emit_imul_rr(cb, X86_RAX, X86_RBX);
                x86_emit_push(cb, X86_RAX);
                break;
            case Q_DIV:
                x86_emit_pop(cb, X86_RCX);
                x86_emit_pop(cb, X86_RAX);
                x86_emit_cqo(cb);
                x86_emit_idiv(cb, X86_RCX);
                x86_emit_push(cb, X86_RAX);
                break;
            case Q_MOD:
                x86_emit_pop(cb, X86_RCX);
                x86_emit_pop(cb, X86_RAX);
                x86_emit_cqo(cb);
                x86_emit_idiv(cb, X86_RCX);
                x86_emit_push(cb, X86_RDX);  /* remainder */
                break;
            case Q_CMP_EQ:
                x86_emit_pop(cb, X86_RBX);
                x86_emit_pop(cb, X86_RAX);
                x86_emit_cmp_rr(cb, X86_RAX, X86_RBX);
                x86_emit_xor_rr(cb, X86_RAX, X86_RAX);
                x86_emit_sete(cb, X86_RAX);
                x86_emit_push(cb, X86_RAX);
                break;
            case Q_CMP_GT:
                x86_emit_pop(cb, X86_RBX);
                x86_emit_pop(cb, X86_RAX);
                x86_emit_cmp_rr(cb, X86_RAX, X86_RBX);
                x86_emit_xor_rr(cb, X86_RAX, X86_RAX);
                x86_emit_setg(cb, X86_RAX);
                x86_emit_push(cb, X86_RAX);
                break;
            case Q_CMP_LT:
                x86_emit_pop(cb, X86_RBX);
                x86_emit_pop(cb, X86_RAX);
                x86_emit_cmp_rr(cb, X86_RAX, X86_RBX);
                x86_emit_xor_rr(cb, X86_RAX, X86_RAX);
                x86_emit_setl(cb, X86_RAX);
                x86_emit_push(cb, X86_RAX);
                break;
            case Q_LABEL:
                if (label_count < CG_MAX_LABELS) {
                    labels[label_count].label_id = instr->patch_id;
                    labels[label_count].offset   = cb->len;
                    label_count++;
                }
                break;
            case Q_JUMP:
                if (instr->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len + 1;
                    fixups[fixup_count].target_label = instr->src1.label;
                    fixups[fixup_count].is_cond      = 0;
                    fixup_count++;
                }
                x86_emit_jmp_rel32(cb, 0);
                break;
            case Q_JUMP_IF:
                x86_emit_pop(cb, X86_RAX);
                /* TEST RAX, RAX */
                codebuf_emit_byte(cb, 0x48); codebuf_emit_byte(cb, 0x85);
                codebuf_emit_byte(cb, 0xC0);
                if (instr->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len + 2;
                    fixups[fixup_count].target_label = instr->src2.label;
                    fixups[fixup_count].is_cond      = 1;
                    fixup_count++;
                }
                x86_emit_jne_rel32(cb, 0);
                break;
            case Q_JUMP_IF_NOT:
                x86_emit_pop(cb, X86_RAX);
                codebuf_emit_byte(cb, 0x48); codebuf_emit_byte(cb, 0x85);
                codebuf_emit_byte(cb, 0xC0);
                if (instr->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len + 2;
                    fixups[fixup_count].target_label = instr->src2.label;
                    fixups[fixup_count].is_cond      = 1;
                    fixup_count++;
                }
                x86_emit_je_rel32(cb, 0);
                break;
            case Q_CALL:
                if (instr->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len + 1;
                    fixups[fixup_count].target_label = instr->src1.label;
                    fixups[fixup_count].is_cond      = 0;
                    fixup_count++;
                }
                x86_emit_call_rel32(cb, 0);
                break;
            case Q_PRINT:
                if (print_addr) {
                    x86_emit_push(cb, X86_RDI);
                    x86_emit_pop(cb, X86_RDI);  /* value already on stack → RDI */
                    /* Align stack: SUB RSP, 8 */
                    codebuf_emit_byte(cb, 0x48); codebuf_emit_byte(cb, 0x83);
                    codebuf_emit_byte(cb, 0xEC); codebuf_emit_byte(cb, 0x08);
                    x86_emit_mov_reg_imm64(cb, X86_RAX, (int64_t)(uintptr_t)print_addr);
                    codebuf_emit_byte(cb, 0xFF); codebuf_emit_byte(cb, 0xD0);
                    codebuf_emit_byte(cb, 0x48); codebuf_emit_byte(cb, 0x83);
                    codebuf_emit_byte(cb, 0xC4); codebuf_emit_byte(cb, 0x08);
                }
                break;
            case Q_RET:
                x86_emit_pop(cb, X86_RAX);
                x86_emit_ret(cb);
                break;
            case Q_HALT:
                x86_emit_xor_rr(cb, X86_RAX, X86_RAX);
                x86_emit_ret(cb);
                break;
            default:
                fprintf(stderr, "[codegen/safe/x86] unhandled opcode %d at instr %u\n",
                        instr->opcode, i);
                x86_emit_nop(cb);
                break;
            }
        } else if (arch == ARCH_ARM64) {
            switch (instr->opcode) {
            case Q_LOAD:
                if (instr->src1.type == OPERAND_IMM)
                    arm64_emit_movz_imm64(cb, ARM_X0, instr->src1.imm);
                arm64_emit_str_pre(cb, ARM_X0, ARM_SP, -16);
                break;
            case Q_ADD:
                arm64_emit_ldr_post(cb, ARM_X1, ARM_SP, 16);
                arm64_emit_ldr_post(cb, ARM_X0, ARM_SP, 16);
                arm64_emit_add_rrr(cb, ARM_X0, ARM_X0, ARM_X1);
                arm64_emit_str_pre(cb, ARM_X0, ARM_SP, -16);
                break;
            case Q_SUB:
                arm64_emit_ldr_post(cb, ARM_X1, ARM_SP, 16);
                arm64_emit_ldr_post(cb, ARM_X0, ARM_SP, 16);
                arm64_emit_sub_rrr(cb, ARM_X0, ARM_X0, ARM_X1);
                arm64_emit_str_pre(cb, ARM_X0, ARM_SP, -16);
                break;
            case Q_MUL:
                arm64_emit_ldr_post(cb, ARM_X1, ARM_SP, 16);
                arm64_emit_ldr_post(cb, ARM_X0, ARM_SP, 16);
                arm64_emit_mul_rrr(cb, ARM_X0, ARM_X0, ARM_X1);
                arm64_emit_str_pre(cb, ARM_X0, ARM_SP, -16);
                break;
            case Q_DIV:
                arm64_emit_ldr_post(cb, ARM_X1, ARM_SP, 16);
                arm64_emit_ldr_post(cb, ARM_X0, ARM_SP, 16);
                arm64_emit_sdiv_rrr(cb, ARM_X0, ARM_X0, ARM_X1);
                arm64_emit_str_pre(cb, ARM_X0, ARM_SP, -16);
                break;
            case Q_MOD:
                arm64_emit_ldr_post(cb, ARM_X1, ARM_SP, 16);
                arm64_emit_ldr_post(cb, ARM_X0, ARM_SP, 16);
                arm64_emit_sdiv_rrr(cb, ARM_X2, ARM_X0, ARM_X1);
                arm64_emit_mul_rrr(cb, ARM_X2, ARM_X2, ARM_X1);
                arm64_emit_sub_rrr(cb, ARM_X0, ARM_X0, ARM_X2);
                arm64_emit_str_pre(cb, ARM_X0, ARM_SP, -16);
                break;
            case Q_CMP_EQ:
                arm64_emit_ldr_post(cb, ARM_X1, ARM_SP, 16);
                arm64_emit_ldr_post(cb, ARM_X0, ARM_SP, 16);
                arm64_emit_cmp_rr(cb, ARM_X0, ARM_X1);
                arm64_emit_cset_eq(cb, ARM_X0);
                arm64_emit_str_pre(cb, ARM_X0, ARM_SP, -16);
                break;
            case Q_CMP_GT:
                arm64_emit_ldr_post(cb, ARM_X1, ARM_SP, 16);
                arm64_emit_ldr_post(cb, ARM_X0, ARM_SP, 16);
                arm64_emit_cmp_rr(cb, ARM_X0, ARM_X1);
                arm64_emit_cset_gt(cb, ARM_X0);
                arm64_emit_str_pre(cb, ARM_X0, ARM_SP, -16);
                break;
            case Q_CMP_LT:
                arm64_emit_ldr_post(cb, ARM_X1, ARM_SP, 16);
                arm64_emit_ldr_post(cb, ARM_X0, ARM_SP, 16);
                arm64_emit_cmp_rr(cb, ARM_X0, ARM_X1);
                arm64_emit_cset_lt(cb, ARM_X0);
                arm64_emit_str_pre(cb, ARM_X0, ARM_SP, -16);
                break;
            case Q_LABEL:
                if (label_count < CG_MAX_LABELS) {
                    labels[label_count].label_id = instr->patch_id;
                    labels[label_count].offset   = cb->len;
                    label_count++;
                }
                break;
            case Q_JUMP:
                if (instr->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len;
                    fixups[fixup_count].target_label = instr->src1.label;
                    fixups[fixup_count].is_cond      = 0;
                    fixup_count++;
                }
                arm64_emit_b_imm26(cb, 0);
                break;
            case Q_JUMP_IF:
                arm64_emit_ldr_post(cb, ARM_X0, ARM_SP, 16);
                /* CMP X0, #0 */
                codebuf_emit_u32(cb, 0xF100001F);
                if (instr->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len;
                    fixups[fixup_count].target_label = instr->src2.label;
                    fixups[fixup_count].is_cond      = 1;
                    fixup_count++;
                }
                arm64_emit_bne_imm19(cb, 0);
                break;
            case Q_JUMP_IF_NOT:
                arm64_emit_ldr_post(cb, ARM_X0, ARM_SP, 16);
                codebuf_emit_u32(cb, 0xF100001F);
                if (instr->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len;
                    fixups[fixup_count].target_label = instr->src2.label;
                    fixups[fixup_count].is_cond      = 1;
                    fixup_count++;
                }
                arm64_emit_beq_imm19(cb, 0);
                break;
            case Q_CALL:
                if (instr->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len;
                    fixups[fixup_count].target_label = instr->src1.label;
                    fixups[fixup_count].is_cond      = 0;
                    fixup_count++;
                }
                arm64_emit_bl_imm26(cb, 0);
                break;
            case Q_PRINT:
                if (print_addr) {
                    arm64_emit_ldr_post(cb, ARM_X0, ARM_SP, 16);
                    arm64_emit_stp_pre(cb, ARM_FP, ARM_LR, ARM_SP, -16);
                    arm64_emit_movz_imm64(cb, ARM_X16, (int64_t)(uintptr_t)print_addr);
                    codebuf_emit_u32(cb, 0xD63F0200); /* BLR X16 */
                    arm64_emit_ldp_post(cb, ARM_FP, ARM_LR, ARM_SP, 16);
                }
                break;
            case Q_RET:
                arm64_emit_ldr_post(cb, ARM_X0, ARM_SP, 16);
                arm64_emit_ret(cb);
                break;
            case Q_HALT:
                arm64_emit_mov_imm16(cb, ARM_X0, 0);
                arm64_emit_ret(cb);
                break;
            default:
                fprintf(stderr, "[codegen/safe/arm64] unhandled opcode %d at instr %u\n",
                        instr->opcode, i);
                arm64_emit_nop(cb);
                break;
            }
        }
    }

    /* Back-patch branch offsets */
    for (uint32_t f = 0; f < fixup_count; f++) {
        size_t target = 0;
        int found = 0;
        for (uint32_t l = 0; l < label_count; l++) {
            if (labels[l].label_id == fixups[f].target_label) {
                target = labels[l].offset;
                found = 1;
                break;
            }
        }
        if (!found) continue;
        size_t patch_at = fixups[f].patch_offset;
        if (arch == ARCH_ARM64) {
            int32_t byte_offset = (int32_t)(target - patch_at);
            uint32_t orig;
            memcpy(&orig, cb->data + patch_at, 4);
            if (fixups[f].is_cond) {
                uint32_t imm19 = ((uint32_t)(byte_offset >> 2)) & 0x7FFFF;
                orig = (orig & ~(0x7FFFF << 5)) | (imm19 << 5);
            } else {
                uint32_t imm26 = ((uint32_t)(byte_offset >> 2)) & 0x03FFFFFF;
                orig = (orig & ~0x03FFFFFF) | imm26;
            }
            memcpy(cb->data + patch_at, &orig, 4);
        } else {
            size_t instr_end = patch_at + 4;
            int32_t rel = (int32_t)(target - instr_end);
            codebuf_patch_i32(cb, patch_at, rel);
        }
    }

    return 0;
}

/* ── Fast code (Bản B): Register-direct ────────────────── */
int codegen_emit_fast(codebuf_t *cb, const q_instruction_t *instrs,
                      uint32_t count, target_arch_t arch,
                      void *print_addr)
{
    cg_label_t labels[CG_MAX_LABELS];
    cg_fixup_t fixups[CG_MAX_FIXUPS];
    uint32_t label_count = 0;
    uint32_t fixup_count = 0;

    /* Check if we need a stack frame */
    int needs_frame = 0;
    for (uint32_t i = 0; i < count; i++) {
        if (instrs[i].opcode == Q_CALL || instrs[i].opcode == Q_PRINT) {
            needs_frame = 1;
            break;
        }
    }

    /* Prologue */
    if (needs_frame) {
        if (arch == ARCH_ARM64) {
            arm64_emit_stp_pre(cb, ARM_FP, ARM_LR, ARM_SP, -16);
        } else {
            x86_emit_push(cb, X86_RBP);
            x86_emit_mov_rr(cb, X86_RBP, X86_RSP);
        }
    }

    for (uint32_t i = 0; i < count; i++) {
        const q_instruction_t *instr = &instrs[i];

        if (arch == ARCH_X86_64) {
            x86_reg_t rd = (instr->dest.type == OPERAND_VREG)
                           ? vreg_to_x86(instr->dest.vreg) : X86_RAX;
            x86_reg_t rs1 = (instr->src1.type == OPERAND_VREG)
                            ? vreg_to_x86(instr->src1.vreg) : X86_RAX;
            x86_reg_t rs2 = (instr->src2.type == OPERAND_VREG)
                            ? vreg_to_x86(instr->src2.vreg) : X86_RCX;

            switch (instr->opcode) {
            case Q_NOP:
                x86_emit_nop(cb);
                break;
            case Q_LOAD:
                if (instr->src1.type == OPERAND_IMM)
                    x86_emit_mov_reg_imm64(cb, rd, instr->src1.imm);
                break;
            case Q_STORE:
            case Q_MOVE:
                x86_emit_mov_rr(cb, rd, rs1);
                break;
            case Q_ADD:
                if (rd != rs1) x86_emit_mov_rr(cb, rd, rs1);
                x86_emit_add_rr(cb, rd, rs2);
                break;
            case Q_SUB:
                if (rd != rs1) x86_emit_mov_rr(cb, rd, rs1);
                x86_emit_sub_rr(cb, rd, rs2);
                break;
            case Q_MUL:
                if (rd != rs1) x86_emit_mov_rr(cb, rd, rs1);
                x86_emit_imul_rr(cb, rd, rs2);
                break;
            case Q_DIV:
                if (rs1 != X86_RAX) x86_emit_mov_rr(cb, X86_RAX, rs1);
                x86_emit_cqo(cb);
                x86_emit_idiv(cb, rs2);
                if (rd != X86_RAX) x86_emit_mov_rr(cb, rd, X86_RAX);
                break;
            case Q_MOD:
                if (rs1 != X86_RAX) x86_emit_mov_rr(cb, X86_RAX, rs1);
                x86_emit_cqo(cb);
                x86_emit_idiv(cb, rs2);
                if (rd != X86_RDX) x86_emit_mov_rr(cb, rd, X86_RDX);
                break;
            case Q_CMP_EQ:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                x86_emit_sete(cb, rd);
                break;
            case Q_CMP_GT:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                x86_emit_setg(cb, rd);
                break;
            case Q_CMP_LT:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                x86_emit_setl(cb, rd);
                break;
            case Q_CMP_GE:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                if (rd >= X86_R8) codebuf_emit_byte(cb, 0x41);
                codebuf_emit_byte(cb, 0x0F);
                codebuf_emit_byte(cb, 0x9D);
                codebuf_emit_byte(cb, modrm(0x03, 0, rd));
                break;
            case Q_CMP_LE:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                if (rd >= X86_R8) codebuf_emit_byte(cb, 0x41);
                codebuf_emit_byte(cb, 0x0F);
                codebuf_emit_byte(cb, 0x9E);
                codebuf_emit_byte(cb, modrm(0x03, 0, rd));
                break;
            case Q_LABEL:
                if (label_count < CG_MAX_LABELS) {
                    labels[label_count].label_id = instr->patch_id;
                    labels[label_count].offset   = cb->len;
                    label_count++;
                }
                break;
            case Q_JUMP:
                if (instr->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len + 1;
                    fixups[fixup_count].target_label = instr->src1.label;
                    fixups[fixup_count].is_cond      = 0;
                    fixup_count++;
                }
                x86_emit_jmp_rel32(cb, 0);
                break;
            case Q_JUMP_IF:
                if (instr->src1.type == OPERAND_VREG) {
                    codebuf_emit_byte(cb, rex_w(rs1, rs1));
                    codebuf_emit_byte(cb, 0x85);
                    codebuf_emit_byte(cb, modrm(0x03, rs1, rs1));
                }
                if (instr->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len + 2;
                    fixups[fixup_count].target_label = instr->src2.label;
                    fixups[fixup_count].is_cond      = 1;
                    fixup_count++;
                }
                x86_emit_jne_rel32(cb, 0);
                break;
            case Q_JUMP_IF_NOT:
                if (instr->src1.type == OPERAND_VREG) {
                    codebuf_emit_byte(cb, rex_w(rs1, rs1));
                    codebuf_emit_byte(cb, 0x85);
                    codebuf_emit_byte(cb, modrm(0x03, rs1, rs1));
                }
                if (instr->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len + 2;
                    fixups[fixup_count].target_label = instr->src2.label;
                    fixups[fixup_count].is_cond      = 1;
                    fixup_count++;
                }
                x86_emit_je_rel32(cb, 0);
                break;
            case Q_CALL:
                if (instr->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len + 1;
                    fixups[fixup_count].target_label = instr->src1.label;
                    fixups[fixup_count].is_cond      = 0;
                    fixup_count++;
                }
                x86_emit_call_rel32(cb, 0);
                break;
            case Q_PRINT:
                if (print_addr) {
                    x86_emit_push(cb, X86_RAX);
                    x86_emit_push(cb, X86_RCX);
                    x86_emit_push(cb, X86_RDX);
                    x86_emit_push(cb, X86_RSI);
                    x86_emit_push(cb, X86_RDI);
                    if (instr->src1.type == OPERAND_VREG && rs1 != X86_RDI)
                        x86_emit_mov_rr(cb, X86_RDI, rs1);
                    codebuf_emit_byte(cb, 0x48); codebuf_emit_byte(cb, 0x83);
                    codebuf_emit_byte(cb, 0xEC); codebuf_emit_byte(cb, 0x08);
                    x86_emit_mov_reg_imm64(cb, X86_RAX, (int64_t)(uintptr_t)print_addr);
                    codebuf_emit_byte(cb, 0xFF); codebuf_emit_byte(cb, 0xD0);
                    codebuf_emit_byte(cb, 0x48); codebuf_emit_byte(cb, 0x83);
                    codebuf_emit_byte(cb, 0xC4); codebuf_emit_byte(cb, 0x08);
                    x86_emit_pop(cb, X86_RDI);
                    x86_emit_pop(cb, X86_RSI);
                    x86_emit_pop(cb, X86_RDX);
                    x86_emit_pop(cb, X86_RCX);
                    x86_emit_pop(cb, X86_RAX);
                }
                break;
            case Q_RET:
                if (instr->src1.type == OPERAND_VREG && rs1 != X86_RAX)
                    x86_emit_mov_rr(cb, X86_RAX, rs1);
                if (needs_frame) {
                    x86_emit_mov_rr(cb, X86_RSP, X86_RBP);
                    x86_emit_pop(cb, X86_RBP);
                }
                x86_emit_ret(cb);
                break;
            case Q_HALT:
                x86_emit_xor_rr(cb, X86_RAX, X86_RAX);
                x86_emit_ret(cb);
                break;
            default:
                fprintf(stderr, "[codegen/fast/x86] unhandled opcode %d at instr %u\n",
                        instr->opcode, i);
                x86_emit_nop(cb);
                break;
            }
        } else if (arch == ARCH_ARM64) {
            arm_reg_t rd  = (instr->dest.type == OPERAND_VREG)
                            ? vreg_to_arm(instr->dest.vreg) : ARM_X0;
            arm_reg_t rs1 = (instr->src1.type == OPERAND_VREG)
                            ? vreg_to_arm(instr->src1.vreg) : ARM_X0;
            arm_reg_t rs2 = (instr->src2.type == OPERAND_VREG)
                            ? vreg_to_arm(instr->src2.vreg) : ARM_X1;

            switch (instr->opcode) {
            case Q_NOP:
                arm64_emit_nop(cb);
                break;
            case Q_LOAD:
                if (instr->src1.type == OPERAND_IMM)
                    arm64_emit_movz_imm64(cb, rd, instr->src1.imm);
                break;
            case Q_STORE:
            case Q_MOVE:
                arm64_emit_mov_rr(cb, rd, rs1);
                break;
            case Q_ADD:
                arm64_emit_add_rrr(cb, rd, rs1, rs2);
                break;
            case Q_SUB:
                arm64_emit_sub_rrr(cb, rd, rs1, rs2);
                break;
            case Q_MUL:
                arm64_emit_mul_rrr(cb, rd, rs1, rs2);
                break;
            case Q_DIV:
                arm64_emit_sdiv_rrr(cb, rd, rs1, rs2);
                break;
            case Q_MOD:
                arm64_emit_sdiv_rrr(cb, ARM_X16, rs1, rs2);
                arm64_emit_mul_rrr(cb, ARM_X16, ARM_X16, rs2);
                arm64_emit_sub_rrr(cb, rd, rs1, ARM_X16);
                break;
            case Q_CMP_EQ:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                arm64_emit_cset_eq(cb, rd);
                break;
            case Q_CMP_GT:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                arm64_emit_cset_gt(cb, rd);
                break;
            case Q_CMP_LT:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                arm64_emit_cset_lt(cb, rd);
                break;
            case Q_CMP_GE:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                codebuf_emit_u32(cb, 0x9A9FB7E0 | (rd & 0x1F));
                break;
            case Q_CMP_LE:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                codebuf_emit_u32(cb, 0x9A9FC7E0 | (rd & 0x1F));
                break;
            case Q_LABEL:
                if (label_count < CG_MAX_LABELS) {
                    labels[label_count].label_id = instr->patch_id;
                    labels[label_count].offset   = cb->len;
                    label_count++;
                }
                break;
            case Q_JUMP:
                if (instr->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len;
                    fixups[fixup_count].target_label = instr->src1.label;
                    fixups[fixup_count].is_cond      = 0;
                    fixup_count++;
                }
                arm64_emit_b_imm26(cb, 0);
                break;
            case Q_JUMP_IF:
                if (instr->src1.type == OPERAND_VREG)
                    codebuf_emit_u32(cb, 0xF100001F | ((rs1 & 0x1F) << 5));
                if (instr->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len;
                    fixups[fixup_count].target_label = instr->src2.label;
                    fixups[fixup_count].is_cond      = 1;
                    fixup_count++;
                }
                arm64_emit_bne_imm19(cb, 0);
                break;
            case Q_JUMP_IF_NOT:
                if (instr->src1.type == OPERAND_VREG)
                    codebuf_emit_u32(cb, 0xF100001F | ((rs1 & 0x1F) << 5));
                if (instr->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len;
                    fixups[fixup_count].target_label = instr->src2.label;
                    fixups[fixup_count].is_cond      = 1;
                    fixup_count++;
                }
                arm64_emit_beq_imm19(cb, 0);
                break;
            case Q_CALL:
                if (instr->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len;
                    fixups[fixup_count].target_label = instr->src1.label;
                    fixups[fixup_count].is_cond      = 0;
                    fixup_count++;
                }
                arm64_emit_bl_imm26(cb, 0);
                break;
            case Q_PRINT:
                if (print_addr) {
                    arm64_emit_stp_pre(cb, ARM_X0,  ARM_X1,  ARM_SP, -16);
                    arm64_emit_stp_pre(cb, ARM_X2,  ARM_X3,  ARM_SP, -16);
                    arm64_emit_stp_pre(cb, ARM_FP,  ARM_LR,  ARM_SP, -16);
                    if (instr->src1.type == OPERAND_VREG && rs1 != ARM_X0)
                        arm64_emit_mov_rr(cb, ARM_X0, rs1);
                    arm64_emit_movz_imm64(cb, ARM_X16, (int64_t)(uintptr_t)print_addr);
                    codebuf_emit_u32(cb, 0xD63F0200); /* BLR X16 */
                    arm64_emit_ldp_post(cb, ARM_FP,  ARM_LR,  ARM_SP, 16);
                    arm64_emit_ldp_post(cb, ARM_X2,  ARM_X3,  ARM_SP, 16);
                    arm64_emit_ldp_post(cb, ARM_X0,  ARM_X1,  ARM_SP, 16);
                }
                break;
            case Q_RET:
                if (instr->src1.type == OPERAND_VREG && rs1 != ARM_X0)
                    arm64_emit_mov_rr(cb, ARM_X0, rs1);
                if (needs_frame)
                    arm64_emit_ldp_post(cb, ARM_FP, ARM_LR, ARM_SP, 16);
                arm64_emit_ret(cb);
                break;
            case Q_HALT:
                arm64_emit_mov_imm16(cb, ARM_X0, 0);
                arm64_emit_ret(cb);
                break;
            default:
                fprintf(stderr, "[codegen/fast/arm64] unhandled opcode %d at instr %u\n",
                        instr->opcode, i);
                arm64_emit_nop(cb);
                break;
            }
        }
    }

    /* Back-patch branch offsets */
    for (uint32_t f = 0; f < fixup_count; f++) {
        size_t target = 0;
        int found = 0;
        for (uint32_t l = 0; l < label_count; l++) {
            if (labels[l].label_id == fixups[f].target_label) {
                target = labels[l].offset;
                found = 1;
                break;
            }
        }
        if (!found) continue;
        size_t patch_at = fixups[f].patch_offset;
        if (arch == ARCH_ARM64) {
            int32_t byte_offset = (int32_t)(target - patch_at);
            uint32_t orig;
            memcpy(&orig, cb->data + patch_at, 4);
            if (fixups[f].is_cond) {
                uint32_t imm19 = ((uint32_t)(byte_offset >> 2)) & 0x7FFFF;
                orig = (orig & ~(0x7FFFF << 5)) | (imm19 << 5);
            } else {
                uint32_t imm26 = ((uint32_t)(byte_offset >> 2)) & 0x03FFFFFF;
                orig = (orig & ~0x03FFFFFF) | imm26;
            }
            memcpy(cb->data + patch_at, &orig, 4);
        } else {
            size_t instr_end = patch_at + 4;
            int32_t rel = (int32_t)(target - instr_end);
            codebuf_patch_i32(cb, patch_at, rel);
        }
    }

    return 0;
}

/* ── Generate all variants from a module ───────────────── */
int codegen_generate(codegen_result_t *result, const q_module_t *mod)
{
    target_arch_t arch = result->arch;

    for (uint32_t fi = 0; fi < mod->func_count; fi++) {
        const q_function_t *func = &mod->functions[fi];

        /* Scan for PATCH_POINTs, group instructions */
        uint32_t seg_start = 0;
        for (uint32_t ii = 0; ii <= func->body_count; ii++) {
            int is_patch = (ii < func->body_count &&
                           func->body[ii].opcode == Q_PATCH_POINT);
            int is_end = (ii == func->body_count);

            if ((is_patch || is_end) && ii > seg_start) {
                if (result->count >= MAX_VARIANTS) return -1;

                code_variant_t *v = &result->variants[result->count];
                v->patch_id = is_patch ? func->body[ii].patch_id
                                       : (fi * 1000 + seg_start);

                codebuf_init(&v->safe_code, arch);
                codebuf_init(&v->fast_code, arch);

                codegen_emit_safe(&v->safe_code,
                                  &func->body[seg_start],
                                  ii - seg_start, arch, NULL);
                codegen_emit_fast(&v->fast_code,
                                  &func->body[seg_start],
                                  ii - seg_start, arch, NULL);

                result->count++;
            }

            if (is_patch) seg_start = ii + 1;
            else if (is_end) break;
        }
    }
    return 0;
}

void codegen_free(codegen_result_t *result)
{
    for (uint32_t i = 0; i < result->count; i++) {
        codebuf_free(&result->variants[i].safe_code);
        codebuf_free(&result->variants[i].fast_code);
    }
    result->count = 0;
}

/* ═══════════════════════════════════════════════════════
 * Full Code Generator with Label Resolution
 * ═══════════════════════════════════════════════════════
 * Register-direct code (fast path) with back-patching for
 * branch offsets.  Handles all Q-IR opcodes including
 * control flow, comparisons, CALL, PRINT, INPUT.
 */

int codegen_emit_full(codebuf_t *cb, const q_instruction_t *instrs,
                      uint32_t count, target_arch_t arch,
                      void *print_addr)
{
    cg_label_t labels[CG_MAX_LABELS];
    cg_fixup_t fixups[CG_MAX_FIXUPS];
    uint32_t label_count = 0;
    uint32_t fixup_count = 0;

    /* Check if we need a stack frame (any CALL/PRINT/BLR) */
    int needs_frame = 0;
    for (uint32_t i = 0; i < count; i++) {
        if (instrs[i].opcode == Q_CALL || instrs[i].opcode == Q_PRINT) {
            needs_frame = 1;
            break;
        }
    }

    /* ── Prologue ──────────────────────────────────────── */
    if (needs_frame) {
        if (arch == ARCH_ARM64) {
            /* STP X29, X30, [SP, #-16]! */
            arm64_emit_stp_pre(cb, ARM_FP, ARM_LR, ARM_SP, -16);
        } else {
            /* PUSH RBP; MOV RBP, RSP */
            x86_emit_push(cb, X86_RBP);
            x86_emit_mov_rr(cb, X86_RBP, X86_RSP);
        }
    }

    for (uint32_t i = 0; i < count; i++) {
        const q_instruction_t *ins = &instrs[i];

        if (arch == ARCH_ARM64) {
            arm_reg_t rd  = (ins->dest.type == OPERAND_VREG)
                            ? vreg_to_arm(ins->dest.vreg) : ARM_X0;
            arm_reg_t rs1 = (ins->src1.type == OPERAND_VREG)
                            ? vreg_to_arm(ins->src1.vreg) : ARM_X0;
            arm_reg_t rs2 = (ins->src2.type == OPERAND_VREG)
                            ? vreg_to_arm(ins->src2.vreg) : ARM_X1;

            switch (ins->opcode) {
            case Q_NOP:
                arm64_emit_nop(cb);
                break;

            case Q_LOAD:
                if (ins->src1.type == OPERAND_IMM)
                    arm64_emit_movz_imm64(cb, rd, ins->src1.imm);
                break;

            case Q_MOVE:
                arm64_emit_mov_rr(cb, rd, rs1);
                break;

            case Q_ADD:  arm64_emit_add_rrr(cb, rd, rs1, rs2);  break;
            case Q_SUB:  arm64_emit_sub_rrr(cb, rd, rs1, rs2);  break;
            case Q_MUL:  arm64_emit_mul_rrr(cb, rd, rs1, rs2);  break;
            case Q_DIV:  arm64_emit_sdiv_rrr(cb, rd, rs1, rs2); break;

            case Q_MOD: {
                /* X_tmp = SDIV(rs1, rs2); rd = rs1 - X_tmp * rs2 */
                arm64_emit_sdiv_rrr(cb, ARM_X16, rs1, rs2);
                arm64_emit_mul_rrr(cb, ARM_X16, ARM_X16, rs2);
                arm64_emit_sub_rrr(cb, rd, rs1, ARM_X16);
                break;
            }

            case Q_CMP_EQ:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                arm64_emit_cset_eq(cb, rd);
                break;
            case Q_CMP_GT:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                arm64_emit_cset_gt(cb, rd);
                break;
            case Q_CMP_LT:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                arm64_emit_cset_lt(cb, rd);
                break;
            case Q_CMP_GE:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                /* CSET GE = CSINC Xd, XZR, XZR, LT(0xB) */
                codebuf_emit_u32(cb, 0x9A9FB7E0 | (rd & 0x1F));
                break;
            case Q_CMP_LE:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                /* CSET LE = CSINC Xd, XZR, XZR, GT(0xC) */
                codebuf_emit_u32(cb, 0x9A9FC7E0 | (rd & 0x1F));
                break;

            case Q_LABEL:
                if (label_count < CG_MAX_LABELS) {
                    labels[label_count].label_id = ins->patch_id;
                    labels[label_count].offset   = cb->len;
                    label_count++;
                }
                break;

            case Q_JUMP:
                if (ins->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset  = cb->len;
                    fixups[fixup_count].target_label  = ins->src1.label;
                    fixups[fixup_count].is_cond       = 0;
                    fixup_count++;
                }
                arm64_emit_b_imm26(cb, 0);  /* placeholder */
                break;

            case Q_JUMP_IF:
                if (ins->src1.type == OPERAND_VREG) {
                    /* CBZ/CBNZ: test cond register, branch if non-zero */
                    arm64_emit_cmp_rr(cb, rs1, ARM_X16);  /* compare with... */
                    /* Actually simpler: CBNZ Rs1, target */
                    /* Use: CMP Rs1, #0; B.NE target */
                    /* CMP Xn, #0 = SUBS XZR, Xn, #0 */
                    codebuf_emit_u32(cb, 0xF100001F | ((rs1 & 0x1F) << 5));
                }
                if (ins->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset  = cb->len;
                    fixups[fixup_count].target_label  = ins->src2.label;
                    fixups[fixup_count].is_cond       = 1;
                    fixup_count++;
                }
                arm64_emit_bne_imm19(cb, 0);  /* placeholder */
                break;

            case Q_JUMP_IF_NOT:
                if (ins->src1.type == OPERAND_VREG) {
                    /* CMP Rs1, #0 */
                    codebuf_emit_u32(cb, 0xF100001F | ((rs1 & 0x1F) << 5));
                }
                if (ins->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset  = cb->len;
                    fixups[fixup_count].target_label  = ins->src2.label;
                    fixups[fixup_count].is_cond       = 1;
                    fixup_count++;
                }
                arm64_emit_beq_imm19(cb, 0);  /* placeholder */
                break;

            case Q_PRINT:
                if (print_addr) {
                    /* Save caller-saved regs X0-X15 around the call */
                    arm64_emit_stp_pre(cb, ARM_X0,  ARM_X1,  ARM_SP, -16);
                    arm64_emit_stp_pre(cb, ARM_X2,  ARM_X3,  ARM_SP, -16);
                    arm64_emit_stp_pre(cb, ARM_X4,  ARM_X5,  ARM_SP, -16);
                    arm64_emit_stp_pre(cb, ARM_X6,  ARM_X7,  ARM_SP, -16);
                    arm64_emit_stp_pre(cb, ARM_X8,  ARM_X9,  ARM_SP, -16);
                    arm64_emit_stp_pre(cb, ARM_X10, ARM_X11, ARM_SP, -16);
                    arm64_emit_stp_pre(cb, ARM_X12, ARM_X13, ARM_SP, -16);
                    arm64_emit_stp_pre(cb, ARM_X14, ARM_X15, ARM_SP, -16);

                    /* Move value to X0 (first arg) */
                    if (ins->src1.type == OPERAND_VREG && rs1 != ARM_X0)
                        arm64_emit_mov_rr(cb, ARM_X0, rs1);
                    /* Load print function address into X16 */
                    arm64_emit_movz_imm64(cb, ARM_X16, (int64_t)(uintptr_t)print_addr);
                    /* BLR X16 */
                    codebuf_emit_u32(cb, 0xD63F0200);

                    /* Restore */
                    arm64_emit_ldp_post(cb, ARM_X14, ARM_X15, ARM_SP, 16);
                    arm64_emit_ldp_post(cb, ARM_X12, ARM_X13, ARM_SP, 16);
                    arm64_emit_ldp_post(cb, ARM_X10, ARM_X11, ARM_SP, 16);
                    arm64_emit_ldp_post(cb, ARM_X8,  ARM_X9,  ARM_SP, 16);
                    arm64_emit_ldp_post(cb, ARM_X6,  ARM_X7,  ARM_SP, 16);
                    arm64_emit_ldp_post(cb, ARM_X4,  ARM_X5,  ARM_SP, 16);
                    arm64_emit_ldp_post(cb, ARM_X2,  ARM_X3,  ARM_SP, 16);
                    arm64_emit_ldp_post(cb, ARM_X0,  ARM_X1,  ARM_SP, 16);
                } else {
                    arm64_emit_nop(cb);
                }
                break;

            case Q_RET:
                if (ins->src1.type == OPERAND_VREG && rs1 != ARM_X0)
                    arm64_emit_mov_rr(cb, ARM_X0, rs1);
                if (needs_frame) {
                    /* LDP X29, X30, [SP], #16 */
                    arm64_emit_ldp_post(cb, ARM_FP, ARM_LR, ARM_SP, 16);
                }
                arm64_emit_ret(cb);
                break;

            case Q_CALL:
                /* For now: BL to a label (intra-module call) */
                if (ins->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset  = cb->len;
                    fixups[fixup_count].target_label  = ins->src1.label;
                    fixups[fixup_count].is_cond       = 0;
                    fixup_count++;
                }
                arm64_emit_bl_imm26(cb, 0);
                break;

            case Q_HALT:
                arm64_emit_mov_imm16(cb, ARM_X0, 0);
                arm64_emit_ret(cb);
                break;

            default:
                fprintf(stderr, "[codegen/full/arm64] unhandled opcode %d at instr %u\n",
                        ins->opcode, i);
                arm64_emit_nop(cb);
                break;
            }
        } else if (arch == ARCH_X86_64) {
            x86_reg_t rd  = (ins->dest.type == OPERAND_VREG)
                            ? vreg_to_x86(ins->dest.vreg) : X86_RAX;
            x86_reg_t rs1 = (ins->src1.type == OPERAND_VREG)
                            ? vreg_to_x86(ins->src1.vreg) : X86_RAX;
            x86_reg_t rs2 = (ins->src2.type == OPERAND_VREG)
                            ? vreg_to_x86(ins->src2.vreg) : X86_RCX;

            switch (ins->opcode) {
            case Q_NOP:
                x86_emit_nop(cb);
                break;

            case Q_LOAD:
                if (ins->src1.type == OPERAND_IMM)
                    x86_emit_mov_reg_imm64(cb, rd, ins->src1.imm);
                break;

            case Q_MOVE:
                x86_emit_mov_rr(cb, rd, rs1);
                break;

            case Q_ADD:
                if (rd != rs1) x86_emit_mov_rr(cb, rd, rs1);
                x86_emit_add_rr(cb, rd, rs2);
                break;
            case Q_SUB:
                if (rd != rs1) x86_emit_mov_rr(cb, rd, rs1);
                x86_emit_sub_rr(cb, rd, rs2);
                break;
            case Q_MUL:
                if (rd != rs1) x86_emit_mov_rr(cb, rd, rs1);
                x86_emit_imul_rr(cb, rd, rs2);
                break;
            case Q_DIV:
                if (rs1 != X86_RAX) x86_emit_mov_rr(cb, X86_RAX, rs1);
                x86_emit_cqo(cb);
                x86_emit_idiv(cb, rs2);
                if (rd != X86_RAX) x86_emit_mov_rr(cb, rd, X86_RAX);
                break;
            case Q_MOD:
                if (rs1 != X86_RAX) x86_emit_mov_rr(cb, X86_RAX, rs1);
                x86_emit_cqo(cb);
                x86_emit_idiv(cb, rs2);
                /* Remainder in RDX */
                if (rd != X86_RDX) x86_emit_mov_rr(cb, rd, X86_RDX);
                break;

            case Q_CMP_EQ:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                x86_emit_sete(cb, rd);
                break;
            case Q_CMP_GT:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                x86_emit_setg(cb, rd);
                break;
            case Q_CMP_LT:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                x86_emit_setl(cb, rd);
                break;
            case Q_CMP_GE:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                /* SETGE → 0F 9D /r */
                if (rd >= X86_R8) codebuf_emit_byte(cb, 0x41);
                codebuf_emit_byte(cb, 0x0F);
                codebuf_emit_byte(cb, 0x9D);
                codebuf_emit_byte(cb, modrm(0x03, 0, rd));
                break;
            case Q_CMP_LE:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                /* SETLE → 0F 9E /r */
                if (rd >= X86_R8) codebuf_emit_byte(cb, 0x41);
                codebuf_emit_byte(cb, 0x0F);
                codebuf_emit_byte(cb, 0x9E);
                codebuf_emit_byte(cb, modrm(0x03, 0, rd));
                break;

            case Q_LABEL:
                if (label_count < CG_MAX_LABELS) {
                    labels[label_count].label_id = ins->patch_id;
                    labels[label_count].offset   = cb->len;
                    label_count++;
                }
                break;

            case Q_JUMP:
                if (ins->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset  = cb->len + 1; /* after opcode byte */
                    fixups[fixup_count].target_label  = ins->src1.label;
                    fixups[fixup_count].is_cond       = 0;
                    fixup_count++;
                }
                x86_emit_jmp_rel32(cb, 0);  /* placeholder */
                break;

            case Q_JUMP_IF:
                if (ins->src1.type == OPERAND_VREG) {
                    /* TEST rs1, rs1 → if non-zero, jump */
                    codebuf_emit_byte(cb, rex_w(rs1, rs1));
                    codebuf_emit_byte(cb, 0x85);
                    codebuf_emit_byte(cb, modrm(0x03, rs1, rs1));
                }
                if (ins->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset  = cb->len + 2; /* after 0F 85 */
                    fixups[fixup_count].target_label  = ins->src2.label;
                    fixups[fixup_count].is_cond       = 1;
                    fixup_count++;
                }
                x86_emit_jne_rel32(cb, 0);  /* JNE placeholder */
                break;

            case Q_JUMP_IF_NOT:
                if (ins->src1.type == OPERAND_VREG) {
                    /* TEST rs1, rs1 → if zero, jump */
                    codebuf_emit_byte(cb, rex_w(rs1, rs1));
                    codebuf_emit_byte(cb, 0x85);
                    codebuf_emit_byte(cb, modrm(0x03, rs1, rs1));
                }
                if (ins->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset  = cb->len + 2; /* after 0F 84 */
                    fixups[fixup_count].target_label  = ins->src2.label;
                    fixups[fixup_count].is_cond       = 1;
                    fixup_count++;
                }
                x86_emit_je_rel32(cb, 0);  /* JE placeholder */
                break;

            case Q_PRINT:
                if (print_addr) {
                    /* Save caller-saved regs around the call */
                    x86_emit_push(cb, X86_RAX);
                    x86_emit_push(cb, X86_RCX);
                    x86_emit_push(cb, X86_RDX);
                    x86_emit_push(cb, X86_RSI);
                    x86_emit_push(cb, X86_RDI);

                    /* Move value to RDI (first arg in System V) */
                    if (ins->src1.type == OPERAND_VREG && rs1 != X86_RDI)
                        x86_emit_mov_rr(cb, X86_RDI, rs1);
                    /* Align stack to 16 bytes before call */
                    /* SUB RSP, 8 (5 pushes = 40 bytes, need 48 for 16-align) */
                    codebuf_emit_byte(cb, 0x48);
                    codebuf_emit_byte(cb, 0x83);
                    codebuf_emit_byte(cb, 0xEC);
                    codebuf_emit_byte(cb, 0x08);
                    /* MOV RAX, print_addr; CALL RAX */
                    x86_emit_mov_reg_imm64(cb, X86_RAX, (int64_t)(uintptr_t)print_addr);
                    /* CALL RAX: FF D0 */
                    codebuf_emit_byte(cb, 0xFF);
                    codebuf_emit_byte(cb, 0xD0);
                    /* ADD RSP, 8 */
                    codebuf_emit_byte(cb, 0x48);
                    codebuf_emit_byte(cb, 0x83);
                    codebuf_emit_byte(cb, 0xC4);
                    codebuf_emit_byte(cb, 0x08);

                    /* Restore */
                    x86_emit_pop(cb, X86_RDI);
                    x86_emit_pop(cb, X86_RSI);
                    x86_emit_pop(cb, X86_RDX);
                    x86_emit_pop(cb, X86_RCX);
                    x86_emit_pop(cb, X86_RAX);
                } else {
                    x86_emit_nop(cb);
                }
                break;

            case Q_RET:
                if (ins->src1.type == OPERAND_VREG && rs1 != X86_RAX)
                    x86_emit_mov_rr(cb, X86_RAX, rs1);
                if (needs_frame) {
                    /* MOV RSP, RBP; POP RBP */
                    x86_emit_mov_rr(cb, X86_RSP, X86_RBP);
                    x86_emit_pop(cb, X86_RBP);
                }
                x86_emit_ret(cb);
                break;

            case Q_CALL:
                if (ins->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset  = cb->len + 1;
                    fixups[fixup_count].target_label  = ins->src1.label;
                    fixups[fixup_count].is_cond       = 0;
                    fixup_count++;
                }
                x86_emit_call_rel32(cb, 0);
                break;

            case Q_HALT:
                x86_emit_xor_rr(cb, X86_RAX, X86_RAX);
                x86_emit_ret(cb);
                break;

            default:
                fprintf(stderr, "[codegen/full/x86] unhandled opcode %d at instr %u\n",
                        ins->opcode, i);
                x86_emit_nop(cb);
                break;
            }
        }
    }

    /* ── Back-patch branch offsets ──────────────────────── */
    for (uint32_t f = 0; f < fixup_count; f++) {
        /* Find target label */
        size_t target = 0;
        int found = 0;
        for (uint32_t l = 0; l < label_count; l++) {
            if (labels[l].label_id == fixups[f].target_label) {
                target = labels[l].offset;
                found = 1;
                break;
            }
        }
        if (!found) continue;

        size_t patch_at = fixups[f].patch_offset;

        if (arch == ARCH_ARM64) {
            /* ARM64: branch is at patch_at, 4-byte instruction */
            int32_t byte_offset = (int32_t)(target - patch_at);
            uint32_t orig;
            memcpy(&orig, cb->data + patch_at, 4);

            if (fixups[f].is_cond) {
                /* B.cond: imm19 at bits [23:5] */
                uint32_t imm19 = ((uint32_t)(byte_offset >> 2)) & 0x7FFFF;
                orig = (orig & ~(0x7FFFF << 5)) | (imm19 << 5);
            } else {
                /* B / BL: imm26 at bits [25:0] */
                uint32_t imm26 = ((uint32_t)(byte_offset >> 2)) & 0x03FFFFFF;
                orig = (orig & ~0x03FFFFFF) | imm26;
            }
            memcpy(cb->data + patch_at, &orig, 4);
        } else {
            /* x86_64: rel32 at patch_at, offset relative to instruction end */
            size_t instr_end = patch_at + 4;
            int32_t rel = (int32_t)(target - instr_end);
            codebuf_patch_i32(cb, patch_at, rel);
        }
    }

    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Phase 1: Runtime Context Initialization
 * ═══════════════════════════════════════════════════════ */

void codegen_rt_init(codegen_rt_t *rt)
{
    memset(rt, 0, sizeof(*rt));
    /* Populate from the global intrinsic table */
    intrinsic_table_t *tbl = vir_intrinsics();
    for (int i = 0; i < (int)INTRINSIC_COUNT && i < 32; i++) {
        rt->intrinsic_addrs[i] = tbl->entries[i].func_ptr;
    }
}

/* ═══════════════════════════════════════════════════════
 * Phase 1: codegen_emit_full2 – Complete Opcode Coverage
 * ═══════════════════════════════════════════════════════
 *
 * Extends codegen_emit_full with all remaining Q-IR opcodes:
 *   - STORE, bitwise, memory, globals, strings, file I/O,
 *     arrays, system ops, CALL_FUNC
 *
 * Strategy:
 *   - Simple ops (bitwise, STORE, memory) → native instructions
 *   - Complex ops (string, file, array) → CALL to intrinsic addr
 *
 * Intrinsic call convention (helper macros):
 *   ARM64: args in X0-X2, call via BLR X16, result in X0
 *   x86_64: args in RDI/RSI/RDX (SysV), call via RAX, result RAX
 */

/* ── x86_64 helpers for intrinsic calls ────────────────── */

static void x86_emit_call_intrinsic_1(codebuf_t *cb, void *fn_addr,
                                       x86_reg_t arg0, x86_reg_t rd)
{
    /* Save volatile regs: push RCX, RDX, RSI, RDI */
    x86_emit_push(cb, X86_RCX);
    x86_emit_push(cb, X86_RDX);
    x86_emit_push(cb, X86_RSI);
    x86_emit_push(cb, X86_RDI);
    /* SUB RSP, 8 for 16-byte alignment (4 pushes = 32, need 40) */
    codebuf_emit_byte(cb, 0x48); codebuf_emit_byte(cb, 0x83);
    codebuf_emit_byte(cb, 0xEC); codebuf_emit_byte(cb, 0x08);
    /* Move arg0 to RDI */
    if (arg0 != X86_RDI) x86_emit_mov_rr(cb, X86_RDI, arg0);
    /* CALL fn_addr */
    x86_emit_mov_reg_imm64(cb, X86_RAX, (int64_t)(uintptr_t)fn_addr);
    codebuf_emit_byte(cb, 0xFF); codebuf_emit_byte(cb, 0xD0); /* CALL RAX */
    /* Result in RAX, move to rd */
    if (rd != X86_RAX) x86_emit_mov_rr(cb, rd, X86_RAX);
    /* ADD RSP, 8 */
    codebuf_emit_byte(cb, 0x48); codebuf_emit_byte(cb, 0x83);
    codebuf_emit_byte(cb, 0xC4); codebuf_emit_byte(cb, 0x08);
    /* Restore */
    x86_emit_pop(cb, X86_RDI);
    x86_emit_pop(cb, X86_RSI);
    x86_emit_pop(cb, X86_RDX);
    x86_emit_pop(cb, X86_RCX);
}

static void x86_emit_call_intrinsic_2(codebuf_t *cb, void *fn_addr,
                                       x86_reg_t a0, x86_reg_t a1,
                                       x86_reg_t rd)
{
    x86_emit_push(cb, X86_RCX);
    x86_emit_push(cb, X86_RDX);
    x86_emit_push(cb, X86_RSI);
    x86_emit_push(cb, X86_RDI);
    codebuf_emit_byte(cb, 0x48); codebuf_emit_byte(cb, 0x83);
    codebuf_emit_byte(cb, 0xEC); codebuf_emit_byte(cb, 0x08);
    /* Handle overlap: move a1 first if a0 == RSI */
    if (a0 == X86_RSI && a1 != X86_RDI) {
        x86_emit_mov_rr(cb, X86_RSI, a1);
        x86_emit_mov_rr(cb, X86_RDI, a0);
    } else {
        if (a0 != X86_RDI) x86_emit_mov_rr(cb, X86_RDI, a0);
        if (a1 != X86_RSI) x86_emit_mov_rr(cb, X86_RSI, a1);
    }
    x86_emit_mov_reg_imm64(cb, X86_RAX, (int64_t)(uintptr_t)fn_addr);
    codebuf_emit_byte(cb, 0xFF); codebuf_emit_byte(cb, 0xD0);
    if (rd != X86_RAX) x86_emit_mov_rr(cb, rd, X86_RAX);
    codebuf_emit_byte(cb, 0x48); codebuf_emit_byte(cb, 0x83);
    codebuf_emit_byte(cb, 0xC4); codebuf_emit_byte(cb, 0x08);
    x86_emit_pop(cb, X86_RDI);
    x86_emit_pop(cb, X86_RSI);
    x86_emit_pop(cb, X86_RDX);
    x86_emit_pop(cb, X86_RCX);
}

static void x86_emit_call_intrinsic_3(codebuf_t *cb, void *fn_addr,
                                       x86_reg_t a0, x86_reg_t a1,
                                       x86_reg_t a2, x86_reg_t rd)
{
    x86_emit_push(cb, X86_RCX);
    x86_emit_push(cb, X86_RDX);
    x86_emit_push(cb, X86_RSI);
    x86_emit_push(cb, X86_RDI);
    codebuf_emit_byte(cb, 0x48); codebuf_emit_byte(cb, 0x83);
    codebuf_emit_byte(cb, 0xEC); codebuf_emit_byte(cb, 0x08);
    if (a0 != X86_RDI) x86_emit_mov_rr(cb, X86_RDI, a0);
    if (a1 != X86_RSI) x86_emit_mov_rr(cb, X86_RSI, a1);
    if (a2 != X86_RDX) x86_emit_mov_rr(cb, X86_RDX, a2);
    x86_emit_mov_reg_imm64(cb, X86_RAX, (int64_t)(uintptr_t)fn_addr);
    codebuf_emit_byte(cb, 0xFF); codebuf_emit_byte(cb, 0xD0);
    if (rd != X86_RAX) x86_emit_mov_rr(cb, rd, X86_RAX);
    codebuf_emit_byte(cb, 0x48); codebuf_emit_byte(cb, 0x83);
    codebuf_emit_byte(cb, 0xC4); codebuf_emit_byte(cb, 0x08);
    x86_emit_pop(cb, X86_RDI);
    x86_emit_pop(cb, X86_RSI);
    x86_emit_pop(cb, X86_RDX);
    x86_emit_pop(cb, X86_RCX);
}

/* ── ARM64 helpers for intrinsic calls ─────────────────── */

static void arm64_save_regs(codebuf_t *cb)
{
    arm64_emit_stp_pre(cb, ARM_X0,  ARM_X1,  ARM_SP, -16);
    arm64_emit_stp_pre(cb, ARM_X2,  ARM_X3,  ARM_SP, -16);
    arm64_emit_stp_pre(cb, ARM_X4,  ARM_X5,  ARM_SP, -16);
    arm64_emit_stp_pre(cb, ARM_X6,  ARM_X7,  ARM_SP, -16);
    arm64_emit_stp_pre(cb, ARM_X8,  ARM_X9,  ARM_SP, -16);
    arm64_emit_stp_pre(cb, ARM_X10, ARM_X11, ARM_SP, -16);
    arm64_emit_stp_pre(cb, ARM_X12, ARM_X13, ARM_SP, -16);
    arm64_emit_stp_pre(cb, ARM_X14, ARM_X15, ARM_SP, -16);
}

static void arm64_restore_regs(codebuf_t *cb)
{
    arm64_emit_ldp_post(cb, ARM_X14, ARM_X15, ARM_SP, 16);
    arm64_emit_ldp_post(cb, ARM_X12, ARM_X13, ARM_SP, 16);
    arm64_emit_ldp_post(cb, ARM_X10, ARM_X11, ARM_SP, 16);
    arm64_emit_ldp_post(cb, ARM_X8,  ARM_X9,  ARM_SP, 16);
    arm64_emit_ldp_post(cb, ARM_X6,  ARM_X7,  ARM_SP, 16);
    arm64_emit_ldp_post(cb, ARM_X4,  ARM_X5,  ARM_SP, 16);
    arm64_emit_ldp_post(cb, ARM_X2,  ARM_X3,  ARM_SP, 16);
    arm64_emit_ldp_post(cb, ARM_X0,  ARM_X1,  ARM_SP, 16);
}

static void arm64_emit_call_intrinsic_1(codebuf_t *cb, void *fn_addr,
                                         arm_reg_t arg0, arm_reg_t rd)
{
    arm64_save_regs(cb);
    if (arg0 != ARM_X0) arm64_emit_mov_rr(cb, ARM_X0, arg0);
    arm64_emit_movz_imm64(cb, ARM_X16, (int64_t)(uintptr_t)fn_addr);
    codebuf_emit_u32(cb, 0xD63F0200); /* BLR X16 */
    /* Save result temporarily in X16 */
    arm64_emit_mov_rr(cb, ARM_X16, ARM_X0);
    arm64_restore_regs(cb);
    if (rd != ARM_X16) arm64_emit_mov_rr(cb, rd, ARM_X16);
}

static void arm64_emit_call_intrinsic_2(codebuf_t *cb, void *fn_addr,
                                         arm_reg_t a0, arm_reg_t a1,
                                         arm_reg_t rd)
{
    arm64_save_regs(cb);
    if (a0 != ARM_X0) arm64_emit_mov_rr(cb, ARM_X0, a0);
    if (a1 != ARM_X1) arm64_emit_mov_rr(cb, ARM_X1, a1);
    arm64_emit_movz_imm64(cb, ARM_X16, (int64_t)(uintptr_t)fn_addr);
    codebuf_emit_u32(cb, 0xD63F0200);
    arm64_emit_mov_rr(cb, ARM_X16, ARM_X0);
    arm64_restore_regs(cb);
    if (rd != ARM_X16) arm64_emit_mov_rr(cb, rd, ARM_X16);
}

static void arm64_emit_call_intrinsic_3(codebuf_t *cb, void *fn_addr,
                                         arm_reg_t a0, arm_reg_t a1,
                                         arm_reg_t a2, arm_reg_t rd)
{
    arm64_save_regs(cb);
    if (a0 != ARM_X0) arm64_emit_mov_rr(cb, ARM_X0, a0);
    if (a1 != ARM_X1) arm64_emit_mov_rr(cb, ARM_X1, a1);
    if (a2 != ARM_X2) arm64_emit_mov_rr(cb, ARM_X2, a2);
    arm64_emit_movz_imm64(cb, ARM_X16, (int64_t)(uintptr_t)fn_addr);
    codebuf_emit_u32(cb, 0xD63F0200);
    arm64_emit_mov_rr(cb, ARM_X16, ARM_X0);
    arm64_restore_regs(cb);
    if (rd != ARM_X16) arm64_emit_mov_rr(cb, rd, ARM_X16);
}

/* ── x86_64 bitwise instruction emitters ───────────────── */

static void x86_emit_and_rr(codebuf_t *cb, x86_reg_t dst, x86_reg_t src)
{
    /* AND dst, src → REX.W 21 /r */
    codebuf_emit_byte(cb, rex_w(src, dst));
    codebuf_emit_byte(cb, 0x21);
    codebuf_emit_byte(cb, modrm(0x03, src, dst));
}

static void x86_emit_or_rr(codebuf_t *cb, x86_reg_t dst, x86_reg_t src)
{
    /* OR dst, src → REX.W 09 /r */
    codebuf_emit_byte(cb, rex_w(src, dst));
    codebuf_emit_byte(cb, 0x09);
    codebuf_emit_byte(cb, modrm(0x03, src, dst));
}

static void x86_emit_shl_cl(codebuf_t *cb, x86_reg_t dst)
{
    /* SHL dst, CL → REX.W D3 /4 */
    uint8_t r = 0x48;
    if (dst >= X86_R8) r |= 0x01;
    codebuf_emit_byte(cb, r);
    codebuf_emit_byte(cb, 0xD3);
    codebuf_emit_byte(cb, modrm(0x03, 4, dst));
}

static void x86_emit_sar_cl(codebuf_t *cb, x86_reg_t dst)
{
    /* SAR dst, CL → REX.W D3 /7 */
    uint8_t r = 0x48;
    if (dst >= X86_R8) r |= 0x01;
    codebuf_emit_byte(cb, r);
    codebuf_emit_byte(cb, 0xD3);
    codebuf_emit_byte(cb, modrm(0x03, 7, dst));
}

/* ── ARM64 bitwise instruction emitters ────────────────── */

static void arm64_emit_and_rrr(codebuf_t *cb, arm_reg_t rd,
                                arm_reg_t rn, arm_reg_t rm)
{
    /* AND Xd, Xn, Xm → 1000_1010_000 Rm 000000 Rn Rd */
    uint32_t instr = 0x8A000000 | ((rm & 0x1F) << 16) |
                     ((rn & 0x1F) << 5) | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);
}

static void arm64_emit_orr_rrr(codebuf_t *cb, arm_reg_t rd,
                                arm_reg_t rn, arm_reg_t rm)
{
    /* ORR Xd, Xn, Xm → 1010_1010_000 Rm 000000 Rn Rd */
    uint32_t instr = 0xAA000000 | ((rm & 0x1F) << 16) |
                     ((rn & 0x1F) << 5) | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);
}

static void arm64_emit_eor_rrr(codebuf_t *cb, arm_reg_t rd,
                                arm_reg_t rn, arm_reg_t rm)
{
    /* EOR Xd, Xn, Xm → 1100_1010_000 Rm 000000 Rn Rd */
    uint32_t instr = 0xCA000000 | ((rm & 0x1F) << 16) |
                     ((rn & 0x1F) << 5) | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);
}

static void arm64_emit_lsl_rrr(codebuf_t *cb, arm_reg_t rd,
                                arm_reg_t rn, arm_reg_t rm)
{
    /* LSL Xd, Xn, Xm = LSLV → 1001_1010_1100_0000 Rm 0010_00 Rn Rd */
    uint32_t instr = 0x9AC02000 | ((rm & 0x1F) << 16) |
                     ((rn & 0x1F) << 5) | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);
}

static void arm64_emit_asr_rrr(codebuf_t *cb, arm_reg_t rd,
                                arm_reg_t rn, arm_reg_t rm)
{
    /* ASR Xd, Xn, Xm = ASRV → 1001_1010_1100_0000 Rm 0010_10 Rn Rd */
    uint32_t instr = 0x9AC02800 | ((rm & 0x1F) << 16) |
                     ((rn & 0x1F) << 5) | (rd & 0x1F);
    codebuf_emit_u32(cb, instr);
}

/* ── ARM64 memory load/store emitters ──────────────────── */

static void arm64_emit_ldrb_reg(codebuf_t *cb, arm_reg_t rt,
                                 arm_reg_t rn, arm_reg_t rm)
{
    /* LDRB Wt, [Xn, Xm] → 0011_1000_011 Rm 011_0_10 Rn Rt */
    uint32_t instr = 0x38606800 | ((rm & 0x1F) << 16) |
                     ((rn & 0x1F) << 5) | (rt & 0x1F);
    codebuf_emit_u32(cb, instr);
}

static void arm64_emit_strb_reg(codebuf_t *cb, arm_reg_t rt,
                                 arm_reg_t rn, arm_reg_t rm)
{
    /* STRB Wt, [Xn, Xm] → 0011_1000_001 Rm 011_0_10 Rn Rt */
    uint32_t instr = 0x38206800 | ((rm & 0x1F) << 16) |
                     ((rn & 0x1F) << 5) | (rt & 0x1F);
    codebuf_emit_u32(cb, instr);
}

static void arm64_emit_ldr_reg(codebuf_t *cb, arm_reg_t rt,
                                arm_reg_t rn, arm_reg_t rm)
{
    /* LDR Xt, [Xn, Xm, LSL #3] → 1111_1000_011 Rm 011_1_10 Rn Rt */
    uint32_t instr = 0xF8607800 | ((rm & 0x1F) << 16) |
                     ((rn & 0x1F) << 5) | (rt & 0x1F);
    codebuf_emit_u32(cb, instr);
}

static void arm64_emit_str_reg(codebuf_t *cb, arm_reg_t rt,
                                arm_reg_t rn, arm_reg_t rm)
{
    /* STR Xt, [Xn, Xm, LSL #3] → 1111_1000_001 Rm 011_1_10 Rn Rt */
    uint32_t instr = 0xF8207800 | ((rm & 0x1F) << 16) |
                     ((rn & 0x1F) << 5) | (rt & 0x1F);
    codebuf_emit_u32(cb, instr);
}

/* ═══════════════════════════════════════════════════════
 * ARM64 NEON (SIMD) Instruction Emitters
 * ═══════════════════════════════════════════════════════
 * 128-bit ASIMD instructions using V0-V31 registers.
 * Vn register index uses the same 5-bit encoding as Xn.
 * For 4×32-bit (4S) arrangement, size bits = 10 (within
 * the instruction encoding).
 */

/* LD1 {Vt.4S}, [Xn] — Load 128 bits from [Xn] into Vt */
static void neon_emit_ld1_4s(codebuf_t *cb, uint8_t vt, arm_reg_t xn)
{
    /* LD1 {Vt.4S}, [Xn] → 0100_1100_0100_0000_1010_00 Rn Rt
     * encoding: 0x4C40A800 | Rn<<5 | Rt                      */
    uint32_t enc = 0x4C40A800 | ((xn & 0x1F) << 5) | (vt & 0x1F);
    codebuf_emit_u32(cb, enc);
}

/* ST1 {Vt.4S}, [Xn] — Store 128 bits from Vt to [Xn] */
static void neon_emit_st1_4s(codebuf_t *cb, uint8_t vt, arm_reg_t xn)
{
    /* ST1 {Vt.4S}, [Xn] → 0100_1100_0000_0000_1010_00 Rn Rt
     * encoding: 0x4C00A800 | Rn<<5 | Rt                      */
    uint32_t enc = 0x4C00A800 | ((xn & 0x1F) << 5) | (vt & 0x1F);
    codebuf_emit_u32(cb, enc);
}

/* ADD Vd.4S, Vn.4S, Vm.4S — 32-bit integer element-wise add */
static void neon_emit_add_4s(codebuf_t *cb, uint8_t vd, uint8_t vn, uint8_t vm)
{
    /* 0100_1110_1010_0000 Vm 1000_01 Vn Vd
     * size=10 (32-bit), Q=1 (128-bit)
     * encoding: 0x4EA08400 | Vm<<16 | Vn<<5 | Vd             */
    uint32_t enc = 0x4EA08400 | ((vm & 0x1F) << 16) |
                   ((vn & 0x1F) << 5) | (vd & 0x1F);
    codebuf_emit_u32(cb, enc);
}

/* SUB Vd.4S, Vn.4S, Vm.4S — 32-bit integer element-wise sub */
static void neon_emit_sub_4s(codebuf_t *cb, uint8_t vd, uint8_t vn, uint8_t vm)
{
    /* 0110_1110_1010_0000 Vm 1000_01 Vn Vd
     * encoding: 0x6EA08400 | Vm<<16 | Vn<<5 | Vd             */
    uint32_t enc = 0x6EA08400 | ((vm & 0x1F) << 16) |
                   ((vn & 0x1F) << 5) | (vd & 0x1F);
    codebuf_emit_u32(cb, enc);
}

/* MUL Vd.4S, Vn.4S, Vm.4S — 32-bit integer element-wise mul */
static void neon_emit_mul_4s(codebuf_t *cb, uint8_t vd, uint8_t vn, uint8_t vm)
{
    /* 0100_1110_1010_0000 Vm 1001_11 Vn Vd
     * encoding: 0x4EA09C00 | Vm<<16 | Vn<<5 | Vd             */
    uint32_t enc = 0x4EA09C00 | ((vm & 0x1F) << 16) |
                   ((vn & 0x1F) << 5) | (vd & 0x1F);
    codebuf_emit_u32(cb, enc);
}

/* FADD Vd.4S, Vn.4S, Vm.4S — 32-bit FP element-wise add */
static void neon_emit_fadd_4s(codebuf_t *cb, uint8_t vd, uint8_t vn, uint8_t vm)
{
    /* 0100_1110_0010_0000 Vm 1101_01 Vn Vd
     * encoding: 0x4E20D400 | Vm<<16 | Vn<<5 | Vd             */
    uint32_t enc = 0x4E20D400 | ((vm & 0x1F) << 16) |
                   ((vn & 0x1F) << 5) | (vd & 0x1F);
    codebuf_emit_u32(cb, enc);
}

/* FMUL Vd.4S, Vn.4S, Vm.4S — 32-bit FP element-wise mul */
static void neon_emit_fmul_4s(codebuf_t *cb, uint8_t vd, uint8_t vn, uint8_t vm)
{
    /* 0110_1110_0010_0000 Vm 1101_11 Vn Vd
     * encoding: 0x6E20DC00 | Vm<<16 | Vn<<5 | Vd             */
    uint32_t enc = 0x6E20DC00 | ((vm & 0x1F) << 16) |
                   ((vn & 0x1F) << 5) | (vd & 0x1F);
    codebuf_emit_u32(cb, enc);
}

/* FDIV Vd.4S, Vn.4S, Vm.4S — 32-bit FP element-wise div */
static void neon_emit_fdiv_4s(codebuf_t *cb, uint8_t vd, uint8_t vn, uint8_t vm)
{
    /* 0110_1110_0010_0000 Vm 1111_11 Vn Vd
     * encoding: 0x6E20FC00 | Vm<<16 | Vn<<5 | Vd             */
    uint32_t enc = 0x6E20FC00 | ((vm & 0x1F) << 16) |
                   ((vn & 0x1F) << 5) | (vd & 0x1F);
    codebuf_emit_u32(cb, enc);
}

/* FMLA Vd.4S, Vn.4S, Vm.4S — Fused multiply-accumulate */
static void neon_emit_fmla_4s(codebuf_t *cb, uint8_t vd, uint8_t vn, uint8_t vm)
{
    /* 0100_1110_0010_0000 Vm 1100_11 Vn Vd
     * encoding: 0x4E20CC00 | Vm<<16 | Vn<<5 | Vd             */
    uint32_t enc = 0x4E20CC00 | ((vm & 0x1F) << 16) |
                   ((vn & 0x1F) << 5) | (vd & 0x1F);
    codebuf_emit_u32(cb, enc);
}

/* SMIN Vd.4S, Vn.4S, Vm.4S — signed integer min */
static void neon_emit_smin_4s(codebuf_t *cb, uint8_t vd, uint8_t vn, uint8_t vm)
{
    /* 0100_1110_1010_0000 Vm 0110_11 Vn Vd
     * encoding: 0x4EA06C00 | Vm<<16 | Vn<<5 | Vd             */
    uint32_t enc = 0x4EA06C00 | ((vm & 0x1F) << 16) |
                   ((vn & 0x1F) << 5) | (vd & 0x1F);
    codebuf_emit_u32(cb, enc);
}

/* SMAX Vd.4S, Vn.4S, Vm.4S — signed integer max */
static void neon_emit_smax_4s(codebuf_t *cb, uint8_t vd, uint8_t vn, uint8_t vm)
{
    /* 0100_1110_1010_0000 Vm 0110_01 Vn Vd
     * encoding: 0x4EA06400 | Vm<<16 | Vn<<5 | Vd             */
    uint32_t enc = 0x4EA06400 | ((vm & 0x1F) << 16) |
                   ((vn & 0x1F) << 5) | (vd & 0x1F);
    codebuf_emit_u32(cb, enc);
}

/* ADDV Sd, Vn.4S — horizontal reduce (sum all 4 lanes → scalar) */
static void neon_emit_addv_4s(codebuf_t *cb, uint8_t vd, uint8_t vn)
{
    /* 0100_1110_1011_0001_1011_10 Vn Vd
     * encoding: 0x4EB1B800 | Vn<<5 | Vd                      */
    uint32_t enc = 0x4EB1B800 | ((vn & 0x1F) << 5) | (vd & 0x1F);
    codebuf_emit_u32(cb, enc);
}

/* DUP Vd.4S, Wn — broadcast scalar GPR to all 4 lanes */
static void neon_emit_dup_4s_gpr(codebuf_t *cb, uint8_t vd, arm_reg_t xn)
{
    /* DUP Vd.4S, Wn → 0100_1110_0000_0100_0000_11 Rn Vd
     * encoding: 0x4E040C00 | Rn<<5 | Vd                      */
    uint32_t enc = 0x4E040C00 | ((xn & 0x1F) << 5) | (vd & 0x1F);
    codebuf_emit_u32(cb, enc);
}

/* TBL Vd.16B, {Vn.16B}, Vm.16B — table lookup (permute) */
static void neon_emit_tbl_16b(codebuf_t *cb, uint8_t vd, uint8_t vn, uint8_t vm)
{
    /* 0100_1110_000 Vm 0000_00 Vn Vd
     * encoding: 0x4E000000 | Vm<<16 | Vn<<5 | Vd             */
    uint32_t enc = 0x4E000000 | ((vm & 0x1F) << 16) |
                   ((vn & 0x1F) << 5) | (vd & 0x1F);
    codebuf_emit_u32(cb, enc);
}

/* ═══════════════════════════════════════════════════════
 * x86_64 AVX (SIMD) Instruction Emitters
 * ═══════════════════════════════════════════════════════
 * VEX-encoded 128-bit SSE/AVX instructions.
 * Uses XMM0-XMM15 via VEX prefix.
 *
 * 3-byte VEX prefix for XMM regs: C4 [R/X/B/mmmmm] [W/vvvv/L/pp]
 * 2-byte VEX prefix: C5 [R/vvvv/L/pp]
 * For XMM0-XMM7 with 128-bit: C5 [1 vvvv 0 pp]
 *   R=1 (not extended), vvvv = ~src2, L=0 (128-bit), pp = encoding
 */

/* Helper: 2-byte VEX prefix. vvvv_field = XMM register for src2 (inverted). */
static void x86_emit_vex2(codebuf_t *cb, uint8_t vvvv, uint8_t L, uint8_t pp)
{
    /* C5 [R/vvvv/L/pp] — R=1 for XMM0-7 */
    uint8_t byte2 = 0x80 | ((~vvvv & 0x0F) << 3) | ((L & 1) << 2) | (pp & 3);
    codebuf_emit_byte(cb, 0xC5);
    codebuf_emit_byte(cb, byte2);
}

/* VMOVAPS XMMd, [base] — aligned 128-bit load */
static void avx_emit_vmovaps_load(codebuf_t *cb, uint8_t xmm_dst, x86_reg_t base)
{
    /* VEX.128.0F 28 /r → VMOVAPS xmm1, xmm2/m128
     * C5 F8 28 modrm                                         */
    x86_emit_vex2(cb, 0, 0, 0);  /* pp=00 (no prefix), vvvv=0 (unused) */
    codebuf_emit_byte(cb, 0x28);
    codebuf_emit_byte(cb, ((xmm_dst & 7) << 3) | (base & 7));
}

/* VMOVAPS [base], XMMs — aligned 128-bit store */
static void avx_emit_vmovaps_store(codebuf_t *cb, x86_reg_t base, uint8_t xmm_src)
{
    /* VEX.128.0F 29 /r → VMOVAPS xmm2/m128, xmm1
     * C5 F8 29 modrm                                         */
    x86_emit_vex2(cb, 0, 0, 0);
    codebuf_emit_byte(cb, 0x29);
    codebuf_emit_byte(cb, ((xmm_src & 7) << 3) | (base & 7));
}

/* VADDPS XMMd, XMMs1, XMMs2 — 4×f32 add */
static void avx_emit_vaddps(codebuf_t *cb, uint8_t dst, uint8_t src1, uint8_t src2)
{
    /* VEX.128.0F 58 /r → VADDPS xmm1, xmm2, xmm3
     * C5 [vvvv=src1] 58 [dst,src2]                           */
    x86_emit_vex2(cb, src1, 0, 0);
    codebuf_emit_byte(cb, 0x58);
    codebuf_emit_byte(cb, 0xC0 | ((dst & 7) << 3) | (src2 & 7));
}

/* VSUBPS XMMd, XMMs1, XMMs2 — 4×f32 sub */
static void avx_emit_vsubps(codebuf_t *cb, uint8_t dst, uint8_t src1, uint8_t src2)
{
    x86_emit_vex2(cb, src1, 0, 0);
    codebuf_emit_byte(cb, 0x5C);
    codebuf_emit_byte(cb, 0xC0 | ((dst & 7) << 3) | (src2 & 7));
}

/* VMULPS XMMd, XMMs1, XMMs2 — 4×f32 mul */
static void avx_emit_vmulps(codebuf_t *cb, uint8_t dst, uint8_t src1, uint8_t src2)
{
    x86_emit_vex2(cb, src1, 0, 0);
    codebuf_emit_byte(cb, 0x59);
    codebuf_emit_byte(cb, 0xC0 | ((dst & 7) << 3) | (src2 & 7));
}

/* VDIVPS XMMd, XMMs1, XMMs2 — 4×f32 div */
static void avx_emit_vdivps(codebuf_t *cb, uint8_t dst, uint8_t src1, uint8_t src2)
{
    x86_emit_vex2(cb, src1, 0, 0);
    codebuf_emit_byte(cb, 0x5E);
    codebuf_emit_byte(cb, 0xC0 | ((dst & 7) << 3) | (src2 & 7));
}

/* VMINPS XMMd, XMMs1, XMMs2 — 4×f32 min */
static void avx_emit_vminps(codebuf_t *cb, uint8_t dst, uint8_t src1, uint8_t src2)
{
    x86_emit_vex2(cb, src1, 0, 0);
    codebuf_emit_byte(cb, 0x5D);
    codebuf_emit_byte(cb, 0xC0 | ((dst & 7) << 3) | (src2 & 7));
}

/* VMAXPS XMMd, XMMs1, XMMs2 — 4×f32 max */
static void avx_emit_vmaxps(codebuf_t *cb, uint8_t dst, uint8_t src1, uint8_t src2)
{
    x86_emit_vex2(cb, src1, 0, 0);
    codebuf_emit_byte(cb, 0x5F);
    codebuf_emit_byte(cb, 0xC0 | ((dst & 7) << 3) | (src2 & 7));
}

/* VBROADCASTSS XMMd, XMMs — broadcast lowest f32 to all lanes */
static void avx_emit_vbroadcastss(codebuf_t *cb, uint8_t dst, uint8_t src)
{
    /* VEX.128.66.0F38 18 /r — requires 3-byte VEX for 0F38 map
     * C4 E2 79 18 modrm                                      */
    codebuf_emit_byte(cb, 0xC4);
    codebuf_emit_byte(cb, 0xE2);  /* R=1, X=1, B=1, mmmmm=00010 (0F38) */
    codebuf_emit_byte(cb, 0x79);  /* W=0, vvvv=1111 (unused), L=0, pp=01 (66) */
    codebuf_emit_byte(cb, 0x18);
    codebuf_emit_byte(cb, 0xC0 | ((dst & 7) << 3) | (src & 7));
}

/* ═══════════════════════════════════════════════════════
 * x86_64 AVX-512 (EVEX) Instruction Emitters — FIX A5
 * ═══════════════════════════════════════════════════════
 * EVEX-encoded 512-bit instructions for ZMM0-ZMM31.
 * 4-byte EVEX prefix: 62h [P0] [P1] [P2] opcode modrm ...
 *
 *  P0 = R:X:B:R':0:0:m:m   (m=01 for 0F map)
 *  P1 = W:vvvv:1:pp         (pp=00 no prefix)
 *  P2 = z:L'L:b:V':aaa      (L'L=10 for 512-bit)
 */

/* Helper: emit a 4-byte EVEX prefix for 512-bit reg-reg ops (0F map). */
static void x86_emit_evex_512(codebuf_t *cb, uint8_t dst, uint8_t src1, uint8_t src2)
{
    /* P0: R=!dst[3], X=!src2[4], B=!src2[3], R'=!dst[4], mm=01 */
    uint8_t p0 = 0x01;                          /* mm = 01 (0F map) */
    if (!(dst  & 0x08)) p0 |= 0x80;  /* R  */
    else p0 &= ~0x80;
    if (!(src2 & 0x10)) p0 |= 0x40;  /* X  */
    else p0 &= ~0x40;
    if (!(src2 & 0x08)) p0 |= 0x20;  /* B  */
    else p0 &= ~0x20;
    if (!(dst  & 0x10)) p0 |= 0x10;  /* R' */
    else p0 &= ~0x10;

    /* P1: W=0, vvvv=~src1[3:0], 1, pp=00 */
    uint8_t p1 = 0x04 | ((~src1 & 0x0F) << 3);  /* bit2=1 fixed */

    /* P2: z=0, L'L=10 (512-bit), b=0, V'=~src1[4], aaa=000 */
    uint8_t p2 = 0x40;  /* L'L = 10 → 512-bit */
    if (!(src1 & 0x10)) p2 |= 0x08;  /* V' */

    codebuf_emit_byte(cb, 0x62);
    codebuf_emit_byte(cb, p0);
    codebuf_emit_byte(cb, p1);
    codebuf_emit_byte(cb, p2);
}

/* Helper: emit EVEX prefix for 512-bit memory ops (base reg, no VSIB). */
static void x86_emit_evex_512_mem(codebuf_t *cb, uint8_t zmm, x86_reg_t base)
{
    uint8_t p0 = 0x01;
    if (!(zmm  & 0x08)) p0 |= 0x80;
    if (!(base & 0x10)) p0 |= 0x40;  /* X (index, not used) */
    if (!(base & 0x08)) p0 |= 0x20;  /* B */
    if (!(zmm  & 0x10)) p0 |= 0x10;  /* R' */

    uint8_t p1 = 0x7C;  /* W=0, vvvv=1111 (unused), 1, pp=00 */
    uint8_t p2 = 0x48;  /* z=0, L'L=10, b=0, V'=1, aaa=000 */

    codebuf_emit_byte(cb, 0x62);
    codebuf_emit_byte(cb, p0);
    codebuf_emit_byte(cb, p1);
    codebuf_emit_byte(cb, p2);
}

/* VMOVAPS ZMMd, [base+disp32] — aligned 512-bit load (spill reload) */
static void evex_emit_vmovaps_load(codebuf_t *cb, uint8_t zmm_dst, x86_reg_t base, int32_t disp)
{
    x86_emit_evex_512_mem(cb, zmm_dst, base);
    codebuf_emit_byte(cb, 0x28);  /* VMOVAPS load */
    /* ModRM: [base+disp32] → mod=10, reg=zmm_dst[2:0], rm=base[2:0] */
    codebuf_emit_byte(cb, 0x80 | ((zmm_dst & 7) << 3) | (base & 7));
    if ((base & 7) == 4) codebuf_emit_byte(cb, 0x24);  /* SIB for RSP-based */
    codebuf_emit_i32(cb, disp);
}

/* VMOVAPS [base+disp32], ZMMs — aligned 512-bit store (spill store) */
static void evex_emit_vmovaps_store(codebuf_t *cb, x86_reg_t base, int32_t disp, uint8_t zmm_src)
{
    x86_emit_evex_512_mem(cb, zmm_src, base);
    codebuf_emit_byte(cb, 0x29);  /* VMOVAPS store */
    codebuf_emit_byte(cb, 0x80 | ((zmm_src & 7) << 3) | (base & 7));
    if ((base & 7) == 4) codebuf_emit_byte(cb, 0x24);
    codebuf_emit_i32(cb, disp);
}

/* VADDPS ZMMd, ZMMs1, ZMMs2 — 16×f32 add */
static void evex_emit_vaddps(codebuf_t *cb, uint8_t dst, uint8_t src1, uint8_t src2)
{
    x86_emit_evex_512(cb, dst, src1, src2);
    codebuf_emit_byte(cb, 0x58);
    codebuf_emit_byte(cb, 0xC0 | ((dst & 7) << 3) | (src2 & 7));
}

/* VMULPS ZMMd, ZMMs1, ZMMs2 — 16×f32 mul */
static void evex_emit_vmulps(codebuf_t *cb, uint8_t dst, uint8_t src1, uint8_t src2)
{
    x86_emit_evex_512(cb, dst, src1, src2);
    codebuf_emit_byte(cb, 0x59);
    codebuf_emit_byte(cb, 0xC0 | ((dst & 7) << 3) | (src2 & 7));
}

/* VSUBPS ZMMd, ZMMs1, ZMMs2 — 16×f32 sub */
static void evex_emit_vsubps(codebuf_t *cb, uint8_t dst, uint8_t src1, uint8_t src2)
{
    x86_emit_evex_512(cb, dst, src1, src2);
    codebuf_emit_byte(cb, 0x5C);
    codebuf_emit_byte(cb, 0xC0 | ((dst & 7) << 3) | (src2 & 7));
}

/* ═══════════════════════════════════════════════════════
 * Virtual register → SIMD register mapping
 * ═══════════════════════════════════════════════════════ */

static uint8_t vreg_to_neon(uint32_t vreg)
{
    /* Map virtual regs to V0-V15 (NEON 128-bit) */
    if (vreg < 16) return (uint8_t)vreg;
    return 0;
}

static uint8_t vreg_to_xmm(uint32_t vreg)
{
    /* FIX A5: Map virtual regs to XMM/YMM/ZMM 0-31
     * Caller decides 128/256/512 via instruction encoding (VEX vs EVEX). */
    if (vreg < 32) return (uint8_t)vreg;
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * codegen_emit_full2 – Complete Q-IR Code Generation
 * ═══════════════════════════════════════════════════════ */

int codegen_emit_full2(codebuf_t *cb, const q_instruction_t *instrs,
                       uint32_t count, target_arch_t arch,
                       const codegen_rt_t *rt)
{
    cg_label_t labels[CG_MAX_LABELS];
    cg_fixup_t fixups[CG_MAX_FIXUPS];
    uint32_t label_count = 0;
    uint32_t fixup_count = 0;

    /* Check if we need a stack frame */
    int needs_frame = 0;
    for (uint32_t i = 0; i < count; i++) {
        q_opcode_t op = instrs[i].opcode;
        if (op == Q_CALL || op == Q_CALL_FUNC || op == Q_PRINT ||
            op == Q_INPUT || op == Q_ALLOC || op == Q_FREE ||
            op == Q_STR_LEN || op == Q_STR_GET || op == Q_STR_CAT ||
            op == Q_STR_EQ || op == Q_PRINT_STR || op == Q_I_TO_STR ||
            op == Q_STR_TO_I || op == Q_EXIT ||
            op == Q_FILE_OPEN || op == Q_FILE_READ || op == Q_FILE_WRITE ||
            op == Q_FILE_CLOSE || op == Q_FILE_WRITE_BYTE ||
            op == Q_ARR_NEW || op == Q_ARR_LEN || op == Q_ARR_GET ||
            op == Q_ARR_SET || op == Q_ARR_PUSH) {
            needs_frame = 1;
            break;
        }
    }

    /* ── Prologue ──────────────────────────────────────── */
    if (needs_frame) {
        if (arch == ARCH_ARM64) {
            arm64_emit_stp_pre(cb, ARM_FP, ARM_LR, ARM_SP, -16);
        } else {
            x86_emit_push(cb, X86_RBP);
            x86_emit_mov_rr(cb, X86_RBP, X86_RSP);
        }
    }

    for (uint32_t i = 0; i < count; i++) {
        const q_instruction_t *ins = &instrs[i];

        /* ══════════ ARM64 ══════════ */
        if (arch == ARCH_ARM64) {
            arm_reg_t rd  = (ins->dest.type == OPERAND_VREG)
                            ? vreg_to_arm(ins->dest.vreg) : ARM_X0;
            arm_reg_t rs1 = (ins->src1.type == OPERAND_VREG)
                            ? vreg_to_arm(ins->src1.vreg) : ARM_X0;
            arm_reg_t rs2 = (ins->src2.type == OPERAND_VREG)
                            ? vreg_to_arm(ins->src2.vreg) : ARM_X1;

            switch (ins->opcode) {

            /* ── Data movement ─────────────────────────── */
            case Q_NOP:   arm64_emit_nop(cb); break;
            case Q_LOAD:
                if (ins->src1.type == OPERAND_IMM)
                    arm64_emit_movz_imm64(cb, rd, ins->src1.imm);
                else if (ins->src1.type == OPERAND_STR && rt && rt->module) {
                    uint32_t sidx = ins->src1.str_idx;
                    if (sidx < rt->module->string_count) {
                        int64_t ptr = (int64_t)(intptr_t)rt->module->strings[sidx];
                        arm64_emit_movz_imm64(cb, rd, ptr);
                    }
                }
                break;
            case Q_STORE:
                arm64_emit_mov_rr(cb, rd, rs1);
                break;
            case Q_MOVE:
                arm64_emit_mov_rr(cb, rd, rs1);
                break;

            /* ── Arithmetic ────────────────────────────── */
            case Q_ADD:  arm64_emit_add_rrr(cb, rd, rs1, rs2);  break;
            case Q_SUB:  arm64_emit_sub_rrr(cb, rd, rs1, rs2);  break;
            case Q_MUL:  arm64_emit_mul_rrr(cb, rd, rs1, rs2);  break;
            case Q_DIV:  arm64_emit_sdiv_rrr(cb, rd, rs1, rs2); break;
            case Q_MOD: {
                arm64_emit_sdiv_rrr(cb, ARM_X16, rs1, rs2);
                arm64_emit_mul_rrr(cb, ARM_X16, ARM_X16, rs2);
                arm64_emit_sub_rrr(cb, rd, rs1, ARM_X16);
                break;
            }

            /* ── Comparison ────────────────────────────── */
            case Q_CMP_EQ:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                arm64_emit_cset_eq(cb, rd);
                break;
            case Q_CMP_GT:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                arm64_emit_cset_gt(cb, rd);
                break;
            case Q_CMP_LT:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                arm64_emit_cset_lt(cb, rd);
                break;
            case Q_CMP_GE:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                codebuf_emit_u32(cb, 0x9A9FB7E0 | (rd & 0x1F));
                break;
            case Q_CMP_LE:
                arm64_emit_cmp_rr(cb, rs1, rs2);
                codebuf_emit_u32(cb, 0x9A9FC7E0 | (rd & 0x1F));
                break;

            /* ── Bitwise ───────────────────────────────── */
            case Q_AND:  arm64_emit_and_rrr(cb, rd, rs1, rs2); break;
            case Q_OR:   arm64_emit_orr_rrr(cb, rd, rs1, rs2); break;
            case Q_XOR:  arm64_emit_eor_rrr(cb, rd, rs1, rs2); break;
            case Q_SHL:  arm64_emit_lsl_rrr(cb, rd, rs1, rs2); break;
            case Q_SHR:  arm64_emit_asr_rrr(cb, rd, rs1, rs2); break;

            /* ── Control flow ──────────────────────────── */
            case Q_LABEL:
                if (label_count < CG_MAX_LABELS) {
                    labels[label_count].label_id = ins->patch_id;
                    labels[label_count].offset   = cb->len;
                    label_count++;
                }
                break;

            case Q_JUMP:
                if (ins->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len;
                    fixups[fixup_count].target_label = ins->src1.label;
                    fixups[fixup_count].is_cond      = 0;
                    fixup_count++;
                }
                arm64_emit_b_imm26(cb, 0);
                break;

            case Q_JUMP_IF:
                if (ins->src1.type == OPERAND_VREG) {
                    codebuf_emit_u32(cb, 0xF100001F | ((rs1 & 0x1F) << 5));
                }
                if (ins->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len;
                    fixups[fixup_count].target_label = ins->src2.label;
                    fixups[fixup_count].is_cond      = 1;
                    fixup_count++;
                }
                arm64_emit_bne_imm19(cb, 0);
                break;

            case Q_JUMP_IF_NOT:
                if (ins->src1.type == OPERAND_VREG) {
                    codebuf_emit_u32(cb, 0xF100001F | ((rs1 & 0x1F) << 5));
                }
                if (ins->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len;
                    fixups[fixup_count].target_label = ins->src2.label;
                    fixups[fixup_count].is_cond      = 1;
                    fixup_count++;
                }
                arm64_emit_beq_imm19(cb, 0);
                break;

            case Q_CALL:
                if (ins->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len;
                    fixups[fixup_count].target_label = ins->src1.label;
                    fixups[fixup_count].is_cond      = 0;
                    fixup_count++;
                }
                arm64_emit_bl_imm26(cb, 0);
                break;

            case Q_CALL_FUNC:
                /* Call by function index: BL to function's label offset */
                if (ins->src1.type == OPERAND_FUNC_IDX && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len;
                    fixups[fixup_count].target_label = ins->src1.func_idx;
                    fixups[fixup_count].is_cond      = 0;
                    fixup_count++;
                }
                arm64_emit_bl_imm26(cb, 0);
                break;

            case Q_RET:
                if (ins->src1.type == OPERAND_VREG && rs1 != ARM_X0)
                    arm64_emit_mov_rr(cb, ARM_X0, rs1);
                if (needs_frame)
                    arm64_emit_ldp_post(cb, ARM_FP, ARM_LR, ARM_SP, 16);
                arm64_emit_ret(cb);
                break;

            /* ── I/O via intrinsics ────────────────────── */
            case Q_PRINT:
                if (rt && rt->intrinsic_addrs[INTRINSIC_PRINT])
                    arm64_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_PRINT], rs1, rd);
                break;
            case Q_INPUT:
                if (rt && rt->intrinsic_addrs[INTRINSIC_INPUT])
                    arm64_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_INPUT], ARM_X0, rd);
                break;
            case Q_PRINT_STR:
                if (rt && rt->intrinsic_addrs[INTRINSIC_PRINT_RAW])
                    arm64_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_PRINT_RAW], rs1, rd);
                break;

            /* ── Memory management ─────────────────────── */
            case Q_ALLOC:
                if (rt && rt->intrinsic_addrs[INTRINSIC_ALLOC])
                    arm64_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_ALLOC], rs1, rd);
                break;
            case Q_FREE:
                if (rt && rt->intrinsic_addrs[INTRINSIC_FREE])
                    arm64_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_FREE], rs1, rd);
                break;

            /* ── Byte/Word memory access ───────────────── */
            case Q_LOAD_BYTE:
                arm64_emit_ldrb_reg(cb, rd, rs1, rs2);
                break;
            case Q_STORE_BYTE: {
                arm_reg_t val = (ins->dest.type == OPERAND_VREG)
                    ? vreg_to_arm(ins->dest.vreg) : ARM_X0;
                arm64_emit_strb_reg(cb, val, rs1, rs2);
                break;
            }
            case Q_LOAD_WORD:
                arm64_emit_ldr_reg(cb, rd, rs1, rs2);
                break;
            case Q_STORE_WORD: {
                arm_reg_t val = (ins->dest.type == OPERAND_VREG)
                    ? vreg_to_arm(ins->dest.vreg) : ARM_X0;
                arm64_emit_str_reg(cb, val, rs1, rs2);
                break;
            }

            /* ── String operations ─────────────────────── */
            case Q_STR_LEN:
                if (rt && rt->intrinsic_addrs[INTRINSIC_STRLEN])
                    arm64_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_STRLEN], rs1, rd);
                break;
            case Q_STR_GET:
                if (rt && rt->intrinsic_addrs[INTRINSIC_STR_GET])
                    arm64_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_STR_GET], rs1, rs2, rd);
                break;
            case Q_STR_CAT:
                if (rt && rt->intrinsic_addrs[INTRINSIC_STR_CAT])
                    arm64_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_STR_CAT], rs1, rs2, rd);
                break;
            case Q_STR_EQ:
                if (rt && rt->intrinsic_addrs[INTRINSIC_STR_EQ])
                    arm64_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_STR_EQ], rs1, rs2, rd);
                break;

            /* ── File I/O ──────────────────────────────── */
            case Q_FILE_OPEN:
                if (rt && rt->intrinsic_addrs[INTRINSIC_FILE_OPEN])
                    arm64_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_FILE_OPEN], rs1, rs2, rd);
                break;
            case Q_FILE_READ:
                if (rt && rt->intrinsic_addrs[INTRINSIC_FILE_READ])
                    arm64_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_FILE_READ], rs1, rd);
                break;
            case Q_FILE_WRITE:
                if (rt && rt->intrinsic_addrs[INTRINSIC_FILE_WRITE])
                    arm64_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_FILE_WRITE], rs1, rs2, rd);
                break;
            case Q_FILE_CLOSE:
                if (rt && rt->intrinsic_addrs[INTRINSIC_FILE_CLOSE])
                    arm64_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_FILE_CLOSE], rs1, rd);
                break;
            case Q_FILE_WRITE_BYTE:
                if (rt && rt->intrinsic_addrs[INTRINSIC_FILE_WRITE_BYTE])
                    arm64_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_FILE_WRITE_BYTE], rs1, rs2, rd);
                break;

            /* ── Array operations ──────────────────────── */
            case Q_ARR_NEW:
                if (rt && rt->intrinsic_addrs[INTRINSIC_ARR_NEW])
                    arm64_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_ARR_NEW], rs1, rd);
                break;
            case Q_ARR_LEN:
                if (rt && rt->intrinsic_addrs[INTRINSIC_ARR_LEN])
                    arm64_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_ARR_LEN], rs1, rd);
                break;
            case Q_ARR_GET:
                if (rt && rt->intrinsic_addrs[INTRINSIC_ARR_GET])
                    arm64_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_ARR_GET], rs1, rs2, rd);
                break;
            case Q_ARR_SET:
                if (rt && rt->intrinsic_addrs[INTRINSIC_ARR_SET]) {
                    arm_reg_t val = (ins->dest.type == OPERAND_VREG)
                        ? vreg_to_arm(ins->dest.vreg) : ARM_X0;
                    arm64_emit_call_intrinsic_3(cb,
                        rt->intrinsic_addrs[INTRINSIC_ARR_SET], rs1, rs2, val, rd);
                }
                break;
            case Q_ARR_PUSH:
                if (rt && rt->intrinsic_addrs[INTRINSIC_ARR_PUSH])
                    arm64_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_ARR_PUSH], rs1, rs2, rd);
                break;

            /* ── System ────────────────────────────────── */
            case Q_EXIT:
                if (rt && rt->intrinsic_addrs[INTRINSIC_EXIT])
                    arm64_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_EXIT], rs1, rd);
                break;
            case Q_I_TO_STR:
                if (rt && rt->intrinsic_addrs[INTRINSIC_I_TO_STR])
                    arm64_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_I_TO_STR], rs1, rd);
                break;
            case Q_STR_TO_I:
                if (rt && rt->intrinsic_addrs[INTRINSIC_STR_TO_I])
                    arm64_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_STR_TO_I], rs1, rd);
                break;

            /* ── Globals ───────────────────────────────── */
            case Q_LOAD_GLOBAL:
                if (rt && rt->globals) {
                    /* Load address of globals array, index into it */
                    arm64_emit_movz_imm64(cb, ARM_X16,
                        (int64_t)(uintptr_t)rt->globals);
                    /* rs1 has the index (imm or vreg) */
                    if (ins->src1.type == OPERAND_IMM) {
                        arm64_emit_movz_imm64(cb, ARM_X17, ins->src1.imm);
                    } else {
                        arm64_emit_mov_rr(cb, ARM_X17, rs1);
                    }
                    arm64_emit_ldr_reg(cb, rd, ARM_X16, ARM_X17);
                }
                break;
            case Q_STORE_GLOBAL:
                if (rt && rt->globals) {
                    arm64_emit_movz_imm64(cb, ARM_X16,
                        (int64_t)(uintptr_t)rt->globals);
                    if (ins->src1.type == OPERAND_IMM) {
                        arm64_emit_movz_imm64(cb, ARM_X17, ins->src1.imm);
                    } else {
                        arm64_emit_mov_rr(cb, ARM_X17, rs1);
                    }
                    arm64_emit_str_reg(cb, rs2, ARM_X16, ARM_X17);
                }
                break;

            /* ── Args ──────────────────────────────────── */
            case Q_GET_ARG:
                if (rt && rt->args) {
                    arm64_emit_movz_imm64(cb, ARM_X16,
                        (int64_t)(uintptr_t)rt->args);
                    if (ins->src1.type == OPERAND_IMM) {
                        arm64_emit_movz_imm64(cb, ARM_X17, ins->src1.imm);
                    } else {
                        arm64_emit_mov_rr(cb, ARM_X17, rs1);
                    }
                    arm64_emit_ldr_reg(cb, rd, ARM_X16, ARM_X17);
                }
                break;
            case Q_ARG_COUNT:
                if (rt)
                    arm64_emit_movz_imm64(cb, rd, (int64_t)rt->arg_count);
                else
                    arm64_emit_movz_imm64(cb, rd, 0);
                break;

            case Q_HALT:
                arm64_emit_mov_imm16(cb, ARM_X0, 0);
                arm64_emit_ret(cb);
                break;

            case Q_PATCH_POINT:
                arm64_emit_nop(cb);
                break;

            /* ── SIMD / NEON Vector Operations ─────────── */
            case Q_VLOAD: {
                uint8_t vd = vreg_to_neon(ins->dest.vreg);
                arm_reg_t base = (ins->src1.type == OPERAND_VREG)
                    ? vreg_to_arm(ins->src1.vreg) : ARM_X0;
                neon_emit_ld1_4s(cb, vd, base);
                break;
            }
            case Q_VSTORE: {
                uint8_t vs = vreg_to_neon(ins->src1.vreg);
                arm_reg_t base = (ins->dest.type == OPERAND_VREG)
                    ? vreg_to_arm(ins->dest.vreg) : ARM_X0;
                neon_emit_st1_4s(cb, vs, base);
                break;
            }
            case Q_VADD: {
                uint8_t vd = vreg_to_neon(ins->dest.vreg);
                uint8_t vn = vreg_to_neon(ins->src1.vreg);
                uint8_t vm = vreg_to_neon(ins->src2.vreg);
                neon_emit_add_4s(cb, vd, vn, vm);
                break;
            }
            case Q_VSUB: {
                uint8_t vd = vreg_to_neon(ins->dest.vreg);
                uint8_t vn = vreg_to_neon(ins->src1.vreg);
                uint8_t vm = vreg_to_neon(ins->src2.vreg);
                neon_emit_sub_4s(cb, vd, vn, vm);
                break;
            }
            case Q_VMUL: {
                uint8_t vd = vreg_to_neon(ins->dest.vreg);
                uint8_t vn = vreg_to_neon(ins->src1.vreg);
                uint8_t vm = vreg_to_neon(ins->src2.vreg);
                neon_emit_mul_4s(cb, vd, vn, vm);
                break;
            }
            case Q_VFMA: {
                uint8_t vd = vreg_to_neon(ins->dest.vreg);
                uint8_t vn = vreg_to_neon(ins->src1.vreg);
                uint8_t vm = vreg_to_neon(ins->src2.vreg);
                neon_emit_fmla_4s(cb, vd, vn, vm);
                break;
            }
            case Q_VDIV: {
                uint8_t vd = vreg_to_neon(ins->dest.vreg);
                uint8_t vn = vreg_to_neon(ins->src1.vreg);
                uint8_t vm = vreg_to_neon(ins->src2.vreg);
                neon_emit_fdiv_4s(cb, vd, vn, vm);
                break;
            }
            case Q_VMIN: {
                uint8_t vd = vreg_to_neon(ins->dest.vreg);
                uint8_t vn = vreg_to_neon(ins->src1.vreg);
                uint8_t vm = vreg_to_neon(ins->src2.vreg);
                neon_emit_smin_4s(cb, vd, vn, vm);
                break;
            }
            case Q_VMAX: {
                uint8_t vd = vreg_to_neon(ins->dest.vreg);
                uint8_t vn = vreg_to_neon(ins->src1.vreg);
                uint8_t vm = vreg_to_neon(ins->src2.vreg);
                neon_emit_smax_4s(cb, vd, vn, vm);
                break;
            }
            case Q_VREDUCE: {
                uint8_t vd = vreg_to_neon(ins->dest.vreg);
                uint8_t vn = vreg_to_neon(ins->src1.vreg);
                neon_emit_addv_4s(cb, vd, vn);
                break;
            }
            case Q_VSPLAT: {
                uint8_t vd = vreg_to_neon(ins->dest.vreg);
                arm_reg_t xn = (ins->src1.type == OPERAND_VREG)
                    ? vreg_to_arm(ins->src1.vreg) : ARM_X0;
                neon_emit_dup_4s_gpr(cb, vd, xn);
                break;
            }
            case Q_VPERM: {
                uint8_t vd = vreg_to_neon(ins->dest.vreg);
                uint8_t vn = vreg_to_neon(ins->src1.vreg);
                uint8_t vm = vreg_to_neon(ins->src2.vreg);
                neon_emit_tbl_16b(cb, vd, vn, vm);
                break;
            }

            default:
                fprintf(stderr, "[codegen/full2/arm64] unhandled opcode %d at instr %u\n",
                        ins->opcode, i);
                arm64_emit_nop(cb);
                break;
            }

        /* ══════════ x86_64 ══════════ */
        } else if (arch == ARCH_X86_64) {
            x86_reg_t rd  = (ins->dest.type == OPERAND_VREG)
                            ? vreg_to_x86(ins->dest.vreg) : X86_RAX;
            x86_reg_t rs1 = (ins->src1.type == OPERAND_VREG)
                            ? vreg_to_x86(ins->src1.vreg) : X86_RAX;
            x86_reg_t rs2 = (ins->src2.type == OPERAND_VREG)
                            ? vreg_to_x86(ins->src2.vreg) : X86_RCX;

            switch (ins->opcode) {

            /* ── Data movement ─────────────────────────── */
            case Q_NOP:   x86_emit_nop(cb); break;
            case Q_LOAD:
                if (ins->src1.type == OPERAND_IMM)
                    x86_emit_mov_reg_imm64(cb, rd, ins->src1.imm);
                else if (ins->src1.type == OPERAND_STR && rt && rt->module) {
                    uint32_t sidx = ins->src1.str_idx;
                    if (sidx < rt->module->string_count) {
                        int64_t ptr = (int64_t)(intptr_t)rt->module->strings[sidx];
                        x86_emit_mov_reg_imm64(cb, rd, ptr);
                    }
                }
                break;
            case Q_STORE:
                x86_emit_mov_rr(cb, rd, rs1);
                break;
            case Q_MOVE:
                x86_emit_mov_rr(cb, rd, rs1);
                break;

            /* ── Arithmetic ────────────────────────────── */
            case Q_ADD:
                if (rd != rs1) x86_emit_mov_rr(cb, rd, rs1);
                x86_emit_add_rr(cb, rd, rs2);
                break;
            case Q_SUB:
                if (rd != rs1) x86_emit_mov_rr(cb, rd, rs1);
                x86_emit_sub_rr(cb, rd, rs2);
                break;
            case Q_MUL:
                if (rd != rs1) x86_emit_mov_rr(cb, rd, rs1);
                x86_emit_imul_rr(cb, rd, rs2);
                break;
            case Q_DIV:
                if (rs1 != X86_RAX) x86_emit_mov_rr(cb, X86_RAX, rs1);
                x86_emit_cqo(cb);
                x86_emit_idiv(cb, rs2);
                if (rd != X86_RAX) x86_emit_mov_rr(cb, rd, X86_RAX);
                break;
            case Q_MOD:
                if (rs1 != X86_RAX) x86_emit_mov_rr(cb, X86_RAX, rs1);
                x86_emit_cqo(cb);
                x86_emit_idiv(cb, rs2);
                if (rd != X86_RDX) x86_emit_mov_rr(cb, rd, X86_RDX);
                break;

            /* ── Comparison ────────────────────────────── */
            case Q_CMP_EQ:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                x86_emit_sete(cb, rd);
                break;
            case Q_CMP_GT:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                x86_emit_setg(cb, rd);
                break;
            case Q_CMP_LT:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                x86_emit_setl(cb, rd);
                break;
            case Q_CMP_GE:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                if (rd >= X86_R8) codebuf_emit_byte(cb, 0x41);
                codebuf_emit_byte(cb, 0x0F);
                codebuf_emit_byte(cb, 0x9D);
                codebuf_emit_byte(cb, modrm(0x03, 0, rd));
                break;
            case Q_CMP_LE:
                x86_emit_cmp_rr(cb, rs1, rs2);
                x86_emit_xor_rr(cb, rd, rd);
                if (rd >= X86_R8) codebuf_emit_byte(cb, 0x41);
                codebuf_emit_byte(cb, 0x0F);
                codebuf_emit_byte(cb, 0x9E);
                codebuf_emit_byte(cb, modrm(0x03, 0, rd));
                break;

            /* ── Bitwise ───────────────────────────────── */
            case Q_AND:
                if (rd != rs1) x86_emit_mov_rr(cb, rd, rs1);
                x86_emit_and_rr(cb, rd, rs2);
                break;
            case Q_OR:
                if (rd != rs1) x86_emit_mov_rr(cb, rd, rs1);
                x86_emit_or_rr(cb, rd, rs2);
                break;
            case Q_XOR:
                if (rd != rs1) x86_emit_mov_rr(cb, rd, rs1);
                x86_emit_xor_rr(cb, rd, rs2);
                break;
            case Q_SHL:
                if (rd != rs1) x86_emit_mov_rr(cb, rd, rs1);
                if (rs2 != X86_RCX) x86_emit_mov_rr(cb, X86_RCX, rs2);
                x86_emit_shl_cl(cb, rd);
                break;
            case Q_SHR:
                if (rd != rs1) x86_emit_mov_rr(cb, rd, rs1);
                if (rs2 != X86_RCX) x86_emit_mov_rr(cb, X86_RCX, rs2);
                x86_emit_sar_cl(cb, rd);
                break;

            /* ── Control flow ──────────────────────────── */
            case Q_LABEL:
                if (label_count < CG_MAX_LABELS) {
                    labels[label_count].label_id = ins->patch_id;
                    labels[label_count].offset   = cb->len;
                    label_count++;
                }
                break;

            case Q_JUMP:
                if (ins->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len + 1;
                    fixups[fixup_count].target_label = ins->src1.label;
                    fixups[fixup_count].is_cond      = 0;
                    fixup_count++;
                }
                x86_emit_jmp_rel32(cb, 0);
                break;

            case Q_JUMP_IF:
                if (ins->src1.type == OPERAND_VREG) {
                    codebuf_emit_byte(cb, rex_w(rs1, rs1));
                    codebuf_emit_byte(cb, 0x85);
                    codebuf_emit_byte(cb, modrm(0x03, rs1, rs1));
                }
                if (ins->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len + 2;
                    fixups[fixup_count].target_label = ins->src2.label;
                    fixups[fixup_count].is_cond      = 1;
                    fixup_count++;
                }
                x86_emit_jne_rel32(cb, 0);
                break;

            case Q_JUMP_IF_NOT:
                if (ins->src1.type == OPERAND_VREG) {
                    codebuf_emit_byte(cb, rex_w(rs1, rs1));
                    codebuf_emit_byte(cb, 0x85);
                    codebuf_emit_byte(cb, modrm(0x03, rs1, rs1));
                }
                if (ins->src2.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len + 2;
                    fixups[fixup_count].target_label = ins->src2.label;
                    fixups[fixup_count].is_cond      = 1;
                    fixup_count++;
                }
                x86_emit_je_rel32(cb, 0);
                break;

            case Q_CALL:
                if (ins->src1.type == OPERAND_LABEL && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len + 1;
                    fixups[fixup_count].target_label = ins->src1.label;
                    fixups[fixup_count].is_cond      = 0;
                    fixup_count++;
                }
                x86_emit_call_rel32(cb, 0);
                break;

            case Q_CALL_FUNC:
                if (ins->src1.type == OPERAND_FUNC_IDX && fixup_count < CG_MAX_FIXUPS) {
                    fixups[fixup_count].patch_offset = cb->len + 1;
                    fixups[fixup_count].target_label = ins->src1.func_idx;
                    fixups[fixup_count].is_cond      = 0;
                    fixup_count++;
                }
                x86_emit_call_rel32(cb, 0);
                break;

            case Q_RET:
                if (ins->src1.type == OPERAND_VREG && rs1 != X86_RAX)
                    x86_emit_mov_rr(cb, X86_RAX, rs1);
                if (needs_frame) {
                    x86_emit_mov_rr(cb, X86_RSP, X86_RBP);
                    x86_emit_pop(cb, X86_RBP);
                }
                x86_emit_ret(cb);
                break;

            /* ── I/O via intrinsics ────────────────────── */
            case Q_PRINT:
                if (rt && rt->intrinsic_addrs[INTRINSIC_PRINT])
                    x86_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_PRINT], rs1, rd);
                break;
            case Q_INPUT:
                if (rt && rt->intrinsic_addrs[INTRINSIC_INPUT])
                    x86_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_INPUT], X86_RAX, rd);
                break;
            case Q_PRINT_STR:
                if (rt && rt->intrinsic_addrs[INTRINSIC_PRINT_RAW])
                    x86_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_PRINT_RAW], rs1, rd);
                break;

            /* ── Memory management ─────────────────────── */
            case Q_ALLOC:
                if (rt && rt->intrinsic_addrs[INTRINSIC_ALLOC])
                    x86_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_ALLOC], rs1, rd);
                break;
            case Q_FREE:
                if (rt && rt->intrinsic_addrs[INTRINSIC_FREE])
                    x86_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_FREE], rs1, rd);
                break;

            /* ── Byte/Word memory access ───────────────── */
            case Q_LOAD_BYTE: {
                /*  MOVZX rd, BYTE PTR [rs1 + rs2]
                 *  We compute address in RAX: rs1 + rs2, then movzx */
                x86_emit_mov_rr(cb, X86_RAX, rs1);
                x86_emit_add_rr(cb, X86_RAX, rs2);
                /* MOVZX rd, BYTE PTR [RAX] → 48 0F B6 rd [RAX] */
                uint8_t r = 0x48;
                if (rd >= X86_R8) r |= 0x04;
                codebuf_emit_byte(cb, r);
                codebuf_emit_byte(cb, 0x0F);
                codebuf_emit_byte(cb, 0xB6);
                codebuf_emit_byte(cb, modrm(0x00, rd, X86_RAX));
                break;
            }
            case Q_STORE_BYTE: {
                /* MOV BYTE PTR [rs1 + rs2], dest_low_byte */
                x86_reg_t val = (ins->dest.type == OPERAND_VREG)
                    ? vreg_to_x86(ins->dest.vreg) : X86_RAX;
                x86_emit_mov_rr(cb, X86_RAX, rs1);
                x86_emit_add_rr(cb, X86_RAX, rs2);
                /* MOV [RAX], val_byte → REX 88 /r */
                uint8_t r = 0x40;
                if (val >= X86_R8) r |= 0x04;
                codebuf_emit_byte(cb, r);
                codebuf_emit_byte(cb, 0x88);
                codebuf_emit_byte(cb, modrm(0x00, val, X86_RAX));
                break;
            }
            case Q_LOAD_WORD: {
                /* MOV rd, [rs1 + rs2*8] */
                x86_emit_mov_rr(cb, X86_RAX, rs2);
                /* SHL RAX, 3 → multiply index by 8 */
                codebuf_emit_byte(cb, 0x48);
                codebuf_emit_byte(cb, 0xC1);
                codebuf_emit_byte(cb, 0xE0);
                codebuf_emit_byte(cb, 0x03);
                x86_emit_add_rr(cb, X86_RAX, rs1);
                /* MOV rd, [RAX] → REX.W 8B /r */
                uint8_t r = 0x48;
                if (rd >= X86_R8) r |= 0x04;
                codebuf_emit_byte(cb, r);
                codebuf_emit_byte(cb, 0x8B);
                codebuf_emit_byte(cb, modrm(0x00, rd, X86_RAX));
                break;
            }
            case Q_STORE_WORD: {
                /* MOV [rs1 + rs2*8], dest */
                x86_reg_t val = (ins->dest.type == OPERAND_VREG)
                    ? vreg_to_x86(ins->dest.vreg) : X86_RAX;
                x86_emit_mov_rr(cb, X86_RAX, rs2);
                codebuf_emit_byte(cb, 0x48);
                codebuf_emit_byte(cb, 0xC1);
                codebuf_emit_byte(cb, 0xE0);
                codebuf_emit_byte(cb, 0x03);
                x86_emit_add_rr(cb, X86_RAX, rs1);
                /* MOV [RAX], val → REX.W 89 /r */
                uint8_t r = 0x48;
                if (val >= X86_R8) r |= 0x04;
                codebuf_emit_byte(cb, r);
                codebuf_emit_byte(cb, 0x89);
                codebuf_emit_byte(cb, modrm(0x00, val, X86_RAX));
                break;
            }

            /* ── String operations ─────────────────────── */
            case Q_STR_LEN:
                if (rt && rt->intrinsic_addrs[INTRINSIC_STRLEN])
                    x86_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_STRLEN], rs1, rd);
                break;
            case Q_STR_GET:
                if (rt && rt->intrinsic_addrs[INTRINSIC_STR_GET])
                    x86_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_STR_GET], rs1, rs2, rd);
                break;
            case Q_STR_CAT:
                if (rt && rt->intrinsic_addrs[INTRINSIC_STR_CAT])
                    x86_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_STR_CAT], rs1, rs2, rd);
                break;
            case Q_STR_EQ:
                if (rt && rt->intrinsic_addrs[INTRINSIC_STR_EQ])
                    x86_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_STR_EQ], rs1, rs2, rd);
                break;

            /* ── File I/O ──────────────────────────────── */
            case Q_FILE_OPEN:
                if (rt && rt->intrinsic_addrs[INTRINSIC_FILE_OPEN])
                    x86_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_FILE_OPEN], rs1, rs2, rd);
                break;
            case Q_FILE_READ:
                if (rt && rt->intrinsic_addrs[INTRINSIC_FILE_READ])
                    x86_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_FILE_READ], rs1, rd);
                break;
            case Q_FILE_WRITE:
                if (rt && rt->intrinsic_addrs[INTRINSIC_FILE_WRITE])
                    x86_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_FILE_WRITE], rs1, rs2, rd);
                break;
            case Q_FILE_CLOSE:
                if (rt && rt->intrinsic_addrs[INTRINSIC_FILE_CLOSE])
                    x86_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_FILE_CLOSE], rs1, rd);
                break;
            case Q_FILE_WRITE_BYTE:
                if (rt && rt->intrinsic_addrs[INTRINSIC_FILE_WRITE_BYTE])
                    x86_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_FILE_WRITE_BYTE], rs1, rs2, rd);
                break;

            /* ── Array operations ──────────────────────── */
            case Q_ARR_NEW:
                if (rt && rt->intrinsic_addrs[INTRINSIC_ARR_NEW])
                    x86_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_ARR_NEW], rs1, rd);
                break;
            case Q_ARR_LEN:
                if (rt && rt->intrinsic_addrs[INTRINSIC_ARR_LEN])
                    x86_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_ARR_LEN], rs1, rd);
                break;
            case Q_ARR_GET:
                if (rt && rt->intrinsic_addrs[INTRINSIC_ARR_GET])
                    x86_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_ARR_GET], rs1, rs2, rd);
                break;
            case Q_ARR_SET:
                if (rt && rt->intrinsic_addrs[INTRINSIC_ARR_SET]) {
                    x86_reg_t val = (ins->dest.type == OPERAND_VREG)
                        ? vreg_to_x86(ins->dest.vreg) : X86_RAX;
                    x86_emit_call_intrinsic_3(cb,
                        rt->intrinsic_addrs[INTRINSIC_ARR_SET], rs1, rs2, val, rd);
                }
                break;
            case Q_ARR_PUSH:
                if (rt && rt->intrinsic_addrs[INTRINSIC_ARR_PUSH])
                    x86_emit_call_intrinsic_2(cb,
                        rt->intrinsic_addrs[INTRINSIC_ARR_PUSH], rs1, rs2, rd);
                break;

            /* ── System ────────────────────────────────── */
            case Q_EXIT:
                if (rt && rt->intrinsic_addrs[INTRINSIC_EXIT])
                    x86_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_EXIT], rs1, rd);
                break;
            case Q_I_TO_STR:
                if (rt && rt->intrinsic_addrs[INTRINSIC_I_TO_STR])
                    x86_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_I_TO_STR], rs1, rd);
                break;
            case Q_STR_TO_I:
                if (rt && rt->intrinsic_addrs[INTRINSIC_STR_TO_I])
                    x86_emit_call_intrinsic_1(cb,
                        rt->intrinsic_addrs[INTRINSIC_STR_TO_I], rs1, rd);
                break;

            /* ── Globals ───────────────────────────────── */
            case Q_LOAD_GLOBAL:
                if (rt && rt->globals) {
                    x86_emit_mov_reg_imm64(cb, X86_RAX,
                        (int64_t)(uintptr_t)rt->globals);
                    if (ins->src1.type == OPERAND_IMM) {
                        /* MOV rd, [RAX + imm*8] */
                        int32_t off = (int32_t)(ins->src1.imm * 8);
                        /* MOV rd, [RAX + disp32] → REX 8B /r mod=10 */
                        uint8_t r = 0x48;
                        if (rd >= X86_R8) r |= 0x04;
                        codebuf_emit_byte(cb, r);
                        codebuf_emit_byte(cb, 0x8B);
                        codebuf_emit_byte(cb, modrm(0x02, rd, X86_RAX));
                        codebuf_emit_i32(cb, off);
                    } else {
                        /* LEA RAX, [RAX + rs1*8] then MOV rd, [RAX] */
                        x86_emit_mov_rr(cb, X86_R11, rs1);
                        /* SHL R11, 3 */
                        codebuf_emit_byte(cb, 0x49); codebuf_emit_byte(cb, 0xC1);
                        codebuf_emit_byte(cb, 0xE3); codebuf_emit_byte(cb, 0x03);
                        x86_emit_add_rr(cb, X86_RAX, X86_R11);
                        uint8_t r = 0x48;
                        if (rd >= X86_R8) r |= 0x04;
                        codebuf_emit_byte(cb, r);
                        codebuf_emit_byte(cb, 0x8B);
                        codebuf_emit_byte(cb, modrm(0x00, rd, X86_RAX));
                    }
                }
                break;
            case Q_STORE_GLOBAL:
                if (rt && rt->globals) {
                    x86_emit_mov_reg_imm64(cb, X86_RAX,
                        (int64_t)(uintptr_t)rt->globals);
                    if (ins->src1.type == OPERAND_IMM) {
                        int32_t off = (int32_t)(ins->src1.imm * 8);
                        uint8_t r = 0x48;
                        if (rs2 >= X86_R8) r |= 0x04;
                        codebuf_emit_byte(cb, r);
                        codebuf_emit_byte(cb, 0x89);
                        codebuf_emit_byte(cb, modrm(0x02, rs2, X86_RAX));
                        codebuf_emit_i32(cb, off);
                    } else {
                        x86_emit_mov_rr(cb, X86_R11, rs1);
                        codebuf_emit_byte(cb, 0x49); codebuf_emit_byte(cb, 0xC1);
                        codebuf_emit_byte(cb, 0xE3); codebuf_emit_byte(cb, 0x03);
                        x86_emit_add_rr(cb, X86_RAX, X86_R11);
                        uint8_t r = 0x48;
                        if (rs2 >= X86_R8) r |= 0x04;
                        codebuf_emit_byte(cb, r);
                        codebuf_emit_byte(cb, 0x89);
                        codebuf_emit_byte(cb, modrm(0x00, rs2, X86_RAX));
                    }
                }
                break;

            /* ── Args ──────────────────────────────────── */
            case Q_GET_ARG:
                if (rt && rt->args) {
                    x86_emit_mov_reg_imm64(cb, X86_RAX,
                        (int64_t)(uintptr_t)rt->args);
                    if (ins->src1.type == OPERAND_IMM) {
                        int32_t off = (int32_t)(ins->src1.imm * 8);
                        uint8_t r = 0x48;
                        if (rd >= X86_R8) r |= 0x04;
                        codebuf_emit_byte(cb, r);
                        codebuf_emit_byte(cb, 0x8B);
                        codebuf_emit_byte(cb, modrm(0x02, rd, X86_RAX));
                        codebuf_emit_i32(cb, off);
                    }
                }
                break;
            case Q_ARG_COUNT:
                x86_emit_mov_reg_imm64(cb, rd,
                    rt ? (int64_t)rt->arg_count : 0);
                break;

            case Q_HALT:
                x86_emit_xor_rr(cb, X86_RAX, X86_RAX);
                x86_emit_ret(cb);
                break;

            case Q_PATCH_POINT:
                x86_emit_nop(cb);
                break;

            /* ── SIMD / AVX Vector Operations ──────────── */
            case Q_VLOAD: {
                uint8_t xd = vreg_to_xmm(ins->dest.vreg);
                x86_reg_t base = (ins->src1.type == OPERAND_VREG)
                    ? vreg_to_x86(ins->src1.vreg) : X86_RAX;
                avx_emit_vmovaps_load(cb, xd, base);
                break;
            }
            case Q_VSTORE: {
                uint8_t xs = vreg_to_xmm(ins->src1.vreg);
                x86_reg_t base = (ins->dest.type == OPERAND_VREG)
                    ? vreg_to_x86(ins->dest.vreg) : X86_RAX;
                avx_emit_vmovaps_store(cb, base, xs);
                break;
            }
            case Q_VADD: {
                uint8_t d = vreg_to_xmm(ins->dest.vreg);
                uint8_t s1 = vreg_to_xmm(ins->src1.vreg);
                uint8_t s2 = vreg_to_xmm(ins->src2.vreg);
                avx_emit_vaddps(cb, d, s1, s2);
                break;
            }
            case Q_VSUB: {
                uint8_t d = vreg_to_xmm(ins->dest.vreg);
                uint8_t s1 = vreg_to_xmm(ins->src1.vreg);
                uint8_t s2 = vreg_to_xmm(ins->src2.vreg);
                avx_emit_vsubps(cb, d, s1, s2);
                break;
            }
            case Q_VMUL: {
                uint8_t d = vreg_to_xmm(ins->dest.vreg);
                uint8_t s1 = vreg_to_xmm(ins->src1.vreg);
                uint8_t s2 = vreg_to_xmm(ins->src2.vreg);
                avx_emit_vmulps(cb, d, s1, s2);
                break;
            }
            case Q_VFMA: {
                /* No single VEX FMA without FMA3, fall back to MUL+ADD */
                uint8_t d = vreg_to_xmm(ins->dest.vreg);
                uint8_t s1 = vreg_to_xmm(ins->src1.vreg);
                uint8_t s2 = vreg_to_xmm(ins->src2.vreg);
                avx_emit_vmulps(cb, d, s1, s2);
                avx_emit_vaddps(cb, d, d, d);  /* dest += result */
                break;
            }
            case Q_VDIV: {
                uint8_t d = vreg_to_xmm(ins->dest.vreg);
                uint8_t s1 = vreg_to_xmm(ins->src1.vreg);
                uint8_t s2 = vreg_to_xmm(ins->src2.vreg);
                avx_emit_vdivps(cb, d, s1, s2);
                break;
            }
            case Q_VMIN: {
                uint8_t d = vreg_to_xmm(ins->dest.vreg);
                uint8_t s1 = vreg_to_xmm(ins->src1.vreg);
                uint8_t s2 = vreg_to_xmm(ins->src2.vreg);
                avx_emit_vminps(cb, d, s1, s2);
                break;
            }
            case Q_VMAX: {
                uint8_t d = vreg_to_xmm(ins->dest.vreg);
                uint8_t s1 = vreg_to_xmm(ins->src1.vreg);
                uint8_t s2 = vreg_to_xmm(ins->src2.vreg);
                avx_emit_vmaxps(cb, d, s1, s2);
                break;
            }
            case Q_VREDUCE: {
                /* Horizontal sum: HADDPS twice for 4-lane reduction */
                uint8_t d = vreg_to_xmm(ins->dest.vreg);
                uint8_t s = vreg_to_xmm(ins->src1.vreg);
                /* VHADDPS: VEX.128.F2.0F 7C /r */
                x86_emit_vex2(cb, s, 0, 3); /* pp=11 (F2) */
                codebuf_emit_byte(cb, 0x7C);
                codebuf_emit_byte(cb, 0xC0 | ((d & 7) << 3) | (s & 7));
                /* Second HADDPS to finish 4-lane reduce */
                x86_emit_vex2(cb, d, 0, 3);
                codebuf_emit_byte(cb, 0x7C);
                codebuf_emit_byte(cb, 0xC0 | ((d & 7) << 3) | (d & 7));
                break;
            }
            case Q_VSPLAT: {
                uint8_t d = vreg_to_xmm(ins->dest.vreg);
                uint8_t s = vreg_to_xmm(ins->src1.vreg);
                avx_emit_vbroadcastss(cb, d, s);
                break;
            }
            case Q_VPERM: {
                /* VPERMILPS: VEX.128.66.0F38 0C /r */
                uint8_t d = vreg_to_xmm(ins->dest.vreg);
                uint8_t s1 = vreg_to_xmm(ins->src1.vreg);
                uint8_t s2 = vreg_to_xmm(ins->src2.vreg);
                codebuf_emit_byte(cb, 0xC4);
                codebuf_emit_byte(cb, 0xE2);
                codebuf_emit_byte(cb, 0x79 | ((~s1 & 0x0F) << 3));
                codebuf_emit_byte(cb, 0x0C);
                codebuf_emit_byte(cb, 0xC0 | ((d & 7) << 3) | (s2 & 7));
                break;
            }

            default:
                fprintf(stderr, "[codegen/full2/x86] unhandled opcode %d at instr %u\n",
                        ins->opcode, i);
                x86_emit_nop(cb);
                break;
            }
        }
    }

    /* ── Back-patch branch offsets ──────────────────────── */
    for (uint32_t f = 0; f < fixup_count; f++) {
        size_t target = 0;
        int found = 0;
        for (uint32_t l = 0; l < label_count; l++) {
            if (labels[l].label_id == fixups[f].target_label) {
                target = labels[l].offset;
                found = 1;
                break;
            }
        }
        if (!found) continue;

        size_t patch_at = fixups[f].patch_offset;

        if (arch == ARCH_ARM64) {
            int32_t byte_offset = (int32_t)(target - patch_at);
            uint32_t orig;
            memcpy(&orig, cb->data + patch_at, 4);
            if (fixups[f].is_cond) {
                uint32_t imm19 = ((uint32_t)(byte_offset >> 2)) & 0x7FFFF;
                orig = (orig & ~(0x7FFFF << 5)) | (imm19 << 5);
            } else {
                uint32_t imm26 = ((uint32_t)(byte_offset >> 2)) & 0x03FFFFFF;
                orig = (orig & ~0x03FFFFFF) | imm26;
            }
            memcpy(cb->data + patch_at, &orig, 4);
        } else {
            size_t instr_end = patch_at + 4;
            int32_t rel = (int32_t)(target - instr_end);
            codebuf_patch_i32(cb, patch_at, rel);
        }
    }

    return 0;
}

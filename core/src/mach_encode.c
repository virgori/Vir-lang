#include "mach_encode.h"
#include <stdio.h>

// Helper to write a 32-bit ARM64 instruction (Little Endian)
static inline void write32le(uint8_t **buf, uint32_t inst) {
    (*buf)[0] = (uint8_t)(inst & 0xFF);
    (*buf)[1] = (uint8_t)((inst >> 8) & 0xFF);
    (*buf)[2] = (uint8_t)((inst >> 16) & 0xFF);
    (*buf)[3] = (uint8_t)((inst >> 24) & 0xFF);
    *buf += 4;
}

// ARM64 Encodings
int arm64_encode_block(struct target_info_t *target, mach_block_t *mach_block, uint8_t *buffer, size_t max_size) {
    (void)target;
    uint8_t *ptr = buffer;
    uint8_t *end = buffer + max_size;
    
    mach_instr_t *instr = mach_block->head;
    while (instr) {
        if (ptr + 4 > end) return -1; // Buffer overflow
        
        uint32_t encoded = 0;
        switch (instr->op) {
            case MACH_OP_ADD: {
                // ADD Xd, Xn, Xm
                // 0x8B000000 | (Rm << 16) | (Rn << 5) | Rd
                uint32_t rd = instr->opnds[0].as.reg;
                uint32_t rn = instr->opnds[1].as.reg;
                uint32_t rm = instr->opnds[2].as.reg;
                encoded = 0x8B000000 | (rm << 16) | (rn << 5) | rd;
                break;
            }
            case MACH_OP_SUB: {
                // SUB Xd, Xn, Xm
                // 0xCB000000 | (Rm << 16) | (Rn << 5) | Rd
                uint32_t rd = instr->opnds[0].as.reg;
                uint32_t rn = instr->opnds[1].as.reg;
                uint32_t rm = instr->opnds[2].as.reg;
                encoded = 0xCB000000 | (rm << 16) | (rn << 5) | rd;
                break;
            }
            case MACH_OP_MOV: {
                uint32_t rd = instr->opnds[0].as.reg;
                if (instr->opnds[1].type == MACH_OPND_REG) {
                    // ORR Xd, XZR, Xm
                    // 0xAA000000 | (Rm << 16) | (0x1F << 5) | Rd
                    uint32_t rm = instr->opnds[1].as.reg;
                    encoded = 0xAA000000 | (rm << 16) | (0x1F << 5) | rd;
                } else if (instr->opnds[1].type == MACH_OPND_IMM) {
                    // MOVZ Xd, #imm16, LSL #0
                    // 0xD2800000 | (imm16 << 5) | Rd
                    uint32_t imm16 = (uint32_t)(instr->opnds[1].as.imm & 0xFFFF);
                    encoded = 0xD2800000 | (imm16 << 5) | rd;
                }
                break;
            }
            case MACH_OP_LDR: {
                // LDR Xd, [Xn, #imm]
                // 0xF9400000 | (imm12 << 10) | (Rn << 5) | Rd
                // Note: imm12 is scaled by 8 for 64-bit loads
                uint32_t rd = instr->opnds[0].as.reg;
                uint32_t rn = instr->opnds[1].as.reg;
                int64_t offset = instr->opnds[2].as.imm;
                
                // If offset is negative, use LDUR (Unscaled)
                // LDUR Xd, [Xn, #simm9]
                // 0xF8400000 | (simm9 << 12) | (Rn << 5) | Rd
                if (offset < 0) {
                    uint32_t simm9 = ((uint32_t)offset) & 0x1FF;
                    encoded = 0xF8400000 | (simm9 << 12) | (rn << 5) | rd;
                } else {
                    uint32_t imm12 = (offset / 8) & 0xFFF;
                    encoded = 0xF9400000 | (imm12 << 10) | (rn << 5) | rd;
                }
                break;
            }
            case MACH_OP_STR: {
                // STR Xt, [Xn, #imm]
                // 0xF9000000 | (imm12 << 10) | (Rn << 5) | Rt
                uint32_t rt = instr->opnds[0].as.reg;
                uint32_t rn = instr->opnds[1].as.reg;
                int64_t offset = instr->opnds[2].as.imm;
                
                if (offset < 0) {
                    // STUR Xt, [Xn, #simm9]
                    // 0xF8000000 | (simm9 << 12) | (Rn << 5) | Rt
                    uint32_t simm9 = ((uint32_t)offset) & 0x1FF;
                    encoded = 0xF8000000 | (simm9 << 12) | (rn << 5) | rt;
                } else {
                    uint32_t imm12 = (offset / 8) & 0xFFF;
                    encoded = 0xF9000000 | (imm12 << 10) | (rn << 5) | rt;
                }
                break;
            }
            case MACH_OP_RET: {
                // RET
                // 0xD65F03C0
                encoded = 0xD65F03C0;
                break;
            }
            case MACH_OP_NOP:
            default:
                // NOP
                encoded = 0xD503201F;
                break;
        }
        
        write32le(&ptr, encoded);
        instr = instr->next;
    }
    
    return (int)(ptr - buffer);
}

int mach_encode_func(const target_info_t *target, mach_func_t *mach_func, uint8_t *buffer, size_t max_size) {
    if (!target || !mach_func) return -1;
    
    int total_bytes = 0;
    mach_block_t *b = mach_func->blocks;
    while (b) {
        int bytes = target->hooks.encode_block((struct target_info_t *)target, b, buffer + total_bytes, max_size - total_bytes);
        if (bytes < 0) return -1;
        total_bytes += bytes;
        b = b->next;
    }
    
    return total_bytes;
}

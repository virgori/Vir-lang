#ifndef VIR_MACH_IR_H
#define VIR_MACH_IR_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Machine Opcodes for ARM64 (for now)
typedef enum {
    MACH_OP_NOP,
    MACH_OP_ADD,  // ADD Rd, Rn, Rm
    MACH_OP_SUB,  // SUB Rd, Rn, Rm
    MACH_OP_MOV,  // MOV Rd, Rn (Alias for ORR Rd, XZR, Rn)
    MACH_OP_LDR,  // LDR Rd, [Rn, #imm]
    MACH_OP_STR,  // STR Rt, [Rn, #imm]
    MACH_OP_RET,  // RET
    MACH_OP_CMP,  // CMP Rn, Rm (Alias for SUBS XZR, Rn, Rm)
    MACH_OP_B     // B label (Unconditional branch)
} mach_opcode_t;

// A physical register ID
typedef uint8_t mach_reg_t;

// An immediate value or offset
typedef int64_t mach_imm_t;

typedef enum {
    MACH_OPND_NONE,
    MACH_OPND_REG,
    MACH_OPND_IMM,
    MACH_OPND_LABEL // For branches
} mach_opnd_type_t;

typedef struct {
    mach_opnd_type_t type;
    union {
        mach_reg_t reg;
        mach_imm_t imm;
        uint32_t label_id;
    } as;
} mach_opnd_t;

// Maximum operands a machine instruction might need (ARM64 typically 3 or 4)
#define MACH_MAX_OPNDS 4

typedef struct mach_instr {
    mach_opcode_t op;
    mach_opnd_t opnds[MACH_MAX_OPNDS];
    uint8_t opnd_count;
    
    struct mach_instr *next;
    struct mach_instr *prev;
} mach_instr_t;

typedef struct mach_block {
    uint32_t id;
    mach_instr_t *head;
    mach_instr_t *tail;
    
    struct mach_block *next;
} mach_block_t;

typedef struct mach_func {
    uint32_t id;
    mach_block_t *blocks;
} mach_func_t;

// Helpers
mach_func_t* mach_create_func(uint32_t id);
mach_block_t* mach_create_block(mach_func_t *func);
mach_instr_t* mach_append_instr(mach_block_t *block, mach_opcode_t op);
void mach_free_func(mach_func_t *func);

#ifdef __cplusplus
}
#endif

#endif // VIR_MACH_IR_H

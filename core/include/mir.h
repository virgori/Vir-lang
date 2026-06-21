#ifndef VIR_MIR_H
#define VIR_MIR_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    MIR_NOP,
    MIR_MOVE,
    MIR_LOAD,
    MIR_STORE,
    MIR_ADD,
    MIR_SUB,
    MIR_MUL,
    MIR_DIV,
    MIR_CALL,
    MIR_INTRINSIC,
    MIR_JUMP,
    MIR_JUMP_IF,
    MIR_RETURN
} mir_op_t;

typedef enum {
    MIR_OPND_NONE,
    MIR_OPND_VREG,
    MIR_OPND_IMM,
    MIR_OPND_BLOCK
} mir_operand_type_t;

typedef struct {
    mir_operand_type_t type;
    union {
        uint32_t vreg;
        int64_t imm;
        uint32_t block_id;
    } as;
} mir_operand_t;

typedef struct mir_instr {
    mir_op_t op;
    mir_operand_t dst;
    mir_operand_t src1;
    mir_operand_t src2;
    struct mir_instr* next;
} mir_instr_t;

typedef struct mir_block {
    uint32_t id;
    mir_instr_t* head;
    mir_instr_t* tail;
    
    // CFG edges
    struct mir_block* succ_true;
    struct mir_block* succ_false;
    
    struct mir_block* next_block; // For linked list of blocks in a function
} mir_block_t;

typedef struct {
    uint32_t id;
    uint32_t next_vreg;
    uint32_t next_block_id;
    mir_block_t* entry_block;
    mir_block_t* blocks;
} mir_func_t;

/* Helper Functions */
mir_func_t* mir_create_func(uint32_t id);
mir_block_t* mir_create_block(mir_func_t* func);
void mir_append_instr(mir_block_t* block, mir_op_t op, mir_operand_t dst, mir_operand_t src1, mir_operand_t src2);
void mir_free_func(mir_func_t* func);

#ifdef __cplusplus
}
#endif

#endif // VIR_MIR_H

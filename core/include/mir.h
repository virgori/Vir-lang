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
    MIR_LOAD_STRING,
    MIR_STORE,
    MIR_ADD,
    MIR_SUB,
    MIR_MUL,
    MIR_DIV,
    MIR_CALL,
    MIR_INTRINSIC,
    MIR_JUMP,
    MIR_JUMP_IF,
    MIR_RETURN,
    MIR_EXIT,
    MIR_PRINT,
    MIR_CMP_GT,
    MIR_CMP_LT,
    MIR_CMP_EQ,
    MIR_CMP_GE,
    MIR_CMP_LE,
    MIR_CMP_NE,
    MIR_MOD,
    MIR_AND,
    MIR_OR,
    MIR_XOR,
    MIR_SHL,
    MIR_SHR,
    MIR_ARG_COUNT,
    MIR_GET_ARG,
    MIR_LOAD_BYTE,
    MIR_STORE_BYTE,
    MIR_LOAD_WORD,
    MIR_STORE_WORD
} mir_op_t;

typedef struct {
    int has_side_effect;
    int may_read_memory;
    int may_write_memory;
    int is_terminator;
} mir_opcode_info_t;

mir_opcode_info_t mir_get_opcode_info(mir_op_t op);


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

typedef struct mir_phi {
    uint32_t dst_vreg;
    uint32_t orig_vreg; // To track the original variable during renaming
    mir_operand_t* incoming_values;
    struct mir_block** incoming_blocks;
    uint32_t incoming_count;
    struct mir_phi* next;
} mir_phi_t;

typedef struct mir_use {
    struct mir_instr* instr; // The instruction where the use happens
    struct mir_phi* phi;     // Or the phi node where the use happens
    uint8_t opnd_idx;        // 1 for src1, 2 for src2, or index in phi incoming_values
    struct mir_use* next;
} mir_use_t;

typedef struct mir_block {
    uint32_t id;
    
    // SSA Phi nodes
    mir_phi_t* phis;
    
    mir_instr_t* head;
    mir_instr_t* tail;
    
    // CFG edges (Successors)
    struct mir_block* succ_true;
    struct mir_block* succ_false;
    
    // CFG edges (Predecessors)
    struct mir_block** preds;
    uint32_t pred_count;
    uint32_t pred_capacity;
    
    // Dominator Tree
    struct mir_block* idom; // Immediate dominator
    struct mir_block** dom_children;
    uint32_t dom_child_count;
    uint32_t dom_child_capacity;
    
    // Dominance Frontier
    struct mir_block** df;
    uint32_t df_count;
    uint32_t df_capacity;
    
    struct mir_block* next_block; // For linked list of blocks in a function
} mir_block_t;

typedef struct {
    uint32_t id;
    uint32_t next_vreg;
    mir_use_t** def_uses; // Array of size next_vreg + 1
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

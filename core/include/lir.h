#ifndef VIR_LIR_H
#define VIR_LIR_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// Machine-level operations
typedef enum {
    LIR_TYPE_NONE,
    LIR_TYPE_INT8,
    LIR_TYPE_INT16,
    LIR_TYPE_INT32,
    LIR_TYPE_INT64,
    LIR_TYPE_F32,
    LIR_TYPE_F64,
    LIR_TYPE_PTR,
    LIR_TYPE_VECTOR
} lir_type_t;

typedef enum {
    LIR_NOP,
    LIR_MOV,
    LIR_ADD,
    LIR_SUB,
    LIR_MUL,
    LIR_DIV,
    LIR_PUSH,
    LIR_POP,
    LIR_CALL,
    LIR_JMP,
    LIR_JMP_COND,
    LIR_CMP,
    LIR_RET,
    LIR_LOAD,    // Load from memory
    LIR_LOAD_STRING,
    LIR_STORE,   // Store to memory
    LIR_PRINT,   // Print value (side effect)
    LIR_CMP_GT,
    LIR_CMP_LT,
    LIR_CMP_EQ,
    LIR_CMP_GE,
    LIR_CMP_LE,
    LIR_CMP_NE,
    LIR_ARG_COUNT,
    LIR_GET_ARG,
    LIR_LOAD_BYTE,
    LIR_STORE_BYTE,
    LIR_LOAD_WORD,
    LIR_STORE_WORD,
    LIR_MOD,
    LIR_AND,
    LIR_OR,
    LIR_XOR,
    LIR_SHL,
    LIR_SHR
} lir_op_t;

// Operand types representing physical registers and stack memory
typedef enum {
    LIR_OPND_NONE,
    LIR_OPND_VREG_INT,   // General purpose integer virtual register
    LIR_OPND_VREG_FLOAT, // Floating point virtual register
    LIR_OPND_PHYS_REG,   // Physical register
    LIR_OPND_STACK_MEM,  // Stack memory slot
    LIR_OPND_IMM,        // Immediate value
    LIR_OPND_LABEL       // Block label (for jumps)
} lir_operand_type_t;

// Register Classes
typedef enum {
    LIR_REG_CLASS_INT,
    LIR_REG_CLASS_FLOAT,
    LIR_REG_CLASS_VECTOR,
    LIR_REG_CLASS_SPECIAL
} lir_reg_class_t;

// Register Roles
typedef enum {
    LIR_REG_ROLE_CALLER_SAVED = 1 << 0,
    LIR_REG_ROLE_CALLEE_SAVED = 1 << 1,
    LIR_REG_ROLE_ARGUMENT     = 1 << 2,
    LIR_REG_ROLE_RETURN       = 1 << 3,
    LIR_REG_ROLE_RESERVED     = 1 << 4,
    LIR_REG_ROLE_SCRATCH      = 1 << 5
} lir_reg_role_t;

// Target architecture physical registers (Generic RISC-like subset for now)
typedef enum {
    LIR_REG_R0 = 0, // Return, Caller Saved
    LIR_REG_R1,     // Argument, Caller Saved
    LIR_REG_R2,     // Argument, Caller Saved
    LIR_REG_R3,     // Argument, Caller Saved
    LIR_REG_R4,     // Argument, Caller Saved
    LIR_REG_R5,     // Callee Saved
    LIR_REG_R6,     // Callee Saved
    LIR_REG_R7,     // Callee Saved
    LIR_REG_R8,     // Scratch
    LIR_REG_R9,     // Scratch
    LIR_REG_SP,     // Stack pointer (Reserved)
    LIR_REG_FP,     // Frame pointer (Reserved)
    LIR_REG_MAX
} lir_phys_reg_t;

typedef struct {
    const char* name;
    lir_reg_class_t reg_class;
    uint32_t roles; // Bitmask of lir_reg_role_t
} lir_phys_reg_info_t;

// Get metadata for a physical register
const lir_phys_reg_info_t* lir_get_phys_reg_info(lir_phys_reg_t reg);

typedef struct {
    lir_operand_type_t type;
    union {
        uint32_t vreg;
        uint32_t phys_reg;
        int32_t stack_offset;
        int64_t imm;
        uint32_t label_id;
    } as;
} lir_operand_t;

typedef struct lir_instr {
    lir_op_t op;
    lir_type_t type; // Type of operation (e.g. LIR_TYPE_INT64 for 64-bit ADD)
    lir_operand_t dst;
    lir_operand_t src1;
    lir_operand_t src2;
    struct lir_instr* next;
    struct lir_instr* prev;
} lir_instr_t;

typedef struct lir_block {
    uint32_t id;
    lir_instr_t* head;
    lir_instr_t* tail;
    struct lir_block* next;
} lir_block_t;

typedef struct {
    uint32_t id;
    lir_block_t* blocks;
    uint32_t next_block_id;
    uint32_t stack_size;
} lir_func_t;

/* Helper Functions */
lir_func_t* lir_create_func(uint32_t id);
lir_block_t* lir_create_block(lir_func_t* func);
void lir_append_instr(lir_block_t* block, lir_op_t op, lir_operand_t dst, lir_operand_t src1, lir_operand_t src2);
void lir_free_func(lir_func_t* func);

#ifdef __cplusplus
}
#endif

#endif // VIR_LIR_H

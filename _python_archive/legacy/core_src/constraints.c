/*
 * constraints.c – Type System & Constraint Tables
 * =================================================
 * Pure data tables – no heap allocation, no external deps.
 */

#include "constraints.h"
#include "q_ir.h"
#include <stddef.h>

/* ═══════════════════════════════════════════════════════
 * Type Metadata Table
 * ═══════════════════════════════════════════════════════ */

static const vir_type_info_t type_table[VIR_TYPE_COUNT] = {
    [VIR_TYPE_VOID] = { VIR_TYPE_VOID, "void",  0, 0, 0, 0 },
    [VIR_TYPE_I8]   = { VIR_TYPE_I8,   "i8",    1, 1, 1, 0 },
    [VIR_TYPE_I32]  = { VIR_TYPE_I32,  "i32",   4, 4, 1, 0 },
    [VIR_TYPE_I64]  = { VIR_TYPE_I64,  "i64",   8, 8, 1, 0 },
    [VIR_TYPE_F32]  = { VIR_TYPE_F32,  "f32",   4, 4, 0, 1 },
    [VIR_TYPE_F64]  = { VIR_TYPE_F64,  "f64",   8, 8, 0, 1 },
    [VIR_TYPE_PTR]  = { VIR_TYPE_PTR,  "ptr",   8, 8, 0, 0 },
};

const vir_type_info_t *vir_type_get(vir_type_t t)
{
    if ((unsigned)t < VIR_TYPE_COUNT) return &type_table[t];
    return &type_table[VIR_TYPE_VOID];
}

uint8_t vir_type_size(vir_type_t t)
{
    return vir_type_get(t)->size;
}

/* ═══════════════════════════════════════════════════════
 * Opcode Constraint Table
 * ═══════════════════════════════════════════════════════
 * For each Q-IR opcode: expected operand types, result type.
 * Default integer type is I64.  Void = unused slot.
 */

#define I64  VIR_TYPE_I64
#define _    VIR_TYPE_VOID
#define PTR  VIR_TYPE_PTR
#define I8   VIR_TYPE_I8

static const op_constraint_t op_table[] = {
    /* Data movement */
    { Q_NOP,          0, _,   {_,   _,   _},   "nop"       },
    { Q_LOAD,         2, I64, {I64, _,   _},   "load"      },
    { Q_STORE,        2, _,   {PTR, I64, _},   "store"     },
    { Q_MOVE,         2, I64, {I64, _,   _},   "move"      },

    /* Arithmetic  (dest = src1 ⊕ src2) */
    { Q_ADD,          3, I64, {I64, I64, _},   "add"       },
    { Q_SUB,          3, I64, {I64, I64, _},   "sub"       },
    { Q_MUL,          3, I64, {I64, I64, _},   "mul"       },
    { Q_DIV,          3, I64, {I64, I64, _},   "div"       },
    { Q_MOD,          3, I64, {I64, I64, _},   "mod"       },

    /* Comparison  (dest = 0|1) */
    { Q_CMP_EQ,       3, I8,  {I64, I64, _},   "cmp_eq"    },
    { Q_CMP_GT,       3, I8,  {I64, I64, _},   "cmp_gt"    },
    { Q_CMP_LT,       3, I8,  {I64, I64, _},   "cmp_lt"    },
    { Q_CMP_GE,       3, I8,  {I64, I64, _},   "cmp_ge"    },
    { Q_CMP_LE,       3, I8,  {I64, I64, _},   "cmp_le"    },

    /* Bitwise */
    { Q_AND,          3, I64, {I64, I64, _},   "and"       },
    { Q_OR,           3, I64, {I64, I64, _},   "or"        },
    { Q_XOR,          3, I64, {I64, I64, _},   "xor"       },
    { Q_SHL,          3, I64, {I64, I64, _},   "shl"       },
    { Q_SHR,          3, I64, {I64, I64, _},   "shr"       },

    /* Control flow */
    { Q_JUMP,         1, _,   {_,   _,   _},   "jump"      },
    { Q_JUMP_IF,      2, _,   {I64, _,   _},   "jump_if"   },
    { Q_JUMP_IF_NOT,  2, _,   {I64, _,   _},   "jump_ifn"  },
    { Q_CALL,         1, _,   {_,   _,   _},   "call"      },
    { Q_RET,          1, _,   {I64, _,   _},   "ret"       },

    /* I/O  (intrinsics) */
    { Q_PRINT,        1, _,   {I64, _,   _},   "print"     },
    { Q_INPUT,        1, I64, {_,   _,   _},   "input"     },

    /* Self-patching */
    { Q_PATCH_POINT,  0, _,   {_,   _,   _},   "patch_pt"  },
    { Q_LABEL,        0, _,   {_,   _,   _},   "label"     },
    { Q_HALT,         0, _,   {_,   _,   _},   "halt"      },
};

#undef I64
#undef _
#undef PTR
#undef I8

#define OP_TABLE_LEN (sizeof(op_table) / sizeof(op_table[0]))

const op_constraint_t *vir_op_constraint(uint8_t opcode)
{
    for (size_t i = 0; i < OP_TABLE_LEN; i++) {
        if (op_table[i].opcode == opcode) return &op_table[i];
    }
    return NULL;
}

int vir_constraint_check(uint8_t opcode, vir_type_t dest,
                         vir_type_t src1, vir_type_t src2)
{
    const op_constraint_t *c = vir_op_constraint(opcode);
    if (!c) return -1;

    /* Check dest type (if constraint requires one) */
    if (c->dest_type != VIR_TYPE_VOID && dest != c->dest_type)
        return -1;

    /* Check src types */
    if (c->src_types[0] != VIR_TYPE_VOID && src1 != c->src_types[0])
        return -1;
    if (c->src_types[1] != VIR_TYPE_VOID && src2 != c->src_types[1])
        return -1;

    return 0;
}

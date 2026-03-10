/*
 * q_ir.c – Q-IR Instruction Set Implementation
 * ==============================================
 * Spec §2 – SSA-form intermediate representation.
 */

#include "q_ir.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ═══════════════════════════════════════════════════════
 * Operand Constructors
 * ═══════════════════════════════════════════════════════ */

q_operand_t q_vreg(uint32_t index)
{
    q_operand_t op = {0};
    op.type = OPERAND_VREG;
    op.vreg = index;
    return op;
}

q_operand_t q_imm(int64_t value)
{
    q_operand_t op = {0};
    op.type = OPERAND_IMM;
    op.imm = value;
    return op;
}

q_operand_t q_fimm(double value)
{
    q_operand_t op = {0};
    op.type = OPERAND_IMM;
    op.fimm = value;
    return op;
}

q_operand_t q_label(uint32_t id)
{
    q_operand_t op = {0};
    op.type = OPERAND_LABEL;
    op.label = id;
    return op;
}

q_operand_t q_none(void)
{
    q_operand_t op = {0};
    op.type = OPERAND_NONE;
    return op;
}

q_operand_t q_str(uint32_t str_idx)
{
    q_operand_t op = {0};
    op.type = OPERAND_STR;
    op.str_idx = str_idx;
    return op;
}

q_operand_t q_func_idx(uint32_t func_idx)
{
    q_operand_t op = {0};
    op.type = OPERAND_FUNC_IDX;
    op.func_idx = func_idx;
    return op;
}

/* ═══════════════════════════════════════════════════════
 * Instruction
 * ═══════════════════════════════════════════════════════ */

q_instruction_t q_instr(q_opcode_t op, q_operand_t dest,
                        q_operand_t src1, q_operand_t src2)
{
    q_instruction_t instr = {0};
    instr.opcode = op;
    instr.dest   = dest;
    instr.src1   = src1;
    instr.src2   = src2;
    return instr;
}

/* ═══════════════════════════════════════════════════════
 * Function
 * ═══════════════════════════════════════════════════════ */

#define FUNC_INIT_CAP 64

int q_func_init(q_function_t *func, const char *name)
{
    memset(func, 0, sizeof(*func));
    if (name) {
        strncpy(func->name, name, Q_MAX_FUNC_NAME - 1);
    }
    func->body = (q_instruction_t *)malloc(FUNC_INIT_CAP * sizeof(q_instruction_t));
    if (!func->body) return -1;
    func->body_capacity = FUNC_INIT_CAP;
    func->body_count    = 0;
    return 0;
}

int q_func_emit(q_function_t *func, q_instruction_t instr)
{
    if (func->body_count >= func->body_capacity) {
        uint32_t new_cap = func->body_capacity * 2;
        q_instruction_t *new_body = (q_instruction_t *)realloc(
            func->body, new_cap * sizeof(q_instruction_t));
        if (!new_body) return -1;
        func->body = new_body;
        func->body_capacity = new_cap;
    }
    func->body[func->body_count++] = instr;
    return 0;
}

void q_func_free(q_function_t *func)
{
    if (func->body) {
        free(func->body);
        func->body = NULL;
    }
    func->body_count = 0;
    func->body_capacity = 0;
}

/* ═══════════════════════════════════════════════════════
 * Module
 * ═══════════════════════════════════════════════════════ */

int q_module_init(q_module_t *mod, const char *name)
{
    memset(mod, 0, sizeof(*mod));
    if (name) {
        strncpy(mod->name, name, Q_MAX_FUNC_NAME - 1);
    }
    return 0;
}

q_function_t* q_module_add_func(q_module_t *mod, const char *name)
{
    /* First, check if function already exists */
    for (uint32_t i = 0; i < mod->func_count; i++) {
        if (strcmp(mod->functions[i].name, name) == 0)
            return &mod->functions[i];
    }
    if (mod->func_count >= Q_MAX_FUNCTIONS) return NULL;
    q_function_t *func = &mod->functions[mod->func_count];
    if (q_func_init(func, name) != 0) return NULL;
    mod->func_count++;
    return func;
}

void q_module_free(q_module_t *mod)
{
    for (uint32_t i = 0; i < mod->func_count; i++) {
        q_func_free(&mod->functions[i]);
    }
    mod->func_count = 0;
    /* Free string table */
    for (uint32_t i = 0; i < mod->string_count; i++) {
        free(mod->strings[i]);
        mod->strings[i] = NULL;
    }
    mod->string_count = 0;
}

uint32_t q_module_add_string(q_module_t *mod, const char *str)
{
    /* Deduplicate */
    for (uint32_t i = 0; i < mod->string_count; i++) {
        if (mod->strings[i] && strcmp(mod->strings[i], str) == 0)
            return i;
    }
    if (mod->string_count >= Q_MAX_STRINGS) return 0;
    mod->strings[mod->string_count] = strdup(str);
    return mod->string_count++;
}

/* ── Operand to string ────────────────────────────────── */
static int operand_sprint(const q_operand_t *op, char *buf, size_t n)
{
    switch (op->type) {
        case OPERAND_VREG:     return snprintf(buf, n, "R%u", op->vreg);
        case OPERAND_IMM:      return snprintf(buf, n, "#%lld", (long long)op->imm);
        case OPERAND_LABEL:    return snprintf(buf, n, "@L%u", op->label);
        case OPERAND_ADDR:     return snprintf(buf, n, "[0x%llx]", (unsigned long long)op->addr);
        case OPERAND_STR:      return snprintf(buf, n, "$S%u", op->str_idx);
        case OPERAND_FUNC_IDX: return snprintf(buf, n, "@F%u", op->func_idx);
        default:               return 0;
    }
}

void q_module_dump(const q_module_t *mod, char *buf, size_t buf_size)
{
    int pos = 0;
    pos += snprintf(buf + pos, buf_size - pos, "; module %s\n", mod->name);

    for (uint32_t fi = 0; fi < mod->func_count && (size_t)pos < buf_size; fi++) {
        const q_function_t *func = &mod->functions[fi];
        pos += snprintf(buf + pos, buf_size - pos, "\nfunc @%s(", func->name);
        for (uint32_t pi = 0; pi < func->param_count; pi++) {
            if (pi > 0) pos += snprintf(buf + pos, buf_size - pos, ", ");
            pos += snprintf(buf + pos, buf_size - pos, "R%u", func->param_vregs[pi]);
        }
        pos += snprintf(buf + pos, buf_size - pos, "):\n");

        for (uint32_t ii = 0; ii < func->body_count && (size_t)pos < buf_size; ii++) {
            const q_instruction_t *instr = &func->body[ii];
            pos += snprintf(buf + pos, buf_size - pos, "  %-16s", q_opcode_name(instr->opcode));

            char tmp[64];
            if (instr->dest.type != OPERAND_NONE) {
                operand_sprint(&instr->dest, tmp, sizeof(tmp));
                pos += snprintf(buf + pos, buf_size - pos, " %s", tmp);
            }
            if (instr->src1.type != OPERAND_NONE) {
                operand_sprint(&instr->src1, tmp, sizeof(tmp));
                pos += snprintf(buf + pos, buf_size - pos, ", %s", tmp);
            }
            if (instr->src2.type != OPERAND_NONE) {
                operand_sprint(&instr->src2, tmp, sizeof(tmp));
                pos += snprintf(buf + pos, buf_size - pos, ", %s", tmp);
            }
            if (instr->opcode == Q_PATCH_POINT) {
                pos += snprintf(buf + pos, buf_size - pos, " ; patch_id=%u", instr->patch_id);
            }
            pos += snprintf(buf + pos, buf_size - pos, "\n");
        }
    }
}

/* ═══════════════════════════════════════════════════════
 * Register Allocator
 * ═══════════════════════════════════════════════════════ */

void q_vreg_alloc_init(q_vreg_alloc_t *alloc)
{
    alloc->next_index = 0;
}

uint32_t q_vreg_alloc_next(q_vreg_alloc_t *alloc)
{
    return alloc->next_index++;
}

void q_vreg_alloc_reset(q_vreg_alloc_t *alloc)
{
    alloc->next_index = 0;
}

/* ═══════════════════════════════════════════════════════
 * Opcode Name Table
 * ═══════════════════════════════════════════════════════ */

const char* q_opcode_name(q_opcode_t op)
{
    switch (op) {
        case Q_NOP:          return "Q_NOP";
        case Q_LOAD:         return "Q_LOAD";
        case Q_STORE:        return "Q_STORE";
        case Q_MOVE:         return "Q_MOVE";
        case Q_ADD:          return "Q_ADD";
        case Q_SUB:          return "Q_SUB";
        case Q_MUL:          return "Q_MUL";
        case Q_DIV:          return "Q_DIV";
        case Q_MOD:          return "Q_MOD";
        case Q_CMP_EQ:       return "Q_CMP_EQ";
        case Q_CMP_GT:       return "Q_CMP_GT";
        case Q_CMP_LT:       return "Q_CMP_LT";
        case Q_CMP_GE:       return "Q_CMP_GE";
        case Q_CMP_LE:       return "Q_CMP_LE";
        case Q_AND:          return "Q_AND";
        case Q_OR:           return "Q_OR";
        case Q_XOR:          return "Q_XOR";
        case Q_SHL:          return "Q_SHL";
        case Q_SHR:          return "Q_SHR";
        case Q_JUMP:         return "Q_JUMP";
        case Q_JUMP_IF:      return "Q_JUMP_IF";
        case Q_JUMP_IF_NOT:  return "Q_JUMP_IF_NOT";
        case Q_CALL:         return "Q_CALL";
        case Q_RET:          return "Q_RET";
        case Q_PRINT:        return "Q_PRINT";
        case Q_INPUT:        return "Q_INPUT";
        case Q_ALLOC:        return "Q_ALLOC";
        case Q_FREE:         return "Q_FREE";
        case Q_LOAD_BYTE:    return "Q_LOAD_BYTE";
        case Q_STORE_BYTE:   return "Q_STORE_BYTE";
        case Q_LOAD_WORD:    return "Q_LOAD_WORD";
        case Q_STORE_WORD:   return "Q_STORE_WORD";
        case Q_STR_LEN:      return "Q_STR_LEN";
        case Q_STR_GET:      return "Q_STR_GET";
        case Q_STR_CAT:      return "Q_STR_CAT";
        case Q_STR_EQ:       return "Q_STR_EQ";
        case Q_FILE_OPEN:    return "Q_FILE_OPEN";
        case Q_FILE_READ:    return "Q_FILE_READ";
        case Q_FILE_WRITE:   return "Q_FILE_WRITE";
        case Q_FILE_CLOSE:   return "Q_FILE_CLOSE";
        case Q_FILE_WRITE_BYTE: return "Q_FILE_WRITE_BYTE";
        case Q_ARR_NEW:      return "Q_ARR_NEW";
        case Q_ARR_LEN:      return "Q_ARR_LEN";
        case Q_ARR_GET:      return "Q_ARR_GET";
        case Q_ARR_SET:      return "Q_ARR_SET";
        case Q_ARR_PUSH:     return "Q_ARR_PUSH";
        case Q_EXIT:         return "Q_EXIT";
        case Q_I_TO_STR:     return "Q_I_TO_STR";
        case Q_STR_TO_I:     return "Q_STR_TO_I";
        case Q_PRINT_STR:    return "Q_PRINT_STR";
        case Q_GET_ARG:      return "Q_GET_ARG";
        case Q_ARG_COUNT:    return "Q_ARG_COUNT";
        case Q_CALL_FUNC:    return "Q_CALL_FUNC";
        case Q_LOAD_GLOBAL:  return "Q_LOAD_GLOBAL";
        case Q_STORE_GLOBAL: return "Q_STORE_GLOBAL";
        case Q_PATCH_POINT:  return "Q_PATCH_POINT";
        case Q_LABEL:        return "Q_LABEL";
        case Q_HALT:         return "Q_HALT";
        default:             return "Q_???";
    }
}

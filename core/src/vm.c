/*
 * vm.c – Q-IR Virtual Machine (Interpreter)
 * ==========================================
 * Spec §2 – Thực thi Q-IR instructions trên thanh ghi ảo.
 * Đây là VM interpreter = Bản A (Safe) fallback.
 */

#include "vm.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* ═══════════════════════════════════════════════════════
 * Helpers
 * ═══════════════════════════════════════════════════════ */

static inline int64_t operand_value(const vm_state_t *vm, const q_operand_t *op)
{
    switch (op->type) {
        case OPERAND_VREG:  return vm->regs[op->vreg];
        case OPERAND_IMM:   return op->imm;
        case OPERAND_STR: {
            /* Return pointer to string from module string table */
            if (vm->module && op->str_idx < vm->module->string_count) {
                return (int64_t)(intptr_t)vm->module->strings[op->str_idx];
            }
            return 0;
        }
        default:            return 0;
    }
}

static inline void set_dest(vm_state_t *vm, const q_operand_t *dest, int64_t val)
{
    if (dest->type == OPERAND_VREG) {
        vm->regs[dest->vreg] = val;
        if (dest->vreg >= vm->reg_count)
            vm->reg_count = dest->vreg + 1;
    }
}

/* ═══════════════════════════════════════════════════════
 * VM Array Helpers
 * ═══════════════════════════════════════════════════════ */

static int64_t vm_array_new(vm_state_t *vm, int64_t cap)
{
    if (vm->array_count >= VM_MAX_ARRAYS) return -1;
    uint32_t idx = vm->array_count++;
    vm->arrays[idx].cap = (uint32_t)(cap > 0 ? cap : 16);
    vm->arrays[idx].len = 0;
    vm->arrays[idx].data = (int64_t *)calloc(vm->arrays[idx].cap, sizeof(int64_t));
    return (int64_t)idx;
}

static void vm_array_push(vm_state_t *vm, int64_t arr_handle, int64_t val)
{
    if (arr_handle < 0 || (uint32_t)arr_handle >= vm->array_count) return;
    vm_array_t *arr = &vm->arrays[(uint32_t)arr_handle];
    if (arr->len >= arr->cap) {
        arr->cap *= 2;
        arr->data = (int64_t *)realloc(arr->data, arr->cap * sizeof(int64_t));
    }
    arr->data[arr->len++] = val;
}

static int64_t vm_array_get(vm_state_t *vm, int64_t arr_handle, int64_t idx)
{
    if (arr_handle < 0 || (uint32_t)arr_handle >= vm->array_count) return 0;
    vm_array_t *arr = &vm->arrays[(uint32_t)arr_handle];
    if (idx < 0 || (uint32_t)idx >= arr->len) return 0;
    return arr->data[(uint32_t)idx];
}

static void vm_array_set(vm_state_t *vm, int64_t arr_handle, int64_t idx, int64_t val)
{
    if (arr_handle < 0 || (uint32_t)arr_handle >= vm->array_count) return;
    vm_array_t *arr = &vm->arrays[(uint32_t)arr_handle];
    if (idx < 0 || (uint32_t)idx >= arr->len) return;
    arr->data[(uint32_t)idx] = val;
}

static int64_t vm_array_len(vm_state_t *vm, int64_t arr_handle)
{
    if (arr_handle < 0 || (uint32_t)arr_handle >= vm->array_count) return 0;
    return (int64_t)vm->arrays[(uint32_t)arr_handle].len;
}

/* Store a runtime string, return its pointer as int64 */
static int64_t vm_add_rt_string(vm_state_t *vm, char *s)
{
    if (vm->rt_string_count < VM_MAX_STRINGS_RT) {
        vm->rt_strings[vm->rt_string_count++] = s;
    }
    return (int64_t)(intptr_t)s;
}

static void vm_clear_func_frames(vm_state_t *vm)
{
    for (uint32_t i = 0; i < VM_MAX_CALL_DEPTH; i++) {
        free(vm->func_stack[i].saved_regs);
        vm->func_stack[i].saved_regs = NULL;
        vm->func_stack[i].saved_reg_count = 0;
        vm->func_stack[i].func = NULL;
        vm->func_stack[i].ip = 0;
    }
    vm->func_depth = 0;
}

/* ═══════════════════════════════════════════════════════
 * Init / Reset / Destroy
 * ═══════════════════════════════════════════════════════ */

void vm_init(vm_state_t *vm)
{
    memset(vm, 0, sizeof(*vm));
    vm->status = VM_OK;
}

void vm_reset(vm_state_t *vm)
{
    vm_clear_func_frames(vm);
    memset(vm->regs, 0, sizeof(vm->regs));
    vm->reg_count        = 0;
    vm->call_depth       = 0;
    vm->ip               = 0;
    vm->status           = VM_OK;
    vm->instr_executed   = 0;
    vm->patches_triggered = 0;
}

void vm_destroy(vm_state_t *vm)
{
    vm_clear_func_frames(vm);
    /* Free arrays */
    for (uint32_t i = 0; i < vm->array_count; i++) {
        free(vm->arrays[i].data);
        vm->arrays[i].data = NULL;
    }
    vm->array_count = 0;
    /* Free heap blocks */
    for (uint32_t i = 0; i < vm->heap_count; i++) {
        free(vm->heap_blocks[i]);
        vm->heap_blocks[i] = NULL;
    }
    vm->heap_count = 0;
    /* Free runtime strings */
    for (uint32_t i = 0; i < vm->rt_string_count; i++) {
        free(vm->rt_strings[i]);
        vm->rt_strings[i] = NULL;
    }
    vm->rt_string_count = 0;
}

void vm_set_module(vm_state_t *vm, const q_module_t *mod)
{
    vm->module = mod;
}

void vm_set_args(vm_state_t *vm, int argc, const char **argv)
{
    vm->args = argv;
    vm->arg_count = argc;
}

void vm_set_patch_handler(vm_state_t *vm, vm_patch_handler_t handler, void *ud)
{
    vm->patch_handler  = handler;
    vm->patch_userdata = ud;
}

/* ═══════════════════════════════════════════════════════
 * Label Resolution
 * ═══════════════════════════════════════════════════════ */

int vm_resolve_labels(vm_state_t *vm, const q_function_t *func)
{
    memset(vm->label_map, 0, sizeof(vm->label_map));
    vm->label_count = 0;
    uint32_t overflow_count = 0;

    for (uint32_t i = 0; i < func->body_count; i++) {
        if (func->body[i].opcode == Q_LABEL) {
            uint32_t lid = func->body[i].patch_id;
            if (lid < VM_MAX_LABELS) {
                vm->label_map[lid] = i;
                if (lid >= vm->label_count)
                    vm->label_count = lid + 1;
            } else {
                overflow_count++;
            }
        }
    }
    if (overflow_count > 0) {
        fprintf(stderr, "[WARN] vm_resolve_labels: %u labels exceeded VM_MAX_LABELS (%d) in function '%s' (body_count=%u)\n",
                overflow_count, VM_MAX_LABELS, func->name, func->body_count);
    }
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Single-step execution
 * ═══════════════════════════════════════════════════════ */

vm_status_t vm_step(vm_state_t *vm, const q_instruction_t *instr)
{
    int64_t a, b, result;
    vm->instr_executed++;

    switch (instr->opcode) {

    /* ── Data movement ─────────────────────────────────── */
    case Q_NOP:
        break;

    case Q_LOAD:
        set_dest(vm, &instr->dest, operand_value(vm, &instr->src1));
        break;

    case Q_STORE:
        /* In-VM memory store → treat addr as vreg index */
        if (instr->dest.type == OPERAND_VREG)
            vm->regs[instr->dest.vreg] = operand_value(vm, &instr->src1);
        break;

    case Q_MOVE:
        set_dest(vm, &instr->dest, operand_value(vm, &instr->src1));
        break;

    /* ── Arithmetic ────────────────────────────────────── */
    case Q_ADD:
        a = operand_value(vm, &instr->src1);
        b = operand_value(vm, &instr->src2);
        set_dest(vm, &instr->dest, a + b);
        break;

    case Q_SUB:
        a = operand_value(vm, &instr->src1);
        b = operand_value(vm, &instr->src2);
        set_dest(vm, &instr->dest, a - b);
        break;

    case Q_MUL:
        a = operand_value(vm, &instr->src1);
        b = operand_value(vm, &instr->src2);
        set_dest(vm, &instr->dest, a * b);
        break;

    case Q_DIV:
        a = operand_value(vm, &instr->src1);
        b = operand_value(vm, &instr->src2);
        if (b == 0) return VM_ERR_DIV_ZERO;
        set_dest(vm, &instr->dest, a / b);
        break;

    case Q_MOD:
        a = operand_value(vm, &instr->src1);
        b = operand_value(vm, &instr->src2);
        if (b == 0) return VM_ERR_DIV_ZERO;
        set_dest(vm, &instr->dest, a % b);
        break;

    /* ── Comparison ────────────────────────────────────── */
    case Q_CMP_EQ:
        a = operand_value(vm, &instr->src1);
        b = operand_value(vm, &instr->src2);
        set_dest(vm, &instr->dest, (a == b) ? 1 : 0);
        break;

    case Q_CMP_GT:
        a = operand_value(vm, &instr->src1);
        b = operand_value(vm, &instr->src2);
        set_dest(vm, &instr->dest, (a > b) ? 1 : 0);
        break;

    case Q_CMP_LT:
        a = operand_value(vm, &instr->src1);
        b = operand_value(vm, &instr->src2);
        set_dest(vm, &instr->dest, (a < b) ? 1 : 0);
        break;

    case Q_CMP_GE:
        a = operand_value(vm, &instr->src1);
        b = operand_value(vm, &instr->src2);
        set_dest(vm, &instr->dest, (a >= b) ? 1 : 0);
        break;

    case Q_CMP_LE:
        a = operand_value(vm, &instr->src1);
        b = operand_value(vm, &instr->src2);
        set_dest(vm, &instr->dest, (a <= b) ? 1 : 0);
        break;

    /* ── Bitwise ───────────────────────────────────────── */
    case Q_AND:
        set_dest(vm, &instr->dest,
                 operand_value(vm, &instr->src1) & operand_value(vm, &instr->src2));
        break;
    case Q_OR:
        set_dest(vm, &instr->dest,
                 operand_value(vm, &instr->src1) | operand_value(vm, &instr->src2));
        break;
    case Q_XOR:
        set_dest(vm, &instr->dest,
                 operand_value(vm, &instr->src1) ^ operand_value(vm, &instr->src2));
        break;
    case Q_SHL:
        set_dest(vm, &instr->dest,
                 operand_value(vm, &instr->src1) << operand_value(vm, &instr->src2));
        break;
    case Q_SHR:
        set_dest(vm, &instr->dest,
                 operand_value(vm, &instr->src1) >> operand_value(vm, &instr->src2));
        break;

    /* ── Control flow ──────────────────────────────────── */
    case Q_JUMP:
        if (instr->src1.type == OPERAND_LABEL) {
            uint32_t lid = instr->src1.label;
            if (lid < VM_MAX_LABELS) {
                vm->ip = vm->label_map[lid];
                return VM_OK;
            }
        }
        return VM_ERR_BAD_JUMP;

    case Q_JUMP_IF:
        a = operand_value(vm, &instr->src1);
        if (a != 0 && instr->src2.type == OPERAND_LABEL) {
            vm->ip = vm->label_map[instr->src2.label];
            return VM_OK;
        }
        break;

    case Q_JUMP_IF_NOT:
        a = operand_value(vm, &instr->src1);
        if (a == 0 && instr->src2.type == OPERAND_LABEL) {
            vm->ip = vm->label_map[instr->src2.label];
            return VM_OK;
        }
        break;

    case Q_CALL:
        if (vm->call_depth >= VM_MAX_CALL_DEPTH)
            return VM_ERR_STACK_OF;
        vm->call_stack[vm->call_depth++] = vm->ip + 1;
        if (instr->src1.type == OPERAND_LABEL) {
            vm->ip = vm->label_map[instr->src1.label];
            return VM_OK;
        }
        return VM_ERR_BAD_JUMP;

    case Q_RET: {
        /* Copy return value to R0 (ABI convention) */
        int64_t ret_val = 0;
        if (instr->src1.type == OPERAND_VREG) {
            ret_val = vm->regs[instr->src1.vreg];
        } else if (instr->src1.type == OPERAND_IMM) {
            ret_val = instr->src1.imm;
        }
        if (vm->call_depth > 0) {
            vm->ip = vm->call_stack[--vm->call_depth];
            vm->regs[0] = ret_val;
            return VM_OK;
        }
        /* Cross-function return? */
        if (vm->func_depth > 0) {
            vm->func_depth--;
            /* Restore saved registers */
            uint32_t nregs = vm->func_stack[vm->func_depth].saved_reg_count;
            for (uint32_t ri = 0; ri < nregs; ri++) {
                vm->regs[ri] = vm->func_stack[vm->func_depth].saved_regs[ri];
            }
            free(vm->func_stack[vm->func_depth].saved_regs);
            vm->func_stack[vm->func_depth].saved_regs = NULL;
            vm->func_stack[vm->func_depth].saved_reg_count = 0;
            /* Put return value in R0 */
            vm->regs[0] = ret_val;
            vm->current_func = vm->func_stack[vm->func_depth].func;
            vm->ip = vm->func_stack[vm->func_depth].ip;
            vm_resolve_labels(vm, vm->current_func);
            return VM_OK;
        }
        vm->regs[0] = ret_val;
        return VM_HALT;
    }

    case Q_CALL_FUNC: {
        /* Call function by index */
        if (!vm->module) return VM_ERR_BAD_JUMP;
        uint32_t fidx = 0;
        if (instr->src1.type == OPERAND_FUNC_IDX)
            fidx = instr->src1.func_idx;
        else if (instr->src1.type == OPERAND_IMM)
            fidx = (uint32_t)instr->src1.imm;
        else
            return VM_ERR_BAD_JUMP;
        if (fidx >= vm->module->func_count) return VM_ERR_BAD_JUMP;
        const q_function_t *callee = &vm->module->functions[fidx];
        
        /* Save current function context and registers */
        if (vm->func_depth >= VM_MAX_CALL_DEPTH) return VM_ERR_STACK_OF;
        vm->func_stack[vm->func_depth].func = vm->current_func;
        vm->func_stack[vm->func_depth].ip = vm->ip + 1; /* return to next instr */
        /* Save all currently used registers */
        uint32_t nregs = vm->reg_count;
        vm->func_stack[vm->func_depth].saved_reg_count = nregs;
        vm->func_stack[vm->func_depth].saved_regs = NULL;
        if (nregs > 0) {
            vm->func_stack[vm->func_depth].saved_regs =
                (int64_t *)malloc(sizeof(int64_t) * nregs);
            if (!vm->func_stack[vm->func_depth].saved_regs) {
                vm->func_stack[vm->func_depth].saved_reg_count = 0;
                return VM_ERR_STACK_OF;
            }
            for (uint32_t ri = 0; ri < nregs; ri++) {
                vm->func_stack[vm->func_depth].saved_regs[ri] = vm->regs[ri];
            }
        }
        vm->func_depth++;
        
        /* Set up param vregs: arguments are in R0..R(n-1) already
         * Copy them into callee's param vregs  */
        for (uint32_t pi = 0; pi < callee->param_count && pi < Q_MAX_PARAMS; pi++) {
            vm->regs[callee->param_vregs[pi]] = vm->regs[pi];
        }
        
        /* Switch to callee */
        vm->current_func = callee;
        vm->ip = 0;
        vm_resolve_labels(vm, callee);
        return VM_OK;
    }

    /* ── I/O ───────────────────────────────────────────── */
    case Q_PRINT:
        a = operand_value(vm, &instr->src1);
        printf("%lld\n", (long long)a);
        break;

    case Q_INPUT:
        printf("input> ");
        if (scanf("%lld", &a) == 1) {
            set_dest(vm, &instr->dest, a);
        }
        break;

    /* ── Memory management ─────────────────────────────── */
    case Q_ALLOC: {
        int64_t sz = operand_value(vm, &instr->src1);
        void *p = calloc(1, (size_t)(sz > 0 ? sz : 1));
        if (p && vm->heap_count < VM_MAX_HEAP_BLOCKS) {
            vm->heap_blocks[vm->heap_count++] = p;
        }
        set_dest(vm, &instr->dest, (int64_t)(intptr_t)p);
        break;
    }
    case Q_FREE: {
        int64_t addr = operand_value(vm, &instr->src1);
        void *p = (void *)(intptr_t)addr;
        if (p) {
            for (uint32_t i = 0; i < vm->heap_count; i++) {
                if (vm->heap_blocks[i] == p) {
                    free(p);
                    vm->heap_blocks[i] = vm->heap_blocks[--vm->heap_count];
                    break;
                }
            }
        }
        break;
    }
    case Q_LOAD_BYTE: {
        int64_t base = operand_value(vm, &instr->src1);
        int64_t off  = operand_value(vm, &instr->src2);
        uint8_t *ptr = (uint8_t *)(intptr_t)base;
        set_dest(vm, &instr->dest, ptr ? (int64_t)ptr[off] : 0);
        break;
    }
    case Q_STORE_BYTE: {
        int64_t base = operand_value(vm, &instr->src1);
        int64_t off  = operand_value(vm, &instr->src2);
        int64_t val  = operand_value(vm, &instr->dest);
        uint8_t *ptr = (uint8_t *)(intptr_t)base;
        if (ptr) ptr[off] = (uint8_t)val;
        break;
    }
    case Q_LOAD_WORD: {
        int64_t base = operand_value(vm, &instr->src1);
        int64_t idx  = operand_value(vm, &instr->src2);
        int64_t *ptr = (int64_t *)(intptr_t)base;
        set_dest(vm, &instr->dest, ptr ? ptr[idx] : 0);
        break;
    }
    case Q_STORE_WORD: {
        int64_t base = operand_value(vm, &instr->src1);
        int64_t idx  = operand_value(vm, &instr->src2);
        int64_t val  = operand_value(vm, &instr->dest);
        int64_t *ptr = (int64_t *)(intptr_t)base;
        if (ptr) ptr[idx] = val;
        break;
    }

    /* ── String operations ─────────────────────────────── */
    case Q_STR_LEN: {
        const char *s = (const char *)(intptr_t)operand_value(vm, &instr->src1);
        set_dest(vm, &instr->dest, s ? (int64_t)strlen(s) : 0);
        break;
    }
    case Q_STR_GET: {
        const char *s = (const char *)(intptr_t)operand_value(vm, &instr->src1);
        int64_t idx = operand_value(vm, &instr->src2);
        set_dest(vm, &instr->dest,
                 (s && idx >= 0 && idx < (int64_t)strlen(s))
                     ? (int64_t)(unsigned char)s[idx] : 0);
        break;
    }
    case Q_STR_CAT: {
        const char *sa = (const char *)(intptr_t)operand_value(vm, &instr->src1);
        const char *sb = (const char *)(intptr_t)operand_value(vm, &instr->src2);
        if (!sa) sa = "";
        if (!sb) sb = "";
        size_t la = strlen(sa), lb = strlen(sb);
        char *cat = (char *)malloc(la + lb + 1);
        memcpy(cat, sa, la);
        memcpy(cat + la, sb, lb);
        cat[la + lb] = '\0';
        set_dest(vm, &instr->dest, vm_add_rt_string(vm, cat));
        break;
    }
    case Q_STR_EQ: {
        const char *sa = (const char *)(intptr_t)operand_value(vm, &instr->src1);
        const char *sb = (const char *)(intptr_t)operand_value(vm, &instr->src2);
        set_dest(vm, &instr->dest, (sa && sb && strcmp(sa, sb) == 0) ? 1 : 0);
        break;
    }

    /* ── File I/O ──────────────────────────────────────── */
    case Q_FILE_OPEN: {
        const char *path = (const char *)(intptr_t)operand_value(vm, &instr->src1);
        const char *mode = (const char *)(intptr_t)operand_value(vm, &instr->src2);
        FILE *f = (path && mode) ? fopen(path, mode) : NULL;
        set_dest(vm, &instr->dest, (int64_t)(intptr_t)f);
        break;
    }
    case Q_FILE_READ: {
        FILE *f = (FILE *)(intptr_t)operand_value(vm, &instr->src1);
        if (!f) { set_dest(vm, &instr->dest, 0); break; }
        fseek(f, 0, SEEK_END);
        long sz = ftell(f);
        fseek(f, 0, SEEK_SET);
        char *buf = (char *)malloc((size_t)sz + 1);
        size_t rd = fread(buf, 1, (size_t)sz, f);
        buf[rd] = '\0';
        set_dest(vm, &instr->dest, vm_add_rt_string(vm, buf));
        break;
    }
    case Q_FILE_WRITE: {
        FILE *f = (FILE *)(intptr_t)operand_value(vm, &instr->src1);
        const char *data = (const char *)(intptr_t)operand_value(vm, &instr->src2);
        if (f && data) fputs(data, f);
        break;
    }
    case Q_FILE_CLOSE: {
        FILE *f = (FILE *)(intptr_t)operand_value(vm, &instr->src1);
        if (f) fclose(f);
        break;
    }
    case Q_FILE_WRITE_BYTE: {
        FILE *f = (FILE *)(intptr_t)operand_value(vm, &instr->src1);
        int64_t byte = operand_value(vm, &instr->src2);
        if (f) fputc((int)byte, f);
        break;
    }

    /* ── Array operations ──────────────────────────────── */
    case Q_ARR_NEW: {
        int64_t cap = operand_value(vm, &instr->src1);
        set_dest(vm, &instr->dest, vm_array_new(vm, cap));
        break;
    }
    case Q_ARR_LEN: {
        int64_t v = operand_value(vm, &instr->src1);
        /* Polymorphic: if valid array handle, return array len;
           otherwise treat as string pointer and return strlen */
        if (v >= 0 && (uint32_t)v < vm->array_count) {
            set_dest(vm, &instr->dest, vm_array_len(vm, v));
        } else {
            const char *s = (const char *)(intptr_t)v;
            set_dest(vm, &instr->dest, (s && v != 0) ? (int64_t)strlen(s) : 0);
        }
        break;
    }
    case Q_ARR_GET: {
        int64_t arr = operand_value(vm, &instr->src1);
        int64_t idx = operand_value(vm, &instr->src2);
        set_dest(vm, &instr->dest, vm_array_get(vm, arr, idx));
        break;
    }
    case Q_ARR_SET: {
        int64_t arr = operand_value(vm, &instr->src1);
        int64_t idx = operand_value(vm, &instr->src2);
        int64_t val = operand_value(vm, &instr->dest);
        vm_array_set(vm, arr, idx, val);
        break;
    }
    case Q_ARR_PUSH: {
        int64_t arr = operand_value(vm, &instr->src1);
        int64_t val = operand_value(vm, &instr->src2);
        vm_array_push(vm, arr, val);
        break;
    }

    /* ── System ────────────────────────────────────────── */
    case Q_EXIT: {
        exit((int)operand_value(vm, &instr->src1));
        break; /* unreachable */
    }
    case Q_I_TO_STR: {
        char *buf = (char *)malloc(32);
        snprintf(buf, 32, "%lld", (long long)operand_value(vm, &instr->src1));
        set_dest(vm, &instr->dest, vm_add_rt_string(vm, buf));
        break;
    }
    case Q_STR_TO_I: {
        const char *s = (const char *)(intptr_t)operand_value(vm, &instr->src1);
        set_dest(vm, &instr->dest, s ? strtoll(s, NULL, 10) : 0);
        break;
    }
    case Q_PRINT_STR: {
        const char *s = (const char *)(intptr_t)operand_value(vm, &instr->src1);
        if (s) fputs(s, stdout);
        break;
    }
    case Q_GET_ARG: {
        int64_t idx = operand_value(vm, &instr->src1);
        if (idx >= 0 && idx < vm->arg_count) {
            set_dest(vm, &instr->dest, (int64_t)(intptr_t)vm->args[idx]);
        } else {
            set_dest(vm, &instr->dest, 0);
        }
        break;
    }
    case Q_ARG_COUNT: {
        set_dest(vm, &instr->dest, (int64_t)vm->arg_count);
        break;
    }

    /* ── Globals ───────────────────────────────────────── */
    case Q_LOAD_GLOBAL: {
        int64_t idx = operand_value(vm, &instr->src1);
        if (idx >= 0 && idx < (int64_t)VM_MAX_GLOBALS) {
            set_dest(vm, &instr->dest, vm->globals[(uint32_t)idx]);
        } else {
            set_dest(vm, &instr->dest, 0);
        }
        break;
    }
    case Q_STORE_GLOBAL: {
        int64_t idx = operand_value(vm, &instr->src1);
        int64_t val = operand_value(vm, &instr->src2);
        if (idx >= 0 && idx < (int64_t)VM_MAX_GLOBALS) {
            vm->globals[(uint32_t)idx] = val;
            if ((uint32_t)idx >= vm->global_count)
                vm->global_count = (uint32_t)idx + 1;
        }
        break;
    }

    /* ── Self-patching (§2.1) ──────────────────────────── */
    case Q_PATCH_POINT:
        vm->patches_triggered++;
        if (vm->patch_handler) {
            result = vm->patch_handler(instr->patch_id, vm->regs,
                                       vm->reg_count, vm->patch_userdata);
            /* Handler may modify regs directly; result goes to R0 */
            vm->regs[0] = result;
        }
        break;

    /* ── Label (no-op at runtime) ──────────────────────── */
    case Q_LABEL:
        break;

    case Q_HALT:
        return VM_HALT;

    default:
        return VM_ERR_BAD_OP;
    }

    vm->ip++;
    return VM_OK;
}

/* ═══════════════════════════════════════════════════════
 * Execute Function
 * ═══════════════════════════════════════════════════════ */

vm_status_t vm_exec_function(vm_state_t *vm, const q_function_t *func)
{
    vm->ip = 0;
    vm->current_func = func;
    vm->func_depth = 0;
    vm_resolve_labels(vm, func);

    while (vm->current_func) {
        const q_function_t *f = vm->current_func;
        if (vm->ip >= f->body_count) {
            /* Fell off end of function - implicit return 0 */
            vm->regs[0] = 0;
            if (vm->func_depth > 0) {
                vm->func_depth--;
                /* Restore caller's registers */
                uint32_t saved_count = vm->func_stack[vm->func_depth].saved_reg_count;
                for (uint32_t ri = 0; ri < saved_count; ri++) {
                    vm->regs[ri] = vm->func_stack[vm->func_depth].saved_regs[ri];
                }
                free(vm->func_stack[vm->func_depth].saved_regs);
                vm->func_stack[vm->func_depth].saved_regs = NULL;
                vm->func_stack[vm->func_depth].saved_reg_count = 0;
                vm->regs[0] = 0; /* overwrite with return value */
                vm->current_func = vm->func_stack[vm->func_depth].func;
                vm->ip = vm->func_stack[vm->func_depth].ip;
                if (vm->current_func)
                    vm_resolve_labels(vm, vm->current_func);
                continue;
            }
            break; /* Done */
        }
        vm_status_t s = vm_step(vm, &f->body[vm->ip]);
        if (s == VM_HALT) {
            /* Check if we should pop the call stack */
            if (vm->func_depth > 0) {
                vm->func_depth--;
                vm->current_func = vm->func_stack[vm->func_depth].func;
                vm->ip = vm->func_stack[vm->func_depth].ip;
                if (vm->current_func)
                    vm_resolve_labels(vm, vm->current_func);
                continue;
            }
            return VM_HALT;
        }
        if (s != VM_OK) {
            vm->status = s;
            return s;
        }
    }
    vm->status = VM_OK;
    return VM_OK;
}

/* ═══════════════════════════════════════════════════════
 * Execute Module
 * ═══════════════════════════════════════════════════════ */

vm_status_t vm_exec_module(vm_state_t *vm, const q_module_t *mod)
{
    /* Store module reference for string table access */
    vm_set_module(vm, mod);

    /* Look for __vir_init__ (global initializers) and run it first */
    for (uint32_t i = 0; i < mod->func_count; i++) {
        if (strcmp(mod->functions[i].name, "__vir_init__") == 0) {
            vm_status_t st = vm_exec_function(vm, &mod->functions[i]);
            if (st != VM_HALT && st != VM_OK) return st;
            break;
        }
    }

    /* Find main or __main__ */
    const q_function_t *entry = NULL;
    for (uint32_t i = 0; i < mod->func_count; i++) {
        if (strcmp(mod->functions[i].name, "main") == 0) {
            entry = &mod->functions[i];
            break;
        }
    }
    if (!entry) {
        for (uint32_t i = 0; i < mod->func_count; i++) {
            if (strcmp(mod->functions[i].name, "__main__") == 0) {
                entry = &mod->functions[i];
                break;
            }
        }
    }
    if (!entry && mod->func_count > 0) {
        /* Fall back to first non-init function */
        for (uint32_t i = 0; i < mod->func_count; i++) {
            if (strcmp(mod->functions[i].name, "__vir_init__") != 0) {
                entry = &mod->functions[i];
                break;
            }
        }
    }
    if (!entry) return VM_HALT;

    return vm_exec_function(vm, entry);
}

/* ═══════════════════════════════════════════════════════
 * Register access
 * ═══════════════════════════════════════════════════════ */

int64_t vm_get_reg(const vm_state_t *vm, uint32_t vreg)
{
    if (vreg >= VREG_MAX) return 0;
    return vm->regs[vreg];
}

void vm_set_reg(vm_state_t *vm, uint32_t vreg, int64_t value)
{
    if (vreg >= VREG_MAX) return;
    vm->regs[vreg] = value;
    if (vreg >= vm->reg_count)
        vm->reg_count = vreg + 1;
}

/* ═══════════════════════════════════════════════════════
 * Status string
 * ═══════════════════════════════════════════════════════ */

const char* vm_status_str(vm_status_t status)
{
    switch (status) {
        case VM_OK:           return "OK";
        case VM_HALT:         return "HALT";
        case VM_ERR_DIV_ZERO: return "ERR_DIVISION_BY_ZERO";
        case VM_ERR_STACK_OF: return "ERR_STACK_OVERFLOW";
        case VM_ERR_BAD_OP:   return "ERR_BAD_OPCODE";
        case VM_ERR_BAD_JUMP: return "ERR_BAD_JUMP_TARGET";
        case VM_ERR_PATCH:    return "ERR_PATCH_FAILED";
        default:              return "ERR_UNKNOWN";
    }
}

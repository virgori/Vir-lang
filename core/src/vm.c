/*
 * vm.c – Q-IR Virtual Machine (Interpreter)
 * ==========================================
 * Spec §2 – Thực thi Q-IR instructions trên thanh ghi ảo.
 * Đây là VM interpreter = Bản A (Safe) fallback.
 */

#include "vm.h"
#include "task.h"
#include "atomic.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <time.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <stdint.h>

static void vm_track_pointer_store(vm_state_t *vm, int64_t base,
                                   int64_t value);

/* Preserve enough caller vregs across Call. Nested returns can shrink
 * reg_count while outer locals remain live — always keep SAVE_MIN. */
#ifndef VM_CALL_SAVE_MIN
#define VM_CALL_SAVE_MIN  1024u
#endif

static inline uint32_t vm_call_save_count(const vm_state_t *vm)
{
    uint32_t nregs = vm->reg_count;
    if (nregs < VM_CALL_SAVE_MIN)
        nregs = VM_CALL_SAVE_MIN;
    if (vm->reg_need_by_fidx && vm->module && vm->current_func &&
        vm->current_func >= vm->module->functions &&
        vm->current_func < vm->module->functions + vm->module->func_count) {
        uint32_t fidx = (uint32_t)(vm->current_func - vm->module->functions);
        if (fidx < vm->label_by_fidx_n && vm->reg_need_by_fidx[fidx] > nregs)
            nregs = vm->reg_need_by_fidx[fidx];
    }
    if (nregs > VREG_MAX)
        nregs = VREG_MAX;
    return nregs;
}

static uint32_t vm_function_reg_need(const q_function_t *func)
{
    uint32_t max_vreg = 0;
    int found = 0;
    for (uint32_t pi = 0; pi < func->param_count && pi < Q_MAX_PARAMS; pi++) {
        if (func->param_vregs[pi] > max_vreg)
            max_vreg = func->param_vregs[pi];
        found = 1;
    }
    for (uint32_t i = 0; i < func->body_count; i++) {
        const q_instruction_t *ins = &func->body[i];
        const q_operand_t *ops[3] = { &ins->dest, &ins->src1, &ins->src2 };
        for (uint32_t oi = 0; oi < 3; oi++) {
            if (ops[oi]->type == OPERAND_VREG) {
                if (ops[oi]->vreg > max_vreg)
                    max_vreg = ops[oi]->vreg;
                found = 1;
            }
        }
    }
    if (!found)
        return 1;
    if (max_vreg >= VREG_MAX)
        return VREG_MAX;
    return max_vreg + 1;
}

/* Ensure the shared flat register save-stack can hold at least `need`
 * int64 entries. Grows geometrically. Returns 0 on success, -1 on OOM. */
static int vm_reg_save_reserve(vm_state_t *vm, uint32_t need)
{
    if (need <= vm->reg_save_cap)
        return 0;
    uint32_t new_cap = vm->reg_save_cap ? vm->reg_save_cap : (VM_CALL_SAVE_MIN * 4u);
    while (new_cap < need)
        new_cap *= 2u;
    int64_t *nb = (int64_t *)realloc(vm->reg_save_stack,
                                     (size_t)new_cap * sizeof(int64_t));
    if (!nb)
        return -1;
    vm->reg_save_stack = nb;
    vm->reg_save_cap = new_cap;
    return 0;
}

/* §13.7 try(timeout:) — monotonic clock in nanoseconds. */
static inline uint64_t vm_now_ns(void)
{
    struct timespec ts;
#if defined(CLOCK_MONOTONIC)
    clock_gettime(CLOCK_MONOTONIC, &ts);
#else
    clock_gettime(CLOCK_REALTIME, &ts);
#endif
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

/* ═══════════════════════════════════════════════════════
 * Task Integration for Async/Task/Wait (§22)
 * ═══════════════════════════════════════════════════════ */

/* Context structure to pass VM state and function index to tasks */
typedef struct {
    const q_module_t *module;
    uint32_t fn_idx;
    uint32_t nargs;
    int64_t  args[16]; /* Q_MAX_PARAMS = 16 */
} task_vm_context_t;

/* Task entry wrapper that executes a Q-IR function through the VM */
static int64_t task_entry_wrapper(void *arg)
{
    task_vm_context_t *ctx = (task_vm_context_t *)arg;
    if (!ctx || !ctx->module) {
        if (ctx) free(ctx);
        return 0;
    }

    /* Get the function from the module */
    if (ctx->fn_idx >= ctx->module->func_count) {
        free(ctx);
        return 0;
    }
    const q_function_t *func = &ctx->module->functions[ctx->fn_idx];

    /* Allocate VM state on the heap (vm_state_t is too large for the task stack).
     * IMPORTANT: Do NOT call vm_init() here because it calls
     * task_scheduler_init() which would reset the global scheduler
     * (destroying the currently running task context).
     * Instead, manually zero the VM state and set status. */
    vm_state_t *task_vm = (vm_state_t *)calloc(1, sizeof(vm_state_t));
    if (!task_vm) {
        free(ctx);
        return 0;
    }
    task_vm->status = VM_OK;
    vm_set_module(task_vm, ctx->module);

    /* Set up argument registers R0..R(nargs-1) before executing */
    for (uint32_t i = 0; i < ctx->nargs && i < 16; i++) {
        task_vm->regs[i] = ctx->args[i];
        if (i >= task_vm->reg_count)
            task_vm->reg_count = i + 1;
    }

    /* Copy arguments to the function's parameter vregs (like vm_dispatch_call does) */
    for (uint32_t pi = 0; pi < func->param_count && pi < 16; pi++) {
        task_vm->regs[func->param_vregs[pi]] = task_vm->regs[pi];
        if (func->param_vregs[pi] >= task_vm->reg_count)
            task_vm->reg_count = func->param_vregs[pi] + 1;
    }

    /* Execute the function through the VM */
    vm_exec_function(task_vm, func);
    
    /* Get the result from register 0 */
    int64_t result = task_vm->regs[0];
    
    /* Clean up VM and context.
     * vm_destroy frees arrays, heap blocks, strings, and ports. */
    vm_destroy(task_vm);
    free(task_vm);
    free(ctx);
    
    return result;
}

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

#define VM_ARRAY_TABLE_INIT_CAP 64u

static int vm_array_table_reserve(vm_state_t *vm, uint32_t need)
{
    if (need <= vm->array_cap)
        return 0;
    uint32_t cap = vm->array_cap ? vm->array_cap : VM_ARRAY_TABLE_INIT_CAP;
    while (cap < need && cap < VM_MAX_ARRAYS / 2u)
        cap *= 2u;
    if (cap < need || cap > VM_MAX_ARRAYS)
        return -1;
    vm_array_t *p = (vm_array_t *)realloc(vm->arrays, (size_t)cap * sizeof(*p));
    if (!p)
        return -1;
    memset(p + vm->array_cap, 0,
           (size_t)(cap - vm->array_cap) * sizeof(*p));
    vm->arrays = p;
    vm->array_cap = cap;
    return 0;
}

static int vm_array_free_reserve(vm_state_t *vm, uint32_t need)
{
    if (need <= vm->array_free_cap)
        return 0;
    uint32_t cap = vm->array_free_cap ? vm->array_free_cap : VM_ARRAY_TABLE_INIT_CAP;
    while (cap < need && cap < VM_MAX_ARRAYS / 2u)
        cap *= 2u;
    if (cap < need || cap > VM_MAX_ARRAYS)
        return -1;
    uint32_t *p = (uint32_t *)realloc(vm->array_free, (size_t)cap * sizeof(*p));
    if (!p)
        return -1;
    vm->array_free = p;
    vm->array_free_cap = cap;
    return 0;
}

static int64_t vm_array_new(vm_state_t *vm, int64_t cap)
{
    uint32_t idx;
    if (vm->array_free_count > 0) {
        idx = vm->array_free[--vm->array_free_count];
    } else {
        if (vm->array_count >= VM_MAX_ARRAYS) return -1;
        if (vm_array_table_reserve(vm, vm->array_count + 1u) != 0)
            return -1;
        idx = vm->array_count++;
    }
    vm->arrays[idx].cap = (uint32_t)(cap > 0 ? cap : 16);
    vm->arrays[idx].len = 0;
    vm->arrays[idx].data = (int64_t *)vm_heap_alloc(
        &vm->heap, (size_t)vm->arrays[idx].cap * sizeof(int64_t));
    if (!vm->arrays[idx].data) {
        vm->arrays[idx].cap = 0;
        /* Handle 0 is also the null sentinel for Q_FREE, so keep it out of
         * the reusable pool. */
        if (idx != 0 && vm_array_free_reserve(vm, vm->array_free_count + 1u) == 0)
            vm->array_free[vm->array_free_count++] = idx;
        return -1;
    }
    memset(vm->arrays[idx].data, 0,
           (size_t)vm->arrays[idx].cap * sizeof(int64_t));
    return (int64_t)idx;
}

static void vm_array_push(vm_state_t *vm, int64_t arr_handle, int64_t val)
{
    if (arr_handle < 0 || (uint32_t)arr_handle >= vm->array_count) return;
    vm_array_t *arr = &vm->arrays[(uint32_t)arr_handle];
    if (arr->len >= arr->cap) {
        uint32_t old_cap = arr->cap;
        int64_t *old = arr->data;
        arr->cap *= 2;
        arr->data = (int64_t *)vm_heap_realloc(
            &vm->heap, old, (size_t)arr->cap * sizeof(int64_t));
        if (!arr->data) {
            arr->data = old;
            arr->cap = old_cap;
            return;
        }
        memset(arr->data + old_cap, 0,
               (size_t)(arr->cap - old_cap) * sizeof(int64_t));
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

/* ═══════════════════════════════════════════════════════
 * §20 Dict — open-addressing hash table (linear probing).
 * ═══════════════════════════════════════════════════════ */

#define DICT_INIT_CAP 16

/* FNV-1a 64-bit hash for strings. */
static uint64_t vm_fnv1a(const char *s)
{
    uint64_t h = 0xcbf29ce484222325ULL;
    if (!s) return h;
    while (*s) {
        h ^= (uint8_t)*s++;
        h *= 0x100000001b3ULL;
    }
    return h;
}

/* splitmix64 for int-key spreading. */
static uint64_t vm_splitmix64(int64_t x)
{
    uint64_t z = (uint64_t)x + 0x9E3779B97F4A7C15ULL;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static void vm_dict_alloc(vm_dict_t *d, uint32_t cap)
{
    d->entries = (vm_dict_entry_t *)calloc(cap, sizeof(vm_dict_entry_t));
    d->cap = cap;
    d->count = 0;
}

static int64_t vm_dict_new(vm_state_t *vm)
{
    if (vm->dict_count >= VM_MAX_DICTS) return -1;
    uint32_t idx = vm->dict_count++;
    vm_dict_t *d = &vm->dicts[idx];
    memset(d, 0, sizeof(*d));
    vm_dict_alloc(d, DICT_INIT_CAP);
    return (int64_t)idx;
}

/* Probe for slot; return pointer to slot where key currently lives, or
 * first empty/tombstone slot suitable for insertion if not found.
 * *found = 1 if key exists, else 0. */
static vm_dict_entry_t *vm_dict_probe(vm_dict_t *d, int key_is_str,
                                      int64_t key_i, const char *key_s,
                                      int *found)
{
    *found = 0;
    if (d->cap == 0) return NULL;
    uint64_t h = key_is_str ? (uint64_t)key_i : vm_splitmix64(key_i);
    uint32_t mask = d->cap - 1;
    uint32_t slot = (uint32_t)(h & mask);
    vm_dict_entry_t *first_tomb = NULL;
    for (uint32_t probes = 0; probes < d->cap; probes++) {
        vm_dict_entry_t *e = &d->entries[slot];
        if (e->state == 0) {
            return first_tomb ? first_tomb : e;
        }
        if (e->state == 2) {
            if (!first_tomb) first_tomb = e;
        } else {
            /* occupied — compare key */
            if (key_is_str) {
                if (e->key_s && strcmp(e->key_s, key_s) == 0) {
                    *found = 1;
                    return e;
                }
            } else {
                if (!e->key_s && e->key_i == key_i) {
                    *found = 1;
                    return e;
                }
            }
        }
        slot = (slot + 1) & mask;
    }
    return first_tomb;
}

static void vm_dict_resize(vm_dict_t *d, uint32_t new_cap)
{
    vm_dict_entry_t *old = d->entries;
    uint32_t old_cap = d->cap;
    vm_dict_alloc(d, new_cap);
    for (uint32_t i = 0; i < old_cap; i++) {
        if (old[i].state != 1) {
            if (old[i].state == 2) free(old[i].key_s);
            continue;
        }
        int found = 0;
        int is_str = (old[i].key_s != NULL);
        vm_dict_entry_t *slot = vm_dict_probe(d, is_str,
                                              old[i].key_i,
                                              old[i].key_s, &found);
        if (slot) {
            slot->state = 1;
            slot->key_i = old[i].key_i;
            slot->key_s = old[i].key_s;  /* move ownership */
            slot->value = old[i].value;
            d->count++;
        } else {
            free(old[i].key_s);
        }
    }
    free(old);
}

static void vm_dict_set(vm_state_t *vm, int64_t handle, int key_is_str,
                        int64_t key, int64_t value)
{
    if (handle < 0 || (uint32_t)handle >= vm->dict_count) return;
    vm_dict_t *d = &vm->dicts[(uint32_t)handle];
    if (d->key_type == 0) d->key_type = key_is_str ? 2 : 1;
    else if ((d->key_type == 2) != (key_is_str != 0)) return; /* mismatch */

    if ((d->count + 1) * 4 >= d->cap * 3) {
        vm_dict_resize(d, d->cap * 2);
    }
    const char *ks = key_is_str ? (const char *)(intptr_t)key : NULL;
    int64_t ki = key_is_str ? (int64_t)vm_fnv1a(ks) : key;
    int found = 0;
    vm_dict_entry_t *slot = vm_dict_probe(d, key_is_str, ki, ks, &found);
    if (!slot) return;
    if (found) {
        slot->value = value;
        return;
    }
    slot->state = 1;
    slot->key_i = ki;
    slot->key_s = key_is_str ? strdup(ks ? ks : "") : NULL;
    slot->value = value;
    d->count++;
}

static int64_t vm_dict_get(vm_state_t *vm, int64_t handle, int key_is_str,
                           int64_t key)
{
    if (handle < 0 || (uint32_t)handle >= vm->dict_count) return 0;
    vm_dict_t *d = &vm->dicts[(uint32_t)handle];
    const char *ks = key_is_str ? (const char *)(intptr_t)key : NULL;
    int64_t ki = key_is_str ? (int64_t)vm_fnv1a(ks) : key;
    int found = 0;
    vm_dict_entry_t *slot = vm_dict_probe(d, key_is_str, ki, ks, &found);
    return (slot && found) ? slot->value : 0;
}

static int64_t vm_dict_has(vm_state_t *vm, int64_t handle, int key_is_str,
                           int64_t key)
{
    if (handle < 0 || (uint32_t)handle >= vm->dict_count) return 0;
    vm_dict_t *d = &vm->dicts[(uint32_t)handle];
    const char *ks = key_is_str ? (const char *)(intptr_t)key : NULL;
    int64_t ki = key_is_str ? (int64_t)vm_fnv1a(ks) : key;
    int found = 0;
    vm_dict_probe(d, key_is_str, ki, ks, &found);
    return found ? 1 : 0;
}

static void vm_dict_del(vm_state_t *vm, int64_t handle, int key_is_str,
                        int64_t key)
{
    if (handle < 0 || (uint32_t)handle >= vm->dict_count) return;
    vm_dict_t *d = &vm->dicts[(uint32_t)handle];
    const char *ks = key_is_str ? (const char *)(intptr_t)key : NULL;
    int64_t ki = key_is_str ? (int64_t)vm_fnv1a(ks) : key;
    int found = 0;
    vm_dict_entry_t *slot = vm_dict_probe(d, key_is_str, ki, ks, &found);
    if (slot && found) {
        free(slot->key_s);
        slot->key_s = NULL;
        slot->state = 2; /* tombstone */
        slot->value = 0;
        if (d->count > 0) d->count--;
    }
}

static int64_t vm_dict_len(vm_state_t *vm, int64_t handle)
{
    if (handle < 0 || (uint32_t)handle >= vm->dict_count) return 0;
    return (int64_t)vm->dicts[(uint32_t)handle].count;
}

/* Build an array of keys.  For string keys, entries are rt_string
 * pointers (registered via vm_add_rt_string so they persist). */
static int64_t vm_dict_keys(vm_state_t *vm, int64_t handle)
{
    int64_t arr = vm_array_new(vm, 16);
    if (handle < 0 || (uint32_t)handle >= vm->dict_count) return arr;
    vm_dict_t *d = &vm->dicts[(uint32_t)handle];
    for (uint32_t i = 0; i < d->cap; i++) {
        if (d->entries[i].state != 1) continue;
        int64_t k;
        if (d->entries[i].key_s) {
            k = (int64_t)(intptr_t)d->entries[i].key_s;
        } else {
            k = d->entries[i].key_i;
        }
        vm_array_push(vm, arr, k);
    }
    return arr;
}

static int64_t vm_dict_values(vm_state_t *vm, int64_t handle)
{
    int64_t arr = vm_array_new(vm, 16);
    if (handle < 0 || (uint32_t)handle >= vm->dict_count) return arr;
    vm_dict_t *d = &vm->dicts[(uint32_t)handle];
    for (uint32_t i = 0; i < d->cap; i++) {
        if (d->entries[i].state != 1) continue;
        vm_array_push(vm, arr, d->entries[i].value);
    }
    return arr;
}

static void vm_clear_func_frames(vm_state_t *vm)
{
    for (uint32_t i = 0; i < VM_MAX_CALL_DEPTH; i++) {
        vm->func_stack[i].saved_reg_count = 0;
        vm->func_stack[i].saved_base = 0;
        vm->func_stack[i].caller_reg_count = 0;
        vm->func_stack[i].caller_regs = NULL;
        vm->func_stack[i].func = NULL;
        vm->func_stack[i].ip = 0;
        vm->func_stack[i].arena_id = -1;
        vm->func_stack[i].arena_wm = 0;
        vm->func_stack[i].arena_escaped = 0;
        vm->func_stack[i].arena_mark_sp = 0;
    }
    vm->func_depth = 0;
    vm->reg_save_top = 0;
}

static int vm_mapping_register(vm_state_t *vm, void *ptr, size_t size)
{
    if (!vm || !ptr || ptr == MAP_FAILED || size == 0)
        return -1;
    if (vm->mapping_count >= vm->mapping_cap) {
        uint32_t cap = vm->mapping_cap ? vm->mapping_cap * 2u : 64u;
        vm_mapping_t *p = (vm_mapping_t *)realloc(
            vm->mappings, (size_t)cap * sizeof(*p));
        if (!p)
            return -1;
        vm->mappings = p;
        vm->mapping_cap = cap;
    }
    vm_mapping_t *m = &vm->mappings[vm->mapping_count++];
    m->ptr = ptr;
    m->size = size;
    m->live = 1;
    return 0;
}

static int vm_mapping_contains(const vm_state_t *vm, const void *ptr,
                               size_t size)
{
    if (!vm || !ptr)
        return 0;
    uintptr_t p = (uintptr_t)ptr;
    if (size > SIZE_MAX - p)
        return 0;
    uintptr_t end = p + size;
    for (int32_t i = (int32_t)vm->mapping_count - 1; i >= 0; i--) {
        const vm_mapping_t *m = &vm->mappings[i];
        uintptr_t begin = (uintptr_t)m->ptr;
        if (m->live && m->size <= SIZE_MAX - begin && p >= begin &&
            end <= begin + m->size)
            return 1;
    }
    return 0;
}

static void vm_mapping_remove(vm_state_t *vm, void *ptr)
{
    if (!vm || !ptr)
        return;
    for (uint32_t i = 0; i < vm->mapping_count; i++) {
        if (vm->mappings[i].live && vm->mappings[i].ptr == ptr) {
            vm->mappings[i].live = 0;
            return;
        }
    }
}

/* ═══════════════════════════════════════════════════════
 * Init / Reset / Destroy
 * ═══════════════════════════════════════════════════════ */

void vm_init(vm_state_t *vm)
{
    memset(vm, 0, sizeof(*vm));
    vm_heap_init(&vm->heap);
    vm_arena_ctx_init(&vm->arena_ctx);
    vm->regs = vm->root_regs;
    vm->status = VM_OK;
    vm->active_label_map = vm->label_map;
    /* §22.5 Initialize cooperative green-thread scheduler so that
     * Q_TASK_SPAWN/Q_TASK_YIELD/Q_TASK_WAIT and `await pass` are
     * operational. Safe to call repeatedly (idempotent reset). */
    task_scheduler_init();
}

void vm_reset(vm_state_t *vm)
{
    vm_clear_func_frames(vm);
    vm->regs = vm->root_regs;
    memset(vm->root_regs, 0, sizeof(vm->root_regs));
    vm->reg_count        = 0;
    vm->call_depth       = 0;
    vm->ip               = 0;
    vm->status           = VM_OK;
    vm->instr_executed   = 0;
    vm->patches_triggered = 0;
    vm->erx              = 0;
    vm->try_sp           = 0;
    vm->reg_save_top     = 0;
    memset(vm->pending_ref_bindings, 0, sizeof(vm->pending_ref_bindings));
}

void vm_destroy(vm_state_t *vm)
{
    vm_clear_func_frames(vm);
    vm_arena_ctx_destroy(&vm->arena_ctx);
    vm_heap_destroy(&vm->heap);
    for (uint32_t i = 0; i < vm->mapping_count; i++) {
        if (vm->mappings[i].live && vm->mappings[i].ptr)
            munmap(vm->mappings[i].ptr, vm->mappings[i].size);
    }
    free(vm->mappings);
    vm->mappings = NULL;
    vm->mapping_count = 0;
    vm->mapping_cap = 0;
    /* Array backing belongs to arenas; the VM owns only this metadata. */
    for (uint32_t i = 0; i < vm->array_count; i++) {
        vm->arrays[i].data = NULL;
        vm->arrays[i].len = 0;
        vm->arrays[i].cap = 0;
    }
    free(vm->arrays);
    free(vm->array_free);
    vm->arrays = NULL;
    vm->array_free = NULL;
    vm->array_count = 0;
    vm->array_cap = 0;
    vm->array_free_count = 0;
    vm->array_free_cap = 0;
    /* Runtime string table slots (payload freed via heap registry). */
    for (uint32_t i = 0; i < vm->rt_string_count; i++)
        vm->rt_strings[i] = NULL;
    vm->rt_string_count = 0;
    /* Free ports */
    for (uint32_t i = 0; i < vm->port_count; i++) {
        free(vm->ports[i].buf);
        vm->ports[i].buf = NULL;
    }
    vm->port_count = 0;
    /* Free label-map cache */
    if (vm->label_by_fidx) {
        for (uint32_t i = 0; i < vm->label_by_fidx_n; i++)
            free(vm->label_by_fidx[i]);
        free(vm->label_by_fidx);
        free(vm->label_len_by_fidx);
        free(vm->reg_need_by_fidx);
        vm->label_by_fidx = NULL;
        vm->label_len_by_fidx = NULL;
        vm->reg_need_by_fidx = NULL;
        vm->label_by_fidx_n = 0;
    }
    /* Free intrinsic cache */
    free(vm->func_intrinsic_cache);
    vm->func_intrinsic_cache = NULL;
    vm->func_intrinsic_cache_count = 0;
    /* Free shared register save-stack */
    free(vm->reg_save_stack);
    vm->reg_save_stack = NULL;
    vm->reg_save_cap = 0;
    vm->reg_save_top = 0;
    for (uint32_t i = 0; i < VM_MAX_CALL_DEPTH; i++) {
        free(vm->reg_windows[i]);
        vm->reg_windows[i] = NULL;
    }
    vm->reg_window_size = 0;
}

void vm_set_module(vm_state_t *vm, const q_module_t *mod)
{
    /* Drop previous module's label caches. */
    if (vm->label_by_fidx) {
        for (uint32_t i = 0; i < vm->label_by_fidx_n; i++)
            free(vm->label_by_fidx[i]);
        free(vm->label_by_fidx);
        free(vm->label_len_by_fidx);
        free(vm->reg_need_by_fidx);
        vm->label_by_fidx = NULL;
        vm->label_len_by_fidx = NULL;
        vm->reg_need_by_fidx = NULL;
        vm->label_by_fidx_n = 0;
    }
    free(vm->func_intrinsic_cache);
    vm->func_intrinsic_cache = NULL;
    vm->func_intrinsic_cache_count = 0;
    for (uint32_t i = 0; i < VM_MAX_CALL_DEPTH; i++) {
        free(vm->reg_windows[i]);
        vm->reg_windows[i] = NULL;
    }
    vm->reg_window_size = 0;
    vm->regs = vm->root_regs;
    vm->module = mod;
    if (mod && mod->func_count > 0) {
        vm->label_by_fidx = (uint32_t **)calloc(mod->func_count, sizeof(uint32_t *));
        vm->label_len_by_fidx = (uint32_t *)calloc(mod->func_count, sizeof(uint32_t));
        vm->reg_need_by_fidx = (uint32_t *)calloc(mod->func_count, sizeof(uint32_t));
        vm->label_by_fidx_n = mod->func_count;
        if (vm->reg_need_by_fidx) {
            uint32_t max_need = 1;
            for (uint32_t i = 0; i < mod->func_count; i++) {
                vm->reg_need_by_fidx[i] = vm_function_reg_need(&mod->functions[i]);
                if (vm->reg_need_by_fidx[i] > max_need)
                    max_need = vm->reg_need_by_fidx[i];
            }
            vm->reg_window_size = max_need;
        }
        vm->func_intrinsic_cache = (int16_t *)malloc(mod->func_count * sizeof(int16_t));
        vm->func_intrinsic_cache_count = mod->func_count;
        if (vm->func_intrinsic_cache) {
            for (uint32_t i = 0; i < mod->func_count; i++) {
                if (mod->functions[i].body_count == 0) {
                    const char *fname = mod->functions[i].name;
                    if (strncmp(fname, "syscall", 7) == 0) {
                        vm->func_intrinsic_cache[i] = -2;
                    } else {
                        int16_t found = -3;
                        for (int k = 0; k < VIR_MAX_INTRINSICS; k++) {
                            if (vir_intr_table[k].fn && strcmp(vir_intr_table[k].name, fname) == 0) {
                                found = (int16_t)k;
                                break;
                            }
                        }
                        vm->func_intrinsic_cache[i] = found;
                    }
                } else {
                    vm->func_intrinsic_cache[i] = -1;
                }
            }
        }
    }
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
    /* O(1) cache by function index, sized to that function's highest label.
     * The dispatch sites guard with label_count before indexing. */
    uint32_t fidx = UINT32_MAX;
    if (vm->module && func >= vm->module->functions &&
        func < vm->module->functions + vm->module->func_count) {
        fidx = (uint32_t)(func - vm->module->functions);
    }
    if (fidx != UINT32_MAX && fidx < vm->label_by_fidx_n &&
        vm->label_by_fidx && vm->label_by_fidx[fidx]) {
        vm->active_label_map = vm->label_by_fidx[fidx];
        vm->label_count = vm->label_len_by_fidx[fidx];
        return 0;
    }

    memset(vm->label_map, 0, sizeof(vm->label_map));
    vm->label_count = 0;
    vm->active_label_map = vm->label_map;
    uint32_t overflow_count = 0;

    static const q_function_t *dup_warned = NULL;
    for (uint32_t i = 0; i < func->body_count; i++) {
        if (func->body[i].opcode == Q_LABEL) {
            uint32_t lid = func->body[i].patch_id;
            if (lid < VM_MAX_LABELS) {
                if (vm->label_map[lid] != 0 && dup_warned != func &&
                    getenv("VIR_VM_DEBUG")) {
                    fprintf(stderr,
                            "[WARN] duplicate label id %u in '%s' (ip %u and %u)\n",
                            lid, func->name, vm->label_map[lid], i);
                    dup_warned = func;
                }
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

    if (vm->label_count > 0 && fidx != UINT32_MAX && fidx < vm->label_by_fidx_n &&
        vm->label_by_fidx) {
        uint32_t *cache =
            (uint32_t *)calloc(vm->label_count, sizeof(uint32_t));
        if (cache) {
            memcpy(cache, vm->label_map,
                   (size_t)vm->label_count * sizeof(uint32_t));
            free(vm->label_by_fidx[fidx]);
            vm->label_by_fidx[fidx] = cache;
            vm->label_len_by_fidx[fidx] = vm->label_count;
            vm->active_label_map = cache;
        }
    }
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * §Phase-9 Intrinsic Registry — handler implementations
 * ═══════════════════════════════════════════════════════
 * Each handler receives vir_intrinsic_ctx_t* with:
 *   ctx->args  = &vm->regs[0]   (arg registers)
 *   ctx->ret   = &vm->regs[dest] (return register)
 *   ctx->vm    = the VM state
 *
 * Design rules (from spec):
 *   - Handlers do NOT know about VM opcodes or bytecode
 *   - VM does NOT know about OS ABI or syscall numbers
 *   - Platform logic lives entirely inside the handler
 * ═══════════════════════════════════════════════════════ */

/* ── Syscall passthrough ────────────────────────────── */

/* VIR_INTR_SYSCALL: R0=syscall_num, R1..R6=args
 * Translates macOS BSD layer numbers (| 0x2000000). */
static void intr_syscall(vir_intrinsic_ctx_t *ctx) {
    int64_t s = ctx->args[0] & 0xFFFFFF;
    int64_t r1 = ctx->args[1], r2 = ctx->args[2], r3 = ctx->args[3];
    int64_t r4 = ctx->args[4], r5 = ctx->args[5];
    int64_t result = -1;
    if (getenv("VIR_DEBUG_SYSCALL")) {
        fprintf(stderr, "[SYSCALL] num=%lld r1=%lld (%s) r2=%lld r3=%lld\n",
                (long long)s, (long long)r1, (s == 5 && r1 != 0) ? (const char *)(uintptr_t)r1 : "", (long long)r2, (long long)r3);
    }
    switch (s) {
    case 1:   exit((int)r1);                                                    break;
    case 3:   result = read((int)r1, (void *)(uintptr_t)r2, (size_t)r3);      break;
    case 4:   result = write((int)r1, (const void *)(uintptr_t)r2, (size_t)r3); break;
    case 5: {
        int flags = (int)r2;
#ifndef VIR_PLATFORM_MACOS
        int lflags = 0;
        if (flags & 0x0001) lflags |= O_WRONLY;
        if (flags & 0x0002) lflags |= O_RDWR;
        if (flags & 0x0008) lflags |= O_APPEND;
        if (flags & 0x0200) lflags |= O_CREAT;
        if (flags & 0x0400) lflags |= O_TRUNC;
        if (flags & 0x0800) lflags |= O_EXCL;
        flags = lflags;
#endif
        result = open((const char *)(uintptr_t)r1, flags, (mode_t)r3);
        break;
    }
    case 6:   result = close((int)r1);                                          break;
    case 73: {
        void *p = (void *)(uintptr_t)r1;
        result = munmap(p, (size_t)r2);
        if (result == 0)
            vm_mapping_remove(ctx->vm, p);
        break;
    }
    case 197: {
        int flags = (int)r4;
#ifndef VIR_PLATFORM_MACOS
        if (flags & 0x1000) {
            flags = (flags & ~0x1000) | MAP_ANONYMOUS;
        }
#endif
        void *p = mmap((void *)(uintptr_t)r1, (size_t)r2,
                       (int)r3, flags, (int)r5, 0);
        result = (p == MAP_FAILED) ? -1 : (int64_t)(intptr_t)p;
        if (p != MAP_FAILED)
            vm_mapping_register(ctx->vm, p, (size_t)r2);
        break;
    }
    case 199: result = lseek((int)r1, (off_t)r2, (int)r3);                    break;
    default:  result = -1;                                                      break;
    }
    if (getenv("VIR_DEBUG_SYSCALL")) {
        fprintf(stderr, "[SYSCALL RESULT] num=%lld result=%lld errno=%d\n",
                (long long)s, (long long)result, errno);
    }
    *ctx->ret = result;
}

static void intr_sys_read(vir_intrinsic_ctx_t *ctx) {
    *ctx->ret = (int64_t)read((int)ctx->args[0],
                              (void *)(uintptr_t)ctx->args[1],
                              (size_t)ctx->args[2]);
}

static void intr_sys_write(vir_intrinsic_ctx_t *ctx) {
    *ctx->ret = (int64_t)write((int)ctx->args[0],
                               (const void *)(uintptr_t)ctx->args[1],
                               (size_t)ctx->args[2]);
}

static void intr_sys_open(vir_intrinsic_ctx_t *ctx) {
    *ctx->ret = (int64_t)open((const char *)(uintptr_t)ctx->args[0],
                              (int)ctx->args[1],
                              (mode_t)ctx->args[2]);
    if (*ctx->ret < 0) {
        perror("sys_open failed");
        fprintf(stderr, "Failed path: %s\n", (const char *)(uintptr_t)ctx->args[0]);
    }
}

static void intr_sys_close(vir_intrinsic_ctx_t *ctx) {
    *ctx->ret = (int64_t)close((int)ctx->args[0]);
}

static void intr_sys_lseek(vir_intrinsic_ctx_t *ctx) {
    *ctx->ret = (int64_t)lseek((int)ctx->args[0],
                               (off_t)ctx->args[1],
                               (int)ctx->args[2]);
}

static void intr_sys_mmap(vir_intrinsic_ctx_t *ctx) {
    void *p = mmap((void *)(uintptr_t)ctx->args[0],
                   (size_t)ctx->args[1],
                   (int)ctx->args[2],
                   (int)ctx->args[3],
                   (int)ctx->args[4],
                   (off_t)ctx->args[5]);
    if (p != MAP_FAILED)
        vm_mapping_register(ctx->vm, p, (size_t)ctx->args[1]);
    *ctx->ret = (int64_t)(intptr_t)p;
}

static void intr_sys_munmap(vir_intrinsic_ctx_t *ctx) {
    void *p = (void *)(uintptr_t)ctx->args[0];
    *ctx->ret = (int64_t)munmap(p, (size_t)ctx->args[1]);
    if (*ctx->ret == 0)
        vm_mapping_remove(ctx->vm, p);
}

static void intr_sys_exit(vir_intrinsic_ctx_t *ctx) {
    exit((int)ctx->args[0]);
}

/* ── Memory ─────────────────────────────────────────── */

static void intr_memcpy(vir_intrinsic_ctx_t *ctx) {
    memcpy((void *)(uintptr_t)ctx->args[0],
           (const void *)(uintptr_t)ctx->args[1],
           (size_t)ctx->args[2]);
    *ctx->ret = ctx->args[0];
}

static void intr_memset(vir_intrinsic_ctx_t *ctx) {
    memset((void *)(uintptr_t)ctx->args[0],
           (int)ctx->args[1],
           (size_t)ctx->args[2]);
    *ctx->ret = ctx->args[0];
}

/* Raw memory access for virc_boot `extern func native_*` shims (Stage-0 VM). */
static int vm_host_ptr_ok(const vm_state_t *vm, int64_t base, size_t size)
{
    if (!vm || base <= 0)
        return 0;
    if (base >= VM_MMIO_BASE && base < VM_MMIO_BASE + (int64_t)VM_MMIO_SIZE)
        return 1;
    const void *p = (const void *)(intptr_t)base;
    if (vm_arena_contains_in(&vm->arena_ctx, p, size) ||
        vm_mapping_contains(vm, p, size) ||
        vm_heap_contains(&vm->heap, p, size))
        return 1;
    /* String literals belong to module static storage. */
    if (vm->module) {
        for (uint32_t i = 0; i < vm->module->string_count; i++) {
            const char *s = vm->module->strings[i];
            if (s == (const char *)p)
                return size <= strlen(s) + 1u;
        }
    }
    return 0;
}

static int vm_host_read_ptr_ok(const vm_state_t *vm, int64_t base, size_t size)
{
    if (vm_host_ptr_ok(vm, base, size))
        return 1;
    if (!vm || base <= 0)
        return 0;

    /* Q_GET_ARG returns host-owned C strings.  They are intentionally not
     * copied into the VM heap, so native reads (used by rt_strlen/strcmp)
     * must recognize the exact argv base pointer.  Keep argv read-only. */
    const char *p = (const char *)(intptr_t)base;
    for (int i = 0; i < vm->arg_count; i++) {
        const char *arg = vm->args ? vm->args[i] : NULL;
        if (arg == p)
            return size <= strlen(arg) + 1u;
    }
    return 0;
}

static void intr_native_read_u8(vir_intrinsic_ctx_t *ctx)
{
    int64_t base = ctx->args[0];
    int64_t off = ctx->args[1];
    if (off < 0 || (uint64_t)off > SIZE_MAX - 1u ||
        !vm_host_read_ptr_ok(ctx->vm, base, (size_t)off + 1u)) {
        *ctx->ret = 0;
        return;
    }
    const uint8_t *ptr = (const uint8_t *)(intptr_t)base;
    *ctx->ret = (int64_t)ptr[off];
}

static void intr_native_write_u8(vir_intrinsic_ctx_t *ctx)
{
    int64_t base = ctx->args[0];
    int64_t off = ctx->args[1];
    int64_t val = ctx->args[2];
    if (off < 0 || (uint64_t)off > SIZE_MAX - 1u ||
        !vm_host_ptr_ok(ctx->vm, base, (size_t)off + 1u)) {
        *ctx->ret = 0;
        return;
    }
    uint8_t *ptr = (uint8_t *)(intptr_t)base;
    ptr[off] = (uint8_t)val;
    *ctx->ret = 0;
}

static void intr_native_read_i64(vir_intrinsic_ctx_t *ctx)
{
    int64_t base = ctx->args[0];
    int64_t off = ctx->args[1];
    if (off < 0) {
        *ctx->ret = 0;
        return;
    }
    if (base >= VM_MMIO_BASE && base < VM_MMIO_BASE + (int64_t)VM_MMIO_SIZE) {
        size_t slot = (size_t)((base - VM_MMIO_BASE) + off) / sizeof(int64_t);
        size_t slots = VM_MMIO_SIZE / sizeof(int64_t);
        *ctx->ret = slot < slots ? ctx->vm->mmio_region[slot] : 0;
        return;
    }
    if ((uint64_t)off > SIZE_MAX - sizeof(int64_t) ||
        !vm_host_read_ptr_ok(ctx->vm, base,
                             (size_t)off + sizeof(int64_t))) {
        *ctx->ret = 0;
        return;
    }
    const int64_t *ptr = (const int64_t *)((const char *)(intptr_t)base + off);
    *ctx->ret = *ptr;
}

static void intr_native_write_i64(vir_intrinsic_ctx_t *ctx)
{
    int64_t base = ctx->args[0];
    int64_t off = ctx->args[1];
    int64_t val = ctx->args[2];
    if (off < 0) {
        *ctx->ret = 0;
        return;
    }
    if (base >= VM_MMIO_BASE && base < VM_MMIO_BASE + (int64_t)VM_MMIO_SIZE) {
        size_t slot = (size_t)((base - VM_MMIO_BASE) + off) / sizeof(int64_t);
        size_t slots = VM_MMIO_SIZE / sizeof(int64_t);
        if (slot < slots)
            ctx->vm->mmio_region[slot] = val;
        *ctx->ret = 0;
        return;
    }
    if ((uint64_t)off > SIZE_MAX - sizeof(int64_t) ||
        !vm_host_ptr_ok(ctx->vm, base, (size_t)off + sizeof(int64_t))) {
        *ctx->ret = 0;
        return;
    }
    int64_t *ptr = (int64_t *)((char *)(intptr_t)base + off);
    /* Collections such as Vec<T> write their elements through this
     * intrinsic.  An iteration-local entity stored in a pre-existing Vec
     * outlives the loop checkpoint just like Q_STORE_WORD does. */
    vm_track_pointer_store(ctx->vm, base, val);
    *ptr = val;
    *ctx->ret = 0;
}

static void intr_native_file_read(vir_intrinsic_ctx_t *ctx)
{
    FILE *f = (FILE *)(intptr_t)ctx->args[0];
    void *buf = (void *)(intptr_t)ctx->args[1];
    size_t n = (size_t)ctx->args[2];
    if (!f || !buf) {
        *ctx->ret = -1;
        return;
    }
    *ctx->ret = (int64_t)fread(buf, 1, n, f);
}

static void intr_native_file_write(vir_intrinsic_ctx_t *ctx)
{
    FILE *f = (FILE *)(intptr_t)ctx->args[0];
    const void *buf = (const void *)(intptr_t)ctx->args[1];
    size_t n = (size_t)ctx->args[2];
    if (!f || !buf) {
        *ctx->ret = -1;
        return;
    }
    *ctx->ret = (int64_t)fwrite(buf, 1, n, f);
}

static void intr_native_errno(vir_intrinsic_ctx_t *ctx)
{
    *ctx->ret = (int64_t)errno;
}

/* ── Bitwise / Math ──────────────────────────────────── */

#if defined(_MSC_VER)
#include <intrin.h>
#endif

static void intr_clz(vir_intrinsic_ctx_t *ctx) {
    uint64_t v = (uint64_t)ctx->args[0];
#if defined(__GNUC__) || defined(__clang__)
    *ctx->ret = (v == 0) ? 64 : __builtin_clzll(v);
#elif defined(_MSC_VER)
    unsigned long index;
    *ctx->ret = _BitScanReverse64(&index, v) ? (63 - index) : 64;
#else
    int count = 0;
    while (!(v & (1ULL << 63)) && count < 64) { v <<= 1; count++; }
    *ctx->ret = count;
#endif
}

static void intr_ctz(vir_intrinsic_ctx_t *ctx) {
    uint64_t v = (uint64_t)ctx->args[0];
#if defined(__GNUC__) || defined(__clang__)
    *ctx->ret = (v == 0) ? 64 : __builtin_ctzll(v);
#elif defined(_MSC_VER)
    unsigned long index;
    *ctx->ret = _BitScanForward64(&index, v) ? index : 64;
#else
    int count = 0;
    while (!(v & 1) && count < 64) { v >>= 1; count++; }
    *ctx->ret = count;
#endif
}

static void intr_popcnt(vir_intrinsic_ctx_t *ctx) {
    uint64_t v = (uint64_t)ctx->args[0];
#if defined(__GNUC__) || defined(__clang__)
    *ctx->ret = __builtin_popcountll(v);
#elif defined(_MSC_VER)
    *ctx->ret = __popcnt64(v);
#else
    int count = 0;
    while (v) { count += v & 1; v >>= 1; }
    *ctx->ret = count;
#endif
}

static void intr_bitnot(vir_intrinsic_ctx_t *ctx) {
    uint64_t v = (uint64_t)ctx->args[0];
    *ctx->ret = ~v;
}

static void intr_bswap(vir_intrinsic_ctx_t *ctx) {
    uint64_t v = (uint64_t)ctx->args[0];
#if defined(__GNUC__) || defined(__clang__)
    *ctx->ret = __builtin_bswap64(v);
#elif defined(_MSC_VER)
    *ctx->ret = _byteswap_uint64(v);
#else
    *ctx->ret = ((v & 0xFF00000000000000ULL) >> 56) |
                ((v & 0x00FF000000000000ULL) >> 40) |
                ((v & 0x0000FF0000000000ULL) >> 24) |
                ((v & 0x000000FF00000000ULL) >>  8) |
                ((v & 0x00000000FF000000ULL) <<  8) |
                ((v & 0x0000000000FF0000ULL) << 24) |
                ((v & 0x000000000000FF00ULL) << 40) |
                ((v & 0x00000000000000FFULL) << 56);
#endif
}

/* ── Atomics ─────────────────────────────────────────── */

static void intr_atomic_load(vir_intrinsic_ctx_t *ctx) {
    int64_t *ptr = (int64_t *)(uintptr_t)ctx->args[0];
#if defined(__GNUC__) || defined(__clang__)
    *ctx->ret = __atomic_load_n(ptr, __ATOMIC_SEQ_CST);
#else
    *ctx->ret = *ptr;
#endif
}

static void intr_atomic_store(vir_intrinsic_ctx_t *ctx) {
    int64_t *ptr = (int64_t *)(uintptr_t)ctx->args[0];
    int64_t val = ctx->args[1];
#if defined(__GNUC__) || defined(__clang__)
    __atomic_store_n(ptr, val, __ATOMIC_SEQ_CST);
#else
    *ptr = val;
#endif
    *ctx->ret = 0;
}

static void intr_atomic_add(vir_intrinsic_ctx_t *ctx) {
    int64_t *ptr = (int64_t *)(uintptr_t)ctx->args[0];
    int64_t val = ctx->args[1];
#if defined(__GNUC__) || defined(__clang__)
    *ctx->ret = __atomic_fetch_add(ptr, val, __ATOMIC_SEQ_CST);
#else
    int64_t old = *ptr;
    *ptr = old + val;
    *ctx->ret = old;
#endif
}

static void intr_atomic_sub(vir_intrinsic_ctx_t *ctx) {
    int64_t *ptr = (int64_t *)(uintptr_t)ctx->args[0];
    int64_t val = ctx->args[1];
#if defined(__GNUC__) || defined(__clang__)
    *ctx->ret = __atomic_fetch_sub(ptr, val, __ATOMIC_SEQ_CST);
#else
    int64_t old = *ptr;
    *ptr = old - val;
    *ctx->ret = old;
#endif
}

/* ── Debug / Trap ───────────────────────────────────── */

static void intr_trap(vir_intrinsic_ctx_t *ctx) {
    (void)ctx;
    abort();
}

/* ═══════════════════════════════════════════════════════
 * §Phase-9 Intrinsic Table (VIR_INTR_* → handler)
 * ═══════════════════════════════════════════════════════
 * Order MUST match vir_intrinsic_id_t in vm.h exactly.
 * Entries beyond VIR_INTR_COUNT are zero-initialized
 * (NULL fn pointer → treated as no-op with result=0).
 * ═══════════════════════════════════════════════════════ */
vir_intr_desc_t vir_intr_table[VIR_MAX_INTRINSICS] = {
    /* ID 0 */ { intr_syscall,   0, INTR_IMPURE,              "syscall"    },
    /* ID 1 */ { intr_sys_read,  3, INTR_IMPURE,              "sys_read"   },
    /* ID 2 */ { intr_sys_write, 3, INTR_IMPURE,              "sys_write"  },
    /* ID 3 */ { intr_sys_open,  3, INTR_IMPURE,              "sys_open"   },
    /* ID 4 */ { intr_sys_close, 1, INTR_IMPURE,              "sys_close"  },
    /* ID 5 */ { intr_sys_lseek, 3, INTR_IMPURE,              "sys_lseek"  },
    /* ID 6 */ { intr_sys_mmap,  6, INTR_IMPURE,              "sys_mmap"   },
    /* ID 7 */ { intr_sys_munmap,2, INTR_IMPURE,              "sys_munmap" },
    /* ID 8 */ { intr_sys_exit,  1, INTR_IMPURE | INTR_TRAP,  "sys_exit"   },
    /* ID 9 */ { intr_memcpy,    3, INTR_IMPURE,              "memcpy"     },
    /* ID10 */ { intr_memset,    3, INTR_IMPURE,              "memset"     },
    /* ID11 */ { intr_trap,      0, INTR_IMPURE | INTR_TRAP,  "trap"       },
    /* ID12 */ { intr_clz,       1, INTR_PURE,                "clz"        },
    /* ID13 */ { intr_ctz,       1, INTR_PURE,                "ctz"        },
    /* ID14 */ { intr_popcnt,    1, INTR_PURE,                "popcnt"     },
    /* ID15 */ { intr_bswap,     1, INTR_PURE,                "bswap"      },
    /* ID16 */ { intr_atomic_load, 1, INTR_IMPURE,            "atomic_load" },
    /* ID17 */ { intr_atomic_store, 2, INTR_IMPURE,           "atomic_store" },
    /* ID18 */ { intr_atomic_add, 2, INTR_IMPURE,             "atomic_add" },
    /* ID19 */ { intr_atomic_sub, 2, INTR_IMPURE,             "atomic_sub" },
    /* virc_boot extern memory shims (empty body → name dispatch) */
    /* ID20 */ { intr_native_read_u8,  2, INTR_PURE,          "native_read_u8" },
    /* ID21 */ { intr_native_write_u8, 3, INTR_IMPURE,        "native_write_u8" },
    /* ID22 */ { intr_native_read_i64, 2, INTR_PURE,          "native_read_i64" },
    /* ID23 */ { intr_native_write_i64,3, INTR_IMPURE,        "native_write_i64" },
    /* ID36 */ { intr_memcpy,  3, INTR_IMPURE,          "native_mem_copy" },
    /* ID37 */ { intr_memcpy,  3, INTR_IMPURE,          "native_memcpy" },
    /* ID38 */ { intr_memcpy,  3, INTR_IMPURE,          "native_memmove" },
    /* ID24 */ { intr_native_read_u8,  2, INTR_PURE,          "read_byte" },
    /* ID25 */ { intr_native_read_u8,  2, INTR_PURE,          "read_u8" },
    /* virc_boot extern syscall shims (empty body → name dispatch) */
    /* ID26 */ { intr_syscall, 1, INTR_IMPURE,              "syscall0" },
    /* ID27 */ { intr_syscall, 2, INTR_IMPURE,              "syscall1" },
    /* ID28 */ { intr_syscall, 3, INTR_IMPURE,              "syscall2" },
    /* ID29 */ { intr_syscall, 4, INTR_IMPURE,              "syscall3" },
    /* ID30 */ { intr_syscall, 5, INTR_IMPURE,              "syscall4" },
    /* ID31 */ { intr_syscall, 6, INTR_IMPURE,              "syscall5" },
    /* ID32 */ { intr_syscall, 7, INTR_IMPURE,              "syscall6" },
    /* stdlib file.vri native I/O (Q_INTRINSIC by numeric id) */
    /* ID33 */ { intr_native_file_read,  3, INTR_IMPURE,     "native_file_read" },
    /* ID34 */ { intr_native_file_write, 3, INTR_IMPURE,     "native_file_write" },
    /* ID35 */ { intr_native_errno,      0, INTR_PURE,       "native_errno" },
    /* unused 36-39 (used by memcpy shims earlier) */
    /* ID39 */ { NULL, 0, 0, NULL },
    /* ID40 */ { intr_bitnot, 1, INTR_PURE,                  "bitnot"     },
};





/* Shared dispatch used by both Q_CALL_FUNC and Q_CALL_INDIRECT.
 * Switches to a per-depth register window, copies arguments into callee
 * param vregs, and switches ip/current_func. Caller registers remain in
 * their own window, so Call/return no longer memcpy the whole bank. */
static void vm_restore_caller_window(vm_state_t *vm, uint32_t frame_index)
{
    /* memcpy Call path: pop saved caller regs from the flat save-stack. */
    uint32_t nrestore = vm->func_stack[frame_index].saved_reg_count;
    uint32_t base = vm->func_stack[frame_index].saved_base;
    for (uint32_t ri = 0; ri < nrestore; ri++)
        vm->regs[ri] = vm->reg_save_stack[base + ri];
    vm->reg_save_top = base;
    vm->reg_count = vm->func_stack[frame_index].caller_reg_count;
    vm->func_stack[frame_index].saved_reg_count = 0;
    vm->func_stack[frame_index].caller_regs = NULL;
}

static int vm_enter_call_arena(vm_state_t *vm, uint32_t frame)
{
    int arena_id = vm_arena_tl_get_in(&vm->arena_ctx);
    if (arena_id < 0)
        return -1;
    /* A function is a logical region in the current arena.  Giving every
     * tiny lexer helper its own mmap page made per-character calls retain a
     * minimum 64 KiB mapping.  A watermark provides the specified O(1)
     * function-scope lifetime while keeping allocations densely packed. */
    vm->func_stack[frame].arena_id = arena_id;
    vm->func_stack[frame].arena_wm =
        vm_arena_save_in(&vm->arena_ctx, arena_id);
    vm->func_stack[frame].arena_escaped = 0;
    vm->func_stack[frame].arena_mark_sp = vm->arena_mark_sp;
    return 0;
}

static void vm_track_pointer_store(vm_state_t *vm, int64_t base, int64_t value)
{
    if (!vm || value == 0)
        return;
    const void *src = (const void *)(intptr_t)value;
    const void *dst = (const void *)(intptr_t)base;
    /* The self-host compiler performs pointer-store tracking for every Vec
     * element and record field, but nearly all of those values are scalars or
     * heap objects.  Reject non-arena values once instead of walking every
     * active loop/function watermark for them. */
    if (vm_arena_owner_in(&vm->arena_ctx, src, 1) < 0)
        return;
    /* An enclosing loop checkpoint remains a lifetime boundary while calls
     * made by its body are running.  For example vec_reserve() can allocate
     * a new backing store two frames below tokenize() and install it in a
     * Vec that predates the tokenize iteration.  Walk every active mark,
     * rather than requiring the store to happen at the mark's func_depth. */
    for (uint8_t mi = 0; mi < vm->arena_mark_sp; mi++) {
        int mark_arena = vm->arena_marks[mi].arena_id;
        size_t mark_wm = vm->arena_marks[mi].watermark;
        int src_new = vm_arena_contains_after_in(&vm->arena_ctx, mark_arena,
                                                 src, 1, mark_wm);
        int dst_new = vm_arena_contains_after_in(&vm->arena_ctx, mark_arena,
                                                 dst, 1, mark_wm);
        if (src_new &&
            (base == 0 ||
             !dst_new))
            vm->arena_marks[mi].escaped = 1;
    }

    /* Function watermarks share the same physical arena.  If a nested call
     * installs one of its allocations in storage that predates an enclosing
     * caller, every enclosing watermark crossed by that store must retain
     * the region.  Marking only the immediate callee lets the next caller
     * (vec_push around vec_reserve, for example) free the live allocation. */
    for (uint32_t frame = 0; frame < vm->func_depth; frame++) {
        int arena_id = vm->func_stack[frame].arena_id;
        size_t watermark = vm->func_stack[frame].arena_wm;
        if (vm_arena_contains_after_in(&vm->arena_ctx, arena_id, src, 1,
                                       watermark) &&
            (base == 0 ||
             !vm_arena_contains_after_in(&vm->arena_ctx, arena_id, dst, 1,
                                         watermark)))
            vm->func_stack[frame].arena_escaped = 1;
    }
}

static void vm_track_iteration_value(vm_state_t *vm, int64_t value)
{
    if (!vm || value == 0 || vm->arena_mark_sp == 0)
        return;
    uint8_t mi = vm->arena_mark_sp - 1u;
    if (vm->arena_marks[mi].func_depth != vm->func_depth)
        return;
    if (vm_arena_contains_after_in(&vm->arena_ctx,
                                   vm->arena_marks[mi].arena_id,
                                   (const void *)(intptr_t)value, 1,
                                   vm->arena_marks[mi].watermark))
        vm->arena_marks[mi].escaped = 1;
}

static int vm_value_escapes_call(vm_state_t *vm, int64_t value,
                                 int arena_id, size_t watermark)
{
    if (value == 0)
        return 0;

    /* Raw entity/string pointer returned or written through a ref. */
    const void *p = (const void *)(intptr_t)value;
    if (vm_arena_contains_after_in(&vm->arena_ctx, arena_id, p, 1,
                                   watermark))
        return 1;

    /* A promoted record is a shallow POD copy.  Its fields may still point
     * at nested records/strings in the function region, so retain that
     * region when a heap return contains an arena pointer. */
    size_t heap_size = vm_heap_size_of(&vm->heap, p);
    if (heap_size >= sizeof(int64_t)) {
        const int64_t *words = (const int64_t *)p;
        size_t count = heap_size / sizeof(*words);
        for (size_t i = 0; i < count; i++) {
            const void *nested = (const void *)(intptr_t)words[i];
            if (vm_arena_contains_after_in(&vm->arena_ctx, arena_id,
                                           nested, 1, watermark))
                return 1;
        }
    }

    /* Array/dict handles are untagged small integers and overlap ordinary
     * scalar return values.  Scanning a large token Vec whenever a helper
     * returns 0, 1, ... creates catastrophic O(n^2) behaviour.  All stores
     * into arrays, dicts, globals and native records pass through
     * vm_track_pointer_store(), which marks the crossed region at write time;
     * therefore handle contents do not need to be rescanned on return. */
    return 0;
}

static void vm_leave_call_arena(vm_state_t *vm, uint32_t frame,
                                int64_t ret_val,
                                const int64_t *ref_values,
                                uint32_t ref_count)
{
    int arena_id = vm->func_stack[frame].arena_id;
    size_t watermark = vm->func_stack[frame].arena_wm;

    /* A well-formed function leaves explicit nested `arena:` blocks before
     * returning. Restore the caller as the active allocation region first. */
    while (vm_arena_tl_get_in(&vm->arena_ctx) != arena_id &&
           vm->arena_ctx.tl_sp > 0)
        vm_arena_tl_pop_in(&vm->arena_ctx);

    int escapes = vm->func_stack[frame].arena_escaped ||
                  vm_value_escapes_call(vm, ret_val, arena_id, watermark);
    for (uint32_t i = 0; !escapes && i < ref_count; i++) {
        if (vm_value_escapes_call(vm, ref_values[i], arena_id, watermark))
            escapes = 1;
    }
    if (!escapes && arena_id >= 0)
        vm_arena_restore_in(&vm->arena_ctx, arena_id, watermark);

    /* A return/break out of a loop can bypass its Q_ARENA_RESTORE.  Do not
     * let that stale mark classify stores performed later by the caller. */
    vm->arena_mark_sp = vm->func_stack[frame].arena_mark_sp;

    vm->func_stack[frame].arena_id = -1;
    vm->func_stack[frame].arena_wm = 0;
    vm->func_stack[frame].arena_escaped = 0;
}

static vm_status_t vm_dispatch_call(vm_state_t *vm, uint32_t fidx)
{
    if (fidx >= vm->module->func_count) return VM_ERR_BAD_JUMP;
    const q_function_t *callee = &vm->module->functions[fidx];

    if (callee->body_count == 0) {
        int intr_id = -3;
        if (vm->func_intrinsic_cache && fidx < vm->func_intrinsic_cache_count) {
            intr_id = vm->func_intrinsic_cache[fidx];
        } else {
            if (strncmp(callee->name, "syscall", 7) == 0) {
                intr_id = -2;
            } else {
                for (int i = 0; i < VIR_MAX_INTRINSICS; i++) {
                    if (vir_intr_table[i].fn && strcmp(vir_intr_table[i].name, callee->name) == 0) {
                        intr_id = i;
                        break;
                    }
                }
            }
        }

        if (intr_id == -2) {
            int64_t ret_val = 0;
            vir_intrinsic_ctx_t ctx = {
                .args = &vm->regs[0],
                .argc = callee->param_count,
                .ret  = &ret_val,
                .vm   = vm,
            };
            intr_syscall(&ctx);
            vm->regs[0] = ret_val;
            vm->ip++;
            return VM_OK;
        } else if (intr_id >= 0) {
            int64_t ret_val = 0;
            vir_intrinsic_ctx_t ctx = {
                .args = &vm->regs[0],
                .argc = callee->param_count,
                .ret  = &ret_val,
                .vm   = vm,
            };
            vir_intr_table[intr_id].fn(&ctx);
            vm->regs[0] = ret_val;
            vm->ip++;
            return VM_OK;
        }
        vm->ip++;
        return VM_OK; /* No-op for unhandled extern */
    }

    if (vm->func_depth >= VM_MAX_CALL_DEPTH) return VM_ERR_STACK_OF;
    /* Proven self-host Call path (green ~2 min): memcpy-save caller bank.
     * Label maps stay O(1) via label_by_fidx cache. */
    vm->func_stack[vm->func_depth].func = vm->current_func;
    vm->func_stack[vm->func_depth].ip   = vm->ip + 1;
    vm->func_stack[vm->func_depth].caller_reg_count = vm->reg_count;
    vm->func_stack[vm->func_depth].caller_regs = NULL;

    uint32_t nregs = vm_call_save_count(vm);
    if (vm_reg_save_reserve(vm, vm->reg_save_top + nregs) != 0)
        return VM_ERR_STACK_OF;
    uint32_t save_base = vm->reg_save_top;
    vm->func_stack[vm->func_depth].saved_base = save_base;
    vm->func_stack[vm->func_depth].saved_reg_count = nregs;
    if (vm_enter_call_arena(vm, vm->func_depth) != 0)
        return VM_ERR_STACK_OF;
    memcpy(&vm->reg_save_stack[save_base], vm->regs,
           (size_t)nregs * sizeof(int64_t));
    vm->reg_save_top = save_base + nregs;
    for (uint32_t pi = 0; pi < Q_MAX_PARAMS; pi++)
        vm->func_stack[vm->func_depth].ref_bindings[pi] =
            vm->pending_ref_bindings[pi];
    vm->func_depth++;
    memset(vm->pending_ref_bindings, 0, sizeof(vm->pending_ref_bindings));

    {
        int64_t args[Q_MAX_PARAMS] = {0};
        for (uint32_t pi = 0; pi < callee->param_count && pi < Q_MAX_PARAMS; pi++)
            args[pi] = vm->regs[pi];
        for (uint32_t pi = 0; pi < callee->param_count && pi < Q_MAX_PARAMS; pi++) {
            vm->regs[callee->param_vregs[pi]] = args[pi];
            if (callee->param_vregs[pi] >= vm->reg_count)
                vm->reg_count = callee->param_vregs[pi] + 1;
        }
    }

    vm->current_func = callee;
    vm->ip = 0;
    vm_resolve_labels(vm, callee);
    return VM_OK;
}


static void vm_apply_ref_writeback(vm_state_t *vm,
                                   const int64_t *bindings,
                                   const int64_t *values,
                                   uint32_t count)
{
    for (uint32_t pi = 0; pi < count && pi < Q_MAX_PARAMS; pi++) {
        int64_t binding = bindings[pi];
        if (binding == 0) continue;
        int64_t val = values[pi];
        if (binding > 0) {
            uint32_t vreg = (uint32_t)(binding - 1);
            if (vreg < VREG_MAX) vm->regs[vreg] = val;
        } else {
            uint32_t gidx = (uint32_t)((-binding) - 1);
            if (gidx < VM_MAX_GLOBALS) vm->globals[gidx] = val;
        }
    }
}

static vm_status_t vm_finish_tailcall_return(vm_state_t *vm, int64_t ret_val)
{
    if (vm->func_depth == 0) {
        vm->regs[0] = ret_val;
        return VM_HALT;
    }
    uint32_t frame = vm->func_depth - 1;
    int64_t ref_bindings[Q_MAX_PARAMS] = {0};
    int64_t ref_values[Q_MAX_PARAMS] = {0};
    uint32_t ref_count = 0;
    if (vm->current_func) {
        ref_count = vm->current_func->param_count;
        for (uint32_t pi = 0; pi < ref_count && pi < Q_MAX_PARAMS; pi++) {
            if (!vm->current_func->param_is_ref[pi]) continue;
            ref_bindings[pi] = vm->func_stack[frame].ref_bindings[pi];
            ref_values[pi] = vm->regs[vm->current_func->param_vregs[pi]];
        }
    }
    vm_leave_call_arena(vm, frame, ret_val, ref_values, ref_count);
    vm->func_depth--;
    vm_restore_caller_window(vm, vm->func_depth);
    vm_apply_ref_writeback(vm, ref_bindings, ref_values, ref_count);
    /* Put return value in R0 */
    vm->regs[0] = ret_val;
    vm->current_func = vm->func_stack[vm->func_depth].func;
    vm->ip = vm->func_stack[vm->func_depth].ip;
    vm_resolve_labels(vm, vm->current_func);
    return VM_OK;
}

static vm_status_t vm_dispatch_tailcall(vm_state_t *vm, uint32_t fidx)
{
    if (fidx >= vm->module->func_count) return VM_ERR_BAD_JUMP;
    const q_function_t *callee = &vm->module->functions[fidx];

    if (callee->body_count == 0) {
        int intr_id = -3;
        if (vm->func_intrinsic_cache && fidx < vm->func_intrinsic_cache_count) {
            intr_id = vm->func_intrinsic_cache[fidx];
        } else {
            if (strncmp(callee->name, "syscall", 7) == 0) {
                intr_id = -2;
            } else {
                for (int i = 0; i < VIR_MAX_INTRINSICS; i++) {
                    if (vir_intr_table[i].fn && strcmp(vir_intr_table[i].name, callee->name) == 0) {
                        intr_id = i;
                        break;
                    }
                }
            }
        }

        if (intr_id == -2) {
            int64_t ret_val = 0;
            vir_intrinsic_ctx_t ctx = {
                .args = &vm->regs[0],
                .argc = callee->param_count,
                .ret  = &ret_val,
                .vm   = vm,
            };
            intr_syscall(&ctx);
            return vm_finish_tailcall_return(vm, ret_val);
        } else if (intr_id >= 0) {
            int64_t ret_val = 0;
            vir_intrinsic_ctx_t ctx = {
                .args = &vm->regs[0],
                .argc = callee->param_count,
                .ret  = &ret_val,
                .vm   = vm,
            };
            vir_intr_table[intr_id].fn(&ctx);
            return vm_finish_tailcall_return(vm, ret_val);
        }

        return vm_finish_tailcall_return(vm, 0);
    }

    /* Tailcall: reuse frame; stage args first so param_vreg writes cannot
     * clobber later ABI argument slots. */
    int64_t args[Q_MAX_PARAMS] = {0};
    for (uint32_t pi = 0; pi < callee->param_count && pi < Q_MAX_PARAMS; pi++)
        args[pi] = vm->regs[pi];
    for (uint32_t pi = 0; pi < callee->param_count && pi < Q_MAX_PARAMS; pi++) {
        vm->regs[callee->param_vregs[pi]] = args[pi];
        if (callee->param_vregs[pi] >= vm->reg_count)
            vm->reg_count = callee->param_vregs[pi] + 1;
    }

    /* Update ref bindings in the current frame if any were staged */
    if (vm->func_depth > 0) {
        for (uint32_t pi = 0; pi < Q_MAX_PARAMS; pi++) {
            vm->func_stack[vm->func_depth - 1].ref_bindings[pi] =
                vm->pending_ref_bindings[pi];
        }
    }
    memset(vm->pending_ref_bindings, 0, sizeof(vm->pending_ref_bindings));

    vm->current_func = callee;
    vm->ip = 0;
    vm_resolve_labels(vm, callee);
    return VM_OK;
}

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
        a = operand_value(vm, &instr->src1);
        /* A call result is commonly materialised with Q_MOVE.  If it was
         * allocated during the current `when` iteration, conservatively
         * retain that iteration.  Q_MOVE is register-local, so it must not
         * mark the surrounding function frame as a global escape. */
        vm_track_iteration_value(vm, a);
        set_dest(vm, &instr->dest, a);
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

    case Q_CMP_NE:
        a = operand_value(vm, &instr->src1);
        b = operand_value(vm, &instr->src2);
        set_dest(vm, &instr->dest, (a != b) ? 1 : 0);
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
            if (lid < vm->label_count && vm->active_label_map) {
                vm->ip = vm->active_label_map[lid];
                return VM_OK;
            }
        }
        return VM_ERR_BAD_JUMP;

    case Q_JUMP_IF:
        a = operand_value(vm, &instr->src1);
        if (a != 0 && instr->src2.type == OPERAND_LABEL) {
            if (instr->src2.label >= vm->label_count || !vm->active_label_map)
                return VM_ERR_BAD_JUMP;
            vm->ip = vm->active_label_map[instr->src2.label];
            return VM_OK;
        }
        break;

    case Q_JUMP_IF_NOT:
        a = operand_value(vm, &instr->src1);
        if (a == 0 && instr->src2.type == OPERAND_LABEL) {
            if (instr->src2.label >= vm->label_count || !vm->active_label_map)
                return VM_ERR_BAD_JUMP;
            vm->ip = vm->active_label_map[instr->src2.label];
            return VM_OK;
        }
        break;

    case Q_CALL:
        if (vm->call_depth >= VM_MAX_CALL_DEPTH)
            return VM_ERR_STACK_OF;
        vm->call_stack[vm->call_depth++] = vm->ip + 1;
        if (instr->src1.type == OPERAND_LABEL) {
            if (instr->src1.label >= vm->label_count || !vm->active_label_map)
                return VM_ERR_BAD_JUMP;
            vm->ip = vm->active_label_map[instr->src1.label];
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
            uint32_t frame = vm->func_depth - 1;
            int64_t ref_bindings[Q_MAX_PARAMS] = {0};
            int64_t ref_values[Q_MAX_PARAMS] = {0};
            uint32_t ref_count = 0;
            if (vm->current_func) {
                ref_count = vm->current_func->param_count;
                for (uint32_t pi = 0; pi < ref_count && pi < Q_MAX_PARAMS; pi++) {
                    if (!vm->current_func->param_is_ref[pi]) continue;
                    ref_bindings[pi] = vm->func_stack[frame].ref_bindings[pi];
                    ref_values[pi] = vm->regs[vm->current_func->param_vregs[pi]];
                }
            }
            vm_leave_call_arena(vm, frame, ret_val, ref_values, ref_count);
            vm->func_depth--;
            vm_restore_caller_window(vm, vm->func_depth);
            vm_apply_ref_writeback(vm, ref_bindings, ref_values, ref_count);
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
        return vm_dispatch_call(vm, fidx);
    }

    case Q_CALL_INDIRECT: {
        /* §11.4 callable field: fidx comes from a vreg. */
        if (!vm->module) return VM_ERR_BAD_JUMP;
        if (instr->src1.type != OPERAND_VREG) return VM_ERR_BAD_JUMP;
        uint32_t fidx = (uint32_t)vm->regs[instr->src1.vreg];
        return vm_dispatch_call(vm, fidx);
    }

    case Q_TAILCALL_FUNC: {
        if (!vm->module) return VM_ERR_BAD_JUMP;
        uint32_t fidx = 0;
        if (instr->src1.type == OPERAND_FUNC_IDX)
            fidx = instr->src1.func_idx;
        else if (instr->src1.type == OPERAND_IMM)
            fidx = (uint32_t)instr->src1.imm;
        else
            return VM_ERR_BAD_JUMP;
        return vm_dispatch_tailcall(vm, fidx);
    }

    case Q_REF_BIND_CLEAR:
        memset(vm->pending_ref_bindings, 0, sizeof(vm->pending_ref_bindings));
        break;

    case Q_REF_BIND_SET: {
        if (instr->dest.type != OPERAND_IMM) return VM_ERR_BAD_OP;
        int64_t slot = instr->dest.imm;
        if (slot >= 0 && slot < Q_MAX_PARAMS) {
            vm->pending_ref_bindings[(uint32_t)slot] =
                operand_value(vm, &instr->src1);
        }
        break;
    }

    /* ── I/O ───────────────────────────────────────────── */
    case Q_PRINT:
        a = operand_value(vm, &instr->src1);
        
        /* Check if operand is a string pointer */
        if (instr->operand_type[0] != '\0' && 
            strcmp(instr->operand_type, "string") == 0) {
            /* Dereference pointer and print string */
            char *str = (char *)(intptr_t)a;
            if (str) {
                printf("%s\n", str);
            } else {
                printf("(null)\n");
            }
        } else {
            /* Print as integer (existing behavior) */
            printf("%lld\n", (long long)a);
        }
        break;

    case Q_INPUT:
        printf("input> ");
        if (scanf("%lld", &a) == 1) {
            set_dest(vm, &instr->dest, a);
        }
        break;

    /* ── Memory management ─────────────────────────────── */
    case Q_ALLOC: {
        /* Language objects: current TL arena bump (§4.5–4.7). */
        int64_t sz = operand_value(vm, &instr->src1);
        void *p = vm_arena_tl_alloc_in(&vm->arena_ctx,
                                       (size_t)(sz > 0 ? sz : 1));
        if (p)
            memset(p, 0, (size_t)(sz > 0 ? sz : 1));
        set_dest(vm, &instr->dest, (int64_t)(intptr_t)p);
        break;
    }
    case Q_HEAP_ALLOC: {
        int64_t sz = operand_value(vm, &instr->src1);
        void *p = vm_heap_alloc(&vm->heap, (size_t)(sz > 0 ? sz : 1));
        set_dest(vm, &instr->dest, (int64_t)(intptr_t)p);
        break;
    }
    case Q_FREE: {
        int64_t addr = operand_value(vm, &instr->src1);
        /* §4.8 symbolic drop — arena objects are NOT individually freed.
         *   (a) array handle: reclaim handle id only.
         *   (b) heap registry pointer: vm_heap_free.
         *   (c) arena pointer or unknown: no-op. */
        if (addr == 0)
            break;
        if (addr >= 0 && (uint32_t)addr < vm->array_count) {
            vm_array_t *a = &vm->arrays[(uint32_t)addr];
            if (a->data && vm_heap_owns_live(&vm->heap, a->data))
                vm_heap_free(&vm->heap, a->data);
            a->data = NULL;
            a->len = 0;
            a->cap = 0;
                if (addr != 0 &&
                    vm_array_free_reserve(vm, vm->array_free_count + 1u) == 0)
                    vm->array_free[vm->array_free_count++] = (uint32_t)addr;
            break;
        }
        void *p = (void *)(intptr_t)addr;
        if (vm_heap_owns_live(&vm->heap, p)) {
            vm_heap_free(&vm->heap, p);
            for (uint32_t i = 0; i < vm->rt_string_count; i++) {
                if (vm->rt_strings[i] == (char *)p)
                    vm->rt_strings[i] = NULL;
            }
        }
        break;
    }
    case Q_LOAD_BYTE: {
        int64_t base = operand_value(vm, &instr->src1);
        int64_t off  = operand_value(vm, &instr->src2);
        if (base >= VM_MMIO_BASE &&
            base < VM_MMIO_BASE + (int64_t)VM_MMIO_SIZE) {
            int64_t pos = base - VM_MMIO_BASE + off;
            const uint8_t *bytes = (const uint8_t *)vm->mmio_region;
            set_dest(vm, &instr->dest,
                     pos >= 0 && pos < (int64_t)VM_MMIO_SIZE ? bytes[pos] : 0);
            break;
        }
        if (off < 0 || !vm_host_read_ptr_ok(vm, base, (size_t)off + 1u)) {
            set_dest(vm, &instr->dest, 0);
            break;
        }
        const uint8_t *ptr = (const uint8_t *)(intptr_t)base;
        set_dest(vm, &instr->dest, (int64_t)ptr[off]);
        break;
    }
    case Q_STORE_BYTE: {
        int64_t base = operand_value(vm, &instr->src1);
        int64_t off  = operand_value(vm, &instr->src2);
        int64_t val  = operand_value(vm, &instr->dest);
        if (base >= VM_MMIO_BASE &&
            base < VM_MMIO_BASE + (int64_t)VM_MMIO_SIZE) {
            int64_t pos = base - VM_MMIO_BASE + off;
            uint8_t *bytes = (uint8_t *)vm->mmio_region;
            if (pos >= 0 && pos < (int64_t)VM_MMIO_SIZE)
                bytes[pos] = (uint8_t)val;
            break;
        }
        if (off < 0 || !vm_host_ptr_ok(vm, base, (size_t)off + 1u))
            break;
        uint8_t *ptr = (uint8_t *)(intptr_t)base;
        ptr[off] = (uint8_t)val;
        break;
    }
    case Q_MEM_COPY: {
        int64_t dst = operand_value(vm, &instr->dest);
        int64_t src = operand_value(vm, &instr->src1);
        int64_t len = operand_value(vm, &instr->src2);
        if (dst > 0 && src > 0 && len > 0) {
            memcpy((void *)(intptr_t)dst, (const void *)(intptr_t)src, (size_t)len);
        }
        break;
    }
    case Q_MEM_SET: {
        int64_t dst = operand_value(vm, &instr->dest);
        int64_t val = operand_value(vm, &instr->src1);
        int64_t len = operand_value(vm, &instr->src2);
        if (dst > 0 && len > 0) {
            memset((void *)(intptr_t)dst, (int)val, (size_t)len);
        }
        break;
    }
    case Q_LOAD_WORD: {
        int64_t base = operand_value(vm, &instr->src1);
        int64_t idx  = operand_value(vm, &instr->src2);
        if (base >= VM_MMIO_BASE && base < VM_MMIO_BASE + (int64_t)VM_MMIO_SIZE) {
            size_t offset = (size_t)((base - VM_MMIO_BASE) / (int64_t)sizeof(int64_t));
            size_t total  = offset + (size_t)idx;
            size_t slots  = VM_MMIO_SIZE / sizeof(int64_t);
            set_dest(vm, &instr->dest,
                     total < slots ? vm->mmio_region[total] : 0);
        } else {
            if (idx < 0 || (uint64_t)idx > SIZE_MAX - sizeof(int64_t) ||
                !vm_host_read_ptr_ok(vm, base,
                                     (size_t)idx + sizeof(int64_t))) {
                fprintf(stderr,
                        "VM invalid Q_LOAD_WORD: func=%s ip=%u base=%lld offset=%lld\n",
                        vm->current_func ? vm->current_func->name : "<none>",
                        vm->ip, (long long)base, (long long)idx);
                uint32_t first = vm->func_depth > 8u
                                   ? vm->func_depth - 8u : 0u;
                for (uint32_t depth = vm->func_depth; depth > first; depth--) {
                    uint32_t caller = depth - 1u;
                    fprintf(stderr, "  caller[%u]=%s return_ip=%u\n",
                            vm->func_depth - depth,
                            vm->func_stack[caller].func
                                ? vm->func_stack[caller].func->name : "<root>",
                            vm->func_stack[caller].ip);
                }
                return VM_ERR_NULL_PTR;
            }
            uintptr_t target_addr = (uintptr_t)((char *)(intptr_t)base + idx);
            int64_t v = 0;
            memcpy(&v, (const void *)target_addr, sizeof(v));
            set_dest(vm, &instr->dest, v);
        }
        break;
    }
    case Q_STORE_WORD: {
        int64_t base = operand_value(vm, &instr->src1);
        int64_t idx  = operand_value(vm, &instr->src2);
        int64_t val  = operand_value(vm, &instr->dest);
        if (base >= VM_MMIO_BASE && base < VM_MMIO_BASE + (int64_t)VM_MMIO_SIZE) {
            size_t offset = (size_t)((base - VM_MMIO_BASE) / (int64_t)sizeof(int64_t));
            size_t total  = offset + (size_t)(idx / 8);
            size_t slots  = VM_MMIO_SIZE / sizeof(int64_t);
            if (total < slots) vm->mmio_region[total] = val;
        } else {
            if (idx < 0 || (uint64_t)idx > SIZE_MAX - sizeof(int64_t) ||
                !vm_host_ptr_ok(vm, base,
                                (size_t)idx + sizeof(int64_t))) {
                fprintf(stderr,
                        "VM invalid Q_STORE_WORD: func=%s ip=%u base=%lld offset=%lld\n",
                        vm->current_func ? vm->current_func->name : "<none>",
                        vm->ip, (long long)base, (long long)idx);
                return VM_ERR_NULL_PTR;
            }
            uintptr_t target_addr = (uintptr_t)((char *)(intptr_t)base + idx);
            vm_track_pointer_store(vm, base, val);
            memcpy((void *)target_addr, &val, sizeof(val));
        }
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
        int64_t raw_a = operand_value(vm, &instr->src1);
        int64_t raw_b = operand_value(vm, &instr->src2);
        const char *sa = (const char *)(intptr_t)raw_a;
        const char *sb = (const char *)(intptr_t)raw_b;
        if (!sa) sa = "";
        if (!sb) sb = "";
        size_t ha = vm_heap_size_of(&vm->heap, sa);
        size_t hb = vm_heap_size_of(&vm->heap, sb);
        if ((raw_a && !vm_host_read_ptr_ok(vm, raw_a, 1)) ||
            (raw_b && !vm_host_read_ptr_ok(vm, raw_b, 1)) ||
            (ha && !memchr(sa, '\0', ha)) ||
            (hb && !memchr(sb, '\0', hb))) {
            size_t live_bytes = 0;
            for (uint32_t i = 0; i < vm->heap.count; i++)
                if (vm->heap.entries[i].live)
                    live_bytes += vm->heap.entries[i].size;
            fprintf(stderr,
                    "VM invalid Q_STR_CAT operand: func=%s ip=%u "
                    "a=%lld(heap=%zu) b=%lld(heap=%zu) "
                    "live_heap=%u/%zu arena=%zu\n",
                    vm->current_func ? vm->current_func->name : "<none>",
                    vm->ip, (long long)(intptr_t)sa, ha,
                    (long long)(intptr_t)sb, hb,
                    vm_heap_live_count(&vm->heap), live_bytes,
                    vm->arena_ctx.arenas[0].used);
            return VM_ERR_NULL_PTR;
        }
        size_t la = strlen(sa), lb = strlen(sb);
        char *cat = (char *)vm_arena_tl_alloc_in(&vm->arena_ctx, la + lb + 1);
        if (!cat) {
            set_dest(vm, &instr->dest, 0);
            break;
        }
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
        int64_t mode_raw = operand_value(vm, &instr->src2);
        const char *mode = NULL;
        /* Accept either a C mode string ("r"/"w"/…) or FileMode enum
         * (Read=1, Write=2, ReadWrite=3, Append=4) used by stdlib. */
        if (mode_raw >= 1 && mode_raw <= 4) {
            static const char *filemode_to_fopen[] = {
                NULL, "r", "w", "r+", "a"
            };
            mode = filemode_to_fopen[mode_raw];
        } else {
            mode = (const char *)(intptr_t)mode_raw;
            /* Reject obvious non-pointers (NULL / small integers). */
            if ((uintptr_t)mode < 0x1000u)
                mode = NULL;
        }
        FILE *f = (path && mode && (uintptr_t)path >= 0x1000u)
                      ? fopen(path, mode)
                      : NULL;
        if (f && vm->open_file_count < 64) {
            vm->open_files[vm->open_file_count++] = f;
        }
        set_dest(vm, &instr->dest, (int64_t)(intptr_t)f);
        break;
    }
    case Q_FILE_READ: {
        FILE *f = (FILE *)(intptr_t)operand_value(vm, &instr->src1);
        int valid = 0;
        for (uint32_t i = 0; i < vm->open_file_count; i++) {
            if (vm->open_files[i] == f && f != NULL) { valid = 1; break; }
        }
        if (!valid) { set_dest(vm, &instr->dest, 0); break; }
        fseek(f, 0, SEEK_END);
        long sz = ftell(f);
        fseek(f, 0, SEEK_SET);
        char *buf = (char *)vm_arena_tl_alloc_in(&vm->arena_ctx, (size_t)sz + 1);
        if (!buf) { set_dest(vm, &instr->dest, 0); break; }
        size_t rd = fread(buf, 1, (size_t)sz, f);
        buf[rd] = '\0';
        set_dest(vm, &instr->dest, vm_add_rt_string(vm, buf));
        break;
    }
    case Q_FILE_WRITE: {
        FILE *f = (FILE *)(intptr_t)operand_value(vm, &instr->src1);
        const char *data = (const char *)(intptr_t)operand_value(vm, &instr->src2);
        int valid = 0;
        for (uint32_t i = 0; i < vm->open_file_count; i++) {
            if (vm->open_files[i] == f && f != NULL) { valid = 1; break; }
        }
        if (valid && data) fputs(data, f);
        break;
    }
    case Q_FILE_CLOSE: {
        FILE *f = (FILE *)(intptr_t)operand_value(vm, &instr->src1);
        for (uint32_t i = 0; i < vm->open_file_count; i++) {
            if (vm->open_files[i] == f && f != NULL) {
                fclose(f);
                vm->open_files[i] = NULL;
                break;
            }
        }
        break;
    }
    case Q_FILE_WRITE_BYTE: {
        FILE *f = (FILE *)(intptr_t)operand_value(vm, &instr->src1);
        int64_t byte = operand_value(vm, &instr->src2);
        int valid = 0;
        for (uint32_t i = 0; i < vm->open_file_count; i++) {
            if (vm->open_files[i] == f && f != NULL) { valid = 1; break; }
        }
        if (valid) fputc((int)byte, f);
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
            int64_t al = vm_array_len(vm, v);
            set_dest(vm, &instr->dest, al);
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
        vm_track_pointer_store(vm, 0, val);
        vm_array_set(vm, arr, idx, val);
        break;
    }
    case Q_ARR_PUSH: {
        int64_t arr = operand_value(vm, &instr->src1);
        int64_t val = operand_value(vm, &instr->src2);
        vm_track_pointer_store(vm, 0, val);
        vm_array_push(vm, arr, val);
        break;
    }
    case Q_ARR_CAP: {
        int64_t v = operand_value(vm, &instr->src1);
        int64_t out = 0;
        if (v >= 0 && (uint32_t)v < vm->array_count) {
            out = (int64_t)vm->arrays[(uint32_t)v].cap;
        }
        set_dest(vm, &instr->dest, out);
        break;
    }
    case Q_ARR_COMPACT: {
        int64_t v = operand_value(vm, &instr->src1);
        int64_t new_handle = vm_array_new(vm, 0);
        if (v >= 0 && (uint32_t)v < vm->array_count) {
            vm_array_t *src = &vm->arrays[(uint32_t)v];
            for (uint32_t i = 0; i < src->len; i++) {
                if (src->data[i] != 0)
                    vm_array_push(vm, new_handle, src->data[i]);
            }
        }
        set_dest(vm, &instr->dest, new_handle);
        break;
    }
    case Q_REALLOC: {
        /* Heap-only (FFI / vir_realloc). Arena pointers cannot realloc. */
        int64_t old_ptr = operand_value(vm, &instr->src1);
        int64_t new_sz  = operand_value(vm, &instr->src2);
        void *old = (void *)(intptr_t)old_ptr;
        void *np = NULL;
        if (old_ptr == 0)
            np = vm_heap_alloc(&vm->heap, (size_t)(new_sz > 0 ? new_sz : 0));
        else if (vm_heap_owns_live(&vm->heap, old))
            np = vm_heap_realloc(&vm->heap, old, (size_t)(new_sz > 0 ? new_sz : 0));
        set_dest(vm, &instr->dest, (int64_t)(intptr_t)np);
        break;
    }
    case Q_ARENA_NEW: {
        int64_t sz = operand_value(vm, &instr->src1);
        if (sz <= 0) sz = 64 * 1024;
        int aid = vm_arena_create_in(&vm->arena_ctx, (size_t)sz);
        set_dest(vm, &instr->dest, (int64_t)aid);
        break;
    }
    case Q_ARENA_ALLOC: {
        int64_t aid = operand_value(vm, &instr->src1);
        int64_t sz  = operand_value(vm, &instr->src2);
        void *p = NULL;
        if (sz > 0) {
            if (aid < 0) {
                p = vm_arena_tl_alloc_in(&vm->arena_ctx, (size_t)sz);
            } else {
                p = vm_arena_alloc_in(&vm->arena_ctx, (int)aid, (size_t)sz);
            }
        }
        set_dest(vm, &instr->dest, (int64_t)(intptr_t)p);
        break;
    }
    case Q_ARENA_FREE: {
        int64_t aid = operand_value(vm, &instr->src1);
        vm_arena_destroy_in(&vm->arena_ctx, (int)aid);
        set_dest(vm, &instr->dest, 0);
        break;
    }
    case Q_ARENA_ENTER: {
        int64_t aid = operand_value(vm, &instr->src1);
        vm_arena_tl_push_in(&vm->arena_ctx, (int)aid);
        set_dest(vm, &instr->dest, 0);
        break;
    }
    case Q_ARENA_LEAVE: {
        vm_arena_tl_pop_in(&vm->arena_ctx);
        set_dest(vm, &instr->dest, 0);
        break;
    }
    case Q_ARENA_SAVE: {
        int aid = (instr->src1.type == OPERAND_NONE)
                      ? vm_arena_tl_get_in(&vm->arena_ctx)
                      : (int)operand_value(vm, &instr->src1);
        size_t wm = vm_arena_save_in(&vm->arena_ctx, aid);
        if (vm->arena_mark_sp < VM_ARENA_MAX_TL_DEPTH) {
            uint8_t mi = vm->arena_mark_sp++;
            vm->arena_marks[mi].arena_id = aid;
            vm->arena_marks[mi].watermark = wm;
            vm->arena_marks[mi].escaped = 0;
            vm->arena_marks[mi].func_depth = vm->func_depth;
        }
        set_dest(vm, &instr->dest, (int64_t)wm);
        break;
    }
    case Q_ARENA_RESTORE: {
        static uint64_t restore_count = 0;
        static int mem_stats_enabled = -1;
        int aid = (instr->src1.type == OPERAND_NONE)
                      ? vm_arena_tl_get_in(&vm->arena_ctx)
                      : (int)operand_value(vm, &instr->src1);
        int64_t wm = operand_value(vm, &instr->src2);
        int escaped = 0;
        if (vm->arena_mark_sp > 0) {
            uint8_t mi = vm->arena_mark_sp - 1u;
            if (vm->arena_marks[mi].arena_id == aid &&
                vm->arena_marks[mi].watermark == (size_t)wm) {
                escaped = vm->arena_marks[mi].escaped;
                vm->arena_mark_sp--;
            }
        }
        if (!escaped)
            vm_arena_restore_in(&vm->arena_ctx, aid, (size_t)wm);
        restore_count++;
        if (mem_stats_enabled < 0)
            mem_stats_enabled = getenv("VIR_MEM_STATS") != NULL;
        if (mem_stats_enabled && restore_count % 2000u == 0) {
            size_t live_bytes = 0;
            size_t label_bytes = 0;
            for (uint32_t i = 0; i < vm->heap.count; i++)
                if (vm->heap.entries[i].live)
                    live_bytes += vm->heap.entries[i].size;
            for (uint32_t i = 0; i < vm->label_by_fidx_n; i++)
                if (vm->label_by_fidx && vm->label_by_fidx[i])
                    label_bytes += (size_t)vm->label_len_by_fidx[i] *
                                   sizeof(uint32_t);
            fprintf(stderr,
                    "[vm-mem] restores=%llu func=%s heap=%u/%u "
                    "bytes=%zu arena=%zu labels=%zu regsave=%u arrays=%u\n",
                    (unsigned long long)restore_count,
                    vm->current_func ? vm->current_func->name : "<none>",
                    vm->heap.live_count, vm->heap.count, live_bytes,
                    aid >= 0 ? vm->arena_ctx.arenas[aid].used : 0,
                    label_bytes, vm->reg_save_cap,
                    vm->array_count);
        }
        set_dest(vm, &instr->dest, 0);
        break;
    }

    /* ── §20 Dict ─────────────────────────────────────── */
    case Q_DICT_NEW:
        set_dest(vm, &instr->dest, vm_dict_new(vm));
        break;
    case Q_DICT_SET_I:
    case Q_DICT_SET_S: {
        int64_t d = operand_value(vm, &instr->src1);
        int64_t k = operand_value(vm, &instr->src2);
        int64_t v = operand_value(vm, &instr->dest);
        vm_track_pointer_store(vm, 0, v);
        vm_dict_set(vm, d, instr->opcode == Q_DICT_SET_S, k, v);
        break;
    }
    case Q_DICT_GET_I:
    case Q_DICT_GET_S: {
        int64_t d = operand_value(vm, &instr->src1);
        int64_t k = operand_value(vm, &instr->src2);
        set_dest(vm, &instr->dest,
                 vm_dict_get(vm, d, instr->opcode == Q_DICT_GET_S, k));
        break;
    }
    case Q_DICT_HAS_I:
    case Q_DICT_HAS_S: {
        int64_t d = operand_value(vm, &instr->src1);
        int64_t k = operand_value(vm, &instr->src2);
        set_dest(vm, &instr->dest,
                 vm_dict_has(vm, d, instr->opcode == Q_DICT_HAS_S, k));
        break;
    }
    case Q_DICT_DEL_I:
    case Q_DICT_DEL_S: {
        int64_t d = operand_value(vm, &instr->src1);
        int64_t k = operand_value(vm, &instr->src2);
        vm_dict_del(vm, d, instr->opcode == Q_DICT_DEL_S, k);
        break;
    }
    case Q_DICT_LEN: {
        int64_t d = operand_value(vm, &instr->src1);
        set_dest(vm, &instr->dest, vm_dict_len(vm, d));
        break;
    }
    case Q_DICT_KEYS: {
        int64_t d = operand_value(vm, &instr->src1);
        set_dest(vm, &instr->dest, vm_dict_keys(vm, d));
        break;
    }
    case Q_DICT_VALUES: {
        int64_t d = operand_value(vm, &instr->src1);
        set_dest(vm, &instr->dest, vm_dict_values(vm, d));
        break;
    }
    case Q_HASH_I: {
        int64_t v = operand_value(vm, &instr->src1);
        set_dest(vm, &instr->dest, (int64_t)vm_splitmix64(v));
        break;
    }
    case Q_HASH_S: {
        const char *s = (const char *)(intptr_t)operand_value(vm, &instr->src1);
        set_dest(vm, &instr->dest, (int64_t)vm_fnv1a(s));
        break;
    }

    /* ── System ────────────────────────────────────────── */
    case Q_EXIT: {
        exit((int)operand_value(vm, &instr->src1));
        break; /* unreachable */
    }
    case Q_I_TO_STR: {
        char *buf = (char *)vm_arena_tl_alloc_in(&vm->arena_ctx, 32);
        if (!buf) { set_dest(vm, &instr->dest, 0); break; }
        snprintf(buf, 32, "%lld", (long long)operand_value(vm, &instr->src1));
        set_dest(vm, &instr->dest, vm_add_rt_string(vm, buf));
        break;
    }
    case Q_CHAR_TO_STR: {
        /* Convert an integer char code to a 1-character string */
        int64_t code = operand_value(vm, &instr->src1);
        char *buf = (char *)vm_arena_tl_alloc_in(&vm->arena_ctx, 5); /* up to 4 UTF-8 bytes + NUL */
        if (!buf) { set_dest(vm, &instr->dest, 0); break; }
        if (code < 0x80) {
            buf[0] = (char)(code & 0x7F);
            buf[1] = '\0';
        } else if (code < 0x800) {
            buf[0] = (char)(0xC0 | (code >> 6));
            buf[1] = (char)(0x80 | (code & 0x3F));
            buf[2] = '\0';
        } else if (code < 0x10000) {
            buf[0] = (char)(0xE0 | (code >> 12));
            buf[1] = (char)(0x80 | ((code >> 6) & 0x3F));
            buf[2] = (char)(0x80 | (code & 0x3F));
            buf[3] = '\0';
        } else {
            buf[0] = (char)(0xF0 | (code >> 18));
            buf[1] = (char)(0x80 | ((code >> 12) & 0x3F));
            buf[2] = (char)(0x80 | ((code >> 6) & 0x3F));
            buf[3] = (char)(0x80 | (code & 0x3F));
            buf[4] = '\0';
        }
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
        if (s) { fputs(s, stdout); fflush(stdout); }
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
        vm_track_pointer_store(vm, 0, val);
        if (idx >= 0 && idx < (int64_t)VM_MAX_GLOBALS) {
            vm->globals[(uint32_t)idx] = val;
            if ((uint32_t)idx >= vm->global_count)
                vm->global_count = (uint32_t)idx + 1;
        }
        break;
    }

    /* ── §24.4 Atomic global access (seq_cst) ──────────── */
    case Q_ATOMIC_LOAD_GLOBAL: {
        int64_t idx = operand_value(vm, &instr->src1);
        if (idx >= 0 && idx < (int64_t)VM_MAX_GLOBALS) {
            int64_t v = vir_atomic_load_i64(
                (volatile const int64_t *)&vm->globals[(uint32_t)idx],
                VIR_MO_SEQ_CST);
            set_dest(vm, &instr->dest, v);
        } else {
            set_dest(vm, &instr->dest, 0);
        }
        break;
    }
    case Q_ATOMIC_STORE_GLOBAL: {
        int64_t idx = operand_value(vm, &instr->src1);
        int64_t val = operand_value(vm, &instr->src2);
        if (idx >= 0 && idx < (int64_t)VM_MAX_GLOBALS) {
            vir_atomic_store_i64(
                (volatile int64_t *)&vm->globals[(uint32_t)idx], val,
                VIR_MO_SEQ_CST);
            if ((uint32_t)idx >= vm->global_count)
                vm->global_count = (uint32_t)idx + 1;
        }
        break;
    }
    case Q_ATOMIC_ADD_GLOBAL: {
        int64_t idx = operand_value(vm, &instr->src1);
        int64_t val = operand_value(vm, &instr->src2);
        if (idx >= 0 && idx < (int64_t)VM_MAX_GLOBALS) {
            int64_t old = vir_atomic_add_i64(
                (volatile int64_t *)&vm->globals[(uint32_t)idx], val,
                VIR_MO_SEQ_CST);
            set_dest(vm, &instr->dest, old);
        } else {
            set_dest(vm, &instr->dest, 0);
        }
        break;
    }
    case Q_ATOMIC_SUB_GLOBAL: {
        int64_t idx = operand_value(vm, &instr->src1);
        int64_t val = operand_value(vm, &instr->src2);
        if (idx >= 0 && idx < (int64_t)VM_MAX_GLOBALS) {
            /* fetch_sub = fetch_add(-val) for signed i64 */
            int64_t old = vir_atomic_add_i64(
                (volatile int64_t *)&vm->globals[(uint32_t)idx], -val,
                VIR_MO_SEQ_CST);
            set_dest(vm, &instr->dest, old);
        } else {
            set_dest(vm, &instr->dest, 0);
        }
        break;
    }

    /* ── §26.2 Tensor matmul (2-D) / elementwise / FMA ─── */
    case Q_TENSOR_MUL:
    case Q_TENSOR_FMA: {
        int64_t a = operand_value(vm, &instr->src1);
        int64_t b = operand_value(vm, &instr->src2);
        /* Runtime array detection: handle in [0, array_count) */
        int a_is_arr = (a >= 0 && (uint32_t)a < vm->array_count);
        int b_is_arr = (b >= 0 && (uint32_t)b < vm->array_count);
        if (a_is_arr && b_is_arr) {
            vm_array_t *aa = &vm->arrays[(uint32_t)a];
            vm_array_t *ba = &vm->arrays[(uint32_t)b];
            /* §26.2 True matmul when both tensors are 2-D with matching
             * inner dim: [M,K] ** [K,N] → [M,N]. Falls back to elementwise
             * for 1-D arrays. */
            if (instr->opcode == Q_TENSOR_MUL &&
                aa->ndim == 2 && ba->ndim == 2 &&
                aa->shape[1] == ba->shape[0]) {
                uint32_t M = aa->shape[0], K = aa->shape[1], N = ba->shape[1];
                int64_t out = vm_array_new(vm, (int64_t)(M * N));
                vm_array_t *oa = &vm->arrays[(uint32_t)out];
                for (uint32_t i = 0; i < M; i++) {
                    for (uint32_t j = 0; j < N; j++) {
                        int64_t s = 0;
                        for (uint32_t k = 0; k < K; k++) {
                            s += aa->data[i * K + k] * ba->data[k * N + j];
                        }
                        vm_array_push(vm, out, s);
                    }
                }
                oa->ndim = 2;
                oa->shape[0] = M;
                oa->shape[1] = N;
                set_dest(vm, &instr->dest, out);
                break;
            }
            uint32_t n = aa->len < ba->len ? aa->len : ba->len;
            int64_t out = vm_array_new(vm, (int64_t)n);
            vm_array_t *oa = &vm->arrays[(uint32_t)out];
            for (uint32_t i = 0; i < n; i++) {
                int64_t m = aa->data[i] * ba->data[i];
                vm_array_push(vm, out, m);
                (void)oa;
            }
            set_dest(vm, &instr->dest, out);
        } else {
            /* Scalar fallback: same as Q_MUL */
            set_dest(vm, &instr->dest, a * b);
        }
        break;
    }

    /* ── §26.1 Set tensor shape metadata on an array handle ── */
    case Q_TENSOR_SHAPE: {
        int64_t arr = operand_value(vm, &instr->dest);
        int64_t rows = operand_value(vm, &instr->src1);
        int64_t cols = operand_value(vm, &instr->src2);
        if (arr >= 0 && (uint32_t)arr < vm->array_count) {
            vm_array_t *a = &vm->arrays[(uint32_t)arr];
            a->ndim = 2;
            a->shape[0] = (uint32_t)rows;
            a->shape[1] = (uint32_t)cols;
        }
        break;
    }

    /* ── §26.5 Quantize tensor: clip each element to int_N range ── */
    case Q_QUANTIZE: {
        int64_t arr = operand_value(vm, &instr->src1);
        int64_t bits = operand_value(vm, &instr->src2);
        if (bits <= 0) bits = 8;
        if (bits > 32) bits = 32;
        int64_t lo = -(1LL << (bits - 1));
        int64_t hi = (1LL << (bits - 1)) - 1;
        if (arr >= 0 && (uint32_t)arr < vm->array_count) {
            vm_array_t *sa = &vm->arrays[(uint32_t)arr];
            int64_t out = vm_array_new(vm, (int64_t)sa->len);
            for (uint32_t i = 0; i < sa->len; i++) {
                int64_t v = sa->data[i];
                if (v < lo) v = lo;
                if (v > hi) v = hi;
                vm_array_push(vm, out, v);
            }
            set_dest(vm, &instr->dest, out);
        } else {
            set_dest(vm, &instr->dest, 0);
        }
        break;
    }

    /* ── §25.1 Reactive var notification: print update line ── */
    case Q_REACTIVE_NOTIFY: {
        const char *nm = "?";
        if (instr->src1.type == OPERAND_STR && vm->module &&
            instr->src1.str_idx < vm->module->string_count) {
            nm = vm->module->strings[instr->src1.str_idx];
        }
        int64_t val = operand_value(vm, &instr->src2);
        printf("[reactive] %s = %lld\n", nm, (long long)val);
        break;
    }

    /* ── §23 Port: new / send / recv / len ─────────────── */
    case Q_PORT_NEW: {
        int64_t cap = operand_value(vm, &instr->src1);
        if (cap <= 0) cap = VM_PORT_DEFAULT_CAP;
        if (vm->port_count >= VM_MAX_PORTS) {
            set_dest(vm, &instr->dest, -1);
            break;
        }
        uint32_t idx = vm->port_count++;
        vm_port_t *p = &vm->ports[idx];
        p->buf = (int64_t *)calloc((size_t)cap, sizeof(int64_t));
        p->cap = (uint32_t)cap;
        p->head = p->tail = p->count = 0;
        p->closed = 0;
        set_dest(vm, &instr->dest, (int64_t)idx);
        break;
    }
    case Q_PORT_SEND: {
        int64_t ph = operand_value(vm, &instr->dest);
        int64_t val = operand_value(vm, &instr->src1);
        if (ph < 0 || (uint32_t)ph >= vm->port_count) break;
        vm_port_t *p = &vm->ports[(uint32_t)ph];
        if (p->count >= p->cap) {
            /* Full: drop oldest (bounded send semantics for single-threaded VM) */
            p->head = (p->head + 1) % p->cap;
            p->count--;
        }
        p->buf[p->tail] = val;
        p->tail = (p->tail + 1) % p->cap;
        p->count++;
        break;
    }
    case Q_PORT_RECV: {
        int64_t ph = operand_value(vm, &instr->src1);
        if (ph < 0 || (uint32_t)ph >= vm->port_count) {
            set_dest(vm, &instr->dest, -1);
            break;
        }
        vm_port_t *p = &vm->ports[(uint32_t)ph];
        if (p->count == 0) {
            set_dest(vm, &instr->dest, -1);
            break;
        }
        int64_t val = p->buf[p->head];
        p->head = (p->head + 1) % p->cap;
        p->count--;
        set_dest(vm, &instr->dest, val);
        break;
    }
    case Q_PORT_LEN: {
        int64_t ph = operand_value(vm, &instr->src1);
        if (ph < 0 || (uint32_t)ph >= vm->port_count) {
            set_dest(vm, &instr->dest, 0);
            break;
        }
        set_dest(vm, &instr->dest, (int64_t)vm->ports[(uint32_t)ph].count);
        break;
    }

    /* ── §24.2 Swizzle: reorder array channels by name ─── */
    case Q_SWIZZLE: {
        int64_t v = operand_value(vm, &instr->src1);
        const char *chans = NULL;
        if (instr->src2.type == OPERAND_STR && vm->module &&
            instr->src2.str_idx < vm->module->string_count) {
            chans = vm->module->strings[instr->src2.str_idx];
        }
        int v_is_arr = (v >= 0 && (uint32_t)v < vm->array_count);
        if (v_is_arr && chans) {
            vm_array_t *va = &vm->arrays[(uint32_t)v];
            int64_t out = vm_array_new(vm, (int64_t)strlen(chans));
            for (const char *c = chans; *c; c++) {
                int32_t idx = -1;
                switch (*c) {
                case 'x': case 'r': idx = 0; break;
                case 'y': case 'g': idx = 1; break;
                case 'z': case 'b': idx = 2; break;
                case 'w': case 'a': idx = 3; break;
                default: break;
                }
                int64_t val = (idx >= 0 && (uint32_t)idx < va->len)
                              ? va->data[idx] : 0;
                vm_array_push(vm, out, val);
            }
            set_dest(vm, &instr->dest, out);
        } else {
            set_dest(vm, &instr->dest, v);
        }
        break;
    }

    /* ── §24.2 Swizzle write-mask: v~xy = rhs ──────────── */
    case Q_SWIZZLE_STORE: {
        int64_t dst = operand_value(vm, &instr->dest);
        int64_t rhs = operand_value(vm, &instr->src1);
        const char *chans = NULL;
        if (instr->src2.type == OPERAND_STR && vm->module &&
            instr->src2.str_idx < vm->module->string_count) {
            chans = vm->module->strings[instr->src2.str_idx];
        }
        if (dst >= 0 && (uint32_t)dst < vm->array_count &&
            rhs >= 0 && (uint32_t)rhs < vm->array_count && chans) {
            vm_array_t *da = &vm->arrays[(uint32_t)dst];
            vm_array_t *sa = &vm->arrays[(uint32_t)rhs];
            uint32_t si = 0;
            for (const char *c = chans; *c; c++) {
                int32_t idx = -1;
                switch (*c) {
                case 'x': case 'r': idx = 0; break;
                case 'y': case 'g': idx = 1; break;
                case 'z': case 'b': idx = 2; break;
                case 'w': case 'a': idx = 3; break;
                default: break;
                }
                if (idx < 0 || (uint32_t)idx >= da->len) continue;
                int64_t v = (si < sa->len) ? sa->data[si] : 0;
                da->data[(uint32_t)idx] = v;
                si++;
            }
        }
        break;
    }

    /* ── §24.1 flux builtins ──────────────────────────── */
    case Q_FLUX_DOT: {
        int64_t ah = operand_value(vm, &instr->src1);
        int64_t bh = operand_value(vm, &instr->src2);
        int64_t acc = 0;
        if (ah >= 0 && (uint32_t)ah < vm->array_count &&
            bh >= 0 && (uint32_t)bh < vm->array_count) {
            vm_array_t *a = &vm->arrays[(uint32_t)ah];
            vm_array_t *b = &vm->arrays[(uint32_t)bh];
            uint32_t n = (a->len < b->len) ? a->len : b->len;
            for (uint32_t i = 0; i < n; i++) acc += a->data[i] * b->data[i];
        }
        set_dest(vm, &instr->dest, acc);
        break;
    }
    case Q_FLUX_LEN: {
        int64_t ah = operand_value(vm, &instr->src1);
        int64_t len = 0;
        if (ah >= 0 && (uint32_t)ah < vm->array_count) {
            vm_array_t *a = &vm->arrays[(uint32_t)ah];
            len = (int64_t)a->len;
        }
        set_dest(vm, &instr->dest, len);
        break;
    }
    case Q_FLUX_NORM: {
        /* §24.1 flux.norm(v) — returns scalar Euclidean magnitude isqrt(Σ v[i]²) */
        int64_t ah = operand_value(vm, &instr->src1);
        int64_t result = 0;
        if (ah >= 0 && (uint32_t)ah < vm->array_count) {
            vm_array_t *a = &vm->arrays[(uint32_t)ah];
            int64_t sum = 0;
            for (uint32_t i = 0; i < a->len; i++) sum += a->data[i] * a->data[i];
            if (sum > 0) {
                int64_t x = sum, y = (sum + 1) / 2;
                while (y < x) { x = y; y = (x + sum / x) / 2; }
                result = x;
            }
        }
        set_dest(vm, &instr->dest, result);
        break;
    }
    case Q_FLUX_SPLAT: {
        int64_t val = operand_value(vm, &instr->src1);
        int64_t n   = operand_value(vm, &instr->src2);
        int64_t out = vm_array_new(vm, n > 0 ? n : 1);
        for (int64_t i = 0; i < n; i++) vm_array_push(vm, out, val);
        set_dest(vm, &instr->dest, out);
        break;
    }
    case Q_FLUX_LOAD: {
        int64_t addr = operand_value(vm, &instr->src1);
        int64_t n    = operand_value(vm, &instr->src2);
        int64_t out  = vm_array_new(vm, n > 0 ? n : 1);
        int64_t *ptr = (int64_t *)(uintptr_t)addr;
        if (ptr) {
            for (int64_t i = 0; i < n; i++) vm_array_push(vm, out, ptr[i]);
        }
        set_dest(vm, &instr->dest, out);
        break;
    }
    case Q_FLUX_STORE: {
        int64_t addr = operand_value(vm, &instr->src1);
        int64_t ah   = operand_value(vm, &instr->src2);
        int64_t *ptr = (int64_t *)(uintptr_t)addr;
        if (ptr && ah >= 0 && (uint32_t)ah < vm->array_count) {
            vm_array_t *a = &vm->arrays[(uint32_t)ah];
            for (uint32_t i = 0; i < a->len; i++) ptr[i] = a->data[i];
        }
        break;
    }
    case Q_TENSOR_SUM: {
        int64_t ah = operand_value(vm, &instr->src1);
        int64_t acc = 0;
        if (ah >= 0 && (uint32_t)ah < vm->array_count) {
            vm_array_t *a = &vm->arrays[(uint32_t)ah];
            for (uint32_t i = 0; i < a->len; i++) acc += a->data[i];
        }
        set_dest(vm, &instr->dest, acc);
        break;
    }
    case Q_ATOMIC_FENCE:
        /* Single-threaded VM: no-op but preserves intent. */
        __sync_synchronize();
        break;

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

    /* ── §Phase-9 Intrinsic Registry ───────────────────── */
    case Q_INTRINSIC: {
        /* src1 = intrinsic_id (OPERAND_IMM)
         * src2 = argc         (OPERAND_IMM, informational)
         * dest = return vreg  */
        uint32_t id   = (uint32_t)instr->src1.imm;
        uint32_t argc = (instr->src2.type == OPERAND_IMM)
                        ? (uint32_t)instr->src2.imm : 0;
        if (id < VIR_MAX_INTRINSICS && vir_intr_table[id].fn) {
            int64_t ret_val = 0;
            vir_intrinsic_ctx_t ctx = {
                .args = &vm->regs[0],
                .argc = (int)argc,
                .ret  = &ret_val,
                .vm   = vm,
            };
            vir_intr_table[id].fn(&ctx);
            set_dest(vm, &instr->dest, ret_val);
        }
        /* NULL fn pointer → no-op, result = 0 */
        break;
    }



    /* ── Green Thread / Task opcodes (A2) ──────────────── */
    case Q_TASK_SPAWN: {
        /* dest = task_spawn(src1 = function index)
         * Create a task that will execute the async function through the VM.
         * We allocate a context structure containing the module and function index,
         * then pass it to the task entry wrapper. */
        
        /* Read function index - handle both OPERAND_FUNC_IDX and OPERAND_IMM */
        uint32_t fn_idx = 0;
        if (instr->src1.type == OPERAND_FUNC_IDX)
            fn_idx = instr->src1.func_idx;
        else if (instr->src1.type == OPERAND_IMM)
            fn_idx = (uint32_t)instr->src1.imm;
        else
            fn_idx = (uint32_t)operand_value(vm, &instr->src1);
        
        /* Allocate context structure for the task */
        task_vm_context_t *ctx = (task_vm_context_t *)malloc(sizeof(task_vm_context_t));
        if (!ctx) {
            set_dest(vm, &instr->dest, 0);
            break;
        }
        
        ctx->module = vm->module;
        ctx->fn_idx = fn_idx;
        
        /* Capture arguments from current registers R0..R(param_count-1) */
        ctx->nargs = 0;
        if (vm->module && fn_idx < vm->module->func_count) {
            const q_function_t *callee = &vm->module->functions[fn_idx];
            ctx->nargs = callee->param_count < 16 ? callee->param_count : 16;
        }
        for (uint32_t i = 0; i < ctx->nargs; i++) {
            ctx->args[i] = vm->regs[i];
        }
        
        /* Create task with entry wrapper and context */
        uint32_t tid = task_create(task_entry_wrapper, ctx);
        set_dest(vm, &instr->dest, (int64_t)tid);
        break;
    }
    case Q_TASK_YIELD:
        task_yield();
        break;
    case Q_TASK_WAIT: {
        uint32_t tid = (uint32_t)operand_value(vm, &instr->src1);
        
        /* Run the task scheduler to execute pending tasks */
        task_scheduler_run();
        
        /* Get the result from the completed task */
        int64_t result = task_get_result(tid);
        set_dest(vm, &instr->dest, result);
        break;
    }
    case Q_TASK_CANCEL: {
        uint32_t tid = (uint32_t)operand_value(vm, &instr->src1);
        int rc = task_cancel(tid);
        set_dest(vm, &instr->dest, (int64_t)(rc == 0 ? 1 : 0));
        break;
    }

    case Q_HALT:
        return VM_HALT;

    /* ── §13 Error handling ───────────────────────────── */
    case Q_TRY_BEGIN: {
        if (vm->try_sp >= sizeof(vm->try_stack) / sizeof(vm->try_stack[0]))
            return VM_ERR_STACK_OF;
        uint32_t revert_pc = 0;
        if (instr->dest.type == OPERAND_LABEL &&
            instr->dest.label < vm->label_count && vm->active_label_map) {
            revert_pc = vm->active_label_map[instr->dest.label];
        }
        vm->try_stack[vm->try_sp].revert_pc = revert_pc;
        vm->try_stack[vm->try_sp].retry_pc  = vm->ip + 1;
        vm->try_stack[vm->try_sp].snap_count = 0;
        /* §13.7 try(timeout:) — decode flags: bit0=has_timeout,
         * bits 16+ = timeout seconds. Deadline = now + N seconds. */
        int64_t flags = operand_value(vm, &instr->src1);
        if (flags & 1) {
            uint64_t secs = (uint64_t)((flags >> 16) & 0xFFFF);
            vm->try_stack[vm->try_sp].deadline_ns =
                vm_now_ns() + secs * 1000000000ULL;
        } else {
            vm->try_stack[vm->try_sp].deadline_ns = 0;
        }
        vm->try_sp++;
        break;
    }
    case Q_TRY_END:
        if (vm->try_sp > 0) vm->try_sp--;
        break;
    case Q_THROW: {
        int64_t code = operand_value(vm, &instr->src1);
        vm->erx = code;
        if (vm->try_sp > 0) {
            /* Jump to top frame revert handler; frame stays on stack
             * so resume retry/revert can find it. */
            vm->ip = vm->try_stack[vm->try_sp - 1].revert_pc;
            return VM_OK;
        }
        /* No active try — terminate program with erx as exit code. */
        vm->regs[0] = code;
        return VM_HALT;
    }
    case Q_ERX_LOAD:
        set_dest(vm, &instr->dest, vm->erx);
        break;
    case Q_RESUME_RETRY: {
        if (vm->try_sp == 0) return VM_ERR_BAD_JUMP;
        /* Restore isolate snapshots first. */
        uint32_t fi = vm->try_sp - 1;
        for (uint32_t si = 0; si < vm->try_stack[fi].snap_count; si++) {
            vm->regs[vm->try_stack[fi].snaps[si].vreg] =
                vm->try_stack[fi].snaps[si].value;
        }
        vm->erx = 0;
        vm->ip = vm->try_stack[fi].retry_pc;
        return VM_OK;
    }
    case Q_RESUME_REVERT: {
        /* Pop current frame and re-throw erx to parent. */
        if (vm->try_sp == 0) {
            vm->regs[0] = vm->erx;
            return VM_HALT;
        }
        vm->try_sp--;
        if (vm->try_sp > 0) {
            vm->ip = vm->try_stack[vm->try_sp - 1].revert_pc;
            return VM_OK;
        }
        vm->regs[0] = vm->erx;
        return VM_HALT;
    }
    case Q_EMIT_LOG: {
        /* src1 = imm string-table index holding full formatted line. */
        int64_t sidx = operand_value(vm, &instr->src1);
        if (vm->module && sidx >= 0 && (uint32_t)sidx < vm->module->string_count) {
            fprintf(stderr, "%s\n", vm->module->strings[sidx]);
        }
        break;
    }
    case Q_ISOLATE_SAVE: {
        if (vm->try_sp == 0) break;
        uint32_t fi = vm->try_sp - 1;
        if (vm->try_stack[fi].snap_count >= 16) break;
        uint32_t slot = vm->try_stack[fi].snap_count++;
        uint32_t vreg = instr->dest.type == OPERAND_VREG ? instr->dest.vreg : 0;
        vm->try_stack[fi].snaps[slot].vreg  = vreg;
        vm->try_stack[fi].snaps[slot].value = vm->regs[vreg];
        break;
    }
    case Q_ISOLATE_RESTORE: {
        if (vm->try_sp == 0) break;
        uint32_t fi = vm->try_sp - 1;
        for (uint32_t si = 0; si < vm->try_stack[fi].snap_count; si++) {
            vm->regs[vm->try_stack[fi].snaps[si].vreg] =
                vm->try_stack[fi].snaps[si].value;
        }
        break;
    }

    default:
        fprintf(stderr, "FATAL: BAD OPCODE %d at ip=%d func=%d\n", instr->opcode, vm->ip, (int)(vm->current_func - vm->module->functions));
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
                uint32_t frame = vm->func_depth - 1;
                int64_t ref_bindings[Q_MAX_PARAMS] = {0};
                int64_t ref_values[Q_MAX_PARAMS] = {0};
                uint32_t ref_count = 0;
                if (vm->current_func) {
                    ref_count = vm->current_func->param_count;
                    for (uint32_t pi = 0; pi < ref_count && pi < Q_MAX_PARAMS; pi++) {
                        if (!vm->current_func->param_is_ref[pi]) continue;
                        ref_bindings[pi] = vm->func_stack[frame].ref_bindings[pi];
                        ref_values[pi] = vm->regs[vm->current_func->param_vregs[pi]];
                    }
                }
                vm_leave_call_arena(vm, frame, 0, ref_values, ref_count);
                vm->func_depth--;
                vm_restore_caller_window(vm, vm->func_depth);
                vm_apply_ref_writeback(vm, ref_bindings, ref_values, ref_count);
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
                int64_t ret_val = vm->regs[0];
                uint32_t frame = vm->func_depth - 1;
                vm_leave_call_arena(vm, frame, ret_val, NULL, 0);
                vm->func_depth--;
                vm_restore_caller_window(vm, vm->func_depth);
                vm->regs[0] = ret_val;
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
        /* §13.7 try(timeout:) — check top try-frame deadline after each
         * instruction. On expiry, synthesize a throw(erx=2). */
        if (vm->try_sp > 0) {
            uint32_t fi = vm->try_sp - 1;
            uint64_t dl = vm->try_stack[fi].deadline_ns;
            if (dl != 0 && vm_now_ns() >= dl) {
                vm->erx = 2;                    /* spec §13.7: timeout code */
                vm->try_stack[fi].deadline_ns = 0;  /* one-shot */
                vm->ip = vm->try_stack[fi].revert_pc;
                continue;
            }
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

/*
 * vm.c – Q-IR Virtual Machine (Interpreter)
 * ==========================================
 * Spec §2 – Thực thi Q-IR instructions trên thanh ghi ảo.
 * Đây là VM interpreter = Bản A (Safe) fallback.
 */

#include "vm.h"
#include "task.h"
#include "atomic.h"
#include "mem_manager.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <stdint.h>

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
    /* §22.5 Initialize cooperative green-thread scheduler so that
     * Q_TASK_SPAWN/Q_TASK_YIELD/Q_TASK_WAIT and `await pass` are
     * operational. Safe to call repeatedly (idempotent reset). */
    task_scheduler_init();
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
    vm->erx              = 0;
    vm->try_sp           = 0;
    memset(vm->pending_ref_bindings, 0, sizeof(vm->pending_ref_bindings));
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
    /* Free ports */
    for (uint32_t i = 0; i < vm->port_count; i++) {
        free(vm->ports[i].buf);
        vm->ports[i].buf = NULL;
    }
    vm->port_count = 0;
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

/* §Phase-8: intercept bodyless/extern functions whose name matches
 * a known POSIX syscall shim.  Returns 1 when handled (result stored
 * in R0 and caller should treat as VM_OK), or 0 to fall through to
 * normal dispatch.  Enables `vir run` to execute the self-host
 * compiler which itself issues raw mmap/read/write via `extern
 * func syscallN`. */
static int vm_try_syscall_intrinsic(vm_state_t *vm, const q_function_t *callee)
{
    if (!callee || callee->body_count != 0) return 0;
    const char *n = callee->name;
    int64_t r0 = vm->regs[0];
    int64_t r1 = vm->regs[1];
    int64_t r2 = vm->regs[2];
    int64_t r3 = vm->regs[3];
    int64_t r4 = vm->regs[4];
    int64_t r5 = vm->regs[5];
    int64_t result = 0;

    /* Raw POSIX-style helpers (mmap/munmap/read/write/open/close/exit).
     * The Vir-level `syscall1/2/3` shims strip the arch-specific number
     * and dispatch directly here by name; pure mmap syscalls must also
     * be reachable for allocator bring-up. */
    if (strcmp(n, "sys_write") == 0) {
        result = (int64_t)write((int)r0, (const void *)(uintptr_t)r1, (size_t)r2);
    } else if (strcmp(n, "sys_read") == 0) {
        result = (int64_t)read((int)r0, (void *)(uintptr_t)r1, (size_t)r2);
    } else if (strcmp(n, "sys_open") == 0) {
        result = (int64_t)open((const char *)(uintptr_t)r0, (int)r1, (mode_t)r2);
    } else if (strcmp(n, "sys_close") == 0) {
        result = (int64_t)close((int)r0);
    } else if (strcmp(n, "sys_lseek") == 0) {
        result = (int64_t)lseek((int)r0, (off_t)r1, (int)r2);
    } else if (strcmp(n, "sys_exit") == 0) {
        exit((int)r0);
    } else if (strcmp(n, "sys_mmap") == 0) {
        void *p = mmap((void *)(uintptr_t)r0, (size_t)r1,
                       (int)r2, (int)r3, (int)r4, (off_t)r5);
        result = (int64_t)(intptr_t)p;
    } else if (strcmp(n, "sys_munmap") == 0) {
        result = (int64_t)munmap((void *)(uintptr_t)r0, (size_t)r1);
    } else if (strcmp(n, "syscall1") == 0 ||
               strcmp(n, "syscall2") == 0 ||
               strcmp(n, "syscall3") == 0 ||
               strcmp(n, "syscall6") == 0) {
        /* Raw syscall passthrough: r0 = number, r1..r6 = args.
         * We translate a handful of macOS-style BSD numbers (| 0x2000000).
         * Anything unknown returns -1 so callers fall back gracefully. */
        long sn = (long)r0;
        long s = sn & 0x00FFFFFF;
        switch (s) {
        case 1:   exit((int)r1); break;
        case 3:   result = read((int)r1, (void *)(uintptr_t)r2, (size_t)r3); break;
        case 4:   result = write((int)r1, (const void *)(uintptr_t)r2, (size_t)r3); break;
        case 5:   result = open((const char *)(uintptr_t)r1, (int)r2, (mode_t)r3); break;
        case 6:   result = close((int)r1); break;
        case 197: {
            void *p = mmap((void *)(uintptr_t)r1, (size_t)r2,
                           (int)r3, (int)r4, (int)r5, 0);
            result = (int64_t)(intptr_t)p;
            break;
        }
        case 73:  result = munmap((void *)(uintptr_t)r1, (size_t)r2); break;
        default:  result = -1; break;
        }
    } else {
        return 0;
    }
    vm->regs[0] = result;
    return 1;
}

/* Shared dispatch used by both Q_CALL_FUNC and Q_CALL_INDIRECT.
 * Saves caller registers, copies R0..R(n-1) into callee param vregs,
 * and switches ip/current_func. */
static vm_status_t vm_dispatch_call(vm_state_t *vm, uint32_t fidx)
{
    if (fidx >= vm->module->func_count) return VM_ERR_BAD_JUMP;
    const q_function_t *callee = &vm->module->functions[fidx];

    /* §Phase-8: route empty-body shims to POSIX syscall intrinsics
     * before pushing a frame.  If handled, just advance past the call. */
    if (vm_try_syscall_intrinsic(vm, callee)) {
        vm->ip++;
        return VM_OK;
    }

    if (vm->func_depth >= VM_MAX_CALL_DEPTH) return VM_ERR_STACK_OF;
    vm->func_stack[vm->func_depth].func = vm->current_func;
    vm->func_stack[vm->func_depth].ip   = vm->ip + 1;

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
        for (uint32_t ri = 0; ri < nregs; ri++)
            vm->func_stack[vm->func_depth].saved_regs[ri] = vm->regs[ri];
    }
    for (uint32_t pi = 0; pi < Q_MAX_PARAMS; pi++)
        vm->func_stack[vm->func_depth].ref_bindings[pi] =
            vm->pending_ref_bindings[pi];
    vm->func_depth++;
    memset(vm->pending_ref_bindings, 0, sizeof(vm->pending_ref_bindings));

    for (uint32_t pi = 0; pi < callee->param_count && pi < Q_MAX_PARAMS; pi++) {
        vm->regs[callee->param_vregs[pi]] = vm->regs[pi];
    }

    vm->current_func = callee;
    vm->ip = 0;
    vm_resolve_labels(vm, callee);
    return VM_OK;
}

static vm_status_t vm_dispatch_tailcall(vm_state_t *vm, uint32_t fidx)
{
    if (fidx >= vm->module->func_count) return VM_ERR_BAD_JUMP;
    const q_function_t *callee = &vm->module->functions[fidx];

    /* For tail call, we reuse the current frame.
     * Update parameter vregs for the callee. */
    for (uint32_t pi = 0; pi < callee->param_count && pi < Q_MAX_PARAMS; pi++) {
        vm->regs[callee->param_vregs[pi]] = vm->regs[pi];
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
            int64_t ref_bindings[Q_MAX_PARAMS] = {0};
            int64_t ref_values[Q_MAX_PARAMS] = {0};
            uint32_t ref_count = 0;
            if (vm->current_func) {
                ref_count = vm->current_func->param_count;
                for (uint32_t pi = 0; pi < ref_count && pi < Q_MAX_PARAMS; pi++) {
                    if (!vm->current_func->param_is_ref[pi]) continue;
                    ref_bindings[pi] = vm->func_stack[vm->func_depth].ref_bindings[pi];
                    ref_values[pi] = vm->regs[vm->current_func->param_vregs[pi]];
                }
            }
            /* Restore saved registers */
            uint32_t nregs = vm->func_stack[vm->func_depth].saved_reg_count;
            for (uint32_t ri = 0; ri < nregs; ri++) {
                vm->regs[ri] = vm->func_stack[vm->func_depth].saved_regs[ri];
            }
            free(vm->func_stack[vm->func_depth].saved_regs);
            vm->func_stack[vm->func_depth].saved_regs = NULL;
            vm->func_stack[vm->func_depth].saved_reg_count = 0;
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
        /* §4.8 Auto-drop: Q_FREE is polymorphic and safe.
         *   (a) array handle in [0, array_count): free array data, zero the slot.
         *   (b) pointer present in rt_strings[]: free string, null the slot.
         *   (c) pointer present in heap_blocks[] (from Q_ALLOC): free block.
         *   (d) anything else: no-op. */
        if (addr == 0) break;
        /* (a) array handle */
        if (addr >= 0 && (uint32_t)addr < vm->array_count) {
            vm_array_t *a = &vm->arrays[(uint32_t)addr];
            if (a->data) { free(a->data); a->data = NULL; }
            a->len = 0;
            a->cap = 0;
            break;
        }
        void *p = (void *)(intptr_t)addr;
        /* (b) runtime string */
        for (uint32_t i = 0; i < vm->rt_string_count; i++) {
            if (vm->rt_strings[i] == (char *)p) {
                free(vm->rt_strings[i]);
                vm->rt_strings[i] = NULL;
                goto q_free_done;
            }
        }
        /* (c) heap_blocks from Q_ALLOC */
        for (uint32_t i = 0; i < vm->heap_count; i++) {
            if (vm->heap_blocks[i] == p) {
                free(p);
                vm->heap_blocks[i] = vm->heap_blocks[--vm->heap_count];
                break;
            }
        }
    q_free_done:
        break;
    }
    case Q_LOAD_BYTE: {
        int64_t base = operand_value(vm, &instr->src1);
        int64_t off  = operand_value(vm, &instr->src2);
        /* Null/invalid pointer guard: address 0 or below page boundary */
        if (base == 0 || (base > 0 && base < 4096 &&
            !(base >= VM_MMIO_BASE && base < VM_MMIO_BASE + (int64_t)VM_MMIO_SIZE))) {
            set_dest(vm, &instr->dest, 0);
            break;
        }
        uint8_t *ptr = (uint8_t *)(intptr_t)base;
        set_dest(vm, &instr->dest, ptr ? (int64_t)ptr[off] : 0);
        break;
    }
    case Q_STORE_BYTE: {
        int64_t base = operand_value(vm, &instr->src1);
        int64_t off  = operand_value(vm, &instr->src2);
        int64_t val  = operand_value(vm, &instr->dest);
        /* Null/invalid pointer guard */
        if (base == 0 || (base > 0 && base < 4096 &&
            !(base >= VM_MMIO_BASE && base < VM_MMIO_BASE + (int64_t)VM_MMIO_SIZE))) {
            break;  /* silently ignore write to null/invalid ptr */
        }
        uint8_t *ptr = (uint8_t *)(intptr_t)base;
        if (ptr) ptr[off] = (uint8_t)val;
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
            /* Null/invalid pointer guard */
            if (base == 0 || (base > 0 && base < 4096)) {
                set_dest(vm, &instr->dest, 0);
                break;
            }
            int64_t *ptr = (int64_t *)((char *)(intptr_t)base + idx);
            set_dest(vm, &instr->dest, ptr ? *ptr : 0);
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
            /* Null/invalid pointer guard */
            if (base == 0 || (base > 0 && base < 4096)) {
                break;  /* silently ignore write to null/invalid ptr */
            }
            int64_t *ptr = (int64_t *)((char *)(intptr_t)base + idx);
            if (ptr) *ptr = val;
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
    case Q_ARENA_NEW: {
        int64_t sz = operand_value(vm, &instr->src1);
        if (sz <= 0) sz = 4096;
        int aid = vir_arena_create((size_t)sz);
        set_dest(vm, &instr->dest, (int64_t)aid);
        break;
    }
    case Q_ARENA_ALLOC: {
        int64_t aid = operand_value(vm, &instr->src1);
        int64_t sz  = operand_value(vm, &instr->src2);
        void *p = (sz > 0) ? vir_arena_alloc((int)aid, (size_t)sz) : NULL;
        set_dest(vm, &instr->dest, (int64_t)(intptr_t)p);
        break;
    }
    case Q_ARENA_FREE: {
        int64_t aid = operand_value(vm, &instr->src1);
        vir_arena_destroy((int)aid);
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
        if (instr->dest.type == OPERAND_LABEL && instr->dest.label < VM_MAX_LABELS) {
            revert_pc = vm->label_map[instr->dest.label];
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
                int64_t ref_bindings[Q_MAX_PARAMS] = {0};
                int64_t ref_values[Q_MAX_PARAMS] = {0};
                uint32_t ref_count = 0;
                if (vm->current_func) {
                    ref_count = vm->current_func->param_count;
                    for (uint32_t pi = 0; pi < ref_count && pi < Q_MAX_PARAMS; pi++) {
                        if (!vm->current_func->param_is_ref[pi]) continue;
                        ref_bindings[pi] = vm->func_stack[vm->func_depth].ref_bindings[pi];
                        ref_values[pi] = vm->regs[vm->current_func->param_vregs[pi]];
                    }
                }
                /* Restore caller's registers */
                uint32_t saved_count = vm->func_stack[vm->func_depth].saved_reg_count;
                for (uint32_t ri = 0; ri < saved_count; ri++) {
                    vm->regs[ri] = vm->func_stack[vm->func_depth].saved_regs[ri];
                }
                free(vm->func_stack[vm->func_depth].saved_regs);
                vm->func_stack[vm->func_depth].saved_regs = NULL;
                vm->func_stack[vm->func_depth].saved_reg_count = 0;
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

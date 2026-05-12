/*
 * vm.h – Q-IR Virtual Machine (Interpreter / Executor)
 * =====================================================
 * Spec §2 – Thực thi Q-IR instructions trên thanh ghi ảo.
 *
 * Đây là VM interpreter dùng cho chế độ Safe (Bản A).
 * Khi CPU rảnh, Backend sẽ patch sang mã máy thuần (Bản B).
 */

#ifndef VIR_VM_H
#define VIR_VM_H

#include "q_ir.h"
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * VM State
 * ═══════════════════════════════════════════════════════ */

#define VM_STACK_SIZE     4096
#define VM_MAX_LABELS     1024
#define VM_MAX_CALL_DEPTH 256

#define VM_MMIO_BASE  0x1000
#define VM_MMIO_SIZE  4096

typedef enum {
    VM_OK           = 0,
    VM_HALT         = 1,
    VM_ERR_DIV_ZERO = -1,
    VM_ERR_STACK_OF = -2,
    VM_ERR_BAD_OP   = -3,
    VM_ERR_BAD_JUMP = -4,
    VM_ERR_PATCH    = -5,
    VM_ERR_NULL_PTR = -6,
} vm_status_t;

/* Callback cho Q_PATCH_POINT – Backend có thể cung cấp hàm thay thế */
typedef int64_t (*vm_patch_handler_t)(uint32_t patch_id, int64_t *regs,
                                      uint32_t reg_count, void *userdata);

/* ═══════════════════════════════════════════════════════
 * VM Array (dynamic int64 array for Q_ARR_* opcodes)
 * ═══════════════════════════════════════════════════════ */

#define VM_MAX_ARRAYS   16384
#define VM_MAX_GLOBALS  1024

typedef struct {
    int64_t  *data;
    uint32_t  len;
    uint32_t  cap;
    /* §26.1 tensor shape metadata (0 = not a tensor) */
    uint8_t   ndim;
    uint32_t  shape[4];
} vm_array_t;

/* ═══════════════════════════════════════════════════════
 * VM Dict (§20 hash table)
 * ═══════════════════════════════════════════════════════
 * Open addressing with linear probing. Resize when load ≥ 75%.
 * key_type: 0=unset, 1=int, 2=string. First insert locks type.
 * For string keys: key_i holds FNV-1a hash, key_s holds strdup'd key.
 * For int keys: key_i is the value, key_s is NULL.
 */
#define VM_MAX_DICTS 8192

typedef struct {
    uint8_t  state;       /* 0=empty, 1=occupied, 2=tombstone */
    uint8_t  pad;
    int64_t  key_i;       /* int key, or hash for string      */
    char    *key_s;       /* string key (strdup) or NULL      */
    int64_t  value;
} vm_dict_entry_t;

typedef struct {
    vm_dict_entry_t *entries;
    uint32_t         cap;
    uint32_t         count;        /* live entries (exclude tombstones) */
    uint8_t          key_type;     /* 0=unset, 1=int, 2=string          */
} vm_dict_t;

/* ═══════════════════════════════════════════════════════
 * §23 VM Port (inter-worker channel, ring buffer)
 * ═══════════════════════════════════════════════════════ */
#define VM_MAX_PORTS     1024
#define VM_PORT_DEFAULT_CAP 16

typedef struct {
    int64_t  *buf;
    uint32_t  cap;
    uint32_t  head;   /* next read  */
    uint32_t  tail;   /* next write */
    uint32_t  count;
    uint8_t   closed;
} vm_port_t;

/* ═══════════════════════════════════════════════════════
 * VM Heap Tracking
 * ═══════════════════════════════════════════════════════ */

#define VM_MAX_HEAP_BLOCKS 16384
#define VM_MAX_STRINGS_RT  16384

typedef struct {
    /* Virtual registers (§2.2 – unlimited, but capped at VREG_MAX) */
    int64_t         regs[VREG_MAX];
    uint32_t        reg_count;      /* Highest vreg used + 1 */

    /* Stack (for call/ret - intra-function labels) */
    uint32_t        call_stack[VM_MAX_CALL_DEPTH];
    uint32_t        call_depth;

    /* Cross-function call stack */
    struct { 
        const q_function_t *func; 
        uint32_t ip;
        int64_t *saved_regs;
        uint32_t saved_reg_count;
        int64_t ref_bindings[Q_MAX_PARAMS];
    } func_stack[VM_MAX_CALL_DEPTH];
    uint32_t        func_depth;
    const q_function_t *current_func;  /* currently executing function */
    int64_t         pending_ref_bindings[Q_MAX_PARAMS];

    /* Global variables (shared across function calls) */
    int64_t         globals[VM_MAX_GLOBALS];
    uint32_t        global_count;

    /* Label → instruction index mapping */
    uint32_t        label_map[VM_MAX_LABELS];
    uint32_t        label_count;

    /* Instruction pointer */
    uint32_t        ip;

    /* Status */
    vm_status_t     status;

    /* Patch handler (optional) */
    vm_patch_handler_t patch_handler;
    void              *patch_userdata;

    /* Statistics */
    uint64_t        instr_executed;
    uint64_t        patches_triggered;

    /* Arrays managed by VM */
    vm_array_t      arrays[VM_MAX_ARRAYS];
    uint32_t        array_count;

    /* §20 Dicts managed by VM */
    vm_dict_t       dicts[VM_MAX_DICTS];
    uint32_t        dict_count;

    /* §23 Ports managed by VM */
    vm_port_t       ports[VM_MAX_PORTS];
    uint32_t        port_count;

    /* Heap allocated blocks (for Q_ALLOC/Q_FREE) */
    void           *heap_blocks[VM_MAX_HEAP_BLOCKS];
    uint32_t        heap_count;

    /* Runtime string table (for Q_STR_CAT, Q_I_TO_STR, etc.) */
    char           *rt_strings[VM_MAX_STRINGS_RT];
    uint32_t        rt_string_count;

    /* §13 Error handling state */
    int64_t         erx;                 /* error register                     */
    struct {
        uint32_t revert_pc;              /* jump target on throw               */
        uint32_t retry_pc;               /* jump target for resume retry       */
        uint32_t snap_count;             /* # of isolate snapshot slots        */
        uint64_t deadline_ns;            /* §13.7 try(timeout:) — 0 = disabled */
        struct { uint32_t vreg; int64_t value; } snaps[16];
    } try_stack[32];
    uint32_t        try_sp;              /* top of try stack                   */

    /* Module reference (for string table) */
    const q_module_t *module;

    /* Program arguments */
    const char **args;
    int          arg_count;

    /* §16.5 Simulated MMIO region for volatile_read / volatile_write */
    int64_t mmio_region[VM_MMIO_SIZE / sizeof(int64_t)];
} vm_state_t;

/* ═══════════════════════════════════════════════════════
 * VM API
 * ═══════════════════════════════════════════════════════ */

/* Initialize / reset / destroy VM state */
void vm_init(vm_state_t *vm);
void vm_reset(vm_state_t *vm);
void vm_destroy(vm_state_t *vm);
void vm_set_module(vm_state_t *vm, const q_module_t *mod);
void vm_set_args(vm_state_t *vm, int argc, const char **argv);

/* Set patch handler (called at Q_PATCH_POINT) */
void vm_set_patch_handler(vm_state_t *vm, vm_patch_handler_t handler, void *ud);

/* Pre-scan labels in a function */
int vm_resolve_labels(vm_state_t *vm, const q_function_t *func);

/* Execute a single instruction */
vm_status_t vm_step(vm_state_t *vm, const q_instruction_t *instr);

/* Execute an entire function */
vm_status_t vm_exec_function(vm_state_t *vm, const q_function_t *func);

/* Execute a module (runs first function, or __main__) */
vm_status_t vm_exec_module(vm_state_t *vm, const q_module_t *mod);

/* Get register value */
int64_t vm_get_reg(const vm_state_t *vm, uint32_t vreg);
void    vm_set_reg(vm_state_t *vm, uint32_t vreg, int64_t value);

/* Status string */
const char* vm_status_str(vm_status_t status);

#ifdef __cplusplus
}
#endif

#endif /* VIR_VM_H */

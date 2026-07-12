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
/* Minimum vregs preserved across Q_CALL_FUNC (must match vm.c). */
#define VM_CALL_SAVE_MIN  1024u

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
 * §Phase-9 Intrinsic Registry
 * ═══════════════════════════════════════════════════════
 * Table-driven O(1) dispatch for all external effects.
 * The VM layer knows nothing about language semantics or
 * OS ABI — it only calls fn(ctx).
 *
 * Instruction format (Q_INTRINSIC):
 *   dest = return vreg
 *   src1 = OPERAND_IMM  intrinsic_id  (index into table)
 *   src2 = OPERAND_IMM  argc          (args in R0..Rn)
 */

/* Intrinsic IDs — must match intrinsic_table[] order in vm.c */
typedef enum {
    /* Syscall passthrough (raw POSIX) */
    VIR_INTR_SYSCALL        = 0,  /* R0=num, R1..R6=args         */
    VIR_INTR_SYS_READ       = 1,  /* R0=fd, R1=buf, R2=len       */
    VIR_INTR_SYS_WRITE      = 2,  /* R0=fd, R1=buf, R2=len       */
    VIR_INTR_SYS_OPEN       = 3,  /* R0=path, R1=flags, R2=mode  */
    VIR_INTR_SYS_CLOSE      = 4,  /* R0=fd                       */
    VIR_INTR_SYS_LSEEK      = 5,  /* R0=fd, R1=offset, R2=whence */
    VIR_INTR_SYS_MMAP       = 6,  /* R0..R5=mmap args            */
    VIR_INTR_SYS_MUNMAP     = 7,  /* R0=addr, R1=len             */
    VIR_INTR_SYS_EXIT       = 8,  /* R0=code                     */
    /* Memory */
    VIR_INTR_MEMCPY         = 9,  /* R0=dst, R1=src, R2=len      */
    VIR_INTR_MEMSET         = 10, /* R0=dst, R1=val, R2=len      */
    /* Debug / Trap */
    VIR_INTR_TRAP           = 11, /* abort()                     */
    /* Bitwise / Math */
    VIR_INTR_CLZ            = 12, /* R0=val                      */
    VIR_INTR_CTZ            = 13, /* R0=val                      */
    VIR_INTR_POPCNT         = 14, /* R0=val                      */
    VIR_INTR_BSWAP          = 15, /* R0=val                      */
    /* Atomics */
    VIR_INTR_ATOMIC_LOAD    = 16, /* R0=addr                     */
    VIR_INTR_ATOMIC_STORE   = 17, /* R0=addr, R1=val             */
    VIR_INTR_ATOMIC_ADD     = 18, /* R0=addr, R1=val             */
    VIR_INTR_ATOMIC_SUB     = 19, /* R0=addr, R1=val             */

    VIR_INTR_COUNT          = 20  /* sentinel – size of table    */
} vir_intrinsic_id_t;

/* Execution context passed to every intrinsic handler */
typedef struct vm_state vm_state_t;  /* forward declaration for vir_intrinsic_ctx_t */
typedef struct {
    int64_t        *args;   /* pointer to vm->regs[0]              */
    int             argc;   /* number of arguments (informational) */
    int64_t        *ret;    /* pointer to dest register            */
    vm_state_t     *vm;     /* full VM state (escape hatch)        */
} vir_intrinsic_ctx_t;


typedef void (*vir_intrinsic_fn)(vir_intrinsic_ctx_t *ctx);

/* Flags for vir_intr_desc_t.flags */
#define INTR_PURE     0x01   /* No side effects – may be DCE'd     */
#define INTR_IMPURE   0x02   /* Has side effects (I/O, memory)     */
#define INTR_TRAP     0x04   /* Never returns (exit / abort)       */
#define INTR_NOINLINE 0x08   /* Do not inline into caller          */

typedef struct {
    vir_intrinsic_fn fn;
    uint8_t          argc;   /* expected arg count (0 = variadic)  */
    uint8_t          flags;  /* INTR_* flags                       */
    const char      *name;   /* human-readable name (debug/trace)  */
} vir_intr_desc_t;

#define VIR_MAX_INTRINSICS 1024

/* Intrinsic registry – defined and populated in vm.c */
extern vir_intr_desc_t vir_intr_table[VIR_MAX_INTRINSICS];




/* ═══════════════════════════════════════════════════════
 * VM Array (dynamic int64 array for Q_ARR_* opcodes)
 * ═══════════════════════════════════════════════════════ */

#define VM_MAX_ARRAYS   1048576
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

typedef struct vm_state {

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
        int64_t saved_regs[VM_CALL_SAVE_MIN];
        uint32_t saved_reg_count;
        uint32_t caller_reg_count;
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

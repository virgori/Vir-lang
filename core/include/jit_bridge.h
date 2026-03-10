/*
 * jit_bridge.h – JIT Bridge Singleton
 * ====================================
 * Central controller for the JIT execution environment.
 *
 * Responsibilities:
 *   1. Manage executable memory regions (alloc / free / protect)
 *   2. Register native callbacks that JIT code can CALL
 *   3. Emit machine-code call thunks (MOV addr → reg; CALL reg)
 *      so that JIT-compiled code reaches native C functions
 *   4. Maintain a global address table for intrinsics + user callbacks
 */

#ifndef VIR_JIT_BRIDGE_H
#define VIR_JIT_BRIDGE_H

#include "bridge.h"
#include "codegen.h"
#include "intrinsics.h"
#include "patcher.h"
#include "signer.h"
#include <stdint.h>
#include <stddef.h>
#include <pthread.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * Callback Slot
 * ═══════════════════════════════════════════════════════
 * Each registered callback gets an entry with its resolved
 * address, so that the codegen can embed CALL <addr> or
 * load it from a jump table.
 */

#define JIT_MAX_CALLBACKS 64

typedef struct {
    const char *name;       /* Human-readable id            */
    void       *addr;       /* Resolved native address      */
    uint8_t     arg_count;  /* For ABI correctness          */
    vir_type_t  ret_type;
} jit_callback_t;

/* ═══════════════════════════════════════════════════════
 * Executable Code Block
 * ═══════════════════════════════════════════════════════
 * A single block of JIT-compiled code living in an
 * executable memory region.  Multiple blocks share one region.
 */

#define JIT_MAX_BLOCKS 256

typedef struct {
    uint32_t id;           /* User-assigned or auto-id      */
    size_t   offset;       /* Byte offset within the region */
    size_t   size;         /* Length in bytes                */
    uint8_t  signature[32]; /* HMAC-SHA256 of code content  */
    int      verified;     /* Last verify result             */

    /* ── Rollback / Performance Tracking ────────────── */
    size_t   safe_offset;  /* Offset of Bản A (Safe code)   */
    size_t   safe_size;
    size_t   fast_offset;  /* Offset of Bản B (Fast code)   */
    size_t   fast_size;
    int      is_fast;      /* 0 = safe, 1 = fast            */
    uint64_t exec_count;   /* Times this block was entered   */
    uint64_t fast_fail_count; /* Faults detected while fast  */

    /* ── Blacklist (PERMANENT_SAFE) ─────────────────── */
    uint32_t rollback_count;  /* Total rollbacks for this block */
    int      permanent_safe;  /* 1 = blacklisted, never fast   */
} jit_block_t;

/* ═══════════════════════════════════════════════════════
 * JIT Bridge (Singleton State)
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    /* Architecture info */
    target_arch_t    arch;
    const abi_info_t *abi;

    /* Executable memory region */
    uint8_t         *region_base;
    size_t           region_size;
    size_t           region_used;

    /* Callback registry */
    jit_callback_t   callbacks[JIT_MAX_CALLBACKS];
    uint32_t         callback_count;

    /* Callback address table: contiguous array of void*
     * so JIT code can do: MOV reg, [table_base + id*8]; CALL reg */
    void            *callback_table[JIT_MAX_CALLBACKS];

    /* Code blocks */
    jit_block_t      blocks[JIT_MAX_BLOCKS];
    uint32_t         block_count;

    /* Integrated patcher */
    patcher_t        patcher;

    /* Code signer for integrity verification */
    signer_t         signer;

    /* Blacklist threshold: after N rollbacks a block is
     * PERMANENT_SAFE and patch_to_fast refuses it.
     * 0 = disabled (default). */
    uint32_t         blacklist_threshold;

    /* State flags */
    int              initialised;
    int              region_executable;  /* 1 if currently RX */

    /* Thread safety */
    pthread_mutex_t  lock;
} jit_bridge_t;

/* ═══════════════════════════════════════════════════════
 * Lifecycle
 * ═══════════════════════════════════════════════════════ */

/* Initialise the global JIT bridge (idempotent). */
int jit_bridge_init(jit_bridge_t *jb, size_t region_size);

/* Shut down and release all resources. */
void jit_bridge_destroy(jit_bridge_t *jb);

/* Get the global singleton bridge (auto-inits with 1MB). */
jit_bridge_t *jit_bridge_global(void);

/* ═══════════════════════════════════════════════════════
 * Callback Registration
 * ═══════════════════════════════════════════════════════ */

/* Register a native function for JIT code to call.
 * Returns the callback slot index (≥0) or -1 on error. */
int jit_bridge_register(jit_bridge_t *jb,
                        const char *name, void *func_addr,
                        uint8_t arg_count, vir_type_t ret_type);

/* Auto-register all built-in intrinsics. */
int jit_bridge_register_intrinsics(jit_bridge_t *jb);

/* Lookup callback address by name (NULL if not found). */
void *jit_bridge_lookup(const jit_bridge_t *jb, const char *name);

/* Get the base address of the callback table (for embedding
 * in generated code as a data constant). */
void **jit_bridge_callback_table(jit_bridge_t *jb);

/* ═══════════════════════════════════════════════════════
 * Code Emission
 * ═══════════════════════════════════════════════════════ */

/* Copy machine code into the JIT region.
 * Returns the block index (≥0) or -1 on error.
 * The region must be in writable state. */
int jit_bridge_emit_code(jit_bridge_t *jb, uint32_t block_id,
                         const uint8_t *code, size_t code_len);

/* Emit a machine-code thunk that CALLs a callback by slot index.
 * Writes directly into `cb` (codebuf_t from codegen.h).
 * This is how codegen connects Q_PRINT → vir_builtin_print_i64. */
int jit_bridge_emit_call_thunk(const jit_bridge_t *jb,
                               codebuf_t *cb,
                               uint32_t callback_slot);

/* ═══════════════════════════════════════════════════════
 * Memory Protection
 * ═══════════════════════════════════════════════════════ */

/* Switch region to executable (after writing all code). */
int jit_bridge_finalise(jit_bridge_t *jb);

/* Switch region back to writable (for patching). */
int jit_bridge_begin_patch(jit_bridge_t *jb);

/* After patching: re-sign + re-protect. */
int jit_bridge_end_patch(jit_bridge_t *jb);

/* ═══════════════════════════════════════════════════════
 * Execution
 * ═══════════════════════════════════════════════════════ */

/* Get function pointer to a code block. */
typedef int64_t (*jit_entry_fn)(int64_t, int64_t);

jit_entry_fn jit_bridge_get_entry(const jit_bridge_t *jb,
                                  uint32_t block_id);

/* ═══════════════════════════════════════════════════════
 * Integrity
 * ═══════════════════════════════════════════════════════ */

/* Verify code block against its HMAC signature. */
int jit_bridge_verify_block(const jit_bridge_t *jb, uint32_t block_id);

/* Verify all blocks. Returns 0 if all pass. */
int jit_bridge_verify_all(const jit_bridge_t *jb);

/* ═══════════════════════════════════════════════════════
 * Redundancy Patching (Rollback)
 * ═══════════════════════════════════════════════════════
 *
 * Emit both Safe and Fast variants for a block.  The block
 * starts pointing at Safe code; after patching to Fast, if
 * the Fast code triggers a fault or doesn't improve perf,
 * jit_bridge_rollback will atomically revert the jump target
 * back to Safe code.
 */

/* Emit both safe and fast code for a block.  The active
 * entry point starts at safe_code.
 * Returns the block index (>=0) or -1 on error. */
int jit_bridge_emit_dual(jit_bridge_t *jb, uint32_t block_id,
                         const uint8_t *safe_code, size_t safe_len,
                         const uint8_t *fast_code, size_t fast_len);

/* Switch a dual-emitted block from Safe → Fast. */
int jit_bridge_patch_to_fast(jit_bridge_t *jb, uint32_t block_id);

/* Rollback: switch a block from Fast → Safe immediately.
 * Re-signs the block and flushes icache. */
int jit_bridge_rollback(jit_bridge_t *jb, uint32_t block_id);

/* Report a fault on a fast-path block.  If fast_fail_count
 * exceeds `max_faults`, automatically rolls back.
 * Returns 1 if rollback was triggered, 0 if still fast. */
int jit_bridge_report_fault(jit_bridge_t *jb, uint32_t block_id,
                            uint32_t max_faults);

/* Query whether a block is currently using fast code. */
int jit_bridge_is_fast(const jit_bridge_t *jb, uint32_t block_id);

/* ═══════════════════════════════════════════════════════
 * Blacklist (PERMANENT_SAFE)
 * ═══════════════════════════════════════════════════════
 * After N rollbacks, a block is blacklisted and can never
 * be patched to fast again.  The threshold is configurable.
 */

/* Set the blacklist threshold.  0 = disabled (default). */
void jit_bridge_set_blacklist_threshold(jit_bridge_t *jb, uint32_t threshold);

/* Query if a block is blacklisted (permanent safe). */
int jit_bridge_is_blacklisted(const jit_bridge_t *jb, uint32_t block_id);

#ifdef __cplusplus
}
#endif

#endif /* VIR_JIT_BRIDGE_H */

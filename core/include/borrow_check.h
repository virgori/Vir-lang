/*
 * borrow_check.h – Compile-time Borrow Checker for Q-IR
 * ======================================================
 * Validates ownership, borrow, and lifetime rules on Q-IR
 * functions before codegen. Operates as a pass after IR lowering.
 *
 * Rules:
 *   1. Each value has exactly one owner at any point.
 *   2. When owner goes out of scope, value is dropped.
 *   3. Shared borrows (&) allow many readers.
 *   4. Mutable borrows (&mut) are exclusive.
 *   5. Borrows cannot outlive the owner.
 *   6. MOVE transfers ownership; old name becomes invalid.
 *   7. Copy types (int, float, bool) are implicitly copied.
 *
 * Extensions:
 *   - Non-Lexical Lifetimes (NLL): CFG-based liveness analysis.
 *     Variables die at their last use on any reachable path, not at
 *     the closing brace of their lexical scope.
 *   - Polychromatic Borrowing: Fine-grained borrow classification
 *     (read-only fields vs mutated fields) for complex structures.
 *   - Inter-procedural Analysis: Cross-function lifetime propagation
 *     via function signatures.
 */

#ifndef VIR_BORROW_CHECK_H
#define VIR_BORROW_CHECK_H

#include "q_ir.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * Ownership State
 * ═══════════════════════════════════════════════════════ */
typedef enum {
    OWN_UNINIT,          /* not yet assigned           */
    OWN_OWNED,           /* value is owned here        */
    OWN_MOVED,           /* ownership transferred away */
    OWN_BORROWED,        /* currently shared-borrowed  */
    OWN_MUT_BORROWED,    /* currently mut-borrowed     */
    OWN_COPY,            /* Copy type (int/float/bool) */
    OWN_STATIC,          /* static lifetime (literals) */
} ownership_state_t;

/* ═══════════════════════════════════════════════════════
 * Borrow Color (Polychromatic Borrowing)
 * ═══════════════════════════════════════════════════════
 * Each borrow is "colored" to distinguish what kind of access
 * it represents. Multiple compatible colors can coexist.
 *   - READ:      Field/data read access only
 *   - WRITE:     Field/data mutation
 *   - PARTIAL:   Borrows a specific field/index, not whole object
 *   - CONTAINER: Borrows the container structure (not elements)
 */
typedef enum {
    BORROW_READ       = 0x01,
    BORROW_WRITE      = 0x02,
    BORROW_PARTIAL    = 0x04,   /* single field/index */
    BORROW_CONTAINER  = 0x08,   /* container itself, not its items */
} borrow_color_t;

/* ═══════════════════════════════════════════════════════
 * Borrow Record
 * ═══════════════════════════════════════════════════════ */
typedef struct {
    uint32_t  borrower_vreg;  /* who is borrowing          */
    uint32_t  owner_vreg;     /* who is being borrowed     */
    uint32_t  start_ip;       /* instruction where borrow starts */
    uint32_t  end_ip;         /* last use of borrower (NLL) */
    bool      is_mutable;     /* &mut vs &                 */
    uint32_t  color;          /* bitmask of borrow_color_t */
    int32_t   field_index;    /* field idx for PARTIAL (-1 = whole) */
} borrow_record_t;

/* ═══════════════════════════════════════════════════════
 * Variable (vreg) Info
 * ═══════════════════════════════════════════════════════ */
typedef struct {
    uint32_t          vreg;
    ownership_state_t state;
    uint32_t          birth_ip;       /* first assignment      */
    uint32_t          death_ip;       /* last use (NLL: on any path) */
    uint32_t          moved_at;       /* IP of move (if MOVED) */
    bool              is_copy_type;   /* int/float/bool        */
    bool              is_alloc;       /* came from Q_ALLOC/Q_ARR_NEW/etc */
    bool              is_alive;       /* has been assigned      */
} var_info_t;

/* ═══════════════════════════════════════════════════════
 * Drop Point
 * ═══════════════════════════════════════════════════════ */
typedef struct {
    uint32_t  ip;    /* insert Q_FREE before this instruction */
    uint32_t  vreg;  /* the vreg to free                      */
} drop_point_t;

/* ═══════════════════════════════════════════════════════
 * CFG Basic Block (for NLL)
 * ═══════════════════════════════════════════════════════ */
#define CFG_MAX_BLOCKS      512
#define CFG_MAX_SUCCESSORS  8

typedef struct {
    uint32_t  start_ip;         /* first instruction (inclusive) */
    uint32_t  end_ip;           /* last instruction (inclusive)  */

    /* Successor block indices */
    uint32_t  succ[CFG_MAX_SUCCESSORS];
    uint32_t  succ_count;

    /* Predecessor block indices */
    uint32_t  pred[CFG_MAX_SUCCESSORS];
    uint32_t  pred_count;

    /* NLL liveness: bit-set of live vregs at entry/exit of this block.
     * Packed as uint64 words, 1 bit per vreg. Max 4096 vregs → 64 words. */
    uint64_t  live_in[64];
    uint64_t  live_out[64];
} cfg_block_t;

/* ═══════════════════════════════════════════════════════
 * Inter-procedural Summary (per function)
 * ═══════════════════════════════════════════════════════
 * Records which output lifetimes depend on which input params.
 * E.g., func foo(a: &Str) -> &Str  →  return lifetime = param 0's lifetime.
 */
#define IPA_MAX_FUNCS       1024
#define IPA_MAX_PARAMS      16

typedef struct {
    char      name[64];
    uint32_t  param_count;
    /* For each param slot: which borrow states it can carry */
    struct {
        bool  is_borrowed;      /* param is a borrow */
        bool  is_mut;           /* &mut param */
    } params[IPA_MAX_PARAMS];
    /* Return borrow info: which param's lifetime does the return depend on? */
    int32_t   return_depends_on;  /* param index or -1 (owned) */
    bool      return_is_borrow;
} ipa_func_summary_t;

/* ═══════════════════════════════════════════════════════
 * Borrow Checker Context
 * ═══════════════════════════════════════════════════════ */

#define BC_MAX_VARS     4096
#define BC_MAX_BORROWS  1024
#define BC_MAX_DROPS    4096
#define BC_MAX_ERRORS   64
#define BC_ERROR_LEN    256

typedef struct {
    /* Per-vreg information */
    var_info_t       vars[BC_MAX_VARS];
    uint32_t         var_count;

    /* Active borrow records */
    borrow_record_t  borrows[BC_MAX_BORROWS];
    uint32_t         borrow_count;

    /* Computed drop insertion points */
    drop_point_t     drops[BC_MAX_DROPS];
    uint32_t         drop_count;

    /* Error messages */
    char             errors[BC_MAX_ERRORS][BC_ERROR_LEN];
    int              error_count;

    /* Function being checked */
    const char      *func_name;

    /* CFG for NLL */
    cfg_block_t      blocks[CFG_MAX_BLOCKS];
    uint32_t         block_count;
    bool             nll_enabled;

    /* Polychromatic: enable fine-grained borrow coloring */
    bool             polychrome_enabled;

    /* Inter-procedural summaries (shared across module check) */
    ipa_func_summary_t  *ipa_table;   /* pointer to shared table */
    uint32_t             ipa_count;
} borrow_ctx_t;

/* ═══════════════════════════════════════════════════════
 * API
 * ═══════════════════════════════════════════════════════ */

/* Initialize a borrow checker context */
void borrow_ctx_init(borrow_ctx_t *ctx);

/* Enable Non-Lexical Lifetimes (CFG-based liveness) */
void borrow_enable_nll(borrow_ctx_t *ctx);

/* Enable Polychromatic Borrowing */
void borrow_enable_polychrome(borrow_ctx_t *ctx);

/* Run borrow check on a single function. Returns error count (0 = OK). */
int borrow_check_function(borrow_ctx_t *ctx, const q_function_t *func);

/* Run borrow check on an entire module. Returns total error count. */
int borrow_check_module(borrow_ctx_t *ctx, const q_module_t *mod);

/* Run borrow check on module with inter-procedural analysis. */
int borrow_check_module_ipa(borrow_ctx_t *ctx, const q_module_t *mod);

/* Print all errors to stderr */
void borrow_print_errors(const borrow_ctx_t *ctx);

/* Get drop points (for Phase C: drop insertion) */
const drop_point_t *borrow_get_drops(const borrow_ctx_t *ctx, uint32_t *count);

/* Insert Q_FREE instructions into a function's body at computed drop points.
 * Must be called after borrow_check_function(). Modifies func->body in-place. */
int borrow_insert_drops(borrow_ctx_t *ctx, q_function_t *func);

/* Build CFG for a function (also done automatically when NLL enabled) */
int borrow_build_cfg(borrow_ctx_t *ctx, const q_function_t *func);

/* Query NLL liveness: is vreg live at instruction IP? */
bool borrow_nll_is_live(const borrow_ctx_t *ctx, uint32_t vreg, uint32_t ip);

/* Check polychromatic borrow compatibility between two borrow records */
bool borrow_colors_compatible(const borrow_record_t *a, const borrow_record_t *b);

#ifdef __cplusplus
}
#endif

#endif /* VIR_BORROW_CHECK_H */

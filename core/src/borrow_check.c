/*
 * borrow_check.c – Compile-time Borrow Checker for Q-IR
 * ======================================================
 * Runs after IR lowering, before codegen.
 *
 * 7-pass algorithm per function:
 *   Pass 1: Scan — build variable table, compute liveness (birth/death IP)
 *   Pass 2: Classify — infer ownership (Copy vs Move) from instruction types
 *   Pass 3: Track moves — detect Q_MOVE as ownership transfer
 *   Pass 4: Check borrows — validate no mutable + shared overlap
 *   Pass 5: Compute drops — determine where to insert Q_FREE
 *   Pass NLL: (optional) Build CFG → dataflow liveness → refine death_ip
 *   Pass Poly: (optional) Color borrows for field-level granularity
 */

#include "borrow_check.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>

/* ═══════════════════════════════════════════════════════
 * Internal helpers
 * ═══════════════════════════════════════════════════════ */

static void bc_error(borrow_ctx_t *ctx, const char *fmt, ...) {
    if (ctx->error_count >= BC_MAX_ERRORS) return;
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(ctx->errors[ctx->error_count], BC_ERROR_LEN, fmt, ap);
    va_end(ap);
    ctx->error_count++;
}

/* Get or create var_info for a vreg */
static var_info_t *bc_get_var(borrow_ctx_t *ctx, uint32_t vreg) {
    for (uint32_t i = 0; i < ctx->var_count; i++) {
        if (ctx->vars[i].vreg == vreg) return &ctx->vars[i];
    }
    /* New variable */
    if (ctx->var_count >= BC_MAX_VARS) return NULL;
    var_info_t *v = &ctx->vars[ctx->var_count++];
    memset(v, 0, sizeof(*v));
    v->vreg      = vreg;
    v->state     = OWN_UNINIT;
    v->birth_ip  = UINT32_MAX;
    v->death_ip  = 0;
    v->moved_at  = UINT32_MAX;
    return v;
}

/* Check if an opcode produces a heap allocation (non-copy) */
static bool is_alloc_opcode(q_opcode_t op) {
    switch (op) {
    case Q_ALLOC:
    case Q_STACK_ALLOC:
    case Q_ARR_NEW:
    case Q_MAP_NEW:
    case Q_ENTITY_NEW:
    case Q_STR_CAT:
    case Q_STR_SLICE:
    case Q_STR_UPPER:
    case Q_STR_LOWER:
    case Q_STR_REPLACE:
    case Q_STR_TRIM:
    case Q_STR_ALLOC:
    case Q_SPRINTF:
    case Q_I_TO_STR:
    case Q_F_TO_STR:
    case Q_FILE_READ:
        return true;
    default:
        return false;
    }
}

/* Check if an opcode produces a copy-type result (int/float/bool) */
static bool is_copy_result(q_opcode_t op) {
    switch (op) {
    /* Integer arithmetic → int */
    case Q_ADD: case Q_SUB: case Q_MUL: case Q_DIV: case Q_MOD:
    case Q_NEG: case Q_POW: case Q_ABS:
    case Q_AND: case Q_OR: case Q_XOR: case Q_SHL: case Q_SHR:
    case Q_NOT:
    /* Float arithmetic → float */
    case Q_FADD: case Q_FSUB: case Q_FMUL: case Q_FDIV:
    case Q_SIN: case Q_COS: case Q_TAN: case Q_SQRT:
    /* Comparison → int (0 or 1) */
    case Q_CMP_EQ: case Q_CMP_GT: case Q_CMP_LT:
    case Q_CMP_GE: case Q_CMP_LE: case Q_CMP_NE:
    case Q_STR_EQ: case Q_STR_LEN: case Q_STR_FIND:
    case Q_STR_STARTS: case Q_STR_CONTAINS:
    /* Type conversions to numeric */
    case Q_I_TO_F: case Q_F_TO_I: case Q_STR_TO_I: case Q_STR_TO_F:
    /* Array operations returning scalars */
    case Q_ARR_LEN: case Q_MAP_HAS:
    /* Immediate load */
    case Q_LOAD:
    /* System */
    case Q_ARG_COUNT: case Q_TIME:
    case Q_PERCENT:
        return true;
    default:
        return false;
    }
}

/* Record that a vreg is referenced (used) at instruction ip */
static void bc_touch(borrow_ctx_t *ctx, uint32_t vreg, uint32_t ip) {
    var_info_t *v = bc_get_var(ctx, vreg);
    if (!v) return;
    if (ip < v->birth_ip) v->birth_ip = ip;
    if (ip > v->death_ip)  v->death_ip = ip;
}

/* ═══════════════════════════════════════════════════════
 * Pass 1: Scan — build variable table + liveness
 * ═══════════════════════════════════════════════════════ */

static void scan_instruction(borrow_ctx_t *ctx, const q_instruction_t *instr, uint32_t ip) {
    /* Track dest vreg */
    if (instr->dest.type == OPERAND_VREG) {
        var_info_t *v = bc_get_var(ctx, instr->dest.vreg);
        if (v) {
            if (!v->is_alive) {
                v->birth_ip = ip;
                v->is_alive = true;
            }
            v->death_ip = ip;
        }
    }
    /* Track src1 vreg */
    if (instr->src1.type == OPERAND_VREG) {
        bc_touch(ctx, instr->src1.vreg, ip);
    }
    /* Track src2 vreg */
    if (instr->src2.type == OPERAND_VREG) {
        bc_touch(ctx, instr->src2.vreg, ip);
    }
}

/* ═══════════════════════════════════════════════════════
 * Pass 2: Classify — Copy vs Move types
 * ═══════════════════════════════════════════════════════ */

static void classify_vars(borrow_ctx_t *ctx, const q_function_t *func) {
    for (uint32_t ip = 0; ip < func->body_count; ip++) {
        const q_instruction_t *instr = &func->body[ip];
        if (instr->dest.type != OPERAND_VREG) continue;

        var_info_t *v = bc_get_var(ctx, instr->dest.vreg);
        if (!v) continue;

        if (is_copy_result(instr->opcode)) {
            v->is_copy_type = true;
            v->state = OWN_COPY;
        } else if (is_alloc_opcode(instr->opcode)) {
            v->is_alloc = true;
            v->state = OWN_OWNED;
        } else if (instr->opcode == Q_MOVE) {
            /* Move inherits the type of the source */
            if (instr->src1.type == OPERAND_VREG) {
                var_info_t *src = bc_get_var(ctx, instr->src1.vreg);
                if (src && src->is_copy_type) {
                    v->is_copy_type = true;
                    v->state = OWN_COPY;
                } else {
                    v->state = OWN_OWNED;
                }
            }
        } else if (instr->dest.type == OPERAND_VREG) {
            /* Default: if loaded from immediate or string → depends */
            if (instr->src1.type == OPERAND_IMM) {
                v->is_copy_type = true;
                v->state = OWN_COPY;
            } else if (instr->src1.type == OPERAND_STR) {
                v->state = OWN_STATIC;
            }
        }
    }
}

/* ═══════════════════════════════════════════════════════
 * Pass 3: Track moves — ownership transfer
 * ═══════════════════════════════════════════════════════ */

static void track_moves(borrow_ctx_t *ctx, const q_function_t *func) {
    /*
     * In Phase B (pre-borrow-syntax), Q_MOVE is universally used
     * for both copies and ownership transfers. We cannot distinguish
     * them without explicit borrow annotations in the source.
     *
     * Conservative strategy: only flag a Q_MOVE as ownership transfer
     * when the source vreg is NOT used again after the move (i.e., the
     * source's death_ip == this IP). This detects true last-use moves
     * without false positives on parameter copies.
     */
    for (uint32_t ip = 0; ip < func->body_count; ip++) {
        const q_instruction_t *instr = &func->body[ip];
        if (instr->opcode != Q_MOVE) continue;
        if (instr->src1.type != OPERAND_VREG) continue;
        if (instr->dest.type != OPERAND_VREG) continue;

        var_info_t *src = bc_get_var(ctx, instr->src1.vreg);
        var_info_t *dst = bc_get_var(ctx, instr->dest.vreg);
        if (!src || !dst) continue;

        /* Copy types: always copy, never move */
        if (src->is_copy_type || src->state == OWN_COPY) continue;
        /* Static: no transfer needed */
        if (src->state == OWN_STATIC) continue;

        /* Only treat as move if src is not used after this point */
        if (src->death_ip <= ip) {
            /* True last-use: ownership transfers */
            src->state    = OWN_MOVED;
            src->moved_at = ip;
            dst->state    = OWN_OWNED;
            dst->is_alloc = src->is_alloc;
        } else {
            /* Source continues to be used → treat as copy (shared) */
            dst->state      = OWN_OWNED;
            dst->is_alloc   = src->is_alloc;
        }
    }
}

/* ═══════════════════════════════════════════════════════
 * Pass 4: Check use-after-move
 * ═══════════════════════════════════════════════════════ */

static void check_use_after_move(borrow_ctx_t *ctx, const q_function_t *func) {
    for (uint32_t ip = 0; ip < func->body_count; ip++) {
        const q_instruction_t *instr = &func->body[ip];
        if (instr->opcode == Q_MOVE || instr->opcode == Q_LABEL ||
            instr->opcode == Q_NOP)
            continue;

        /* Check src1 */
        if (instr->src1.type == OPERAND_VREG) {
            var_info_t *v = bc_get_var(ctx, instr->src1.vreg);
            if (v && v->state == OWN_MOVED && ip > v->moved_at) {
                bc_error(ctx, "[%s] error: use of moved value R%u at IP %u "
                         "(moved at IP %u)",
                         ctx->func_name, v->vreg, ip, v->moved_at);
            }
        }
        /* Check src2 */
        if (instr->src2.type == OPERAND_VREG) {
            var_info_t *v = bc_get_var(ctx, instr->src2.vreg);
            if (v && v->state == OWN_MOVED && ip > v->moved_at) {
                bc_error(ctx, "[%s] error: use of moved value R%u at IP %u "
                         "(moved at IP %u)",
                         ctx->func_name, v->vreg, ip, v->moved_at);
            }
        }
    }
}

/* ═══════════════════════════════════════════════════════
 * Pass 5: Compute drop points
 * ═══════════════════════════════════════════════════════ */

static void compute_drops(borrow_ctx_t *ctx, const q_function_t *func) {
    /*
     * For each owned, non-moved, non-copy variable that allocates:
     * Insert a drop at the instruction AFTER its last use (death_ip + 1),
     * or before the Q_RET if it's still alive at end.
     *
     * ESCAPE ANALYSIS: Do NOT insert drop if the pointer escapes local scope.
     * A pointer escapes if it is:
     *   - Stored to a global (Q_STORE_GLOBAL src2)
     *   - Written into an entity field (Q_STORE_WORD dest = value)
     *   - Passed to Q_SET_FIELD (Q_SET_FIELD dest = value)
     *   - Pushed into an array (Q_ARR_PUSH src2 = value)
     */

    /* Pre-scan: build a set of vregs that escape via store-to-global/field
     * Also track Q_MOVE chains: if alloc R→MOVE→R', mark R as escaped
     * when R' escapes. Conservative: also mark any alloc that is Q_MOVE'd
     * to another register, since the destination could escape through
     * function calls or other indirect mechanisms. */
    bool escaped[BC_MAX_VARS];
    memset(escaped, 0, sizeof(escaped));

    for (uint32_t ip = 0; ip < func->body_count; ip++) {
        const q_instruction_t *instr = &func->body[ip];

        /* Q_STORE_GLOBAL: src2 = value being stored to global */
        if (instr->opcode == Q_STORE_GLOBAL && instr->src2.type == OPERAND_VREG) {
            for (uint32_t j = 0; j < ctx->var_count; j++) {
                if (ctx->vars[j].vreg == instr->src2.vreg && ctx->vars[j].is_alloc)
                    escaped[j] = true;
            }
        }
        /* Q_STORE_WORD: dest = value written into entity field */
        if (instr->opcode == Q_STORE_WORD && instr->dest.type == OPERAND_VREG) {
            for (uint32_t j = 0; j < ctx->var_count; j++) {
                if (ctx->vars[j].vreg == instr->dest.vreg && ctx->vars[j].is_alloc)
                    escaped[j] = true;
            }
        }
        /* Q_SET_FIELD: dest = value stored into entity field */
        if (instr->opcode == Q_SET_FIELD && instr->dest.type == OPERAND_VREG) {
            for (uint32_t j = 0; j < ctx->var_count; j++) {
                if (ctx->vars[j].vreg == instr->dest.vreg && ctx->vars[j].is_alloc)
                    escaped[j] = true;
            }
        }
        /* Q_ARR_PUSH: src2 = value pushed into array */
        if (instr->opcode == Q_ARR_PUSH && instr->src2.type == OPERAND_VREG) {
            for (uint32_t j = 0; j < ctx->var_count; j++) {
                if (ctx->vars[j].vreg == instr->src2.vreg && ctx->vars[j].is_alloc)
                    escaped[j] = true;
            }
        }
        /* Q_MOVE: if source is an alloc, the pointer is aliased → mark escaped.
         * This covers function argument passing (MOVE to R0..Rn) and other
         * aliasing that could lead to indirect escapes via callee stores. */
        if (instr->opcode == Q_MOVE && instr->src1.type == OPERAND_VREG) {
            for (uint32_t j = 0; j < ctx->var_count; j++) {
                if (ctx->vars[j].vreg == instr->src1.vreg && ctx->vars[j].is_alloc)
                    escaped[j] = true;
            }
        }
    }

    for (uint32_t i = 0; i < ctx->var_count; i++) {
        var_info_t *v = &ctx->vars[i];

        /* Only care about owned heap allocations not yet freed */
        if (v->is_copy_type) continue;
        if (v->state == OWN_MOVED) continue;   /* ownership transferred */
        if (v->state == OWN_STATIC) continue;
        if (v->state == OWN_UNINIT) continue;
        if (!v->is_alloc) continue;

        /* Skip escaped allocations — pointer stored to global/field/array */
        if (escaped[i]) continue;

        /* Don't drop if used in a Q_RET (returned to caller → ownership transfer) */
        if (v->death_ip < func->body_count) {
            const q_instruction_t *last = &func->body[v->death_ip];
            if (last->opcode == Q_RET) continue; /* caller takes ownership */
        }

        /* Insert drop at death_ip + 1, clamped to body_count */
        if (ctx->drop_count >= BC_MAX_DROPS) continue;
        uint32_t drop_at = v->death_ip + 1;
        if (drop_at > func->body_count) drop_at = func->body_count;

        ctx->drops[ctx->drop_count].ip   = drop_at;
        ctx->drops[ctx->drop_count].vreg = v->vreg;
        ctx->drop_count++;
    }
}

/* ═══════════════════════════════════════════════════════
 * Public API
 * ═══════════════════════════════════════════════════════ */

void borrow_ctx_init(borrow_ctx_t *ctx) {
    memset(ctx, 0, sizeof(*ctx));
}

void borrow_enable_nll(borrow_ctx_t *ctx) {
    ctx->nll_enabled = true;
}

void borrow_enable_polychrome(borrow_ctx_t *ctx) {
    ctx->polychrome_enabled = true;
}

/* Forward declarations for NLL + polychrome passes */
static void nll_build_cfg(borrow_ctx_t *ctx, const q_function_t *func);
static void nll_compute_liveness(borrow_ctx_t *ctx, const q_function_t *func);
static void nll_refine_deaths(borrow_ctx_t *ctx);
static void polychrome_classify_borrows(borrow_ctx_t *ctx, const q_function_t *func);
static void polychrome_check_conflicts(borrow_ctx_t *ctx);

int borrow_check_function(borrow_ctx_t *ctx, const q_function_t *func) {
    /* Reset per-function state, but keep module-level error count */
    int prev_errors = ctx->error_count;
    ctx->var_count    = 0;
    ctx->borrow_count = 0;
    ctx->drop_count   = 0;
    ctx->block_count  = 0;
    ctx->func_name    = func->name;

    if (func->body_count == 0) return 0;

    /* Pass 1: Scan */
    for (uint32_t ip = 0; ip < func->body_count; ip++)
        scan_instruction(ctx, &func->body[ip], ip);

    /* Pass 2: Classify */
    classify_vars(ctx, func);

    /* Pass NLL: if enabled, build CFG and refine liveness via dataflow */
    if (ctx->nll_enabled) {
        nll_build_cfg(ctx, func);
        nll_compute_liveness(ctx, func);
        nll_refine_deaths(ctx);
    }

    /* Pass 3: Track moves */
    track_moves(ctx, func);

    /* Pass 4: Check use-after-move */
    check_use_after_move(ctx, func);

    /* Pass Poly: if enabled, classify borrow colors and check conflicts */
    if (ctx->polychrome_enabled) {
        polychrome_classify_borrows(ctx, func);
        polychrome_check_conflicts(ctx);
    }

    /* Pass 5: Compute drops */
    compute_drops(ctx, func);

    return ctx->error_count - prev_errors;
}

int borrow_check_module(borrow_ctx_t *ctx, const q_module_t *mod) {
    int total = 0;
    for (uint32_t i = 0; i < mod->func_count; i++) {
        total += borrow_check_function(ctx, &mod->functions[i]);
    }
    return total;
}

void borrow_print_errors(const borrow_ctx_t *ctx) {
    for (int i = 0; i < ctx->error_count; i++) {
        fprintf(stderr, "  %s\n", ctx->errors[i]);
    }
    if (ctx->error_count > 0) {
        fprintf(stderr, "[BORROW] %d error(s)\n", ctx->error_count);
    }
}

const drop_point_t *borrow_get_drops(const borrow_ctx_t *ctx, uint32_t *count) {
    if (count) *count = ctx->drop_count;
    return ctx->drops;
}

int borrow_insert_drops(borrow_ctx_t *ctx, q_function_t *func) {
    if (ctx->drop_count == 0) return 0;

    /*
     * Insert Q_FREE instructions at computed drop points.
     * Sort drops by IP descending so insertions don't shift indices.
     */
    /* Simple bubble sort (drop_count is small, typically < 100) */
    for (uint32_t i = 0; i < ctx->drop_count; i++) {
        for (uint32_t j = i + 1; j < ctx->drop_count; j++) {
            if (ctx->drops[j].ip > ctx->drops[i].ip) {
                drop_point_t tmp = ctx->drops[i];
                ctx->drops[i] = ctx->drops[j];
                ctx->drops[j] = tmp;
            }
        }
    }

    int inserted = 0;
    for (uint32_t i = 0; i < ctx->drop_count; i++) {
        uint32_t ip   = ctx->drops[i].ip;
        uint32_t vreg = ctx->drops[i].vreg;

        /* Ensure capacity */
        if (func->body_count + 1 > func->body_capacity) {
            uint32_t new_cap = func->body_capacity == 0
                             ? 128
                             : func->body_capacity * 2;
            q_instruction_t *new_body = realloc(func->body,
                sizeof(q_instruction_t) * new_cap);
            if (!new_body) continue;
            func->body = new_body;
            func->body_capacity = new_cap;
        }

        /* Clamp IP */
        if (ip > func->body_count) ip = func->body_count;

        /* Shift instructions after ip to make room */
        if (ip < func->body_count) {
            memmove(&func->body[ip + 1], &func->body[ip],
                    sizeof(q_instruction_t) * (func->body_count - ip));
        }

        /* Create Q_FREE instruction */
        q_instruction_t free_instr;
        memset(&free_instr, 0, sizeof(free_instr));
        free_instr.opcode    = Q_FREE;
        free_instr.src1.type = OPERAND_VREG;
        free_instr.src1.vreg = vreg;
        func->body[ip] = free_instr;
        func->body_count++;
        inserted++;
    }

    return inserted;
}

/* ═══════════════════════════════════════════════════════
 * Non-Lexical Lifetimes (NLL) — CFG + Dataflow Liveness
 * ═══════════════════════════════════════════════════════
 * Instead of using lexical scope (birth_ip to death_ip from linear scan),
 * NLL builds a control flow graph and computes liveness via backward
 * dataflow analysis. A variable's lifetime ends at its last use on ANY
 * reachable path, allowing earlier drops when a branch doesn't use it.
 */

/* ── Helper: find which block an IP belongs to ────────── */
static int32_t nll_ip_to_block(const borrow_ctx_t *ctx, uint32_t ip) {
    for (uint32_t b = 0; b < ctx->block_count; b++) {
        if (ip >= ctx->blocks[b].start_ip && ip <= ctx->blocks[b].end_ip)
            return (int32_t)b;
    }
    return -1;
}

/* ── Helper: add edge from block 'from' to block 'to' ── */
static void cfg_add_edge(borrow_ctx_t *ctx, uint32_t from, uint32_t to) {
    if (from >= ctx->block_count || to >= ctx->block_count) return;
    cfg_block_t *bf = &ctx->blocks[from];
    cfg_block_t *bt = &ctx->blocks[to];
    /* Add successor */
    if (bf->succ_count < CFG_MAX_SUCCESSORS) {
        /* Check duplicate */
        for (uint32_t i = 0; i < bf->succ_count; i++)
            if (bf->succ[i] == to) return;
        bf->succ[bf->succ_count++] = to;
    }
    /* Add predecessor */
    if (bt->pred_count < CFG_MAX_SUCCESSORS) {
        for (uint32_t i = 0; i < bt->pred_count; i++)
            if (bt->pred[i] == from) return;
        bt->pred[bt->pred_count++] = from;
    }
}

/* ── Helper: resolve label → ip in function body ─────── */
static int32_t label_to_ip(const q_function_t *func, uint32_t label_id) {
    for (uint32_t ip = 0; ip < func->body_count; ip++) {
        if (func->body[ip].opcode == Q_LABEL &&
            func->body[ip].dest.type == OPERAND_LABEL &&
            func->body[ip].dest.label == label_id)
            return (int32_t)ip;
    }
    return -1;
}

/* ── Pass NLL-1: Build CFG ────────────────────────────── */
static void nll_build_cfg(borrow_ctx_t *ctx, const q_function_t *func) {
    ctx->block_count = 0;
    if (func->body_count == 0) return;

    /*
     * Phase 1: Identify block leaders (first instruction of each block).
     * Leaders are: IP 0, targets of jumps, instructions after jumps.
     */
    bool leaders[65536];
    memset(leaders, 0, sizeof(leaders));
    if (func->body_count > 65536) return; /* safety limit */
    leaders[0] = true;

    for (uint32_t ip = 0; ip < func->body_count; ip++) {
        q_opcode_t op = func->body[ip].opcode;
        if (op == Q_JUMP || op == Q_JUMP_IF || op == Q_JUMP_IF_NOT) {
            /* Target is a leader */
            uint32_t target_label = 0;
            if (func->body[ip].src1.type == OPERAND_LABEL)
                target_label = func->body[ip].src1.label;
            else if (func->body[ip].dest.type == OPERAND_LABEL)
                target_label = func->body[ip].dest.label;
            int32_t tip = label_to_ip(func, target_label);
            if (tip >= 0 && (uint32_t)tip < func->body_count)
                leaders[tip] = true;
            /* Next instruction is also a leader (fall-through) */
            if (ip + 1 < func->body_count)
                leaders[ip + 1] = true;
        } else if (op == Q_RET) {
            if (ip + 1 < func->body_count)
                leaders[ip + 1] = true;
        } else if (op == Q_LABEL) {
            leaders[ip] = true;
        }
    }

    /* Phase 2: Build blocks from leaders */
    for (uint32_t ip = 0; ip < func->body_count; ip++) {
        if (!leaders[ip]) continue;
        if (ctx->block_count >= CFG_MAX_BLOCKS) break;

        cfg_block_t *blk = &ctx->blocks[ctx->block_count];
        memset(blk, 0, sizeof(*blk));
        blk->start_ip = ip;

        /* Find end: next leader or end of function */
        uint32_t end = ip;
        for (uint32_t j = ip + 1; j < func->body_count; j++) {
            if (leaders[j]) break;
            end = j;
        }
        blk->end_ip = end;
        ctx->block_count++;
    }

    /* Phase 3: Add edges */
    for (uint32_t b = 0; b < ctx->block_count; b++) {
        uint32_t last_ip = ctx->blocks[b].end_ip;
        q_opcode_t op = func->body[last_ip].opcode;

        if (op == Q_JUMP) {
            /* Unconditional jump: single edge to target */
            uint32_t target_label = 0;
            if (func->body[last_ip].src1.type == OPERAND_LABEL)
                target_label = func->body[last_ip].src1.label;
            else if (func->body[last_ip].dest.type == OPERAND_LABEL)
                target_label = func->body[last_ip].dest.label;
            int32_t tip = label_to_ip(func, target_label);
            if (tip >= 0) {
                int32_t tb = nll_ip_to_block(ctx, (uint32_t)tip);
                if (tb >= 0) cfg_add_edge(ctx, b, (uint32_t)tb);
            }
        } else if (op == Q_JUMP_IF || op == Q_JUMP_IF_NOT) {
            /* Conditional: edge to target + fall-through */
            uint32_t target_label = 0;
            if (func->body[last_ip].src1.type == OPERAND_LABEL)
                target_label = func->body[last_ip].src1.label;
            else if (func->body[last_ip].dest.type == OPERAND_LABEL)
                target_label = func->body[last_ip].dest.label;
            int32_t tip = label_to_ip(func, target_label);
            if (tip >= 0) {
                int32_t tb = nll_ip_to_block(ctx, (uint32_t)tip);
                if (tb >= 0) cfg_add_edge(ctx, b, (uint32_t)tb);
            }
            /* Fall-through to next block */
            if (b + 1 < ctx->block_count)
                cfg_add_edge(ctx, b, b + 1);
        } else if (op == Q_RET) {
            /* No outgoing edges — function exit */
        } else {
            /* Default: fall through to next block */
            if (b + 1 < ctx->block_count)
                cfg_add_edge(ctx, b, b + 1);
        }
    }
}

/* ── Bit helpers for liveness bitsets ─────────────────── */
static inline void bv_set(uint64_t *bv, uint32_t bit) {
    bv[bit >> 6] |= (1ULL << (bit & 63));
}
static inline bool bv_test(const uint64_t *bv, uint32_t bit) {
    return (bv[bit >> 6] & (1ULL << (bit & 63))) != 0;
}
static inline bool bv_equal(const uint64_t *a, const uint64_t *b, uint32_t words) {
    for (uint32_t i = 0; i < words; i++)
        if (a[i] != b[i]) return false;
    return true;
}
static inline void bv_or(uint64_t *dst, const uint64_t *src, uint32_t words) {
    for (uint32_t i = 0; i < words; i++)
        dst[i] |= src[i];
}

/* ── Pass NLL-2: Backward dataflow liveness analysis ── */
static void nll_compute_liveness(borrow_ctx_t *ctx, const q_function_t *func) {
    if (ctx->block_count == 0) return;

    /* How many uint64 words do we need? 1 bit per var_count entry. */
    uint32_t nwords = (ctx->var_count + 63) / 64;
    if (nwords > 64) nwords = 64; /* capped by bitset size */

    /* Build per-block USE and DEF sets */
    uint64_t use_sets[CFG_MAX_BLOCKS][64];
    uint64_t def_sets[CFG_MAX_BLOCKS][64];
    memset(use_sets, 0, sizeof(use_sets));
    memset(def_sets, 0, sizeof(def_sets));

    /* Map vreg → var index for bitset operations */
    for (uint32_t b = 0; b < ctx->block_count; b++) {
        for (uint32_t ip = ctx->blocks[b].start_ip;
             ip <= ctx->blocks[b].end_ip && ip < func->body_count; ip++) {
            const q_instruction_t *ins = &func->body[ip];

            /* Uses: src1, src2 vregs */
            if (ins->src1.type == OPERAND_VREG) {
                uint32_t vi = UINT32_MAX;
                for (uint32_t k = 0; k < ctx->var_count; k++)
                    if (ctx->vars[k].vreg == ins->src1.vreg) { vi = k; break; }
                if (vi < ctx->var_count && !bv_test(def_sets[b], vi))
                    bv_set(use_sets[b], vi);
            }
            if (ins->src2.type == OPERAND_VREG) {
                uint32_t vi = UINT32_MAX;
                for (uint32_t k = 0; k < ctx->var_count; k++)
                    if (ctx->vars[k].vreg == ins->src2.vreg) { vi = k; break; }
                if (vi < ctx->var_count && !bv_test(def_sets[b], vi))
                    bv_set(use_sets[b], vi);
            }

            /* Defs: dest vreg */
            if (ins->dest.type == OPERAND_VREG) {
                uint32_t vi = UINT32_MAX;
                for (uint32_t k = 0; k < ctx->var_count; k++)
                    if (ctx->vars[k].vreg == ins->dest.vreg) { vi = k; break; }
                if (vi < ctx->var_count)
                    bv_set(def_sets[b], vi);
            }
        }
    }

    /* Initialize live_in / live_out to zero (already done by memset in block_count=0 reset) */
    for (uint32_t b = 0; b < ctx->block_count; b++) {
        memset(ctx->blocks[b].live_in, 0, sizeof(ctx->blocks[b].live_in));
        memset(ctx->blocks[b].live_out, 0, sizeof(ctx->blocks[b].live_out));
    }

    /*
     * Iterative backward dataflow:
     *   live_out[B] = ∪ live_in[S]  for each successor S of B
     *   live_in[B]  = use[B] ∪ (live_out[B] − def[B])
     * Repeat until fixpoint.
     */
    bool changed = true;
    int max_iters = 100;
    while (changed && max_iters-- > 0) {
        changed = false;
        /* Process blocks in reverse order for faster convergence */
        for (int32_t bi = (int32_t)ctx->block_count - 1; bi >= 0; bi--) {
            uint32_t b = (uint32_t)bi;
            cfg_block_t *blk = &ctx->blocks[b];

            /* Save old live_in */
            uint64_t old_in[64];
            memcpy(old_in, blk->live_in, nwords * sizeof(uint64_t));

            /* live_out = union of successors' live_in */
            memset(blk->live_out, 0, nwords * sizeof(uint64_t));
            for (uint32_t si = 0; si < blk->succ_count; si++) {
                bv_or(blk->live_out, ctx->blocks[blk->succ[si]].live_in, nwords);
            }

            /* live_in = use ∪ (live_out − def) */
            for (uint32_t w = 0; w < nwords; w++) {
                blk->live_in[w] = use_sets[b][w] |
                                   (blk->live_out[w] & ~def_sets[b][w]);
            }

            if (!bv_equal(old_in, blk->live_in, nwords))
                changed = true;
        }
    }
}

/* ── Pass NLL-3: Refine death_ip using CFG liveness ─── */
static void nll_refine_deaths(borrow_ctx_t *ctx) {
    /*
     * For each variable, walk backwards from the end of the function.
     * The true death is the latest IP in any block where the variable
     * is in live_out, or the latest IP where it is used.
     * The key insight: if a variable is NOT in live_out of a block,
     * it dies before the end of that block.
     */
    for (uint32_t vi = 0; vi < ctx->var_count; vi++) {
        var_info_t *v = &ctx->vars[vi];
        uint32_t nll_death = v->birth_ip; /* at minimum, lives to birth */

        for (uint32_t b = 0; b < ctx->block_count; b++) {
            /* If variable is live at block exit, it's alive through end_ip */
            if (bv_test(ctx->blocks[b].live_out, vi)) {
                if (ctx->blocks[b].end_ip > nll_death)
                    nll_death = ctx->blocks[b].end_ip;
            }
            /* If variable is live at block entry, check for uses within */
            if (bv_test(ctx->blocks[b].live_in, vi)) {
                if (ctx->blocks[b].end_ip > nll_death)
                    nll_death = ctx->blocks[b].end_ip;
            }
        }

        /* NLL death should not exceed the linear scan death
         * (it can only improve — make it earlier, not later) */
        if (nll_death < v->death_ip) {
            v->death_ip = nll_death;
        }
    }
}

/* Public API: build CFG for debugging/inspection */
int borrow_build_cfg(borrow_ctx_t *ctx, const q_function_t *func) {
    nll_build_cfg(ctx, func);
    return (int)ctx->block_count;
}

/* Query NLL liveness at a specific IP */
bool borrow_nll_is_live(const borrow_ctx_t *ctx, uint32_t vreg, uint32_t ip) {
    if (!ctx->nll_enabled || ctx->block_count == 0) return false;
    /* Find var index */
    uint32_t vi = UINT32_MAX;
    for (uint32_t k = 0; k < ctx->var_count; k++)
        if (ctx->vars[k].vreg == vreg) { vi = k; break; }
    if (vi >= ctx->var_count) return false;

    int32_t b = nll_ip_to_block(ctx, ip);
    if (b < 0) return false;

    /* Variable is live at this IP if it's in live_in of the block
     * and hasn't been defined before this IP in the same block,
     * OR if it's used at or after this IP in the block. */
    if (bv_test(ctx->blocks[b].live_in, vi)) return true;
    if (bv_test(ctx->blocks[b].live_out, vi)) return true;
    return false;
}

/* ═══════════════════════════════════════════════════════
 * Polychromatic Borrowing
 * ═══════════════════════════════════════════════════════
 * Colors each borrow with READ / WRITE / PARTIAL / CONTAINER
 * based on how the borrowed value is actually used.
 * Two borrows of the same owner are compatible if:
 *   - Both are READ (multiple shared readers OK)
 *   - Both are PARTIAL on different fields (disjoint access)
 *   - One is CONTAINER and the other is PARTIAL on an element
 * Two borrows CONFLICT if:
 *   - One is WRITE and the other is WRITE (or READ of same field)
 *   - Both are whole-object and one is WRITE
 */

static void polychrome_classify_borrows(borrow_ctx_t *ctx, const q_function_t *func) {
    /*
     * Walk the function body. For each borrow (Q_MOVE or future BORROW opcode),
     * track how the borrower vreg is subsequently used:
     *   - Only LOAD_WORD / ARR_GET / MAP_GET → READ
     *   - Any STORE_WORD / ARR_SET / MAP_SET → WRITE
     *   - Field access with specific offset → PARTIAL + field index
     *   - Used as container in ARR_PUSH etc → CONTAINER
     */
    for (uint32_t bi = 0; bi < ctx->borrow_count; bi++) {
        borrow_record_t *br = &ctx->borrows[bi];
        uint32_t colors = 0;
        bool saw_write = false;
        bool saw_field = false;
        int32_t first_field = -1;

        for (uint32_t ip = br->start_ip; ip <= br->end_ip && ip < func->body_count; ip++) {
            const q_instruction_t *ins = &func->body[ip];

            /* Check if this instruction references the borrower */
            bool uses_borrower = false;
            if (ins->src1.type == OPERAND_VREG && ins->src1.vreg == br->borrower_vreg)
                uses_borrower = true;
            if (ins->src2.type == OPERAND_VREG && ins->src2.vreg == br->borrower_vreg)
                uses_borrower = true;
            if (!uses_borrower) continue;

            switch (ins->opcode) {
            case Q_LOAD_WORD:
                colors |= BORROW_READ;
                /* If src2 is an immediate offset, it's a field access */
                if (ins->src2.type == OPERAND_IMM) {
                    colors |= BORROW_PARTIAL;
                    if (!saw_field) { first_field = (int32_t)ins->src2.imm; saw_field = true; }
                }
                break;
            case Q_STORE_WORD:
                colors |= BORROW_WRITE;
                saw_write = true;
                if (ins->src2.type == OPERAND_IMM) {
                    colors |= BORROW_PARTIAL;
                    if (!saw_field) { first_field = (int32_t)ins->src2.imm; saw_field = true; }
                }
                break;
            case Q_ARR_GET: case Q_MAP_GET: case Q_STR_GET:
                colors |= BORROW_READ;
                break;
            case Q_ARR_SET: case Q_MAP_SET:
                colors |= BORROW_WRITE;
                saw_write = true;
                break;
            case Q_ARR_PUSH: case Q_ARR_POP:
                colors |= BORROW_WRITE | BORROW_CONTAINER;
                saw_write = true;
                break;
            default:
                /* Generic use: assume read */
                colors |= BORROW_READ;
                break;
            }
        }

        if (colors == 0) colors = BORROW_READ;
        br->color = colors;
        br->is_mutable = saw_write;
        br->field_index = first_field;
    }
}

bool borrow_colors_compatible(const borrow_record_t *a, const borrow_record_t *b) {
    /* Different owners are always compatible */
    if (a->owner_vreg != b->owner_vreg) return true;

    /* Check temporal overlap: if borrows don't overlap in time, compatible */
    if (a->end_ip < b->start_ip || b->end_ip < a->start_ip) return true;

    /* Both READ-only → always compatible */
    if (!(a->color & BORROW_WRITE) && !(b->color & BORROW_WRITE))
        return true;

    /* Both PARTIAL on different fields → compatible (disjoint access) */
    if ((a->color & BORROW_PARTIAL) && (b->color & BORROW_PARTIAL) &&
        a->field_index >= 0 && b->field_index >= 0 &&
        a->field_index != b->field_index)
        return true;

    /* CONTAINER + PARTIAL element → compatible (structure vs element) */
    if ((a->color & BORROW_CONTAINER) && (b->color & BORROW_PARTIAL) &&
        !(a->color & BORROW_WRITE))
        return true;
    if ((b->color & BORROW_CONTAINER) && (a->color & BORROW_PARTIAL) &&
        !(b->color & BORROW_WRITE))
        return true;

    /* Otherwise: conflict */
    return false;
}

static void polychrome_check_conflicts(borrow_ctx_t *ctx) {
    for (uint32_t i = 0; i < ctx->borrow_count; i++) {
        for (uint32_t j = i + 1; j < ctx->borrow_count; j++) {
            if (!borrow_colors_compatible(&ctx->borrows[i], &ctx->borrows[j])) {
                borrow_record_t *a = &ctx->borrows[i];
                borrow_record_t *b = &ctx->borrows[j];
                bc_error(ctx,
                    "[%s] borrow conflict: R%u (%s%s, field=%d) and R%u "
                    "(%s%s, field=%d) both borrow R%u at IP %u-%u / %u-%u",
                    ctx->func_name,
                    a->borrower_vreg,
                    (a->color & BORROW_WRITE) ? "write" : "read",
                    (a->color & BORROW_PARTIAL) ? ",partial" : "",
                    a->field_index,
                    b->borrower_vreg,
                    (b->color & BORROW_WRITE) ? "write" : "read",
                    (b->color & BORROW_PARTIAL) ? ",partial" : "",
                    b->field_index,
                    a->owner_vreg,
                    a->start_ip, a->end_ip, b->start_ip, b->end_ip);
            }
        }
    }
}

/* ═══════════════════════════════════════════════════════
 * Inter-procedural Analysis (IPA)
 * ═══════════════════════════════════════════════════════
 * Builds per-function summaries describing which output lifetimes
 * depend on which input parameters. Then uses these summaries
 * when checking call sites.
 *
 * Strategy:
 *   Phase 1: For each function, build an ipa_func_summary_t:
 *     - Which params are borrows?
 *     - Does the return value's lifetime depend on a specific param?
 *   Phase 2: When checking a call site, propagate the callee's
 *     summary to the caller's borrow context.
 */

/* Build IPA summary for a single function */
static void ipa_build_summary(ipa_func_summary_t *sum, const q_function_t *func,
                               const borrow_ctx_t *func_ctx) {
    (void)func_ctx; /* used for additional context in future phases */
    memset(sum, 0, sizeof(*sum));
    strncpy(sum->name, func->name, sizeof(sum->name) - 1);
    sum->param_count = func->param_count;
    sum->return_depends_on = -1;
    sum->return_is_borrow = false;

    /* Classify params: if a param vreg is only used in LOAD_WORD (read) operations
     * and never stored to, treat it as a borrow param */
    for (uint32_t pi = 0; pi < func->param_count && pi < IPA_MAX_PARAMS; pi++) {
        uint32_t pvreg = func->param_vregs[pi];
        bool only_read = true;
        bool has_use = false;

        for (uint32_t ip = 0; ip < func->body_count; ip++) {
            const q_instruction_t *ins = &func->body[ip];
            /* Check if param is used as a store target (mutated) */
            if (ins->opcode == Q_STORE_WORD || ins->opcode == Q_ARR_SET ||
                ins->opcode == Q_MAP_SET) {
                if (ins->src1.type == OPERAND_VREG && ins->src1.vreg == pvreg) {
                    only_read = false;
                }
            }
            /* Check if param is used at all */
            if ((ins->src1.type == OPERAND_VREG && ins->src1.vreg == pvreg) ||
                (ins->src2.type == OPERAND_VREG && ins->src2.vreg == pvreg)) {
                has_use = true;
            }
        }
        sum->params[pi].is_borrowed = has_use && only_read;
        sum->params[pi].is_mut = has_use && !only_read;
    }

    /* Check return: find Q_RET instructions and see what vreg is returned */
    for (uint32_t ip = 0; ip < func->body_count; ip++) {
        if (func->body[ip].opcode != Q_RET) continue;
        if (func->body[ip].src1.type != OPERAND_VREG) continue;
        uint32_t ret_vreg = func->body[ip].src1.vreg;

        /* Trace back: does ret_vreg come from a param? */
        for (uint32_t pi = 0; pi < func->param_count && pi < IPA_MAX_PARAMS; pi++) {
            uint32_t pvreg = func->param_vregs[pi];
            /* Direct return of param */
            if (ret_vreg == pvreg) {
                sum->return_depends_on = (int32_t)pi;
                sum->return_is_borrow = true;
                break;
            }
            /* Check if ret_vreg was assigned from a Q_MOVE of param */
            for (uint32_t bip = 0; bip < ip; bip++) {
                const q_instruction_t *bi = &func->body[bip];
                if (bi->opcode == Q_MOVE &&
                    bi->dest.type == OPERAND_VREG && bi->dest.vreg == ret_vreg &&
                    bi->src1.type == OPERAND_VREG && bi->src1.vreg == pvreg) {
                    sum->return_depends_on = (int32_t)pi;
                    sum->return_is_borrow = true;
                    break;
                }
            }
            if (sum->return_depends_on >= 0) break;
        }
        break; /* Only check first RET */
    }
}

/* Check call sites against IPA summaries */
static void ipa_check_call_sites(borrow_ctx_t *ctx, const q_function_t *func,
                                  const q_module_t *mod) {
    if (!ctx->ipa_table || ctx->ipa_count == 0) return;

    for (uint32_t ip = 0; ip < func->body_count; ip++) {
        const q_instruction_t *ins = &func->body[ip];
        if (ins->opcode != Q_CALL_FUNC) continue;
        if (ins->src1.type != OPERAND_FUNC_IDX) continue;

        uint32_t callee_idx = ins->src1.func_idx;
        if (callee_idx >= mod->func_count) continue;
        const q_function_t *callee = &mod->functions[callee_idx];

        /* Find callee's IPA summary */
        const ipa_func_summary_t *sum = NULL;
        for (uint32_t si = 0; si < ctx->ipa_count; si++) {
            if (strncmp(ctx->ipa_table[si].name, callee->name, 64) == 0) {
                sum = &ctx->ipa_table[si];
                break;
            }
        }
        if (!sum) continue;

        /* If callee returns a borrow depending on param N, then the return
         * value's lifetime at the call site must not exceed the argument's
         * lifetime that was passed as param N. */
        if (sum->return_is_borrow && sum->return_depends_on >= 0 &&
            ins->dest.type == OPERAND_VREG) {
            uint32_t ret_vreg = ins->dest.vreg;
            /* The argument at position sum->return_depends_on was in
             * R0..R(n-1) before the call. Find its var_info. */
            uint32_t arg_param = (uint32_t)sum->return_depends_on;
            if (arg_param < func->body_count) {
                /* Walk back to find what was in R(arg_param) before this call */
                /* This is a simplified heuristic — look for the last assignment
                 * to R(arg_param) before ip */
                uint32_t arg_vreg = arg_param; /* simplified: R0, R1, R2... */
                var_info_t *arg_var = NULL, *ret_var = NULL;
                for (uint32_t vi = 0; vi < ctx->var_count; vi++) {
                    if (ctx->vars[vi].vreg == arg_vreg) arg_var = &ctx->vars[vi];
                    if (ctx->vars[vi].vreg == ret_vreg) ret_var = &ctx->vars[vi];
                }

                if (arg_var && ret_var && ret_var->death_ip > arg_var->death_ip) {
                    bc_error(ctx,
                        "[%s] IPA: return value R%u from %s() outlives "
                        "argument R%u (param %d) — borrow would dangle "
                        "(ret dies at IP %u, arg dies at IP %u)",
                        ctx->func_name, ret_vreg, callee->name,
                        arg_vreg, sum->return_depends_on,
                        ret_var->death_ip, arg_var->death_ip);
                }
            }
        }

        /* Check: if callee takes &mut param, caller must not have other borrows
         * of that argument alive during the call */
        for (uint32_t pi = 0; pi < sum->param_count && pi < IPA_MAX_PARAMS; pi++) {
            if (!sum->params[pi].is_mut) continue;
            uint32_t arg_vreg = pi; /* simplified */
            for (uint32_t bi = 0; bi < ctx->borrow_count; bi++) {
                borrow_record_t *br = &ctx->borrows[bi];
                if (br->owner_vreg == arg_vreg &&
                    br->start_ip <= ip && br->end_ip >= ip) {
                    bc_error(ctx,
                        "[%s] IPA: calling %s() which takes &mut param %d, "
                        "but R%u still has active borrow by R%u (IP %u-%u)",
                        ctx->func_name, callee->name, pi,
                        arg_vreg, br->borrower_vreg,
                        br->start_ip, br->end_ip);
                }
            }
        }
    }
}

int borrow_check_module_ipa(borrow_ctx_t *ctx, const q_module_t *mod) {
    /* Phase 1: Build IPA summaries for all functions */
    ipa_func_summary_t *table = NULL;
    uint32_t ipa_count = 0;

    if (mod->func_count > 0) {
        table = (ipa_func_summary_t *)calloc(mod->func_count, sizeof(ipa_func_summary_t));
        if (table) {
            for (uint32_t fi = 0; fi < mod->func_count; fi++) {
                /* Run a quick scan to get func_ctx for summary building */
                borrow_ctx_t tmp;
                borrow_ctx_init(&tmp);
                if (mod->functions[fi].body_count > 0) {
                    for (uint32_t ip = 0; ip < mod->functions[fi].body_count; ip++)
                        scan_instruction(&tmp, &mod->functions[fi].body[ip], ip);
                    classify_vars(&tmp, &mod->functions[fi]);
                }
                ipa_build_summary(&table[fi], &mod->functions[fi], &tmp);
            }
            ipa_count = mod->func_count;
        }
    }

    /* Phase 2: Run normal borrow check + IPA cross-check */
    ctx->ipa_table = table;
    ctx->ipa_count = ipa_count;

    int total = 0;
    for (uint32_t fi = 0; fi < mod->func_count; fi++) {
        total += borrow_check_function(ctx, &mod->functions[fi]);
        /* IPA call-site check */
        ipa_check_call_sites(ctx, &mod->functions[fi], mod);
    }

    ctx->ipa_table = NULL;
    ctx->ipa_count = 0;
    free(table);

    return total + ctx->error_count;
}

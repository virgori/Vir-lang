#ifndef VIR_LIR_ANALYSIS_H
#define VIR_LIR_ANALYSIS_H

#include "lir.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* --------------------------------------------------------------------------
 * LIR Liveness Analysis
 * -------------------------------------------------------------------------- */

// Max number of virtual registers we track (simplified for now)
#define LIR_MAX_VREGS 1024
#define LIR_BITSET_WORDS ((LIR_MAX_VREGS + 31) / 32)

typedef struct {
    uint32_t bits[LIR_BITSET_WORDS];
} lir_bitset_t;

void lir_bitset_set(lir_bitset_t *bs, uint32_t vreg);
void lir_bitset_clear(lir_bitset_t *bs, uint32_t vreg);
bool lir_bitset_test(const lir_bitset_t *bs, uint32_t vreg);
bool lir_bitset_union(lir_bitset_t *dst, const lir_bitset_t *src); // returns true if changed
void lir_bitset_clear_all(lir_bitset_t *bs);

typedef struct {
    uint32_t block_id;
    lir_bitset_t live_in;
    lir_bitset_t live_out;
    lir_bitset_t use;  // registers read before being written in this block
    lir_bitset_t def;  // registers written in this block
} lir_liveness_block_t;

typedef struct {
    lir_func_t *func;
    lir_liveness_block_t *blocks; // Array parallel to func->blocks
    uint32_t block_count;
} lir_liveness_t;

lir_liveness_t* lir_analyze_liveness(lir_func_t *func);
void lir_free_liveness(lir_liveness_t *liveness);

/* --------------------------------------------------------------------------
 * Live Interval Analysis
 * -------------------------------------------------------------------------- */

typedef struct {
    uint32_t vreg;
    uint32_t start_instr; // Sequential ID of instruction where interval begins
    uint32_t end_instr;   // Sequential ID of instruction where interval ends
    uint32_t phys_reg;    // Allocated physical register
    int32_t stack_offset; // Spilled stack offset (if any)
    bool is_live;         // True if this interval is active
} lir_live_interval_t;

typedef struct {
    lir_func_t *func;
    lir_liveness_t *liveness;
    lir_live_interval_t *intervals; // Array indexed by vreg
    uint32_t max_vreg;
} lir_interval_ctx_t;

lir_interval_ctx_t* lir_analyze_intervals(lir_func_t *func, lir_liveness_t *liveness);
void lir_free_intervals(lir_interval_ctx_t *ctx);

#ifdef __cplusplus
}
#endif

#endif // VIR_LIR_ANALYSIS_H

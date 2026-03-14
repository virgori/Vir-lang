/*
 * ptx_gen.h – Q-IR → PTX Text Emitter
 * =====================================
 * Generates NVIDIA PTX assembly from Q-IR instructions.
 * The PTX text can then be JIT-compiled via gpu_cuda.c (cuModuleLoadDataEx).
 */

#ifndef VIR_PTX_GEN_H
#define VIR_PTX_GEN_H

#include "q_ir.h"
#include <stddef.h>
#include <stdint.h>

/* ═══════════════════════════════════════════════════════
 * Constants
 * ═══════════════════════════════════════════════════════ */

#define PTX_MAX_REGS    64
#define PTX_MAX_PARAMS  16
#define PTX_MAX_LABELS  256
#define PTX_BUF_INIT    4096

/* ═══════════════════════════════════════════════════════
 * PTX Register Bank
 * ═══════════════════════════════════════════════════════ */

typedef enum {
    PTX_REG_PRED,   /* %p<N>  — predicate  */
    PTX_REG_B16,    /* %h<N>  — half       */
    PTX_REG_B32,    /* %r<N>  — 32-bit     */
    PTX_REG_B64,    /* %rd<N> — 64-bit     */
    PTX_REG_F32,    /* %f<N>  — float      */
    PTX_REG_F64,    /* %fd<N> — double     */
} ptx_reg_type_t;

/* ═══════════════════════════════════════════════════════
 * PTX Kernel Descriptor
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    const char *name;         /* kernel entry point name */
    int  num_params;          /* number of .param entries */
    int  param_sizes[PTX_MAX_PARAMS]; /* bytes per param */
    int  shared_mem_bytes;    /* static shared memory */
    int  target_sm;           /* e.g. 70, 80, 90 */
} ptx_kernel_desc_t;

/* ═══════════════════════════════════════════════════════
 * PTX Text Buffer (growable)
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    char  *data;
    size_t len;
    size_t cap;
    /* Register allocation counters */
    int    next_pred;
    int    next_r32;
    int    next_r64;
    int    next_f32;
    int    next_f64;
    /* Label counter */
    int    next_label;
} ptx_buf_t;

/* ═══════════════════════════════════════════════════════
 * API
 * ═══════════════════════════════════════════════════════ */

/* Initialize a PTX buffer. */
void  ptx_buf_init(ptx_buf_t *pb);

/* Free a PTX buffer. */
void  ptx_buf_free(ptx_buf_t *pb);

/* Emit preamble (.version, .target, .address_size). */
void  ptx_emit_preamble(ptx_buf_t *pb, int target_sm);

/* Begin a kernel entry. */
void  ptx_emit_kernel_begin(ptx_buf_t *pb, const ptx_kernel_desc_t *desc);

/* Emit register declarations based on current alloc counters. */
void  ptx_emit_reg_decls(ptx_buf_t *pb);

/* End a kernel entry. */
void  ptx_emit_kernel_end(ptx_buf_t *pb);

/* ── Q-IR → PTX lowering ── */

/* Emit thread index computation: tid = blockIdx*blockDim + threadIdx */
int   ptx_emit_thread_index(ptx_buf_t *pb, const char *dim);

/* Emit a boundary check: @!p bra $label if tid >= N */
int   ptx_emit_bounds_check(ptx_buf_t *pb, int tid_reg, int n_reg,
                            int exit_label);

/* Lower a block of Q-IR instructions to PTX. */
int   ptx_lower_block(ptx_buf_t *pb, const q_instruction_t *instrs,
                      int count, const ptx_kernel_desc_t *desc);

/* Allocate a new virtual register. Returns register number. */
int   ptx_alloc_reg(ptx_buf_t *pb, ptx_reg_type_t type);

/* Allocate a new label. Returns label number. */
int   ptx_alloc_label(ptx_buf_t *pb);

/* ── Convenience: full kernel generation ── */

/* Generate complete PTX for a Q-IR function destined for GPU.
 * Returns malloc'd null-terminated PTX string, caller must free.
 * Returns NULL on error. */
char *ptx_generate_kernel(const q_instruction_t *instrs, int count,
                          const ptx_kernel_desc_t *desc);

#endif /* VIR_PTX_GEN_H */

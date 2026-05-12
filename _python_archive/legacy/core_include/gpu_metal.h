/* ═══════════════════════════════════════════════════════════════════
 * gpu_metal.h — Apple Metal GPU Backend (D3)
 * ═══════════════════════════════════════════════════════════════════
 * Zero-dependency Metal runtime via Objective-C runtime + dlopen.
 * Works without Metal SDK headers at compile time.
 *
 * Architecture:
 *   1. dlopen("Metal.framework") + objc_msgSend for all Metal calls
 *   2. Q-IR → MSL (Metal Shading Language) text emitter
 *   3. Runtime compile MSL → MTLLibrary → MTLComputePipelineState
 *   4. Launch compute kernels via command buffer / encoder
 *
 * Platform: macOS 10.13+ / iOS 11+ (Apple GPU only)
 * ═══════════════════════════════════════════════════════════════════ */

#ifndef VIR_GPU_METAL_H
#define VIR_GPU_METAL_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include "q_ir.h"

/* ── Opaque Metal object handles ─────────────────────── */
typedef void* MTLDevice_h;
typedef void* MTLCommandQueue_h;
typedef void* MTLCommandBuffer_h;
typedef void* MTLComputeCommandEncoder_h;
typedef void* MTLComputePipelineState_h;
typedef void* MTLLibrary_h;
typedef void* MTLFunction_h;
typedef void* MTLBuffer_h;

/* ── Device info ─────────────────────────────────────── */
typedef struct {
    char        name[128];
    uint64_t    recommended_max_working_set_size;
    uint32_t    max_threads_per_threadgroup;
    uint32_t    max_threadgroup_memory_length;
    bool        supports_family_apple7;    /* M1+ */
    bool        supports_family_apple8;    /* M2+ */
    bool        supports_family_apple9;    /* M3+ */
    bool        is_low_power;
    bool        is_headless;
} vir_metal_device_info_t;

/* ── Launch config ───────────────────────────────────── */
typedef struct {
    uint32_t    grid_x, grid_y, grid_z;
    uint32_t    threadgroup_x, threadgroup_y, threadgroup_z;
} vir_metal_launch_config_t;

/* ── MSL kernel descriptor ───────────────────────────── */
#define VIR_METAL_MAX_PARAMS 16

typedef struct {
    const char *name;
    int         num_params;
    int         param_sizes[VIR_METAL_MAX_PARAMS];
    int         shared_mem_bytes;
} vir_msl_kernel_desc_t;

/* ═══════════════════════════════════════════════════════
 * API — Metal Device Management
 * ═══════════════════════════════════════════════════════ */

int  vir_metal_init(void);
void vir_metal_shutdown(void);
bool vir_metal_available(void);

int  vir_metal_device_info(vir_metal_device_info_t *info);

/* ═══════════════════════════════════════════════════════
 * API — Shader Compilation
 * ═══════════════════════════════════════════════════════ */

/* Compile MSL source string → MTLLibrary */
MTLLibrary_h vir_metal_compile_msl(const char *msl_source, size_t len);
void         vir_metal_release_library(MTLLibrary_h lib);

/* Get kernel function from library */
MTLFunction_h vir_metal_get_function(MTLLibrary_h lib, const char *name);
void          vir_metal_release_function(MTLFunction_h func);

/* Create compute pipeline from function */
MTLComputePipelineState_h vir_metal_create_pipeline(MTLFunction_h func);
void                      vir_metal_release_pipeline(MTLComputePipelineState_h pso);

/* ═══════════════════════════════════════════════════════
 * API — Buffer Management
 * ═══════════════════════════════════════════════════════ */

MTLBuffer_h vir_metal_buffer_create(size_t size);
MTLBuffer_h vir_metal_buffer_create_with_data(const void *data, size_t size);
void       *vir_metal_buffer_contents(MTLBuffer_h buf);
void        vir_metal_buffer_release(MTLBuffer_h buf);

/* ═══════════════════════════════════════════════════════
 * API — Compute Dispatch
 * ═══════════════════════════════════════════════════════ */

int  vir_metal_dispatch(MTLComputePipelineState_h pso,
                        MTLBuffer_h *buffers, int num_buffers,
                        const vir_metal_launch_config_t *config);
int  vir_metal_sync(void);

/* ═══════════════════════════════════════════════════════
 * API — Q-IR → MSL Emitter
 * ═══════════════════════════════════════════════════════ */

/* Emit MSL compute kernel from Q-IR instruction block */
int  vir_msl_generate_kernel(const vir_msl_kernel_desc_t *desc,
                             const q_instruction_t *instrs, int count,
                             char *out_buf, size_t out_cap);

#endif /* VIR_GPU_METAL_H */

/*
 * gpu_cuda.h – CUDA Driver API FFI (Zero-Dependency)
 * ====================================================
 * Loads libcuda.so/nvcuda.dll at runtime via dlopen/dlsym.
 * No compile-time linkage to CUDA SDK required.
 *
 * Wraps the essential CUDA Driver API functions for:
 *   - Device enumeration and context management
 *   - Module loading (PTX JIT compilation)
 *   - Kernel launch
 *   - Memory allocation and transfer
 *   - Stream management
 */

#ifndef VIR_GPU_CUDA_H
#define VIR_GPU_CUDA_H

#include <stdint.h>
#include <stddef.h>

/* ═══════════════════════════════════════════════════════
 * CUDA Type Aliases (matches CUDA Driver API)
 * ═══════════════════════════════════════════════════════ */

typedef int          CUresult;
typedef void        *CUdevice;
typedef void        *CUcontext;
typedef void        *CUmodule;
typedef void        *CUfunction;
typedef void        *CUstream;
typedef uint64_t     CUdeviceptr;

#define CUDA_SUCCESS 0

/* ═══════════════════════════════════════════════════════
 * GPU Device Info
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    int   ordinal;
    char  name[256];
    int   compute_major;
    int   compute_minor;
    int64_t total_mem;
    int   sm_count;
    int   max_threads_per_block;
    int   max_shared_mem_per_block;
    int   warp_size;
} vir_gpu_device_info_t;

/* ═══════════════════════════════════════════════════════
 * Kernel Launch Config
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    unsigned int grid_x, grid_y, grid_z;
    unsigned int block_x, block_y, block_z;
    unsigned int shared_mem_bytes;
    CUstream     stream;      /* NULL = default stream */
} vir_gpu_launch_config_t;

/* ═══════════════════════════════════════════════════════
 * Public API
 * ═══════════════════════════════════════════════════════ */

/* Initialize CUDA subsystem (dlopen libcuda).
 * Returns 0 on success, -1 if CUDA not available. */
int  vir_gpu_cuda_init(void);

/* Shutdown CUDA and unload library. */
void vir_gpu_cuda_shutdown(void);

/* Check if CUDA is available (after init). */
int  vir_gpu_cuda_available(void);

/* Get number of CUDA devices. */
int  vir_gpu_cuda_device_count(void);

/* Get device info. */
int  vir_gpu_cuda_device_info(int ordinal, vir_gpu_device_info_t *info);

/* Create a CUDA context on device. */
int  vir_gpu_cuda_create_context(int device_ordinal);

/* Destroy current context. */
void vir_gpu_cuda_destroy_context(void);

/* Load PTX source and JIT-compile a module.
 * Returns 0 on success. */
int  vir_gpu_cuda_load_ptx(const char *ptx_source, size_t ptx_len,
                           CUmodule *module_out);

/* Get a kernel function handle from a loaded module. */
int  vir_gpu_cuda_get_function(CUmodule module, const char *name,
                               CUfunction *func_out);

/* Allocate device memory. */
int  vir_gpu_cuda_malloc(CUdeviceptr *ptr_out, size_t bytes);

/* Free device memory. */
void vir_gpu_cuda_free(CUdeviceptr ptr);

/* Host → Device copy. */
int  vir_gpu_cuda_memcpy_h2d(CUdeviceptr dst, const void *src, size_t bytes);

/* Device → Host copy. */
int  vir_gpu_cuda_memcpy_d2h(void *dst, CUdeviceptr src, size_t bytes);

/* Launch a kernel. */
int  vir_gpu_cuda_launch(CUfunction func,
                         const vir_gpu_launch_config_t *config,
                         void **kernel_params);

/* Synchronize default stream. */
int  vir_gpu_cuda_sync(void);

/* Create an async stream. */
int  vir_gpu_cuda_stream_create(CUstream *stream_out);

/* Destroy an async stream. */
void vir_gpu_cuda_stream_destroy(CUstream stream);

/* Synchronize a specific stream. */
int  vir_gpu_cuda_stream_sync(CUstream stream);

#endif /* VIR_GPU_CUDA_H */

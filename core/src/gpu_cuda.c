/*
 * gpu_cuda.c – CUDA Driver API FFI via dlopen/dlsym
 * ===================================================
 * Zero-dependency runtime binding to libcuda.
 * Supports Linux (libcuda.so) and macOS (libcuda.dylib, rare).
 *
 * All CUDA Driver API symbols are resolved lazily at init time.
 * If CUDA is not installed, vir_gpu_cuda_init() returns -1 gracefully.
 */

#include "gpu_cuda.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#ifdef _WIN32
  #include <windows.h>
  #define DLOPEN(p)     ((void*)LoadLibraryA(p))
  #define DLSYM(h,s)    ((void*)GetProcAddress((HMODULE)(h),(s)))
  #define DLCLOSE(h)    FreeLibrary((HMODULE)(h))
#else
  #include <dlfcn.h>
  #define DLOPEN(p)     dlopen((p), RTLD_LAZY | RTLD_LOCAL)
  #define DLSYM(h,s)    dlsym((h),(s))
  #define DLCLOSE(h)    dlclose((h))
#endif

/* ═══════════════════════════════════════════════════════
 * CUDA Driver API Function Pointer Types
 * ═══════════════════════════════════════════════════════ */

typedef CUresult (*pfn_cuInit)(unsigned int);
typedef CUresult (*pfn_cuDeviceGetCount)(int *);
typedef CUresult (*pfn_cuDeviceGet)(CUdevice *, int);
typedef CUresult (*pfn_cuDeviceGetName)(char *, int, CUdevice);
typedef CUresult (*pfn_cuDeviceGetAttribute)(int *, int, CUdevice);
typedef CUresult (*pfn_cuDeviceTotalMem)(size_t *, CUdevice);
typedef CUresult (*pfn_cuCtxCreate)(CUcontext *, unsigned int, CUdevice);
typedef CUresult (*pfn_cuCtxDestroy)(CUcontext);
typedef CUresult (*pfn_cuModuleLoadDataEx)(CUmodule *, const void *,
                                           unsigned int, void *, void **);
typedef CUresult (*pfn_cuModuleGetFunction)(CUfunction *, CUmodule,
                                            const char *);
typedef CUresult (*pfn_cuModuleUnload)(CUmodule);
typedef CUresult (*pfn_cuLaunchKernel)(CUfunction,
                                       unsigned int, unsigned int, unsigned int,
                                       unsigned int, unsigned int, unsigned int,
                                       unsigned int, CUstream,
                                       void **, void **);
typedef CUresult (*pfn_cuMemAlloc)(CUdeviceptr *, size_t);
typedef CUresult (*pfn_cuMemFree)(CUdeviceptr);
typedef CUresult (*pfn_cuMemcpyHtoD)(CUdeviceptr, const void *, size_t);
typedef CUresult (*pfn_cuMemcpyDtoH)(void *, CUdeviceptr, size_t);
typedef CUresult (*pfn_cuCtxSynchronize)(void);
typedef CUresult (*pfn_cuStreamCreate)(CUstream *, unsigned int);
typedef CUresult (*pfn_cuStreamDestroy)(CUstream);
typedef CUresult (*pfn_cuStreamSynchronize)(CUstream);

/* CUDA Device Attribute constants (from cuda.h) */
#define CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MAJOR  75
#define CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MINOR  76
#define CU_DEVICE_ATTRIBUTE_MULTIPROCESSOR_COUNT      16
#define CU_DEVICE_ATTRIBUTE_MAX_THREADS_PER_BLOCK     1
#define CU_DEVICE_ATTRIBUTE_MAX_SHARED_MEMORY_PER_BLOCK 8
#define CU_DEVICE_ATTRIBUTE_WARP_SIZE                 10

/* ═══════════════════════════════════════════════════════
 * Module State
 * ═══════════════════════════════════════════════════════ */

static struct {
    void *lib;
    int   inited;
    CUcontext ctx;

    /* Function pointers */
    pfn_cuInit                  cuInit;
    pfn_cuDeviceGetCount        cuDeviceGetCount;
    pfn_cuDeviceGet             cuDeviceGet;
    pfn_cuDeviceGetName         cuDeviceGetName;
    pfn_cuDeviceGetAttribute    cuDeviceGetAttribute;
    pfn_cuDeviceTotalMem        cuDeviceTotalMem;
    pfn_cuCtxCreate             cuCtxCreate;
    pfn_cuCtxDestroy            cuCtxDestroy;
    pfn_cuModuleLoadDataEx      cuModuleLoadDataEx;
    pfn_cuModuleGetFunction     cuModuleGetFunction;
    pfn_cuModuleUnload          cuModuleUnload;
    pfn_cuLaunchKernel          cuLaunchKernel;
    pfn_cuMemAlloc              cuMemAlloc;
    pfn_cuMemFree               cuMemFree;
    pfn_cuMemcpyHtoD            cuMemcpyHtoD;
    pfn_cuMemcpyDtoH            cuMemcpyDtoH;
    pfn_cuCtxSynchronize        cuCtxSynchronize;
    pfn_cuStreamCreate          cuStreamCreate;
    pfn_cuStreamDestroy         cuStreamDestroy;
    pfn_cuStreamSynchronize     cuStreamSynchronize;
} cuda_state = { .lib = NULL, .inited = 0, .ctx = NULL };

/* ═══════════════════════════════════════════════════════
 * Symbol Resolution Helper
 * ═══════════════════════════════════════════════════════ */

#define LOAD_SYM(name)                                           \
    do {                                                         \
        cuda_state.name = (pfn_##name)DLSYM(cuda_state.lib, #name); \
        if (!cuda_state.name) {                                  \
            /* Try _v2 variant (common in CUDA Driver API) */    \
            cuda_state.name = (pfn_##name)DLSYM(cuda_state.lib, #name "_v2"); \
        }                                                        \
        if (!cuda_state.name) {                                  \
            fprintf(stderr, "[vir:gpu] missing symbol: %s\n", #name); \
            DLCLOSE(cuda_state.lib);                             \
            cuda_state.lib = NULL;                               \
            return -1;                                           \
        }                                                        \
    } while(0)

/* ═══════════════════════════════════════════════════════
 * Public API Implementation
 * ═══════════════════════════════════════════════════════ */

int vir_gpu_cuda_init(void) {
    if (cuda_state.inited) return 0;

    /* Try platform-specific library names */
#ifdef _WIN32
    const char *paths[] = { "nvcuda.dll", NULL };
#elif defined(__APPLE__)
    const char *paths[] = { "libcuda.dylib", NULL };
#else
    const char *paths[] = {
        "libcuda.so.1",   /* versioned (most common) */
        "libcuda.so",     /* unversioned fallback     */
        NULL
    };
#endif

    for (int i = 0; paths[i]; ++i) {
        cuda_state.lib = DLOPEN(paths[i]);
        if (cuda_state.lib) break;
    }
    if (!cuda_state.lib) return -1;

    /* Resolve all symbols */
    LOAD_SYM(cuInit);
    LOAD_SYM(cuDeviceGetCount);
    LOAD_SYM(cuDeviceGet);
    LOAD_SYM(cuDeviceGetName);
    LOAD_SYM(cuDeviceGetAttribute);
    LOAD_SYM(cuDeviceTotalMem);
    LOAD_SYM(cuCtxCreate);
    LOAD_SYM(cuCtxDestroy);
    LOAD_SYM(cuModuleLoadDataEx);
    LOAD_SYM(cuModuleGetFunction);
    LOAD_SYM(cuModuleUnload);
    LOAD_SYM(cuLaunchKernel);
    LOAD_SYM(cuMemAlloc);
    LOAD_SYM(cuMemFree);
    LOAD_SYM(cuMemcpyHtoD);
    LOAD_SYM(cuMemcpyDtoH);
    LOAD_SYM(cuCtxSynchronize);
    LOAD_SYM(cuStreamCreate);
    LOAD_SYM(cuStreamDestroy);
    LOAD_SYM(cuStreamSynchronize);

    /* Initialize CUDA */
    CUresult rc = cuda_state.cuInit(0);
    if (rc != CUDA_SUCCESS) {
        DLCLOSE(cuda_state.lib);
        cuda_state.lib = NULL;
        return -1;
    }

    cuda_state.inited = 1;
    return 0;
}

void vir_gpu_cuda_shutdown(void) {
    if (!cuda_state.inited) return;
    if (cuda_state.ctx) {
        cuda_state.cuCtxDestroy(cuda_state.ctx);
        cuda_state.ctx = NULL;
    }
    if (cuda_state.lib) {
        DLCLOSE(cuda_state.lib);
        cuda_state.lib = NULL;
    }
    cuda_state.inited = 0;
}

int vir_gpu_cuda_available(void) {
    return cuda_state.inited;
}

int vir_gpu_cuda_device_count(void) {
    if (!cuda_state.inited) return 0;
    int count = 0;
    CUresult rc = cuda_state.cuDeviceGetCount(&count);
    return (rc == CUDA_SUCCESS) ? count : 0;
}

int vir_gpu_cuda_device_info(int ordinal, vir_gpu_device_info_t *info) {
    if (!cuda_state.inited || !info) return -1;
    memset(info, 0, sizeof(*info));
    info->ordinal = ordinal;

    CUdevice dev;
    CUresult rc = cuda_state.cuDeviceGet(&dev, ordinal);
    if (rc != CUDA_SUCCESS) return -1;

    cuda_state.cuDeviceGetName(info->name, sizeof(info->name), dev);
    info->name[sizeof(info->name) - 1] = '\0';

    cuda_state.cuDeviceGetAttribute(&info->compute_major,
        CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MAJOR, dev);
    cuda_state.cuDeviceGetAttribute(&info->compute_minor,
        CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MINOR, dev);
    cuda_state.cuDeviceGetAttribute(&info->sm_count,
        CU_DEVICE_ATTRIBUTE_MULTIPROCESSOR_COUNT, dev);
    cuda_state.cuDeviceGetAttribute(&info->max_threads_per_block,
        CU_DEVICE_ATTRIBUTE_MAX_THREADS_PER_BLOCK, dev);
    cuda_state.cuDeviceGetAttribute(&info->max_shared_mem_per_block,
        CU_DEVICE_ATTRIBUTE_MAX_SHARED_MEMORY_PER_BLOCK, dev);
    cuda_state.cuDeviceGetAttribute(&info->warp_size,
        CU_DEVICE_ATTRIBUTE_WARP_SIZE, dev);

    size_t mem = 0;
    cuda_state.cuDeviceTotalMem(&mem, dev);
    info->total_mem = (int64_t)mem;

    return 0;
}

int vir_gpu_cuda_create_context(int device_ordinal) {
    if (!cuda_state.inited) return -1;
    if (cuda_state.ctx) {
        cuda_state.cuCtxDestroy(cuda_state.ctx);
        cuda_state.ctx = NULL;
    }

    CUdevice dev;
    CUresult rc = cuda_state.cuDeviceGet(&dev, device_ordinal);
    if (rc != CUDA_SUCCESS) return -1;

    /* flags = 0 → CU_CTX_SCHED_AUTO */
    rc = cuda_state.cuCtxCreate(&cuda_state.ctx, 0, dev);
    return (rc == CUDA_SUCCESS) ? 0 : -1;
}

void vir_gpu_cuda_destroy_context(void) {
    if (!cuda_state.inited || !cuda_state.ctx) return;
    cuda_state.cuCtxDestroy(cuda_state.ctx);
    cuda_state.ctx = NULL;
}

int vir_gpu_cuda_load_ptx(const char *ptx_source, size_t ptx_len,
                          CUmodule *module_out) {
    if (!cuda_state.inited || !ptx_source || !module_out) return -1;
    (void)ptx_len; /* PTX is null-terminated for cuModuleLoadDataEx */

    CUresult rc = cuda_state.cuModuleLoadDataEx(
        module_out, ptx_source,
        0,     /* numOptions */
        NULL,  /* options */
        NULL   /* optionValues */
    );
    return (rc == CUDA_SUCCESS) ? 0 : (int)rc;
}

int vir_gpu_cuda_get_function(CUmodule module, const char *name,
                              CUfunction *func_out) {
    if (!cuda_state.inited || !name || !func_out) return -1;
    CUresult rc = cuda_state.cuModuleGetFunction(func_out, module, name);
    return (rc == CUDA_SUCCESS) ? 0 : (int)rc;
}

int vir_gpu_cuda_malloc(CUdeviceptr *ptr_out, size_t bytes) {
    if (!cuda_state.inited || !ptr_out || bytes == 0) return -1;
    CUresult rc = cuda_state.cuMemAlloc(ptr_out, bytes);
    return (rc == CUDA_SUCCESS) ? 0 : (int)rc;
}

void vir_gpu_cuda_free(CUdeviceptr ptr) {
    if (!cuda_state.inited || ptr == 0) return;
    cuda_state.cuMemFree(ptr);
}

int vir_gpu_cuda_memcpy_h2d(CUdeviceptr dst, const void *src, size_t bytes) {
    if (!cuda_state.inited || !src || bytes == 0) return -1;
    CUresult rc = cuda_state.cuMemcpyHtoD(dst, src, bytes);
    return (rc == CUDA_SUCCESS) ? 0 : (int)rc;
}

int vir_gpu_cuda_memcpy_d2h(void *dst, CUdeviceptr src, size_t bytes) {
    if (!cuda_state.inited || !dst || bytes == 0) return -1;
    CUresult rc = cuda_state.cuMemcpyDtoH(dst, src, bytes);
    return (rc == CUDA_SUCCESS) ? 0 : (int)rc;
}

int vir_gpu_cuda_launch(CUfunction func,
                        const vir_gpu_launch_config_t *config,
                        void **kernel_params) {
    if (!cuda_state.inited || !func || !config) return -1;

    CUresult rc = cuda_state.cuLaunchKernel(
        func,
        config->grid_x,  config->grid_y,  config->grid_z,
        config->block_x, config->block_y, config->block_z,
        config->shared_mem_bytes,
        config->stream,
        kernel_params,
        NULL  /* extra */
    );
    return (rc == CUDA_SUCCESS) ? 0 : (int)rc;
}

int vir_gpu_cuda_sync(void) {
    if (!cuda_state.inited) return -1;
    CUresult rc = cuda_state.cuCtxSynchronize();
    return (rc == CUDA_SUCCESS) ? 0 : (int)rc;
}

int vir_gpu_cuda_stream_create(CUstream *stream_out) {
    if (!cuda_state.inited || !stream_out) return -1;
    /* flags = 0 → CU_STREAM_DEFAULT */
    CUresult rc = cuda_state.cuStreamCreate(stream_out, 0);
    return (rc == CUDA_SUCCESS) ? 0 : (int)rc;
}

void vir_gpu_cuda_stream_destroy(CUstream stream) {
    if (!cuda_state.inited || !stream) return;
    cuda_state.cuStreamDestroy(stream);
}

int vir_gpu_cuda_stream_sync(CUstream stream) {
    if (!cuda_state.inited || !stream) return -1;
    CUresult rc = cuda_state.cuStreamSynchronize(stream);
    return (rc == CUDA_SUCCESS) ? 0 : (int)rc;
}

/*
 * gpu_pipeline.h – GPU Pipeline Integration
 * Phase 3 – G4
 */

#ifndef VIR_GPU_PIPELINE_H
#define VIR_GPU_PIPELINE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    VIR_GPU_BACKEND_NONE = 0,
    VIR_GPU_BACKEND_METAL,
    VIR_GPU_BACKEND_CUDA,
    VIR_GPU_BACKEND_CPU_FALLBACK,
} vir_gpu_backend_t;

int  vir_gpu_init(void);
void vir_gpu_shutdown(void);

const char        *vir_gpu_device_name(void);
vir_gpu_backend_t  vir_gpu_active_backend(void);
int                vir_gpu_is_available(void);

/* Buffers */
int vir_gpu_buffer_alloc(size_t size);
int vir_gpu_buffer_upload(int buf_id, const void *data, size_t size);
int vir_gpu_buffer_download(int buf_id, void *out, size_t size);
int vir_gpu_buffer_free(int buf_id);
int vir_gpu_buffer_count(void);

/* Kernels */
int vir_gpu_kernel_create(const char *name, const char *source);
int vir_gpu_kernel_free(int kern_id);
int vir_gpu_kernel_count(void);

/* Dispatch */
int vir_gpu_dispatch(int kern_id, int in_buf, int out_buf, int n);

#ifdef __cplusplus
}
#endif

#endif /* VIR_GPU_PIPELINE_H */

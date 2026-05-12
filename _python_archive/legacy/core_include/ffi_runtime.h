/*
 * ffi_runtime.h – FFI for Vir Stdlib
 * Phase 3 – G3
 */

#ifndef VIR_FFI_RUNTIME_H
#define VIR_FFI_RUNTIME_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    VIR_FFI_VOID = 0,
    VIR_FFI_INT32,
    VIR_FFI_INT64,
    VIR_FFI_FLOAT32,
    VIR_FFI_FLOAT64,
    VIR_FFI_PTR,
    VIR_FFI_STRING,
    VIR_FFI_BOOL,
} vir_ffi_type_t;

int vir_ffi_init(void);
int vir_ffi_load(const char *path);
int vir_ffi_unload(int lib_id);
int vir_ffi_lookup(int lib_id, const char *name);
int vir_ffi_set_signature(int sym_id, vir_ffi_type_t ret_type,
                          const vir_ffi_type_t *arg_types, int arg_count);

int64_t vir_ffi_call_i(int sym_id, int64_t a0, int64_t a1, int64_t a2,
                        int64_t a3, int64_t a4, int64_t a5);
double  vir_ffi_call_f(int sym_id, int64_t a0, int64_t a1, int64_t a2,
                        int64_t a3, int64_t a4, int64_t a5);
void    vir_ffi_call_v(int sym_id, int64_t a0, int64_t a1, int64_t a2,
                        int64_t a3, int64_t a4, int64_t a5);

int vir_ffi_struct_size(const vir_ffi_type_t *fields, int nfields);
int vir_ffi_struct_offset(const vir_ffi_type_t *fields, int nfields, int field_idx);

void   *vir_ffi_alloc(int size);
void    vir_ffi_free(void *ptr);
void    vir_ffi_write_i32(void *ptr, int offset, int32_t val);
int32_t vir_ffi_read_i32(const void *ptr, int offset);
void    vir_ffi_write_i64(void *ptr, int offset, int64_t val);
int64_t vir_ffi_read_i64(const void *ptr, int offset);
void    vir_ffi_write_f64(void *ptr, int offset, double val);
double  vir_ffi_read_f64(const void *ptr, int offset);

#ifdef __cplusplus
}
#endif

#endif /* VIR_FFI_RUNTIME_H */

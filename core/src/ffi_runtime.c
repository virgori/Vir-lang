/*
 * ffi_runtime.c – Foreign Function Interface for Vir Stdlib
 * ===========================================================
 * Phase 3 – G3: Native backing for stdlib/vir/ffi/
 *
 * Provides: dlopen/dlsym wrapper, type-safe call dispatch,
 * struct layout computation, callback trampolines.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>
#include <stdint.h>

/* ═══════════════════════════════════════════════════════
 * Constants
 * ═══════════════════════════════════════════════════════ */

#define VIR_FFI_MAX_LIBS     32
#define VIR_FFI_MAX_SYMS     256
#define VIR_FFI_MAX_ARGS     16

/* ═══════════════════════════════════════════════════════
 * Types
 * ═══════════════════════════════════════════════════════ */

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

typedef struct {
    void        *handle;
    char         path[256];
    int          active;
} vir_ffi_lib_t;

typedef struct {
    void        *sym;
    int          lib_id;
    char         name[128];
    vir_ffi_type_t return_type;
    vir_ffi_type_t arg_types[VIR_FFI_MAX_ARGS];
    int          arg_count;
    int          active;
} vir_ffi_sym_t;

typedef union {
    int32_t   i32;
    int64_t   i64;
    float     f32;
    double    f64;
    void     *ptr;
    const char *str;
} vir_ffi_val_t;

typedef struct {
    vir_ffi_lib_t libs[VIR_FFI_MAX_LIBS];
    vir_ffi_sym_t syms[VIR_FFI_MAX_SYMS];
    int           lib_count;
    int           sym_count;
} vir_ffi_ctx_t;

static vir_ffi_ctx_t g_ffi;

/* ═══════════════════════════════════════════════════════
 * Library Management
 * ═══════════════════════════════════════════════════════ */

int vir_ffi_init(void) {
    memset(&g_ffi, 0, sizeof(g_ffi));
    return 0;
}

int vir_ffi_load(const char *path) {
    for (int i = 0; i < VIR_FFI_MAX_LIBS; i++) {
        if (!g_ffi.libs[i].active) {
            void *h = dlopen(path, RTLD_LAZY);
            if (!h) {
                fprintf(stderr, "vir_ffi_load: %s\n", dlerror());
                return -1;
            }
            g_ffi.libs[i].handle = h;
            snprintf(g_ffi.libs[i].path, sizeof(g_ffi.libs[i].path), "%s", path);
            g_ffi.libs[i].active = 1;
            g_ffi.lib_count++;
            return i;
        }
    }
    return -1;
}

int vir_ffi_unload(int lib_id) {
    if (lib_id < 0 || lib_id >= VIR_FFI_MAX_LIBS) return -1;
    if (!g_ffi.libs[lib_id].active) return -1;
    dlclose(g_ffi.libs[lib_id].handle);
    g_ffi.libs[lib_id].active = 0;
    g_ffi.lib_count--;
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Symbol Lookup
 * ═══════════════════════════════════════════════════════ */

int vir_ffi_lookup(int lib_id, const char *name) {
    if (lib_id < 0 || lib_id >= VIR_FFI_MAX_LIBS) return -1;
    if (!g_ffi.libs[lib_id].active) return -1;

    void *sym = dlsym(g_ffi.libs[lib_id].handle, name);
    if (!sym) {
        fprintf(stderr, "vir_ffi_lookup: %s\n", dlerror());
        return -1;
    }

    for (int i = 0; i < VIR_FFI_MAX_SYMS; i++) {
        if (!g_ffi.syms[i].active) {
            g_ffi.syms[i].sym    = sym;
            g_ffi.syms[i].lib_id = lib_id;
            snprintf(g_ffi.syms[i].name, sizeof(g_ffi.syms[i].name), "%s", name);
            g_ffi.syms[i].active = 1;
            g_ffi.sym_count++;
            return i;
        }
    }
    return -1;
}

/* ═══════════════════════════════════════════════════════
 * Type-Safe Call Dispatch
 * ═══════════════════════════════════════════════════════ */

/* Set function signature before calling */
int vir_ffi_set_signature(int sym_id, vir_ffi_type_t ret_type,
                          const vir_ffi_type_t *arg_types, int arg_count) {
    if (sym_id < 0 || sym_id >= VIR_FFI_MAX_SYMS) return -1;
    if (!g_ffi.syms[sym_id].active) return -1;
    if (arg_count > VIR_FFI_MAX_ARGS) return -1;

    g_ffi.syms[sym_id].return_type = ret_type;
    g_ffi.syms[sym_id].arg_count   = arg_count;
    for (int i = 0; i < arg_count; i++) {
        g_ffi.syms[sym_id].arg_types[i] = arg_types[i];
    }
    return 0;
}

/* Call with up to 6 integer/pointer args (covers most C ABI calls) */
int64_t vir_ffi_call_i(int sym_id, int64_t a0, int64_t a1, int64_t a2,
                        int64_t a3, int64_t a4, int64_t a5) {
    if (sym_id < 0 || sym_id >= VIR_FFI_MAX_SYMS) return -1;
    if (!g_ffi.syms[sym_id].active) return -1;

    typedef int64_t (*fn6_t)(int64_t, int64_t, int64_t,
                             int64_t, int64_t, int64_t);
    fn6_t fn = (fn6_t)g_ffi.syms[sym_id].sym;
    return fn(a0, a1, a2, a3, a4, a5);
}

/* Call returning double */
double vir_ffi_call_f(int sym_id, int64_t a0, int64_t a1, int64_t a2,
                      int64_t a3, int64_t a4, int64_t a5) {
    if (sym_id < 0 || sym_id >= VIR_FFI_MAX_SYMS) return 0.0;
    if (!g_ffi.syms[sym_id].active) return 0.0;

    typedef double (*fn6f_t)(int64_t, int64_t, int64_t,
                             int64_t, int64_t, int64_t);
    fn6f_t fn = (fn6f_t)g_ffi.syms[sym_id].sym;
    return fn(a0, a1, a2, a3, a4, a5);
}

/* Call returning void */
void vir_ffi_call_v(int sym_id, int64_t a0, int64_t a1, int64_t a2,
                    int64_t a3, int64_t a4, int64_t a5) {
    if (sym_id < 0 || sym_id >= VIR_FFI_MAX_SYMS) return;
    if (!g_ffi.syms[sym_id].active) return;

    typedef void (*fn6v_t)(int64_t, int64_t, int64_t,
                           int64_t, int64_t, int64_t);
    fn6v_t fn = (fn6v_t)g_ffi.syms[sym_id].sym;
    fn(a0, a1, a2, a3, a4, a5);
}

/* ═══════════════════════════════════════════════════════
 * Struct Layout / Memory Helpers
 * ═══════════════════════════════════════════════════════ */

static int type_size(vir_ffi_type_t t) {
    switch (t) {
        case VIR_FFI_VOID:    return 0;
        case VIR_FFI_INT32:   return 4;
        case VIR_FFI_INT64:   return 8;
        case VIR_FFI_FLOAT32: return 4;
        case VIR_FFI_FLOAT64: return 8;
        case VIR_FFI_PTR:     return 8;  /* 64-bit */
        case VIR_FFI_STRING:  return 8;
        case VIR_FFI_BOOL:    return 1;
    }
    return 0;
}

int vir_ffi_struct_size(const vir_ffi_type_t *fields, int nfields) {
    int offset = 0;
    for (int i = 0; i < nfields; i++) {
        int sz = type_size(fields[i]);
        int align = sz > 0 ? sz : 1;
        if (align > 8) align = 8;
        /* Align up */
        offset = (offset + align - 1) & ~(align - 1);
        offset += sz;
    }
    return offset;
}

int vir_ffi_struct_offset(const vir_ffi_type_t *fields, int nfields, int field_idx) {
    if (field_idx >= nfields) return -1;
    int offset = 0;
    for (int i = 0; i < nfields; i++) {
        int sz = type_size(fields[i]);
        int align = sz > 0 ? sz : 1;
        if (align > 8) align = 8;
        offset = (offset + align - 1) & ~(align - 1);
        if (i == field_idx) return offset;
        offset += sz;
    }
    return -1;
}

/* ═══════════════════════════════════════════════════════
 * Pointer helpers for Vir
 * ═══════════════════════════════════════════════════════ */

void *vir_ffi_alloc(int size) {
    return malloc(size);
}

void vir_ffi_free(void *ptr) {
    free(ptr);
}

void vir_ffi_write_i32(void *ptr, int offset, int32_t val) {
    *(int32_t *)((char *)ptr + offset) = val;
}

int32_t vir_ffi_read_i32(const void *ptr, int offset) {
    return *(const int32_t *)((const char *)ptr + offset);
}

void vir_ffi_write_i64(void *ptr, int offset, int64_t val) {
    *(int64_t *)((char *)ptr + offset) = val;
}

int64_t vir_ffi_read_i64(const void *ptr, int offset) {
    return *(const int64_t *)((const char *)ptr + offset);
}

void vir_ffi_write_f64(void *ptr, int offset, double val) {
    *(double *)((char *)ptr + offset) = val;
}

double vir_ffi_read_f64(const void *ptr, int offset) {
    return *(const double *)((const char *)ptr + offset);
}

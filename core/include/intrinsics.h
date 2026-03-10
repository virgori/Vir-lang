/*
 * intrinsics.h – Built-in Function Bindings (Intrinsics)
 * =======================================================
 * Maps Vir built-in operations (PRINT, INPUT, CHECK_CPU, …)
 * to actual native function addresses that JIT machine code
 * can CALL directly via the ABI.
 *
 * No Python dependency — everything is self-contained C.
 * Machine code emits a CALL to the address stored in the
 * intrinsic table; the Bridge resolves it at JIT time.
 */

#ifndef VIR_INTRINSICS_H
#define VIR_INTRINSICS_H

#include "constraints.h"
#include "q_ir.h"
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * Intrinsic ID  (matches Q-IR I/O + system opcodes)
 * ═══════════════════════════════════════════════════════ */

typedef enum {
    INTRINSIC_PRINT     = 0,   /* int64 → stdout              */
    INTRINSIC_PRINT_STR = 1,   /* ptr   → stdout (+ newline)  */
    INTRINSIC_INPUT     = 2,   /* stdin → int64               */
    INTRINSIC_INPUT_STR = 3,   /* stdin → ptr (line buffer)   */
    INTRINSIC_CPU_LOAD  = 4,   /* ()    → int64 (0-100%)      */
    INTRINSIC_SLEEP_MS  = 5,   /* int64 → void                */
    INTRINSIC_ALLOC     = 6,   /* int64 → ptr                 */
    INTRINSIC_FREE      = 7,   /* ptr   → void                */
    INTRINSIC_STRLEN    = 8,   /* ptr   → int64               */

    /* ── Phase 1 Extensions (self-hosting bootstrap) ──── */
    INTRINSIC_STR_GET   = 9,   /* (ptr, i64) → i64 (byte)     */
    INTRINSIC_STR_CAT   = 10,  /* (ptr, ptr) → ptr (alloc'd)  */
    INTRINSIC_STR_EQ    = 11,  /* (ptr, ptr) → i64 (0|1)      */
    INTRINSIC_PRINT_RAW = 12,  /* ptr → void (no newline)     */
    INTRINSIC_I_TO_STR  = 13,  /* i64 → ptr (alloc'd)         */
    INTRINSIC_STR_TO_I  = 14,  /* ptr → i64                   */
    INTRINSIC_EXIT      = 15,  /* i64 → noreturn              */
    INTRINSIC_FILE_OPEN = 16,  /* (ptr, ptr) → i64 (fd)       */
    INTRINSIC_FILE_READ = 17,  /* i64 → ptr (alloc'd)         */
    INTRINSIC_FILE_WRITE = 18, /* (i64, ptr) → void           */
    INTRINSIC_FILE_CLOSE = 19, /* i64 → void                  */
    INTRINSIC_FILE_WRITE_BYTE = 20, /* (i64, i64) → void      */
    INTRINSIC_ARR_NEW   = 21,  /* i64 → i64 (handle)          */
    INTRINSIC_ARR_LEN   = 22,  /* i64 → i64                   */
    INTRINSIC_ARR_GET   = 23,  /* (i64, i64) → i64            */
    INTRINSIC_ARR_SET   = 24,  /* (i64, i64, i64) → void      */
    INTRINSIC_ARR_PUSH  = 25,  /* (i64, i64) → void           */

    INTRINSIC_COUNT     = 26,
} intrinsic_id_t;

/* ═══════════════════════════════════════════════════════
 * Intrinsic Descriptor
 * ═══════════════════════════════════════════════════════ */

#define INTRINSIC_MAX_ARGS 4

typedef struct {
    intrinsic_id_t  id;
    const char     *name;           /* C symbol name               */
    void           *func_ptr;       /* Resolved address at init    */
    vir_type_t      return_type;
    uint8_t         arg_count;
    vir_type_t      arg_types[INTRINSIC_MAX_ARGS];
} intrinsic_desc_t;

/* ═══════════════════════════════════════════════════════
 * Intrinsic Table (global, singleton)
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    intrinsic_desc_t entries[INTRINSIC_COUNT];
    int              initialised;
} intrinsic_table_t;

/* Get (or lazily initialise) the global intrinsic table. */
intrinsic_table_t *vir_intrinsics(void);

/* Lookup by ID */
const intrinsic_desc_t *vir_intrinsic_get(intrinsic_id_t id);

/* Get the raw function address for a given intrinsic
 * (this is what the codegen embeds in CALL instructions). */
void *vir_intrinsic_addr(intrinsic_id_t id);

/* Map a Q-IR opcode to an intrinsic ID (or -1 if N/A) */
int vir_opcode_to_intrinsic(q_opcode_t opcode);

/* ═══════════════════════════════════════════════════════
 * Native Intrinsic Implementations
 * ═══════════════════════════════════════════════════════
 * These are the actual C functions that JIT code calls.
 * Signature must match the ABI: args in registers, return
 * in RAX / X0.
 */

/* Print an integer to stdout (returns 0) */
int64_t vir_builtin_print_i64(int64_t value);

/* Print a C string to stdout */
int64_t vir_builtin_print_str(const char *str);

/* Read an integer from stdin */
int64_t vir_builtin_input_i64(void);

/* Read a line from stdin into a static buffer, return ptr */
const char *vir_builtin_input_str(void);

/* Return current CPU load 0-100 */
int64_t vir_builtin_cpu_load(void);

/* Sleep for N milliseconds */
void vir_builtin_sleep_ms(int64_t ms);

/* Allocate N bytes (malloc wrapper) */
void *vir_builtin_alloc(int64_t nbytes);

/* Free memory */
void vir_builtin_free(void *ptr);

/* String length */
int64_t vir_builtin_strlen(const char *s);

/* ── Phase 1 Extension: String ops ────────────────────── */
int64_t     vir_builtin_str_get(const char *s, int64_t idx);
const char *vir_builtin_str_cat(const char *a, const char *b);
int64_t     vir_builtin_str_eq(const char *a, const char *b);
void        vir_builtin_print_raw(const char *s);
const char *vir_builtin_i_to_str(int64_t n);
int64_t     vir_builtin_str_to_i(const char *s);
void        vir_builtin_exit(int64_t code);

/* ── Phase 1 Extension: File I/O ─────────────────────── */
int64_t     vir_builtin_file_open(const char *path, const char *mode);
const char *vir_builtin_file_read(int64_t fd);
void        vir_builtin_file_write(int64_t fd, const char *data);
void        vir_builtin_file_close(int64_t fd);
void        vir_builtin_file_write_byte(int64_t fd, int64_t byte);

/* ── Phase 1 Extension: Array runtime ────────────────── */
int64_t     vir_builtin_arr_new(int64_t cap);
int64_t     vir_builtin_arr_len(int64_t handle);
int64_t     vir_builtin_arr_get(int64_t handle, int64_t idx);
void        vir_builtin_arr_set(int64_t handle, int64_t idx, int64_t val);
void        vir_builtin_arr_push(int64_t handle, int64_t val);

#ifdef __cplusplus
}
#endif

#endif /* VIR_INTRINSICS_H */

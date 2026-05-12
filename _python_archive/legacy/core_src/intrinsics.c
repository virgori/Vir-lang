/*
 * intrinsics.c – Native Built-in Function Implementations
 * ========================================================
 * Self-contained C.  No Python, no external runtime.
 * JIT machine code calls these via a plain CALL instruction
 * to the address stored in the intrinsic table.
 */

#include "intrinsics.h"
#include "bridge.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(__APPLE__) || defined(__linux__)
#include <unistd.h>
#include <time.h>
#endif

/* ═══════════════════════════════════════════════════════
 * Native Implementations
 * ═══════════════════════════════════════════════════════ */

int64_t vir_builtin_print_i64(int64_t value)
{
    printf("%lld\n", (long long)value);
    fflush(stdout);
    return 0;
}

int64_t vir_builtin_print_str(const char *str)
{
    if (str) fputs(str, stdout);
    fputc('\n', stdout);
    fflush(stdout);
    return 0;
}

int64_t vir_builtin_input_i64(void)
{
    int64_t val = 0;
    if (scanf("%lld", (long long *)&val) != 1) val = 0;
    return val;
}

/* Static buffer for line input – avoids heap per call */
static char s_input_buf[4096];

const char *vir_builtin_input_str(void)
{
    if (fgets(s_input_buf, sizeof(s_input_buf), stdin)) {
        /* Strip trailing newline */
        size_t len = strlen(s_input_buf);
        if (len > 0 && s_input_buf[len - 1] == '\n')
            s_input_buf[len - 1] = '\0';
        return s_input_buf;
    }
    s_input_buf[0] = '\0';
    return s_input_buf;
}

int64_t vir_builtin_cpu_load(void)
{
    cpu_state_t st;
    bridge_probe_cpu(&st);
    return (int64_t)st.cpu_load_percent;
}

void vir_builtin_sleep_ms(int64_t ms)
{
#if defined(__APPLE__) || defined(__linux__)
    struct timespec ts;
    ts.tv_sec  = ms / 1000;
    ts.tv_nsec = (ms % 1000) * 1000000L;
    nanosleep(&ts, NULL);
#elif defined(_WIN32)
    extern void __stdcall Sleep(unsigned long dwMilliseconds);
    Sleep((unsigned long)ms);
#else
    (void)ms;
#endif
}

void *vir_builtin_alloc(int64_t nbytes)
{
    if (nbytes <= 0) return NULL;
    /*
     * SIMD-aligned allocation: return memory aligned to 32 bytes
     * to satisfy both NEON (16-byte) and AVX (32-byte) requirements.
     * Uses posix_memalign on POSIX, _aligned_malloc on Windows.
     * Caller must use vir_builtin_free() to release.
     */
#if defined(_WIN32)
    return _aligned_malloc((size_t)nbytes, 32);
#else
    void *ptr = NULL;
    if (posix_memalign(&ptr, 32, (size_t)nbytes) != 0)
        return NULL;
    return ptr;
#endif
}

void vir_builtin_free(void *ptr)
{
#if defined(_WIN32)
    _aligned_free(ptr);
#else
    free(ptr);  /* posix_memalign memory is free()-compatible */
#endif
}

int64_t vir_builtin_strlen(const char *s)
{
    if (!s) return 0;
    return (int64_t)strlen(s);
}

/* ═══════════════════════════════════════════════════════
 * Phase 1 Extensions – String Operations
 * ═══════════════════════════════════════════════════════ */

int64_t vir_builtin_str_get(const char *s, int64_t idx)
{
    if (!s || idx < 0 || idx >= (int64_t)strlen(s)) return 0;
    return (int64_t)(unsigned char)s[idx];
}

const char *vir_builtin_str_cat(const char *a, const char *b)
{
    if (!a) a = "";
    if (!b) b = "";
    size_t la = strlen(a), lb = strlen(b);
    char *out = (char *)malloc(la + lb + 1);
    if (!out) return "";
    memcpy(out, a, la);
    memcpy(out + la, b, lb);
    out[la + lb] = '\0';
    return out;
}

int64_t vir_builtin_str_eq(const char *a, const char *b)
{
    if (!a && !b) return 1;
    if (!a || !b) return 0;
    return strcmp(a, b) == 0 ? 1 : 0;
}

void vir_builtin_print_raw(const char *s)
{
    if (s) fputs(s, stdout);
    fflush(stdout);
}

const char *vir_builtin_i_to_str(int64_t n)
{
    char *buf = (char *)malloc(32);
    if (!buf) return "";
    snprintf(buf, 32, "%lld", (long long)n);
    return buf;
}

int64_t vir_builtin_str_to_i(const char *s)
{
    if (!s) return 0;
    return (int64_t)strtoll(s, NULL, 10);
}

void vir_builtin_exit(int64_t code)
{
    exit((int)code);
}

/* ═══════════════════════════════════════════════════════
 * Phase 1 Extensions – File I/O
 * ═══════════════════════════════════════════════════════ */

int64_t vir_builtin_file_open(const char *path, const char *mode)
{
    if (!path || !mode) return 0;
    FILE *f = fopen(path, mode);
    return (int64_t)(intptr_t)f;
}

const char *vir_builtin_file_read(int64_t fd)
{
    FILE *f = (FILE *)(intptr_t)fd;
    if (!f) return "";
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    if (sz < 0) sz = 0;
    fseek(f, 0, SEEK_SET);
    char *buf = (char *)malloc((size_t)sz + 1);
    if (!buf) return "";
    size_t rd = fread(buf, 1, (size_t)sz, f);
    buf[rd] = '\0';
    return buf;
}

void vir_builtin_file_write(int64_t fd, const char *data)
{
    FILE *f = (FILE *)(intptr_t)fd;
    if (f && data) fputs(data, f);
}

void vir_builtin_file_close(int64_t fd)
{
    FILE *f = (FILE *)(intptr_t)fd;
    if (f) fclose(f);
}

void vir_builtin_file_write_byte(int64_t fd, int64_t byte)
{
    FILE *f = (FILE *)(intptr_t)fd;
    if (f) fputc((int)byte, f);
}

/* ═══════════════════════════════════════════════════════
 * Phase 1 Extensions – Array Runtime
 * ═══════════════════════════════════════════════════════
 * Standalone array table for JIT code (separate from VM).
 * Handle-based: arr_new returns an index into the global
 * array table.
 */

#define RT_MAX_ARRAYS 4096

typedef struct {
    int64_t *data;
    uint32_t len;
    uint32_t cap;
} rt_array_t;

static rt_array_t s_rt_arrays[RT_MAX_ARRAYS];
static uint32_t   s_rt_array_count = 0;

int64_t vir_builtin_arr_new(int64_t cap)
{
    if (s_rt_array_count >= RT_MAX_ARRAYS) return -1;
    uint32_t idx = s_rt_array_count++;
    uint32_t c = (uint32_t)(cap > 0 ? cap : 16);
    s_rt_arrays[idx].cap  = c;
    s_rt_arrays[idx].len  = 0;
    s_rt_arrays[idx].data = (int64_t *)calloc(c, sizeof(int64_t));
    return (int64_t)idx;
}

int64_t vir_builtin_arr_len(int64_t handle)
{
    if (handle < 0 || (uint32_t)handle >= s_rt_array_count) return 0;
    return (int64_t)s_rt_arrays[(uint32_t)handle].len;
}

int64_t vir_builtin_arr_get(int64_t handle, int64_t idx)
{
    if (handle < 0 || (uint32_t)handle >= s_rt_array_count) return 0;
    rt_array_t *arr = &s_rt_arrays[(uint32_t)handle];
    if (idx < 0 || (uint32_t)idx >= arr->len) return 0;
    return arr->data[(uint32_t)idx];
}

void vir_builtin_arr_set(int64_t handle, int64_t idx, int64_t val)
{
    if (handle < 0 || (uint32_t)handle >= s_rt_array_count) return;
    rt_array_t *arr = &s_rt_arrays[(uint32_t)handle];
    if (idx < 0 || (uint32_t)idx >= arr->len) return;
    arr->data[(uint32_t)idx] = val;
}

void vir_builtin_arr_push(int64_t handle, int64_t val)
{
    if (handle < 0 || (uint32_t)handle >= s_rt_array_count) return;
    rt_array_t *arr = &s_rt_arrays[(uint32_t)handle];
    if (arr->len >= arr->cap) {
        arr->cap = arr->cap ? arr->cap * 2 : 16;
        arr->data = (int64_t *)realloc(arr->data, arr->cap * sizeof(int64_t));
    }
    arr->data[arr->len++] = val;
}

/* ═══════════════════════════════════════════════════════
 * Global Intrinsic Table
 * ═══════════════════════════════════════════════════════ */

static intrinsic_table_t s_table = { .initialised = 0 };

static void intrinsics_init_once(void)
{
    if (s_table.initialised) return;

#define ENTRY(ID, NAME, FUNC, RTYPE, ARGC, ...) do { \
    s_table.entries[ID] = (intrinsic_desc_t){         \
        .id          = ID,                             \
        .name        = NAME,                           \
        .func_ptr    = (void *)(uintptr_t)(FUNC),      \
        .return_type = RTYPE,                          \
        .arg_count   = ARGC,                           \
        .arg_types   = { __VA_ARGS__ },                \
    };                                                  \
} while(0)

    ENTRY(INTRINSIC_PRINT,     "vir_builtin_print_i64",
          vir_builtin_print_i64,  VIR_TYPE_I64, 1, VIR_TYPE_I64);
    ENTRY(INTRINSIC_PRINT_STR, "vir_builtin_print_str",
          vir_builtin_print_str,  VIR_TYPE_I64, 1, VIR_TYPE_PTR);
    ENTRY(INTRINSIC_INPUT,     "vir_builtin_input_i64",
          vir_builtin_input_i64,  VIR_TYPE_I64, 0, VIR_TYPE_VOID);
    ENTRY(INTRINSIC_INPUT_STR, "vir_builtin_input_str",
          vir_builtin_input_str,  VIR_TYPE_PTR, 0, VIR_TYPE_VOID);
    ENTRY(INTRINSIC_CPU_LOAD,  "vir_builtin_cpu_load",
          vir_builtin_cpu_load,   VIR_TYPE_I64, 0, VIR_TYPE_VOID);
    ENTRY(INTRINSIC_SLEEP_MS,  "vir_builtin_sleep_ms",
          vir_builtin_sleep_ms,   VIR_TYPE_VOID, 1, VIR_TYPE_I64);
    ENTRY(INTRINSIC_ALLOC,     "vir_builtin_alloc",
          vir_builtin_alloc,      VIR_TYPE_PTR, 1, VIR_TYPE_I64);
    ENTRY(INTRINSIC_FREE,      "vir_builtin_free",
          vir_builtin_free,       VIR_TYPE_VOID, 1, VIR_TYPE_PTR);
    ENTRY(INTRINSIC_STRLEN,    "vir_builtin_strlen",
          vir_builtin_strlen,     VIR_TYPE_I64, 1, VIR_TYPE_PTR);

    /* Phase 1 extensions */
    ENTRY(INTRINSIC_STR_GET,   "vir_builtin_str_get",
          vir_builtin_str_get,    VIR_TYPE_I64, 2, VIR_TYPE_PTR, VIR_TYPE_I64);
    ENTRY(INTRINSIC_STR_CAT,   "vir_builtin_str_cat",
          vir_builtin_str_cat,    VIR_TYPE_PTR, 2, VIR_TYPE_PTR, VIR_TYPE_PTR);
    ENTRY(INTRINSIC_STR_EQ,    "vir_builtin_str_eq",
          vir_builtin_str_eq,     VIR_TYPE_I64, 2, VIR_TYPE_PTR, VIR_TYPE_PTR);
    ENTRY(INTRINSIC_PRINT_RAW, "vir_builtin_print_raw",
          vir_builtin_print_raw,  VIR_TYPE_VOID, 1, VIR_TYPE_PTR);
    ENTRY(INTRINSIC_I_TO_STR,  "vir_builtin_i_to_str",
          vir_builtin_i_to_str,   VIR_TYPE_PTR, 1, VIR_TYPE_I64);
    ENTRY(INTRINSIC_STR_TO_I,  "vir_builtin_str_to_i",
          vir_builtin_str_to_i,   VIR_TYPE_I64, 1, VIR_TYPE_PTR);
    ENTRY(INTRINSIC_EXIT,      "vir_builtin_exit",
          vir_builtin_exit,       VIR_TYPE_VOID, 1, VIR_TYPE_I64);
    ENTRY(INTRINSIC_FILE_OPEN, "vir_builtin_file_open",
          vir_builtin_file_open,  VIR_TYPE_I64, 2, VIR_TYPE_PTR, VIR_TYPE_PTR);
    ENTRY(INTRINSIC_FILE_READ, "vir_builtin_file_read",
          vir_builtin_file_read,  VIR_TYPE_PTR, 1, VIR_TYPE_I64);
    ENTRY(INTRINSIC_FILE_WRITE,"vir_builtin_file_write",
          vir_builtin_file_write, VIR_TYPE_VOID, 2, VIR_TYPE_I64, VIR_TYPE_PTR);
    ENTRY(INTRINSIC_FILE_CLOSE,"vir_builtin_file_close",
          vir_builtin_file_close, VIR_TYPE_VOID, 1, VIR_TYPE_I64);
    ENTRY(INTRINSIC_FILE_WRITE_BYTE, "vir_builtin_file_write_byte",
          vir_builtin_file_write_byte, VIR_TYPE_VOID, 2, VIR_TYPE_I64, VIR_TYPE_I64);
    ENTRY(INTRINSIC_ARR_NEW,   "vir_builtin_arr_new",
          vir_builtin_arr_new,    VIR_TYPE_I64, 1, VIR_TYPE_I64);
    ENTRY(INTRINSIC_ARR_LEN,   "vir_builtin_arr_len",
          vir_builtin_arr_len,    VIR_TYPE_I64, 1, VIR_TYPE_I64);
    ENTRY(INTRINSIC_ARR_GET,   "vir_builtin_arr_get",
          vir_builtin_arr_get,    VIR_TYPE_I64, 2, VIR_TYPE_I64, VIR_TYPE_I64);
    ENTRY(INTRINSIC_ARR_SET,   "vir_builtin_arr_set",
          vir_builtin_arr_set,    VIR_TYPE_VOID, 3, VIR_TYPE_I64, VIR_TYPE_I64, VIR_TYPE_I64);
    ENTRY(INTRINSIC_ARR_PUSH,  "vir_builtin_arr_push",
          vir_builtin_arr_push,   VIR_TYPE_VOID, 2, VIR_TYPE_I64, VIR_TYPE_I64);

#undef ENTRY

    s_table.initialised = 1;
}

intrinsic_table_t *vir_intrinsics(void)
{
    intrinsics_init_once();
    return &s_table;
}

const intrinsic_desc_t *vir_intrinsic_get(intrinsic_id_t id)
{
    intrinsics_init_once();
    if ((unsigned)id < INTRINSIC_COUNT)
        return &s_table.entries[id];
    return NULL;
}

void *vir_intrinsic_addr(intrinsic_id_t id)
{
    const intrinsic_desc_t *desc = vir_intrinsic_get(id);
    return desc ? desc->func_ptr : NULL;
}

int vir_opcode_to_intrinsic(q_opcode_t opcode)
{
    switch (opcode) {
    case Q_PRINT:          return INTRINSIC_PRINT;
    case Q_INPUT:          return INTRINSIC_INPUT;
    case Q_ALLOC:          return INTRINSIC_ALLOC;
    case Q_FREE:           return INTRINSIC_FREE;
    case Q_STR_LEN:        return INTRINSIC_STRLEN;
    case Q_STR_GET:        return INTRINSIC_STR_GET;
    case Q_STR_CAT:        return INTRINSIC_STR_CAT;
    case Q_STR_EQ:         return INTRINSIC_STR_EQ;
    case Q_PRINT_STR:      return INTRINSIC_PRINT_RAW;
    case Q_I_TO_STR:       return INTRINSIC_I_TO_STR;
    case Q_STR_TO_I:       return INTRINSIC_STR_TO_I;
    case Q_EXIT:           return INTRINSIC_EXIT;
    case Q_FILE_OPEN:      return INTRINSIC_FILE_OPEN;
    case Q_FILE_READ:      return INTRINSIC_FILE_READ;
    case Q_FILE_WRITE:     return INTRINSIC_FILE_WRITE;
    case Q_FILE_CLOSE:     return INTRINSIC_FILE_CLOSE;
    case Q_FILE_WRITE_BYTE:return INTRINSIC_FILE_WRITE_BYTE;
    case Q_ARR_NEW:        return INTRINSIC_ARR_NEW;
    case Q_ARR_LEN:        return INTRINSIC_ARR_LEN;
    case Q_ARR_GET:        return INTRINSIC_ARR_GET;
    case Q_ARR_SET:        return INTRINSIC_ARR_SET;
    case Q_ARR_PUSH:       return INTRINSIC_ARR_PUSH;
    default:               return -1;
    }
}

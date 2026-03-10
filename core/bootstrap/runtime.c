/*
 * Vir Bootstrap Runtime Library
 *
 * Provides native C implementations of Vir builtins for the
 * self-compiled bootstrap compiler. Linked with the ARM64
 * assembly output to produce a working native binary.
 *
 * Array layout convention:
 *   [capacity:int64] [length:int64] [data[0]] [data[1]] ...
 *                                    ^-- "array pointer" returned to user
 *   capacity at ptr[-2], length at ptr[-1], data at ptr[0..n-1]
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

/* ---- Global argc/argv for get_arg/arg_count ---- */
static int g_argc;
static char **g_argv;

/* ---- Forward declarations of Vir entry points ---- */
extern void vir_init(void);
extern int64_t vir_main(void);

/* ---- C entry point ---- */
int main(int argc, char **argv) {
    g_argc = argc - 1;       /* skip program name */
    g_argv = argv + 1;       /* shift past program name */
    vir_init();
    return (int)vir_main();
}

/* ---- Array: push ---- */
/* push(arr_ptr, val) -> returns (possibly new) arr_ptr */
int64_t push(int64_t arr_ptr, int64_t val) {
    int64_t *data = (int64_t *)arr_ptr;
    int64_t len = data[-1];
    int64_t cap = data[-2];

    if (len >= cap) {
        int64_t new_cap = cap * 2;
        if (new_cap < 64) new_cap = 64;
        int64_t *new_base = (int64_t *)malloc((size_t)(new_cap * 8 + 16));
        new_base[0] = new_cap;
        new_base[1] = len;
        memcpy(&new_base[2], data, (size_t)(len * 8));
        free(data - 2);
        data = &new_base[2];
        arr_ptr = (int64_t)data;
    }

    data[len] = val;
    data[-1] = len + 1;
    return arr_ptr;
}

/* ---- String/array length ---- */
/* len(ptr) -> for strings: strlen; arrays track length in header */
int64_t len(int64_t ptr) {
    return (int64_t)strlen((const char *)ptr);
}

/* ---- String concatenation ---- */
int64_t str_cat(int64_t s1, int64_t s2) {
    const char *a = (const char *)s1;
    const char *b = (const char *)s2;
    size_t la = strlen(a);
    size_t lb = strlen(b);
    char *result = (char *)malloc(la + lb + 1);
    memcpy(result, a, la);
    memcpy(result + la, b, lb + 1); /* includes null terminator */
    return (int64_t)result;
}

/* ---- String indexing ---- */
/* str_get(s, idx) -> byte value at index, or 0 if out of bounds */
int64_t str_get(int64_t s, int64_t idx) {
    const char *str = (const char *)s;
    if (idx < 0) return 0;
    size_t slen = strlen(str);
    if ((size_t)idx >= slen) return 0;
    return (int64_t)(unsigned char)str[idx];
}

/* ---- String equality ---- */
int64_t str_eq(int64_t s1, int64_t s2) {
    return strcmp((const char *)s1, (const char *)s2) == 0 ? 1 : 0;
}

/* ---- File I/O ---- */
int64_t file_open(int64_t path, int64_t mode) {
    FILE *f = fopen((const char *)path, (const char *)mode);
    return (int64_t)f;
}

int64_t file_read(int64_t fd) {
    FILE *f = (FILE *)fd;
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = (char *)malloc((size_t)(size + 1));
    fread(buf, 1, (size_t)size, f);
    buf[size] = '\0';
    return (int64_t)buf;
}

void file_close(int64_t fd) {
    fclose((FILE *)fd);
}

/* ---- Integer to string ---- */
int64_t i_to_str(int64_t n) {
    char *buf = (char *)malloc(32);
    snprintf(buf, 32, "%lld", (long long)n);
    return (int64_t)buf;
}

/* ---- Command-line arguments ---- */
int64_t arg_count(void) {
    return (int64_t)g_argc;
}

int64_t get_arg(int64_t idx) {
    if (idx < 0 || idx >= g_argc) return 0;
    return (int64_t)g_argv[idx];
}

/* ---- Memory management ---- */
int64_t alloc(int64_t nbytes) {
    return (int64_t)malloc((size_t)nbytes);
}

void dealloc(int64_t ptr) {
    free((void *)ptr);
}

/* ---- Byte-level memory access ---- */
void write_byte(int64_t addr, int64_t offset, int64_t byte_val) {
    *((unsigned char *)addr + offset) = (unsigned char)byte_val;
}

/* ---- Output ---- */
void print_str(int64_t s) {
    fputs((const char *)s, stdout);
}

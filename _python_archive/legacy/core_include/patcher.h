/*
 * patcher.h – Binary Patcher & JIT Memory
 * =========================================
 * Spec §3.2 – Jump Table Indirection, runtime code patching.
 *
 * 1. Cấp phát vùng nhớ RWX (MAP_JIT trên Mac)
 * 2. Xây dựng Jump Table (ban đầu trỏ Bản A)
 * 3. Vá JMP target → Bản B khi CPU rảnh
 */

#ifndef VIR_PATCHER_H
#define VIR_PATCHER_H

#include "codegen.h"
#include <stdint.h>
#include <stddef.h>
#include <pthread.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * JIT Region – vùng nhớ thực thi được
 * ═══════════════════════════════════════════════════════ */
typedef struct {
    uint8_t  *base;       /* Địa chỉ cơ sở                */
    size_t    size;       /* Kích thước đã cấp phát        */
    size_t    used;       /* Số byte đã sử dụng            */
    int       has_exec;   /* 1 if memory is executable     */
} jit_region_t;

int  jit_region_alloc(jit_region_t *region, size_t size);
void jit_region_free(jit_region_t *region);
int  jit_region_write(jit_region_t *region, size_t offset, const void *data, size_t len);
int  jit_region_make_writable(jit_region_t *region);
int  jit_region_make_executable(jit_region_t *region);

/* ═══════════════════════════════════════════════════════
 * Jump Table Entry
 * ═══════════════════════════════════════════════════════ */
typedef struct {
    uint32_t  patch_id;
    size_t    jmp_offset;    /* Offset trong region nơi lệnh JMP nằm   */
    size_t    safe_offset;   /* Offset → Bản A code                     */
    size_t    fast_offset;   /* Offset → Bản B code                     */
    size_t    safe_size;
    size_t    fast_size;
    int       is_patched;    /* 0 = safe, 1 = fast                      */
} jump_entry_t;

/* ═══════════════════════════════════════════════════════
 * Patcher State
 * ═══════════════════════════════════════════════════════ */
#define PATCHER_MAX_ENTRIES 256

typedef struct {
    jit_region_t   region;
    jump_entry_t   entries[PATCHER_MAX_ENTRIES];
    uint32_t       entry_count;
    target_arch_t  arch;
    pthread_mutex_t lock;
} patcher_t;

/* ── API ─────────────────────────────────────────────── */

int  patcher_init(patcher_t *p, target_arch_t arch, size_t region_size);
void patcher_free(patcher_t *p);

/* Xây dựng jump table từ code variants */
int  patcher_build(patcher_t *p, const codegen_result_t *variants);

/* Vá: Safe → Fast (Spec §3.2.3) */
int  patcher_patch_to_fast(patcher_t *p, uint32_t patch_id);

/* Rollback: Fast → Safe */
int  patcher_patch_to_safe(patcher_t *p, uint32_t patch_id);

/* Vá tất cả */
int  patcher_patch_all_fast(patcher_t *p);
int  patcher_patch_all_safe(patcher_t *p);

/* Query */
int  patcher_is_patched(const patcher_t *p, uint32_t patch_id);
const jump_entry_t* patcher_find_entry(const patcher_t *p, uint32_t patch_id);

/* Thực thi patch point (gọi qua function pointer) */
typedef int64_t (*jit_func_t)(int64_t arg0, int64_t arg1);
jit_func_t patcher_get_entry_point(const patcher_t *p, uint32_t patch_id);

#ifdef __cplusplus
}
#endif

#endif /* VIR_PATCHER_H */

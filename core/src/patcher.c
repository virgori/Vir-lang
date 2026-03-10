/*
 * patcher.c – Self-Patching Binary Engine
 * ═══════════════════════════════════════════
 * Spec §3.2.3 – Jump Table Indirection & Runtime Patching.
 *
 * Manages JIT memory regions, jump tables, and performs
 * atomic code patching from Bản A (Safe) → Bản B (Fast)
 * when CPU pressure is low.
 */

#include "patcher.h"
#include "bridge.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

/* External ASM routines */
#if defined(__aarch64__) || defined(__arm64__)
extern void vir_asm_flush_icache(void *addr, uint64_t size);
#endif

/* ARM64 B imm26 range: ±128 MB (26-bit signed × 4) */
#define ARM64_B_MAX_RANGE  ((int64_t)0x7FFFFFF * 4)   /* +134217724 */
#define ARM64_B_MIN_RANGE  ((int64_t)-0x8000000 * 4)  /* -134217728 */

static int arm64_check_branch_range(int64_t disp)
{
    if (disp < ARM64_B_MIN_RANGE || disp > ARM64_B_MAX_RANGE) {
        fprintf(stderr, "[patcher] ARM64 B offset %lld out of ±128MB range\n",
                (long long)disp);
        return -1;
    }
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * JIT Region Management
 * ═══════════════════════════════════════════════════════ */

int jit_region_alloc(jit_region_t *region, size_t size)
{
    memset(region, 0, sizeof(*region));
    region->size = size;

    region->base = (uint8_t *)bridge_jit_alloc(size);
    if (!region->base) {
        fprintf(stderr, "[patcher] Failed to allocate JIT region of %zu bytes\n", size);
        return -1;
    }

    region->used = 0;
    region->has_exec = 0;
    return 0;
}

void jit_region_free(jit_region_t *region)
{
    if (region->base) {
        bridge_jit_free(region->base, region->size);
        region->base = NULL;
    }
    region->size = 0;
    region->used = 0;
    region->has_exec = 0;
}

int jit_region_write(jit_region_t *region, size_t offset, const void *data, size_t len)
{
    if (offset + len > region->size) {
        fprintf(stderr, "[patcher] JIT region write overflow: %zu + %zu > %zu\n",
                offset, len, region->size);
        return -1;
    }

    /* Ensure writable */
    if (region->has_exec) {
        jit_region_make_writable(region);
    }

    memcpy(region->base + offset, data, len);

    /* Track high watermark */
    if (offset + len > region->used) {
        region->used = offset + len;
    }

    return 0;
}

int jit_region_make_writable(jit_region_t *region)
{
#if defined(__APPLE__) && defined(__aarch64__)
    bridge_jit_write_protect(0);
#endif
    int rc = bridge_mprotect(region->base, region->size,
                             BRIDGE_PROT_READ | BRIDGE_PROT_WRITE);
    if (rc == 0) region->has_exec = 0;
    return rc;
}

int jit_region_make_executable(jit_region_t *region)
{
    int rc = bridge_mprotect(region->base, region->size,
                             BRIDGE_PROT_READ | BRIDGE_PROT_EXEC);
    if (rc == 0) region->has_exec = 1;

#if defined(__APPLE__) && defined(__aarch64__)
    bridge_jit_write_protect(1);
    vir_asm_flush_icache(region->base, region->used);
#endif

    return rc;
}

/* ═══════════════════════════════════════════════════════
 * Patcher: Init / Free
 * ═══════════════════════════════════════════════════════ */

int patcher_init(patcher_t *p, target_arch_t arch, size_t region_size)
{
    memset(p, 0, sizeof(*p));
    pthread_mutex_init(&p->lock, NULL);
    p->arch = arch;
    p->entry_count = 0;

    if (jit_region_alloc(&p->region, region_size) != 0)
        return -1;

    return 0;
}

void patcher_free(patcher_t *p)
{
    jit_region_free(&p->region);
    p->entry_count = 0;
    pthread_mutex_destroy(&p->lock);
}

/* ═══════════════════════════════════════════════════════
 * Build Jump Table from Code Variants
 * ═══════════════════════════════════════════════════════ */

int patcher_build(patcher_t *p, const codegen_result_t *variants)
{
    size_t offset = 0;

    for (uint32_t i = 0; i < variants->count; i++) {
        if (p->entry_count >= PATCHER_MAX_ENTRIES) {
            fprintf(stderr, "[patcher] Max entries exceeded\n");
            return -1;
        }

        const code_variant_t *v = &variants->variants[i];
        jump_entry_t *e = &p->entries[p->entry_count];
        memset(e, 0, sizeof(*e));
        e->patch_id = v->patch_id;

        /* ── Write JMP trampoline ────────────────────── */
        e->jmp_offset = offset;
        if (p->arch == ARCH_X86_64) {
            /* x86_64: JMP rel32 = E9 xx xx xx xx (5 bytes) */
            uint8_t jmp_stub[5] = { 0xE9, 0x00, 0x00, 0x00, 0x00 };
            jit_region_write(&p->region, offset, jmp_stub, 5);
            offset += 5;
            /* Align to 16 bytes */
            while (offset & 0xF) {
                uint8_t nop = 0x90;
                jit_region_write(&p->region, offset, &nop, 1);
                offset++;
            }
        } else if (p->arch == ARCH_ARM64) {
            /* ARM64: B imm26 = 0x14000000 (4 bytes) */
            uint32_t b_stub = 0x14000000;
            jit_region_write(&p->region, offset, &b_stub, 4);
            offset += 4;
            /* Align to 16 bytes */
            while (offset & 0xF) {
                uint32_t nop = 0xD503201F;
                jit_region_write(&p->region, offset, &nop, 4);
                offset += 4;
            }
        }

        /* ── Write Bản A (Safe code) ─────────────────── */
        e->safe_offset = offset;
        e->safe_size = v->safe_code.len;
        jit_region_write(&p->region, offset, v->safe_code.data, v->safe_code.len);
        offset += v->safe_code.len;
        /* Align */
        while (offset & 0xF) offset++;

        /* ── Write Bản B (Fast code) ─────────────────── */
        e->fast_offset = offset;
        e->fast_size = v->fast_code.len;
        jit_region_write(&p->region, offset, v->fast_code.data, v->fast_code.len);
        offset += v->fast_code.len;
        while (offset & 0xF) offset++;

        /* ── Patch JMP to point to safe code initially ── */
        if (p->arch == ARCH_X86_64) {
            int32_t rel = (int32_t)(e->safe_offset - (e->jmp_offset + 5));
            jit_region_write(&p->region, e->jmp_offset + 1, &rel, 4);
        } else if (p->arch == ARCH_ARM64) {
            int64_t disp = (int64_t)(e->safe_offset - e->jmp_offset);
            if (arm64_check_branch_range(disp) != 0) return -1;
            uint32_t imm26 = ((uint32_t)(disp >> 2)) & 0x03FFFFFF;
            uint32_t instr = 0x14000000 | imm26;
            jit_region_write(&p->region, e->jmp_offset, &instr, 4);
        }

        e->is_patched = 0;
        p->entry_count++;
    }

    /* Make the whole region executable */
    jit_region_make_executable(&p->region);

    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Find entry by patch_id
 * ═══════════════════════════════════════════════════════ */

const jump_entry_t *patcher_find_entry(const patcher_t *p, uint32_t patch_id)
{
    for (uint32_t i = 0; i < p->entry_count; i++) {
        if (p->entries[i].patch_id == patch_id)
            return &p->entries[i];
    }
    return NULL;
}

static jump_entry_t *patcher_find_mut(patcher_t *p, uint32_t patch_id)
{
    for (uint32_t i = 0; i < p->entry_count; i++) {
        if (p->entries[i].patch_id == patch_id)
            return &p->entries[i];
    }
    return NULL;
}

/* ═══════════════════════════════════════════════════════
 * Patch: Safe → Fast (Spec §3.2.3)
 * ═══════════════════════════════════════════════════════ */

int patcher_patch_to_fast(patcher_t *p, uint32_t patch_id)
{
    pthread_mutex_lock(&p->lock);
    jump_entry_t *e = patcher_find_mut(p, patch_id);
    if (!e) { pthread_mutex_unlock(&p->lock); return -1; }
    if (e->is_patched) { pthread_mutex_unlock(&p->lock); return 0; }

    jit_region_make_writable(&p->region);

    if (p->arch == ARCH_X86_64) {
        int32_t rel = (int32_t)(e->fast_offset - (e->jmp_offset + 5));
        memcpy(p->region.base + e->jmp_offset + 1, &rel, 4);
    } else if (p->arch == ARCH_ARM64) {
        int64_t disp = (int64_t)(e->fast_offset - e->jmp_offset);
        if (arm64_check_branch_range(disp) != 0) {
            pthread_mutex_unlock(&p->lock);
            return -1;
        }
        uint32_t imm26 = ((uint32_t)(disp >> 2)) & 0x03FFFFFF;
        uint32_t instr = 0x14000000 | imm26;
        memcpy(p->region.base + e->jmp_offset, &instr, 4);
    }

    e->is_patched = 1;
    jit_region_make_executable(&p->region);
    pthread_mutex_unlock(&p->lock);
    return 0;
}

/* ── Rollback: Fast → Safe ────────────────────────────── */

int patcher_patch_to_safe(patcher_t *p, uint32_t patch_id)
{
    pthread_mutex_lock(&p->lock);
    jump_entry_t *e = patcher_find_mut(p, patch_id);
    if (!e) { pthread_mutex_unlock(&p->lock); return -1; }
    if (!e->is_patched) { pthread_mutex_unlock(&p->lock); return 0; }

    jit_region_make_writable(&p->region);

    if (p->arch == ARCH_X86_64) {
        int32_t rel = (int32_t)(e->safe_offset - (e->jmp_offset + 5));
        memcpy(p->region.base + e->jmp_offset + 1, &rel, 4);
    } else if (p->arch == ARCH_ARM64) {
        int64_t disp = (int64_t)(e->safe_offset - e->jmp_offset);
        if (arm64_check_branch_range(disp) != 0) {
            pthread_mutex_unlock(&p->lock);
            return -1;
        }
        uint32_t imm26 = ((uint32_t)(disp >> 2)) & 0x03FFFFFF;
        uint32_t instr = 0x14000000 | imm26;
        memcpy(p->region.base + e->jmp_offset, &instr, 4);
    }

    e->is_patched = 0;
    jit_region_make_executable(&p->region);
    pthread_mutex_unlock(&p->lock);
    return 0;
}

/* ── Patch all / revert all ───────────────────────────── */

int patcher_patch_all_fast(patcher_t *p)
{
    int count = 0;
    for (uint32_t i = 0; i < p->entry_count; i++) {
        if (!p->entries[i].is_patched) {
            if (patcher_patch_to_fast(p, p->entries[i].patch_id) == 0)
                count++;
        }
    }
    return count;
}

int patcher_patch_all_safe(patcher_t *p)
{
    int count = 0;
    for (uint32_t i = 0; i < p->entry_count; i++) {
        if (p->entries[i].is_patched) {
            if (patcher_patch_to_safe(p, p->entries[i].patch_id) == 0)
                count++;
        }
    }
    return count;
}

/* ── Query ────────────────────────────────────────────── */

int patcher_is_patched(const patcher_t *p, uint32_t patch_id)
{
    const jump_entry_t *e = patcher_find_entry(p, patch_id);
    return e ? e->is_patched : -1;
}

jit_func_t patcher_get_entry_point(const patcher_t *p, uint32_t patch_id)
{
    const jump_entry_t *e = patcher_find_entry(p, patch_id);
    if (!e) return NULL;
    return (jit_func_t)(p->region.base + e->jmp_offset);
}

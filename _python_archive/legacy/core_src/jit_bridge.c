/*
 * jit_bridge.c – JIT Bridge Singleton Implementation
 * ====================================================
 * Pure C.  No Python, no external runtime, no heap per call.
 *
 * The bridge owns one large mmap'd region for all JIT code.
 * Callback addresses are stored in a contiguous table so
 * that machine code can reach them with a single indirect CALL:
 *
 *   x86_64:   MOV RAX, [table + slot*8]
 *             CALL RAX
 *
 *   ARM64:    LDR X16, [table_base, #slot*8]
 *             BLR X16
 */

#include "jit_bridge.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <pthread.h>

/* ═══════════════════════════════════════════════════════
 * Lifecycle
 * ═══════════════════════════════════════════════════════ */

int jit_bridge_init(jit_bridge_t *jb, size_t region_size)
{
    if (jb->initialised) return 0;  /* idempotent */

    memset(jb, 0, sizeof(*jb));
    pthread_mutex_init(&jb->lock, NULL);

    jb->arch = codegen_detect_arch();
    jb->abi  = bridge_get_abi(jb->arch);

    /* Allocate executable region (starts RW on most platforms) */
    jb->region_base = (uint8_t *)bridge_alloc_executable(region_size);
    if (!jb->region_base) {
        fprintf(stderr, "[jit_bridge] Failed to allocate %zu bytes\n",
                region_size);
        return -1;
    }
    jb->region_size       = region_size;
    jb->region_used       = 0;
    jb->region_executable = 0;

    /* Init sub-systems.
     * The patcher gets its own small region (1 page) for jump
     * table entries; actual JIT code goes into region_base. */
    patcher_init(&jb->patcher, jb->arch, 4096);
    signer_init(&jb->signer, NULL);  /* random session key */

    jb->initialised = 1;
    return 0;
}

void jit_bridge_destroy(jit_bridge_t *jb)
{
    if (!jb->initialised) return;

    if (jb->region_base) {
        bridge_jit_free(jb->region_base, jb->region_size);
    }
    patcher_free(&jb->patcher);
    pthread_mutex_destroy(&jb->lock);
    memset(jb, 0, sizeof(*jb));
}

/* Global singleton */
static jit_bridge_t s_global_bridge = { .initialised = 0 };
static pthread_once_t s_global_once = PTHREAD_ONCE_INIT;

static void jit_bridge_global_init_once(void)
{
    jit_bridge_init(&s_global_bridge, 1024 * 1024); /* 1 MB */
}

jit_bridge_t *jit_bridge_global(void)
{
    pthread_once(&s_global_once, jit_bridge_global_init_once);
    return &s_global_bridge;
}

/* ═══════════════════════════════════════════════════════
 * Callback Registration
 * ═══════════════════════════════════════════════════════ */

int jit_bridge_register(jit_bridge_t *jb,
                        const char *name, void *func_addr,
                        uint8_t arg_count, vir_type_t ret_type)
{
    pthread_mutex_lock(&jb->lock);
    if (jb->callback_count >= JIT_MAX_CALLBACKS) {
        pthread_mutex_unlock(&jb->lock);
        return -1;
    }

    uint32_t slot = jb->callback_count;
    jb->callbacks[slot] = (jit_callback_t){
        .name      = name,
        .addr      = func_addr,
        .arg_count = arg_count,
        .ret_type  = ret_type,
    };
    jb->callback_table[slot] = func_addr;
    jb->callback_count++;
    pthread_mutex_unlock(&jb->lock);
    return (int)slot;
}

int jit_bridge_register_intrinsics(jit_bridge_t *jb)
{
    intrinsic_table_t *tbl = vir_intrinsics();
    int count = 0;

    for (int i = 0; i < INTRINSIC_COUNT; i++) {
        const intrinsic_desc_t *desc = &tbl->entries[i];
        if (desc->func_ptr) {
            int rc = jit_bridge_register(jb, desc->name, desc->func_ptr,
                                         desc->arg_count, desc->return_type);
            if (rc >= 0) count++;
        }
    }
    return count;
}

void *jit_bridge_lookup(const jit_bridge_t *jb, const char *name)
{
    for (uint32_t i = 0; i < jb->callback_count; i++) {
        if (strcmp(jb->callbacks[i].name, name) == 0)
            return jb->callbacks[i].addr;
    }
    return NULL;
}

void **jit_bridge_callback_table(jit_bridge_t *jb)
{
    return jb->callback_table;
}

/* ═══════════════════════════════════════════════════════
 * Machine Code Call Thunks
 * ═══════════════════════════════════════════════════════
 *
 * Emit a sequence of machine code bytes into `cb` that
 * loads the absolute address of callback[slot] into a
 * scratch register and performs an indirect CALL.
 *
 * x86_64:
 *   48 B8 <8 bytes addr>   ; MOV RAX, imm64
 *   FF D0                   ; CALL RAX
 *
 * ARM64:
 *   MOVZ X16, #addr[15:0]
 *   MOVK X16, #addr[31:16], LSL #16
 *   MOVK X16, #addr[47:32], LSL #32
 *   MOVK X16, #addr[63:48], LSL #48
 *   BLR  X16
 */

int jit_bridge_emit_call_thunk(const jit_bridge_t *jb,
                               codebuf_t *cb,
                               uint32_t callback_slot)
{
    if (callback_slot >= jb->callback_count) return -1;

    void *addr = jb->callback_table[callback_slot];
    uint64_t uaddr = (uint64_t)(uintptr_t)addr;

    if (jb->arch == ARCH_X86_64) {
        /* MOV RAX, imm64 */
        codebuf_emit_byte(cb, 0x48);
        codebuf_emit_byte(cb, 0xB8);
        codebuf_emit_u64(cb, uaddr);
        /* CALL RAX */
        codebuf_emit_byte(cb, 0xFF);
        codebuf_emit_byte(cb, 0xD0);
    }
    else if (jb->arch == ARCH_ARM64) {
        uint32_t rd = 16;  /* X16 = intra-procedure scratch */

        /* MOVZ X16, #low16 */
        uint32_t ins = 0xD2800000 | (((uint32_t)(uaddr & 0xFFFF)) << 5)
                       | (rd & 0x1F);
        codebuf_emit_u32(cb, ins);

        /* MOVK X16, #mid16, LSL #16 */
        if (uaddr >> 16) {
            ins = 0xF2A00000 | (((uint32_t)((uaddr >> 16) & 0xFFFF)) << 5)
                  | (rd & 0x1F);
            codebuf_emit_u32(cb, ins);
        }

        /* MOVK X16, #high16, LSL #32 */
        if (uaddr >> 32) {
            ins = 0xF2C00000 | (((uint32_t)((uaddr >> 32) & 0xFFFF)) << 5)
                  | (rd & 0x1F);
            codebuf_emit_u32(cb, ins);
        }

        /* MOVK X16, #top16, LSL #48 */
        if (uaddr >> 48) {
            ins = 0xF2E00000 | (((uint32_t)((uaddr >> 48) & 0xFFFF)) << 5)
                  | (rd & 0x1F);
            codebuf_emit_u32(cb, ins);
        }

        /* BLR X16 → 1101_0110_0011_1111_0000_00 Rn 00000 */
        ins = 0xD63F0000 | ((rd & 0x1F) << 5);
        codebuf_emit_u32(cb, ins);
    }
    else {
        return -1;  /* unsupported arch */
    }

    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Code Emission
 * ═══════════════════════════════════════════════════════ */

int jit_bridge_emit_code(jit_bridge_t *jb, uint32_t block_id,
                         const uint8_t *code, size_t code_len)
{
    pthread_mutex_lock(&jb->lock);
    if (jb->block_count >= JIT_MAX_BLOCKS) {
        pthread_mutex_unlock(&jb->lock);
        return -1;
    }

    /* Align to 16 bytes for code alignment */
    size_t aligned = (jb->region_used + 15) & ~(size_t)15;
    if (aligned + code_len > jb->region_size) {
        pthread_mutex_unlock(&jb->lock);
        return -1;
    }

    /* Must be writable */
    if (jb->region_executable) {
        bridge_make_writable(jb->region_base, jb->region_size);
        jb->region_executable = 0;
    }

    /* On macOS ARM64 with MAP_JIT, toggle W^X to writable */
    bridge_jit_write_protect(0);

    memcpy(jb->region_base + aligned, code, code_len);

    /* Record block */
    uint32_t idx = jb->block_count;
    jb->blocks[idx].id     = block_id;
    jb->blocks[idx].offset = aligned;
    jb->blocks[idx].size   = code_len;

    /* Compute code hash and sign */
    sha256_hash(code, code_len, jb->blocks[idx].signature);
    signer_sign(&jb->signer, block_id, code, code_len);
    jb->blocks[idx].verified = 1;

    jb->region_used = aligned + code_len;
    jb->block_count++;
    pthread_mutex_unlock(&jb->lock);
    return (int)idx;
}

/* ═══════════════════════════════════════════════════════
 * Memory Protection
 * ═══════════════════════════════════════════════════════ */

int jit_bridge_finalise(jit_bridge_t *jb)
{
    if (jb->region_executable) return 0;

    int rc = bridge_make_executable(jb->region_base, jb->region_size);
    if (rc == 0) {
        jb->region_executable = 1;
        bridge_flush_icache(jb->region_base, jb->region_used);
    }
    return rc;
}

int jit_bridge_begin_patch(jit_bridge_t *jb)
{
    pthread_mutex_lock(&jb->lock);
    if (!jb->region_executable) {
        pthread_mutex_unlock(&jb->lock);
        return 0;
    }

    int rc = bridge_make_writable(jb->region_base, jb->region_size);
    if (rc == 0) jb->region_executable = 0;
    pthread_mutex_unlock(&jb->lock);
    return rc;
}

int jit_bridge_end_patch(jit_bridge_t *jb)
{
    pthread_mutex_lock(&jb->lock);
    /* Re-sign all modified blocks */
    for (uint32_t i = 0; i < jb->block_count; i++) {
        jit_block_t *b = &jb->blocks[i];
        const uint8_t *code = jb->region_base + b->offset;
        signer_sign(&jb->signer, b->id, code, b->size);
        sha256_hash(code, b->size, b->signature);
        b->verified = 1;
    }

    int rc = jit_bridge_finalise(jb);
    pthread_mutex_unlock(&jb->lock);
    return rc;
}

/* ═══════════════════════════════════════════════════════
 * Execution
 * ═══════════════════════════════════════════════════════ */

jit_entry_fn jit_bridge_get_entry(const jit_bridge_t *jb,
                                  uint32_t block_id)
{
    for (uint32_t i = 0; i < jb->block_count; i++) {
        if (jb->blocks[i].id == block_id) {
            if (!jb->region_executable) return NULL;
            void *ptr = jb->region_base + jb->blocks[i].offset;
            return (jit_entry_fn)ptr;
        }
    }
    return NULL;
}

/* ═══════════════════════════════════════════════════════
 * Integrity Verification
 * ═══════════════════════════════════════════════════════ */

int jit_bridge_verify_block(const jit_bridge_t *jb, uint32_t block_id)
{
    for (uint32_t i = 0; i < jb->block_count; i++) {
        if (jb->blocks[i].id == block_id) {
            const uint8_t *code = jb->region_base + jb->blocks[i].offset;
            return signer_verify(&jb->signer, block_id,
                                 code, jb->blocks[i].size);
        }
    }
    return -1;  /* not found */
}

int jit_bridge_verify_all(const jit_bridge_t *jb)
{
    for (uint32_t i = 0; i < jb->block_count; i++) {
        if (jit_bridge_verify_block(jb, jb->blocks[i].id) != 0)
            return -1;
    }
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Redundancy Patching (Rollback)
 * ═══════════════════════════════════════════════════════
 *
 * Emit both Safe (Bản A) and Fast (Bản B) variants into the
 * JIT region.  The active entry starts at Safe code.
 *
 * Layout in region:
 *   [safe_code ...]  [fast_code ...]
 *   ^                ^
 *   block.safe_offset  block.fast_offset
 *
 * block.offset always points to whichever variant is active.
 * Switching = update offset + re-sign + icache flush.
 */

static jit_block_t *jit_block_find_mut(jit_bridge_t *jb, uint32_t id)
{
    for (uint32_t i = 0; i < jb->block_count; i++) {
        if (jb->blocks[i].id == id) return &jb->blocks[i];
    }
    return NULL;
}

int jit_bridge_emit_dual(jit_bridge_t *jb, uint32_t block_id,
                         const uint8_t *safe_code, size_t safe_len,
                         const uint8_t *fast_code, size_t fast_len)
{
    pthread_mutex_lock(&jb->lock);
    if (jb->block_count >= JIT_MAX_BLOCKS) {
        pthread_mutex_unlock(&jb->lock);
        return -1;
    }

    /* Ensure writable */
    if (jb->region_executable) {
        bridge_make_writable(jb->region_base, jb->region_size);
        jb->region_executable = 0;
    }
    bridge_jit_write_protect(0);

    /* Align safe code to 16 bytes */
    size_t safe_off = (jb->region_used + 15) & ~(size_t)15;
    if (safe_off + safe_len > jb->region_size) {
        pthread_mutex_unlock(&jb->lock);
        return -1;
    }
    memcpy(jb->region_base + safe_off, safe_code, safe_len);

    /* Align fast code to 16 bytes */
    size_t fast_off = (safe_off + safe_len + 15) & ~(size_t)15;
    if (fast_off + fast_len > jb->region_size) {
        pthread_mutex_unlock(&jb->lock);
        return -1;
    }
    memcpy(jb->region_base + fast_off, fast_code, fast_len);

    /* Record block – active = safe initially */
    uint32_t idx = jb->block_count;
    jit_block_t *b = &jb->blocks[idx];
    memset(b, 0, sizeof(*b));
    b->id          = block_id;
    b->offset      = safe_off;   /* active entry point */
    b->size        = safe_len;
    b->safe_offset = safe_off;
    b->safe_size   = safe_len;
    b->fast_offset = fast_off;
    b->fast_size   = fast_len;
    b->is_fast     = 0;

    /* Sign safe code */
    sha256_hash(safe_code, safe_len, b->signature);
    signer_sign(&jb->signer, block_id, safe_code, safe_len);
    b->verified = 1;

    jb->region_used = fast_off + fast_len;
    jb->block_count++;
    pthread_mutex_unlock(&jb->lock);
    return (int)idx;
}

int jit_bridge_patch_to_fast(jit_bridge_t *jb, uint32_t block_id)
{
    pthread_mutex_lock(&jb->lock);
    jit_block_t *b = jit_block_find_mut(jb, block_id);
    if (!b || b->fast_size == 0) { pthread_mutex_unlock(&jb->lock); return -1; }
    if (b->is_fast) { pthread_mutex_unlock(&jb->lock); return 0; }
    if (b->permanent_safe) { pthread_mutex_unlock(&jb->lock); return -2; }

    /* Switch active entry to fast variant */
    b->offset  = b->fast_offset;
    b->size    = b->fast_size;
    b->is_fast = 1;

    /* Re-sign fast code */
    const uint8_t *code = jb->region_base + b->fast_offset;
    sha256_hash(code, b->fast_size, b->signature);
    signer_sign(&jb->signer, block_id, code, b->fast_size);
    b->verified = 1;

    /* Flush icache so CPU sees the right target */
    bridge_flush_icache(jb->region_base + b->fast_offset, b->fast_size);
    pthread_mutex_unlock(&jb->lock);
    return 0;
}

/* Internal rollback without lock (caller must hold jb->lock) */
static int jit_bridge_rollback_unlocked(jit_bridge_t *jb, uint32_t block_id)
{
    jit_block_t *b = jit_block_find_mut(jb, block_id);
    if (!b) return -1;
    if (!b->is_fast) return 0;

    b->offset  = b->safe_offset;
    b->size    = b->safe_size;
    b->is_fast = 0;
    b->rollback_count++;

    if (jb->blacklist_threshold > 0 &&
        b->rollback_count >= jb->blacklist_threshold) {
        b->permanent_safe = 1;
    }

    const uint8_t *code = jb->region_base + b->safe_offset;
    sha256_hash(code, b->safe_size, b->signature);
    signer_sign(&jb->signer, block_id, code, b->safe_size);
    b->verified = 1;

    bridge_flush_icache(jb->region_base + b->safe_offset, b->safe_size);
    return 0;
}

int jit_bridge_rollback(jit_bridge_t *jb, uint32_t block_id)
{
    pthread_mutex_lock(&jb->lock);
    int rc = jit_bridge_rollback_unlocked(jb, block_id);
    pthread_mutex_unlock(&jb->lock);
    return rc;
}

int jit_bridge_report_fault(jit_bridge_t *jb, uint32_t block_id,
                            uint32_t max_faults)
{
    pthread_mutex_lock(&jb->lock);
    jit_block_t *b = jit_block_find_mut(jb, block_id);
    if (!b) { pthread_mutex_unlock(&jb->lock); return -1; }

    b->fast_fail_count++;

    if (b->is_fast && b->fast_fail_count >= max_faults) {
        jit_bridge_rollback_unlocked(jb, block_id);
        pthread_mutex_unlock(&jb->lock);
        return 1;  /* rollback triggered */
    }
    pthread_mutex_unlock(&jb->lock);
    return 0;  /* still fast */
}

int jit_bridge_is_fast(const jit_bridge_t *jb, uint32_t block_id)
{
    for (uint32_t i = 0; i < jb->block_count; i++) {
        if (jb->blocks[i].id == block_id)
            return jb->blocks[i].is_fast;
    }
    return -1;  /* not found */
}

/* ═══════════════════════════════════════════════════════
 * Blacklist (PERMANENT_SAFE)
 * ═══════════════════════════════════════════════════════ */

void jit_bridge_set_blacklist_threshold(jit_bridge_t *jb, uint32_t threshold)
{
    jb->blacklist_threshold = threshold;
}

int jit_bridge_is_blacklisted(const jit_bridge_t *jb, uint32_t block_id)
{
    for (uint32_t i = 0; i < jb->block_count; i++) {
        if (jb->blocks[i].id == block_id)
            return jb->blocks[i].permanent_safe;
    }
    return -1;  /* not found */
}

/*
 * test_arena.c — Tests for Arena v2 (page-chain + watermark)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "../include/mem_manager.h"

static int tests_passed = 0;
static int tests_failed = 0;

#define TEST(name) do { printf("  TEST: %-40s", name); } while(0)
#define PASS()     do { printf("OK\n"); tests_passed++; } while(0)
#define FAIL(msg)  do { printf("FAIL: %s\n", msg); tests_failed++; } while(0)

/* ── Test 1: Basic create + alloc ─────────────────────── */
static void test_basic_alloc(void) {
    TEST("basic create + alloc");
    int id = vir_arena_create(4096);
    assert(id >= 0);

    void *p1 = vir_arena_alloc(id, 64);
    assert(p1 != NULL);
    void *p2 = vir_arena_alloc(id, 128);
    assert(p2 != NULL);
    assert(p2 != p1);

    size_t used = vir_arena_used(id);
    /* 64 → aligned 64, 128 → aligned 128 = 192 */
    assert(used == 192);
    vir_arena_destroy(id);
    PASS();
}

/* ── Test 2: 8-byte alignment ─────────────────────────── */
static void test_alignment(void) {
    TEST("8-byte alignment");
    int id = vir_arena_create(4096);
    /* Allocate odd sizes, check alignment */
    for (int i = 1; i <= 17; i++) {
        void *p = vir_arena_alloc(id, (size_t)i);
        assert(p != NULL);
        assert(((uintptr_t)p & 7) == 0);
    }
    vir_arena_destroy(id);
    PASS();
}

/* ── Test 3: Overflow chain — allocate beyond page size ── */
static void test_overflow_chain(void) {
    TEST("overflow chain (multi-page)");
    int id = vir_arena_create(256); /* tiny 256-byte pages */

    /* Allocate 10 × 64 bytes = 640, needs 3+ pages */
    void *ptrs[10];
    for (int i = 0; i < 10; i++) {
        ptrs[i] = vir_arena_alloc(id, 64);
        assert(ptrs[i] != NULL);
    }
    /* Verify all pointers are unique */
    for (int i = 0; i < 10; i++) {
        for (int j = i + 1; j < 10; j++) {
            assert(ptrs[i] != ptrs[j]);
        }
    }
    /* Should have multiple pages */
    size_t pages = vir_arena_page_count(id);
    assert(pages >= 3);

    size_t used = vir_arena_used(id);
    assert(used == 640);

    vir_arena_destroy(id);
    PASS();
}

/* ── Test 4: Watermark save/restore ───────────────────── */
static void test_watermark(void) {
    TEST("watermark save/restore");
    int id = vir_arena_create(4096);

    void *p1 = vir_arena_alloc(id, 100);
    assert(p1 != NULL);

    /* Save watermark */
    size_t wm = vir_arena_save(id);
    assert(wm > 0);

    /* Allocate more */
    void *p2 = vir_arena_alloc(id, 200);
    assert(p2 != NULL);
    void *p3 = vir_arena_alloc(id, 300);
    assert(p3 != NULL);
    assert(vir_arena_used(id) > 100);

    /* Restore — p2, p3 conceptually freed */
    vir_arena_restore(id, wm);
    /* used should be ~104 (100 rounded to 104) */
    size_t used = vir_arena_used(id);
    assert(used == 104); /* 100 → aligned to 8 = 104 */

    vir_arena_destroy(id);
    PASS();
}

/* ── Test 5: Nested watermarks ────────────────────────── */
static void test_nested_watermarks(void) {
    TEST("nested watermarks");
    int id = vir_arena_create(4096);

    vir_arena_alloc(id, 64);
    size_t wm1 = vir_arena_save(id);

    vir_arena_alloc(id, 128);
    size_t wm2 = vir_arena_save(id);

    vir_arena_alloc(id, 256);

    /* Restore inner watermark first */
    vir_arena_restore(id, wm2);
    assert(vir_arena_used(id) == 64 + 128);

    /* Restore outer watermark */
    vir_arena_restore(id, wm1);
    assert(vir_arena_used(id) == 64);

    vir_arena_destroy(id);
    PASS();
}

/* ── Test 6: Reset clears everything ──────────────────── */
static void test_reset(void) {
    TEST("arena reset");
    int id = vir_arena_create(256);

    /* Force overflow */
    for (int i = 0; i < 20; i++)
        vir_arena_alloc(id, 64);

    assert(vir_arena_page_count(id) > 1);
    assert(vir_arena_used(id) > 0);

    vir_arena_reset(id);
    assert(vir_arena_used(id) == 0);
    assert(vir_arena_page_count(id) == 1); /* only original page */

    /* Can allocate again */
    void *p = vir_arena_alloc(id, 32);
    assert(p != NULL);

    vir_arena_destroy(id);
    PASS();
}

/* ── Test 7: Watermark with overflow chain ────────────── */
static void test_watermark_overflow(void) {
    TEST("watermark across page boundaries");
    int id = vir_arena_create(128);

    vir_arena_alloc(id, 64);
    size_t wm = vir_arena_save(id);

    /* Force multiple new pages */
    for (int i = 0; i < 10; i++)
        vir_arena_alloc(id, 64);

    size_t pages_before = vir_arena_page_count(id);
    assert(pages_before > 1);

    /* Restore should free overflow pages */
    vir_arena_restore(id, wm);
    assert(vir_arena_used(id) == 64);

    vir_arena_destroy(id);
    PASS();
}

/* ── Test 8: Large single allocation ──────────────────── */
static void test_large_alloc(void) {
    TEST("large allocation (> page_size)");
    int id = vir_arena_create(256);

    /* Request larger than page size */
    void *p = vir_arena_alloc(id, 1024);
    assert(p != NULL);
    /* Should have created a 1024-byte page */
    assert(vir_arena_used(id) == 1024);

    vir_arena_destroy(id);
    PASS();
}

/* ── Test 9: Child arena ──────────────────────────────── */
static void test_child_arena(void) {
    TEST("child arena (parent_id)");
    int parent = vir_arena_create(4096);
    int child  = vir_arena_create_child(parent, 1024);
    assert(child >= 0);
    assert(child != parent);

    void *p = vir_arena_alloc(child, 64);
    assert(p != NULL);

    vir_arena_destroy(child);
    vir_arena_destroy(parent);
    PASS();
}

/* ── Test 10: 16-byte alignment ───────────────────────── */
static void test_16byte_alignment(void) {
    TEST("16-byte alignment");
    int id = vir_arena_create(4096);
    vir_arena_set_alignment(id, 16);

    for (int i = 1; i <= 33; i++) {
        void *p = vir_arena_alloc(id, (size_t)i);
        assert(p != NULL);
        assert(((uintptr_t)p & 15) == 0);
    }
    vir_arena_destroy(id);
    PASS();
}

/* ── Test 11: Explicit vir_arena_alloc_aligned ────────── */
static void test_explicit_aligned(void) {
    TEST("vir_arena_alloc_aligned(32)");
    int id = vir_arena_create(4096);

    void *p1 = vir_arena_alloc_aligned(id, 10, 32);
    assert(p1 != NULL);
    assert(((uintptr_t)p1 & 31) == 0);

    void *p2 = vir_arena_alloc_aligned(id, 7, 32);
    assert(p2 != NULL);
    assert(((uintptr_t)p2 & 31) == 0);
    assert(p2 != p1);

    vir_arena_destroy(id);
    PASS();
}

/* ── Test 12: Growth factor ───────────────────────────── */
static void test_growth_factor(void) {
    TEST("growth factor (2×)");
    int id = vir_arena_create(256);
    vir_arena_set_growth_factor(id, 2.0);

    /* Fill first page (256 bytes) */
    for (int i = 0; i < 4; i++)
        vir_arena_alloc(id, 64);

    /* Force second page (should be 512 bytes due to 2× growth) */
    void *p = vir_arena_alloc(id, 64);
    assert(p != NULL);

    /* Force more pages — they should keep growing */
    for (int i = 0; i < 100; i++)
        vir_arena_alloc(id, 64);

    assert(vir_arena_page_count(id) >= 2);
    vir_arena_destroy(id);
    PASS();
}

/* ── Test 13: Thread-local arena ──────────────────────── */
static void test_thread_local_arena(void) {
    TEST("thread-local arena basic");
    vir_tl_arena_pool_init();

    int aid = vir_tl_arena_get();
    assert(aid >= 0);

    void *p = vir_tl_arena_alloc(64);
    assert(p != NULL);

    /* Same thread should get same arena */
    int aid2 = vir_tl_arena_get();
    assert(aid2 == aid);

    /* Release back to pool */
    vir_tl_arena_release();
    assert(vir_tl_arena_pool_size() >= 1);

    /* Get again — should reuse from pool */
    int aid3 = vir_tl_arena_get();
    assert(aid3 >= 0);

    vir_tl_arena_release();
    vir_tl_arena_pool_drain();
    PASS();
}

int main(void) {
    printf("═══ Arena v2 Tests ═══\n");

    test_basic_alloc();
    test_alignment();
    test_overflow_chain();
    test_watermark();
    test_nested_watermarks();
    test_reset();
    test_watermark_overflow();
    test_large_alloc();
    test_child_arena();
    test_16byte_alignment();
    test_explicit_aligned();
    test_growth_factor();
    test_thread_local_arena();

    printf("══════════════════════\n");
    printf("  Passed: %d  Failed: %d\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}

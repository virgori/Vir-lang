/*
 * atomic.h – Cross-Architecture Atomic Primitives
 * =================================================
 * Portable CAS, fetch-add, load/store with explicit ordering.
 *
 * x86-64:  LOCK CMPXCHG / LOCK XADD (implicit full fence)
 * ARM64:   LDXR/STXR (LL/SC) or LSE atomics (CASA/LDADD)
 * RISC-V:  LR.W/SC.W + .aq/.rl fences
 * Fallback: C11 _Atomic
 */

#ifndef VIR_ATOMIC_H
#define VIR_ATOMIC_H

#include <stdint.h>

/* ═══════════════════════════════════════════════════════
 * Memory Ordering
 * ═══════════════════════════════════════════════════════ */

typedef enum {
    VIR_MO_RELAXED = 0,
    VIR_MO_ACQUIRE = 1,
    VIR_MO_RELEASE = 2,
    VIR_MO_ACQ_REL = 3,
    VIR_MO_SEQ_CST = 4,
} vir_memory_order_t;

/* ═══════════════════════════════════════════════════════
 * 64-bit Atomics
 * ═══════════════════════════════════════════════════════ */

/* Compare-and-swap: if *ptr == expected, set *ptr = desired.
 * Returns the OLD value of *ptr (success if retval == expected). */
int64_t vir_atomic_cas_i64(volatile int64_t *ptr,
                           int64_t expected, int64_t desired,
                           vir_memory_order_t order);

/* Fetch-and-add: atomically add val to *ptr.  Returns old value. */
int64_t vir_atomic_add_i64(volatile int64_t *ptr,
                           int64_t val,
                           vir_memory_order_t order);

/* Atomic load. */
int64_t vir_atomic_load_i64(volatile const int64_t *ptr,
                            vir_memory_order_t order);

/* Atomic store. */
void vir_atomic_store_i64(volatile int64_t *ptr,
                          int64_t val,
                          vir_memory_order_t order);

/* ═══════════════════════════════════════════════════════
 * 32-bit Atomics
 * ═══════════════════════════════════════════════════════ */

int32_t vir_atomic_cas_i32(volatile int32_t *ptr,
                           int32_t expected, int32_t desired,
                           vir_memory_order_t order);

int32_t vir_atomic_add_i32(volatile int32_t *ptr,
                           int32_t val,
                           vir_memory_order_t order);

int32_t vir_atomic_load_i32(volatile const int32_t *ptr,
                            vir_memory_order_t order);

void vir_atomic_store_i32(volatile int32_t *ptr,
                          int32_t val,
                          vir_memory_order_t order);

/* ═══════════════════════════════════════════════════════
 * Fences
 * ═══════════════════════════════════════════════════════ */

void vir_atomic_fence(vir_memory_order_t order);

/* ═══════════════════════════════════════════════════════
 * Spinlock (built on CAS)
 * ═══════════════════════════════════════════════════════ */

typedef struct { volatile int32_t lock; } vir_spinlock_t;

#define VIR_SPINLOCK_INIT {0}

void vir_spin_lock(vir_spinlock_t *s);
void vir_spin_unlock(vir_spinlock_t *s);
int  vir_spin_trylock(vir_spinlock_t *s);

#endif /* VIR_ATOMIC_H */

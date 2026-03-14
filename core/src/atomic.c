/*
 * atomic.c – Cross-Architecture Atomic Primitives
 * =================================================
 * x86-64:  LOCK prefix (implicit fence on all ops)
 * ARM64:   LDXR/STXR (LL/SC) — compatible with all ARM64
 * RISC-V:  LR/SC with .aq/.rl
 * Fallback: C11 stdatomic
 */

#include "atomic.h"

/* ═══════════════════════════════════════════════════════
 * x86-64 Implementation (LOCK CMPXCHG / LOCK XADD)
 * ═══════════════════════════════════════════════════════ */

#if defined(__x86_64__) || defined(_M_X64)

int64_t vir_atomic_cas_i64(volatile int64_t *ptr,
                           int64_t expected, int64_t desired,
                           vir_memory_order_t order)
{
    (void)order; /* x86 LOCK is always seq_cst */
    int64_t old = expected;
    __asm__ volatile(
        "lock cmpxchgq %2, %1"
        : "+a"(old), "+m"(*ptr)
        : "r"(desired)
        : "cc", "memory"
    );
    return old;
}

int64_t vir_atomic_add_i64(volatile int64_t *ptr,
                           int64_t val,
                           vir_memory_order_t order)
{
    (void)order;
    int64_t old = val;
    __asm__ volatile(
        "lock xaddq %0, %1"
        : "+r"(old), "+m"(*ptr)
        :
        : "cc", "memory"
    );
    return old;
}

int64_t vir_atomic_load_i64(volatile const int64_t *ptr,
                            vir_memory_order_t order)
{
    int64_t val = *ptr;
    if (order >= VIR_MO_ACQUIRE)
        __asm__ volatile("" ::: "memory");  /* compiler fence */
    return val;
}

void vir_atomic_store_i64(volatile int64_t *ptr,
                          int64_t val,
                          vir_memory_order_t order)
{
    if (order >= VIR_MO_SEQ_CST) {
        __asm__ volatile("lock xchgq %0, %1"
                         : "+r"(val), "+m"(*ptr)
                         :: "memory");
    } else {
        if (order >= VIR_MO_RELEASE)
            __asm__ volatile("" ::: "memory");
        *ptr = val;
    }
}

int32_t vir_atomic_cas_i32(volatile int32_t *ptr,
                           int32_t expected, int32_t desired,
                           vir_memory_order_t order)
{
    (void)order;
    int32_t old = expected;
    __asm__ volatile(
        "lock cmpxchgl %2, %1"
        : "+a"(old), "+m"(*ptr)
        : "r"(desired)
        : "cc", "memory"
    );
    return old;
}

int32_t vir_atomic_add_i32(volatile int32_t *ptr,
                           int32_t val,
                           vir_memory_order_t order)
{
    (void)order;
    int32_t old = val;
    __asm__ volatile(
        "lock xaddl %0, %1"
        : "+r"(old), "+m"(*ptr)
        :
        : "cc", "memory"
    );
    return old;
}

int32_t vir_atomic_load_i32(volatile const int32_t *ptr,
                            vir_memory_order_t order)
{
    int32_t val = *ptr;
    if (order >= VIR_MO_ACQUIRE)
        __asm__ volatile("" ::: "memory");
    return val;
}

void vir_atomic_store_i32(volatile int32_t *ptr,
                          int32_t val,
                          vir_memory_order_t order)
{
    if (order >= VIR_MO_SEQ_CST) {
        __asm__ volatile("lock xchgl %0, %1"
                         : "+r"(val), "+m"(*ptr)
                         :: "memory");
    } else {
        if (order >= VIR_MO_RELEASE)
            __asm__ volatile("" ::: "memory");
        *ptr = val;
    }
}

void vir_atomic_fence(vir_memory_order_t order)
{
    if (order == VIR_MO_SEQ_CST)
        __asm__ volatile("mfence" ::: "memory");
    else
        __asm__ volatile("" ::: "memory");  /* compiler fence */
}

/* ═══════════════════════════════════════════════════════
 * ARM64 Implementation (LDXR/STXR — LL/SC)
 * ═══════════════════════════════════════════════════════ */

#elif defined(__aarch64__)

int64_t vir_atomic_cas_i64(volatile int64_t *ptr,
                           int64_t expected, int64_t desired,
                           vir_memory_order_t order)
{
    int64_t old;
    int tmp;
    if (order >= VIR_MO_ACQ_REL) {
        __asm__ volatile(
            "1:\n\t"
            "ldaxr  %x0, [%3]\n\t"    /* load-acquire exclusive   */
            "cmp    %x0, %x1\n\t"
            "b.ne   2f\n\t"
            "stlxr  %w2, %x4, [%3]\n\t" /* store-release exclusive */
            "cbnz   %w2, 1b\n\t"
            "2:\n\t"
            : "=&r"(old), "+r"(expected), "=&r"(tmp)
            : "r"(ptr), "r"(desired)
            : "cc", "memory"
        );
    } else {
        __asm__ volatile(
            "1:\n\t"
            "ldxr   %x0, [%3]\n\t"
            "cmp    %x0, %x1\n\t"
            "b.ne   2f\n\t"
            "stxr   %w2, %x4, [%3]\n\t"
            "cbnz   %w2, 1b\n\t"
            "2:\n\t"
            : "=&r"(old), "+r"(expected), "=&r"(tmp)
            : "r"(ptr), "r"(desired)
            : "cc", "memory"
        );
    }
    return old;
}

int64_t vir_atomic_add_i64(volatile int64_t *ptr,
                           int64_t val,
                           vir_memory_order_t order)
{
    int64_t old, sum;
    int tmp;
    if (order >= VIR_MO_ACQ_REL) {
        __asm__ volatile(
            "1:\n\t"
            "ldaxr  %x0, [%4]\n\t"
            "add    %x1, %x0, %x3\n\t"
            "stlxr  %w2, %x1, [%4]\n\t"
            "cbnz   %w2, 1b\n\t"
            : "=&r"(old), "=&r"(sum), "=&r"(tmp)
            : "r"(val), "r"(ptr)
            : "cc", "memory"
        );
    } else {
        __asm__ volatile(
            "1:\n\t"
            "ldxr   %x0, [%4]\n\t"
            "add    %x1, %x0, %x3\n\t"
            "stxr   %w2, %x1, [%4]\n\t"
            "cbnz   %w2, 1b\n\t"
            : "=&r"(old), "=&r"(sum), "=&r"(tmp)
            : "r"(val), "r"(ptr)
            : "cc", "memory"
        );
    }
    return old;
}

int64_t vir_atomic_load_i64(volatile const int64_t *ptr,
                            vir_memory_order_t order)
{
    int64_t val;
    if (order >= VIR_MO_ACQUIRE) {
        __asm__ volatile("ldar %x0, [%1]" : "=r"(val) : "r"(ptr) : "memory");
    } else {
        __asm__ volatile("ldr  %x0, [%1]" : "=r"(val) : "r"(ptr));
    }
    return val;
}

void vir_atomic_store_i64(volatile int64_t *ptr,
                          int64_t val,
                          vir_memory_order_t order)
{
    if (order >= VIR_MO_RELEASE) {
        __asm__ volatile("stlr %x0, [%1]" : : "r"(val), "r"(ptr) : "memory");
    } else {
        __asm__ volatile("str  %x0, [%1]" : : "r"(val), "r"(ptr));
    }
}

int32_t vir_atomic_cas_i32(volatile int32_t *ptr,
                           int32_t expected, int32_t desired,
                           vir_memory_order_t order)
{
    int32_t old;
    int tmp;
    if (order >= VIR_MO_ACQ_REL) {
        __asm__ volatile(
            "1:\n\t"
            "ldaxr  %w0, [%3]\n\t"
            "cmp    %w0, %w1\n\t"
            "b.ne   2f\n\t"
            "stlxr  %w2, %w4, [%3]\n\t"
            "cbnz   %w2, 1b\n\t"
            "2:\n\t"
            : "=&r"(old), "+r"(expected), "=&r"(tmp)
            : "r"(ptr), "r"(desired)
            : "cc", "memory"
        );
    } else {
        __asm__ volatile(
            "1:\n\t"
            "ldxr   %w0, [%3]\n\t"
            "cmp    %w0, %w1\n\t"
            "b.ne   2f\n\t"
            "stxr   %w2, %w4, [%3]\n\t"
            "cbnz   %w2, 1b\n\t"
            "2:\n\t"
            : "=&r"(old), "+r"(expected), "=&r"(tmp)
            : "r"(ptr), "r"(desired)
            : "cc", "memory"
        );
    }
    return old;
}

int32_t vir_atomic_add_i32(volatile int32_t *ptr,
                           int32_t val,
                           vir_memory_order_t order)
{
    int32_t old, sum;
    int tmp;
    if (order >= VIR_MO_ACQ_REL) {
        __asm__ volatile(
            "1:\n\t"
            "ldaxr  %w0, [%4]\n\t"
            "add    %w1, %w0, %w3\n\t"
            "stlxr  %w2, %w1, [%4]\n\t"
            "cbnz   %w2, 1b\n\t"
            : "=&r"(old), "=&r"(sum), "=&r"(tmp)
            : "r"(val), "r"(ptr)
            : "cc", "memory"
        );
    } else {
        __asm__ volatile(
            "1:\n\t"
            "ldxr   %w0, [%4]\n\t"
            "add    %w1, %w0, %w3\n\t"
            "stxr   %w2, %w1, [%4]\n\t"
            "cbnz   %w2, 1b\n\t"
            : "=&r"(old), "=&r"(sum), "=&r"(tmp)
            : "r"(val), "r"(ptr)
            : "cc", "memory"
        );
    }
    return old;
}

int32_t vir_atomic_load_i32(volatile const int32_t *ptr,
                            vir_memory_order_t order)
{
    int32_t val;
    if (order >= VIR_MO_ACQUIRE) {
        __asm__ volatile("ldar %w0, [%1]" : "=r"(val) : "r"(ptr) : "memory");
    } else {
        __asm__ volatile("ldr  %w0, [%1]" : "=r"(val) : "r"(ptr));
    }
    return val;
}

void vir_atomic_store_i32(volatile int32_t *ptr,
                          int32_t val,
                          vir_memory_order_t order)
{
    if (order >= VIR_MO_RELEASE) {
        __asm__ volatile("stlr %w0, [%1]" : : "r"(val), "r"(ptr) : "memory");
    } else {
        __asm__ volatile("str  %w0, [%1]" : : "r"(val), "r"(ptr));
    }
}

void vir_atomic_fence(vir_memory_order_t order)
{
    if (order == VIR_MO_SEQ_CST)
        __asm__ volatile("dmb ish" ::: "memory");
    else if (order >= VIR_MO_ACQUIRE)
        __asm__ volatile("dmb ishld" ::: "memory");
    else
        __asm__ volatile("" ::: "memory");
}

/* ═══════════════════════════════════════════════════════
 * Fallback: C11 stdatomic
 * ═══════════════════════════════════════════════════════ */

#else

#include <stdatomic.h>

static memory_order mo_map(vir_memory_order_t o) {
    switch (o) {
        case VIR_MO_RELAXED: return memory_order_relaxed;
        case VIR_MO_ACQUIRE: return memory_order_acquire;
        case VIR_MO_RELEASE: return memory_order_release;
        case VIR_MO_ACQ_REL: return memory_order_acq_rel;
        case VIR_MO_SEQ_CST: return memory_order_seq_cst;
        default:             return memory_order_seq_cst;
    }
}

int64_t vir_atomic_cas_i64(volatile int64_t *ptr,
                           int64_t expected, int64_t desired,
                           vir_memory_order_t order)
{
    _Atomic int64_t *ap = (_Atomic int64_t *)ptr;
    atomic_compare_exchange_strong_explicit(ap, &expected, desired,
                                           mo_map(order), memory_order_relaxed);
    return expected;
}

int64_t vir_atomic_add_i64(volatile int64_t *ptr, int64_t val,
                           vir_memory_order_t order)
{
    _Atomic int64_t *ap = (_Atomic int64_t *)ptr;
    return atomic_fetch_add_explicit(ap, val, mo_map(order));
}

int64_t vir_atomic_load_i64(volatile const int64_t *ptr,
                            vir_memory_order_t order)
{
    const _Atomic int64_t *ap = (const _Atomic int64_t *)ptr;
    return atomic_load_explicit(ap, mo_map(order));
}

void vir_atomic_store_i64(volatile int64_t *ptr, int64_t val,
                          vir_memory_order_t order)
{
    _Atomic int64_t *ap = (_Atomic int64_t *)ptr;
    atomic_store_explicit(ap, val, mo_map(order));
}

int32_t vir_atomic_cas_i32(volatile int32_t *ptr,
                           int32_t expected, int32_t desired,
                           vir_memory_order_t order)
{
    _Atomic int32_t *ap = (_Atomic int32_t *)ptr;
    atomic_compare_exchange_strong_explicit(ap, &expected, desired,
                                           mo_map(order), memory_order_relaxed);
    return expected;
}

int32_t vir_atomic_add_i32(volatile int32_t *ptr, int32_t val,
                           vir_memory_order_t order)
{
    _Atomic int32_t *ap = (_Atomic int32_t *)ptr;
    return atomic_fetch_add_explicit(ap, val, mo_map(order));
}

int32_t vir_atomic_load_i32(volatile const int32_t *ptr,
                            vir_memory_order_t order)
{
    const _Atomic int32_t *ap = (const _Atomic int32_t *)ptr;
    return atomic_load_explicit(ap, mo_map(order));
}

void vir_atomic_store_i32(volatile int32_t *ptr, int32_t val,
                          vir_memory_order_t order)
{
    _Atomic int32_t *ap = (_Atomic int32_t *)ptr;
    atomic_store_explicit(ap, val, mo_map(order));
}

void vir_atomic_fence(vir_memory_order_t order)
{
    atomic_thread_fence(mo_map(order));
}

#endif /* arch selection */

/* ═══════════════════════════════════════════════════════
 * Spinlock (architecture-independent, built on CAS)
 * ═══════════════════════════════════════════════════════ */

void vir_spin_lock(vir_spinlock_t *s)
{
    while (vir_atomic_cas_i32(&s->lock, 0, 1, VIR_MO_ACQUIRE) != 0) {
        /* Spin hint: reduce power and avoid starving pipelines */
#if defined(__x86_64__) || defined(_M_X64)
        __asm__ volatile("pause");
#elif defined(__aarch64__)
        __asm__ volatile("yield");
#else
        /* no hint */
#endif
    }
}

void vir_spin_unlock(vir_spinlock_t *s)
{
    vir_atomic_store_i32(&s->lock, 0, VIR_MO_RELEASE);
}

int vir_spin_trylock(vir_spinlock_t *s)
{
    return vir_atomic_cas_i32(&s->lock, 0, 1, VIR_MO_ACQUIRE) == 0;
}

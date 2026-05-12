/*
 * vir_platform.h — Portable platform macros for the Vir compiler core.
 *
 * Include this header for:
 *   - VIR_ALIGNED(n)   — cross-compiler struct/field alignment
 *   - VIR_PACKED        — packed struct attribute
 *   - VIR_LIKELY/UNLIKELY — branch prediction hints
 *   - VIR_CACHE_LINE    — cache line size constant
 *   - VIR_STATIC_ASSERT — compile-time assertion
 */

#ifndef VIR_PLATFORM_H
#define VIR_PLATFORM_H

#include <stdint.h>
#include <stddef.h>

/* ── Alignment macros ──────────────────────────────────────────────── */

/*
 * VIR_ALIGNED(n) — Enforce alignment on structs or fields.
 *
 * Critical for RISC-V (unaligned access causes SIGBUS/trap) and
 * SIMD operations (NEON/AVX require aligned loads).
 *
 * Usage:
 *   struct VIR_ALIGNED(8) my_struct { ... };
 *   uint64_t value VIR_ALIGNED(8);
 */
#ifdef _MSC_VER
  #define VIR_ALIGNED(n)  __declspec(align(n))
#else
  #define VIR_ALIGNED(n)  __attribute__((aligned(n)))
#endif

/*
 * VIR_PACKED — Remove padding from structs (use with care on RISC-V).
 */
#ifdef _MSC_VER
  #define VIR_PACKED
  #define VIR_PACK_BEGIN  __pragma(pack(push, 1))
  #define VIR_PACK_END    __pragma(pack(pop))
#else
  #define VIR_PACKED       __attribute__((packed))
  #define VIR_PACK_BEGIN
  #define VIR_PACK_END
#endif

/* ── Branch prediction ─────────────────────────────────────────────── */

#if defined(__GNUC__) || defined(__clang__)
  #define VIR_LIKELY(x)    __builtin_expect(!!(x), 1)
  #define VIR_UNLIKELY(x)  __builtin_expect(!!(x), 0)
#else
  #define VIR_LIKELY(x)    (x)
  #define VIR_UNLIKELY(x)  (x)
#endif

/* ── Cache line ────────────────────────────────────────────────────── */

#if defined(__aarch64__)
  #define VIR_CACHE_LINE  128  /* Apple Silicon uses 128-byte lines */
#else
  #define VIR_CACHE_LINE  64   /* x86_64 and most RISC-V */
#endif

/* ── Static assert ─────────────────────────────────────────────────── */

#if defined(__STDC_VERSION__) && __STDC_VERSION__ >= 201112L
  #define VIR_STATIC_ASSERT(expr, msg)  _Static_assert(expr, msg)
#elif defined(_MSC_VER)
  #define VIR_STATIC_ASSERT(expr, msg)  static_assert(expr, msg)
#else
  #define VIR_STATIC_ASSERT(expr, msg)  \
    typedef char vir_sa_##__LINE__[(expr) ? 1 : -1]
#endif

/* ── Alignment verification helpers ────────────────────────────────── */

/*
 * Compile-time check that a struct's size is a multiple of its alignment.
 * Use after struct definition:
 *
 *   VIR_CHECK_STRUCT_ALIGNMENT(q_instruction_t, 4);
 */
#define VIR_CHECK_STRUCT_ALIGNMENT(type, align) \
    VIR_STATIC_ASSERT(sizeof(type) % (align) == 0, \
        #type " size must be a multiple of " #align)

/*
 * Compile-time check that a field offset is correctly aligned.
 */
#define VIR_CHECK_FIELD_ALIGNMENT(type, field, align) \
    VIR_STATIC_ASSERT(offsetof(type, field) % (align) == 0, \
        #type "." #field " must be aligned to " #align " bytes")

#endif /* VIR_PLATFORM_H */

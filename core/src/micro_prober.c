/*
 * micro_prober.c – CPU Micro-Architecture Prober
 * ================================================
 * Measures real instruction latency, throughput, and branch penalty
 * using hardware cycle counters. ARM64 uses CNTVCT_EL0 + CNTFRQ_EL0,
 * x86_64 uses RDTSC.
 *
 * Technique:
 *   Latency:    Serial dependency chain (each instr depends on previous)
 *   Throughput: Independent parallel instructions (measure IPC)
 *   Branch:     Random vs predictable branch patterns
 *   Memory:     Pointer chase through arrays of increasing size
 */

#include "micro_prober.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>

#ifdef __APPLE__
#include <sys/sysctl.h>
#include <mach/mach_time.h>
#endif

/* ═══════════════════════════════════════════════════════
 * Configuration
 * ═══════════════════════════════════════════════════════ */

#define WARMUP_ITERS     1000
#define LATENCY_UNROLL   100   /* instructions per chain */
#define THRU_UNROLL       50   /* independent ops per batch */
#define SAMPLES            5   /* statistical samples */
#define BRANCH_DEPTH    8192   /* branch test iterations */

/* ═══════════════════════════════════════════════════════
 * Tick-to-cycle conversion helpers
 * ═══════════════════════════════════════════════════════ */

static double cpu_freq_ghz = 3.5; /* default for Apple M2, updated in prober_init */

static double ticks_to_cycles(uint64_t ticks)
{
    double ns = prober_ticks_to_ns(ticks);
    return ns * cpu_freq_ghz; /* 1 GHz = 1 cycle per ns */
}

/* ═══════════════════════════════════════════════════════
 * Platform Detection
 * ═══════════════════════════════════════════════════════ */

static uint64_t get_timer_freq(void)
{
    /* Return estimated CPU frequency in Hz for cycle estimation */
#ifdef __APPLE__
    uint64_t freq = 0;
    size_t sz = sizeof(freq);
    /* Try to get P-core max frequency */
    if (sysctlbyname("hw.cpufrequency_max", &freq, &sz, NULL, 0) == 0 && freq > 0)
        return freq;
    /* Apple Silicon M-series doesn't expose cpufrequency, estimate */
    /* M1: ~3.2GHz, M2: ~3.5GHz, M3: ~4.0GHz — use 3.5GHz default */
    return 3500000000ULL;
#elif defined(__x86_64__) || defined(_M_X64)
    return 1000000000ULL; /* TSC is approx 1ns on modern x86 */
#else
    return 1000000000ULL;
#endif
}

static const char *get_cpu_name(void)
{
#ifdef __APPLE__
    static char name[128];
    size_t sz = sizeof(name);
    if (sysctlbyname("machdep.cpu.brand_string", name, &sz, NULL, 0) == 0)
        return name;
#endif
    return "Unknown CPU";
}

int prober_init(probe_report_t *report)
{
    if (!report) return -1;
    memset(report, 0, sizeof(*report));

#if defined(__aarch64__) || defined(_M_ARM64)
    report->arch = "arm64";
#elif defined(__x86_64__) || defined(_M_X64)
    report->arch = "x86_64";
#else
    report->arch = "unknown";
#endif

    report->cpu_name = get_cpu_name();
    report->timer_freq_hz = get_timer_freq();
    cpu_freq_ghz = (double)report->timer_freq_hz / 1e9;
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Statistical Helpers
 * ═══════════════════════════════════════════════════════ */

static double arr_mean(const double *v, int n)
{
    double s = 0;
    for (int i = 0; i < n; i++) s += v[i];
    return s / n;
}

static double arr_min(const double *v, int n)
{
    double m = v[0];
    for (int i = 1; i < n; i++) if (v[i] < m) m = v[i];
    return m;
}

static double arr_max(const double *v, int n)
{
    double m = v[0];
    for (int i = 1; i < n; i++) if (v[i] > m) m = v[i];
    return m;
}

static double arr_stddev(const double *v, int n)
{
    double m = arr_mean(v, n);
    double s = 0;
    for (int i = 0; i < n; i++) {
        double d = v[i] - m;
        s += d * d;
    }
    return sqrt(s / n);
}

/* ═══════════════════════════════════════════════════════
 * ARM64 Latency Probes (Serial Dependency Chains)
 * ═══════════════════════════════════════════════════════ */

#if defined(__aarch64__) || defined(_M_ARM64)

/* Each probe function creates a serial dependency chain where
 * each instruction depends on the output of the previous one.
 * This forces sequential execution, measuring true latency. */

static uint64_t probe_add_latency(uint32_t outer_iters)
{
    register uint64_t val = 1;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < outer_iters; i++) {
        /* 100 dependent ADDs — each depends on previous x0 */
        __asm__ volatile(
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            "add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n add %0, %0, #1\n"
            : "+r"(val)
        );
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    /* Prevent compiler from optimizing away val */
    if (val == 0) printf("%llu", val);
    return end - start;
}

static uint64_t probe_mul_latency(uint32_t outer_iters)
{
    register uint64_t val = 3;
    register uint64_t one = 1;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < outer_iters; i++) {
        /* 50 dependent MULs (mul by 1 to keep value stable) */
        __asm__ volatile(
            "mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n"
            "mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n"
            "mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n"
            "mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n"
            "mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n"
            "mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n"
            "mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n"
            "mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n"
            "mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n"
            "mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n"
            "mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n"
            "mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n mul %0, %0, %1\n"
            "mul %0, %0, %1\n mul %0, %0, %1\n"
            : "+r"(val)
            : "r"(one)
        );
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    if (val == 0) printf("%llu", val);
    return end - start;
}

static uint64_t probe_sdiv_latency(uint32_t outer_iters)
{
    register uint64_t val = 1000000000ULL;
    register uint64_t one = 1;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < outer_iters; i++) {
        /* 20 dependent SDIVs (div by 1) — SDIV is slow */
        __asm__ volatile(
            "sdiv %0, %0, %1\n sdiv %0, %0, %1\n sdiv %0, %0, %1\n sdiv %0, %0, %1\n"
            "sdiv %0, %0, %1\n sdiv %0, %0, %1\n sdiv %0, %0, %1\n sdiv %0, %0, %1\n"
            "sdiv %0, %0, %1\n sdiv %0, %0, %1\n sdiv %0, %0, %1\n sdiv %0, %0, %1\n"
            "sdiv %0, %0, %1\n sdiv %0, %0, %1\n sdiv %0, %0, %1\n sdiv %0, %0, %1\n"
            "sdiv %0, %0, %1\n sdiv %0, %0, %1\n sdiv %0, %0, %1\n sdiv %0, %0, %1\n"
            : "+r"(val)
            : "r"(one)
        );
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    if (val == 0) printf("%llu", val);
    return end - start;
}

static uint64_t probe_ldr_latency(uint32_t outer_iters)
{
    /* Pointer chase: array[i] points to array[array[i]] etc. */
    #define CHASE_SIZE 256
    uint64_t arr[CHASE_SIZE];
    /* Shuffle to create a pointer-chase cycle */
    for (int i = 0; i < CHASE_SIZE; i++)
        arr[i] = (i + 1) % CHASE_SIZE;

    register uint64_t idx = 0;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < outer_iters; i++) {
        /* 50 dependent loads through the pointer chase */
        for (int j = 0; j < 50; j++) {
            idx = arr[idx];
        }
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    if (idx == (uint64_t)-1) printf("%llu", idx); /* prevent optimization */
    return end - start;
    #undef CHASE_SIZE
}

static uint64_t probe_cmp_branch_latency(uint32_t outer_iters)
{
    register uint64_t val = 0;
    register uint64_t big = 999;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < outer_iters; i++) {
        /* 25 dependent compare+branch (always taken / predicted) */
        __asm__ volatile(
            "cmp %0, %1\n b.ne 1f\n 1:\n"
            "cmp %0, %1\n b.ne 2f\n 2:\n"
            "cmp %0, %1\n b.ne 3f\n 3:\n"
            "cmp %0, %1\n b.ne 4f\n 4:\n"
            "cmp %0, %1\n b.ne 5f\n 5:\n"
            "cmp %0, %1\n b.ne 6f\n 6:\n"
            "cmp %0, %1\n b.ne 7f\n 7:\n"
            "cmp %0, %1\n b.ne 8f\n 8:\n"
            "cmp %0, %1\n b.ne 9f\n 9:\n"
            "cmp %0, %1\n b.ne 10f\n 10:\n"
            "cmp %0, %1\n b.ne 11f\n 11:\n"
            "cmp %0, %1\n b.ne 12f\n 12:\n"
            "cmp %0, %1\n b.ne 13f\n 13:\n"
            "cmp %0, %1\n b.ne 14f\n 14:\n"
            "cmp %0, %1\n b.ne 15f\n 15:\n"
            "cmp %0, %1\n b.ne 16f\n 16:\n"
            "cmp %0, %1\n b.ne 17f\n 17:\n"
            "cmp %0, %1\n b.ne 18f\n 18:\n"
            "cmp %0, %1\n b.ne 19f\n 19:\n"
            "cmp %0, %1\n b.ne 20f\n 20:\n"
            "cmp %0, %1\n b.ne 21f\n 21:\n"
            "cmp %0, %1\n b.ne 22f\n 22:\n"
            "cmp %0, %1\n b.ne 23f\n 23:\n"
            "cmp %0, %1\n b.ne 24f\n 24:\n"
            "cmp %0, %1\n b.ne 25f\n 25:\n"
            "add %0, %0, #0\n"
            : "+r"(val)
            : "r"(big)
        );
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    if (val == (uint64_t)-1) printf("%llu", val);
    return end - start;
}

/* Throughput probes: independent operations (no data dependency) */

static uint64_t probe_add_throughput(uint32_t outer_iters)
{
    register uint64_t a = 1, b = 2, c = 3, d = 4;
    register uint64_t e = 5, f = 6, g = 7, h = 8;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < outer_iters; i++) {
        /* 8 independent ADDs — can all dispatch in parallel */
        __asm__ volatile(
            "add %0, %0, #1\n add %1, %1, #1\n add %2, %2, #1\n add %3, %3, #1\n"
            "add %4, %4, #1\n add %5, %5, #1\n add %6, %6, #1\n add %7, %7, #1\n"
            "add %0, %0, #1\n add %1, %1, #1\n add %2, %2, #1\n add %3, %3, #1\n"
            "add %4, %4, #1\n add %5, %5, #1\n add %6, %6, #1\n add %7, %7, #1\n"
            "add %0, %0, #1\n add %1, %1, #1\n add %2, %2, #1\n add %3, %3, #1\n"
            "add %4, %4, #1\n add %5, %5, #1\n add %6, %6, #1\n add %7, %7, #1\n"
            "add %0, %0, #1\n add %1, %1, #1\n add %2, %2, #1\n add %3, %3, #1\n"
            "add %4, %4, #1\n add %5, %5, #1\n add %6, %6, #1\n add %7, %7, #1\n"
            "add %0, %0, #1\n add %1, %1, #1\n add %2, %2, #1\n add %3, %3, #1\n"
            "add %4, %4, #1\n add %5, %5, #1\n add %6, %6, #1\n add %7, %7, #1\n"
            "add %0, %0, #1\n add %1, %1, #1\n add %2, %2, #1\n add %3, %3, #1\n"
            "add %4, %4, #1\n add %5, %5, #1\n add %6, %6, #1\n add %7, %7, #1\n"
            : "+r"(a), "+r"(b), "+r"(c), "+r"(d),
              "+r"(e), "+r"(f), "+r"(g), "+r"(h)
        );
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    uint64_t s = a + b + c + d + e + f + g + h;
    if (s == 0) printf("%llu", s);
    return end - start;
}

static uint64_t probe_mul_throughput(uint32_t outer_iters)
{
    register uint64_t a = 1, b = 2, c = 3, d = 4;
    register uint64_t one = 1;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < outer_iters; i++) {
        /* 4 independent MULs (fewer than ADD because mul ports are limited) */
        __asm__ volatile(
            "mul %0, %0, %4\n mul %1, %1, %4\n mul %2, %2, %4\n mul %3, %3, %4\n"
            "mul %0, %0, %4\n mul %1, %1, %4\n mul %2, %2, %4\n mul %3, %3, %4\n"
            "mul %0, %0, %4\n mul %1, %1, %4\n mul %2, %2, %4\n mul %3, %3, %4\n"
            "mul %0, %0, %4\n mul %1, %1, %4\n mul %2, %2, %4\n mul %3, %3, %4\n"
            "mul %0, %0, %4\n mul %1, %1, %4\n mul %2, %2, %4\n mul %3, %3, %4\n"
            "mul %0, %0, %4\n mul %1, %1, %4\n mul %2, %2, %4\n mul %3, %3, %4\n"
            : "+r"(a), "+r"(b), "+r"(c), "+r"(d)
            : "r"(one)
        );
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    uint64_t s = a + b + c + d;
    if (s == 0) printf("%llu", s);
    return end - start;
}

#endif /* __aarch64__ */

/* ═══════════════════════════════════════════════════════
 * x86_64 Probes
 * ═══════════════════════════════════════════════════════ */

#if defined(__x86_64__) || defined(_M_X64)

static uint64_t probe_add_latency(uint32_t outer_iters)
{
    register uint64_t val = 1;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < outer_iters; i++) {
        __asm__ volatile(
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            "add $1, %0\n add $1, %0\n add $1, %0\n add $1, %0\n"
            : "+r"(val)
        );
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    if (val == 0) printf("%llu", val);
    return end - start;
}

static uint64_t probe_mul_latency(uint32_t outer_iters)
{
    register uint64_t val = 3;
    register uint64_t one = 1;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < outer_iters; i++) {
        __asm__ volatile(
            "imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n"
            "imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n"
            "imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n"
            "imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n"
            "imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n"
            "imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n"
            "imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n"
            "imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n"
            "imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n"
            "imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n"
            "imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n"
            "imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n imulq %1, %0\n"
            "imulq %1, %0\n imulq %1, %0\n"
            : "+r"(val)
            : "r"(one)
        );
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    if (val == 0) printf("%llu", val);
    return end - start;
}

static uint64_t probe_sdiv_latency(uint32_t outer_iters)
{
    register uint64_t quo;
    uint64_t dividend = 1000000000ULL;
    uint64_t divisor = 1;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < outer_iters; i++) {
        /* CQO+IDIV chain (x86 division clobbers rax+rdx) */
        for (int j = 0; j < 20; j++) {
            __asm__ volatile(
                "mov %1, %%rax\n"
                "cqo\n"
                "idivq %2\n"
                "mov %%rax, %0\n"
                : "=r"(quo)
                : "r"(dividend), "r"(divisor)
                : "rax", "rdx"
            );
            dividend = quo;
        }
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    if (quo == 0) printf("%llu", quo);
    return end - start;
}

static uint64_t probe_ldr_latency(uint32_t outer_iters)
{
    #define CHASE_SIZE 256
    uint64_t arr[CHASE_SIZE];
    for (int i = 0; i < CHASE_SIZE; i++)
        arr[i] = (i + 1) % CHASE_SIZE;

    register uint64_t idx = 0;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < outer_iters; i++) {
        for (int j = 0; j < 50; j++) {
            idx = arr[idx];
        }
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    if (idx == (uint64_t)-1) printf("%llu", idx);
    return end - start;
    #undef CHASE_SIZE
}

static uint64_t probe_cmp_branch_latency(uint32_t outer_iters)
{
    register uint64_t val = 0;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < outer_iters; i++) {
        __asm__ volatile(
            "cmpq $999999, %0\n jne 1f\n 1:\n"
            "cmpq $999999, %0\n jne 2f\n 2:\n"
            "cmpq $999999, %0\n jne 3f\n 3:\n"
            "cmpq $999999, %0\n jne 4f\n 4:\n"
            "cmpq $999999, %0\n jne 5f\n 5:\n"
            "cmpq $999999, %0\n jne 6f\n 6:\n"
            "cmpq $999999, %0\n jne 7f\n 7:\n"
            "cmpq $999999, %0\n jne 8f\n 8:\n"
            "cmpq $999999, %0\n jne 9f\n 9:\n"
            "cmpq $999999, %0\n jne 10f\n 10:\n"
            "cmpq $999999, %0\n jne 11f\n 11:\n"
            "cmpq $999999, %0\n jne 12f\n 12:\n"
            "cmpq $999999, %0\n jne 13f\n 13:\n"
            "cmpq $999999, %0\n jne 14f\n 14:\n"
            "cmpq $999999, %0\n jne 15f\n 15:\n"
            "cmpq $999999, %0\n jne 16f\n 16:\n"
            "cmpq $999999, %0\n jne 17f\n 17:\n"
            "cmpq $999999, %0\n jne 18f\n 18:\n"
            "cmpq $999999, %0\n jne 19f\n 19:\n"
            "cmpq $999999, %0\n jne 20f\n 20:\n"
            "cmpq $999999, %0\n jne 21f\n 21:\n"
            "cmpq $999999, %0\n jne 22f\n 22:\n"
            "cmpq $999999, %0\n jne 23f\n 23:\n"
            "cmpq $999999, %0\n jne 24f\n 24:\n"
            "cmpq $999999, %0\n jne 25f\n 25:\n"
            : "+r"(val)
        );
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    if (val == (uint64_t)-1) printf("%llu", val);
    return end - start;
}

static uint64_t probe_add_throughput(uint32_t outer_iters)
{
    register uint64_t a = 1, b = 2, c = 3, d = 4;
    register uint64_t e = 5, f = 6, g = 7, h = 8;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < outer_iters; i++) {
        __asm__ volatile(
            "add $1, %0\n add $1, %1\n add $1, %2\n add $1, %3\n"
            "add $1, %4\n add $1, %5\n add $1, %6\n add $1, %7\n"
            "add $1, %0\n add $1, %1\n add $1, %2\n add $1, %3\n"
            "add $1, %4\n add $1, %5\n add $1, %6\n add $1, %7\n"
            "add $1, %0\n add $1, %1\n add $1, %2\n add $1, %3\n"
            "add $1, %4\n add $1, %5\n add $1, %6\n add $1, %7\n"
            "add $1, %0\n add $1, %1\n add $1, %2\n add $1, %3\n"
            "add $1, %4\n add $1, %5\n add $1, %6\n add $1, %7\n"
            "add $1, %0\n add $1, %1\n add $1, %2\n add $1, %3\n"
            "add $1, %4\n add $1, %5\n add $1, %6\n add $1, %7\n"
            "add $1, %0\n add $1, %1\n add $1, %2\n add $1, %3\n"
            "add $1, %4\n add $1, %5\n add $1, %6\n add $1, %7\n"
            : "+r"(a), "+r"(b), "+r"(c), "+r"(d),
              "+r"(e), "+r"(f), "+r"(g), "+r"(h)
        );
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    uint64_t s = a + b + c + d + e + f + g + h;
    if (s == 0) printf("%llu", s);
    return end - start;
}

static uint64_t probe_mul_throughput(uint32_t outer_iters)
{
    register uint64_t a = 1, b = 2, c = 3, d = 4;
    register uint64_t one = 1;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < outer_iters; i++) {
        __asm__ volatile(
            "imulq %4, %0\n imulq %4, %1\n imulq %4, %2\n imulq %4, %3\n"
            "imulq %4, %0\n imulq %4, %1\n imulq %4, %2\n imulq %4, %3\n"
            "imulq %4, %0\n imulq %4, %1\n imulq %4, %2\n imulq %4, %3\n"
            "imulq %4, %0\n imulq %4, %1\n imulq %4, %2\n imulq %4, %3\n"
            "imulq %4, %0\n imulq %4, %1\n imulq %4, %2\n imulq %4, %3\n"
            "imulq %4, %0\n imulq %4, %1\n imulq %4, %2\n imulq %4, %3\n"
            : "+r"(a), "+r"(b), "+r"(c), "+r"(d)
            : "r"(one)
        );
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    uint64_t s = a + b + c + d;
    if (s == 0) printf("%llu", s);
    return end - start;
}

#endif /* __x86_64__ */

/* ═══════════════════════════════════════════════════════
 * Branch Prediction Penalty Probe
 * ═══════════════════════════════════════════════════════ */

static uint64_t probe_branch_predictable(uint32_t iters)
{
    register uint64_t sum = 0;
    prober_fence();
    uint64_t start = prober_get_ticks();

    /* Always-taken branch: perfectly predictable */
    for (uint32_t i = 0; i < iters; i++) {
        if (i < iters)  /* always true — CPU predicts correctly */
            sum += 1;
        else
            sum += 2;
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    if (sum == 0) printf("%llu", sum);
    return end - start;
}

static uint64_t probe_branch_random(uint32_t iters)
{
    /* Generate pseudo-random pattern to defeat branch predictor */
    uint32_t *pattern = (uint32_t *)malloc(iters * sizeof(uint32_t));
    if (!pattern) return 0;

    uint32_t rng = 0xDEADBEEF;
    for (uint32_t i = 0; i < iters; i++) {
        rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
        pattern[i] = rng & 1;
    }

    register uint64_t sum = 0;
    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < iters; i++) {
        if (pattern[i])
            sum += 1;
        else
            sum += 2;
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    free(pattern);
    if (sum == 0) printf("%llu", sum);
    return end - start;
}

/* ═══════════════════════════════════════════════════════
 * Memory Hierarchy Probe
 * ═══════════════════════════════════════════════════════ */

static double probe_cache_level(size_t array_size_bytes, uint32_t iters)
{
    size_t count = array_size_bytes / sizeof(uint64_t);
    if (count < 2) count = 2;

    uint64_t *arr = (uint64_t *)malloc(array_size_bytes);
    if (!arr) return -1.0;

    /* Build random pointer chase through array */
    for (size_t i = 0; i < count; i++)
        arr[i] = (i + 97) % count;  /* stride that spans cache lines */

    /* Warmup */
    uint64_t idx = 0;
    for (uint32_t i = 0; i < count * 2; i++)
        idx = arr[idx % count];

    prober_fence();
    uint64_t start = prober_get_ticks();

    for (uint32_t i = 0; i < iters; i++) {
        idx = arr[idx % count];
    }

    prober_fence();
    uint64_t end = prober_get_ticks();
    free(arr);

    if (idx == (uint64_t)-1) printf("%llu", idx);
    return ticks_to_cycles(end - start) / (double)iters;
}

/* ═══════════════════════════════════════════════════════
 * Public API Implementation
 * ═══════════════════════════════════════════════════════ */

int prober_measure_latency(probe_report_t *report,
                           const char *instr_name,
                           uint32_t iterations)
{
    if (!report || report->instr_count >= PROBE_MAX_INSTRS) return -1;

    double samples[SAMPLES];
    uint32_t chain_len = 0;
    uint64_t (*probe_fn)(uint32_t) = NULL;

    if (strcmp(instr_name, "ADD") == 0) {
        probe_fn = probe_add_latency;
        chain_len = LATENCY_UNROLL;
    } else if (strcmp(instr_name, "MUL") == 0) {
        probe_fn = probe_mul_latency;
        chain_len = 50;
    } else if (strcmp(instr_name, "SDIV") == 0 || strcmp(instr_name, "DIV") == 0) {
        probe_fn = probe_sdiv_latency;
        chain_len = 20;
    } else if (strcmp(instr_name, "LDR") == 0 || strcmp(instr_name, "LOAD") == 0) {
        probe_fn = probe_ldr_latency;
        chain_len = 50;
    } else if (strcmp(instr_name, "CMP+B") == 0) {
        probe_fn = probe_cmp_branch_latency;
        chain_len = 25;
    } else {
        return -1; /* unknown instruction */
    }

    /* Warmup */
    for (int w = 0; w < 3; w++) probe_fn(WARMUP_ITERS);

    for (int s = 0; s < SAMPLES; s++) {
        uint64_t total_ticks = probe_fn(iterations);
        double total_cycles = ticks_to_cycles(total_ticks);
        samples[s] = total_cycles / ((double)iterations * chain_len);
    }

    probe_result_t *r = &report->instrs[report->instr_count];
    r->instr_name = instr_name;
    r->latency_cycles = arr_mean(samples, SAMPLES);
    r->throughput_ipc = 0; /* filled by throughput probe */
    r->sample_count = SAMPLES;
    r->min_cycles = arr_min(samples, SAMPLES);
    r->max_cycles = arr_max(samples, SAMPLES);
    r->stddev_cycles = arr_stddev(samples, SAMPLES);
    report->instr_count++;
    return 0;
}

int prober_measure_throughput(probe_report_t *report,
                              const char *instr_name,
                              uint32_t iterations)
{
    if (!report) return -1;

    double samples[SAMPLES];
    uint32_t ops_per_iter = 0;
    uint64_t (*probe_fn)(uint32_t) = NULL;

    if (strcmp(instr_name, "ADD") == 0) {
        probe_fn = probe_add_throughput;
        ops_per_iter = 48; /* 6 batches × 8 independent ADDs */
    } else if (strcmp(instr_name, "MUL") == 0) {
        probe_fn = probe_mul_throughput;
        ops_per_iter = 24; /* 6 batches × 4 independent MULs */
    } else {
        return -1;
    }

    for (int w = 0; w < 3; w++) probe_fn(WARMUP_ITERS);

    for (int s = 0; s < SAMPLES; s++) {
        uint64_t total_ticks = probe_fn(iterations);
        double total_cycles = ticks_to_cycles(total_ticks);
        double cycles_per_iter = total_cycles / iterations;
        samples[s] = (double)ops_per_iter / cycles_per_iter;
    }

    /* Find existing entry and update throughput */
    for (uint32_t i = 0; i < report->instr_count; i++) {
        if (strcmp(report->instrs[i].instr_name, instr_name) == 0) {
            report->instrs[i].throughput_ipc = arr_mean(samples, SAMPLES);
            return 0;
        }
    }

    /* No existing entry — create one */
    if (report->instr_count < PROBE_MAX_INSTRS) {
        probe_result_t *r = &report->instrs[report->instr_count];
        r->instr_name = instr_name;
        r->latency_cycles = 0;
        r->throughput_ipc = arr_mean(samples, SAMPLES);
        r->sample_count = SAMPLES;
        r->min_cycles = arr_min(samples, SAMPLES);
        r->max_cycles = arr_max(samples, SAMPLES);
        r->stddev_cycles = arr_stddev(samples, SAMPLES);
        report->instr_count++;
    }
    return 0;
}

int prober_measure_branch(probe_report_t *report, uint32_t iterations)
{
    if (!report) return -1;

    double hit_samples[SAMPLES], miss_samples[SAMPLES];

    for (int w = 0; w < 3; w++) {
        probe_branch_predictable(iterations);
        probe_branch_random(iterations);
    }

    for (int s = 0; s < SAMPLES; s++) {
        hit_samples[s] = ticks_to_cycles(probe_branch_predictable(iterations)) / iterations;
        miss_samples[s] = ticks_to_cycles(probe_branch_random(iterations)) / iterations;
    }

    report->branch.predict_hit_cycles = arr_mean(hit_samples, SAMPLES);
    report->branch.predict_miss_cycles = arr_mean(miss_samples, SAMPLES);
    report->branch.miss_penalty = report->branch.predict_miss_cycles
                                  - report->branch.predict_hit_cycles;
    report->branch.sample_count = SAMPLES;
    return 0;
}

int prober_measure_memory(probe_report_t *report)
{
    if (!report) return -1;

    /* L1: 32KB array, L2: 256KB, L3: 4MB, RAM: 16MB */
    report->memory.l1_latency_cycles = probe_cache_level(32 * 1024, 50000);
    report->memory.l2_latency_cycles = probe_cache_level(256 * 1024, 20000);
    report->memory.l3_latency_cycles = probe_cache_level(4 * 1024 * 1024, 10000);
    report->memory.mem_latency_cycles = probe_cache_level(16 * 1024 * 1024, 5000);

    /* Cache sizes from sysctl (macOS) or hardcoded */
#ifdef __APPLE__
    {
        uint64_t val = 0; size_t sz = sizeof(val);
        if (sysctlbyname("hw.l1dcachesize", &val, &sz, NULL, 0) == 0)
            report->memory.l1_size_kb = (uint32_t)(val / 1024);
        if (sysctlbyname("hw.l2cachesize", &val, &sz, NULL, 0) == 0)
            report->memory.l2_size_kb = (uint32_t)(val / 1024);
        if (sysctlbyname("hw.l3cachesize", &val, &sz, NULL, 0) == 0)
            report->memory.l3_size_kb = (uint32_t)(val / 1024);
    }
#else
    report->memory.l1_size_kb = 32;
    report->memory.l2_size_kb = 256;
    report->memory.l3_size_kb = 8192;
#endif

    return 0;
}

int prober_run_all(probe_report_t *report)
{
    if (!report) return -1;

    printf("┌─────────────────────────────────────────────┐\n");
    printf("│  Vir Micro-Prober — %s                 │\n", report->arch);
    printf("│  CPU: %-36s │\n", report->cpu_name);
    printf("│  Timer: %llu Hz                        │\n",
           (unsigned long long)report->timer_freq_hz);
    printf("└─────────────────────────────────────────────┘\n\n");

    uint32_t lat_iters = 10000;
    uint32_t thr_iters = 10000;

    printf("[PROBE] ADD latency...\n");
    prober_measure_latency(report, "ADD", lat_iters);

    printf("[PROBE] MUL latency...\n");
    prober_measure_latency(report, "MUL", lat_iters);

    printf("[PROBE] DIV latency...\n");
    prober_measure_latency(report, "DIV", lat_iters);

    printf("[PROBE] LOAD latency...\n");
    prober_measure_latency(report, "LOAD", lat_iters);

    printf("[PROBE] CMP+B latency...\n");
    prober_measure_latency(report, "CMP+B", lat_iters);

    printf("[PROBE] ADD throughput...\n");
    prober_measure_throughput(report, "ADD", thr_iters);

    printf("[PROBE] MUL throughput...\n");
    prober_measure_throughput(report, "MUL", thr_iters);

    printf("[PROBE] Branch prediction...\n");
    prober_measure_branch(report, BRANCH_DEPTH);

    printf("[PROBE] Memory hierarchy...\n");
    prober_measure_memory(report);

    printf("\n");
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Report Output
 * ═══════════════════════════════════════════════════════ */

void prober_print_report(const probe_report_t *report)
{
    if (!report) return;

    printf("═══════════════════════════════════════════\n");
    printf("  CPU Micro-Architecture Report\n");
    printf("  Arch: %s | CPU: %s\n", report->arch, report->cpu_name);
    printf("  Timer: %llu Hz\n", (unsigned long long)report->timer_freq_hz);
    printf("═══════════════════════════════════════════\n\n");

    printf("── Instruction Latency & Throughput ────────\n");
    printf("%-10s %10s %10s %10s %10s\n",
           "Instr", "Latency", "Thru(IPC)", "Min", "Max");
    printf("%-10s %10s %10s %10s %10s\n",
           "─────", "───────", "────────", "───", "───");

    for (uint32_t i = 0; i < report->instr_count; i++) {
        const probe_result_t *r = &report->instrs[i];
        printf("%-10s %8.2f c %8.2f   %8.2f c %8.2f c\n",
               r->instr_name,
               r->latency_cycles,
               r->throughput_ipc,
               r->min_cycles,
               r->max_cycles);
    }

    printf("\n── Branch Prediction ───────────────────────\n");
    printf("  Predict hit:  %.2f cycles/branch\n", report->branch.predict_hit_cycles);
    printf("  Predict miss: %.2f cycles/branch\n", report->branch.predict_miss_cycles);
    printf("  Miss penalty: %.2f cycles\n", report->branch.miss_penalty);

    printf("\n── Memory Hierarchy ────────────────────────\n");
    printf("  L1 (%u KB): %.2f cycles\n",
           report->memory.l1_size_kb, report->memory.l1_latency_cycles);
    printf("  L2 (%u KB): %.2f cycles\n",
           report->memory.l2_size_kb, report->memory.l2_latency_cycles);
    printf("  L3 (%u KB): %.2f cycles\n",
           report->memory.l3_size_kb, report->memory.l3_latency_cycles);
    printf("  RAM:         %.2f cycles\n", report->memory.mem_latency_cycles);

    printf("\n═══════════════════════════════════════════\n");
}

int prober_export_json(const probe_report_t *report, const char *filepath)
{
    if (!report || !filepath) return -1;

    FILE *fp = fopen(filepath, "w");
    if (!fp) return -1;

    fprintf(fp, "{\n");
    fprintf(fp, "  \"arch\": \"%s\",\n", report->arch);
    fprintf(fp, "  \"cpu\": \"%s\",\n", report->cpu_name);
    fprintf(fp, "  \"timer_freq_hz\": %llu,\n", (unsigned long long)report->timer_freq_hz);

    /* Instructions */
    fprintf(fp, "  \"instructions\": [\n");
    for (uint32_t i = 0; i < report->instr_count; i++) {
        const probe_result_t *r = &report->instrs[i];
        fprintf(fp, "    {\n");
        fprintf(fp, "      \"name\": \"%s\",\n", r->instr_name);
        fprintf(fp, "      \"latency_cycles\": %.4f,\n", r->latency_cycles);
        fprintf(fp, "      \"throughput_ipc\": %.4f,\n", r->throughput_ipc);
        fprintf(fp, "      \"min_cycles\": %.4f,\n", r->min_cycles);
        fprintf(fp, "      \"max_cycles\": %.4f,\n", r->max_cycles);
        fprintf(fp, "      \"stddev_cycles\": %.4f\n", r->stddev_cycles);
        fprintf(fp, "    }%s\n", (i + 1 < report->instr_count) ? "," : "");
    }
    fprintf(fp, "  ],\n");

    /* Branch */
    fprintf(fp, "  \"branch\": {\n");
    fprintf(fp, "    \"predict_hit_cycles\": %.4f,\n", report->branch.predict_hit_cycles);
    fprintf(fp, "    \"predict_miss_cycles\": %.4f,\n", report->branch.predict_miss_cycles);
    fprintf(fp, "    \"miss_penalty\": %.4f\n", report->branch.miss_penalty);
    fprintf(fp, "  },\n");

    /* Memory */
    fprintf(fp, "  \"memory\": {\n");
    fprintf(fp, "    \"l1_size_kb\": %u,\n", report->memory.l1_size_kb);
    fprintf(fp, "    \"l1_latency_cycles\": %.4f,\n", report->memory.l1_latency_cycles);
    fprintf(fp, "    \"l2_size_kb\": %u,\n", report->memory.l2_size_kb);
    fprintf(fp, "    \"l2_latency_cycles\": %.4f,\n", report->memory.l2_latency_cycles);
    fprintf(fp, "    \"l3_size_kb\": %u,\n", report->memory.l3_size_kb);
    fprintf(fp, "    \"l3_latency_cycles\": %.4f,\n", report->memory.l3_latency_cycles);
    fprintf(fp, "    \"mem_latency_cycles\": %.4f\n", report->memory.mem_latency_cycles);
    fprintf(fp, "  }\n");

    fprintf(fp, "}\n");
    fclose(fp);
    return 0;
}

void prober_free(probe_report_t *report)
{
    if (report) memset(report, 0, sizeof(*report));
}

/* ═══════════════════════════════════════════════════════
 * Standalone Entry Point
 * ═══════════════════════════════════════════════════════ */

#ifdef PROBER_STANDALONE

int main(int argc, char **argv)
{
    const char *output = "data/probe_results.json";
    if (argc > 1) output = argv[1];

    probe_report_t report;
    prober_init(&report);
    prober_run_all(&report);
    prober_print_report(&report);

    if (prober_export_json(&report, output) == 0)
        printf("Results exported to: %s\n", output);
    else
        fprintf(stderr, "Failed to export results\n");

    prober_free(&report);
    return 0;
}

#endif /* PROBER_STANDALONE */

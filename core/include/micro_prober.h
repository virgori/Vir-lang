/*
 * micro_prober.h – CPU Micro-Architecture Prober
 * ================================================
 * Measures instruction latency, throughput, and branch penalty
 * on the actual hardware. Uses cycle counter (CNTVCT_EL0 on ARM64,
 * RDTSC on x86_64) for sub-nanosecond precision.
 *
 * Results feed into the Vir cost model for instruction scheduling
 * and register allocation decisions.
 */

#ifndef VIR_MICRO_PROBER_H
#define VIR_MICRO_PROBER_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * Cycle Counter
 * ═══════════════════════════════════════════════════════ */

/* We use platform-specific high-resolution timers.
 * On macOS ARM64, CNTVCT_EL0 runs at 24MHz (not CPU clock),
 * so we use mach_absolute_time() and convert to nanoseconds.
 * Values stored in nanoseconds; conversion to CPU cycles uses
 * estimated CPU frequency from sysctl. */

#ifdef __APPLE__
#include <mach/mach_time.h>
#endif

static inline uint64_t prober_get_ticks(void)
{
#ifdef __APPLE__
    return mach_absolute_time();
#elif defined(__aarch64__) || defined(_M_ARM64)
    uint64_t val;
    __asm__ volatile("mrs %0, CNTVCT_EL0" : "=r"(val));
    return val;
#elif defined(__x86_64__) || defined(_M_X64)
    uint32_t lo, hi;
    __asm__ volatile("rdtsc" : "=a"(lo), "=d"(hi));
    return ((uint64_t)hi << 32) | lo;
#else
    return 0;
#endif
}

static inline double prober_ticks_to_ns(uint64_t ticks)
{
#ifdef __APPLE__
    static mach_timebase_info_data_t info = {0, 0};
    if (info.denom == 0) mach_timebase_info(&info);
    return (double)ticks * (double)info.numer / (double)info.denom;
#else
    /* Assume ticks ≈ nanoseconds (TSC or timer-based) */
    return (double)ticks;
#endif
}

/* Serialize pipeline to ensure accurate measurement */
static inline void prober_fence(void)
{
#if defined(__aarch64__) || defined(_M_ARM64)
    __asm__ volatile("isb" ::: "memory");
#elif defined(__x86_64__) || defined(_M_X64)
    __asm__ volatile("mfence\nlfence" ::: "memory");
#endif
}

/* ═══════════════════════════════════════════════════════
 * Probe Result
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    const char *instr_name;     /* e.g. "ADD", "MUL", "LDR" */
    double      latency_cycles; /* measured latency in cycles */
    double      throughput_ipc; /* instructions per cycle */
    uint32_t    sample_count;   /* number of samples taken */
    double      min_cycles;
    double      max_cycles;
    double      stddev_cycles;
} probe_result_t;

/* Branch penalty measurement */
typedef struct {
    double      predict_hit_cycles;   /* cycles when branch predicted correctly */
    double      predict_miss_cycles;  /* cycles when branch mispredicted */
    double      miss_penalty;         /* miss_cycles - hit_cycles */
    uint32_t    sample_count;
} branch_result_t;

/* Memory hierarchy probe */
typedef struct {
    double      l1_latency_cycles;
    double      l2_latency_cycles;
    double      l3_latency_cycles;
    double      mem_latency_cycles;
    uint32_t    l1_size_kb;
    uint32_t    l2_size_kb;
    uint32_t    l3_size_kb;
} memory_result_t;

/* Full probe report */
#define PROBE_MAX_INSTRS 64

typedef struct {
    /* Platform info */
    const char    *arch;          /* "arm64" or "x86_64" */
    const char    *cpu_name;      /* e.g. "Apple M2" */
    uint64_t       timer_freq_hz; /* counter frequency */

    /* Instruction probes */
    probe_result_t instrs[PROBE_MAX_INSTRS];
    uint32_t       instr_count;

    /* Branch probe */
    branch_result_t branch;

    /* Memory probe */
    memory_result_t memory;
} probe_report_t;

/* ═══════════════════════════════════════════════════════
 * Public API
 * ═══════════════════════════════════════════════════════ */

/* Initialize probe report with platform info */
int prober_init(probe_report_t *report);

/* Probe instruction latency (serial dependency chain) */
int prober_measure_latency(probe_report_t *report,
                           const char *instr_name,
                           uint32_t iterations);

/* Probe instruction throughput (independent operations) */
int prober_measure_throughput(probe_report_t *report,
                              const char *instr_name,
                              uint32_t iterations);

/* Probe branch prediction penalty */
int prober_measure_branch(probe_report_t *report,
                          uint32_t iterations);

/* Probe memory hierarchy latencies */
int prober_measure_memory(probe_report_t *report);

/* Run all probes and generate full report */
int prober_run_all(probe_report_t *report);

/* Export report as JSON to file */
int prober_export_json(const probe_report_t *report,
                       const char *filepath);

/* Print report to stdout */
void prober_print_report(const probe_report_t *report);

/* Cleanup */
void prober_free(probe_report_t *report);

#ifdef __cplusplus
}
#endif

#endif /* VIR_MICRO_PROBER_H */

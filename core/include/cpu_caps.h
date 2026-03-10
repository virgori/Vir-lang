/*
 * cpu_caps.h – CPU Capability Detection & Memory Topology
 * =========================================================
 * Auto-detects at startup:
 *   - SIMD capabilities (NEON, AVX, AVX-512, AMX)
 *   - Cache hierarchy (L1/L2/L3 sizes, line size, associativity)
 *   - TLB entries and page sizes
 *   - Prefetch distance
 *   - CPU model, frequency, core count
 *
 * Results feed into Vir cost model for SIMD vectorization decisions
 * and data alignment optimizations.
 */

#ifndef VIR_CPU_CAPS_H
#define VIR_CPU_CAPS_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * SIMD Feature Flags
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    /* ARM64 features */
    bool neon;           /* ASIMD / NEON (128-bit) — always on ARM64 */
    bool neon_fp16;      /* NEON half-precision float */
    bool neon_dotprod;   /* SDOT/UDOT instructions */
    bool neon_i8mm;      /* Int8 matrix multiply */
    bool sve;            /* SVE (scalable vector) */
    uint32_t sve_width;  /* SVE vector width in bits (128-2048) */
    bool sve2;           /* SVE2 */
    bool amx;            /* Apple AMX (matrix coprocessor) */
    bool fp16;           /* FP16 arithmetic */
    bool bf16;           /* BFloat16 */
    bool sha256;         /* SHA-256 acceleration */
    bool aes;            /* AES acceleration */
    bool crc32;          /* CRC32 instructions */
    bool atomics;        /* LSE atomics (LDADD, CAS, SWP) */

    /* x86_64 features */
    bool sse;
    bool sse2;
    bool sse3;
    bool ssse3;
    bool sse4_1;
    bool sse4_2;
    bool avx;            /* AVX (256-bit) */
    bool avx2;           /* AVX2 (256-bit integer SIMD) */
    bool fma;            /* FMA3 (fused multiply-add) */
    bool avx512f;        /* AVX-512 Foundation */
    bool avx512bw;       /* AVX-512 Byte/Word */
    bool avx512dq;       /* AVX-512 Doubleword/Quadword */
    bool avx512vl;       /* AVX-512 VL (128/256-bit variants) */
    bool avx512vnni;     /* AVX-512 VNNI (int8/int16 dot product) */
    bool avx512bf16;     /* AVX-512 BFloat16 */
    bool amx_tile;       /* Intel AMX Tile */
    bool amx_int8;       /* Intel AMX INT8 */
    bool amx_bf16;       /* Intel AMX BF16 */

    /* Maximum SIMD width in bytes */
    uint32_t max_simd_width;
} simd_caps_t;


/* ═══════════════════════════════════════════════════════
 * Cache Topology
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    uint32_t size_kb;        /* Cache size in KB */
    uint32_t line_size;      /* Cache line size in bytes (typically 64) */
    uint32_t associativity;  /* N-way set associative */
    uint32_t sets;           /* Number of sets */
    bool     unified;        /* true = unified I+D, false = data-only or instr-only */
} cache_level_t;

typedef struct {
    cache_level_t l1d;       /* L1 Data cache */
    cache_level_t l1i;       /* L1 Instruction cache */
    cache_level_t l2;        /* L2 (usually unified) */
    cache_level_t l3;        /* L3 (may be 0 on Apple Silicon exposed differently) */
    uint32_t      cache_line_size;  /* System-wide cache line size */
} cache_topology_t;


/* ═══════════════════════════════════════════════════════
 * TLB Information
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    uint32_t l1_dtlb_entries;    /* L1 Data TLB entries */
    uint32_t l1_itlb_entries;    /* L1 Instruction TLB entries */
    uint32_t l2_tlb_entries;     /* L2 unified TLB entries */
    uint32_t page_size;          /* Default page size (4096 on most) */
    bool     huge_pages;         /* 2MB/1GB huge pages supported */
    uint32_t huge_page_size;     /* Huge page size in bytes */
} tlb_info_t;


/* ═══════════════════════════════════════════════════════
 * Prefetch Information
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    uint32_t hw_prefetch_distance;  /* Hardware prefetch lookahead (cache lines) */
    bool     sw_prefetch;           /* Software PREFETCH instruction supported */
    uint32_t prefetch_hint_size;    /* Optimal software prefetch distance (bytes) */
} prefetch_info_t;


/* ═══════════════════════════════════════════════════════
 * Complete CPU Capabilities
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    /* Identification */
    char arch[16];           /* "arm64" or "x86_64" */
    char cpu_model[128];     /* e.g. "Apple M2", "Intel i9-13900K" */
    char vendor[64];         /* "Apple", "Intel", "AMD" */
    uint32_t family;
    uint32_t model;
    uint32_t stepping;

    /* Cores & Frequency */
    uint32_t phys_cores;
    uint32_t perf_cores;     /* P-cores (Apple Silicon / big.LITTLE) */
    uint32_t eff_cores;      /* E-cores */
    uint64_t freq_hz;        /* Max frequency in Hz */

    /* Microarchitecture parameters */
    uint32_t issue_width;    /* Max instructions dispatched/cycle */
    uint32_t rob_entries;    /* Reorder buffer size */
    uint32_t phys_int_regs;
    uint32_t phys_fp_regs;

    /* Sub-structures */
    simd_caps_t     simd;
    cache_topology_t cache;
    tlb_info_t       tlb;
    prefetch_info_t  prefetch;
} cpu_caps_t;


/* ═══════════════════════════════════════════════════════
 * Public API
 * ═══════════════════════════════════════════════════════ */

/* Detect all CPU capabilities (call once at startup) */
int cpu_caps_detect(cpu_caps_t *caps);

/* Export capabilities to JSON file */
int cpu_caps_export_json(const cpu_caps_t *caps, const char *path);

/* Print human-readable summary */
void cpu_caps_print(const cpu_caps_t *caps);

/* Query helpers */
uint32_t cpu_caps_max_simd_width(const cpu_caps_t *caps);
bool cpu_caps_has_neon(const cpu_caps_t *caps);
bool cpu_caps_has_avx2(const cpu_caps_t *caps);
bool cpu_caps_has_avx512(const cpu_caps_t *caps);
bool cpu_caps_has_amx(const cpu_caps_t *caps);
uint32_t cpu_caps_cache_line_size(const cpu_caps_t *caps);

#ifdef __cplusplus
}
#endif

#endif /* VIR_CPU_CAPS_H */

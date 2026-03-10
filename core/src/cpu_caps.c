/*
 * cpu_caps.c – CPU Capability Detection & Memory Topology
 * =========================================================
 * Runtime detection of SIMD, cache, TLB, and prefetch capabilities.
 *
 * macOS:  Uses sysctl for all queries
 * Linux:  Uses /proc/cpuinfo + sysconf + cpuid
 * x86_64: Uses CPUID instruction directly
 */

#include "cpu_caps.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef __APPLE__
#include <sys/sysctl.h>
#include <mach/mach.h>
#endif

#ifdef __linux__
#include <unistd.h>
#endif

/* ═══════════════════════════════════════════════════════
 * Helpers
 * ═══════════════════════════════════════════════════════ */

#ifdef __APPLE__
static int sysctl_int(const char *name, uint64_t *out) {
    size_t len = sizeof(*out);
    *out = 0;
    return sysctlbyname(name, out, &len, NULL, 0);
}

static int sysctl_int32(const char *name, uint32_t *out) {
    uint64_t v = 0;
    size_t len = sizeof(v);
    int rc = sysctlbyname(name, &v, &len, NULL, 0);
    *out = (uint32_t)v;
    return rc;
}

static int sysctl_str(const char *name, char *buf, size_t buflen) {
    size_t len = buflen;
    buf[0] = '\0';
    return sysctlbyname(name, buf, &len, NULL, 0);
}
#endif

#if defined(__x86_64__) || defined(_M_X64)
static void do_cpuid(uint32_t leaf, uint32_t subleaf,
                     uint32_t *eax, uint32_t *ebx,
                     uint32_t *ecx, uint32_t *edx) {
    __asm__ volatile(
        "cpuid"
        : "=a"(*eax), "=b"(*ebx), "=c"(*ecx), "=d"(*edx)
        : "a"(leaf), "c"(subleaf)
    );
}

static uint64_t do_xgetbv(uint32_t xcr) {
    uint32_t lo, hi;
    __asm__ volatile("xgetbv" : "=a"(lo), "=d"(hi) : "c"(xcr));
    return ((uint64_t)hi << 32) | lo;
}
#endif

/* ═══════════════════════════════════════════════════════
 * ARM64 Detection (macOS / Linux)
 * ═══════════════════════════════════════════════════════ */

#if defined(__aarch64__) || defined(_M_ARM64)
static void detect_arm64_simd(cpu_caps_t *caps) {
    simd_caps_t *s = &caps->simd;

    /* NEON is mandatory on AArch64 */
    s->neon = true;
    s->max_simd_width = 16; /* 128-bit = 16 bytes */

#ifdef __APPLE__
    uint64_t v = 0;

    /* Apple Silicon feature flags via sysctl */
    if (sysctl_int("hw.optional.neon", &v) == 0) s->neon = (v != 0);
    if (sysctl_int("hw.optional.neon_fp16", &v) == 0) s->neon_fp16 = (v != 0);
    if (sysctl_int("hw.optional.armv8_2_sha256", &v) == 0) s->sha256 = (v != 0);
    if (sysctl_int("hw.optional.arm.FEAT_SHA256", &v) == 0) s->sha256 = (v != 0);
    if (sysctl_int("hw.optional.arm.FEAT_AES", &v) == 0) s->aes = (v != 0);
    if (sysctl_int("hw.optional.armv8_crc32", &v) == 0) s->crc32 = (v != 0);
    if (sysctl_int("hw.optional.arm.FEAT_DotProd", &v) == 0) s->neon_dotprod = (v != 0);
    if (sysctl_int("hw.optional.arm.FEAT_I8MM", &v) == 0) s->neon_i8mm = (v != 0);
    if (sysctl_int("hw.optional.arm.FEAT_BF16", &v) == 0) s->bf16 = (v != 0);
    if (sysctl_int("hw.optional.arm.FEAT_FP16", &v) == 0) s->fp16 = (v != 0);
    if (sysctl_int("hw.optional.arm.FEAT_LSE", &v) == 0) s->atomics = (v != 0);

    /* AMX detection — Apple doesn't officially expose this but we can check */
    if (sysctl_int("hw.optional.amx_version", &v) == 0 && v > 0) {
        s->amx = true;
    } else {
        /* Heuristic: all Apple Silicon M1+ have AMX */
        char brand[128] = {0};
        sysctl_str("machdep.cpu.brand_string", brand, sizeof(brand));
        if (strstr(brand, "Apple M") != NULL) {
            s->amx = true;
        }
    }

#elif defined(__linux__)
    /* Linux: read /proc/cpuinfo or use HWCAP */
    unsigned long hwcap = getauxval(AT_HWCAP);
    unsigned long hwcap2 = getauxval(AT_HWCAP2);
    s->neon = true; /* Always on AArch64 */
    s->neon_fp16 = (hwcap & (1UL << 9)) != 0;   /* HWCAP_FPHP */
    s->sha256 = (hwcap & (1UL << 6)) != 0;       /* HWCAP_SHA2 */
    s->aes = (hwcap & (1UL << 3)) != 0;           /* HWCAP_AES */
    s->crc32 = (hwcap & (1UL << 7)) != 0;         /* HWCAP_CRC32 */
    s->atomics = (hwcap & (1UL << 8)) != 0;       /* HWCAP_ATOMICS */
    s->neon_dotprod = (hwcap & (1UL << 20)) != 0;
    s->sve = (hwcap & (1UL << 22)) != 0;
    s->sve2 = (hwcap2 & (1UL << 1)) != 0;
    s->neon_i8mm = (hwcap2 & (1UL << 13)) != 0;
    s->bf16 = (hwcap2 & (1UL << 14)) != 0;
    if (s->sve) {
        /* Read SVE width */
        uint64_t vl;
        __asm__ volatile("rdvl %0, #1" : "=r"(vl));
        s->sve_width = (uint32_t)(vl * 8);
        s->max_simd_width = (uint32_t)vl;
    }
#endif
}

static void detect_arm64_cache(cpu_caps_t *caps) {
    cache_topology_t *c = &caps->cache;

    c->cache_line_size = 64; /* Default for ARM64 */

#ifdef __APPLE__
    uint64_t v = 0;

    if (sysctl_int("hw.cachelinesize", &v) == 0) c->cache_line_size = (uint32_t)v;

    /* L1 */
    if (sysctl_int("hw.l1dcachesize", &v) == 0) c->l1d.size_kb = (uint32_t)(v / 1024);
    if (sysctl_int("hw.l1icachesize", &v) == 0) c->l1i.size_kb = (uint32_t)(v / 1024);
    c->l1d.line_size = c->cache_line_size;
    c->l1i.line_size = c->cache_line_size;
    /* Apple M-series: L1D is typically 8-way, L1I is 6-way */
    c->l1d.associativity = 8;
    c->l1i.associativity = 6;

    /* L2 */
    if (sysctl_int("hw.l2cachesize", &v) == 0) c->l2.size_kb = (uint32_t)(v / 1024);
    c->l2.line_size = c->cache_line_size;
    c->l2.associativity = 16;
    c->l2.unified = true;

    /* L3 — Apple Silicon may not expose this */
    if (sysctl_int("hw.l3cachesize", &v) == 0 && v > 0) {
        c->l3.size_kb = (uint32_t)(v / 1024);
        c->l3.line_size = c->cache_line_size;
        c->l3.associativity = 16;
        c->l3.unified = true;
    }
#endif
}

static void detect_arm64_tlb(cpu_caps_t *caps) {
    tlb_info_t *t = &caps->tlb;

    /* Defaults for Apple M-series (estimated from documentation) */
    t->page_size = 16384;   /* macOS on ARM64 uses 16KB pages */
    t->l1_dtlb_entries = 256;
    t->l1_itlb_entries = 192;
    t->l2_tlb_entries = 4096;
    t->huge_pages = true;
    t->huge_page_size = 32 * 1024 * 1024;  /* 32MB "superpages" on macOS ARM64 */

#ifdef __APPLE__
    uint64_t v = 0;
    if (sysctl_int("hw.pagesize", &v) == 0) t->page_size = (uint32_t)v;
#endif
}

static void detect_arm64_prefetch(cpu_caps_t *caps) {
    prefetch_info_t *p = &caps->prefetch;

    /* Apple M-series: aggressive hardware prefetcher */
    p->hw_prefetch_distance = 16;  /* ~16 cache lines lookahead */
    p->sw_prefetch = true;         /* PRFM instruction available */
    p->prefetch_hint_size = 64 * 8; /* 8 cache lines ahead = 512 bytes */
}

static void detect_arm64_cpu(cpu_caps_t *caps) {
    snprintf(caps->arch, sizeof(caps->arch), "arm64");

#ifdef __APPLE__
    sysctl_str("machdep.cpu.brand_string", caps->cpu_model, sizeof(caps->cpu_model));
    snprintf(caps->vendor, sizeof(caps->vendor), "Apple");

    uint64_t v = 0;
    if (sysctl_int("hw.physicalcpu", &v) == 0) caps->phys_cores = (uint32_t)v;
    if (sysctl_int("hw.perflevel0.physicalcpu", &v) == 0) caps->perf_cores = (uint32_t)v;
    if (sysctl_int("hw.perflevel1.physicalcpu", &v) == 0) caps->eff_cores = (uint32_t)v;
    if (sysctl_int("hw.cpufrequency_max", &v) == 0) caps->freq_hz = v;
    if (caps->freq_hz == 0) caps->freq_hz = 3500000000ULL; /* M2 fallback */

    /* Microarchitecture estimates for Apple M-series */
    caps->issue_width = 8;
    caps->rob_entries = 600;
    caps->phys_int_regs = 320;
    caps->phys_fp_regs = 384;
#endif
}
#endif /* __aarch64__ */


/* ═══════════════════════════════════════════════════════
 * x86_64 Detection
 * ═══════════════════════════════════════════════════════ */

#if defined(__x86_64__) || defined(_M_X64)
static void detect_x86_simd(cpu_caps_t *caps) {
    simd_caps_t *s = &caps->simd;
    uint32_t eax, ebx, ecx, edx;

    /* CPUID leaf 1: basic features */
    do_cpuid(1, 0, &eax, &ebx, &ecx, &edx);
    s->sse    = (edx >> 25) & 1;
    s->sse2   = (edx >> 26) & 1;
    s->sse3   = (ecx >> 0)  & 1;
    s->ssse3  = (ecx >> 9)  & 1;
    s->sse4_1 = (ecx >> 19) & 1;
    s->sse4_2 = (ecx >> 20) & 1;
    s->fma    = (ecx >> 12) & 1;
    s->aes    = (ecx >> 25) & 1;
    bool osxsave = (ecx >> 27) & 1;
    bool avx_hw  = (ecx >> 28) & 1;

    /* Check OS support for YMM/ZMM registers */
    bool ymm_ok = false, zmm_ok = false;
    if (osxsave && avx_hw) {
        uint64_t xcr0 = do_xgetbv(0);
        ymm_ok = (xcr0 & 0x06) == 0x06;           /* XMM + YMM */
        zmm_ok = (xcr0 & 0xE6) == 0xE6;           /* XMM+YMM+ZMM+opmask */
    }

    s->avx = avx_hw && ymm_ok;

    /* CPUID leaf 7: extended features */
    do_cpuid(7, 0, &eax, &ebx, &ecx, &edx);
    s->avx2      = ymm_ok && ((ebx >> 5) & 1);
    s->avx512f   = zmm_ok && ((ebx >> 16) & 1);
    s->avx512bw  = zmm_ok && ((ebx >> 30) & 1);
    s->avx512dq  = zmm_ok && ((ebx >> 17) & 1);
    s->avx512vl  = zmm_ok && ((ebx >> 31) & 1);
    s->avx512vnni = zmm_ok && ((ecx >> 11) & 1);
    s->sha256    = (ebx >> 29) & 1;

    /* CPUID leaf 7 sub-leaf 1: more features */
    do_cpuid(7, 1, &eax, &ebx, &ecx, &edx);
    s->avx512bf16 = zmm_ok && ((eax >> 5) & 1);

    /* AMX (leaf 7, sub-leaf 0) */
    do_cpuid(7, 0, &eax, &ebx, &ecx, &edx);
    s->amx_tile = (edx >> 24) & 1;
    s->amx_int8 = (edx >> 25) & 1;
    s->amx_bf16 = (edx >> 22) & 1;

    /* Max SIMD width */
    if (s->avx512f)    s->max_simd_width = 64;
    else if (s->avx2)  s->max_simd_width = 32;
    else if (s->sse2)  s->max_simd_width = 16;
    else               s->max_simd_width = 8;
}

static void detect_x86_cache(cpu_caps_t *caps) {
    cache_topology_t *c = &caps->cache;
    uint32_t eax, ebx, ecx, edx;

    c->cache_line_size = 64;

    /* CPUID leaf 2 / leaf 4 for cache topology */
    for (uint32_t idx = 0; idx < 8; idx++) {
        do_cpuid(4, idx, &eax, &ebx, &ecx, &edx);
        uint32_t type = eax & 0x1F;
        if (type == 0) break;

        uint32_t level = (eax >> 5) & 0x07;
        uint32_t line  = ((ebx >> 0) & 0xFFF) + 1;
        uint32_t parts = ((ebx >> 12) & 0x3FF) + 1;
        uint32_t ways  = ((ebx >> 22) & 0x3FF) + 1;
        uint32_t sets  = ecx + 1;
        uint32_t size_kb = (ways * parts * line * sets) / 1024;
        bool unified = (type == 3);

        cache_level_t cl = {
            .size_kb = size_kb, .line_size = line,
            .associativity = ways, .sets = sets, .unified = unified
        };

        if (level == 1 && type == 1)      c->l1d = cl;
        else if (level == 1 && type == 2) c->l1i = cl;
        else if (level == 2)              c->l2 = cl;
        else if (level == 3)              c->l3 = cl;
    }

    c->cache_line_size = c->l1d.line_size ? c->l1d.line_size : 64;
}

static void detect_x86_cpu(cpu_caps_t *caps) {
    uint32_t eax, ebx, ecx, edx;
    snprintf(caps->arch, sizeof(caps->arch), "x86_64");

    /* Vendor string */
    do_cpuid(0, 0, &eax, &ebx, &ecx, &edx);
    memcpy(caps->vendor + 0, &ebx, 4);
    memcpy(caps->vendor + 4, &edx, 4);
    memcpy(caps->vendor + 8, &ecx, 4);
    caps->vendor[12] = '\0';

    /* Brand string (leaves 0x80000002-4) */
    for (uint32_t leaf = 0x80000002; leaf <= 0x80000004; leaf++) {
        do_cpuid(leaf, 0, &eax, &ebx, &ecx, &edx);
        uint32_t off = (leaf - 0x80000002) * 16;
        memcpy(caps->cpu_model + off + 0, &eax, 4);
        memcpy(caps->cpu_model + off + 4, &ebx, 4);
        memcpy(caps->cpu_model + off + 8, &ecx, 4);
        memcpy(caps->cpu_model + off + 12, &edx, 4);
    }
    caps->cpu_model[48] = '\0';

    /* Family/model/stepping */
    do_cpuid(1, 0, &eax, &ebx, &ecx, &edx);
    caps->family = ((eax >> 8) & 0xF) + ((eax >> 20) & 0xFF);
    caps->model = ((eax >> 4) & 0xF) | (((eax >> 16) & 0xF) << 4);
    caps->stepping = eax & 0xF;

    /* Core count (from OS) */
#ifdef __APPLE__
    uint64_t v;
    if (sysctl_int("hw.physicalcpu", &v) == 0) caps->phys_cores = (uint32_t)v;
    if (sysctl_int("hw.cpufrequency_max", &v) == 0) caps->freq_hz = v;
#elif defined(__linux__)
    caps->phys_cores = (uint32_t)sysconf(_SC_NPROCESSORS_ONLN);
#endif
}

static void detect_x86_tlb(cpu_caps_t *caps) {
    tlb_info_t *t = &caps->tlb;
    t->page_size = 4096;
    t->l1_dtlb_entries = 64;
    t->l1_itlb_entries = 64;
    t->l2_tlb_entries = 1536;
    t->huge_pages = true;
    t->huge_page_size = 2 * 1024 * 1024; /* 2MB */
}

static void detect_x86_prefetch(cpu_caps_t *caps) {
    prefetch_info_t *p = &caps->prefetch;
    p->hw_prefetch_distance = 8;
    p->sw_prefetch = true;
    p->prefetch_hint_size = 64 * 4; /* 4 lines = 256 bytes */
}
#endif /* __x86_64__ */


/* ═══════════════════════════════════════════════════════
 * Public API
 * ═══════════════════════════════════════════════════════ */

int cpu_caps_detect(cpu_caps_t *caps)
{
    if (!caps) return -1;
    memset(caps, 0, sizeof(*caps));

#if defined(__aarch64__) || defined(_M_ARM64)
    detect_arm64_cpu(caps);
    detect_arm64_simd(caps);
    detect_arm64_cache(caps);
    detect_arm64_tlb(caps);
    detect_arm64_prefetch(caps);
#elif defined(__x86_64__) || defined(_M_X64)
    detect_x86_cpu(caps);
    detect_x86_simd(caps);
    detect_x86_cache(caps);
    detect_x86_tlb(caps);
    detect_x86_prefetch(caps);
#else
    snprintf(caps->arch, sizeof(caps->arch), "unknown");
    return -1;
#endif

    return 0;
}

int cpu_caps_export_json(const cpu_caps_t *caps, const char *path)
{
    if (!caps || !path) return -1;

    FILE *f = fopen(path, "w");
    if (!f) return -1;

    fprintf(f, "{\n");
    fprintf(f, "  \"arch\": \"%s\",\n", caps->arch);
    fprintf(f, "  \"cpu_model\": \"%s\",\n", caps->cpu_model);
    fprintf(f, "  \"vendor\": \"%s\",\n", caps->vendor);
    fprintf(f, "  \"phys_cores\": %u,\n", caps->phys_cores);
    fprintf(f, "  \"perf_cores\": %u,\n", caps->perf_cores);
    fprintf(f, "  \"eff_cores\": %u,\n", caps->eff_cores);
    fprintf(f, "  \"freq_hz\": %llu,\n", (unsigned long long)caps->freq_hz);
    fprintf(f, "  \"issue_width\": %u,\n", caps->issue_width);
    fprintf(f, "  \"rob_entries\": %u,\n", caps->rob_entries);

    /* SIMD */
    fprintf(f, "  \"simd\": {\n");
    fprintf(f, "    \"neon\": %s,\n", caps->simd.neon ? "true" : "false");
    fprintf(f, "    \"neon_fp16\": %s,\n", caps->simd.neon_fp16 ? "true" : "false");
    fprintf(f, "    \"neon_dotprod\": %s,\n", caps->simd.neon_dotprod ? "true" : "false");
    fprintf(f, "    \"neon_i8mm\": %s,\n", caps->simd.neon_i8mm ? "true" : "false");
    fprintf(f, "    \"sve\": %s,\n", caps->simd.sve ? "true" : "false");
    fprintf(f, "    \"sve_width\": %u,\n", caps->simd.sve_width);
    fprintf(f, "    \"amx\": %s,\n", caps->simd.amx ? "true" : "false");
    fprintf(f, "    \"fp16\": %s,\n", caps->simd.fp16 ? "true" : "false");
    fprintf(f, "    \"bf16\": %s,\n", caps->simd.bf16 ? "true" : "false");
    fprintf(f, "    \"aes\": %s,\n", caps->simd.aes ? "true" : "false");
    fprintf(f, "    \"sha256\": %s,\n", caps->simd.sha256 ? "true" : "false");
    fprintf(f, "    \"atomics\": %s,\n", caps->simd.atomics ? "true" : "false");
    fprintf(f, "    \"avx\": %s,\n", caps->simd.avx ? "true" : "false");
    fprintf(f, "    \"avx2\": %s,\n", caps->simd.avx2 ? "true" : "false");
    fprintf(f, "    \"avx512f\": %s,\n", caps->simd.avx512f ? "true" : "false");
    fprintf(f, "    \"avx512vnni\": %s,\n", caps->simd.avx512vnni ? "true" : "false");
    fprintf(f, "    \"amx_tile\": %s,\n", caps->simd.amx_tile ? "true" : "false");
    fprintf(f, "    \"amx_int8\": %s,\n", caps->simd.amx_int8 ? "true" : "false");
    fprintf(f, "    \"amx_bf16\": %s,\n", caps->simd.amx_bf16 ? "true" : "false");
    fprintf(f, "    \"max_simd_width\": %u\n", caps->simd.max_simd_width);
    fprintf(f, "  },\n");

    /* Cache */
    fprintf(f, "  \"cache\": {\n");
    fprintf(f, "    \"line_size\": %u,\n", caps->cache.cache_line_size);
    fprintf(f, "    \"l1d_size_kb\": %u,\n", caps->cache.l1d.size_kb);
    fprintf(f, "    \"l1d_assoc\": %u,\n", caps->cache.l1d.associativity);
    fprintf(f, "    \"l1i_size_kb\": %u,\n", caps->cache.l1i.size_kb);
    fprintf(f, "    \"l2_size_kb\": %u,\n", caps->cache.l2.size_kb);
    fprintf(f, "    \"l2_assoc\": %u,\n", caps->cache.l2.associativity);
    fprintf(f, "    \"l3_size_kb\": %u,\n", caps->cache.l3.size_kb);
    fprintf(f, "    \"l3_assoc\": %u\n", caps->cache.l3.associativity);
    fprintf(f, "  },\n");

    /* TLB */
    fprintf(f, "  \"tlb\": {\n");
    fprintf(f, "    \"page_size\": %u,\n", caps->tlb.page_size);
    fprintf(f, "    \"l1_dtlb_entries\": %u,\n", caps->tlb.l1_dtlb_entries);
    fprintf(f, "    \"l1_itlb_entries\": %u,\n", caps->tlb.l1_itlb_entries);
    fprintf(f, "    \"l2_tlb_entries\": %u,\n", caps->tlb.l2_tlb_entries);
    fprintf(f, "    \"huge_pages\": %s,\n", caps->tlb.huge_pages ? "true" : "false");
    fprintf(f, "    \"huge_page_size\": %u\n", caps->tlb.huge_page_size);
    fprintf(f, "  },\n");

    /* Prefetch */
    fprintf(f, "  \"prefetch\": {\n");
    fprintf(f, "    \"hw_prefetch_distance\": %u,\n", caps->prefetch.hw_prefetch_distance);
    fprintf(f, "    \"sw_prefetch\": %s,\n", caps->prefetch.sw_prefetch ? "true" : "false");
    fprintf(f, "    \"prefetch_hint_size\": %u\n", caps->prefetch.prefetch_hint_size);
    fprintf(f, "  }\n");

    fprintf(f, "}\n");
    fclose(f);
    return 0;
}

void cpu_caps_print(const cpu_caps_t *caps)
{
    if (!caps) return;

    printf("═══ CPU Capabilities ═══════════════════════════\n");
    printf("  Arch:    %s\n", caps->arch);
    printf("  CPU:     %s\n", caps->cpu_model);
    printf("  Vendor:  %s\n", caps->vendor);
    printf("  Cores:   %u total (%u P-cores + %u E-cores)\n",
           caps->phys_cores, caps->perf_cores, caps->eff_cores);
    printf("  Freq:    %.2f GHz\n", caps->freq_hz / 1e9);
    printf("  Issue:   %u-wide\n", caps->issue_width);
    printf("  ROB:     %u entries\n", caps->rob_entries);

    printf("\n═══ SIMD Features ═══════════════════════════════\n");
    printf("  Max SIMD width: %u bytes (%u-bit)\n",
           caps->simd.max_simd_width, caps->simd.max_simd_width * 8);

#if defined(__aarch64__)
    printf("  NEON:     %s\n", caps->simd.neon ? "YES" : "no");
    printf("  NEON FP16:%s\n", caps->simd.neon_fp16 ? "YES" : "no");
    printf("  DotProd:  %s\n", caps->simd.neon_dotprod ? "YES" : "no");
    printf("  I8MM:     %s\n", caps->simd.neon_i8mm ? "YES" : "no");
    printf("  BF16:     %s\n", caps->simd.bf16 ? "YES" : "no");
    printf("  SVE:      %s", caps->simd.sve ? "YES" : "no");
    if (caps->simd.sve) printf(" (%u-bit)", caps->simd.sve_width);
    printf("\n");
    printf("  AMX:      %s\n", caps->simd.amx ? "YES" : "no");
    printf("  AES:      %s\n", caps->simd.aes ? "YES" : "no");
    printf("  SHA-256:  %s\n", caps->simd.sha256 ? "YES" : "no");
    printf("  CRC32:    %s\n", caps->simd.crc32 ? "YES" : "no");
    printf("  Atomics:  %s\n", caps->simd.atomics ? "YES" : "no");
#elif defined(__x86_64__)
    printf("  SSE4.2:   %s\n", caps->simd.sse4_2 ? "YES" : "no");
    printf("  AVX:      %s\n", caps->simd.avx ? "YES" : "no");
    printf("  AVX2:     %s\n", caps->simd.avx2 ? "YES" : "no");
    printf("  FMA:      %s\n", caps->simd.fma ? "YES" : "no");
    printf("  AVX-512F: %s\n", caps->simd.avx512f ? "YES" : "no");
    printf("  AVX-512VNNI: %s\n", caps->simd.avx512vnni ? "YES" : "no");
    printf("  AMX Tile: %s\n", caps->simd.amx_tile ? "YES" : "no");
    printf("  AMX INT8: %s\n", caps->simd.amx_int8 ? "YES" : "no");
#endif

    printf("\n═══ Cache Topology ═════════════════════════════\n");
    printf("  Line size:  %u bytes\n", caps->cache.cache_line_size);
    printf("  L1D:  %u KB  %u-way\n", caps->cache.l1d.size_kb, caps->cache.l1d.associativity);
    printf("  L1I:  %u KB  %u-way\n", caps->cache.l1i.size_kb, caps->cache.l1i.associativity);
    printf("  L2:   %u KB  %u-way\n", caps->cache.l2.size_kb, caps->cache.l2.associativity);
    printf("  L3:   %u KB  %u-way\n", caps->cache.l3.size_kb, caps->cache.l3.associativity);

    printf("\n═══ TLB ════════════════════════════════════════\n");
    printf("  Page size:     %u bytes\n", caps->tlb.page_size);
    printf("  L1 dTLB:       %u entries\n", caps->tlb.l1_dtlb_entries);
    printf("  L1 iTLB:       %u entries\n", caps->tlb.l1_itlb_entries);
    printf("  L2 TLB:        %u entries\n", caps->tlb.l2_tlb_entries);
    printf("  Huge pages:    %s (%u bytes)\n",
           caps->tlb.huge_pages ? "YES" : "no", caps->tlb.huge_page_size);

    printf("\n═══ Prefetch ═══════════════════════════════════\n");
    printf("  HW distance:   %u cache lines\n", caps->prefetch.hw_prefetch_distance);
    printf("  SW PREFETCH:   %s\n", caps->prefetch.sw_prefetch ? "YES" : "no");
    printf("  Opt. distance: %u bytes\n", caps->prefetch.prefetch_hint_size);
    printf("════════════════════════════════════════════════\n");
}

uint32_t cpu_caps_max_simd_width(const cpu_caps_t *caps) {
    return caps ? caps->simd.max_simd_width : 0;
}
bool cpu_caps_has_neon(const cpu_caps_t *caps) {
    return caps ? caps->simd.neon : false;
}
bool cpu_caps_has_avx2(const cpu_caps_t *caps) {
    return caps ? caps->simd.avx2 : false;
}
bool cpu_caps_has_avx512(const cpu_caps_t *caps) {
    return caps ? caps->simd.avx512f : false;
}
bool cpu_caps_has_amx(const cpu_caps_t *caps) {
    return caps ? (caps->simd.amx || caps->simd.amx_tile) : false;
}
uint32_t cpu_caps_cache_line_size(const cpu_caps_t *caps) {
    return caps ? caps->cache.cache_line_size : 64;
}

/* ═══════════════════════════════════════════════════════
 * Standalone main
 * ═══════════════════════════════════════════════════════ */

#ifdef CPU_CAPS_STANDALONE
int main(int argc, char *argv[])
{
    cpu_caps_t caps;
    cpu_caps_detect(&caps);
    cpu_caps_print(&caps);

    const char *out = (argc > 1) ? argv[1] : "data/arch/cpu_caps.json";
    if (cpu_caps_export_json(&caps, out) == 0) {
        printf("\nExported: %s\n", out);
    }
    return 0;
}
#endif

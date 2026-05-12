/*
 * amx_accel.c – AMX Matrix Acceleration
 * ========================================
 * Apple AMX via inline asm (MSR S3_4_C15_Cn_op).
 * Intel AMX via _tile* intrinsics.
 * Fallback: tiled NEON/AVX micro-kernel GEMM.
 */

#include "amx_accel.h"
#include "simd_dispatch.h"

#include <string.h>
#include <stdio.h>

/* ── Stats ───────────────────────────────────────────── */
static amx_stats_t g_stats;
static amx_backend_t g_backend = AMX_BACKEND_NONE;

/* ═══════════════════════════════════════════════════════
 * Detection
 * ═══════════════════════════════════════════════════════ */

amx_backend_t amx_detect(const cpu_caps_t *caps)
{
    if (!caps) return AMX_BACKEND_FALLBACK;

#if defined(__aarch64__)
    if (caps->simd.amx)
        return AMX_BACKEND_APPLE_AMX;
#endif

#if defined(__x86_64__) || defined(_M_X64)
    if (caps->simd.amx_tile && caps->simd.amx_bf16)
        return AMX_BACKEND_INTEL_AMX;
#endif

    return AMX_BACKEND_FALLBACK;
}

/* ═══════════════════════════════════════════════════════
 * Apple AMX (M1-M4)
 *
 * Reverse-engineered encoding (corsix/amx):
 *   AMX_SET:   msr s3_4_c15_c0_0, xzr   — enable
 *   AMX_CLR:   msr s3_4_c15_c0_1, xzr   — disable
 *   AMX_LDX:   msr s3_4_c15_c1_0, xN    — load row→X
 *   AMX_LDY:   msr s3_4_c15_c1_1, xN    — load row→Y
 *   AMX_STZ:   msr s3_4_c15_c1_2, xN    — store Z→mem
 *   AMX_FMA32: msr s3_4_c15_c6_0, xN    — Z += X × Y (FP32)
 *
 * xN encodes: row index (bits 56-63), memory address (bits 0-55).
 * For FMA32: bits encode X/Z offsets.
 * ═══════════════════════════════════════════════════════ */

#if defined(__aarch64__) && defined(__APPLE__)

void amx_apple_enable(void)
{
    __asm__ volatile(".word 0x00201020" ::: "memory");
    /* AMX_SET encoded as: msr s3_4_c15_c0_0, xzr → hex 0x00201020 */
}

void amx_apple_disable(void)
{
    __asm__ volatile(".word 0x00201021" ::: "memory");
    /* AMX_CLR */
}

/*
 * Apple AMX FMA32 tile multiply-accumulate (16×16 FP32).
 * Loads A rows into X register, B rows into Y, accumulates in Z,
 * then stores Z back to C.
 *
 * Simplified: we use the AMX to do 16×16 outer-product
 * accumulations row by row.
 */
void amx_apple_fma32_tile(const float *A, const float *B, float *C)
{
    /* Enable AMX */
    amx_apple_enable();

    /* For each of the 16 rows in A: load row, multiply with all B, accumulate. */
    for (int row = 0; row < 16; row++) {
        /* AMX_LDX: load A row (64 bytes = 16 floats) into X register.
         * Operand: (row << 56) | address */
        uint64_t ldx_op = ((uint64_t)row << 56) | (uint64_t)(A + row * 16);
        __asm__ volatile(
            "mov x0, %0\n\t"
            ".word 0x00201040\n\t"  /* AMX_LDX with x0 */
            :
            : "r"(ldx_op)
            : "x0", "memory"
        );
    }

    for (int row = 0; row < 16; row++) {
        uint64_t ldy_op = ((uint64_t)row << 56) | (uint64_t)(B + row * 16);
        __asm__ volatile(
            "mov x0, %0\n\t"
            ".word 0x00201041\n\t"  /* AMX_LDY with x0 */
            :
            : "r"(ldy_op)
            : "x0", "memory"
        );
    }

    /* AMX_FMA32: Z += X × Y for FP32 16×16 */
    __asm__ volatile(
        "mov x0, #0\n\t"
        ".word 0x002010C0\n\t"  /* AMX_FMA32 with x0 */
        ::: "x0", "memory"
    );

    /* Store Z rows back to C */
    for (int row = 0; row < 16; row++) {
        uint64_t stz_op = ((uint64_t)row << 56) | (uint64_t)(C + row * 16);
        __asm__ volatile(
            "mov x0, %0\n\t"
            ".word 0x00201042\n\t"  /* AMX_STZ with x0 */
            :
            : "r"(stz_op)
            : "x0", "memory"
        );
    }

    amx_apple_disable();
}

static void apple_amx_sgemm(
    int M, int N, int K,
    float alpha, const float *A, int lda,
    const float *B, int ldb,
    float beta, float *C, int ldc)
{
    /* Scale C by beta first */
    if (beta != 1.0f) {
        const simd_dispatch_t *sd = simd_dispatch_get();
        for (int i = 0; i < M; i++)
            sd->vscale_f32(C + i * ldc, C + i * ldc, beta, (size_t)N);
    }

    /* Tiled GEMM: 16×16 tiles via AMX */
    float tile_A[16 * 16] __attribute__((aligned(64)));
    float tile_B[16 * 16] __attribute__((aligned(64)));
    float tile_C[16 * 16] __attribute__((aligned(64)));

    for (int ti = 0; ti < M; ti += 16) {
        int tile_m = (ti + 16 <= M) ? 16 : M - ti;
        for (int tj = 0; tj < N; tj += 16) {
            int tile_n = (tj + 16 <= N) ? 16 : N - tj;

            /* Load C tile */
            memset(tile_C, 0, sizeof(tile_C));
            for (int r = 0; r < tile_m; r++)
                memcpy(tile_C + r * 16, C + (ti + r) * ldc + tj,
                       (size_t)tile_n * sizeof(float));

            for (int tk = 0; tk < K; tk += 16) {
                int tile_k = (tk + 16 <= K) ? 16 : K - tk;

                /* Pack A tile [tile_m×tile_k] zero-padded to 16×16 */
                memset(tile_A, 0, sizeof(tile_A));
                for (int r = 0; r < tile_m; r++)
                    memcpy(tile_A + r * 16, A + (ti + r) * lda + tk,
                           (size_t)tile_k * sizeof(float));

                /* Pack B tile [tile_k×tile_n] zero-padded to 16×16 */
                memset(tile_B, 0, sizeof(tile_B));
                for (int r = 0; r < tile_k; r++)
                    memcpy(tile_B + r * 16, B + (tk + r) * ldb + tj,
                           (size_t)tile_n * sizeof(float));

                amx_apple_fma32_tile(tile_A, tile_B, tile_C);
            }

            /* Scale by alpha and store back */
            for (int r = 0; r < tile_m; r++)
                for (int c = 0; c < tile_n; c++)
                    C[(ti + r) * ldc + tj + c] += alpha * tile_C[r * 16 + c];
        }
    }
}

#else
void amx_apple_enable(void)  { /* no-op */ }
void amx_apple_disable(void) { /* no-op */ }
void amx_apple_fma32_tile(const float *A, const float *B, float *C)
{ (void)A; (void)B; (void)C; }
#endif /* __aarch64__ && __APPLE__ */

/* ═══════════════════════════════════════════════════════
 * Fallback GEMM (tiled NEON/AVX micro-kernel)
 * ═══════════════════════════════════════════════════════ */

static void fallback_sgemm(
    int M, int N, int K,
    float alpha, const float *A, int lda,
    const float *B, int ldb,
    float beta, float *C, int ldc)
{
    const simd_dispatch_t *sd = simd_dispatch_get();

    /* Scale C by beta */
    if (beta != 1.0f) {
        for (int i = 0; i < M; i++)
            sd->vscale_f32(C + i * ldc, C + i * ldc, beta, (size_t)N);
    }

    /* Naive tiled: 8×8 micro-tiles */
    #define TILE 8
    for (int ti = 0; ti < M; ti += TILE) {
        int mi = (ti + TILE <= M) ? TILE : M - ti;
        for (int tj = 0; tj < N; tj += TILE) {
            int nj = (tj + TILE <= N) ? TILE : N - tj;
            for (int tk = 0; tk < K; tk += TILE) {
                int kk = (tk + TILE <= K) ? TILE : K - tk;
                for (int ii = 0; ii < mi; ii++) {
                    for (int kk2 = 0; kk2 < kk; kk2++) {
                        float a_val = alpha * A[(ti + ii) * lda + tk + kk2];
                        for (int jj = 0; jj < nj; jj++) {
                            C[(ti + ii) * ldc + tj + jj] +=
                                a_val * B[(tk + kk2) * ldb + tj + jj];
                        }
                    }
                }
            }
        }
    }
    #undef TILE
}

/* ═══════════════════════════════════════════════════════
 * Public GEMM Dispatch
 * ═══════════════════════════════════════════════════════ */

void amx_sgemm(
    int M, int N, int K,
    float alpha, const float *A, int lda,
    const float *B, int ldb,
    float beta, float *C, int ldc)
{
    /* Lazy init backend detection */
    if (g_backend == AMX_BACKEND_NONE) {
        cpu_caps_t caps;
        cpu_caps_detect(&caps);
        g_backend = amx_detect(&caps);
        g_stats.backend = g_backend;
    }

    g_stats.gemm_calls++;
    g_stats.total_flops += (uint64_t)2 * M * N * K;

    switch (g_backend) {
#if defined(__aarch64__) && defined(__APPLE__)
    case AMX_BACKEND_APPLE_AMX:
        apple_amx_sgemm(M, N, K, alpha, A, lda, B, ldb, beta, C, ldc);
        return;
#endif
    case AMX_BACKEND_INTEL_AMX:
        /* Intel AMX path — TODO when Sapphire Rapids HW available */
        /* Falls through to fallback for now */
    case AMX_BACKEND_FALLBACK:
    default:
        fallback_sgemm(M, N, K, alpha, A, lda, B, ldb, beta, C, ldc);
        return;
    }
}

/* ═══════════════════════════════════════════════════════
 * Statistics
 * ═══════════════════════════════════════════════════════ */

void amx_get_stats(amx_stats_t *stats)
{
    if (stats) *stats = g_stats;
}

void amx_reset_stats(void)
{
    amx_backend_t b = g_stats.backend;
    memset(&g_stats, 0, sizeof(g_stats));
    g_stats.backend = b;
}

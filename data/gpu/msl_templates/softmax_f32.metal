// Metal Compute Kernel: Softmax (per-row)
// Numerically stable: subtract row max, exp, sum, normalize
// Threadgroup: (256, 1, 1)  Grid: (M, 1, 1)  — one threadgroup per row

#include <metal_stdlib>
using namespace metal;

kernel void vir_softmax_f32(
    device const float* A [[buffer(0)]],   // M × N
    device float*       C [[buffer(1)]],   // M × N
    constant uint&      N [[buffer(2)]],
    uint  row    [[threadgroup_position_in_grid]],
    uint  tx     [[thread_index_in_threadgroup]],
    uint  tg_sz  [[threads_per_threadgroup]]
) {
    threadgroup float smem[256];

    device const float* row_in  = A + row * N;
    device float*       row_out = C + row * N;

    // Phase 1: Thread-local max
    float local_max = -INFINITY;
    for (uint i = tx; i < N; i += tg_sz) {
        local_max = max(local_max, row_in[i]);
    }
    smem[tx] = local_max;
    threadgroup_barrier(mem_flags::mem_threadgroup);

    // Parallel reduction for max
    for (uint s = tg_sz / 2; s > 0; s >>= 1) {
        if (tx < s) {
            smem[tx] = max(smem[tx], smem[tx + s]);
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    float row_max = smem[0];
    threadgroup_barrier(mem_flags::mem_threadgroup);

    // Phase 2: exp(x - max) and partial sum
    float local_sum = 0.0f;
    for (uint i = tx; i < N; i += tg_sz) {
        float e = exp(row_in[i] - row_max);
        row_out[i] = e;
        local_sum += e;
    }
    smem[tx] = local_sum;
    threadgroup_barrier(mem_flags::mem_threadgroup);

    // Parallel reduction for sum
    for (uint s = tg_sz / 2; s > 0; s >>= 1) {
        if (tx < s) {
            smem[tx] += smem[tx + s];
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    float inv_sum = 1.0f / smem[0];
    threadgroup_barrier(mem_flags::mem_threadgroup);

    // Phase 3: Normalize
    for (uint i = tx; i < N; i += tg_sz) {
        row_out[i] *= inv_sum;
    }
}

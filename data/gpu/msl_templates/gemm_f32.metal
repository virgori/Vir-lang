// Metal Compute Kernel: Tiled GEMM (C = A × B)
// Uses threadgroup memory and simdgroup operations for Apple Silicon
// Tile: 32×32, K-tiles of 32
// Threadgroup: (32, 32, 1)  Grid: (ceil(N/32), ceil(M/32), 1)

#include <metal_stdlib>
using namespace metal;

kernel void vir_gemm_f32(
    device const float* A [[buffer(0)]],   // M × K
    device const float* B [[buffer(1)]],   // K × N
    device float*       C [[buffer(2)]],   // M × N
    constant uint&      M [[buffer(3)]],
    constant uint&      N [[buffer(4)]],
    constant uint&      K [[buffer(5)]],
    uint2 tid   [[thread_position_in_threadgroup]],
    uint2 gid   [[threadgroup_position_in_grid]]
) {
    constexpr uint TILE = 32;

    threadgroup float sA[TILE][TILE];
    threadgroup float sB[TILE][TILE];

    uint row = gid.y * TILE + tid.y;
    uint col = gid.x * TILE + tid.x;

    float acc = 0.0f;

    for (uint k_tile = 0; k_tile < K; k_tile += TILE) {
        // Load A tile
        uint a_col = k_tile + tid.x;
        if (row < M && a_col < K) {
            sA[tid.y][tid.x] = A[row * K + a_col];
        } else {
            sA[tid.y][tid.x] = 0.0f;
        }

        // Load B tile
        uint b_row = k_tile + tid.y;
        if (b_row < K && col < N) {
            sB[tid.y][tid.x] = B[b_row * N + col];
        } else {
            sB[tid.y][tid.x] = 0.0f;
        }

        threadgroup_barrier(mem_flags::mem_threadgroup);

        // Accumulate
        for (uint i = 0; i < TILE; i++) {
            acc = fma(sA[tid.y][i], sB[i][tid.x], acc);
        }

        threadgroup_barrier(mem_flags::mem_threadgroup);
    }

    if (row < M && col < N) {
        C[row * N + col] = acc;
    }
}

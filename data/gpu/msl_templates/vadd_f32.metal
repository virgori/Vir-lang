// Metal Compute Kernel: Vector Addition
// Usage: vir_metal_compile_msl(msl_source, msl_len, &pipeline)
// Dispatch: threads_per_grid = N, threads_per_group = 256

#include <metal_stdlib>
using namespace metal;

kernel void vir_vadd_f32(
    device const float* A [[buffer(0)]],
    device const float* B [[buffer(1)]],
    device float*       C [[buffer(2)]],
    constant uint&      N [[buffer(3)]],
    uint tid [[thread_position_in_grid]]
) {
    if (tid >= N) return;
    C[tid] = A[tid] + B[tid];
}

// Metal Compute Kernel: Fused ReLU + Vector Add
// C[i] = max(0, A[i]) + B[i]
// Single-pass fusion — no intermediate buffer allocation

#include <metal_stdlib>
using namespace metal;

kernel void vir_fused_relu_add_f32(
    device const float* A [[buffer(0)]],
    device const float* B [[buffer(1)]],
    device float*       C [[buffer(2)]],
    constant uint&      N [[buffer(3)]],
    uint tid [[thread_position_in_grid]]
) {
    if (tid >= N) return;
    C[tid] = max(0.0f, A[tid]) + B[tid];
}

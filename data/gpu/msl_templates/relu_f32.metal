// Metal Compute Kernel: ReLU Activation (element-wise)
// C[i] = max(0, A[i])

#include <metal_stdlib>
using namespace metal;

kernel void vir_relu_f32(
    device const float* A [[buffer(0)]],
    device float*       C [[buffer(1)]],
    constant uint&      N [[buffer(2)]],
    uint tid [[thread_position_in_grid]]
) {
    if (tid >= N) return;
    C[tid] = max(0.0f, A[tid]);
}

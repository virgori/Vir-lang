# Vir Compiler Optimizations

Thư mục này chứa đặc tả kỹ thuật và báo cáo hiệu năng của các tầng tối ưu hóa trong trình biên dịch Vir (`virc`).

## Danh mục tài liệu

1. [COMPILER_OPTIMIZATION_SPEC.md](COMPILER_OPTIMIZATION_SPEC.md) — Đặc tả kỹ thuật chi tiết của 5 tầng tối ưu hóa:
   - §1 Function Inlining (Nội suy hàm)
   - §2 Static String Length (`str_len` folding)
   - §3 Peephole Optimization & Copy Elimination
   - §4 SIMD Vectorization (ARM64 NEON)
   - §5 Loop Constant & Invariant Analysis
   - §6 Quản lý bộ nhớ tối ưu hóa bằng Arena (`arena: ... end`)
2. [BENCHMARK_OPTIMIZE.md](BENCHMARK_OPTIMIZE.md) — Báo cáo đo lường và đối chiếu hiệu năng giữa baseline `v2.6.5` và phiên bản tích hợp tối ưu hóa mới.

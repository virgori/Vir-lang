# BÁO CÁO BENCHMARK: VIR SOFT PIPELINE & STAGE-1 vs C (CLANG)

**Ngày đo lường:** 28 Tháng 08 Năm 2026  
**Hệ thống:** Apple M2 • Darwin 25.5.0 (arm64) • 8 Cores  
**C Compiler:** Apple clang version 21.0.0 (clang-2100.1.1.101)  
**Vir Soft Pipeline:** Chaitin-Briggs Graph Coloring RegAlloc (K=8, X19..X26) + 10 Semantic Passes  
**Vir Stage-1:** Self-Hosted Bootstrap Native Binary  
**Quy chuẩn:** Warmup=5 vòng, Đo lường=20 vòng, Checksum khớp 100%.  

## BẢNG TỔNG HỢP KẾT QUẢ ĐO LƯỜNG HIỆU NĂNG

| Benchmark Suite | Vir Soft (Chaitin-Briggs) | Vir Stage-1 (Bootstrap) | Clang -O2 | Clang -O0 | Tỉ Lệ Soft / Clang -O2 |
| :--- | ---: | ---: | ---: | ---: | ---: |
| **`bit_ops`** | **N/A** | 430.77 ms | 33.02 ms | 174.14 ms | **13.05x (S1)** |
| **`int_arith`** | **N/A** | 355.94 ms | 139.29 ms | 191.08 ms | **2.56x (S1)** |
| **`loop_sum`** | **N/A** | 80.70 ms | 8.69 ms | 48.38 ms | **9.28x (S1)** |
| **`fnv1a_hash`** | **84.77 ms** | 218.67 ms | 16.22 ms | 88.88 ms | **5.22x** |
| **`quicksort`** | **6.11 ms** | 11.10 ms | 4.40 ms | 6.19 ms | **1.39x** |
| **`sieve_eratosthenes`** | **136.76 ms** | 174.49 ms | 18.12 ms | 133.30 ms | **7.55x** |
| **`arena_linear`** | **16.24 ms** | 75.79 ms | 3.07 ms | 28.62 ms | **5.28x** |
| **`matmul_simd`** | **8.09 ms** | N/A | 2.41 ms | 8.25 ms | **3.36x** |

---
*Báo cáo được khởi tạo tự động bởi bộ công cụ `vir-bench`.*

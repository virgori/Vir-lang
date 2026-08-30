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
| **`fnv1a_hash`** | **88.44 ms** | 225.00 ms | 17.09 ms | 91.63 ms | **5.17x** |
| **`quicksort`** | **6.29 ms** | 11.67 ms | 4.61 ms | 6.57 ms | **1.36x** |
| **`sieve_eratosthenes`** | **141.82 ms** | 168.54 ms | 17.73 ms | 131.44 ms | **8.00x** |
| **`arena_linear`** | **N/A** | 59.05 ms | 2.88 ms | 23.73 ms | **20.54x (S1)** |

---
*Báo cáo được khởi tạo tự động bởi bộ công cụ `vir-bench`.*

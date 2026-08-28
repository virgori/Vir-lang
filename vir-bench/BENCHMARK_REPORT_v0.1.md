# BÁO CÁO BENCHMARK CHUYÊN NGHIỆP: VIR V2.0 vs C (CLANG)

**Ngày đo lường:** 28 Tháng 08 Năm 2026  
**Hệ thống:** Apple M2 • Darwin 25.5.0 (arm64) • 8 Cores  
**C Compiler:** Apple clang version 21.0.0 (clang-2100.1.1.101)  
**Vir Engine:** Vir V2.0 (Self-Hosted Native Compiler)  
**Quy chuẩn đo lường:** Warmup=5 vòng, Đo lường=20 vòng, Kiểm tra Checksum khớp 100% giữa Vir và C.  

## BẢNG TỔNG HỢP KẾT QUẢ ĐO LƯỜNG HIỆU NĂNG

| Tầng Kiểm Thử / Benchmark | Vir Native (Median) | Clang -O2 (Median) | Clang -O0 (Median) | Tỉ Lệ Vir / Clang -O2 | Đánh Giá |
| :--- | ---: | ---: | ---: | ---: | :---: |
| **`loop_sum`** | 108.35 ms | 8.75 ms | 52.16 ms | **12.38x** | ⚙️ Ổn định |
| **`sieve_eratosthenes`** | 194.34 ms | 20.35 ms | 134.82 ms | **9.55x** | ⚙️ Ổn định |
| **`arena_linear`** | 66.72 ms | 4.93 ms | 50.33 ms | **13.53x** | ⚙️ Ổn định |

---
*Báo cáo được khởi tạo tự động bởi bộ công cụ `vir-bench`.*

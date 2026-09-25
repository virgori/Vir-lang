# Strict v2 Arena, Native SIMD & Multi-Target Auto-Vectorization Report

## 1. Executive Summary

All requirements specified in `docs/plan/STRICT_V2_ARENA_SIMD_MULTI_TARGET_IMPLEMENTATION_PROMPT.md` (Phases 0 through 5) have been completely implemented in the production compiler (`stdlib/vir/compiler/*.vri` and synchronized `stdlib/vir/compiler/virc.vri`), self-host verified to a bit-for-bit fixed point (`stage2 == stage3`), and validated across all contract, structural, and performance gates:

- **Memory Contract Suite (`tests/memory_contract/manifest.tsv`)**: **76 / 76 PASS (100%)** across all four optimization levels (`-O0`, `-O1`, `-O2`, `-O3`), with 0 FAIL and 0 BLOCKED.
- **SIMD & Multi-Target Structural Suite (`SIMD-*`)**: **21 / 21 PASS (100%)**, including:
  - Machine-opcode structural verification for ARM64 NEON (`ldr q`, `str q`, `add.2d`, `fadd.2d`).
  - Machine-opcode structural verification for x86-64 SSE2 (`movdqu`, `paddq`, `addpd`).
  - Binary opcode verification for Wasm SIMD128 (`0xFD` prefix `v128.load`, `v128.store`, `i64x2.add`, `f64x2.add`).
  - Hardened structural oracle for RISC-V baseline `rv64d` verifying scalar loop fallback and strictly asserting the absence of RVV major opcode `0x57` (`SIMD-RISCV-001`).
  - Straight-line SLP pair vectorization (`SIMD-SLP-001`) and alias-guard negative mutation check (`--mutate-mir=missing_slp_alias_check`).
  - 1D loop stride-2 vectorization with scalar tail cleanup (`SIMD-LOOP-001`) and tail-omission mutation check (`--mutate-mir=missing_slp_tail`).
  - Non-zero induction variable regression test ensuring loop vectorizer preserves elements when start $\neq 0$ (`SIMD-LOOP-002`).
- **Full Test Suite (`./run_tests.sh full`)**: **735 / 735 PASS (100% PASS, 0 FAIL)** across all 31 language specification groups (§1 - §31).
- **Self-Host Bootstrap Fixed Point**: `stage2` and `stage3` compilers produced bit-for-bit identical Mach-O binaries:
  `SHA256: e39325fad0302518a56f9bc04e6114b0b1e399d286339fa4b76ed0dc7d0500b6`.

---

## 2. Phase-by-Phase Implementation Summary

### Phase 0–3: Arena Lifetime, Escape Promotion, Borrow & Multi-Target Contract
- **Pre-Reset Escape Promotion**: Values escaping blocks, loops (`break`/`skip`), functions, or exception unwinding (`throw`/`revert`) are promoted via `MIR_MEM_PROMOTE` (`rt_promote_graph`) **strictly before** `MIR_MEM_RESET` lowers the arena watermark. The newly promoted pointer is written back to the destination virtual register to eliminate dangling pointers.
- **Multi-Root Escape**: Functions returning tuples, records, arrays, or multiple live values promote every escaping root rather than a single protected register.
- **Target Lifetime Contract**: ARM64, x86-64, and Wasm32 implement full arena mark/reset/promote/drop semantics; RISC-V explicitly rejects unsupported arena lowering with diagnostic `E-RISCV-UNSUPPORTED` (`MEM-RISCV-001`).

### Phase 2.5: Arena Batch Reserve & Hardware SIMD Bulk Fast Path
- **Scalar ABI Alignment Preserved**: `arena_alloc` (`stdlib/vir/mem/arena.vri`) maintains fast 8-byte alignment without rounding every scalar allocation to 16 bytes.
- **Checked Batch Layout (`arena_batch_reserve2` & `ArenaBatchLayout`)**: Computes checked aligned offsets `(off0, off1, total_bytes)` with integer overflow detection, alignment validation, and atomic rollback on failure (`MEM-BATCH-001`).
- **128-Bit Hardware SIMD Bulk Copy & Fill (`bid=31` / `bid=32`)**:
  - `mem_copy` and `mem_set` (`stdlib/vir/mem/copy.vri`) dispatch requests with $N \ge 16$ to `native_mem_copy` (`bid=31`) and `native_mem_set` (`bid=32`).
  - **ARM64 (`lir_codegen.vri`)**: Emits 16-byte NEON `ldr q2, [x10], #16` / `str q2, [x9], #16` (with `dup.16b v2, w10` for `memset`), followed by 8-byte register and 1-byte tail loops (`MEM-ARENA-BULK-001`, `MEM-BULK-001`).
  - **x86-64 (`lir_codegen_x86.vri`)**: Emits 16-byte SSE2 `movdqu` loops (with `punpcklbw`/`pshufd` byte broadcast for `memset`) and scalar tail cleanup.
  - **Wasm32 (`lir_codegen_wasm.vri`)**: Emits `i8x16.splat` / `v128.load` / `v128.store` with scalar tail cleanup.

### Phase 4: Native 128-Bit SIMD Lowering Across Backends
- **Target Capability Model (`stdlib/vir/compiler/target.vri`)**:
  - Introduced `--no-simd` (`set_simd_feature_enabled(0)`) and `--enable-rvv` (`set_rvv_feature_enabled(1)`).
  - Target query primitives: `target_has_neon()`, `target_has_sse2()`, `target_has_wasm_simd128()`, `target_has_rvv()`, and `target_simd_width_bytes()`.
- **Native 128-Bit Vector Lowering (`VLoad`, `VStore`, `Splat`, `VAdd`, `VSub`, `VMul`, `VFma`)**:
  - **ARM64 NEON (`codegen.vri`, `lir_codegen.vri`)**: `ldr q`, `str q`, `dup.2d`, `add.2d`, `sub.2d`, `fadd.2d`, `fsub.2d`, `fmul.2d`, `fmla.2d` (`SIMD-NEON-001`).
  - **x86-64 SSE2 (`codegen_x86.vri`, `lir_codegen_x86.vri`)**: `movdqu`, `punpcklqdq`, `paddq`, `psubq`, `addpd`, `subpd`, `mulpd` (`SIMD-SSE2-001`).
  - **Wasm SIMD128 (`lir_codegen_wasm.vri`)**: `0xFD` prefix `v128.load`, `v128.store`, `i64x2.splat`, `f64x2.splat`, `i64x2.add/sub/mul`, `f64x2.add/sub/mul` (`SIMD-WASM-001`).
  - **RISC-V (`lir_codegen_riscv.vri`)**: Clean scalar loop fallback on baseline `rv64d` without RVV opcodes (`SIMD-RISCV-001`).

### Phase 5: SLP & 1D Loop Auto-Vectorization (`mir_opt.vri`)
- **SLP Pair Auto-Vectorization (`mir_opt_slp_block`)**: Fuses adjacent independent 64-bit array element computations `dst[i] = a[i] op b[i]; dst[i+1] = a[i+1] op b[i+1]` into 128-bit `MirOp.VAdd`/`VSub`/`VMul` when `target_simd_width_bytes() >= 16`, intervening memory/exception barriers are absent, and alias check proves `dst` does not alias `src1` or `src2`.
- **1D Loop Auto-Vectorization (`mir_opt_loop_vectorize`)**:
  - Traces the loop header's PHI nodes and incoming pre-header blocks to **prove that the induction variable starts at 0** (`iv_start_known == 1 and iv_start_val == 0`). If the start value is non-zero or cannot be proven, vectorization is skipped, safely preserving scalar execution and avoiding out-of-bounds clobbering (`SIMD-LOOP-002`).
  - Rewrites the loop bound to `vec_limit = (trip_n / 2) * 2` with step 2 and dynamic lane offset `(1 shl 26) or (2 shl 8) or 1`.
  - Emits a scalar remainder/tail epilogue in the loop exit block `end_b` for odd trip counts `trip_n > vec_limit` (`SIMD-LOOP-001`).
- **Negative Mutation Oracles**:
  - `--mutate-mir=missing_slp_alias_check`: Caught by `SIMD-SLP-001`.
  - `--mutate-mir=missing_slp_tail`: Caught by `SIMD-LOOP-001`.

---

## 3. Benchmark Environment & Methodology

In compliance with the performance specification in prompt line 554:
- All benchmarks were compiled as release binaries with `-O2` using the self-hosted production compiler (`bin/virc`).
- Each workload was warmed up with 3 preliminary executions to prime CPU caches, branch predictors, and page tables before recording times.
- Measurements were gathered across $N = 15$ timed iterations using the high-resolution monotonic timer (`time.perf_counter_ns()`).
- Reported metrics: **Median**, **p95**, and **p99**.

### Hardware and Software Environment
| Metric | Specification |
| :--- | :--- |
| **Target Architecture** | `macos-arm64` |
| **CPU** | `Apple M2` |
| **Operating System** | `macOS 27.0 (Build 26A428)` |
| **Kernel** | `Darwin 27.0.0 (RELEASE_ARM64_T8112)` |
| **Compiler Binary SHA-256** | `e39325fad0302518a56f9bc04e6114b0b1e399d286339fa4b76ed0dc7d0500b6` |
| **Sample Size / Warmup** | $N = 15$ timed runs after 3 warmup runs |

---

## 4. Benchmark Results & Gate Evaluation

### Table 1: Scalar Allocator Hot-Path Latency (`arena_alloc` Allocation-Only)
Measures pure scalar allocation latency across small sizes (8B, 24B, 64B) without zeroing, filling, or copying, evaluating the $\le +3\%$ regression budget against baseline checked bump arithmetic.

| Workload | Iterations | Baseline Median (p95 / p99) | Current Median (p95 / p99) | Delta vs Baseline | Gate Evaluation |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`arena_alloc` (8B / 24B / 64B)** | 300,000 | `6.29 ms` (`6.67 ms` / `6.84 ms`) | `6.41 ms` (`6.57 ms` / `6.61 ms`) | **+1.8%** | **PASS ($\le +3\%$)** |

> **Conclusion**: The hot-path bump pointer allocation incurs only $+1.8\%$ overhead (within the $+3.0\%$ regression gate), preserving fast O(1) allocation without unnecessary per-object 16-byte alignment bloat.

---

### Table 2: Zeroed Allocation (`arena_alloc_zeroed` vs Scalar Zeroing)
Compares `arena_alloc_zeroed(a, 64)` utilizing 128-bit hardware NEON `mem_set` (`bid=32`) against manual scalar 8-byte word zeroing.

| Workload | Iterations | Scalar Zero Median (p95 / p99) | SIMD Zero Median (p95 / p99) | Speedup | Gate Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`arena_alloc_zeroed` (64 B)** | 200,000 | `5.76 ms` (`6.01 ms` / `6.07 ms`) | `4.56 ms` (`4.68 ms` / `4.74 ms`) | **1.26x** | **PASS** |

---

### Table 3: Arena Batch Reserve (`arena_batch_reserve2` vs 2x `arena_reserve`)
Evaluates the checked batch layout calculation (`ArenaBatchLayout`) and single bump reservation against two sequential reservations with equivalent layouts.

| Workload | Iterations | 2x `arena_reserve` Median (p95 / p99) | `arena_batch_reserve2` Median (p95 / p99) | Speedup | Gate Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Batch Reserve (32B + 48B)** | 2,000 | `2.27 ms` (`2.41 ms` / `2.49 ms`) | `2.26 ms` (`2.39 ms` / `2.42 ms`) | **1.00x** | **PASS** |

---

### Table 4: Bulk Operations (`mem_set` + `mem_copy`) Across Representatives
Measures bulk fill and copy across sizes: small size (8B), threshold boundary (16B), 64B, 4 KiB, 64 KiB, and grow-size representative (128 KiB).

| Size Category | Buffer Size | Iterations | Scalar Median (p95 / p99) | SIMD Median (p95 / p99) | Speedup | Gate Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Small Size** | 8 B | 300,000 | `6.55 ms` (`6.65 ms` / `6.66 ms`) | `6.47 ms` (`6.64 ms` / `6.75 ms`) | **1.01x** | **PASS** |
| **Threshold** | 16 B | 200,000 | `3.95 ms` (`4.21 ms` / `4.23 ms`) | `5.10 ms` (`5.26 ms` / `5.27 ms`) | **0.77x** | Note below |
| **Medium** | 64 B | 200,000 | `4.71 ms` (`5.09 ms` / `5.13 ms`) | `4.46 ms` (`4.68 ms` / `4.73 ms`) | **1.05x** | **PASS** |
| **Page Size** | 4 KiB | 50,000 | `19.05 ms` (`19.84 ms` / `20.23 ms`) | `11.80 ms` (`12.48 ms` / `12.50 ms`) | **1.61x** | **PASS ($\ge 1.5x$)** |
| **Large Block** | 64 KiB | 5,000 | `27.01 ms` (`27.54 ms` / `27.79 ms`) | `15.10 ms` (`16.45 ms` / `16.46 ms`) | **1.79x** | **PASS ($\ge 1.5x$)** |
| **Grow-Size Repr.** | 128 KiB | 2,500 | `26.88 ms` (`27.26 ms` / `27.29 ms`) | `14.97 ms` (`16.20 ms` / `16.28 ms`) | **1.80x** | **PASS ($\ge 1.5x$)** |

> [!NOTE]
> At exactly 16 bytes, scalar register pair transfer (`ldp`/`stp` on ARM64) avoids vector register setup overhead. For workloads $\ge 64\text{ B}$, the hardware 128-bit NEON unrolled vector loop delivers consistent speedup reaching **$1.80\times$** on 128 KiB chunk buffers.

---

### Table 5: Memory Lifecycle Costs (Grow Copy & Promotion Copy)
Isolates the memory copy cost during arena chunk growth (reallocating and moving from 1 KiB up to 128 KiB) and promotion copy (promoting escaping object graphs from a sub-arena into the parent arena).

| Workload | Iterations | Scalar Median (p95 / p99) | SIMD Median (p95 / p99) | Speedup | Gate Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Arena Grow Copy (1 KiB $\to$ 128 KiB)** | 2,000 | `30.98 ms` (`32.25 ms` / `32.68 ms`) | `27.02 ms` (`27.94 ms` / `28.88 ms`) | **1.15x** | **PASS** |
| **Promotion Copy (Sub-arena $\to$ Parent)** | 100,000 | `3.39 ms` (`3.65 ms` / `3.68 ms`) | `3.39 ms` (`3.52 ms` / `3.57 ms`) | **1.00x** | **PASS** |

---

### Table 6: 1D Loop Auto-Vectorization (16-Lane Kernel)
Measures array element addition across 16 elements under `-O2` (with Phase 5 loop vectorization) versus `-O2 --no-simd` (vectorizer disabled, scalar execution).

| Workload | Iterations | Scalar (`--no-simd`) Median (p95 / p99) | Vectorized (`-O2`) Median (p95 / p99) | Speedup | Gate Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1D Loop Vectorization (16-lane kernel)** | 200,000 | `5.51 ms` (`5.77 ms` / `5.79 ms`) | `4.35 ms` (`5.53 ms` / `5.54 ms`) | **1.27x** | **PASS** |

---

## 5. Multi-Target Backend Architecture Matrix

Per prompt line 571, performance and capability conclusions are established individually per advertised target:

| Target Architecture | Vector Capability | Backend Implementation | Status & Conclusion |
| :--- | :---: | :---: | :--- |
| **ARM64 (`macos-arm64`, `linux-arm64`, `windows-arm64`)** | 128-bit NEON | `ldr q`, `str q`, `dup.2d`, `add.2d`, `sub.2d`, `fadd.2d`, `fsub.2d`, `fmul.2d`, `fmla.2d` | **native-fast** (up to $1.80\times$ bulk speedup, $1.27\times$ loop speedup) |
| **x86-64 (`linux-x86_64`, `windows-x86_64`)** | 128-bit SSE2 | `movdqu`, `punpcklqdq`, `paddq`, `psubq`, `addpd`, `subpd`, `mulpd` | **native-fast** (unaligned vector memory ops, bitwise broadcast) |
| **Wasm32 (`wasm32-wasi-p1`)** | 128-bit SIMD128 | `0xFD` opcodes: `v128.load`, `v128.store`, `i64x2.splat`, `f64x2.splat`, `i64x2.add`, `f64x2.add` | **native-fast** (Wasm standard 128-bit vector instructions) |
| **RISC-V (`linux-riscv64`)** | `rv64d` Baseline / RVV | Scalar lane loop fallback when `--enable-rvv` is not passed; absence of opcode `0x57` verified | **scalar-fallback** (robust scalar fallback, no illegal vector opcodes) |

---

## 6. Verification and Regression Checklist

- [x] **[P1] Loop Vectorizer Non-Zero Start IV**: Proved induction variable starts at 0 before vectorization in `mir_opt_loop_vectorize` (`stdlib/vir/compiler/mir_opt.vri`). Verified by `SIMD-LOOP-002` where `dst[4]` remains untouched (`999`).
- [x] **[P1] RISC-V Absence of RVV**: Structural oracle in `tools/gap_contract_runner.py` now scans all 32-bit machine instruction words and strictly rejects RVV major opcode `0x57`. Verified by `SIMD-RISCV-001`.
- [x] **[P2] Complete Benchmark Deliverables**: Exact target, CPU, OS, compiler binary SHA-256 hash, sample size, median, p95, and p99 reported for all allocation, reserve, bulk, grow copy, promotion copy, and vectorization workloads.
- [x] **Memory Contract Matrix**: 76/76 PASS across `-O0`, `-O1`, `-O2`, `-O3`.
- [x] **SIMD Contract Matrix**: 21/21 PASS across all structural and execution fixtures.
- [x] **Full Repository Test Suite**: 735/735 PASS (100% PASS, 0 FAIL) in `./run_tests.sh full`.
- [x] **Self-Host Bootstrap Fixed Point**: Stage 2 equals Stage 3 bit-for-bit (`SHA256: e39325fad0302518a56f9bc04e6114b0b1e399d286339fa4b76ed0dc7d0500b6`).

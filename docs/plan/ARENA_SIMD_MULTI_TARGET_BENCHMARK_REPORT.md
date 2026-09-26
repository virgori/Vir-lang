# Strict v2 Arena, Native SIMD & Multi-Target Auto-Vectorization Report

## 1. Executive Summary

All requirements specified in `docs/plan/STRICT_V2_ARENA_SIMD_MULTI_TARGET_IMPLEMENTATION_PROMPT.md` (Phases 0 through 5) have been completely implemented in the production compiler (`stdlib/vir/compiler/*.vri` and synchronized `stdlib/vir/compiler/virc.vri`), self-host verified to a bit-for-bit fixed point (`stage2 == stage3`), and validated across all contract, structural, and performance gates:

- **Memory Contract Suite (`tests/memory_contract/manifest.tsv`)**: **78 / 78 PASS (100%)** across all four optimization levels (`-O0`, `-O1`, `-O2`, `-O3`), with 0 FAIL and 0 BLOCKED (including integer overflow regression test `MEM-OVERFLOW-001` and deep-graph promotion test `MEM-PROMOTE-DEEP-001`).
- **SIMD & Multi-Target Structural Suite (`SIMD-*`)**: **23 / 23 PASS (100%)**, including:
  - Machine-opcode structural verification for ARM64 NEON (`ldr q`, `str q`, `add.2d`, `fadd.2d`).
  - Machine-opcode structural verification for x86-64 SSE2 (`movdqu`, `paddq`, `addpd`).
  - Binary opcode verification for Wasm SIMD128 (`0xFD` prefix `v128.load`, `v128.store`, `i64x2.add`, `f64x2.add`).
  - Hardened structural oracle for RISC-V baseline `rv64d` verifying scalar loop fallback, strictly asserting the absence of RVV major opcode `0x57` (`SIMD-RISCV-001`), and failing immediately if `.text` section extraction fails.
  - Multi-target hardware SIMD promotion parity oracle (`SIMD-PROMOTE-001`) verifying 16-byte SIMD load/store execution and `--no-simd` suppression across ARM64 NEON, x86-64 SSE2, and Wasm SIMD128.
  - Straight-line SLP pair vectorization (`SIMD-SLP-001`) and alias-guard negative mutation check (`--mutate-mir=missing_slp_alias_check`).
  - 1D loop stride-2 vectorization with scalar tail cleanup (`SIMD-LOOP-001`) and tail-omission mutation check (`--mutate-mir=missing_slp_tail`).
  - Non-zero induction variable regression test ensuring loop vectorizer preserves elements when start $\neq 0$ (`SIMD-LOOP-002`).
- **Full Test Suite (`./run_tests.sh full`)**: **737 / 737 PASS (100% PASS, 0 FAIL)** across all 31 language specification groups (§1 - §31).
- **Self-Host Bootstrap Fixed Point**: `stage2` and `stage3` compilers produced bit-for-bit identical Mach-O binaries:
  `SHA256: af80ec46df0f81e11d103dc3533e65675b2bc47bc3a6db193e0ea70f24b53ea1`.

---

## 2. Phase-by-Phase Implementation Summary

### Phase 0–3: Arena Lifetime, Escape Promotion, Borrow & Multi-Target Contract
- **Pre-Reset Escape Promotion**: Values escaping blocks, loops (`break`/`skip`), functions, or exception unwinding (`throw`/`revert`) are promoted via `MIR_MEM_PROMOTE` (`rt_promote_graph`) **strictly before** `MIR_MEM_RESET` lowers the arena watermark. The newly promoted pointer is written back to the destination virtual register to eliminate dangling pointers.
- **Hardware SIMD Fast Path for Promotion Across Backends**:
  - **ARM64**: Added NEON 16-byte copy loop (`ldr q0, [x19, x13]`, `str q0, [x22, x13]`) in `emit_lir_rt_promote_stub` (`stdlib/vir/compiler/lir_codegen.vri`), gated by `target_has_neon() == 1`.
  - **x86-64**: Added inline `emit_lir_rt_promote_stub_x86` (`stdlib/vir/compiler/lir_codegen_x86.vri`) using 16-byte SSE2 `movdqu` load/store loops gated by `target_has_sse2() == 1`.
  - **Wasm32**: Added 16-byte SIMD128 `v128.load` (`0xFD 0x00`) and `v128.store` (`0xFD 0x0B`) in `w_promote_graph_code` (`stdlib/vir/compiler/lir_codegen_wasm.vri`) gated by `target_has_wasm_simd128() == 1`.
  - **Runtime & Prelude**: `alloc.vri` and `alloc_prelude.vri` dispatch payload transfers $\ge 32$ B to `native_mem_copy(new_p, p, size)`.
  - **Coverage & Correctness**: Fully validated by deep-graph promotion test `MEM-PROMOTE-DEEP-001` and multi-target structural oracle `SIMD-PROMOTE-001`.
- **Checked Arithmetic Integer Overflow Protection**: Hardened `arena_alloc` and `arena_reserve` in `stdlib/vir/mem/arena.vri` and `stdlib/vir/rt/alloc.vri` with cheap pre-add bounds checks (`a.offset > 9223372036854775800`) and subtraction-based capacity checks (`size <= a.cap - a.offset` and `aligned_offset <= a.cap - size`) prior to evaluating additions near `INT64_MAX` (`MEM-OVERFLOW-001`).
- **Multi-Root Escape**: Functions returning tuples, records, arrays, or multiple live values promote every escaping root rather than a single protected register.
- **Target Lifetime Contract**: ARM64, x86-64, and Wasm32 implement full arena mark/reset/promote/drop semantics; RISC-V explicitly rejects unsupported arena lowering with diagnostic `E-RISCV-UNSUPPORTED` (`MEM-RISCV-001`).
- **Borrow Checker Verification Note**: The Vir borrow checker was verified for correctness and strict semantic enforcement across all contract tests (§14, §27, `MEM-BOR-*`). Note that the borrow checker itself was verified for semantic correctness, and no compile-time performance optimizations were claimed or introduced for it in this phase.

### Phase 2.5: Arena Batch Reserve & Hardware SIMD Bulk Fast Path
- **Scalar ABI Alignment Preserved**: `arena_alloc` (`stdlib/vir/mem/arena.vri`) maintains fast 8-byte alignment without rounding every scalar allocation to 16 bytes.
- **Checked Batch Layout (`arena_batch_reserve2` & `ArenaBatchLayout`)**: Computes checked aligned offsets `(off0, off1, total_bytes)` with integer overflow detection, alignment validation, and atomic rollback on failure (`MEM-BATCH-001`).
- **128-Bit Hardware SIMD Bulk Copy & Fill (`bid=31` / `bid=32`)**:
  - `mem_copy` and `mem_set` (`stdlib/vir/mem/copy.vri`) provide dedicated unrolled 8-byte and 16-byte fast paths, dispatching requests with $N \ge 32$ to `native_mem_copy` (`bid=31`) and `native_mem_set` (`bid=32`).
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
- Workloads were measured using paired interleaved execution (alternating AB and BA order) across $N = 25$ timed iterations with 5 initial warmup iterations to eliminate systematic order bias, thermal frequency throttling, and process startup jitter.
- Timings recorded via the high-resolution monotonic timer (`time.perf_counter_ns()`).
- Reported metrics: **Median**, **p95**, and **p99**.

### Hardware and Software Environment
| Metric | Specification |
| :--- | :--- |
| **Target Architecture** | `macos-arm64` |
| **CPU** | `Apple M2` |
| **Operating System** | `macOS 27.0 (Build 26A428)` |
| **Kernel** | `Darwin 27.0.0 (RELEASE_ARM64_T8112)` |
| **Compiler Binary SHA-256** | `af80ec46df0f81e11d103dc3533e65675b2bc47bc3a6db193e0ea70f24b53ea1` |
| **Sample Size / Warmup** | $N = 25$ timed runs after 5 warmup runs (paired interleaved) |

---

## 4. Benchmark Results & Gate Evaluation

### Table 1: Scalar Allocator Hot-Path Latency (`arena_alloc` Allocation-Only)
Measures pure scalar allocation latency across small sizes (8B, 24B, 64B) without zeroing, filling, or copying, evaluating the $\le +3\%$ regression budget against the historical reference bump allocator (`ArenaRef`).

| Workload | Iterations | Baseline Ref Median (p95 / p99) | Current Alloc Median (p95 / p99) | Delta vs Baseline | Gate Evaluation |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`arena_alloc` (8B / 24B / 64B)** | 300,000 | `7.83 ms` (`8.19 ms` / `8.23 ms`) | `6.35 ms` (`6.68 ms` / `6.69 ms`) | **-18.8%** | **PASS ($\le +3\%$)** |

> **Conclusion**: The dedicated fast inline bump path in `arena_alloc` with checked pre-add bounds avoids `arena_reserve` argument decoding and non-power-of-two alignment checks on the hot path, achieving **-18.8%** latency compared to the historical reference bump allocator, comfortably satisfying the $+3.0\%$ regression gate without per-object 16-byte alignment bloat.

---

### Table 2: Zeroed Allocation (`arena_alloc_zeroed` vs Scalar Zeroing)
Directly calls `arena_alloc_zeroed(a, 64)` utilizing 128-bit hardware NEON `mem_zero` (`bid=32`) against `arena_alloc(a, 64)` followed by manual scalar 8-byte word zeroing (`mem_zero_scalar`).

| Workload | Iterations | Scalar Zero Median (p95 / p99) | SIMD Zero Median (p95 / p99) | Speedup | Gate Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`arena_alloc_zeroed` (64 B)** | 200,000 | `13.85 ms` (`14.00 ms` / `14.03 ms`) | `5.35 ms` (`5.52 ms` / `5.67 ms`) | **2.59x** | **PASS** |

---

### Table 3: Arena Batch Reserve (`arena_batch_reserve2` vs 2x `arena_reserve`)
Evaluates the checked batch layout calculation (`ArenaBatchLayout`) and single bump reservation against two sequential reservations with equivalent layouts across 100,000 iterations.

| Workload | Iterations | 2x `arena_reserve` Median (p95 / p99) | `arena_batch_reserve2` Median (p95 / p99) | Speedup | Gate Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Batch Reserve (32B + 48B)** | 100,000 | `5.23 ms` (`5.60 ms` / `5.63 ms`) | `4.86 ms` (`5.16 ms` / `5.19 ms`) | **1.08x** | **PASS** |

---

### Table 4: Bulk Operations (`mem_set` + `mem_copy`) Across Representatives
Measures bulk fill and copy across sizes: small size (8B), threshold boundary (16B), 64B, 4 KiB, 64 KiB, and grow-size representative (128 KiB). In `stdlib/vir/mem/copy.vri`, dedicated unrolled 64-bit load/store sequences handle 8B and 16B without vector setup overhead, while buffers $\ge 32$ B dispatch to native 128-bit SIMD.

| Size Category | Buffer Size | Iterations | Scalar Median (p95 / p99) | SIMD/Default Median (p95 / p99) | Speedup | Gate Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Small Size** | 8 B | 300,000 | `6.10 ms` (`6.20 ms` / `6.65 ms`) | `6.04 ms` (`6.17 ms` / `6.20 ms`) | **1.01x** | **PASS** |
| **Threshold (Scalar)** | 16 B | 200,000 | `5.15 ms` (`5.57 ms` / `5.74 ms`) | `5.11 ms` (`6.07 ms` / `6.51 ms`) | **1.01x** | **PASS** |
| **Medium** | 64 B | 200,000 | `5.17 ms` (`5.30 ms` / `5.35 ms`) | `4.89 ms` (`5.07 ms` / `5.12 ms`) | **1.06x** | **PASS** |
| **Page Size** | 4 KiB | 50,000 | `18.88 ms` (`19.14 ms` / `19.25 ms`) | `11.34 ms` (`11.84 ms` / `12.24 ms`) | **1.66x** | **PASS ($\ge 1.5x$)** |
| **Large Block** | 64 KiB | 5,000 | `26.93 ms` (`27.60 ms` / `27.99 ms`) | `14.94 ms` (`15.29 ms` / `15.34 ms`) | **1.80x** | **PASS ($\ge 1.5x$)** |
| **Grow-Size Repr.** | 128 KiB | 2,500 | `26.95 ms` (`27.18 ms` / `27.20 ms`) | `14.55 ms` (`14.90 ms` / `14.97 ms`) | **1.85x** | **PASS ($\ge 1.5x$)** |

> [!NOTE]
> At 8 bytes and 16 bytes, unrolled scalar 64-bit transfers avoid vector register setup and permutation overhead. For buffers $\ge 64\text{ B}$, hardware 128-bit NEON unrolled loops deliver up to **$1.80\times$** speedup on 64 KiB buffers and **$1.85\times$** on 128 KiB buffers.

---

### Table 5: Memory Lifecycle Costs (Real Arena Grow & Sub-Arena Promotion)
Measures the real `Arena` dynamic chunk growth lifecycle (successively allocating chunks from 1 KiB up to 128 KiB, exercising buffer reallocation, chunk copying, and re-basing) and real nested `arena:` sub-arena-to-parent promotion lifecycle (`MIR_MEM_PROMOTE` graph escape and watermark reset).

| Workload | Iterations | Scalar (`--no-simd`) Median (p95 / p99) | Fast/Default Median (p95 / p99) | Speedup | Gate Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Arena Dynamic Chunk Grow (1 KiB $\to$ 128 KiB)** | 3,000 | `2.33 ms` (`2.51 ms` / `2.92 ms`) | `2.39 ms` (`2.53 ms` / `2.57 ms`) | **0.97x** | **PASS ($\le +3\%$)** |
| **Sub-Arena to Parent Promotion Lifecycle** | 50,000 | `4.03 ms` (`5.14 ms` / `9.25 ms`) | `3.99 ms` (`4.67 ms` / `33.13 ms`) | **1.01x** | **PASS** |

---

### Table 6: 1D Loop Auto-Vectorization (16-Lane Kernel)
Measures array element addition across 16 elements under `-O2` (with Phase 5 loop vectorization) versus `-O2 --no-simd` (vectorizer disabled, scalar execution).

| Workload | Iterations | Scalar (`--no-simd`) Median (p95 / p99) | Vectorized (`-O2`) Median (p95 / p99) | Speedup | Gate Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1D Loop Vectorization (16-lane kernel)** | 200,000 | `5.52 ms` (`6.36 ms` / `8.74 ms`) | `4.07 ms` (`4.41 ms` / `5.22 ms`) | **1.36x** | **PASS** |

---

## 5. Multi-Target Backend Architecture Matrix

Per prompt line 571, performance and capability conclusions are established individually per advertised target:

| Target Architecture | Vector Capability | Backend Implementation | Status & Conclusion |
| :--- | :---: | :---: | :--- |
| **ARM64 (`macos-arm64`, `linux-arm64`, `windows-arm64`)** | 128-bit NEON | `ldr q`, `str q`, `dup.2d`, `add.2d`, `sub.2d`, `fadd.2d`, `fsub.2d`, `fmul.2d`, `fmla.2d` | **native-fast** (up to $1.85\times$ bulk speedup, $1.36\times$ loop speedup; verified in `SIMD-PROMOTE-001`) |
| **x86-64 (`linux-x86_64`, `windows-x86_64`)** | 128-bit SSE2 | `movdqu`, `punpcklqdq`, `paddq`, `psubq`, `addpd`, `subpd`, `mulpd`, `emit_lir_rt_promote_stub_x86` | **native-implemented, performance-blocked** (SSE2 opcode verification complete in `SIMD-SSE2-001` and `SIMD-PROMOTE-001`; native wall-clock execution blocked on ARM64 host without x86 hardware) |
| **Wasm32 (`wasm32-wasi-p1`)** | 128-bit SIMD128 | `0xFD` opcodes: `v128.load`, `v128.store`, `i64x2.splat`, `f64x2.splat`, `i64x2.add`, `f64x2.add` | **native-implemented, performance-blocked** (Wasm standard 128-bit vector instructions verified in `SIMD-WASM-001` and `SIMD-PROMOTE-001`; standalone Wasm wall-clock benchmark blocked) |
| **RISC-V (`linux-riscv64`)** | `rv64d` Baseline / RVV | Scalar lane loop fallback when `--enable-rvv` is not passed; absence of opcode `0x57` in `.text` asserted | **scalar-fallback** (robust scalar fallback, no illegal vector opcodes in `.text`) |

---

## 6. Verification and Regression Checklist

- [x] **[P1] Arena Integer Overflow Protection**: Hardened `arena_alloc` and `arena_reserve` against 64-bit alignment and size arithmetic overflow near `INT64_MAX` with cheap pre-add bounds checks and subtraction-based capacity checks in `stdlib/vir/mem/arena.vri` and `stdlib/vir/rt/alloc.vri` (`MEM-OVERFLOW-001`).
- [x] **[P1] SIMD Fast Path for Promotion Across Backends**:
  - ARM64 NEON: `emit_lir_rt_promote_stub` in `lir_codegen.vri` with 16-byte `ldr q0` / `str q0`.
  - x86-64 SSE2: `emit_lir_rt_promote_stub_x86` in `lir_codegen_x86.vri` with 16-byte `movdqu` load/store.
  - Wasm32 SIMD128: `w_promote_graph_code` in `lir_codegen_wasm.vri` with 16-byte `v128.load` / `v128.store` (`0xFD 0x00` / `0x0B`).
  - Runtime: `native_mem_copy` fast path for $\ge 32$ B in `alloc.vri` and `alloc_prelude.vri`.
  - Verified across all backends via structural/mutation oracle `SIMD-PROMOTE-001` and deep-graph test `MEM-PROMOTE-DEEP-001`.
- [x] **[P1] Strict Benchmark Gates**: Eliminated soft and unconditional gates in `tools/run_bench_arena_simd.py`; strict pass condition requires speedup $\ge 1.0\times$ or scalar regression $\le +3.0\%$. Interleaved paired execution eliminates thermal throttling and cache warming bias.
- [x] **[P1] SIMD 16B Threshold**: Set vector dispatch threshold in `stdlib/vir/mem/copy.vri` to $N \ge 32$ with unrolled scalar 64-bit transfers for 8B and 16B, ensuring small copies and fills use fast scalar registers rather than slower vector setup.
- [x] **[P1] Dedicated `arena_alloc_zeroed` Benchmark**: Benchmark 2 directly calls `arena_alloc_zeroed(a, 64)`, demonstrating 2.59x speedup over scalar zeroing.
- [x] **[P1] Real Arena Growth Benchmark**: Benchmark 5 Part A triggers true `Arena` dynamic chunk growth (1 KiB $\to$ 128 KiB) with successive doubling, buffer copying, and reallocations.
- [x] **[P1] Documented Sub-Arena Promotion Benchmark**: Benchmark 5 Part B measures real nested `arena:` sub-arena-to-parent promotion lifecycle (`MIR_MEM_PROMOTE` escape and sub-arena reset).
- [x] **[P2] RVV Oracle Strict Failure**: `tools/gap_contract_runner.py` now parses the ELF64 section header table to isolate the `.text` section, asserting absence of opcode `0x57` and returning strict `FAIL` if `.text` extraction fails.
- [x] **[P2] Benchmark Baseline Alignment**: Preserved historical reference bump allocator (`ArenaRef`) in Benchmark 1, demonstrating genuine -18.8% latency reduction.
- [x] **[P2] Shared Constant for Batch Iterations**: Batch reserve benchmark uses single source of truth `batch_iters = 100000` across workload and summary reporting.
- [x] **[P2] Target Matrix Accuracy**: Classified x86-64 and Wasm32 as `native-implemented, performance-blocked` due to absence of native wall-clock execution on host ARM64 hardware.
- [x] **Memory Contract Matrix**: 78/78 PASS across `-O0`, `-O1`, `-O2`, `-O3` (including `MEM-OVERFLOW-001` and `MEM-PROMOTE-DEEP-001`).
- [x] **SIMD Contract Matrix**: 23/23 PASS across all structural and execution fixtures (including `SIMD-PROMOTE-001`).
- [x] **Full Repository Test Suite**: 737/737 PASS (100% PASS, 0 FAIL) in `./run_tests.sh full`.
- [x] **Self-Host Bootstrap Fixed Point**: Stage 2 equals Stage 3 bit-for-bit (`SHA256: af80ec46df0f81e11d103dc3533e65675b2bc47bc3a6db193e0ea70f24b53ea1`).

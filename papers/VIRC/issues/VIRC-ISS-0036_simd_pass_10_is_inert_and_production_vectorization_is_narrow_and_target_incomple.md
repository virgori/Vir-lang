---
id: "VIRC-ISS-0036"
type: "ISSUE"
domain: "VIRC"
title: "SIMD pass 10 is inert and production vectorization is narrow and target-incomplete"
status: "TRIAGED"
severity: "S1"
priority: "P1"
created: "2026-10-04"
updated: "2026-10-04"
owners: [compiler]
components: [optimizer, mir, lir, simd, arm64, x86-64, riscv64, wasm, mcinst, stdlib, tests]
related:
  issues: [VIRC-ISS-0009, VIRC-ISS-0017]
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags: [simd, auto-vectorization, slp, neon, sse2, avx2, rvv, wasm-simd]
---

# VIRC-ISS-0036 — SIMD pass 10 is inert and production vectorization is narrow and target-incomplete

## 1. Summary

The compiler exposes a registered pass 10 named SIMD Auto-Vectorization, but
the production MIR pipeline skips it and the ARM64 backend hook assigned to it
is an identity transformation. General scalar code therefore has no production
pass-10 vectorization at any optimization level.

Explicit `flux` operations do reach native NEON, SSE2, and Wasm SIMD encoders,
and pass 20 can vectorize two narrowly shaped scalar patterns at `-O2` and
`-O3`. Those paths do not satisfy the active language and compiler contracts:
the optimizer is hard-coded to two 64-bit lanes and a small set of integer
array patterns, target coverage is incomplete, vector operation/type coverage
is incomplete, and the `-S` MCInst path silently omits vector LIR operations.

## 2. Context

`VIR-SPC-0017` and `VIR-SPC-0018` specify first-class `flux` vectors mapped to
ARM NEON, x86 SSE/AVX, and Wasm SIMD. Their optimizer inventory also names pass
10 as NEON 128-bit / AVX2 256-bit SIMD auto-vectorization and pass 20 as SLP.
`VIRC-SPC-0001` additionally requires vector reductions and 128/256-bit target
lowering.

This issue records the general compiler and target-lowering gap. Dense tensor
matmul remains scoped to `VIRC-ISS-0017`; binary/MCInst architectural
convergence remains scoped to `VIRC-ISS-0009` except for the vector-specific
correctness evidence recorded here.

The audit used the active canonical compiler sources and `bin/virc 4.2.1` on
2026-10-04. The working tree contained concurrent unrelated compiler work, so
this issue does not claim that uncommitted source represents a released
revision.

## 3. Expected Behavior

- Pass 10 performs measurable, type-correct, target-aware vectorization at its
  documented optimization tier, or is removed/reclassified through an
  approved specification change.
- Pass traces distinguish an executed transformation from a no-candidate or
  unsupported-target result; an identity hook is not reported as SIMD work.
- Scalar loop and basic-block vectorization use element dtype, legal target
  width, alignment, alias/dependence checks, and a correct scalar or masked
  tail without changing program semantics.
- Explicit `flux` arithmetic, load/store, splat, shuffle, reductions, and FMA
  either lower correctly for every advertised target/feature combination or
  produce an approved diagnostic/fallback.
- ARM64, x86-64, RISC-V, and Wasm follow a documented feature matrix including
  `--no-simd`, x86 ISA selection, and `--enable-rvv` behavior.
- Executable and `-S` output preserve the same vector program semantics.

## 4. Actual Behavior

- `compiler/src/ir/mir/mir_opt_pipeline.vri` explicitly skips pass 10.
- `mir_opt_neon_simd_vector_lowering()` returns its input unchanged. The x86,
  RISC-V, and Wasm backend post-MIR dispatch has no corresponding pass-10
  vector lowering.
- JSON optimization traces at `-O2` and `-O3` contain pass 20 and the custom
  hook name `arm64.simd-layout`, but never pass ID 10.
- SLP recognizes only two adjacent indexed stores for lanes 0 and 1. Loop
  vectorization requires a constant trip count, zero initial induction value,
  stride one, one store, two loads, one `Add`/`Sub`/`Mul`, and non-aliasing
  operands. It then hard-codes two lanes and integer element metadata.
- ARM64 explicit vector lowering uses 128-bit NEON but falls back to scalar
  operations for unsupported cases such as integer vector multiply and
  shuffle. x86-64 uses SSE2 128-bit code and has no AVX2/AVX-512 feature path.
- RISC-V reports an RVV feature flag, but target SIMD width excludes RVV and
  vector LIR is emitted as scalar RV64 operations even with `--enable-rvv`.
- Wasm emits SIMD128 for covered explicit operations, but `VFma` shares the
  multiply opcode path and no production MIR producer for `VFma` was found.
- MIR/LIR has no vector divide, comparison, select, reduction, mask, or
  conversion operations. `flux_dot` and `flux_norm` lower to scalar sequences.
- The LIR register allocator has no vector register class; vector values are
  represented through general-purpose registers pointing at allocated lane
  storage and repeatedly loaded into fixed scratch vector registers.
- ARM64/x86-64/RISC-V LIR-to-MC lowering has no `LirOp.V*` cases. `-S` succeeds
  while omitting the vector computation from the emitted assembly.
- `stdlib/vir/hw/simd.vri` describes Q-IR auto-vectorization and calls
  `vir_hw_simd_detect`; no provider for that symbol or
  `vir_hw_cpu_features` was found in the repository.

## 5. Reproduction

From the repository root:

```sh
./bin/virc --version

python3 tools/gap_contract_runner.py \
  --virc bin/virc \
  --target macos-arm64 \
  --filter '^SIMD-(NEON|SSE2|WASM|RISCV|SLP|LOOP)-' \
  --timeout 15 --compile-timeout 60 -v

./bin/virc tests/spec_gap_contract/simd_loop_autovec_tail.vri \
  -O2 --json -o /tmp/vir_simd_loop

./bin/virc tests/spec_gap_contract/simd_neon_native_structural.vri \
  -O0 -o /tmp/vir_flux_o0
otool -tvV /tmp/vir_flux_o0 | \
  rg 'ldr[[:space:]]+q|str[[:space:]]+q|add\.2d|fadd\.2d'

./bin/virc tests/spec_gap_contract/simd_neon_native_structural.vri \
  -O2 -S -o /tmp/vir_flux.s
rg -n -i '\.2d|\.4s|fadd|addpd|padd|xmm|ymm' /tmp/vir_flux.s
```

To compare ordinary scalar source across optimization levels, remove the
fixture-local `# VIRC_FLAGS: -O2` line from
`simd_slp_pair_autovec.vri`, compile the copy at `-O0` through `-O3`, and
disassemble each artifact. The audited ARM64 result contained no vector
arithmetic at `-O0/-O1` and contained `add.2d` at `-O2/-O3`.

## 6. Evidence

- CONFIRMED: `bin/virc` identified itself as self-hosted version 4.2.1.
- CONFIRMED: the focused SIMD contract runner passed 7/7 tests. This proves
  explicit SIMD and the two registered narrow auto-vectorization patterns; it
  does not prove pass 10 or general loop vectorization.
- CONFIRMED: explicit `flux` at `-O0` emitted ARM64 `ldr q`, `str q`,
  `add.2d`, and `fadd.2d` instructions.
- CONFIRMED: an ordinary adjacent scalar pair and the registered stride-one
  loop emitted vector arithmetic only at `-O2/-O3` through pass 20.
- CONFIRMED: `--json` reported pass 20 at `-O2/-O3` and did not report pass 10
  at `-O0`, `-O1`, `-O2`, or `-O3`.
- CONFIRMED: source inspection found the pass-10 skip, identity ARM64 SIMD
  hook, hard-coded two-lane integer SLP/loop metadata, SSE2-only x86 feature
  query, RVV-excluding SIMD width, scalar RVV lowering, and missing vector
  MCInst cases.
- CONFIRMED: `-S` for the explicit `flux` fixture exited successfully but its
  generated ARM64 assembly contained no vector instructions and omitted the
  vector arithmetic performed by direct binary codegen.
- CONFIRMED: repository-wide symbol search found declarations/calls for
  `vir_hw_simd_detect` and `vir_hw_cpu_features` only in the stdlib consumers,
  with no runtime provider.
- NOT_VERIFIED: performance uplift, instruction legality on every CPU model,
  SVE support, AVX frequency trade-offs, scalable RVV lane policy, and native
  execution on every advertised host/target combination.

## 7. Scope

### Affected

- optimizer pass registry, pass tracing, SLP, and loop vectorization;
- vector MIR/LIR operation and dtype coverage;
- ARM64, x86-64, RISC-V, and Wasm vector lowering and feature selection;
- vector register allocation, spills, ABI preservation, and code generation;
- MCInst assembly lowering and binary/assembly semantic parity;
- stdlib SIMD detection bridge and compiler/runtime providers;
- SIMD structural, mutation, runtime, disassembly, and optimization-level tests.

### Not affected / Unknown

- Dense tensor `**` and `><` kernels are tracked by `VIRC-ISS-0017`.
- Quantized Q8_0 storage and consumer-specific kernels remain under their
  existing issues.
- GPU/NPU lowering is outside the current native SIMD audit.
- Existing explicit `flux` add/subtract and covered loads/stores on NEON,
  SSE2, and Wasm SIMD128 are not claimed to be wholly absent.

## 8. Impact

Users cannot rely on optimization flags to provide the general SIMD
auto-vectorization promised by the active specifications. Real numeric loops
outside the two narrow patterns remain scalar, x86 cannot reach the documented
AVX2 width, and RISC-V cannot produce RVV. More seriously, hard-coded element
metadata and the vector-blind `-S` path can produce semantically wrong output
instead of merely slower output. Passing current SIMD tests can therefore give
a materially stronger capability signal than the production compiler supports.

## 9. Preliminary Analysis

- CONFIRMED: explicit-vector frontend/lowering and direct binary encoders were
  added independently from the registered pass-10 backend contract.
- CONFIRMED: pass 20 currently owns both basic-block SLP and the only production
  scalar-loop vectorization transform.
- CONFIRMED: target capability queries do not describe AVX2 or usable RVV, so
  the optimizer cannot select the widths promised by the compiler spec.
- OBSERVED: existing structural tests are effective for their exact fixtures
  but do not assert pass-10 invocation, dtype-aware vectorization, positive RVV,
  `-S` parity, reductions, masks, or general loop legality.
- HYPOTHESIS: a target-neutral legality/cost layer and typed vector IR can unify
  explicit `flux`, SLP, loop vectorization, and target feature selection without
  making tensor kernels part of this issue.
- NOT_VERIFIED: whether current concurrent compiler work already intends to
  replace any of these paths.

## 10. Acceptance Criteria

- [ ] An approved target/ISA/dtype capability matrix defines supported vector
  widths, feature gates, tails, fallbacks, diagnostics, and `--no-simd` behavior
  for ARM64, x86-64, RISC-V, and Wasm.
- [ ] Pass 10 either performs a real, independently testable transformation at
  its documented tier or the registry/spec/pipeline is changed consistently so
  no inert pass is advertised.
- [ ] Optimization telemetry reports pass 10 and pass 20 truthfully, including
  changed/no-candidate/unsupported reasons, with mutation controls that fail
  when either production transformation is bypassed.
- [ ] Vectorization legality is dtype-aware and covers target width, alignment,
  alias/dependence, trip count, induction start/step, and complete scalar or
  masked tails without hard-coded integer/two-lane metadata.
- [ ] The accepted vector IR operation set covers every supported `flux`
  operation and rejects unsupported operations instead of silently substituting
  another opcode.
- [ ] ARM64, x86-64, RISC-V, and Wasm emit only legal instructions for enabled
  features; positive NEON/SSE-or-AVX/RVV/SIMD128 and negative fallback gates are
  scoped to the transformed function or hot loop.
- [ ] Vector values have an approved register/spill/ABI representation with
  verified call preservation and pressure/spill tests.
- [ ] Direct executable and `-S` paths preserve equivalent vector semantics;
  unsupported MC lowering fails explicitly rather than dropping operations.
- [ ] The stdlib SIMD feature-detection contract has a verified provider or is
  moved to a separately linked follow-up issue with a stable fallback contract.
- [ ] O0-O3 runtime equivalence, `--no-simd`, scalar-tail, alias, alignment,
  mixed dtype, reduction, FMA, dynamic trip-count, and multi-target regression
  suites pass together with fixed-point self-host verification.
- [ ] `VIRC-ISS-0017` remains independently verified for dense tensor kernels;
  unrelated tensor evidence is not used to close this general issue.

## 11. Related Papers

### Issues

- `VIRC-ISS-0009` — Native codegen conflates architecture, OS, ABI, and object format.
- `VIRC-ISS-0017` — Dense tensor matmul lacks required target-native SIMD lowering.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Created and triaged from active-source inspection, optimizer JSON traces, focused SIMD contracts, O0-O3 disassembly, and `-S` parity audit |

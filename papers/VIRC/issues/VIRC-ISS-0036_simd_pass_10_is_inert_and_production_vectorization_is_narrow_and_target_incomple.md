---
id: "VIRC-ISS-0036"
type: "ISSUE"
domain: "VIRC"
title: "SIMD pass 10 is inert and production vectorization is narrow and target-incomplete"
status: "TRIAGED"
severity: "S1"
priority: "P1"
created: "2026-10-04"
updated: "2026-10-09"
owners:
  - "compiler"
components:
  - "optimizer"
  - "mir"
  - "lir"
  - "simd"
  - "arm64"
  - "x86-64"
  - "riscv64"
  - "wasm"
  - "mcinst"
  - "stdlib"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0009"
    - "VIRC-ISS-0017"
    - "VIRC-ISS-0057"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "simd"
  - "auto-vectorization"
  - "slp"
  - "neon"
  - "sse2"
  - "avx2"
  - "rvv"
  - "wasm-simd"
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
- `MCOpcode` has no first-class vector/SIMD opcode family for ARM64, x86-64,
  or RISC-V. Wasm SIMD is emitted through raw `0xfd`-prefixed byte sequences
  rather than a typed MC instruction layer. Direct native codegen therefore
  has vector encoders that cannot be represented, verified, or printed through
  the current MC path.
- The direct ARM64 backend has raw encoders for operations including Q-register
  loads/stores, `FADD`, `FSUB`, `FMUL`, `FMLA`, `DUP`, pairwise reductions,
  comparisons, and bit-select forms. The direct x86-64 backend similarly has a
  narrow SSE2 encoder set. Their existence does not satisfy the MC contract
  while `MCOpcode`, target LIR-to-MC lowering, printer, verifier, and encoder
  coverage remain absent.
- Current FMA behavior is not target-equivalent: ARM64 can emit vector `FMLA`,
  x86-64 expands `VFma` to multiply plus add, and Wasm maps `VFma` through the
  same arithmetic opcode selection as multiply. This is incompatible with the
  specified fused operation when intermediate rounding is observable.
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
- CONFIRMED on 2026-10-09 with self-hosted `virc 2026.1.6`: the direct ARM64
  Q80 fixture contained `ldr/str q`, `fmul.2d`, and `fadd.2d`; its
  `--no-simd` binary contained none of those vector operations, while its `-S`
  output contained no vector instruction at all.
- CONFIRMED on 2026-10-09: the native memory-contract fixture executed with
  the expected output and disassembled to `ldr/str q` and `dup.16b`. This
  proves a working direct NEON path, not MC opcode coverage.
- CONFIRMED on 2026-10-09: `MCOpcode` additions present in concurrent work are
  typed scalar load/store operations only; no ARM64 NEON, x86 packed-SIMD, or
  RISC-V RVV opcodes were added.
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

## 10. Required MC Opcode Coverage

The following is the minimum semantic surface that the machine-instruction
layer must be able to represent. The exact enum spelling may use target-specific
opcodes or typed target-neutral pseudos expanded before final emission, but a
vector operation must become one or more explicit, verifiable MC instructions.
A raw code-buffer helper, magic byte/word literal, or an empty LIR-to-MC case is
not an MC opcode implementation.

### 10.1 Cross-target MC contract

- Every existing vector LIR operation (`VLoad`, `VStore`, `VAdd`, `VSub`,
  `VMul`, `VFma`, `Splat`, and `Shuffle`) must either lower to a legal MC
  sequence or produce an explicit unsupported-target/feature diagnostic before
  MC emission. Emitting zero instructions is forbidden.
- MC operands or opcode variants must retain element type, signedness, lane
  width/count, vector width, register class, memory alignment/addressing form,
  mask state, and required ISA feature. These properties must not be recovered
  later from an untyped GPR or a hard-coded two-lane assumption.
- MC verification must reject illegal opcode/type/feature combinations before
  encoding or printing. Examples include an unavailable ARM64 integer
  `MUL.2D`, AVX/FMA instructions under an SSE2-only target, RVV operations
  without vector configuration, and Relaxed SIMD operations without the Wasm
  feature enabled.
- Direct binary emission and `-S` must consume the same MC semantics. If raw
  target encoders remain as final byte/word emitters, they must be selected by
  MC opcodes rather than forming a second vector lowering path.
- `VFma` is fused: lowering it to multiply-only or ordinary multiply followed
  by add is not equivalent because it introduces an intermediate rounding.
  A target without a legal fused instruction must use a semantics-preserving
  helper/expansion approved by the capability matrix or reject the operation;
  it must not silently weaken the contract.
- Scalar fallback and tail code remain legal only when selected explicitly by
  target legality and tested for semantic equivalence. Fallback must not be
  represented as a misleading vector MC opcode.

### 10.2 Minimum target opcode families

| Target / feature tier | Required MC-representable opcode families | Required legality and fallback behavior |
|---|---|---|
| ARM64 Advanced SIMD / NEON 128-bit | Vector memory `LD1`/`ST1` and the selected `LDR`/`STR Q` forms; `FADD`, `FSUB`, `FMUL`, `FMLA` for legal `.4S`/`.2D` shapes; integer `ADD`/`SUB` and legal-width `MUL`; `DUP`, `INS`, lane move/extract; `TBL`/`EXT` and ZIP/UZP/TRN-class shuffle forms; integer/floating compare; `BSL`/`BIT`/`BIF` mask select; `ADDP`/`ADDV`/`FADDP` or equivalent reduction sequences | Preserve dtype and arrangement suffix in MC. Do not invent integer `MUL.2D`; use an approved scalar/legal expansion or diagnostic for unsupported i64x2 multiply. Distinguish ordinary vector `FMLA` from matrix `FMMLA`, which remains under the tensor issue. |
| x86-64 SSE2 baseline | Packed loads/stores such as `MOVDQU`/`MOVUPD`/`MOVUPS` plus aligned variants where selected; `ADDPS/PD`, `SUBPS/PD`, `MULPS/PD`; applicable `PADD*`/`PSUB*`; broadcast/splat sequences; `SHUFP*`, `PSHUFD`, `UNPCK*`; packed compares; logical mask/select; explicit reduction sequences | SSE2 baseline must not emit SSE4.1, AVX, AVX2, or FMA3 opcodes. Operations absent at the baseline, including packed integer widths without a legal multiply, require a feature-gated expansion, scalar fallback, or diagnostic. |
| x86-64 AVX/AVX2/FMA tiers | VEX vector loads/stores; `VADDPS/PD`, `VSUBPS/PD`, `VMULPS/PD`; legal `VPADD*`/`VPSUB*`/`VPMUL*`; `VBROADCAST*`; `VPERM*`/`VSHUF*`; vector compare/blend/mask operations; one explicitly selected `VFMADD132/213/231PS/PD` operand convention | MC must record vector width and required AVX, AVX2, and FMA features separately. The selected FMA operand order must be tested so accumulator/source roles cannot be swapped. `vzeroupper` policy and XMM/YMM spill/ABI behavior must be defined where YMM is used. |
| RISC-V V / RVV | `VSETVLI`/`VSETIVLI`; unit-stride `VLE8/16/32/64.V` and `VSE8/16/32/64.V`; `VADD`/`VSUB`/`VMUL`; `VFADD`/`VFSUB`/`VFMUL`; fused accumulate such as the correctly ordered `VFMACC`/`VFMADD` form; `VMV.V.X`/`VFMV.V.F`; `VRGATHER` and slide forms; mask comparisons and `VMERGE`/`VFMERGE`; integer/floating reduction forms | Each MC sequence must carry or be dominated by compatible SEW, LMUL, VL, mask, tail, and rounding policy. RVV is emitted only when `--enable-rvv` and the target feature contract allow it; otherwise use the documented scalar fallback. Fixed-width `flux` semantics must hold for VLEN-independent hardware. |
| Wasm SIMD128 | Typed MC or an equivalently verified target-machine layer for `v128.load`/`v128.store`; `f32x4`/`f64x2` add, subtract, and multiply; legal integer lane arithmetic; lane splat/extract/replace; `i8x16.shuffle`/swizzle; comparisons; `v128.bitselect`; and explicit reduction sequences | Raw `0xfd` byte pairs are not sufficient without a typed opcode and verifier mapping. Standard SIMD128 has no ordinary fused FMA, and Relaxed SIMD `f32x4.relaxed_madd`/`f64x2.relaxed_madd` does not by itself guarantee Vir's strict one-rounding fused semantics. It therefore requires an explicit compatible semantics decision or must use a semantics-preserving helper/diagnostic. `VFma -> VMul` is forbidden. |

The language-required operations that currently have no MIR/LIR representation
must also receive IR and MC coverage before this issue can close: dot/reduction,
length/normalization support, comparison/mask/select where required by lowering,
lane conversion/extract/insert, and swizzle write-mask/blend semantics. Target
families may implement these with multi-instruction MC sequences, but the
sequence must remain visible to validation and assembly printing.

### 10.3 Opcode completion evidence

For every accepted target/feature row, verification must include:

1. a positive MC construction and verifier test for each supported opcode
   family and lane/dtype shape;
2. a printer golden test and an encoder/disassembler round trip for the same MC
   instruction or sequence;
3. a negative verifier test for illegal feature, register class, lane shape,
   alignment/addressing, and accumulator ordering;
4. a scoped end-to-end fixture proving the expected SIMD instructions occur in
   the transformed function for both direct executable and `-S` output;
5. a `--no-simd` or disabled-feature counterpart proving no forbidden SIMD
   opcode remains and runtime results match the enabled path; and
6. mutation coverage that fails if a vector LIR case emits nothing, maps FMA to
   multiply, selects the wrong opcode width, or bypasses MC through a raw helper.

## 11. Acceptance Criteria

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
- [ ] MC represents all eight existing vector LIR operations and the additional
  reduction/mask/lane operations required by the active `flux` specification;
  no target LIR-to-MC path can silently emit zero instructions for a vector op.
- [ ] The ARM64 MC family covers legal NEON `LD1`/`ST1` or selected Q-register
  load/store forms, `FADD`/`FSUB`/`FMUL`/`FMLA`, integer arithmetic, splat,
  shuffle/lane, compare/select, and reduction operations with verified lane
  arrangements and feature legality.
- [ ] x86-64 MC coverage distinguishes SSE2, SSE4.1 where used, AVX, AVX2, and
  FMA tiers; RISC-V MC coverage includes RVV configuration plus typed vector
  operations; Wasm SIMD uses a typed and verified opcode layer rather than
  unchecked raw byte emission.
- [ ] Fused multiply-add tests prove one-rounding accumulator semantics and
  correct operand order on every supported target. Multiply-only and ordinary
  multiply-plus-add substitutions are rejected unless an approved contract
  explicitly changes the source semantics.
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

## 12. Related Papers

### Issues

- `VIRC-ISS-0009` — Native codegen conflates architecture, OS, ABI, and object format.
- `VIRC-ISS-0017` — Dense tensor matmul lacks required target-native SIMD lowering.

### Plans

- None yet.

### Reports

- None yet.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Created and triaged from active-source inspection, optimizer JSON traces, focused SIMD contracts, O0-O3 disassembly, and `-S` parity audit |
| 2026-10-08 | Linked VIRC-ISS-0057 |
| 2026-10-09 | Added audited MC opcode requirements for ARM64 NEON, x86 SSE/AVX/FMA, RISC-V RVV, and Wasm SIMD128; added direct-binary versus `-S` evidence and fused-FMA legality gates |

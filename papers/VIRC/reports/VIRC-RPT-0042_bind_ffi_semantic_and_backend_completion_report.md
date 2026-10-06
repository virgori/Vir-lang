---
id: "VIRC-RPT-0042"
type: "REPORT"
domain: "VIRC"
title: "Bind FFI semantic and backend completion report"
status: "ACCEPTED"
created: "2026-10-05"
updated: "2026-10-05"
owners: [compiler]
components: [semantic-analysis, ffi, mir, lir, wasm, object-writers, tests]
related:
  issues:
    - "VIRC-ISS-0004"
  plans:
    - "VIRC-PLN-0025"
  reports: []
supersedes: null
superseded_by: null
tags: [bind, ffi, wasm-import, no-opt, artifact-contract, checkpoint]
---

# VIRC-RPT-0042 — Bind FFI semantic and backend completion report

## 1. Executive Summary

The implemented bind path closes the confirmed semantic/backend disconnect:
C/Wasm declaration bindings normalize to the shared external registry, invalid
bodies fail before artifacts, asm bodies retain function-scoped no-opt, and
Wasm emits and executes an exact typed host import. Native C bindings now also
transport f64 arguments/results in AAPCS64 D registers and SysV AMD64 XMM
registers, including mixed f64/integer signatures with independent register
indices. The active contract is 12/12 and Group 15 is 7/7. This report remains
an accepted checkpoint; the source issue stays open for the complete native
runtime/relocation matrix and broad-suite prerequisites.

## 2. Source Issues

- VIRC-ISS-0004

## 3. Source Plans

- VIRC-PLN-0025

## 4. Implementation Summary

- Added stable semantic diagnostics for C/Wasm bodies, missing asm bodies,
  invalid targets/placement, and unsupported signatures.
- Normalized valid C/Wasm binds to `ExternFunc`, preserving parameter/return
  types and provider (`os` or `env`) in the existing FFI registry.
- Removed Vir ERX post-call CFG from foreign calls.
- Added an asm no-opt name registry used by MIR and LIR optional optimizers.
- Emitted per-import Wasm function types, typed arguments/results, and correct
  import call indices.
- Added bit-preserving f64 GPR-to-D/XMM argument moves and D/XMM-to-GPR return
  moves in both direct codegen and LIR-to-MC assembly paths.
- Classified mixed foreign arguments into independent floating and integer ABI
  indices and rejected unsupported RISC-V f64 before artifact emission.
- Replaced generic FFI structural passes with exact assembly/Wasm/runtime and
  mutation oracles.

## 5. Changes by Component

### Semantic classification

- change: body-form, placement, target, and scalar-signature validation plus
  `FuncDef` to `ExternFunc` normalization for declaration-only binds;
- reason: binding identity previously disappeared before lowering;
- impact: FFI-001/002/004/005/006/009/010 reject with no artifact.

### Lowering and optimizer pipeline

- change: foreign calls bypass Vir ERX checks; asm names bypass only optional
  MIR/LIR optimizer hooks while CFG, SSA, verification, lowering, register
  allocation, and code emission remain active;
- reason: foreign callees do not implement Vir error registers and asm requires
  exact function-scoped output;
- impact: external calls no longer create synthetic fallible CFG and asm output
  is stable across O0..O3.

### Wasm writer and contract runner

- change: one exact function type per used import, typed parameter/result
  conversion, import/type/call inspection, host instantiation, and three
  negative mutations;
- reason: the old writer hard-coded one `() -> i32` import type and the runner
  compiled FFI-007 as native;
- impact: `env.host_value: () -> i64` is called and returns `42n` at runtime.

## 6. Deviations from Plan

The plan aimed at the full ISSUE acceptance surface. Native f64 transport is
now implemented and runtime-verified on macOS ARM64, with Linux ARM64 and
x86-64 MC assembly verification. `f32`, Wasm floating binds, and RISC-V native
f64 remain explicit fail-closed cases. Linux x86-64 runtime plus the complete
relocation/dependency matrix were not executable on this host. The repository
`min` suite also has pre-existing failures in float spill/cast and out-parameter
definite-assignment tests; the promoted pre-change compiler reproduces the
float failure. Therefore the ISSUE and PLAN remain active rather than claiming
the unchecked closure criteria.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| FFI contract | PASS | 12/12, 0 blocked |
| C runtime binding | PASS | changing `abs` inputs, pointer/void `write`, 9-argument stack call, f64 `fabs`, mixed `ldexp(f64, i32)` |
| Native f64 structure | PASS | Linux ARM64 uses D registers/FMOV; Linux x86-64 uses XMM/MOVQ; mixed FP/GPR indices are independent |
| Unsupported target ABI | PASS | RISC-V f64 and unavailable Windows runtime fail without artifacts |
| Wasm import | PASS | exact `env.host_value: () -> i64`, called and host-instantiated |
| Wasm mutations | PASS | missing import, wrong signature, and missing call all rejected |
| Asm no-opt | PASS | function assembly identical at O0/O1/O2/O3; main control differs |
| Existing FFI/OS group | PASS | Group 15: 7/7 |
| Generated-source sync | PASS | generator check reports identical |
| Dependency discipline | PASS | 316/316 source files |
| Bootstrap fixed point | PASS | stage 2 = stage 3, SHA-256 `af63c79d2f984eb5c5859ed00a0ea769f8fd13b3922a28b89394d9bb6d04f2d5` |
| Broad `min` suite | NOT GREEN | pre-existing float spill/cast and out-parameter definite-assignment failures; stopped after reproduction because they are outside this plan |

### Regression

All three originally failing negative contracts now reject semantically and
leave no artifact. The two former generic structural contracts now perform
target-specific inspection. Four new cases cover real native calls, unsupported
Wasm/native float signatures, stack arguments, and mutation sensitivity.

### Conformance

No grammar or public stdlib API changed. Existing `extern func` and Group 15
tests remain green. Unsupported floating bind signatures fail before lowering.

## 8. Acceptance Criteria

Mapping 1:1 với ISSUE:

- [x] C/Wasm body and asm missing-body negatives reject with no artifact.
- [x] C invocation reaches real external symbols with changing inputs and an
  observable unbuffered side effect.
- [x] Binding kind/signature/provider and asm no-opt identity reach writers.
- [ ] Full supported-native evidence for floating, every native target ABI,
  relocation/alignment/clobber combinations, and dependency variants.
- [x] Wasm exact import/type/call oracle instantiates with a host function.
- [x] Asm optimizer exclusion is proven at O0..O3 with a normal control.
- [x] Generic structural fallbacks were replaced and mutations are rejected.
- [x] Existing FFI group, sync, dependency, and fixed-point gates pass.
- [x] PLAN and accepted REPORT are linked; ISSUE remains open for the unchecked
  native ABI criterion.

## 9. Known Limitations

Native `@bind(c)` supports integer, boolean, pointer/string, void, and f64
scalar ABI forms on AAPCS64 and SysV AMD64. Native f32, RISC-V foreign f64,
aggregate-by-value, variadic, and callback signatures remain unsupported and
fail closed. Full Linux x86-64/RISC-V execution and object-relocation matrices
were not available in this host verification.

## 10. Remaining Work

Continue `VIRC-ISS-0004` / `VIRC-PLN-0025` with Linux x86-64 runtime and
relocation/dependency execution evidence, RV64D foreign floating transport if
it becomes supported, and resolution or formal baseline treatment of the
pre-existing broad-suite failures.

## 11. Conclusion

REQUIRES_FOLLOWUP

## 12. Related Papers

- `VIRC-ISS-0004`
- `VIRC-PLN-0025`

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Accepted semantic, registry, asm no-opt, Wasm import/runtime, native scalar runtime, sync, and fixed-point checkpoint; retained open native ABI criterion |
| 2026-10-05 | Added AAPCS64/SysV AMD64 f64 plus mixed FP/GPR ABI transport, expanded FFI evidence to 12/12, promoted fixed-point hash `af63c79d2f984eb5c5859ed00a0ea769f8fd13b3922a28b89394d9bb6d04f2d5`, and retained REQUIRES_FOLLOWUP for cross-runtime and broad-suite closure criteria |

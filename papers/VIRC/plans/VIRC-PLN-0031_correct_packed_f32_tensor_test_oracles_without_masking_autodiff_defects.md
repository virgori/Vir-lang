---
id: "VIRC-PLN-0031"
type: "PLAN"
domain: "VIRC"
title: "Correct packed f32 tensor test oracles without masking autodiff defects"
status: "COMPLETED"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "compiler"
components:
  - "tests"
  - "tensor"
  - "matmul"
related:
  issues:
    - "VIRC-ISS-0059"
  plans: []
  reports:
    - "VIRC-RPT-0048"
supersedes: null
superseded_by: null
tags:
  - "tensor"
  - "f32"
  - "test-oracle"
  - "regression"
---

# VIRC-PLN-0031 — Correct packed f32 tensor test oracles without masking autodiff defects

## 1. Objective

Replace obsolete 8-byte `f64` assumptions in dense `f32` matmul fixtures with
oracles that match the structured tensor dtype while preserving failures that
expose the separate width-unaware autodiff runtime.

## 2. Source Issues

- VIRC-ISS-0059

The source issue contains a deterministic reproduction and source-backed
classification of stale test behavior versus active compiler defects.

## 3. Scope

### In Scope

- update the focused identity-matmul layout fixture to 32-bit reads and
  binary32 bit patterns;
- update the aggregate infer-stage assertion to use typed indexing;
- run both fixtures at O0-O3 and rerun Group 26;
- record remaining failures without changing their expected results.

### Out of Scope

- compiler tensor lowering or backend changes;
- autodiff/backward implementation tracked by `VIRC-ISS-0018`;
- quantization and float-print failures;
- language specification changes and compiler version bumps.

## 4. Current Architecture

Dense tensor descriptors distinguish `f32`, `f16`, and `f64`. Literal lowering
uses the descriptor element size, and native matmul carries explicit 16-bit and
32-bit width flags. A dense tensor handle has a 16-byte header followed by a
row-major payload; current `f32` payloads use 4-byte elements.

The focused matmul fixture bypasses typed indexing and reads the payload as
four 8-byte values. The aggregate proof repeats that layout assumption in its
infer stage. The backward runtime is architecturally separate and remains
hard-coded to 8-byte loads and fixed 48-byte gradient buffers.

## 5. Proposed Architecture

Keep one focused physical-layout oracle using `native_read_i32` at the exact
packed offsets. Use typed tensor indexing in the aggregate semantic proof so
that it verifies inference behavior without depending on private element
width. Leave backward fixtures unchanged until `VIRC-ISS-0018` repairs the
runtime contract.

## 6. Design Decisions

### Decision 1 — Separate layout and semantic assertions

**Decision:** Retain raw bit assertions only in the dedicated matmul layout
fixture; use tensor indexing in the aggregate infer proof.

**Rationale:** This preserves direct regression coverage for packed `f32`
storage without coupling a broad semantic proof to an internal ABI.

**Alternatives considered:** Replacing expected 64-bit integers with the two
observed concatenated values was rejected because it would encode host
endianness and still read beyond the logical payload. Converting all checks to
typed indexing was rejected because it would remove direct width coverage.

**Trade-offs:** The raw fixture remains native-runtime specific; the aggregate
proof becomes more portable and easier to interpret.

### Decision 2 — Preserve real backward failures

**Decision:** Do not change autodiff gradient expectations in this plan.

**Rationale:** Source inspection confirms the runtime loads packed `f32`
operands with 8-byte instructions. Updating the test to accept those results
would mask `VIRC-ISS-0018`.

**Alternatives considered:** Marking the backward fixture as expected-failure
was rejected because the existing Group 26 runner has no scoped known-failure
contract and the user requested a fixture correction, not suppression.

**Trade-offs:** Group 26 remains red until its independent compiler defects are
fixed, but each remaining failure retains diagnostic value.

## 7. Implementation Plan

### Phase 1 — Correct the focused physical-layout oracle

- files/modules: `tests/strict_v2/test_float_matmul_e2e.vri`;
- changes: use `native_read_i32`, offsets 16/20/24/28, and binary32 expected
  values;
- dependencies: current tensor header and descriptor contract;
- expected result: exact packed-layout verification passes at O0-O3.

### Phase 2 — Decouple the aggregate infer proof from payload width

- files/modules: `tests/strict_v2/test_spec26_ai_huge_proof.vri`;
- changes: replace Stage 5 raw payload reads with typed multi-index checks;
- dependencies: working typed tensor indexing;
- expected result: Stage 5 passes and execution reaches the independently
  failing Stage 6 backward contract.

### Phase 3 — Verify and document boundaries

- files/modules: Group 26 runner plus VPS ISSUE/PLAN/REPORT;
- changes: run O0-O3 focused checks, Group 26, registry check, and paper
  validation; document all remaining failures;
- dependencies: native `virc`, paper tooling;
- expected result: stale oracles are removed without broadening the claimed
  compiler fix.

## 8. Compatibility

- No language source, parser, ABI, serialized format, LSP, public API, or
  standard-library behavior changes.
- Test expectations become consistent with the already-shipped packed `f32`
  representation.

## 9. Migration

No user migration is required. Only repository-owned fixtures change.

## 10. Validation Plan

- compile and execute the focused layout fixture at O0-O3;
- compile and execute the aggregate proof at O0-O3, expecting it to pass Stage
  5 and retain the Stage 6 failure until `VIRC-ISS-0018` is fixed;
- run `./run_tests.sh 26` and compare the stale-oracle failure set;
- run `./paper registry --check` and `./paper validate`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A test-only change masks a compiler defect | Medium | High | Change only confirmed stale reads and preserve backward assertions |
| Raw bit oracle becomes endian-specific | Low | Medium | Read one 32-bit element at a time and document native target coverage |
| Group 26 remains red | High | Low for this scope | Report independent failures and link their existing issues |

## 12. Rollback Strategy

Revert only the two fixture edits and associated VPS lifecycle records. No
compiler artifact or public interface requires rollback.

## 13. Exit Criteria

- [x] both scoped fixture edits are implemented;
- [x] the focused layout test passes at O0-O3;
- [x] the aggregate proof passes Stage 5 and fails only at the known Stage 6
  backward boundary within this issue's affected stages;
- [x] Group 26 is rerun and remaining failures are classified;
- [x] all VIRC-ISS-0059 acceptance criteria are evaluated;
- [x] an implementation REPORT is accepted;
- [x] VIRC-ISS-0059 is resolved or closed without changing VIRC-ISS-0018.

## 14. Related Papers

- VIRC-ISS-0059 — Packed f32 tensor fixtures retain stale f64 layout oracles.
- VIRC-ISS-0016 — Dense tensor element dtype preservation repair.
- VIRC-ISS-0018 — Infer/train/autodiff runtime gaps.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Approved and activated the scoped fixture-correction plan |
| 2026-10-08 | Completed after focused O0-O3 verification, Group 26 rerun, and accepted report evidence |
| 2026-10-08 | Linked VIRC-RPT-0048 |

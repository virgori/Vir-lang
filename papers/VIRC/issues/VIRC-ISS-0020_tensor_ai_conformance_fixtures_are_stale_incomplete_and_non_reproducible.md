---
id: "VIRC-ISS-0020"
type: "ISSUE"
domain: "VIRC"
title: "Tensor AI conformance fixtures are stale incomplete and non reproducible"
status: "TRIAGED"
severity: "S2"
priority: "P1"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "compiler"
  - "tests"
components:
  - "tensor"
  - "conformance"
  - "strict-v2"
  - "spec-gap-runner"
  - "q8-0"
  - "diagnostics"
  - "ci"
related:
  issues: []
  plans: []
  reports:
    - "VIRC-RPT-0001"
supersedes: null
superseded_by: null
tags:
  - "tensor"
  - "test-debt"
  - "conformance"
  - "oracle"
  - "q8-0"
  - "reproducibility"
---

# VIRC-ISS-0020 — Tensor AI conformance fixtures are stale incomplete and non reproducible

## 1. Summary

Tensor AI verification is not a reliable closure gate in the current tree.
The registered AI contract has stale diagnostic text, missing gradient
observability, and numeric failures; focused strict fixtures include malformed
or obsolete cases; and Q8_0 verification claimed by an existing report cannot
be reproduced because its Python test and manifest rows are absent.

## 2. Context

VIRC-SPC-0005 and VIRC-SPC-0007 require registered executable contracts rather
than source presence or compilation alone. The 2026-10-03 audit compared the
current manifest, strict fixtures, active compiler behavior, and
VIRC-RPT-0001's recorded commands. This ISSUE tracks test and evidence integrity
only; numeric or compiler defects discovered by the tests remain separate
implementation issues.

## 3. Expected Behavior

- Every tensor, matmul/FMA, infer/train/autodiff, quantize, Q8_0, alignment, and
  supported-dtype claim has a registered positive or negative contract.
- Diagnostic oracles use stable codes plus necessary structured fields rather
  than brittle prose fragments.
- Tests compile with canonical Vir syntax and fail only when the capability
  under test regresses.
- Reported verification commands remain present and reproducible from the
  checked-in tree, or the report records superseding evidence without erasing
  history.
- Structural SIMD claims are verified by scoped disassembly and mutation
  controls, not by searching the whole artifact for any vector opcode.

## 4. Actual Behavior

- Running the `AI-*` manifest produced 2 PASS, 6 FAIL, and 1 BLOCKED.
- AI-001, AI-003, and AI-006 expose real zero-result runtime failures.
- AI-005, AI-007, and AI-008 fail because manifest prose does not match the
  compiler's current valid `E3019`, `E3014`, and `E3009` diagnostics.
- AI-002 is blocked because no public gradient observation contract exists.
- `tests/strict_v2/tensor_supported_types_positive.vri` lacks a containing
  function and fails on its trailing `out 0` instead of testing dtype support.
- `tensor_dtype_negative.vri` treats f64 as unsupported even though f64 is
  normative and accepted.
- `tensor_result_alignment_e2e.vri` uses `%` instead of canonical `mod` and
  fails in the parser before checking alignment.
- VIRC-RPT-0001 records five passing Python Q8_0 tests and a `Q80-001` manifest
  row, but neither `tests/test_tensor_q8_0_contract.py` nor any current Q80 row
  exists.

## 5. Reproduction

```sh
python3 tools/gap_contract_runner.py \
  --virc ./bin/virc --filter '^(AI|Q80)-' --verbose

./bin/virc tests/strict_v2/tensor_supported_types_positive.vri \
  --check --json -q
./bin/virc tests/strict_v2/tensor_dtype_negative.vri \
  --check --json -q
./bin/virc tests/strict_v2/tensor_result_alignment_e2e.vri \
  --check --json -q

python3 -m pytest -q tests/test_tensor_q8_0_contract.py
rg -n 'Q80-' tests/spec_gap_contract/manifest.tsv
```

## 6. Evidence

- CONFIRMED: current AI manifest execution produced PASS 2, FAIL 6, BLOCKED 1.
- CONFIRMED: three failures are numeric and three are diagnostic-oracle wording
  mismatches despite the expected error codes being emitted.
- CONFIRMED: the dtype-positive fixture is malformed, the f64-negative fixture
  contradicts VIR-SPC-0018, and the alignment fixture uses rejected syntax.
- CONFIRMED: the Q8_0 Python path reported by VIRC-RPT-0001 does not exist and
  pytest reports no tests ran.
- CONFIRMED: no current `Q80-*` row exists in the spec-gap manifest.
- OBSERVED: the explicit `math.tensor_q8_0` module still compiles, so missing
  verification must not be misreported as proof that the implementation is
  absent.
- NOT_VERIFIED: when or why the Q8 fixtures disappeared and whether equivalent
  coverage exists outside the searched registered suites.

## 7. Scope

### Affected

- registered tensor AI manifest rows, fixtures, runners, and CI entry points;
- stable diagnostic and numeric oracles;
- independent codec/reference checks and scoped opcode verification;
- traceability between current reports and reproducible evidence.

### Not affected / Unknown

- implementation fixes for dense numeric correctness, SIMD, autodiff, generic
  quantization, or stdlib APIs;
- changing active language specifications to match broken fixtures;
- deleting or rewriting historical report claims.

## 8. Impact

Stale and missing tests can both hide real compiler defects and create false
failures, while non-reproducible report evidence prevents ISSUE closure under
VPS. The defect affects release confidence rather than directly changing
program semantics, so it is S2/P1.

## 9. Preliminary Analysis

- CONFIRMED: the current registered suite cannot serve as a green tensor AI
  closure gate.
- CONFIRMED: stale fixture syntax and diagnostic text are separable from the
  real numeric failures.
- HYPOTHESIS: Q8_0 verification was created in a transient implementation tree
  and not preserved when later module work was integrated.
- NOT_VERIFIED: CI coverage or immutable external artifacts that might retain
  the missing evidence.

## 10. Acceptance Criteria

- [ ] Every active tensor AI requirement maps to a registered row with a
  canonical fixture, deterministic oracle, owner, and target/optimization scope.
- [ ] Diagnostic negatives assert stable error codes and structured fields;
  prose is asserted only where wording is itself normative.
- [ ] Supported-type, rejected-syntax, shape, alignment, `**`, `><`, infer,
  train, backward, and quantize fixtures compile with canonical Vir syntax.
- [ ] Independent Q8_0 codec, malformed-view, lifetime, scalar/SIMD/GEMV/GEMM,
  `--no-simd`, and scoped opcode gates are restored and registered.
- [ ] AI-002 is enabled only after a public gradient observation contract is
  approved; until then its blocked state names the governing issue/spec.
- [ ] Test runners distinguish compile failure, runtime nonzero exit, stdout
  mismatch, diagnostic mismatch, and unsupported target in machine output.
- [ ] Mutation controls demonstrate that each critical oracle fails when its
  target behavior is deliberately broken.
- [ ] CI runs the supported target/optimization matrix and retains command,
  compiler revision, artifact, and result evidence referenced by REPORTs.
- [ ] A VPS PLAN and REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- None yet.

### Plans

- None yet.

### Reports

- VIRC-RPT-0001 — historical Q8_0 implementation report containing currently
  non-reproducible test commands.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Created and triaged from current manifest execution, fixture audit, and report-evidence reconciliation |
| 2026-10-03 | Linked VIRC-RPT-0001 |

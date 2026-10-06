---
id: "VIRC-RPT-0025"
type: "REPORT"
domain: "VIRC"
title: "Independent acceptance audit of production PRE and loop transforms"
status: "ACCEPTED"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
components:
  - "mir"
  - "optimizer"
  - "cfg"
  - "ssa"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0001"
  plans:
    - "VIRC-PLN-0001"
  reports:
    - "VIRC-RPT-0024"
supersedes: "VIRC-RPT-0024"
superseded_by: null
tags:
  - "acceptance-audit"
  - "optimizer"
  - "pre"
  - "loop-transforms"
  - "failed-verification"
---

# VIRC-RPT-0025 — Independent acceptance audit of production PRE and loop transforms

## 1. Executive Summary

Independent verification does not support closing `VIRC-ISS-0001`.

The registered seven-test runner passes, but it does not serialize or compare
MIR before/after state, its two mutation tests only assert successful
compilation, and it contains no tiling fixture. The loop fusion and loop
interchange positive fixtures emit assembly that is bit-identical when the
production loop transforms are bypassed by mutation mode 9. The fusion fixture
also retains three distinct loops in optimized assembly.

This report therefore supersedes the closure conclusion of `VIRC-RPT-0024`,
records `FAILED_VERIFICATION`, and returns `VIRC-ISS-0001` to implementation.
The audit does not assert that every implementation path is incorrect; it
establishes that the current evidence cannot prove the acceptance criteria.

## 2. Source Issues

- VIRC-ISS-0001

## 3. Source Plans

- VIRC-PLN-0001

## 4. Implementation Summary

No compiler implementation was changed by this audit. The reviewed change set
adds PRE and loop-transform code, enables PRE in the MIR pipeline, adds two
mutation modes, and registers a Python runner plus `.vri` fixtures. This report
evaluates whether those changes satisfy the ISSUE closure gate.

## 5. Changes by Component

### `tests/test_opt_pre_and_loop_transforms.py`

- observed: all seven tests pass with the current compiler;
- finding: no test captures deterministic MIR before/after structure;
- finding: `test_03_pre_mutation_control_catches_identity_regression` and
  `test_06_loop_mutation_marker_control` only require return code zero;
- impact: identity PRE and marker/identity loop behavior are not rejected by
  the named mutation-control tests.

### `tests/opt_structural/`

- observed: PRE, fusion, and interchange fixtures exist;
- finding: no loop-tiling fixture exists and no fusion negative fixture exists;
- impact: the acceptance matrix for fusion, tiling, and interchange is
  incomplete.

### `compiler/src/ir/mir/mir_opt_pipeline.vri`

- observed: pass 9 invokes the combined loop transform entry point and pass 19
  invokes PRE;
- finding: the only verifier around the complete optimization round is
  `mir_verify_memory_contract`, which verifies arena/ownership metadata rather
  than complete CFG/SSA invariants;
- impact: the claim that MIR verifiers pass after every individual mutation is
  not established.

### VPS lifecycle

- change: superseded the unsupported closure conclusion in `VIRC-RPT-0024` and
  returned `VIRC-ISS-0001` to implementation;
- reason: mandatory closure evidence failed independent review;
- impact: no release or implementation claim may treat this ISSUE as closed.

## 6. Deviations from Plan

Material deviations from `VIRC-PLN-0001` are present:

- planned: a production-pass structural harness with deterministic before/after
  facts; actual: compilation/runtime checks plus pass-invocation metadata;
- planned: mutation controls that make the oracle fail; actual: mutation tests
  explicitly accept successful compilation and assert no structural delta;
- planned: positive and legality-negative coverage for fusion, tiling, and
  interchange; actual: no tiling fixture and no fusion negative fixture;
- planned: verifier execution after each CFG/SSA mutation; actual: a memory
  contract verifier runs before and after the whole optimization round;
- planned: reproducible self-host, min/full, and target evidence; actual:
  `VIRC-RPT-0024` records summary claims without exact self-host commands,
  artifact hashes, full-suite output, or target results.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| `python3 tests/test_opt_pre_and_loop_transforms.py --virc bin/virc` | PASS, but insufficient | 7/7 in 0.828s; source inspection shows no structural oracle and ineffective mutation assertions |
| PRE normal vs `--mutate-mir=identity_pre`, `-O2 -S` | OBSERVED delta | SHA-256 differs and assembly shows edge computation/merge changes; this supports one positive PRE case but is not deterministic MIR serialization |
| Fusion normal vs `--mutate-mir=marker_loop_transforms`, `-O2 -S` | FAIL acceptance | both assemblies SHA-256 `95e36eef9da0fac2a17ab60fa62bb42f9c70b90e2c8d404ed97c8ea02b8a6ce5`; optimized fixture retains loop headers at `LBB_1_3`, `LBB_1_6`, and `LBB_1_9` |
| Interchange normal vs `--mutate-mir=marker_loop_transforms`, `-O2 -S` | FAIL acceptance | both assemblies SHA-256 `8a8f48bfa5d5aec80cb1ce7f6830c4050d6693dfbb15959b7f3cddb2b44efdbd` |
| `python3 tools/sync_virc.py --check` | PASS | generated bundle identical to modular sources |
| `python3 tools/check_module_dependencies.py --verbose` | PASS | 314 compiler source files clean |
| `python3 tools/check_pass_architecture.py` | PASS | 3 orchestrators checked; no reported architecture violation |
| `./paper registry --check && ./paper validate` | PASS before lifecycle correction | registry synchronized; 99 production papers and 3 examples valid |

Exact focused commands executed from the repository root:

```sh
python3 tests/test_opt_pre_and_loop_transforms.py --virc bin/virc
python3 tools/sync_virc.py --check
python3 tools/check_module_dependencies.py --verbose
python3 tools/check_pass_architecture.py

bin/virc tests/opt_structural/pre_positive.vri -O2 -S \
  -o /private/tmp/pre_normal.s
bin/virc tests/opt_structural/pre_positive.vri -O2 -S \
  --mutate-mir=identity_pre -o /private/tmp/pre_identity.s
bin/virc tests/opt_structural/loop_fusion_positive.vri -O2 -S \
  -o /private/tmp/loop_normal.s
bin/virc tests/opt_structural/loop_fusion_positive.vri -O2 -S \
  --mutate-mir=marker_loop_transforms -o /private/tmp/loop_marker.s
bin/virc tests/opt_structural/loop_interchange_positive.vri -O2 -S \
  -o /private/tmp/interchange_normal.s
bin/virc tests/opt_structural/loop_interchange_positive.vri -O2 -S \
  --mutate-mir=marker_loop_transforms -o /private/tmp/interchange_identity.s

shasum -a 256 /private/tmp/pre_normal.s /private/tmp/pre_identity.s \
  /private/tmp/loop_normal.s /private/tmp/loop_marker.s \
  /private/tmp/interchange_normal.s /private/tmp/interchange_identity.s
cmp -s /private/tmp/loop_normal.s /private/tmp/loop_marker.s
cmp -s /private/tmp/interchange_normal.s /private/tmp/interchange_identity.s
```

### Regression

The user-provided `./run_tests.sh min` summary reports 413 PASS and 4 FAIL out
of 417. This audit treats that as OBSERVED context, not as proof that required
regression suites passed. No independent full-suite or new-compiler self-host
artifact was available with reproducible hashes in `VIRC-RPT-0024`.

### Conformance

`VIRC-SPC-0008` is ACTIVE but does not specify PRE, fusion, tiling, or
interchange. It therefore cannot substantiate the report's detailed algorithm
claims. The ISSUE and approved PLAN remain the governing acceptance contract.

## 8. Acceptance Criteria

Mapping 1:1 with `VIRC-ISS-0001`:

- [ ] A registered structural harness invokes production MIR passes and
  serializes deterministic before/after structure — NOT VERIFIED; the runner
  observes pass invocation and final execution/assembly only.
- [ ] PRE implements a named algorithm on an explicit safe domain with edge
  placement and SSA repair — PARTIALLY OBSERVED for one diamond; the claimed
  formulation and negative domain are not fully demonstrated.
- [ ] Positive PRE fixtures mutate and required unsafe cases remain unchanged —
  PARTIALLY OBSERVED; no barrier, trap, or unsupported-shape structural oracle.
- [ ] Fusion, tiling, and interchange have structural positive and legality
  negative cases — FAILED; tiling coverage is absent and fusion/interchange
  positives do not prove a transform.
- [ ] Successful loop transforms change loop/CFG/SSA structure without relying
  on patch points — FAILED for current fixtures; bypass and normal assembly are
  bit-identical.
- [ ] MIR verifiers pass after every mutation and mutation controls catch
  identity/marker regressions — FAILED; mutation tests assert success and only
  the memory-contract verifier surrounds the whole optimization round.
- [ ] O0/O1/O2/O3 host parity and honest cross-target results — NOT VERIFIED as
  a complete matrix; PRE omits O1, interchange omits O1/O3, tiling is absent,
  and cross-target evidence is absent.
- [ ] Generated source, self-host fixed point, and required regression suites
  pass using the new compiler — PARTIALLY OBSERVED; source sync passes, but the
  remaining evidence is not reproduced in this audit and the recorded min run
  contains four failures.
- [ ] A REPORT records exact commands, structural diffs, results, limitations,
  and deviations — FAILED for the closure report; this audit records the gaps
  but cannot substitute for missing implementation evidence.

## 9. Known Limitations

- This audit proves insufficiency of the current acceptance evidence; it is not
  a complete semantic proof against every PRE or loop-transform input.
- Static inspection also shows `mir_pre_is_safe_to_insert_in_pred` accepts
  source operands but does not test their availability or dominance. This is an
  OBSERVED review risk, not yet a demonstrated miscompile, and needs a focused
  negative structural/runtime fixture before closure.
- Assembly identity is decisive against the current structural-positive oracle,
  but a future MIR-level harness is still required to diagnose why the pass
  skipped or whether later passes canonicalized a real mutation away.
- Self-host fixed-point and full regression claims remain NOT_VERIFIED here
  because `VIRC-RPT-0024` does not provide reproducible commands and hashes.

## 10. Remaining Work

Work remains within `VIRC-ISS-0001`:

1. Add a deterministic production MIR harness that records before/after CFG,
   SSA, transform status, and skip reason.
2. Make identity PRE and marker/identity loop mutation modes cause the
   structural test suite to fail.
3. Add structural positive and legality-negative fixtures for fusion, tiling,
   and interchange, plus PRE barrier/trap/redefinition/unsupported cases.
4. Add or invoke CFG/SSA verification after each transform, not only the memory
   contract verifier around a whole optimization round.
5. Re-run the full optimization-level, target, self-host, generated-source,
   min/full regression, and mutation matrices with exact commands and artifact
   hashes in a new report that is eligible for closure.

## 11. Conclusion

FAILED_VERIFICATION

## 12. Related Papers

- VIRC-ISS-0001 — MIR PRE and loop transform passes lack production transformations
- VIRC-PLN-0001 — Implement production PRE loop transforms and George-Appel IRC
- VIRC-RPT-0024 — Superseded closure report
- VIRC-SPC-0001 — Compiler Runtime Algorithms
- VIRC-SPC-0008 — Compiler Optimization

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Independent acceptance audit; superseded VIRC-RPT-0024 closure conclusion and recorded failed verification |

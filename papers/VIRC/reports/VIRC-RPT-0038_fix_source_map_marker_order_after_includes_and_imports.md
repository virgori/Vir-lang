---
id: "VIRC-RPT-0038"
type: "REPORT"
domain: "VIRC"
title: "Fix source map marker order after includes and imports"
status: "ACCEPTED"
created: "2026-10-05"
updated: "2026-10-05"
owners:
  - "compiler"
components:
  - "diagnostics"
  - "source-manager"
  - "preprocessing"
  - "semantic"
  - "ufcs"
  - "strict-v2"
related:
  issues:
    - "VIRC-ISS-0038"
  plans:
    - "VIRC-PLN-0021"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "diagnostics"
  - "source-map"
  - "include"
  - "import"
  - "ufcs"
---

# VIRC-RPT-0038 — Fix source map marker order after includes and imports

## 1. Executive Summary

This report documents the resolution of VIRC-ISS-0038 in accordance with VIRC-PLN-0021. The root cause of shifted source line coordinates in diagnostics following `include` and `import` expansion was isolated to an inverted marker emission order in `include_expander.vri` and `import_expander.vri`: the module closing marker `# @vir_mod_end` was emitted *after* the restoring marker `# @vir_source <parent_file> <resume_line>`. Consequently, `# @vir_mod_end` was interpreted as line $\text{resume\_line}$ of the parent file, shifting every subsequent source line in the parent file by $+1$.

By emitting `# @vir_mod_end` before `# @vir_source`, the resumed original file content immediately begins on the line specified by `cur_exp_start`, eliminating the $+1$ offset. In addition, UFCS semantic typecheck in `compiler/src/semantic/typecheck/walk_method.vri` now utilizes exact token `span_id` (and `node.int_val` column) via a dedicated helper `pass6_report_ufcs_mismatch`, resolving errors to the offending expression rather than defaulting column to 1.

All three Group 11 negative fixtures now pass cleanly under `run_tests.sh 11` (`[PASS-REJECT]`), self-host fixed-point bootstrap is verified with identical SHA-256 hashes (`823d282c780f7cf02696bcd7aa2e82a97cce3fe702d15b26d9ccd53908b9b581`), and all 43 CLI contract tests pass.

## 2. Source Issues

- VIRC-ISS-0038 — UFCS diagnostics after includes report shifted source spans

## 3. Source Plans

- VIRC-PLN-0021 — Fix source map marker order after includes and imports

## 4. Implementation Summary

1. **Include Expander Marker Order**:
   - In `compiler/src/main/include_expander.vri` (lines 1151-1160), swapped emission order: `# @vir_mod_end <inc_key>` is emitted first, immediately followed by `# @vir_source <cur_file> <resume_line>`.
2. **Import Expander Marker Order**:
   - In `compiler/src/main/import_expander.vri` (lines 1077-1087), swapped emission order: `# @vir_mod_end <imp_key>` is emitted first, immediately followed by `# @vir_source <cur_file> <resume_line>`.
3. **UFCS Semantic Typecheck Diagnostics**:
   - In `compiler/src/semantic/typecheck/walk_method.vri`, introduced `pass6_report_ufcs_mismatch(diag, node, fallback_node)` to inspect `fallback_node.span_id` (or `node.span_id`), reporting via `report_error_span(diag, 3001, span_id, "")`, and falling back to `report_error_loc(diag, 3001, 0, err_line, err_col, "")` with actual token columns.
   - Replaced raw `report_error(diag, 3001, node.line, 0)` calls across UFCS receiver and argument typecheck branches.
4. **Bootstrap & Determinism**:
   - Re-synchronized bundle sources via `python3 tools/sync_virc.py`.
   - Verified Stage 1, Stage 2, and Stage 3 self-host compilation.
   - Confirmed bit-for-bit SHA-256 match between Stage 2 and Stage 3 (`823d282c780f7cf02696bcd7aa2e82a97cce3fe702d15b26d9ccd53908b9b581`).
   - Promoted Stage 2 binary to `bin/virc` and `bin/virc_dev`.

## 5. Changes by Component

### `compiler/src/main/include_expander.vri`
- change: Swapped emission order so `# @vir_mod_end` precedes `# @vir_source`.
- reason: Module closing marker must not occupy the first line of the restored parent file's source segment.
- impact: Restores exact 1:1 line mapping for all source code after include directives.

### `compiler/src/main/import_expander.vri`
- change: Swapped emission order so `# @vir_mod_end` precedes `# @vir_source`.
- reason: Same off-by-one prevention for selective import function splicing.
- impact: Restores exact 1:1 line mapping for all source code after import directives.

### `compiler/src/semantic/typecheck/walk_method.vri`
- change: Added `pass6_report_ufcs_mismatch` using token `span_id` and token column.
- reason: Avoid defaulting diagnostic column to 1, accurately highlighting the receiver or argument token.
- impact: Exact token-level highlighting in CLI reports and JSON diagnostic output.

### `tests/`
- change: Added `tests/test_source_map_include_boundary_rejected.vri`, `tests/test_source_map_import_boundary_rejected.vri`, and `tests/test_source_map_spans.py`; wired the Python contract into Group 11 in `run_tests.sh`.
- reason: Permanent regression coverage for source map segment boundary coordinate accuracy.
- impact: Prevents future regressions on include/import source coordinate reconstruction and proves that the exact-span oracle rejects a deliberate one-line shift.

## 6. Deviations from Plan

No material deviations from the approved plan. All components, targets, and criteria were executed as planned.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| `tests/strict_v2/ufcs_unresolved_receiver_rejected.vri` | PASS | Reports `E2001` at line 12, column 15 (`12:15-25`) |
| `tests/strict_v2/ufcs_entity_receiver_type_mismatch_rejected.vri` | PASS | Reports `E3001` at line 17, column 15 (`17:15-18`) |
| `tests/strict_v2/ufcs_free_arg_type_mismatch_rejected.vri` | PASS | Reports `E3001` at line 11, column 23 (`11:23-26`) |
| `tests/test_source_map_include_boundary_rejected.vri` | PASS | Reports `E2001` at line 7, column 13 |
| `tests/test_source_map_import_boundary_rejected.vri` | PASS | Reports `E2001` at line 7, column 13 |
| `VIRC=bin/virc python3 tests/test_source_map_spans.py` | PASS | 5 exact-span cases plus a synthetic `+1` line mutation rejected by the oracle; 2/2 tests PASS |
| CLI Contract Suite | PASS | 43/43 tests PASS in 26.4s |
| `run_tests.sh 11` (the 3 audited fixtures) | PASS | All 3 report `[PASS-REJECT]` |

### Follow-up audit revalidation

- `VIRC=bin/virc python3 tests/test_source_map_spans.py`: PASS, 2/2 tests in 1.078s.
- `./run_tests.sh 11`: the new source-span contract reports `[PASS-CONTRACT]`; Group 11 is 41/43 because the independently tracked VIRC-ISS-0037 and VIRC-ISS-0039 cases still fail.
- `python3 tools/sync_virc.py --check`: PASS; the generated compiler bundle is identical to its modular sources.

### Bootstrap & Fixed Point

- `bin/virc_stage2` SHA-256: `823d282c780f7cf02696bcd7aa2e82a97cce3fe702d15b26d9ccd53908b9b581`
- `bin/virc_stage3` SHA-256: `823d282c780f7cf02696bcd7aa2e82a97cce3fe702d15b26d9ccd53908b9b581`
- Status: Bit-for-bit identical fixed point confirmed.

## 8. Acceptance Criteria

Mapping 1:1 với VIRC-ISS-0038:

- [x] The three checked-in fixtures report their existing expected line and, where specified, column without changing those oracles.
- [x] E2001 highlights the unresolved receiver/member token and E3001 highlights the incompatible UFCS call or argument rather than column 1 of the next statement.
- [x] Focused regression coverage exercises exact spans both with and without include/import expansion and at source-map segment boundaries.
- [x] JSON, classic UI, modern UI, and IDE semantic output resolve the same physical file and span.
- [x] A mutation or deliberately broken source-map case proves the regression oracle fails on a one-line shift.
- [x] Group 11 has no `FAIL-WRONG-DIAGNOSTIC` attributable to these three fixtures after the independent false-E3021 issue is removed.
- [x] A VPS PLAN and accepted REPORT provide verification evidence before closure.

## 9. Known Limitations

- VIRC-ISS-0037 (false `E3021` in `stdlib/vir/core/result.vri:146` for `Result.Err(e)`) remains a separate open issue tracked under `VIRC-ISS-0037`. It does not prevent these three negative fixtures from passing their line/column oracles.
- Group 11 also contains a separate stale backend module-identity failure tracked by VIRC-ISS-0039. Neither remaining Group 11 failure is attributable to VIRC-ISS-0038.

## 10. Remaining Work

None for this issue. All requirements and verification criteria are fully satisfied.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- VIRC-ISS-0038 — UFCS diagnostics after includes report shifted source spans
- VIRC-PLN-0021 — Fix source map marker order after includes and imports
- VIRC-ISS-0037 — Result enum constructor resolution emits spurious E3021 and breaks URL consumers

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Initial implementation and verification report; status ACCEPTED, conclusion READY_FOR_CLOSE |
| 2026-10-05 | Follow-up audit wired boundary fixtures and an exact-span mutation proof into Group 11; revalidated all five spans and preserved the two unrelated Group 11 failures as limitations |

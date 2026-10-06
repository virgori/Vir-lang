---
id: "VIRC-PLN-0021"
type: "PLAN"
domain: "VIRC"
title: "Fix source map marker order after includes and imports"
status: "COMPLETED"
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
  plans: []
  reports:
    - "VIRC-RPT-0038"
supersedes: null
superseded_by: null
tags:
  - "diagnostics"
  - "source-map"
  - "include"
  - "import"
  - "ufcs"
---

# VIRC-PLN-0021 — Fix source map marker order after includes and imports

## 1. Objective

Resolve VIRC-ISS-0038 by restoring exact original-source coordinates and spans for all tokens and diagnostics following `include` and `import` expansion:
1. Ensure `include_expander.vri` and `import_expander.vri` emit `# @vir_mod_end` before the restoring `# @vir_source <cur_file> <resume_line>` marker, so that no non-marker line exists between `# @vir_source` and the resumed original file content.
2. Ensure UFCS typecheck in `compiler/src/semantic/typecheck/walk_method.vri` uses token `span_id` (or `node.int_val` column) when reporting `E3001` rather than passing column 0, which previously defaulted to column 1.
3. Verify that the three Group 11 negative fixtures (`ufcs_unresolved_receiver_rejected.vri`, `ufcs_entity_receiver_type_mismatch_rejected.vri`, `ufcs_free_arg_type_mismatch_rejected.vri`) report exact lines (12, 17, 11) and columns matching their existing oracles without modifying those oracles.
4. Execute full self-host fixed-point bootstrap and verify the entire test suite.

## 2. Source Issues

- VIRC-ISS-0038 — UFCS diagnostics after includes report shifted source spans

## 3. Scope

### In Scope

- `compiler/src/main/include_expander.vri`:
  - In `expand_include_recurse`, swap emission order so `# @vir_mod_end` precedes `# @vir_source <cur_file> <resume_line>`.
- `compiler/src/main/import_expander.vri`:
  - In `expand_import_recurse`, swap emission order so `# @vir_mod_end` precedes `# @vir_source <cur_file> <resume_line>`.
- `compiler/src/semantic/typecheck/walk_method.vri`:
  - When reporting error 3001 for receiver or argument mismatch in UFCS calls, prefer `report_error_span` with `node.span_id` or `arg_node.span_id`, falling back to `report_error(diag, 3001, node.line, node.int_val)` instead of column 0.
- Test and regression verification:
  - Verify Group 11 and Group 16 test suites.
  - Add regression coverage ensuring source map segment boundaries accurately preserve line and column coordinates.

### Out of Scope

- VIRC-ISS-0037: False `E3021` on `Result.Err(e)` constructor resolution (independent semantic issue).
- Redesigning `SourceManager` data structures or wire formats.

## 4. Current Architecture

In `compiler/src/main/include_expander.vri` (lines 1154-1160) and `import_expander.vri` (lines 1080-1086):
```vir
sb = sb_append(sb, "# @vir_source ")
sb = sb_append(sb, cur_file)
sb = sb_append_char(sb, 32)
sb = sb_append_int(sb, resume_line)
sb = sb_append(sb, "\n# @vir_mod_end ")
sb = sb_append(sb, inc_key)
sb = sb_append(sb, "\n")
```
At expanded line $E$, `# @vir_source cur_file resume_line` is emitted.
`SourceManager.sm_build_from_source` sets `cur_orig_start = resume_line` and `cur_exp_start = E + 1`.
However, expanded line $E + 1$ contains `# @vir_mod_end inc_key`.
The actual original source code resumes on expanded line $E + 2$.
When mapping token line $E + 2$ back to original source, `sm_line_from_expanded` calculates:
$$\text{orig\_line} = \text{orig\_start} + (\text{exp\_line} - \text{s\_start}) = \text{resume\_line} + (E + 2 - (E + 1)) = \text{resume\_line} + 1$$
Every single source line following the include/import in `cur_file` is therefore systematically shifted by $+1$.

Furthermore, in `compiler/src/semantic/typecheck/walk_method.vri`, calls to `report_error(diag, 3001, node.line, 0)` supply column 0. In `diagnostic/context.vri`, column $\le 0$ defaults to column 1. Combined with the $+1$ line shift, errors pointed to column 1 of the subsequent statement rather than the call itself.

## 5. Proposed Architecture

1. Emit `# @vir_mod_end <key>\n` first (closing the included/imported module's expanded range).
2. Immediately emit `# @vir_source <cur_file> <resume_line>\n` (establishing the source-map segment for `cur_file` starting at `resume_line`).
3. The very next expanded line is line `resume_line` of `cur_file`. Thus `cur_exp_start` corresponds exactly to `resume_line`, yielding 0 offset delta:
   $$\text{orig\_line} = \text{resume\_line} + (\text{cur\_exp\_start} - \text{cur\_exp\_start}) = \text{resume\_line}$$
4. In `walk_method.vri`, report `E3001` via `report_error_span` whenever `node.span_id > 0` or `arg_node.span_id > 0`, preserving exact token spans in both JSON and human diagnostics.

## 6. Design Decisions

### Decision 1: Marker ordering vs modifying SourceManager parser

**Decision:** Swap the emission order in `include_expander.vri` and `import_expander.vri` rather than changing `SourceManager` to treat `# @vir_mod_end` specially.

**Rationale:** Syntactically, an included module begins at `# @vir_mod_start` and ends at `# @vir_mod_end`. Emitting `# @vir_mod_end` before switching back to the parent file with `# @vir_source` accurately represents the nesting hierarchy. `SourceManager` assumes that all non-marker lines belong to the file named in the most recent preceding `# @vir_source`.

**Trade-offs:** None. This keeps `SourceManager` simple and maintains parity between `SourceManager` and `driver/locate.vri`.

## 7. Implementation Plan

### Phase 1 — Expander Marker Order
- Update `compiler/src/main/include_expander.vri`.
- Update `compiler/src/main/import_expander.vri`.

### Phase 2 — UFCS Diagnostic Spans
- Update `compiler/src/semantic/typecheck/walk_method.vri` to use `span_id` and column metadata for `E3001`.

### Phase 3 — Synchronization, Build & Bootstrap
- Run `python3 tools/sync_virc.py` and verify `compiler/generated/virc.vri --check`.
- Build Stage 1 compiler: `bin/virc compiler/generated/virc.vri -O1 -o bin/virc_stage1`.
- Verify the three test cases with `bin/virc_stage1`.
- Build Stage 2 and Stage 3 compilers to establish fixed-point determinism (`shasum -a 256`).
- Promote compiler to `bin/virc` and `bin/virc_dev`.

### Phase 4 — Test Verification
- Run `./run_tests.sh 11`.
- Run full CLI contract test suite.

## 8. Compatibility

- Preserves backward compatibility with all valid source programs.
- Makes diagnostics strictly conform to existing negative test oracles and user expectations.
- No changes to serialized formats, ABI, or syntax.

## 9. Migration

No migration required. Existing test suites and sources automatically benefit from accurate source span mappings.

## 10. Validation Plan

- Verify `tests/strict_v2/ufcs_unresolved_receiver_rejected.vri` reports line 12, column 15.
- Verify `tests/strict_v2/ufcs_entity_receiver_type_mismatch_rejected.vri` reports line 17.
- Verify `tests/strict_v2/ufcs_free_arg_type_mismatch_rejected.vri` reports line 11.
- Verify full bootstrap fixed point between Stage 2 and Stage 3 compilers.
- Run test groups and CLI contract suite.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Existing tests that might rely on shifted lines fail | Low | Low | Only the three Group 11 tests previously had shifted lines; all other strict fixtures without includes already expected unshifted lines |
| Bootstrap non-determinism | Low | High | SHA-256 fixed-point verification across successive stages |

## 12. Rollback Strategy

Revert modifications to `include_expander.vri`, `import_expander.vri`, and `walk_method.vri`, then resynchronize `compiler/generated/virc.vri`.

## 13. Exit Criteria

- [x] `include_expander.vri` and `import_expander.vri` emit `# @vir_mod_end` before `# @vir_source`.
- [x] `ufcs_unresolved_receiver_rejected.vri` reports line 12, column 15 (`E2001`).
- [x] `ufcs_entity_receiver_type_mismatch_rejected.vri` reports line 17 (`E3001`).
- [x] `ufcs_free_arg_type_mismatch_rejected.vri` reports line 11 (`E3001`).
- [x] Self-host fixed-point bootstrap matches SHA-256 between Stage 2 and Stage 3.
- [x] VIRC-RPT report created and accepted, closing VIRC-ISS-0038.

## 14. Related Papers

- VIRC-ISS-0038 — UFCS diagnostics after includes report shifted source spans
- VIRC-ISS-0037 — Result enum constructor resolution emits spurious E3021 and breaks URL consumers

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Initial plan created for VIRC-ISS-0038 implementation |
| 2026-10-05 | Linked VIRC-RPT-0038 |
| 2026-10-05 | Marked COMPLETED upon verification and acceptance of VIRC-RPT-0038 |

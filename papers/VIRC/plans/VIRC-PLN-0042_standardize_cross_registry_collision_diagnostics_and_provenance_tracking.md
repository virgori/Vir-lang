---
id: "VIRC-PLN-0042"
type: "PLAN"
domain: "VIRC"
title: "Standardize cross-registry collision diagnostics and provenance tracking"
status: "COMPLETED"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "compiler"
  - "frontend"
  - "tooling"
components:
  - "module-resolution"
  - "module-registry"
  - "diagnostics"
  - "regression-suite"
related:
  issues:
    - "VIRC-ISS-0047"
  plans: []
  reports:
    - "VIRC-RPT-0059"
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "module-list"
  - "collision"
  - "e2123"
  - "diagnostic-provenance"
---

# VIRC-PLN-0042 — Standardize cross-registry collision diagnostics and provenance tracking

## 1. Objective

Standardize cross-registry collision error diagnostics, fix diagnostic classification inversion between duplicate project module registrations (E2121) and cross-registry stdlib collisions (E2123), preserve Module ID strings and declaration provenance across both classic and JSON diagnostic outputs, achieve cross-tool diagnostic parity between the native compiler and Python module graph tooling, and establish comprehensive native regression coverage for exact collision rejection and prefix allowance.

## 2. Source Issues

- **VIRC-ISS-0047**: Cross-registry collision diagnostics lose module identity and registry provenance.
- **VIR-ISS-0008**: Standard library module identifiers are not normatively reserved against project collisions.
- **VIRC-ISS-0043**: Active toolchain sysroot and stdlib registry discovery.

## 3. Scope

### In Scope

- Fix string conversion bug at error reporting call sites in `compiler/src/main/module_resolver.vri` (`full_key as string` -> `str_from_cstr(full_key)`) so canonical Module IDs are rendered in diagnostics.
- Correct inverted diagnostic messages in `compiler/src/semantic/diagnostics/msg_frontend.vri` for error codes E2121 and E2123.
- Capture and format standard library declaration provenance (`reg_path`, `line_no`, `mapping`) in `compiler/src/main/module_resolver.vri` when detecting cross-registry collisions.
- Align Python resolver `tools/module_graph.py` to emit E2123 with full provenance on cross-registry collision, E2121 on intra-registry duplicates, and E2126 on prefix collisions.
- Add focused native unit tests in `tests/module/resolver_test.vri` covering:
  - Exact project vs. stdlib collision (E2123) with provenance reporting.
  - Prefix-only allowance matrix (`http`/`http.app`, `json`/`json.app`, `db.sqlite`/`db.sqlite3`).
  - Distinct separation of project duplicate (E2121), prefix collision (E2126), and cross-registry collision (E2123).
- Synchronize self-hosted compiler `compiler/generated/virc.vri`, rebuild `bin/virc`, and verify bootstrap reproducibility.

### Out of Scope

- Modifying active sysroot discovery policy (`VIRC-ISS-0043`).
- Altering the normative exact-only reservation semantics specified in `VIR-ISS-0008` and `VIR-SPC-0006`.
- Changing symbol-level lexical shadowing (local variables or functions).

## 4. Current Architecture

Currently, the native resolver loads `stdlib.vri` followed by project `module.list`. During project registry ingestion in `compiler/src/main/module_resolver.vri`:
1. When a project key duplicates an existing project key, it invokes `inc_report_early_error_related(2121, ...)`.
2. When a project key exact-matches an stdlib key, it invokes `inc_report_early_error_related(2123, ...)`.
3. However, both call sites pass `full_key as string`, casting a raw 64-bit integer pointer to a fat string slice. Because the length field of the slice is evaluated from invalid memory offsets, `fat_str_len` evaluates to 0, stripping the module name from the diagnostic.
4. In `compiler/src/semantic/diagnostics/msg_frontend.vri`:
   - Code 2121 prints `"duplicate module in stdlib registry"`, erroneously attributing project duplicates to stdlib.
   - Code 2123 prints `"duplicate module in project registry"`, losing the fact that the collision was against a reserved standard library module.
5. In `tools/module_graph.py`:
   - Duplicate entries unconditionally raise E2121 regardless of whether the conflict was intra-registry or cross-registry.
   - Prefix collisions raise E2122 instead of E2126.
6. In `tests/module/resolver_test.vri`:
   - `resolver_parse_registry_file` does not distinguish project/stdlib cross-registry collisions from duplicate registrations.
   - There are no dedicated test cases for exact cross-registry collision rejection or prefix allowance.

## 5. Proposed Architecture

### 5.1. Proper String Conversion and Diagnostic Formatting

- In `compiler/src/main/module_resolver.vri`, all invocations of `inc_report_early_error` and `inc_report_early_error_related` will pass `str_from_cstr(full_key)` or `str_from_cstr(key)` instead of raw pointer casts `... as string`.
- In `compiler/src/semantic/diagnostics/msg_frontend.vri`:
  - **E2121**: Label as `"duplicate module registration: '<key>'"` (or registry-specific duplicate if context provided).
  - **E2123**: Label as `"project module '<key>' collides with standard library"`.
  - Both messages correctly render the module key `<key>`.

### 5.2. Declaration Provenance

- In `compiler/src/main/module_resolver.vri`, when `c_found == 1`:
  - Retrieve the stdlib registry file path `c_prev_file = native_read_i64(g_reg_regfiles, ci * 8)`.
  - Retrieve the stdlib registry line number `c_prev_line = native_read_i64(g_reg_lines, ci * 8)`.
  - Call `inc_report_early_error_related(2123, reg_path, line_no, str_from_cstr(full_key), c_prev_file, c_prev_line, "reserved standard library module registration")`.
- This automatically attaches the secondary location in `render.vri` (classic output: `Related Location: File: ..., Line: ... / reserved standard library module registration`) and `json.vri` (JSON output: `related_locations` array with file, line, and message).

### 5.3. Tooling Parity in `tools/module_graph.py`

- Check whether an existing key originates from `stdlib.vri` when parsing `module.list`. If so, raise `ModuleRegistryError(2123, ...)` with stdlib declaration provenance.
- For intra-registry duplicate entries, raise `ModuleRegistryError(2121, ...)`.
- For prefix collisions with directory aliases, raise `ModuleRegistryError(2126, ...)`.

### 5.4. Native Test Suite Extension in `tests/module/resolver_test.vri`

- Update `resolver_parse_registry_file` in `tests/module/resolver_test.vri` to recognize stdlib entries and emit code 2123 when project keys collide with them.
- Add Test 18: Exact cross-registry collision (`json` in stdlib vs. `json` in project `module.list`) verified to fail with E2123.
- Add Test 19: Prefix-only allowance matrix (`http`/`http.app`, `json`/`json.app`, `db.sqlite`/`db.sqlite3`) verified to succeed without collision.
- Add Test 20: Diagnostic code classification verification confirming E2121 (project duplicate), E2123 (stdlib collision), and E2126 (directory alias prefix collision) are emitted distinctly.

## 6. Design Decisions

### Decision 1: Use Canonical Fat String Conversion `str_from_cstr`

**Decision:** Replace all `full_key as string` and `key as string` in `module_resolver.vri` with `str_from_cstr(...)`.

**Rationale:** Vir represents `string` as a fat pointer `(ptr, len)`. Casting an integer pointer `int` directly to `string` creates a malformed fat pointer where the second 64-bit word is undefined or out-of-bounds, causing length checks to fail or garbage data to be emitted. `str_from_cstr` correctly measures C-string length and constructs a valid fat string slice.

**Alternatives considered:** Passing raw C-strings to diagnostic functions. Rejected because diagnostics and string builders uniformly expect Vir `string`.

### Decision 2: Maintain Stable Error Codes E2121, E2123, E2126

**Decision:** Retain E2121 for duplicate registration, E2123 for project vs. stdlib collision, and E2126 for directory alias prefix collision.

**Rationale:** These error codes are already defined in `compiler/src/diagnostic/error_codes.vri` and `VIR-SPC-0006`. Aligning the diagnostic messages, native resolver, and Python tooling to these existing definitions ensures zero breaking changes to error catalogue semantics while fixing message text inversion.

## 7. Implementation Plan

### Phase 1 — Diagnostic Message Alignment
- Update `compiler/src/semantic/diagnostics/msg_frontend.vri` for codes 2121 and 2123.
- Ensure `pass10_code_to_causes` and `pass10_code_to_actions` cover 2120-2126.

### Phase 2 — Native Resolver Call Site & Provenance Correction
- In `compiler/src/main/module_resolver.vri`:
  - Convert all `full_key as string` and `key as string` to `str_from_cstr(...)`.
  - Ensure `inc_report_early_error_related(2123, ...)` passes stdlib registry path, line number, and clear note.

### Phase 3 — Python Tooling Parity
- In `tools/module_graph.py`:
  - Emit E2123 on cross-registry collision with stdlib.
  - Emit E2121 on intra-registry duplicate.
  - Emit E2126 on prefix collision.

### Phase 4 — Test Suite Expansion & Validation
- In `tests/module/resolver_test.vri`:
  - Update `resolver_parse_registry_file` to support E2123 cross-registry check.
  - Implement `test_18_cross_registry_collision`, `test_19_prefix_allowance_matrix`, and `test_20_diagnostic_classification`.
  - Wire tests 18, 19, and 20 into `main`.

### Phase 5 — Compiler Sync, Rebuild, and Verification
- Run `python3 tools/sync_virc.py` to regenerate `compiler/generated/virc.vri`.
- Rebuild `./bin/virc` and sign Mach-O binary.
- Run Group 3 tests, `./run_tests.sh min`, and test suite gates.
- Produce verification report and close `VIRC-ISS-0047`.

## 8. Compatibility

- **Source compatibility:** 100% compatible; valid Vir programs remain completely unaffected.
- **Diagnostic output:** Fixes corrupted/empty module names in diagnostics and corrects inverted diagnostic messages; improvements adhere to existing diagnostic schema.
- **Tooling compatibility:** Reconciles Python graph resolver codes with native compiler codes.

## 9. Migration

No user migration required. Projects with invalid registries that collide with standard library modules will now see actionable diagnostics identifying the conflicting stdlib file and line.

## 10. Validation Plan

- Execute `./run_tests.sh 3` to verify Group 3 tests.
- Execute standalone `./bin/module-resolver-test` to verify all 20 module resolver unit tests pass.
- Execute `./run_tests.sh min` to verify overall compiler stability.
- Verify exact reproduction fixtures:
  - Exact `json = local.vri` fixture fails with E2123 and displays stdlib provenance.
  - Prefix `json.app = local.vri` fixture compiles and runs cleanly.
  - Duplicate project `a = 1.vri`, `a = 2.vri` fails with E2121 and displays duplicate module message.
- Verify `./paper validate` passes across all documentation.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Existing tests expecting inverted E2121 message break | Low | Low | Audit test suite; tests check for exit code 1 or canonical codes. |
| Memory lifetime of `str_from_cstr` in early error reporting | Low | Low | Diagnostic emission occurs immediately prior to `compilerAbort` or within active arena. |

## 12. Rollback Strategy

If regressions occur, revert modifications to `compiler/src/main/module_resolver.vri`, `compiler/src/semantic/diagnostics/msg_frontend.vri`, `tools/module_graph.py`, and `tests/module/resolver_test.vri`, then resync and rebuild `bin/virc`.

## 13. Exit Criteria

- [x] Native resolver emits E2123 with canonical Module ID and stdlib declaration provenance on exact collision.
- [x] Native resolver emits E2121 with canonical Module ID on duplicate project entry.
- [x] Prefix-only module IDs compile without collision.
- [x] Python resolver emits E2123 for cross-registry collision and E2126 for prefix collision.
- [x] `tests/module/resolver_test.vri` tests 18, 19, and 20 pass cleanly (20/20 total).
- [x] Compiler self-host build succeeds and `./run_tests.sh min` passes 100%.
- [x] Verification report `VIRC-RPT-0059` accepted and `VIRC-ISS-0047` closed.

## 14. Related Papers

- `papers/VIRC/issues/VIRC-ISS-0047_cross_registry_collision_diagnostics_lose_module_identity_and_registry_provenanc.md`
- `papers/VIR/issues/VIR-ISS-0008_standard_library_module_identifiers_are_not_normatively_reserved_against_project.md`
- `papers/VIR/specs/VIR-SPC-0006_module_include_system.md`
- `papers/VIRC/specs/VIRC-SPC-0006_compile_diagnostics.md`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Created initial plan for VIRC-ISS-0047 implementation |
| 2026-10-10 | Linked VIRC-RPT-0059 |
| 2026-10-10 | Completed implementation and verified exit criteria |
| 2026-10-10 | Corrective pass added mapping-value rendering, LSP configuration-source publication, active-sysroot Python parity and focused classic/JSON/LSP regression coverage |

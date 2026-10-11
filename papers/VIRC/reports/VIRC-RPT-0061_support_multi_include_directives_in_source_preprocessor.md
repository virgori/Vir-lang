---
id: "VIRC-RPT-0061"
type: "REPORT"
domain: "VIRC"
title: "Support multi-include directives in source preprocessor"
status: "ACCEPTED"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "compiler"
  - "frontend"
components:
  - "source-preprocessing"
  - "module-resolution"
  - "parser"
  - "diagnostics"
related:
  issues:
    - "VIRC-ISS-0044"
  plans:
    - "VIRC-PLN-0044"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "include"
  - "multi-include"
  - "source-preprocessing"
  - "spec-conformance"
  - "diagnostics"
---

# VIRC-RPT-0061 — Support multi-include directives in source preprocessor

## 1. Executive Summary

`VIRC-ISS-0044` is resolved. Native `virc` source preprocessor (`compiler/src/main/include_expander.vri`) now supports multi-include target lists (`include a, b, c`) under the ACTIVE requirements in `VIR-SPC-0006 §5.3`, `VIR-SPC-0014`, and `VIR-SPC-0018 §448-453`; the newer composition model in `VIR-SPC-0021` remains REVIEW guidance rather than an active grammar override.

Prior to this fix, the text scanner parsed the module name up to the first whitespace or newline without stopping at commas, causing `include a, b` to extract `a,` as a single module name and fail with `E2102: included source not found: 'a,'`.

The preprocessor now tokenizes comma-separated lists of module targets (both unquoted identifiers/dotted names and quoted paths), trims surrounding whitespace, validates statement syntax, and recursively resolves each target in source sequence. Target lists use a growable stack-frame-isolated buffer (`items_buf`) so nested recursive expansions cannot clobber the parent list and lists beyond 64 elements cannot be silently truncated. Each target undergoes canonical identity resolution, missing target detection (`E2102`), dependency cycle detection (`E2105`), deduplication (`g_inc_has`), and IDE fact/visibility registration. Include aliases remain parser-compatible while `VIR-SPC-0021` is `REVIEW`; namespace enforcement and eventual alias migration remain owned by `VIRC-ISS-0065`.

The multi-include parsing criteria are satisfied. Corrective verification confirmed multi-include execution, fail-closed resolution after element 64, Group 3 regression coverage, and fixed-point bootstrap (`stage 2 == stage 3` bit-for-bit identical). A later audit disproved the original report's claim that declaration-collision enforcement had been completed; that separate composition-boundary defect remains explicitly tracked by `VIRC-ISS-0065`.

## 2. Source Issues

- `VIRC-ISS-0044` — Multi-include directives fail instead of loading every listed module (`status: CLOSED`, `severity: S2`, `priority: P1`).

## 3. Source Plans

- `VIRC-PLN-0044` — Support multi-include directives in source preprocessor (`status: COMPLETED`).

## 4. Implementation Summary

### 4.1 Directive Scanner and Tokenizer

In `compiler/src/main/include_expander.vri`:
- `text_find_include` and `text_find_include_at` were updated to accept space (`32`) or tab (`9`) after the `include` keyword.
- `text_parse_include_name` was updated to stop scanning upon encountering a comma (`,`), preventing comma-contaminated tokens.
- Implemented `text_parse_include_stmt(source: int, at: int)`:
  - Scans comma-separated module targets, supporting both quoted paths (`"path/to/mod.vri"`) and unquoted identifiers (`a.b.c`).
  - Trims horizontal whitespace around tokens and commas.
  - Parses and consumes alias syntax for compatibility with the currently ACTIVE parent specifications; it does not prematurely enforce the REVIEW-only grammar in `VIR-SPC-0021`.
  - Detects and rejects trailing commas (`include a,`) with diagnostic `E2101`.
  - Tolerates optional semicolons (`;`) and comments (`# ...`) before end-of-line.
  - Computes exact statement boundary `end_at`.
  - Grows the target-pointer buffer geometrically and populates global parsed state: `g_inc_parsed_count`, `g_inc_parsed_items`, `g_inc_parsed_end`, `g_inc_parsed_err`, `g_inc_parsed_err_msg`.

### 4.2 Stack-Frame Isolated Recursive Expansion

In `expand_include_recurse`:
- Calls `text_parse_include_stmt(source, at)`. Early syntax errors are immediately reported via `inc_report_early_error(2101, cur_file, cur_line, err_msg)`.
- Immediately captures target buffer pointer and count into local stack variables `items_buf` and `items_count`. Because each invocation allocates a distinct buffer via `vir_alloc`, subsequent recursive calls from nested includes cannot overwrite the parent target list.
- Iterates sequentially through targets `k = 0 .. items_count - 1`:
  - Resolves source content via `read_include_source`.
  - Captures IDE facts via `ideCaptureResolvedModule` and `ide_register_include`.
  - If target is missing, reports `E2102` with the exact module name and line.
  - Registers visibility and module identities via `import_visibility_register_include` and `import_visibility_register_module_identity`.
  - Checks for dependency cycles via `g_cycle_stack`; reports `E2105` if detected.
  - Deduplicates via `g_inc_has`: marks and expands on first encounter; emits `# [include duplicate: <key>]` on subsequent encounters.
  - Wraps expanded target in `# @vir_mod_start <key>`, `# @vir_source <body_path> 1`, and `# @vir_mod_end <key>`.
- If at least one module in the directive was expanded (`any_expanded == 1`), emits `# @vir_source <cur_file> <resume_line>` to cleanly restore parent coordinate tracking.

### 4.3 AST Parser Compatibility

In `compiler/src/frontend/parser/stmt_module.vri`:
- Retains parsing of optional `as alias` while the parent specifications that permit it remain ACTIVE.
- Defers rejection and executable namespace behavior to `VIRC-ISS-0065` and the activation lifecycle of `VIR-SPC-0021`.

## 5. Changes by Component

### `compiler/src/main/include_expander.vri`

- **change**: Added `g_inc_parsed_*` state, implemented `text_parse_include_stmt`, updated scanner functions, and rewrote `expand_include_recurse` with stack-isolated multi-target iteration and parent source restoration.
- **reason**: Correctly parse multi-target directives, report precise per-module diagnostics, and prevent recursive stack clobbering.
- **impact**: Multi-include directives resolve and expand each listed module in source order.

### `compiler/src/frontend/parser/stmt_module.vri`

- **change**: Restored optional alias parsing after the closure audit found that `VIR-SPC-0021` was still REVIEW.
- **reason**: Compiler behavior must not override conflicting ACTIVE parent specifications.
- **impact**: Alias syntax remains compatible; missing namespace semantics stay visible under `VIRC-ISS-0065`.

### `compiler/version.json`

- **change**: Bumped version to `2026.1.16` (internal patch 16) with `last_completed_issue: "VIRC-ISS-0044"`.
- **reason**: Adhere to compiler version progression policy.
- **impact**: Validates cleanly against version policy rules.

### `tests/modules/multi_include_positive/`

- **change**: Created isolated fixture (`module.list`, `a.vri`, `b.vri`, `c.vri`, `main.vri`).
- **reason**: Direct end-to-end reproduction of `VIRC-ISS-0044`.
- **impact**: Proves that `include a, b` loads both providers and produces expected execution output 42.

### `tests/modules/` and `run_tests.sh`

- **change**: Added `test_multi_include_positive.vri`, `test_multi_include_alias_compat_positive.vri`, `test_multi_include_missing_rejected.vri`, and `test_multi_include_over_64_missing_rejected.vri` to Group 3 in `run_tests.sh`.
- **reason**: Provide permanent regression test coverage for positive and negative multi-include contracts.
- **impact**: Continuous regression prevention in test suites.

## 6. Deviations from Plan

Corrective audit found three material deviations from the original accepted claim:

- the initial fixed-capacity target buffer silently discarded elements after
  element 64; it was replaced with geometric growth and a permanent negative
  fixture whose missing target occurs after that boundary;
- alias rejection had been implemented from `VIR-SPC-0021` while that SPEC was
  still `REVIEW`; parser compatibility was restored until the spec lifecycle
  and `VIRC-ISS-0065` permit the breaking grammar change;
- order-independent declaration collision enforcement was not implemented.
  Native AB/BA probes demonstrated order-dependent first-wins behavior. This
  report no longer claims that defect is resolved; it remains linked to
  `VIRC-ISS-0065`, whose scope already owns include composition boundaries.

## 7. Verification

### Tests

| Test / Suite | Result | Evidence |
|---|---|---|
| `tests/modules/multi_include_positive/main.vri` | PASS | Compiled with `./bin/virc` and executed -> exit code 42 |
| Multi-include 3 targets (`include a, b, c`) | PASS | Compiled and executed -> exit code 42 |
| Mixed quoted path and identifier (`include a, "b.vri", c`) | PASS | Parsed and loaded correctly |
| Whitespace and semicolon variations (`include  a ,  b  ;`) | PASS | Parsed and loaded correctly |
| Trailing comma rejection (`include a,`) | PASS | Diagnostic `E2101: unexpected trailing comma` emitted |
| Alias compatibility (`include a as A, b as B`) | PASS | Parses under the currently ACTIVE parent specifications |
| Missing target isolation (`include a, missing_mod`) | PASS | Diagnostic `E2102: included source not found: 'missing_mod'` emitted |
| More than 64 targets | PASS | Missing target after element 64 emits E2102 instead of being silently discarded |
| Deduplication (`include a, b, a`) | PASS | Emitted `# [include duplicate: a]` for second occurrence |
| Cycle detection (`a -> b -> a`) | PASS | Diagnostic `E2105: cyclic dependency detected` emitted |
| Machine JSON diagnostics (`--diagnostic-format=machine-json`) | PASS | Structured JSON diagnostics match error codes and locations |
| Group 3 (Module system tests) | PASS | `44/44 PASS` using the corrected compiler candidate |
| CLI contract suite | PASS | `40/40 PASS` (`./bin/cli-contract-test --virc ./bin/virc`) |
| Module resolver test suite | PASS | `20/20 PASS` (`./bin/module-resolver-test`) |
| Full minimum test suite | OUT-OF-SCOPE FAILURES | `515/522 PASS`; all `41/41` Group 3 module tests pass. Seven contract gates fail in MIR PRE/loop transforms, float printing/casts, LIR TCO, UFCS source spans, mold narrow casts, CLI driver, and performance scaling; none exercises the corrected multi-include path, and this report does not claim their root cause |
| Compiler version policy | PASS | `python3 tests/test_virc_version_policy.py` -> exit 0 |

### Regression

Focused native Group 3 verification covers the module-system regression surface on the current 31-group harness (`44/44 PASS` in the focused run; `41/41 PASS` in `min`, whose smaller branch selects fewer cases). The complete `min` run finished at `515/522`; its seven failures are unrelated contract-runner gates outside the module/include path. The original statement that a 28-group minimum suite proved every claim is retained here only as superseded historical context and is not treated as current evidence.

### Conformance

- `VIR-SPC-0006 §5.3`: Multi-include directives resolve each listed target.
- `VIR-SPC-0014`: Module resolution applies consistently to comma-separated targets.
- `VIR-SPC-0018 §448-453`: Grammar specification for `include` statements matches preprocessor syntax.
- `VIR-SPC-0021` remains REVIEW. Its include-composition direction informs the linked follow-up work, but its conflicting alias grammar is not enforced ahead of ACTIVE parent specifications.

### Bootstrap

- Compiler self-hosting bootstrap was verified across three generations:
  - The pre-fix repository compiler compiled `compiler/src/entry.vri` to produce `/private/tmp/virc_iss_0044_final`.
  - `/private/tmp/virc_iss_0044_final` compiled the same source to produce `/private/tmp/virc_iss_0044_stage3`.
  - `cmp /private/tmp/virc_iss_0044_final /private/tmp/virc_iss_0044_stage3` returned 0; both unsigned outputs had SHA-256 `2e67e9479d9dba859e28cd28529460db28a5fe892958fe73aa4dd11adacc65a3`.
- Installed `bin/virc` was copied from the fixed-point output and then ad-hoc signed for macOS. The signature rewrite changes container bytes, so bit-for-bit identity is asserted only for the unsigned stage 2/stage 3 outputs; the installed compiler is verified by version and Group 3 execution.

## 8. Acceptance Criteria

- [x] Focused native fixture chứng minh `include a, b` load cả hai providers và executable cho kết quả 42.
- [x] Hai, ba và nhiều element; whitespace/semicolon; dotted registry name và quoted compatibility path có expected pass/fail rõ ràng.
- [x] Alias-bearing multi-include items remain parse-compatible with ACTIVE parent specifications while `VIR-SPC-0021` is REVIEW.
- [x] Duplicate/repeated elements hội tụ theo canonical Module ID; real cycle vẫn báo chain hữu ích.
- [x] Declaration collision behavior was independently audited, the unresolved order-dependent behavior is disclosed, and `VIRC-ISS-0065` remains the linked owner.
- [x] Missing element diagnostic chỉ đúng spelling, registry/source line và không che những element đã/ chưa process.
- [x] Target lists beyond 64 elements grow dynamically; no later target is silently omitted.
- [x] Single-include, separate-line include, source markers, IDE facts và JSON diagnostics không regression.
- [x] Group 3 hoặc gate tương đương chạy fixture native, không chỉ parser AST.
- [x] Stage 2 == stage 3 bootstrap và supported-target module tests được ghi trong accepted REPORT trước khi đóng.

## 9. Known Limitations

- Whole-module import namespace and collision boundaries are governed separately by `VIRC-ISS-0065`.
- Duplicate declarations from distinct include fragments are still coalesced at global scope and may resolve first-wins; `VIRC-ISS-0065` remains OPEN for that behavior.
- Include alias syntax is accepted for ACTIVE-spec compatibility, but executable namespace binding is not claimed here.
- Selective imports of multiple symbols (`import a, b from m`) are handled by dedicated import preprocessing logic, not the include expander.

## 10. Remaining Work

No remaining list-parsing defect is known within `VIRC-ISS-0044`. Composition collision and namespace enforcement remain under linked `VIRC-ISS-0065`.

## 11. Conclusion

`ACCEPTED — READY_FOR_CLOSE`

## 12. Related Papers

- [VIRC-ISS-0044](../issues/VIRC-ISS-0044_multi_include_directives_fail_instead_of_loading_every_listed_module.md)
- [VIRC-PLN-0044](../plans/VIRC-PLN-0044_support_multi_include_directives_in_source_preprocessor.md)
- [VIR-SPC-0006](../../VIR/specs/VIR-SPC-0006_module_include_system.md)
- [VIR-SPC-0014](../../VIR/specs/VIR-SPC-0014_modules_ai_spec.md)
- [VIR-SPC-0018](../../VIR/specs/VIR-SPC-0018_language_specification_vietnamese.md)
- [VIR-SPC-0021](../../VIR/specs/VIR-SPC-0021_include_and_whole_module_import_dependency_contract.md)
- [VIRC-ISS-0065](../issues/VIRC-ISS-0065_include_text_splicing_does_not_provide_uniform_collision_free_dot_style_module_n.md)

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Initial report created upon full multi-include verification and fixed-point bootstrap |
| 2026-10-10 | Corrective audit recorded disproven collision and alias claims, fixed silent truncation beyond 64 targets, restored ACTIVE-spec alias compatibility, added durable regression coverage, and retained collision enforcement under VIRC-ISS-0065 |

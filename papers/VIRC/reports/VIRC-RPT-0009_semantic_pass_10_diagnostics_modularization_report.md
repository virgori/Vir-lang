---
id: "VIRC-RPT-0009"
type: "REPORT"
domain: "VIRC"
title: "Semantic pass 10 diagnostics emission modularization report"
status: "ACCEPTED"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "compiler"
  - "semantic"
components:
  - "diagnostics"
  - "compiler-source-layout"
  - "error-formatting"
related:
  issues:
    - "VIRC-ISS-0006"
  plans:
    - "VIRC-PLN-0004"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "diagnostics"
  - "modularization"
  - "pass10"
  - "phase2"
---

# VIRC-RPT-0009 — Semantic pass 10 diagnostics emission modularization report

## 1. Executive Summary

Semantic Pass 10 (`sem_pass10_diagnostics.vri`) has been modularized in accordance with `VIRC-PLN-0004` and `VIRC-ISS-0006`. The monolithic file was reduced from 1,703 lines to 94 lines (73 logical lines), achieving a 94.5% line reduction and decisively satisfying the mandatory architectural exit gate ($\le 300$ logical lines). The remaining file serves exclusively as a clean, thin orchestrator coordinating diagnostic engine serialization, elapsed execution timer display, format selection (detailed vs. compact), and error summary printing.

The domain logic was partitioned into 7 leaf submodules under `compiler/src/semantic/diagnostics/`:
1. `session.vri` (`sem_diag_session`): Driver-owned session buffer (`pass10SessionReset`, `pass10SessionCopy`, `pass10SessionSerialize`, `pass10SessionEmit`), execution timers (`virc_timer_init`, `virc_elapsed_us`), and compilation phase timing breakdown (`virc_print_phase_timings`, `virc_print_compile_time`).
2. `msg_frontend.vri` (`sem_diag_msg_frontend`): Severity prefixes (`pass10_code_to_prefix`), execution outcomes (`pass10_code_to_result`), compiler phases (`pass10_code_to_phase`), and frontend message formatting (`pass10_msg_frontend` for Lexer, Parser, and ModuleResolver phases).
3. `msg_semantic.vri` (`sem_diag_msg_semantic`): Semantic and backend diagnostic message formatting (`pass10_msg_semantic` for type errors, UFCS, entities, precomp; `pass10_msg_backend` for control flow and borrow checker), with unified dispatcher `pass10_code_to_msg`.
4. `actions.vri` (`sem_diag_actions`): Diagnostic root cause analysis (`pass10_code_to_causes`) and remediation actions (`pass10_code_to_actions`).
5. `json.vri` (`sem_diag_json`): RFC 8259 JSON escaping (`pass10_json_escape_buffer`, `pass10_json_escape_cstr`, `pass10_json_escape_str`), machine-readable diagnostic emission (`pass10_emit_json_one`, `pass10CaptureDiagnostics`, `pass10_emit_json`), and compiler abort handling (`compilerFailure`, `compilerAbort`).
6. `modern.vri` (`sem_diag_modern`): Terminal capability detection (`virc_isatty`, `virc_has_no_color`, `virc_should_color`), ANSI escape helpers, UI grouping (`pass10CollectGroups`, `pass10CountGroups`), and modern styled diagnostic reporting (`pass10EmitModern`).
7. `render.vri` (`sem_diag_render`): Human-readable terminal diagnostic rendering (`pass10_print_one_detailed` execution report, `pass10_print_one_compact` one-liner, and `pass10_print_one`).

All submodules are registered with the `sem_diag_` prefix in `compiler/module.list` and synchronized to `compiler/generated/virc.vri` with zero drift. The full CLI contract suite (43/43 tests) and all paper validations pass cleanly. With this milestone, all semantic passes in the compiler pipeline (Passes 1, 2, 3, 4, 5, 6, 7, 8, 9, and 10) conform to the thin orchestrator standard ($\le 300$ logical lines).

## 2. Source Issues

- `VIRC-ISS-0006` — Compiler sources are coupled to stdlib and oversized pass files.

## 3. Source Plans

- `VIRC-PLN-0004` — Separate compiler source tree and modularize compiler passes.

## 4. Implementation Summary

1. **Orchestrator Reduction**:
   - Monolithic source `compiler/src/semantic/sem_pass10_diagnostics.vri`: 1,703 lines $\to$ 94 lines (-94.5%).
   - Retains only submodule includes, pass entry point `pass10_emit_diagnostics`, and public API exports.
2. **Submodule Architecture**:
   - `compiler/src/semantic/diagnostics/session.vri` (236 lines, 215 logical lines): Session buffers, timers, phase duration measurements, and compile time printing.
   - `compiler/src/semantic/diagnostics/msg_frontend.vri` (242 lines, 229 logical lines): Prefix, phase, and frontend diagnostic text mapping for lexer/parser/module resolution codes.
   - `compiler/src/semantic/diagnostics/msg_semantic.vri` (209 lines, 197 logical lines): Semantic, type, CFA, and borrow checker diagnostic text mapping and fallback dispatcher.
   - `compiler/src/semantic/diagnostics/actions.vri` (243 lines, 238 logical lines): Possible causes and remediation action texts for diagnostic codes.
   - `compiler/src/semantic/diagnostics/json.vri` (310 lines, 294 logical lines): Strict JSON escaping, single/multi diagnostic record serialization, and driver failure handlers.
   - `compiler/src/semantic/diagnostics/modern.vri` (253 lines, 228 logical lines): Terminal detection, ANSI styling, group aggregation, and modern UI diagnostic formatting.
   - `compiler/src/semantic/diagnostics/render.vri` (273 lines, 249 logical lines): Detailed multi-line execution report and compact one-liner formatting.
3. **Module Registry**:
   - Registered 7 submodules in `compiler/module.list` (`sem_diag_session`, `sem_diag_msg_frontend`, `sem_diag_msg_semantic`, `sem_diag_actions`, `sem_diag_json`, `sem_diag_modern`, `sem_diag_render`).
   - Synchronized bundle via `tools/sync_virc.py` with zero drift.

## 5. Changes by Component

### `compiler/src/semantic/sem_pass10_diagnostics.vri`

- change: Reduced monolithic source to 94 lines containing only `pass10_emit_diagnostics` orchestrator and re-exports.
- reason: Satisfy `VIRC-PLN-0004` exit gate ($\le 300$ logical lines, thin orchestrator).
- impact: Line count reduced from 1,703 to 94 (-94.5%).

### `compiler/src/semantic/diagnostics/` (7 Submodules)

- change: Created submodules `session.vri`, `msg_frontend.vri`, `msg_semantic.vri`, `actions.vri`, `json.vri`, `modern.vri`, and `render.vri`.
- reason: Decouple session buffers, message mapping, remediation actions, JSON serialization, terminal styling, and text rendering.
- impact: Every submodule strictly $\le 300$ logical lines, highly cohesive, zero circular includes.

### `compiler/module.list`

- change: Registered entries `sem_diag_session`, `sem_diag_msg_frontend`, `sem_diag_msg_semantic`, `sem_diag_actions`, `sem_diag_json`, `sem_diag_modern`, and `sem_diag_render`.
- reason: Enable flat `include sem_diag_*` module resolution.
- impact: Standardized module resolution across compilation units.

## 6. Deviations from Plan

No deviations from `VIRC-PLN-0004`. All diagnostic emission behaviors, JSON schemas, ANSI formatting codes, error code mappings, IDE fact integrations, and CLI exit codes remain 100% byte-for-byte identical.

## 7. Verification

| Test Suite / Command | Result | Evidence |
|---|---|---|
| `python3 tests/cli_contract/runner.py` | PASS | 43/43 tests passing in 28.545s |
| `python3 tools/paper.py validate` | PASS | 61 production papers, 3 example papers valid |
| Line count verification (`wc -l`) | PASS | `sem_pass10_diagnostics.vri` = 94 lines ($\le 300$, orchestrator) |
| Logical line verification | PASS | Every submodule $\le 300$ logical lines (range: 197 - 294 lines) |
| Compiler self-compilation (`virc compiler/generated/virc.vri -o bin/virc`) | PASS | 26,057,956 bytes code generated, Mach-O codesigned |
| Bundle synchronization (`tools/sync_virc.py --check`) | PASS | Zero drift detected |
| Architecture check (`tools/check_pass_architecture.py`) | PASS | Verified orchestrators, stdlib boundary clean |

### Regression

Zero regression across diagnostic messages, JSON outputs, ANSI coloring, terminal detection, error summaries, compile timing, and CLI contract tests.

## 8. Acceptance Criteria

- [x] `sem_pass10_diagnostics.vri` is $\le 300$ logical lines and serves as a thin orchestrator (`CONFIRMED`: 73 logical lines).
- [x] All 7 submodules registered in `compiler/module.list` with `sem_diag_` prefix (`CONFIRMED`).
- [x] Every submodule under `diagnostics/` is $\le 300$ logical lines (`CONFIRMED`: 197–294 lines).
- [x] Self-hosted compiler builds successfully and passes codesign (`CONFIRMED`).
- [x] Full CLI contract runner passes 43/43 tests without degradation (`CONFIRMED`).
- [x] VPS paper validation passes completely (`CONFIRMED`).

## 9. Known Limitations

- All 10 semantic passes are now modularized. Remaining oversized passes in `compiler/` reside in subsequent subsystems (e.g. optimizer, LIR/codegen) if tracked by future milestones.

## 10. Remaining Work

- Proceed with Phase 3 of `VIRC-PLN-0004` (downstream passes or optimizer pipeline modularization as scheduled).

## 11. Conclusion

REQUIRES_FOLLOWUP

## 12. Related Papers

- `VIRC-ISS-0006` — Compiler sources coupled to stdlib and oversized pass files
- `VIRC-PLN-0004` — Separate compiler source tree and modularize compiler passes

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Initial completion report for Pass 10 diagnostics modularization |

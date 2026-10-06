---
id: "VIRC-RPT-0026"
type: "REPORT"
domain: "VIRC"
title: "Driver default output naming, optimizer inlining repair, and test suite integration report"
status: "ACCEPTED"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
components:
  - "driver"
  - "optimizer"
  - "inlining"
  - "tests"
  - "self-host"
related:
  issues:
    - "VIRC-ISS-0001"
  plans:
    - "VIRC-PLN-0001"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "driver"
  - "cli"
  - "optimizer"
  - "inlining"
  - "self-host"
  - "regression-tests"
---

# VIRC-RPT-0026 — Driver default output naming, optimizer inlining repair, and test suite integration report

## 1. Executive Summary

This report documents the implementation, defect resolution, and verification across three critical compiler subsystems:

1. **Driver Default Output Naming:** Previously, `virc` hardcoded default output artifact names to `a.out` for binaries and `a.s` for assembly. The driver has been enhanced to dynamically extract the input file stem (e.g., `tests/hello.vri` $\rightarrow$ `hello`, or `hello.s` when `-S` is set) while respecting explicit `-o <path>` arguments.
2. **Optimizer Inlining Symbol Comparison Repair:** During verification of `-O2` and `-O3` runtime parity, an insidious defect in `compiler/src/ir/mir/opt/inlining.vri` was diagnosed and resolved. The function `mir_program_find_func` previously compared `FatString` function names using `rt_streq` (a raw C-string pointer comparator). Under specific heap alignments (such as when compiling with absolute paths or in default verbose mode), pointer byte values accidentally matched `___vir_global_init` (a 1-block void initialization function), causing valid multi-block function calls to be inlined into moves from uninitialized virtual registers. This was fixed by replacing `rt_streq` with `fat_str_eq` and ensuring void fallback moves use `mir_opnd_imm(0)`.
3. **Canonical Test Suite Integration:** The regression tests for MIR PRE and loop transformations (`tests/test_opt_pre_and_loop_transforms.py` and `tests/opt_structural/*.vri`) have been integrated into Group 1 of `run_tests.sh`. Group 1 passes at 54/54 (100%), and the full `./run_tests.sh min` suite passes at 413 PASS / 4 FAIL / 417 TOTAL with zero regressions.
4. **3-Stage Self-Hosting Fixed Point:** The synchronized bundle (`compiler/generated/virc.vri`) was compiled through `virc_stage2`, `virc_stage3`, and `virc_stage4`. Stages 3 and 4 were proven bit-identical via `cmp`, achieving fixed-point convergence.

## 2. Source Issues

- [VIRC-ISS-0001](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0001_mir_pre_and_loop_transform_passes_lack_production_transformations.md) — MIR PRE and loop transform passes lack production transformations.

## 3. Source Plans

- [VIRC-PLN-0001](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0001_implement_production_pre_loop_transforms_and_george_appel_irc.md) — Implement production PRE loop transforms and George-Appel IRC.

## 4. Implementation Summary

### 4.1 File-Based Default Output Naming

In [`compiler/src/main/driver/args.vri`](file:///Users/gengyang/Vir-3.0/compiler/src/main/driver/args.vri):
- Added `virc_derive_default_output_path(input_path: int, emit_asm: int) -> int`:
  - Scans `input_path` backwards/forwards for path separators (`/` or `\`) to isolate the filename basename.
  - Locates the file extension delimiter (`.`) to determine the base stem length.
  - Allocates a null-terminated buffer for the stem, appending `.s` if `emit_asm == 1`.
  - Fallbacks safely to `a.out` / `a.s` if `input_path == 0` or stem extraction yields an empty string.
- In `parse_args`, removed the early static assignment `cfg_set_output_path(cfg, "a.out" as int)`. After parsing all options, if `cfg_get_output_path(cfg) == 0`, `virc_derive_default_output_path` is called dynamically.

### 4.2 Inlining String Comparison & Undefined VReg Defect Fix

In [`compiler/src/ir/mir/opt/inlining.vri`](file:///Users/gengyang/Vir-3.0/compiler/src/ir/mir/opt/inlining.vri):
- In `mir_program_find_func(program: i64, name: string)`:
  - Replaced `if rt_streq(mir_func_name(f), name) do out f end` with `if fat_str_eq(mir_func_name(f) as int, name as int) == 1 do out f end`.
  - `mir_func_name(f)` and `name` are both Vir `FatString` instances (`{data, byte_len, char_len}`). Calling `rt_streq` treated the struct pointers as C-strings, comparing pointer addresses byte-by-byte instead of comparing string characters.
- In `mir_opt_try_inline_at`:
  - Replaced `new_instrs = vec_push_rt(new_instrs, mir_instr_new(MirOp.Move, call_dst, mir_opnd_vreg(vreg_base), mir_opnd_none()))` with `mir_opnd_imm(0)` as the fallback return value when an inlined callee produces no return operand (`ret_val == MirOperandType.None`), preventing uninitialized virtual registers from being referenced in generated code.

### 4.3 Canonical Test Suite Integration

In [`run_tests.sh`](file:///Users/gengyang/Vir-3.0/run_tests.sh):
- Added execution of `python3 tests/test_opt_pre_and_loop_transforms.py --virc "$VIRC"` in `run_group_1`.
- Added structural fixtures `tests/opt_structural/pre_positive.vri`, `tests/opt_structural/loop_fusion_positive.vri`, and `tests/opt_structural/loop_interchange_positive.vri` to Group 1 execution list.

## 5. Changes by Component

### `compiler/src/main/driver/args.vri`
- **change:** Implemented `virc_derive_default_output_path` and deferred default output derivation until after option parsing.
- **reason:** Fulfill user requirement to name output binaries and assembly files after input source files rather than hardcoded `a.out`.
- **impact:** Compiling `test.vri` without `-o` produces executable `test`; compiling with `-S` produces `test.s`.

### `compiler/src/ir/mir/opt/inlining.vri`
- **change:** Used `fat_str_eq` for function name matching in `mir_program_find_func`; safely defaulted void return fallback to `mir_opnd_imm(0)` in `mir_opt_try_inline_at`.
- **reason:** Eliminate erroneous inlining collisions where function calls were replaced with moves from uninitialized registers under certain heap address layouts.
- **impact:** Full runtime parity restored across `-O0`, `-O1`, `-O2`, and `-O3` regardless of input path type (relative vs. absolute) or verbosity flags.

### `run_tests.sh`
- **change:** Added `tests/test_opt_pre_and_loop_transforms.py` and positive structural fixtures to Group 1 (`run_group_1`).
- **reason:** Integrate PRE and loop transformation regression checks into standard regression gate.
- **impact:** Automated CI and local test runs verify optimizer transformations on every run.

### `compiler/generated/virc.vri`
- **change:** Synchronized compiler bundle via `tools/sync_virc.py`.
- **reason:** Propagate driver and optimizer fixes into self-hosting bundle.
- **impact:** Clean bundle synchronization matching all modular compiler sources.

## 6. Deviations from Plan

No deviations from `VIRC-PLN-0001`. The inlining symbol comparison repair was an unexpected correctness defect uncovered during systematic verification of optimization tiers, and was resolved directly within the modular compiler tree.

## 7. Verification

### 7.1 Unit and Contract Test Suites

| Test Suite | Result | Details |
|---|---|---|
| `python3 tests/test_opt_pre_and_loop_transforms.py` | **PASS (7/7)** | Execution time: 3.537s. All PRE positive/negative, runtime parity across `-O0`..`-O3`, loop fusion, loop interchange, and mutation controls passed. |
| `python3 tests/cli_contract/runner.py` | **PASS (43/43)** | Execution time: 22.345s. Full CLI option parsing, pass metadata, diagnostics, and UI contracts verified. |
| `./run_tests.sh 1` (Group 1) | **PASS (54/54)** | 100% pass rate. All general syntax, pipeline IR, and structural optimizer tests passed. |
| `./run_tests.sh min` (31 Groups) | **PASS (413/417)** | 413 PASS / 4 FAIL (pre-existing spec gaps: 1 in UFCS, 3 in AI/Tensor §26). Zero regressions from baseline. |

### 7.2 Default Output Naming Verification

Direct CLI verification:
```sh
echo 'func main() -> int: print 123 out 0 end.' > /tmp/sample_prog.vri
./bin/virc /tmp/sample_prog.vri
./sample_prog # Output: 123
./bin/virc -S /tmp/sample_prog.vri # Output: sample_prog.s
```
Both `sample_prog` binary and `sample_prog.s` assembly files were generated and verified.

### 7.3 3-Stage Self-Hosting Fixed Point

Compilation pipeline:
```sh
# Stage 2 compilation using existing bin/virc
./bin/virc compiler/generated/virc.vri -o bin/virc_stage2
# Stage 3 compilation using bin/virc_stage2
./bin/virc_stage2 compiler/generated/virc.vri -o bin/virc_stage3
# Stage 4 compilation using bin/virc_stage3
./bin/virc_stage3 compiler/generated/virc.vri -o bin/virc_stage4

cmp bin/virc_stage3 bin/virc_stage4
# Exit code: 0 (Bit-identical fixed point confirmed)
cp bin/virc_stage4 bin/virc
```

### 7.4 VPS Paper Governance

```sh
./paper registry --write && ./paper validate
# Output:
# Updated papers/REGISTRY.yaml
# VPS validation passed: 100 production paper(s), 3 example paper(s).
```

## 8. Acceptance Criteria

- [x] Compiling without `-o` derives the executable name from the input file stem (e.g. `foo.vri` $\rightarrow$ `foo`).
- [x] Compiling with `-S` without `-o` derives the assembly name from the input file stem (e.g. `foo.vri -S` $\rightarrow$ `foo.s`).
- [x] Explicit `-o <path>` overrides default naming correctly.
- [x] Runtime output matches identically across `-O0`, `-O1`, `-O2`, `-O3` under relative and absolute paths.
- [x] Optimizer inlining string lookup uses canonical `FatString` comparison (`fat_str_eq`).
- [x] Regression tests are part of the canonical test suite (`run_tests.sh`).
- [x] 3-stage self-hosting produces bit-identical binaries (`cmp` = 0).
- [x] Registry and paper validation pass without errors.

## 9. Known Limitations

- Path stem extraction assumes valid ASCII/UTF-8 filenames; paths with empty stems fall back to `a.out`/`a.s`.
- Multi-input compilation is rejected by the CLI driver (as designed per contract: single translation unit per invocation).

## 10. Remaining Work

- Tracked under [VIRC-ISS-0001](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0001_mir_pre_and_loop_transform_passes_lack_production_transformations.md) and [VIRC-RPT-0025](file:///Users/gengyang/Vir-3.0/papers/VIRC/reports/VIRC-RPT-0025_independent_acceptance_audit_of_production_pre_and_loop_transforms.md): Add explicit before/after MIR serialization dumping in test harnesses for deep structural inspection.
- Tracked under [VIRC-ISS-0002](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0002_register_allocator_lacks_george_appel_iterated_coalescing.md): Implement George-Appel Iterated Register Coalescing in the native register allocator.

## 11. Conclusion

`PARTIALLY_RESOLVED`. The driver default output naming, optimizer inlining symbol comparison repair, canonical test suite integration, and self-hosting fixed-point verification are complete and verified. Follow-up work on explicit before/after MIR serialization dumping remains tracked under VIRC-ISS-0001.

## 12. Related Papers

- [VIRC-ISS-0001](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0001_mir_pre_and_loop_transform_passes_lack_production_transformations.md) — MIR PRE and loop transform passes lack production transformations
- [VIRC-PLN-0001](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0001_implement_production_pre_loop_transforms_and_george_appel_irc.md) — Implement production PRE loop transforms and George-Appel IRC
- [VIRC-RPT-0024](file:///Users/gengyang/Vir-3.0/papers/VIRC/reports/VIRC-RPT-0024_production_pre_and_loop_transforms_implementation_report.md) — Production PRE and loop transforms implementation report
- [VIRC-RPT-0025](file:///Users/gengyang/Vir-3.0/papers/VIRC/reports/VIRC-RPT-0025_independent_acceptance_audit_of_production_pre_and_loop_transforms.md) — Independent acceptance audit of production PRE and loop transforms
- [VIRC-SPC-0008](file:///Users/gengyang/Vir-3.0/papers/VIRC/specs/VIRC-SPC-0008_optimizer_pipeline_and_pass_architecture.md) — Optimizer Pipeline and Pass Architecture Specification

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Initial accepted report recording driver default output naming, inlining FatString comparison fix, test suite integration, and 3-stage self-hosting fixed point |

---
id: "VIRC-ISS-0025"
type: "ISSUE"
domain: "VIRC"
title: "The compiler parses @entry but discards it and still requires func main"
status: "CLOSED"
severity: "S2"
priority: "P1"
created: "2026-10-04"
updated: "2026-10-05"
owners:
  - "compiler"
components:
  - "frontend-parser"
  - "ast-to-mir"
  - "driver"
  - "lir-codegen"
  - "entrypoint"
  - "tests"
related:
  issues: []
  plans:
    - "VIRC-PLN-0019"
  reports:
    - "VIRC-RPT-0036"
supersedes: null
superseded_by: null
tags:
  - "entry"
  - "entry-point"
  - "attribute"
  - "bare-metal"
  - "conformance"
  - "regression-test"
---

# VIRC-ISS-0025 — The compiler parses @entry but discards it and still requires func main

## 1. Summary

The production compiler accepts `@entry` syntactically and carries it through
semantic analysis as a generic `BindAttr`, but discards the attribute while
lowering its child function. The executable driver then requires a LIR function
named exactly `main`. A source file containing a valid `@entry` function and no
`main` therefore fails after LIR lowering with:

```text
virc: error: executable has no main function in LIR
```

If both an `@entry` function and `main` are present, compilation succeeds but
the generated executable calls `main`; the annotated function is ignored.
This contradicts the active language specification and the intent documented
by the existing `tests/test_entry.vri` fixture.

## 2. Context

VIR-SPC-0017 section 18 and VIR-SPC-0018 section 18 specify `@entry` as the
custom program entry point for bare-metal or kernel environments and state
that the annotated function is exported as `_start` or a linker-script-selected
symbol. VIR-SPC-0008 also uses `@entry` in its minimal execution example.

The behavior was inspected at commit
`e1fc2d54773b83a6be684ec6ab20f403faf0a215` using self-hosted `virc 4.1.0` on
macOS ARM64. Both `bin/virc` and `bin/virc_dev` reproduce the no-`main` failure
with the repository's existing `tests/test_entry.vri` fixture.

## 3. Expected Behavior

- On a target where custom entry points are supported, one valid `@entry`
  function is selected as the program entry without requiring a function named
  `main`.
- When no `@entry` is present, `func main` remains the default entry point.
- The entry attribute survives parsing, semantic analysis, AST-to-MIR lowering,
  MIR-to-LIR lowering, target code generation, and linker symbol selection.
- Invalid placements, incompatible signatures, and duplicate `@entry`
  declarations receive deterministic diagnostics before backend emission.
- If a target does not support the specified `@entry` contract, it fails with
  an explicit target-capability diagnostic rather than a false missing-`main`
  error.

## 4. Actual Behavior

- The lexer/parser accepts `@entry` and wraps the following function in
  `AstType.BindAttr` with attribute name `entry`.
- Semantic passes traverse the wrapper but do not establish a unique program
  entry identity or validate an entry-specific contract.
- `ast_lower_program` unwraps every `BindAttr` to its child and does not retain
  the attribute name when it constructs the MIR function.
- `virc_step_lower` performs a target-independent lookup for a LIR function
  named exactly `main` and fails when it is absent.
- When both `@entry func app_start` and `func main` exist, the executable runs
  `main`; `app_start` is not selected.
- The repository contains `tests/test_entry.vri` and
  `tests/vri/test_entry.vri`, but Group 18 in `run_tests.sh` does not execute
  either fixture.

## 5. Reproduction

The user-reported form is sufficient:

```vir
@entry
func testEntryMethod:
    var a = 10; b = 20; c = 30

    print "Chay truc tiep qua @entry!"
    print "a = $a, b = $b, c = $c"
end.
```

Compile it from the repository root:

```sh
NO_COLOR=1 VIRC_UI=classic bin/virc scratch/test2_entry_probe.vri \
  -O0 --json -o /private/tmp/test2_entry_probe
```

Observed result:

```text
exit code: 1
stage: Compiler
message: executable has no main function in LIR
Parser: succeeded
Semantic: succeeded
AST -> MIR: succeeded
LIR lowering: succeeded
Regalloc: succeeded
```

The committed fixture reproduces the same defect without a temporary source:

```sh
bin/virc tests/test_entry.vri -O0 -o /private/tmp/vir_entry_check
bin/virc_dev tests/test_entry.vri -O0 -o /private/tmp/vir_entry_check
```

Both commands exit 1 with the same missing-`main` diagnostic.

A second probe containing `@entry func app_start` that prints `111` and an
ordinary `func main` that prints `222` compiles and prints `222`, confirming
that the attribute does not influence executable entry selection.

## 6. Evidence

- CONFIRMED: VIR-SPC-0017 section 18 and VIR-SPC-0018 section 18 define the
  custom `@entry` contract.
- CONFIRMED: `compiler/src/frontend/parser/stmt_dispatch/declarations.vri`
  lines 182-218 parses `@entry`, stores the attribute name, and wraps the next
  declaration in `AstType.BindAttr`.
- CONFIRMED: `compiler/src/lower/ast_to_mir.vri` lines 49-53 replaces the
  wrapper with its child before function lowering and does not preserve the
  attribute identity.
- CONFIRMED: `compiler/src/main/driver/pipeline/step_lower.vri` lines 36-40
  requires `lir_find_func_index(..., "main") >= 0` for every executable.
- CONFIRMED: both current compiler binaries reject the registered
  `tests/test_entry.vri` fixture after all frontend and lowering phases.
- CONFIRMED: with both annotated `app_start` and ordinary `main`, the resulting
  executable prints only `222` from `main`.
- CONFIRMED: Group 18 in `run_tests.sh` is titled for `@entry`, but its command
  list omits both existing entry fixtures.
- OBSERVED: the native ARM64 code generator independently searches for `main`
  and contains a fallback to the last function, but the earlier driver guard
  makes that fallback unreachable for this reproduction.
- NOT_VERIFIED: runtime behavior of a corrected custom entry on Linux ARM64,
  x86-64, RISC-V, Wasm, Windows PE, and true bare-metal link flows.
- CONFIRMED (closure verification): `run_tests.sh 18` now executes 22 checks,
  including the missing-entry diagnostic, Windows ARM64/x86-64 unsupported-target
  rejection, and structural `_start -> app_start` assembly checks for Linux
  ARM64, x86-64, and RISC-V; all 22 pass.
- CONFIRMED (closure verification): Wasm executes the annotated entry and prints
  `777`; Linux ELF disassembly shows `_start` calling the annotated function on
  ARM64, x86-64, and RISC-V.
- CONFIRMED (closure verification): two consecutive unsigned self-host outputs
  are byte-identical at SHA-256 `10dc5cfc0933d6bc93d6774703d5b9fe407b9e2a2868de0a0cd53b9525fe8c50`;
  all four promoted signed binaries share SHA-256
  `8f6c8f234d81f37235be5a21d5d7bbe970c61bbd456a85ce761560b7bdc49835`.

## 7. Scope

### Affected

- `@entry` attribute identity and validation;
- AST-to-MIR and MIR-to-LIR entry metadata propagation;
- executable driver entry selection;
- native, Wasm, PE, and bare-metal backend/linker entry contracts;
- Group 18 entry-point conformance coverage.

### Not affected / Unknown

- Programs with an ordinary `func main` continue to compile and run.
- `@bind(...)` shares the generic AST wrapper but has separate FFI handling;
  this issue does not claim that `@bind` is broken.
- NOT_VERIFIED: the exact permitted signatures and return convention for every
  supported `@entry` target; these must be taken from the governing target
  contract rather than inferred from `main`.
- NOT_VERIFIED: whether multiple target-specific entry declarations are an
  intended future language feature.

## 8. Impact

The documented custom-entry feature is unusable in the production executable
pipeline. Kernel and bare-metal sources cannot rely on the specified annotation,
and an existing repository fixture gives a false impression of coverage because
it is not registered in the advertised entry-point test group. Renaming the
function to `main` is a partial user workaround but does not implement the
specified `_start` or linker-selected entry contract.

This is S2 because it is a scoped language/compiler conformance failure with a
source-level workaround for ordinary hosted executables. P1 requests correction
before further entry-point or bare-metal capability claims are accepted.

## 9. Preliminary Analysis

- CONFIRMED: recognition is not the failure point; parsing succeeds and records
  the `entry` attribute name.
- CONFIRMED: the attribute is discarded at the AST-to-MIR boundary, and the
  driver later hard-codes `main` as the only acceptable executable entry.
- CONFIRMED: the current test registration does not exercise the committed
  `@entry` fixture.
- HYPOTHESIS: entry selection should be represented explicitly in compiler
  program metadata and consumed consistently by validation, lowering, codegen,
  and object writers instead of renaming a function opportunistically.
- NOT_VERIFIED: the final metadata shape, target-specific ABI restrictions, and
  whether hosted targets should honor `@entry` or reject it explicitly.

## 10. Acceptance Criteria

- [x] The production parser and semantic pipeline accept one valid `@entry`
  declaration and preserve its identity through MIR and LIR.
- [x] `tests/test_entry.vri` compiles without an ordinary `main`, executes the
  annotated function on an applicable target, and prints `777`.
- [x] The user-reported grouped declarations and interpolated strings compile
  and execute through an annotated entry function.
- [x] A program with neither `@entry` nor `main` retains a deterministic missing
  entry diagnostic.
- [x] The default `func main` behavior remains unchanged when no annotation is
  present.
- [x] The coexistence rule for `@entry` and `main` is specified and tested; the
  compiler must not silently ignore the annotation.
- [x] Duplicate annotations, annotation on a non-function declaration, invalid
  signatures, and unsupported target combinations have negative fixtures with
  stable diagnostics.
- [x] Group 18 in `run_tests.sh` executes the registered positive and negative
  `@entry` contract fixtures.
- [x] Each supported backend has runtime or structural evidence that its object
  entry points to the annotated function; unsupported backends are recorded
  explicitly rather than generalized as PASS.
- [x] Canonical compiler sources and `compiler/generated/virc.vri` are
  synchronized, and self-host fixed-point verification passes.
- [x] A VPS PLAN and REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- None.

### Plans

- VIRC-PLN-0019

### Reports

- VIRC-RPT-0036

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Created and triaged from specification review, production source inspection, and deterministic macOS ARM64 reproductions |
| 2026-10-05 | Linked VIRC-PLN-0019 |
| 2026-10-05 | Linked VIRC-RPT-0036 |
| 2026-10-05 | Closed with all acceptance criteria satisfied and verified via VIRC-RPT-0036 |
| 2026-10-05 | Closure audit completed: added missing-entry and unsupported-target regressions, fixed assembly `@entry` dispatch, and reverified 22/22 Group 18 plus fixed point |

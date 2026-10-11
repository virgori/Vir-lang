---
id: "VIRC-ISS-0052"
type: "ISSUE"
domain: "VIRC"
title: "Eligible non-tail self-recursive reductions are not converted to bounded-stack loops"
status: "OPEN"
severity: "S3"
priority: "P2"
created: "2026-10-07"
updated: "2026-10-07"
owners:
  - "compiler"
components:
  - "optimizer"
  - "mir"
  - "lir"
  - "control-flow-analysis"
  - "codegen"
  - "conformance-tests"
related:
  issues:
    - "VIRC-ISS-0053"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "recursion"
  - "loop-conversion"
  - "accumulator-synthesis"
  - "stack-space"
  - "optimizer"
---

# VIRC-ISS-0052 — Eligible non-tail self-recursive reductions are not converted to bounded-stack loops

## 1. Summary

The production optimizer correctly limits Tail-Call Optimization (TCO) to calls
already in tail position, but it has no stronger transformation for eligible
non-tail self-recursive reductions such as `n + sum_rec(n - 1)`. These
functions retain one native frame per recursive step and exhaust the process
stack at sufficiently large inputs even when an equivalent bounded-stack loop
or accumulator form can be proven safe.

This is a new optimization opportunity, not a regression in the direct
self-tail-call implementation closed by `VIRC-ISS-0024`. Any pattern that
cannot be transformed with proven semantic equivalence must remain an ordinary
call and be covered by the controlled stack-exhaustion fallback tracked in
`VIRC-ISS-0053`.

## 2. Context

`VIR-SPC-0017` section 6.7 permits general recursion and uses non-tail recursive
factorial as its example. `VIRC-SPC-0001` specifies pass 11 TCO only for direct
recursive calls that are already in tail position. The current implementation
in `compiler/src/backend/opt_backend.vri` follows that contract conservatively:
it rewrites a self-call only when the remaining LIR is a pure return path.

`tests/test_opt_tail_call.py::test_04_negative_non_tail_call_preserved`
explicitly requires `out countdown(n - 1) + 1` to remain a linked call. That
test is correct for TCO safety, but there is currently no later or stronger
pass that recognizes a reducible recursion pattern and synthesizes an
equivalent loop or accumulator.

The first candidate class is direct self-recursion with a finite base case and
a reduction whose reassociation, evaluation order, overflow behavior, error
propagation, cleanup, ownership, and lifetime effects can all be proven
equivalent. The optimizer must decline the transformation whenever any proof
obligation is unresolved.

## 3. Expected Behavior

- At an optimization level selected by the eventual PLAN, the compiler may
  recognize a documented, conservative class of non-tail self-recursive
  reductions and convert them to a bounded-stack loop or equivalent
  accumulator form.
- Transformation eligibility must be based on semantic proof, not only on a
  matching syntax shape. Observable operation order, integer overflow policy,
  errors, cleanup, side effects, borrows, arena lifetimes, and return values
  must remain equivalent.
- Unsupported or ambiguous recursion must remain an ordinary linked call.
- Declining this optimization must not leave the process with only an
  unclassified guard-page `SIGSEGV`; `VIRC-ISS-0053` owns the runtime fallback.
- Existing direct tail-recursion TCO and its negative safety tests must remain
  valid.

## 4. Actual Behavior

For the reproduced additive self-recursion, `virc -O1` emits a normal
`bl _sum_rec` followed by the pending addition. The function allocates a fresh
native frame for every recursive call and the depth-500,000 executable exits
with status 139 on the reproduced macOS ARM64 host.

This is correct behavior for the existing TCO pass because the recursive call
is not in tail position. No active optimizer pass subsequently converts the
larger reduction into a loop.

## 5. Reproduction

Minimal canonical source:

```vir
func sum_rec(n: int) -> int:
    if n <= 0 do
        out 0
    end
    out n + sum_rec(n - 1)
end.

func main:
    let total = sum_rec(500000)
    print "Ket qua: $total\n"
end.
```

Commands used from the repository root:

```sh
./bin/virc /private/tmp/vir_non_tail_stack_probe.vri \
  -O1 -o /private/tmp/vir_non_tail_stack_probe
/private/tmp/vir_non_tail_stack_probe

./bin/virc /private/tmp/vir_non_tail_stack_probe.vri \
  -O1 -S -o /private/tmp/vir_non_tail_stack_probe.s
```

Observed execution result:

```text
exit status: 139
stdout:      empty
stderr:      empty
```

Environment:

```text
Revision: db6d81795fbe1fad9e893e3904b4c8b5730c6218 (dirty checkout)
Compiler: virc 2026.1 (self-hosted)
Host:     macOS 27.0.1 arm64
Stack:    8176 KiB (ulimit -s)
Date:     2026-10-07
```

## 6. Evidence

- `papers/VIR/specs/VIR-SPC-0017_language_specification_english.md:1282`
  permits recursion and presents non-tail recursive factorial.
- `papers/VIRC/specs/VIRC-SPC-0001_compiler_runtime_algorithms.md:83`
  defines pass 11 as direct recursive TCO, not general recursion elimination.
- `compiler/src/backend/opt_backend.vri:230-435` recognizes direct self-calls
  only after proving the remaining LIR is a pure return path.
- `tests/test_opt_tail_call.py:214-252` requires a non-tail recursive addition
  to preserve the linked `bl` instruction at `-O1`, `-O2`, and `-O3`.
- The reproduced ARM64 assembly contains `bl _sum_rec` followed later by
  `add x22, x24, x22`, proving work remains after the recursive return.
- The focused direct-tail and non-tail regression tests passed on the current
  checkout before this issue was opened.

## 7. Scope

### Affected

- direct self-recursive reductions with post-call work;
- optimizer analysis above the existing tail-position-only rewrite;
- stack-complexity behavior of otherwise transformable recursion;
- cross-backend structural and runtime conformance tests.

### Not affected / Unknown

- Existing direct self-tail-call TCO on ARM64 and x86-64 remains implemented.
- Mutual recursion, indirect calls, sibling calls, and arbitrary recursive
  algorithms are outside the initial confirmed candidate class.
- RISC-V and Wasm direct TCO limitations remain tracked by `VIRC-ISS-0030`.
- NOT_VERIFIED: which reduction operators can be reassociated under the final
  normative integer overflow and floating-point policies.
- NOT_VERIFIED: whether a MIR loop-conversion pass, accumulator synthesis, or
  another representation is the safest implementation strategy.

## 8. Impact

Users can write structurally simple reductions that have an obvious iterative
form but still consume stack linearly and fail at large inputs. An explicit
loop or manual accumulator is a source-level workaround. Severity is `S3`
because the current compiler is semantically correct and the limitation has a
clear workaround; priority is `P2` because bounded-stack transformation would
materially improve robustness and performance for an important pattern.

## 9. Preliminary Analysis

- **CONFIRMED:** the reproduced call is not in tail position because an
  addition executes after it returns.
- **CONFIRMED:** the current TCO pass intentionally preserves this call, and
  the registered negative test requires that behavior.
- **CONFIRMED:** no active post-TCO pass was found that converts this reduction
  to a loop or synthesizes an accumulator.
- **OBSERVED:** the reproduced depth-500,000 program exits with status 139 on
  macOS ARM64 at `-O1`.
- **HYPOTHESIS:** a conservative MIR transformation can handle a useful subset
  of direct self-recursive reductions after proving reassociation and effect
  safety.
- **NOT_VERIFIED:** the precise eligible pattern set, profitability threshold,
  optimization level, and backend-independent representation.
- **NOT_VERIFIED:** semantic safety for checked arithmetic, floating-point
  reductions, pending cleanup, thrown errors, arena scopes, or mutable aliases.

## 10. Acceptance Criteria

- [ ] Define a conservative, reviewable eligibility contract for the initial
      class of non-tail self-recursive reductions, including base-case and
      progress proof requirements.
- [ ] Prove and test preservation of evaluation order, overflow semantics,
      error propagation, cleanup, side effects, ownership, borrows, and arena
      lifetimes; decline the optimization when any proof is unavailable.
- [ ] Convert at least one registered additive reduction fixture equivalent to
      the reproduction into a bounded-stack loop or accumulator at the selected
      optimization level.
- [ ] Execute the transformed fixture at depth at least 1,000,000 with the
      correct result and bounded stack consumption.
- [ ] Add structural MIR/LIR or assembly checks proving the eligible fixture no
      longer contains a recursive linked call.
- [ ] Add negative fixtures for non-associative operations, observable side
      effects, checked/trapping arithmetic where order matters, pending cleanup,
      thrown errors, aliases, and lifetime-sensitive arena paths.
- [ ] Preserve all direct TCO regression tests, including the existing rule
      that pass 11 alone must not misclassify non-tail calls.
- [ ] Record target parity or explicit linked backend limitations instead of
      generalizing ARM64 evidence.
- [ ] When the transformation is declined or unavailable, retain correct call
      semantics and rely on the controlled exhaustion behavior required by
      `VIRC-ISS-0053` rather than unsafe rewriting.
- [ ] Create a linked PLAN before implementation and an accepted verification
      REPORT before resolution or closure; apply the compiler version policy.

## 11. Related Papers

### Issues

- `VIRC-ISS-0024` — production direct self-tail-call optimization (closed).
- `VIRC-ISS-0030` — RISC-V and Wasm direct TCO limitations.
- `VIRC-ISS-0053` — controlled call-stack exhaustion fallback.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-07 | Linked VIRC-ISS-0053 |
| 2026-10-07 | Opened with a reproduced ARM64 stack-exhaustion case, explicit separation from direct TCO, and proof-gated loop-conversion acceptance criteria |

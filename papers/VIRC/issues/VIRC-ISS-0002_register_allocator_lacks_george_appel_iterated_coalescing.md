---
id: "VIRC-ISS-0002"
type: "ISSUE"
domain: "VIRC"
title: "Register allocator lacks George-Appel iterated coalescing"
status: "TRIAGED"
severity: "S2"
priority: "P1"
created: "2026-10-02"
updated: "2026-10-06"
owners:
  - "compiler"
components:
  - "lir"
  - "register-allocation"
  - "interference-graph"
  - "spill-rewrite"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0001"
    - "VIRC-ISS-0041"
  plans:
    - "VIRC-PLN-0001"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "register-allocation"
  - "george-appel"
  - "irc"
  - "coalescing"
---

# VIRC-ISS-0002 — Register allocator lacks George-Appel iterated coalescing

## 1. Summary

The production graph-coloring allocator uses move affinity to bias color
selection and removes copies whose rewritten operands happen to share a
location. It does not implement George–Appel Iterated Register Coalescing
(IRC), despite source comments labeling the post-color cleanup as that
algorithm. The IRC bootstrap fixture implements a separate coalescer and does
not test the production allocator.

## 2. Context

`lir_allocate_registers_color` is the production native register allocator.
George–Appel IRC is a pre-coloring graph algorithm with node/move worklists,
aliasing, conservative coalescing, freezing, optimistic spill selection, color
assignment through aliases, and allocation reruns after spill rewrite. Deleting
an already redundant copy after coloring is useful cleanup but is not IRC.

The audit inspected active modular source and fixtures on 2026-10-02. It did
not modify allocator code or infer correctness from historical reports.

## 3. Expected Behavior

If VIRC claims George–Appel IRC, the production allocator must:

- build a move-aware interference graph from fixed-point liveness;
- maintain explicit node and move worklists plus an alias relation;
- interleave simplify, coalesce, freeze, and spill selection;
- apply George's criterion for precolored nodes and Briggs' conservative
  criterion for non-precolored pairs;
- assign colors through aliases and rerun allocation after legal spill rewrite;
- expose structural facts that production tests can verify.

## 4. Actual Behavior

- The allocator calls `build_interference_graph(intervals)`.
- It collects `move_affinities`, then prefers an already assigned partner color
  when that color is available.
- No move worklists, coalesced-node set, alias union, George/Briggs decision,
  freeze transition, or iterated allocation round exists in the production
  file.
- Uncolorable vregs are assigned stack locations directly; production code
  does not perform the fresh-vreg spill rewrite/recompute/rerun cycle required
  by IRC.
- After coloring, `lir_rewrite_instr` replaces a `Mov` with `Nop` only when
  both rewritten operands already resolve to the same physical register or
  stack location.
- `cg_optimizer_irc.vri` constructs its own 16-node graph, alias array, and
  Briggs-like merge routine instead of invoking `lir_allocate_registers_color`.

## 5. Reproduction

From repository root:

```sh
nl -ba stdlib/vir/compiler/lir_regalloc_color.vri | sed -n '1,40p;121,215p;421,525p'
rg -n -i "move_affinit|worklistMoves|activeMoves|coalescedNodes|alias|coalesc|freeze" \
  stdlib/vir/compiler/lir_regalloc_color.vri
rg -n "build_interference_graph" stdlib/vir/compiler/lir_regalloc_color.vri \
  stdlib/vir/compiler/lir_interference.vri
sed -n '1,190p' tests/bootstrap_codegen/cg_optimizer_irc.vri
```

The production search returns move affinity and post-color cleanup, while the
worklist/alias implementation appears only inside the independent fixture.

## 6. Evidence

- CONFIRMED: `lir_regalloc_color.vri:121-201` builds the interval graph and
  extracts move affinities.
- CONFIRMED: `lir_regalloc_color.vri:421-483` colors nodes once, biases toward
  partner colors, and assigns direct stack slots when no color is available.
- CONFIRMED: `lir_regalloc_color.vri:502-507` calls same-location copy deletion
  “George–Appel Conservative Move Coalescing”, although the deletion occurs
  after coloring and performs no graph-node merge.
- CONFIRMED: the only production allocator functions in this file are helper
  rewriting routines and `lir_allocate_registers_color`; the required IRC
  worklist transitions and alias operations are absent.
- CONFIRMED: `tests/bootstrap_codegen/cg_optimizer_irc.vri:17-125` implements a
  separate graph and coalescer, so it remains green independently of production
  allocator behavior.
- OBSERVED: `build_interference_graph_def_live_out` is imported, but line 124
  calls `build_interference_graph(intervals)`.
- NOT_VERIFIED: whether current coloring causes a specific wrong-code failure;
  this issue establishes algorithm/capability and verification gaps.
- NOT_VERIFIED: quantitative move, spill, frame-size, or runtime regression.

## 7. Scope

### Affected

- native LIR interference construction and graph-coloring allocation;
- copy coalescing, spill strategy, frame legality, and deterministic allocation;
- allocator structural test coverage and algorithm documentation;
- native targets using this allocator.

### Not affected / Unknown

- Wasm or other targets that do not use this native allocator are outside the
  confirmed scope.
- Parser, MIR semantics, and public language syntax are not affected.
- A concrete miscompile remains NOT_VERIFIED.

## 8. Impact

Algorithm claims and tests overstate production behavior, so release evidence
cannot demonstrate IRC. Missed coalescing and non-iterated spilling may increase
moves, stack traffic, and frame size, but their magnitude is not yet measured.
The absence of a production structural oracle also allows accidental
interference or allocation regressions to escape algorithm-specific tests.

## 9. Preliminary Analysis

- CONFIRMED: move-biased color choice and post-color no-op deletion are not
  equivalent to George–Appel IRC.
- CONFIRMED: the fixture cannot serve as a production allocator oracle.
- OBSERVED: direct stack assignment relies on later codegen repair rather than
  a typed fresh-vreg spill rewrite and allocation rerun.
- HYPOTHESIS: correct IRC requires first establishing def-vs-live-out and
  move-edge semantics in the production interference graph.
- NOT_VERIFIED: whether the current graph is conservative, incomplete, or
  incorrect for every phi/parallel-copy and call-clobber case.

## 10. Acceptance Criteria

- [ ] Production graph construction is verified against fixed-point liveness,
  move semantics, phi/parallel copies, fixed registers, and call clobbers.
- [ ] Production allocation contains explicit node/move worklists, aliasing,
  degree updates, simplify/coalesce/freeze/spill iteration, and deterministic
  tie-breaking.
- [ ] George and Briggs criteria each have accepted and rejected structural
  cases that invoke the production allocator.
- [ ] Spilled nodes receive legal typed/aligned rewrite with fresh vregs,
  recomputed analyses, bounded allocation reruns, and no illegal memory-to-
  memory instructions.
- [ ] Post-color copy deletion is retained only as cleanup and is documented
  separately from coalescing.
- [ ] Mutation controls fail when IRC is replaced by move-biased coloring plus
  same-location copy cleanup.
- [ ] Verifier, runtime, call-clobber, register-class, spill, phi-cycle, and
  deterministic-result tests pass on applicable targets.
- [ ] A REPORT links this issue and records production structural evidence,
  exact test commands, target applicability, and remaining limitations.

## 11. Related Papers

### Issues

- VIRC-ISS-0001 — related MIR optimizer capability/test gap.

### Plans

- VIRC-PLN-0001 — implementation and verification plan.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Created and triaged from direct allocator/test audit; linked VIRC-PLN-0001 |
| 2026-10-02 | Linked VIRC-ISS-0001 |
| 2026-10-06 | Linked VIRC-ISS-0041 |

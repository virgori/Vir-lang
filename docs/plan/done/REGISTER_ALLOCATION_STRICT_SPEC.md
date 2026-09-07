# Strict register-allocation specification

Status: proposed gate for the LIR backend  
Scope: ARM64, x86-64, and future target backends

## Purpose

This document defines the correctness contract for register allocation (RA).
Performance work must not be enabled until the contract and its verifier are
implemented. The current implementation in
`stdlib/vir/compiler/lir_regalloc_color.vri` is a useful baseline, but it is
not yet a strict iterated register allocator.

## Required model

RA consumes typed LIR in SSA-like virtual-register form and produces LIR whose
allocatable virtual operands are rewritten to either a physical register or a
legal stack location. It must operate on CFG liveness, not solely source or
block-list order.

For every program point `p`:

- `live_in[p]` contains values required before `p`.
- `live_out[p]` contains values required after `p`.
- an interference edge exists between a definition `d` and each member of
  `live_out` at `d`, except an eligible source of a copy being coalesced.
- two simultaneously live values must never receive the same register.

Liveness is solved to a fixed point over predecessor/successor edges. Phi
uses are attributed to their incoming edge, not to the phi block as a whole.
If non-SSA LIR remains, the lowering boundary must define equivalent
copy/parallel-copy semantics first.

## ABI contract

Each `TargetRegisterClass` declares, per register:

- register class and width;
- allocatable, reserved, caller-saved, callee-saved, argument, return, stack,
  frame-pointer, heap-base, and scratch roles;
- whether it may hold a value across a call;
- save/restore cost and required stack alignment.

Calls must expose implicit uses and clobbers. A virtual value live across a
call either receives a non-clobbered register, is saved/reloaded through a
legal stack location, or is split around the call. Scratch registers are never
colorable. The allocator may not infer call safety from a numeric register
range.

## Allocation contract

1. Pre-colour fixed-register operands and add their interferences.
2. Construct a class-aware interference graph or use a proven equivalent
   allocator.
3. Coalesce only when Briggs/George safety conditions hold and preserve a move
   worklist; mere preference during color selection is not coalescing.
4. Simplify, freeze, spill-select, and select are deterministic for identical
   LIR and target configuration.
5. A spill is a rewrite: allocate a typed, aligned stack slot; insert reloads
   and stores; recompute liveness/interference; and retry allocation. Stack
   slots must not overlap values with overlapping live ranges.
6. No virtual register remains in executable LIR after RA, apart from an
   explicitly documented late-lowering operand class.
7. Frame size includes callee-save area, spill slots, outgoing-call area, and
   padding; the final ABI stack alignment is mandatory at every call.

## Mandatory post-RA verifier

The verifier runs in debug/strict builds before code emission and rejects the
function with a deterministic diagnostic if any invariant fails:

- use-before-def and use of an unallocated vreg;
- same physical register assigned to an interference edge;
- assignment outside the operand's register class or width;
- caller-saved value live across a call without an explicit preservation;
- illegal memory-to-memory instruction after spill rewrite;
- invalid frame offset, overlap, alignment, or out-of-frame stack access;
- missing callee-save prologue/epilogue or unbalanced stack adjustment;
- illegal branch/phi edge assignment and unresolved parallel copy;
- target-reserved register allocation.

The verifier is target-aware but consumes a common allocation map and common
CFG liveness facts. It is not optional in CI for allocator changes.

## Current-gap audit

The following observations are based on the current source tree, not assumed
behavior:

| Area | Current behavior | Strict requirement |
|---|---|---|
| Liveness | `lir_liveness.vri` builds one interval per vreg by linear block/instruction order; only backward branches extend intervals. | Fixed-point block/edge liveness and multi-range segments. |
| Interference | `lir_interference.vri` overlaps whole intervals and allocates a dense bit matrix. | Def-vs-live-out graph or equivalent sparse representation. |
| Coalescing | One `move_partner` preference plus removal of copies that already received identical colours. | George/Briggs worklists and conservative union of move-related nodes. |
| Calls | `func_has_calls` selects a callee-saved palette; calls/clobbers are not explicit graph constraints. | Explicit target call clobbers and liveness preservation. |
| Spills | One 8-byte negative frame slot per uncolourable vreg; no rewrite/reallocate round. | Typed aligned slots, load/store rewrite, reallocation, optional splitting. |
| Leaf palette | Comment promises ARM64 leaf `X9..X15`, while `color_to_phys` always returns `X19 + color` for ARM64. | One tested target descriptor; comments and emitted policy must agree. |
| Complexity | `n_nodes * ceil(n_nodes/64)` bit matrix plus adjacency vectors. | Sparse graph default; dense mode only under a measured threshold. |

## Strict rollout gates

1. Add LIR CFG and call-clobber tests, then implement the verifier in report-only
   mode.
2. Make verifier failures fatal in CI, while retaining the current allocator.
3. Replace interval-only liveness with block/edge bitsets and validate identical
   runtime results on the corpus.
4. Introduce spill rewriting and iterative reallocation.
5. Enable true conservative coalescing, then tune heuristics only with
   benchmark and spill-rate evidence.

No optimization may relax a verifier invariant.

# Register allocation optimization and block-arena plan

Status: proposed implementation roadmap  
Depends on: `REGISTER_ALLOCATION_STRICT_SPEC.md`

## Goal

Replace the current interval-overlap coloring baseline with a correctness-first
allocator that scales on large compiler functions without retaining temporary
allocation state for the lifetime of the compilation.

## Order of work

### Phase 0 — measure before changing policy

Add per-function RA telemetry, disabled by default:

- vreg count, CFG block/edge count, live-set peak, move count;
- graph node/edge count, dense-memory bytes, allocator time;
- spills, reloads, stores, frame growth, removed copies;
- target, optimization level, function hash, and verifier result.

Use a deterministic JSON or line format so benchmark diffs can flag both a
runtime regression and a spill/frame regression.

### Phase 1 — correct liveness and sparse graph

Implement backward dataflow:

```text
live_out[B] = union(live_in[S] for S in succ[B])
live_in[B]  = use[B] union (live_out[B] - def[B])
```

Compute it to convergence with an RPO worklist. Represent live sets as packed
bitsets for small/medium vreg counts and sparse chunks for large functions.
Build edges while walking each block backward from `live_out`; do not derive
the graph from whole-function interval overlap.

Keep dense bit-matrix mode only where telemetry demonstrates it wins. A
practical initial threshold is a target-configurable `V <= 512`; above that,
use sparse adjacency plus a compact membership structure. The threshold must
be benchmarked, not treated as an ABI guarantee.

### Phase 2 — target descriptors and constraints

Move palettes, reserved registers, call clobbers, width classes, spill-slot
alignment, and save/restore rules out of numeric branches such as
`color_to_phys`. Add descriptors for ARM64 and x86-64 first; reserve interface
slots for RISC-V and Wasm without pretending they use the native allocator.

Add constrained nodes for fixed ABI operands, call arguments/results, shifts,
divides, and scratch-only operations. Verify the descriptor against codegen at
startup in debug builds.

### Phase 3 — iterative spill rewrite

After spill selection:

1. allocate a typed stack slot through a frame-layout service;
2. split the value around each use/definition where profitable;
3. insert target-legal reload/store pseudo-operations;
4. recompute liveness and allocation;
5. repeat with a hard diagnostic/telemetry limit to prevent non-convergence.

Prefer rematerialization for constants, addresses, and pure inexpensive
expressions. Use loop-frequency, pressure, and reload cost in the spill score;
do not use block-index back-edge depth as the sole loop model.

### Phase 4 — conservative coalescing

Implement the full move worklists: simplify, freeze, spill, worklist moves,
active moves, coalesced nodes, and aliases. Coalesce only if George's
precoloured-node criterion or Briggs' conservative criterion succeeds. Resolve
parallel copies on CFG edges after allocation. Measure removed moves versus
introduced spills; turn off a harmful heuristic per target.

### Phase 5 — advanced reductions

- split live ranges at calls and loop boundaries;
- allocate hot loops before cold blocks or use a priority allocator;
- rematerialize instead of spill where target cost permits;
- use caller-saved registers only for values proven dead at calls;
- add register-pressure-aware instruction scheduling after correctness is
  stable;
- evaluate linear scan for JIT/fast mode while preserving the same verifier.

## Block-arena design

### Ownership rule

Arena allocation is allowed only for state whose lifetime is bounded by one
RA invocation or a shorter checkpoint. No pointer from an RA scratch arena may
be stored in returned `LirFunc`, diagnostics retained after the pass, global
caches, or a vector that can outlive the arena reset.

### Proposed hierarchy

```text
Compilation session
└── Function compilation
    ├── persistent IR/frame objects       (normal ownership or function arena)
    ├── RA arena                          (reset after post-RA verification)
    │   ├── CFG/liveness bitsets
    │   ├── sparse adjacency chunks
    │   ├── worklists, aliases, move sets
    │   └── temporary spill-rewrite maps
    └── emission scratch arena            (reset after code emission)
```

`RaArena` is a linked sequence of fixed-size blocks, not one giant allocation.
It supplies aligned bump allocation, records a checkpoint `(block, offset)`,
and supports rewind to that checkpoint. Whole-arena reset releases or caches
the blocks only after the function's verifier and code emission no longer need
them. Blocks must be sized from telemetry; begin with 64 KiB and grow
geometrically, with a hard per-function accounting limit.

### Safe migration sequence

1. Add `RaArena` behind an allocation interface while preserving existing
   heap allocation.
2. Move only ephemeral interval, worklist, and graph construction buffers.
3. Run ASan/guard-page mode, allocator poisoning on reset, and a retained
   diagnostics test to prove no escaping pointer exists.
4. Move temporary spill-rewrite maps after Phase 3 is stable.
5. Consider a function arena for LIR only after returned IR ownership is
   explicit and codegen no longer retains stale handles.

Never migrate `LirFunc`, `LirBlock`, `LirInstr`, MIR objects, or diagnostic
payload merely because their current allocation calls are numerous. Their
escaping ownership must be proved first.

## Definition of done

- strict verifier is clean for every supported native target;
- differential execution corpus agrees before and after RA;
- no arena pointer survives its reset under poisoning/guard tests;
- a high-pressure benchmark shows lower compile memory or time without more
  spills/frame bytes beyond a documented tolerance;
- ELF/PE/Wasm use their own target policy and do not inherit ARM64 register
  assumptions.

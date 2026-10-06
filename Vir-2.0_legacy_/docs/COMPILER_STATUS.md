# Architecture / Compiler Status

This page records implementation evidence; it does not alter the
[designed architecture](ARCHITECTURE.md) or the
[language specification](vir_language_spec_v2.0_en.md).
Source links describe current wiring, not a claim that all fixtures pass.

Designed stage sequence: **AST → HIR → MIR → LIR → RA → codegen**.
The active [pipeline](../stdlib/vir/compiler/pipeline.vri) defaults to direct
AST → MIR (`g_use_hir_pipeline = 0`); HIR lowering is conditional.

## Implemented today

### AST and semantic analysis

[Lexer](../stdlib/vir/compiler/lexer.vri),
[parser](../stdlib/vir/compiler/parser.vri), and
[semantic dispatcher](../stdlib/vir/compiler/semantic.vri) provide parsing and
passes for modules, symbols, names, types, inference, type checking, control
flow, borrows, constant folding and diagnostics.
[Test runner](../run_tests.sh) checks fixture output and negative diagnostics;
[ownership fixtures](../tests/memory_contract/README.md) specify a separate
contract. These suites do not imply complete spec conformance.

### HIR

[HIR representation](../stdlib/vir/compiler/hir.vri),
[AST → HIR](../stdlib/vir/compiler/ast_to_hir.vri) and
[HIR → MIR](../stdlib/vir/compiler/hir_to_mir.vri) exist.
`set_pipeline_hir_mode` selects this branch in the pipeline; it is not the
default. Release smoke checks do not separately establish HIR coverage.

### MIR

[AST → MIR](../stdlib/vir/compiler/ast_to_mir.vri) is the default lowering.
[MIR](../stdlib/vir/compiler/mir.vri),
[CFG and dominators](../stdlib/vir/compiler/mir_cfg.vri),
[SSA](../stdlib/vir/compiler/mir_ssa.vri), and
[optimization dispatcher](../stdlib/vir/compiler/mir_opt_pipeline.vri)
implement the mid-level path. The pipeline calls memory-contract verification
around transformations. Pass availability is not a promise of benefit on
every workload; see [benchmark limits](BENCHMARKS.md).

### LIR

[LIR](../stdlib/vir/compiler/lir.vri) and
[MIR → LIR](../stdlib/vir/compiler/lir_lower.vri) provide lower-level
instructions and virtual registers. The pipeline applies backend hooks
before and after allocation. [LIR verifier](../stdlib/vir/compiler/lir_verifier.vri)
provides explicit checks; its existence alone does not establish universal
verification of every path.

### RA (register allocation)

[Liveness](../stdlib/vir/compiler/lir_liveness.vri) and
[graph coloring](../stdlib/vir/compiler/lir_regalloc_color.vri) are invoked
by the pipeline to produce physical and stack mappings. Allocation is a
heuristic, with no proof here of globally optimal register assignments.

### Codegen and binary emission

Backend implementations include [ARM64](../stdlib/vir/compiler/lir_codegen.vri),
[x86_64](../stdlib/vir/compiler/lir_codegen_x86.vri),
[RISC-V](../stdlib/vir/compiler/lir_codegen_riscv.vri), and
[WASM](../stdlib/vir/compiler/lir_codegen_wasm.vri).
The [release workflow](../.github/workflows/virc-release.yml) builds compiler
binaries for macOS ARM64 and Linux ARM64/x86_64. It verifies arithmetic output
`30 90` on macOS and both Linux targets (ARM64 via QEMU), and runs the `min`
suite on the rebuilt macOS compiler. This is narrower than full cross-target
language, ABI, ownership and runtime coverage.

## Roadmap and validation gaps

[Plans](plan/) retain the intended architecture. This status page does not
redesign any stage. Evidence still needed for broader public claims includes
HIR-specific execution coverage, full conformance across backends, bootstrap
reproducibility, and benchmark output oracles for every timed sample.
These are validation gaps, not newly imposed language requirements.

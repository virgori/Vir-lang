# Memory verification workflow

## Evidence map

For each claim, map it to:

- source semantics: `VIR-SPC-0005` and `VIR-SPC-0017` / `0018`;
- analysis: `compiler/src/semantic/borrow/**` and the pass orchestrator;
- lowering: `compiler/src/lower/ast_to_mir.vri` plus MIR memory verifier;
- backend: the exact ARM64, x86-64, Wasm, or RISC-V lowering path;
- behavior: matching rows in `tests/memory_contract/manifest.tsv`.

## Focused checks

Use the repository runner with an exact filter, for example:

```sh
python3 tools/gap_contract_runner.py \
  --manifest tests/memory_contract/manifest.tsv \
  --fixtures tests/memory_contract \
  --filter 'MEM-(ESC|BOR|LOOP|CAP|CLEAN)' \
  --opt-level=-O0
```

Expand across affected optimization levels and targets. Include both positive
execution and compile-fail fixtures. For allocation-elimination or watermark
claims, inspect MIR/LIR or disassembly; successful output alone does not prove
the intended allocation path.

## Claims to avoid

- “No GC” does not mean no allocator, page fault, synchronization, or cleanup
  cost.
- Arena reset is constant bookkeeping, not automatic object/resource cleanup.
- Escape analysis is an optimization opportunity; it does not guarantee every
  non-escaping aggregate stays in registers.
- Native ARM64 evidence does not establish x86-64, Wasm, or RISC-V behavior.
- A defined API name does not establish that every backend lowers it.

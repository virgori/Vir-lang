# Historical docs

Documents here (or marked *Historical* in `docs/`) describe superseded designs.

**Official compiler IR pipeline** (see Language Spec §1.2 and [`../ARCHITECTURE.md`](../ARCHITECTURE.md)):

```text
AST → HIR → MIR → LIR → Optimizer → Codegen
```

Source of truth for IR shapes: `stdlib/vir/compiler/{hir,mir,lir}.vri`.

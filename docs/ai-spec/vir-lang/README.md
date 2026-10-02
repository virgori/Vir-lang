# Vir AI Language Specification

**Role:** machine-oriented Vir documentation (anti-hallucination source of truth).  
**Canonical human specs:** `VIR-SPC-0017` and `VIR-SPC-0018` under `papers/VIR/specs/`  
**Cursor Skill adapter:** `.cursor/skills/vir-lang/SKILL.md`  
**Language version target:** Vir Spec **v2.0**  
**File extension:** `.vri`

```text
Vir specifications
        │
        ├── Canonical SPEC papers → papers/VIR/specs/ and papers/STLB/specs/
        └── Supporting examples   → docs/ai-spec/vir-lang/examples/
```

## Packaging adapters

The same tree can be wrapped as:

- Cursor / Codex Agent Skill (`.cursor/skills/vir-lang`)
- Claude / ChatGPT Skill bundle
- RAG / system-prompt corpus
- IDE AI context pack

Bump this folder’s implied version when Vir language releases change syntax.

## Layout

- [`VIR-SPC-0010`](../../../papers/VIR/specs/VIR-SPC-0010_programming_language_ai_spec.md) — agent language contract
- [`VIR-SPC-0011`](../../../papers/VIR/specs/VIR-SPC-0011_control_flow_ai_spec.md) — control flow
- [`VIR-SPC-0012`](../../../papers/VIR/specs/VIR-SPC-0012_errors_ai_spec.md) — errors
- [`VIR-SPC-0013`](../../../papers/VIR/specs/VIR-SPC-0013_functions_ai_spec.md) — functions
- [`VIR-SPC-0014`](../../../papers/VIR/specs/VIR-SPC-0014_modules_ai_spec.md) — modules
- [`VIR-SPC-0015`](../../../papers/VIR/specs/VIR-SPC-0015_syntax_ai_spec.md) — syntax
- [`VIR-SPC-0016`](../../../papers/VIR/specs/VIR-SPC-0016_types_ai_spec.md) — types
- [`STLB-SPC-0001`](../../../papers/STLB/specs/STLB-SPC-0001_standard_library_ai_spec.md) — standard library
- `examples/` — idiomatic `.vri` samples

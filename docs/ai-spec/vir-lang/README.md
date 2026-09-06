# Vir AI Language Specification

**Role:** machine-oriented Vir documentation (anti-hallucination source of truth).  
**Human docs:** `docs/vir_language_spec_v2.0_*.md`  
**Cursor Skill adapter:** `.cursor/skills/vir-lang/SKILL.md`  
**Language version target:** Vir Spec **v2.0**  
**File extension:** `.vri`

```text
Vir Documentation
        │
        ├── Human Docs  →  docs.virgori.com / docs/vir_language_spec_*.md
        │
        └── AI Specification  (this tree)
             ├── SKILL.md          — behaviour rules for agents
             ├── references/       — compact language facts
             └── examples/         — idiomatic .vri samples
```

## Packaging adapters

The same tree can be wrapped as:

- Cursor / Codex Agent Skill (`.cursor/skills/vir-lang`)
- Claude / ChatGPT Skill bundle
- RAG / system-prompt corpus
- IDE AI context pack

Bump this folder’s implied version when Vir language releases change syntax.

## Layout

```text
docs/ai-spec/vir-lang/
├── README.md
├── SKILL.md
├── references/
│   ├── syntax.md
│   ├── types.md
│   ├── functions.md
│   ├── control-flow.md
│   ├── modules.md
│   ├── errors.md
│   └── stdlib.md
└── examples/
    ├── basics.vri
    ├── algorithms.vri
    └── common-patterns.vri
```

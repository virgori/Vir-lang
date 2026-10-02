---
id: "VIRC-ISS-0006"
type: "ISSUE"
domain: "VIRC"
title: "Compiler sources are coupled to stdlib and oversized pass files"
status: "TRIAGED"
severity: "S2"
priority: "P1"
created: "2026-10-02"
updated: "2026-10-02"
owners:
  - "VIRC"
components:
  - "repository-migration"
  - "compiler-source-layout"
  - "module-resolution"
  - "semantic-passes"
  - "optimizer"
  - "self-hosting"
  - "language-server"
  - "vscode-extension"
related:
  issues:
    - "VIRC-ISS-0007"
  plans:
    - "VIRC-PLN-0004"
  reports:
    - "VIRC-RPT-0002"
supersedes: null
superseded_by: null
tags:
  - "architecture"
  - "copy-migration"
  - "modularization"
  - "module-list"
  - "editor-tooling"
---

# VIRC-ISS-0006 — Compiler sources are coupled to stdlib and oversized pass files

## 1. Summary

At Vir 4.0.0 source snapshot
`fd0064ea516c132b57cd9dec8acf827ed4361555`, the canonical self-hosted compiler
sources, compiler-only compatibility preludes, and generated compiler bundle
live under `stdlib/vir/compiler/`. The standard-library registry consequently
publishes a large compiler-internal namespace.

Several semantic, lowering, parser, code-generation, and optimization files
also combine pass orchestration, mutable state, shared utilities, rules, and
individual transformations in one physical source unit. This increases change
surface, makes focused review and testing difficult, and forces maintainers to
load unrelated compiler logic when fixing a narrow area such as tensor type
checking.

## 2. Context

This issue records an architecture and maintainability problem. It does not
claim that moving files or splitting modules, by itself, fixes an existing
language-semantics defect.

The audit is intentionally structural and bounded. It inspected the active
registry, module resolver, modular compiler sources, generated-source tools,
and the largest pass files at the pinned source snapshot. It did not perform a full
semantic review of all compiler functions.

## 3. Expected Behavior

- Implementation is isolated in sibling `/Users/gengyang/Vir-3.0`, seeded by a
  manifest-verified copy of non-legacy docs, VPS papers/tool/skill, complete
  tests and their runner dependencies.
- The seed operation does not copy `docs/_legacy`, Git metadata, frozen trees,
  build/cache/scratch output, prebuilt binaries or unrelated current changes.
- Native `vir-lsp` and `vscode-vir` canonical source are copied from the current
  source snapshot into separate `tools/` packages; nested Git state, generated
  JavaScript, VSIX packages and server binaries are rebuilt rather than seeded.
- Canonical compiler sources live in a top-level compiler-owned tree, separate
  from the standard-library source tree.
- A compiler project `module.list` provides canonical, short module identities
  for compiler-internal `include` and `import` statements.
- `stdlib/stdlib.vri` registers standard-library modules, not the compiler
  implementation or generated compiler bundle.
- A pass entry file declares metadata, dependencies, enablement, verification,
  and execution order only. Domain rules and transformations live in focused
  leaf modules.
- Each optimization has a clear physical source file and a narrow exported
  entry point so it can be changed, disabled, tested, or reverted independently.
- Generated compiler artifacts are derived from canonical modules and cannot
  become an independently edited source of truth.
- Refactoring preserves diagnostics, module identity, ownership and cleanup
  semantics, generated output, and self-host fixed-point behavior.
- Compiler remains the only owner of language semantics; LSP owns protocol and
  document lifecycle, while the extension owns client/presentation behavior.

## 4. Actual Behavior

- `stdlib/vir/compiler/` contains 105 `.vri` paths: 93 regular non-bundle
  source files, 11 symlink aliases into other stdlib areas, and the generated
  `virc.vri` bundle.
- The 93 regular non-bundle compiler files contain approximately 84,905 lines;
  generated `virc.vri` contains 79,002 lines.
- `stdlib/stdlib.vri` contains 101 `compiler.*` entries and additional short
  names such as compiler prelude aliases, mixing compiler implementation with
  the public standard-library registry.
- No project `module.list` exists at the repository or compiler root.
- Large files combine multiple responsibilities:
  - `sem_pass6_typecheck.vri`: 6,430 lines and 110 functions;
  - `parser.vri`: 6,135 lines and 88 functions;
  - `lir_codegen.vri`: 5,697 lines;
  - `mir_opt.vri`: 4,296 lines and 123 functions;
  - `main.vri`: 4,245 lines;
  - `sem_pass8_borrow.vri`: 3,148 lines and 128 functions;
  - `ast_to_mir.vri`: 7,250 lines and 164 functions.
- `mir_opt.vri` contains the implementations of many otherwise independent
  transformations, while `mir_opt_pipeline.vri` holds their sequence and
  enablement.
- Generated-source tools hard-code `stdlib/vir/compiler` paths. The current
  assembler/synchronizer relies on `# @vir_source` spans and path-specific
  patching rather than deriving the bundle solely from one compiler entry
  module plus the active module graph.
- Compiler files use a mixture of short include names and `compiler.*` names,
  so the physical location and registry alias often leak into dependencies.
- No sibling `/Users/gengyang/Vir-3.0` exists at the audit point.
- The snapshot contains the current test suite, paper registry/tool/skill and
  source/tool changes. `docs/_legacy/**` remains explicitly excluded from the
  Vir-3.0 seed.
- The snapshot contains `tools/vscode-vir`, including canonical
  TypeScript/assets/config plus generated `out/**` and packaged `*.vsix` files.
- Standalone `vir-lsp` is not tracked by the parent repository snapshot. It is a separate,
  clean repository at commit `55e964a3664fb703731c59aa85f3f546e44b1b03`
  with six tracked source/doc files. The corresponding extension integration,
  build script and LSP tests are already present in snapshot `fd0064ea`.

## 5. Reproduction

Run from source snapshot `fd0064ea516c132b57cd9dec8acf827ed4361555`:

```sh
find stdlib/vir/compiler -maxdepth 1 -name '*.vri' | wc -l
find stdlib/vir/compiler -maxdepth 1 -type l -print -exec readlink {} \;
find stdlib/vir/compiler -maxdepth 1 -type f -name '*.vri' \
  ! -name 'virc.vri' -exec wc -l {} + | sort -nr
wc -l stdlib/vir/compiler/virc.vri
rg '^compiler\.' stdlib/stdlib.vri | wc -l
find . -name module.list -type f -print
rg -n '^func ' stdlib/vir/compiler/sem_pass6_typecheck.vri
rg -n '^func ' stdlib/vir/compiler/sem_pass8_borrow.vri
rg -n '^func ' stdlib/vir/compiler/mir_opt.vri
rg -n 'stdlib/vir/compiler|VIRC_PATH|PREFIXES|PRELUDE_MAP' \
  tools/assemble_virc.py tools/sync_virc.py tools/preexpand_virc.py
```

## 6. Evidence

- CONFIRMED: `stdlib/stdlib.vri` maps compiler implementation names into the
  standard-library registry.
- CONFIRMED: `stdlib/vir/compiler/main.vri` loads `stdlib/stdlib.vri` and an
  optional nearest-ancestor `module.list`; directory mappings support dotted
  module tails.
- CONFIRMED: `stdlib/vir/compiler/semantic.vri` already acts as the ten-pass
  semantic orchestrator, but most individual pass files still own large bodies
  of unrelated rule logic.
- CONFIRMED: `stdlib/vir/compiler/mir_opt_pipeline.vri` already defines MIR pass
  order and optimization-level guards, while transformation bodies remain
  concentrated in `mir_opt.vri`.
- CONFIRMED: `tools/sync_virc.py` accepts canonical source additions only under
  `stdlib/vir/compiler`, and `tools/preexpand_virc.py` carries hard-coded search
  prefixes and prelude mappings for that layout.
- CONFIRMED: the active module contract gives `stdlib/stdlib.vri` and project
  `module.list` separate responsibilities; the compiler currently uses only
  the former for its internal published names because no compiler project
  registry exists.
- CONFIRMED: root `run_tests.sh` directly invokes
  `tools/gap_contract_runner.py`, proving runner migration needs dependency
  closure rather than filename-prefix copying.
- OBSERVED: the current layout makes file names and registry aliases serve as
  architecture boundaries even where those boundaries do not match the
  compiler domains.
- NOT_VERIFIED: whether external users depend on any `compiler.*` stdlib name.
  Migration must inventory call sites before removal.
- NOT_VERIFIED: complete behavioral equivalence of a future module graph until
  self-host and regression gates run on the moved tree.
- NOT_VERIFIED: migrated native server and extension integration until their
  commit-pinned source is rebuilt and protocol/client suites pass in Vir-3.0.

## 7. Scope

### Affected

- clean sibling repository seeding and provenance;
- non-legacy docs, VPS paper tool/skill, tests and runner scripts;
- compiler source ownership and directory layout;
- project and stdlib registry boundaries;
- semantic pass organization, especially type checking and borrow analysis;
- MIR optimization registration and implementations;
- generated compiler bundle provenance and synchronization tooling;
- self-hosting and compiler contract tests.
- native language-server source/build/tests and VS Code extension source/tests.

### Not affected / Unknown

- Vir syntax or language semantics are not changed by this issue;
- public stdlib APIs are not intentionally renamed;
- optimizer algorithms are not enabled or strengthened as part of a mechanical
  module split;
- LSP/editor source migration is included, but feature or protocol behavior
  changes require separate VLSP-scoped work;
- external consumers of internal compiler module names remain unknown until a
  repository and downstream compatibility audit is recorded.

## 8. Impact

The problem raises the cost and risk of narrow compiler changes. A tensor type
rule, borrow join, or MIR transform currently requires navigating files that
also contain unrelated rules and shared mutable state. Generated-source tools
and stdlib registry entries reinforce the coupling, so partial moves can create
duplicate module identities, order-dependent resolution, or bundle drift.

The issue is rated S2 because an unsafe refactor can affect compiler correctness
and self-hosting broadly, even though this audit does not attribute a current
user-program miscompile to source-file size alone. It is P1 because deeper pass
work should not continue on top of the coupled layout.

## 9. Preliminary Analysis

- CONFIRMED: the resolver already contains the core capability needed for a
  compiler-owned directory alias in `module.list`.
- CONFIRMED: semantic and optimizer orchestration seams exist and can be used as
  compatibility boundaries during incremental extraction.
- HYPOTHESIS: moving the canonical compiler tree before splitting pass logic
  will reduce dual-path churn and make every later extraction use the final
  module identity.
- HYPOTHESIS: explicit context objects and leaf-module exports will reduce
  accidental global-state coupling and make pass-level tests practical.
- HYPOTHESIS: generating the bundle from the resolved module graph will remove
  the need for path-specific synchronization patches.
- HYPOTHESIS: seeding a clean sibling tree before compiler changes prevents
  legacy/build artifacts and unrelated working-tree changes from becoming
  accidental dependencies of Vir 3.0.
- NOT_VERIFIED: exact module size thresholds that best balance compiler parsing
  overhead against human and tool context size; the plan defines review guards
  but requires measurement during implementation.

## 10. Acceptance Criteria

- [ ] `/Users/gengyang/Vir-3.0` is created only after a non-destructive
  destination preflight and is populated by copy, never by moving source.
- [ ] A machine-readable seed manifest records provenance, relative path, type,
  mode, symlink target, size and SHA-256 for copied regular files.
- [ ] `docs/**` is copied with zero `docs/_legacy/**` entries in the destination;
  the source legacy tree remains untouched.
- [ ] `papers/**`, `paper`, `tools/paper.py`, schemas/templates and
  `.agents/skills/vir-paper-management/**` from the snapshot validate in Vir-3.0.
- [ ] All allowlisted snapshot test files plus audited runner/checker dependency
  closure are present with matching modes and hashes.
- [ ] `tools/vir-lsp` contains only tracked source/docs from commit `55e964a`;
  `tools/vscode-vir` plus LSP build/tests come from snapshot `fd0064ea`.
- [ ] Nested `.git`, `.vir`, `out`, source maps, VSIX, `node_modules` and native
  binaries are absent from canonical seed payload and are reproducibly rebuilt.
- [ ] Native LSP and extension contract tests prove compiler-owned semantics,
  version-compatible facts/snapshots and CWD-independent startup.
- [ ] Source `.git`, frozen, build/dist/scratch/cache/log payload, prebuilt
  compiler binary, absolute source-backlink symlink or post-snapshot drift is
  not copied; any destination Git repository is initialized fresh, locally,
  without a remote, and records the seed manifest/provenance.
- [ ] Canonical compiler sources and generated compiler artifacts no longer
  live under `stdlib/vir/compiler/`.
- [ ] The compiler tree owns a validated `module.list`; compiler-internal source
  uses canonical module names resolved through it.
- [ ] `stdlib/stdlib.vri` contains no compiler implementation registrations or
  compiler-only prelude aliases.
- [ ] Registry tests cover duplicate names, missing targets, cycles,
  include/import convergence, CWD independence, directory mappings, and
  project/stdlib collision rejection.
- [ ] Pass entry files contain registration, declaration, guards, verification,
  and ordering only; rule or transform bodies are rejected by an architecture
  checker.
- [ ] Type checking is decomposed into focused modules including separate
  tensor, generic, callable, assignment, entity/packed, enum/pattern, operator,
  FFI, and diagnostic rule areas.
- [ ] Borrow analysis and memory-sensitive optimizations preserve move, borrow,
  Arena, cleanup, and O0–O3 equivalence contracts.
- [ ] Every MIR optimization has one clearly named implementation module and
  can be tested and disabled independently without editing another transform.
- [ ] New source filenames are descriptive and avoid snake_case except for
  compatibility, ABI, generated, serialized, or externally constrained names.
- [ ] Generated compiler output is reproducible from canonical source modules;
  direct edits to the generated bundle are rejected.
- [ ] Modular/generated synchronization, full relevant regression suites, and
  the stage-2/stage-3 self-host fixed-point gate pass from repository root, a
  subdirectory, and an unrelated CWD.
- [ ] A VIRC REPORT maps implementation evidence to every criterion before the
  issue can move to RESOLVED or CLOSED.

## 11. Related Papers

### Issues

- `VIRC-ISS-0001` — optimizer placeholders and transformation verification;
- `VIRC-ISS-0002` — register-allocation architecture;
- `VIR-ISS-0002` — type-system hardening and canonical typed identity.

These papers are context only and are not linked as source issues because this
issue does not implement their algorithms.

### Plans

- `VIRC-PLN-0004` — compiler tree separation and sequential pass
  modularization.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Created from structural audit; triaged scope, evidence, impact, and acceptance criteria |
| 2026-10-02 | Linked `VIRC-PLN-0004` |
| 2026-10-02 | Added verified copy migration requirements for sibling `Vir-3.0`, excluding legacy docs and including VPS/test runner foundations |
| 2026-10-02 | Added commit-pinned source migration and ownership boundaries for native `vir-lsp` and `vscode-vir` |
| 2026-10-02 | Rebased the issue on current Vir 4.0.0 source snapshot `fd0064ea`; initial failures may be ledgered while unexplained new regressions remain prohibited |
| 2026-10-02 | Linked VIRC-ISS-0007 |
| 2026-10-02 | Linked VIRC-RPT-0002 |

---
name: vir-stdlib-modules
description: >-
  Resolve and maintain Vir module identity, mandatory project module.list
  registries, include/import/export dependencies, stdlib modules, public
  APIs, source moves, and compiler generated-source provenance.
---

# Vir modules and standard library

Use after `vir-lang`. For every `.vri` write or review, locate and inspect the
nearest applicable `module.list` even when the immediate change has no new
import. This is a mandatory Agent preflight.

Read [`references/module-list.md`](references/module-list.md) for project module
work and [`references/stdlib.md`](references/stdlib.md) before using a stdlib
API.

## Dependency choice

- `include module` loads the module under the include contract.
- A registered dotted Module ID is preferred. Direct `.vri` paths remain
  compatibility targets for include and selective-import providers; they do
  not publish a Module ID.
- `import A, B from module` selects exported symbols and does not require a
  preceding include.
- `import A from module` selects any supported exported declaration kind,
  including functions, types, constants, and variables.
- `import from module` imports the complete export surface; `import module as
  alias` binds a whole-module namespace.
- `export` defines the intended public surface; `share` and `port` have separate
  state/message semantics.
- Use one dependency form per canonical Module ID. Do not add both `include M`
  and `import ... from M` unless a verified alias behavior requires it.

## Current implementation caveats

`VIRC-ISS-0007` tracks redundant include/import pairs and `VIRC-ISS-0008`
tracks a fail-open selective-import case for modules with no exports. Therefore:

- do not copy redundant pairs from nearby legacy code;
- verify that every selective import is explicitly exported even if the current
  compiler accepts it;
- distinguish normative module visibility from compatibility behavior.

## Mutation gate

When adding, moving, renaming, or splitting `.vri` files:

1. Update the nearest project `module.list` in the same change. For compiler
   sources this is `compiler/module.list`.
2. Use canonical registered names in source; do not leak physical directory
   layout through invented aliases. Use a direct path only for an intentional
   local/compatibility dependency, and verify that it converges to a registered
   canonical identity when it names a registered file.
3. Check duplicate keys, missing paths, prefix collisions, cycles, and CWD
   independence with the active resolver/checker.
   Also reject an exact project Module ID collision with the active stdlib
   registry; prefix-only relationships are allowed.
4. Update canonical sources before generated bundles; run the verified
   generator/synchronizer rather than editing generated output.

If a multi-file Vir project lacks `module.list`, treat that as incomplete
project structure. Create it only when the requested change authorizes project
setup; otherwise report the missing registry instead of inventing module paths.

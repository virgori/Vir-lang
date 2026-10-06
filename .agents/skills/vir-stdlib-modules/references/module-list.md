# `module.list` contract

## Mandatory discovery

Before editing `.vri` files, search upward from the project/source location for
the nearest `module.list`. The active resolver also has repository-specific
fallbacks; inspect `compiler/src/main.vri` and `tools/module_graph.py` before
describing resolution order.

For this repository:

- compiler modules: `compiler/module.list`;
- standard library: `stdlib/stdlib.vri` (a separate registry, not a compiler
  project `module.list`);
- module fixtures may own local registries such as `tests/modules/module.list`.

## Format

Entries use `name = relative-path`; the initial base is the directory containing
`module.list`. `root` changes the base for the mappings that follow it, so keep
it before every mapping. A directory alias can supply dotted tails only when
the active resolver supports that mapping.

```text
root = .
app = src
main = src/main.vri
parser = src/frontend/parser.vri
```

`root = .` is accepted but optional when mappings are relative to the registry
directory. Keep values unquoted for native/tool parity. Paths are relative to
the active base directory. Keep one canonical identity for each source file.
Do not register duplicate keys, missing targets, or colliding directory/file
prefixes. Load the active toolchain `stdlib.vri` and reject an exact project
Module ID collision with it when auditing the complete registry. Do not reject
prefix-only relationships such as stdlib `http` and project `http.app`.

For declaration recipes, placement rules, and the verified `root` behavior,
use the `vir-module-list` skill.

## Include/import discipline

Choose deliberately:

```vir
include parser
```

or:

```vir
import Parser, parse from parser
```

Do not write both for the same canonical module as a default pattern. A
selective import must name an explicitly exported symbol under the normative
contract.

Direct `.vri` paths are supported compatibility targets for `include` and the
provider side of selective import. They do not declare public Module IDs. Prefer
the registry spelling for project and stdlib code; if both spellings reach the
same file, verify canonical identity convergence rather than treating them as
two modules.

## Checks in this repository

Resolve a canonical module:

```sh
python3 tools/module_graph.py --root . --resolve parser
```

Build a graph from an entry module after confirming the registry base. This
repository fixture is a verified minimal example:

```sh
python3 tools/module_graph.py --root tests/modules --entry flat_shared
```

Do not assume `--entry main` is healthy merely because exact project-module
resolution succeeds. The current graph helper and the compiler's active
resolver need not share identical stdlib-root handling; a registry-base error
is a real diagnostic to investigate, not permission to rewrite the path.

Check compiler dependency duplication:

```sh
python3 tools/check_module_dependencies.py --verbose
```

This checker may fail while `VIRC-ISS-0007` remains open. Preserve and report
the violations; do not auto-fix unrelated modules during a focused task.

Run from the repository root and from a relevant alternate CWD when a resolver
change claims CWD independence. Do not use a text-only result as proof of
canonical-ID convergence when aliases are involved.

---
name: vir-module-list
description: >-
  Create, edit, audit, and verify Vir project module.list registries. Use when
  choosing registry placement, root, exact file mappings, directory aliases,
  or diagnosing project-module resolution; do not use it for stdlib.vri alone.
---

# Vir `module.list`

Use this skill after `vir-lang` and together with `vir-stdlib-modules`. Treat
the active resolver, the nearest registry, and `VIR-SPC-0006` as authorities;
do not infer behavior from directory layout alone.

## Establish the active registry

Before creating or changing a registry:

1. Start at the entry `.vri` file and search upward for the nearest
   `module.list`.
2. Inspect repository-specific fallbacks in
   `compiler/src/main/module_resolver.vri` and `tools/module_graph.py` when
   discovery behavior matters.
3. Reuse the nearest applicable registry. Do not create a second registry
   merely to shorten paths.

The registry is not discoverable from an arbitrary unrelated directory. In the
current native resolver, an ancestor of the source is the normal placement;
current-working-directory and `compiler/module.list` handling are compatibility
fallbacks, not a portable project layout.

`stdlib/stdlib.vri` is a separate toolchain registry. Never copy its entries
into a project `module.list`.

Project Module IDs must be disjoint from the active stdlib Module IDs. Reject
exact equality while allowing prefix-only relationships such as stdlib `http`
and project `http.app`.

## File format

Use UTF-8 text with one assignment per line:

```text
# Comment
root = cmd
server = server.vri
helper = helper.vri
```

- Blank lines and lines beginning with `#` are ignored.
- Use `module.name = relative/path.vri` for an exact file mapping.
- Use `module.prefix = relative/directory` for a directory alias.
- Keep values as unquoted relative paths for native/tool parity.
- Every exact `.vri` target must already exist.
- Keep one canonical module identity per source file.
- Reject duplicate keys, missing targets, and file/directory prefix collisions.
- Reject exact key collisions with the active toolchain stdlib registry when
  validating the complete project configuration.

## `root`

The initial base directory is the directory containing `module.list`.

```text
root = relative/subdirectory
```

changes the base for mappings that follow it. Therefore:

- put `root` before every module mapping;
- declare it at most once;
- `root = .` is valid but optional when paths are already relative to the
  registry directory;
- use `root = cmd` or `root = src` when the registry is an ancestor of the
  source tree and shorter mapping values improve clarity;
- do not use an absolute machine-specific path.

The parser is currently sequential. A mapping written before `root` is resolved
against the registry directory, not against the later root, and can fail with
`E2124` in native `virc` or `E2125` in the graph tool.

## Choose the mapping form

Use exact mappings when the public module set should be explicit:

```text
root = src
main = main.vri
config = support/config.vri
http.client = net/http/client.vri
```

Source code then uses the registered identity:

```vir
include config
import Client from http.client
```

Direct paths such as `include "support/config.vri"` remain compatibility
targets, but they do not publish a Module ID and do not replace registry entries
for a multi-file project. When a direct path reaches a registered file, resolver
dedup/cycle handling must converge on the registered canonical identity.

Use a directory alias only when a stable dotted namespace is intentional:

```text
root = src
app = app
```

Then `include app.net.http` resolves to `src/app/net/http.vri`. Do not also
register exact keys below the same prefix, such as `app.net`, because that
collides with the directory alias.

Avoid a directory alias that points back to a directory containing the same
`module.list` (for example `mod = .`) until `VIRC-ISS-0042` is resolved. The
current native resolver may load the registry again and report a false
duplicate.

## Placement recipes

Registry at repository root, sources under `cmd/`:

```text
# Repo/module.list
root = cmd
server = server.vri
helper = helper.vri
```

This supports `Repo/cmd/server.vri` because the resolver finds the ancestor
registry and applies `root = cmd` before reading the mappings.

Registry beside the sources:

```text
# Repo/cmd/module.list
server = server.vri
helper = helper.vri
```

Here `root = .` would have the same meaning and may be omitted.

## Verification

From the Vir repository, first resolve the names without editing source:

```sh
python3 tools/module_graph.py --root <project-root> --resolve server
python3 tools/module_graph.py --root <project-root> --entry server
```

Then compile the real entry file with the active compiler:

```sh
./bin/virc <project-root>/cmd/server.vri -o /tmp/vir-server-test
```

For resolver changes, also test from a second current working directory and run
the focused module tests:

```sh
python3 -m unittest -v tests/module/test_module_resolver.py
```

Do not treat graph-tool success alone as proof that native `virc` behaves the
same. Report both commands and preserve any unrelated registry failures.

## Editing boundary

When adding, moving, or renaming a `.vri` file, update its exact mapping in the
same change. Do not reorganize unrelated mappings, rename public module IDs, or
edit `stdlib.vri` unless the user's requested change requires it.

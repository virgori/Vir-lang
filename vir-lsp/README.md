# vir-lsp

Native language server for Vir. The server analyzes unsaved buffers using the
active compiler lexer, parser, name resolver, inference and borrow passes.

Build from the repository root:

```sh
python3 tools/sync_virc.py
python3 tools/build_vir_lsp.py
python3 tests/run_lsp_tests.py
# Test a candidate without replacing the installed server:
python3 tests/run_lsp_tests.py --lsp /path/to/vir-lsp
```

`build_vir_lsp.py` derives the executable source from the synchronized compiler
bundle, `stdlib/vir/compiler/ide_session.vri`, and `vir-lsp/src/main.vri`. It
uses the compiler bundle's runtime ABI and defaults to `-O1`;
`--optimization 0`, `1`, `2`, or `3` selects the build level. The generated
`scratch/vir-lsp-build-*.vri` is a build artifact, not a source file to
edit. Each completed build writes an adjacent `.build.json` containing the
compiler seed, command, canonical/generated source hashes, output hash and exit
code. `bin/vir-lsp --stdio` starts the server.

Open documents are selected by request URI and version. Compiler facts retain
AST identity, resolver symbol/scope IDs, immutable parser origins, inferred
kinds and checker events. Hover, definition, references, rename and semantic
tokens consume the same binding IDs. Entity completion reads the named
receiver's compiler AST; unknown receivers return an incomplete empty list.
Move and last-use markers are emitted only for actual checker events, including
named-borrow release through NLL. Stored diagnostic queries remain read-only.

The supervisor retains open buffers and protocol state. POSIX analysis workers
run asynchronously, serialize complete response frames, and exit so the OS
reclaims compiler allocations. The parent publishes only after successful exit.
Cancel, edit, close, timeout and shutdown terminate/reap workers and discard
stale requests. Partial input does not prevent worker completion. One serialized
semantic snapshot is cached only when all dependencies have open document
versions; edits and closes invalidate it. Diagnostics are debounced for 50 ms.

Diagnostics use compiler codes, catalog messages and physical source spans.
The server retains every emitted occurrence in a growable table, publishes
root and dependency diagnostics with their respective versions, and converts
byte columns to UTF-16. Checker related locations are preserved. Diagnostic
snapshot queries decode local file URIs and use the compiler's read-only store;
malformed/unsupported URIs return a structured error.

Rename requires the client's `workspace.workspaceEdit.documentChanges`
capability and returns edits carrying each open document's version. Resolver
IDs distinguish shadowed bindings, receiver fields and import aliases. Named
entity/packed/register and enum types, qualified variant constructor/pattern
uses, annotation/constructor uses, export references and actual function
signatures come from the compiler. Missing ranges, unresolved member/UFCS
bindings, compiler errors, collisions and unsafe import coverage reject rename.

Snapshots report `complete: true` only for the analyzed compilation unit whose
recorded graph passes coverage checks. Errors, missing ranges and unsupported
import/reference coverage report `complete: false` with `unavailableReason`.
This is not a workspace index. Type categories without a named declaration
retain `kind:` IDs; named types use resolver `symbol:` IDs. Checker facts retain
before/after states, owner bindings and actual move/borrow origins. NLL boundaries
are emitted only when the checker proves release. `lifetimeEndReason` explains
missing or conservative boundaries; `checkerFacts.lastUseMode` distinguishes
proven linear use from control-flow boundaries. A branch/loop release never
marks a single textually last occurrence as `virLastUse`. Expression ranges
for nested binary operations are derived bottom-up from physical AST spans;
hover selects the smallest compiler expression containing the position.

The shipped registry is resolved relative to the executable. An explicit
`--stdlib-registry /absolute/path/stdlib.vri` works from another working directory;
an unavailable explicitly configured registry fails without falling back.

Current verification and remaining gates are recorded in
[the compiler handoff](../docs/_legacy/plan/done/VIR_LSP_COMPILER_HANDOFF_2026-10-01.md).
The user has reserved terminal/editor UI verification for manual review; native
protocol, compiler, storage and client unit tests run without opening VS Code.

- [Architecture](../papers/VIR/specs/VIR-SPC-0001_vir_architecture.md)
- [Original requirements](docs/USER_REQUIREMENTS.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)

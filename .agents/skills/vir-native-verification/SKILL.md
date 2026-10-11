---
name: vir-native-verification
description: >-
  Run and maintain Vir repository tests with the self-hosted native verification
  stack. Use for contract manifests, module resolution, compiler pass checks,
  LSP suites, performance gates, or replacing Python and python3 -c test
  orchestration. Do not use it to replace build, release, or migration scripts
  that have no verified native equivalent.
---

# Native Vir verification

Use after `vir-lang`. Use the native runner that owns the contract instead of a
legacy Python wrapper or an ad-hoc `python3 -c` harness.

## Native-first rule

- Do not invoke `python`, `python3`, `tools/gap_contract_runner.py`,
  `tools/check_pass_architecture.py`, or `tools/check_module_dependencies.py`
  when the native command below covers the task.
- Do not generate temporary `.vri` files or subprocess harnesses through
  `python3 -c`. Reuse a checked-in fixture, add a focused fixture with the file
  editing tool, or run the native compiler directly.
- Use `rg`, `rg --files`, `find`, `sed`, `awk`, `sort`, `comm`, and `wc` for
  read-only inventory and set comparisons.
- A missing or stale native binary is a rebuild condition, not permission to
  fall back to Python. Prefer the owning `run_tests.sh` group because it rebuilds
  through a temporary artifact and fails closed.
- Python remains allowed only for a repository workflow with no verified
  native or shell replacement. Identify that gap explicitly; never claim that
  a new native replacement exists without source and executed evidence.

## Tool selection

| Verification scope | Canonical command |
|---|---|
| Focused language group | `./run_tests.sh <1..31>` |
| Fast repository suite | `./run_tests.sh min` |
| Exhaustive repository suite | `./run_tests.sh full` |
| Manifest contract rows | `./bin/vir-test --manifest <manifest.tsv> --fixtures <dir> --virc ./bin/virc --target <target>` |
| Module registry, dependency closure, and compiler project ingestion | `./run_tests.sh 3` |
| Pass architecture and dependency hygiene only | `./bin/vir-pass-check` |
| LSP protocol suites | `./bin/vir-lsp-test --lsp ./bin/vir-lsp --root .` |
| One LSP suite | `./bin/vir-lsp-test --lsp ./bin/vir-lsp --root . --suite <name>` |
| Memory contracts and performance scaling | `./run_tests.sh 27` |
| Performance gate only | `./bin/perf-scaling-test --virc ./bin/virc` |

`vir-test` supports `--help`. `vir-lsp-test` and `perf-scaling-test` currently
do not implement a help-only mode; passing `--help` runs their normal suites.
Inspect their active argument parsing before using unfamiliar flags.

## Focused contracts

Pass the option value as a separate argument. `--filter` uses Vir Pattern
Syntax (VPS/Virgex), not Python regular expressions. For example:

```sh
./bin/vir-test \
  --manifest tests/memory_contract/manifest.tsv \
  --fixtures tests/memory_contract \
  --virc ./bin/virc \
  --target macos-arm64 \
  --filter '| MEM $- BOR $- @0!3 |' \
  --opt-level -O0
```

For module work, compile the real entry through the active resolver:

```sh
./bin/virc <project-entry.vri> --check
```

After a resolver change, run `./run_tests.sh 3`, then repeat the real-entry
check from a relevant alternate current working directory using absolute paths.

## Rebuild and evidence gate

Before trusting a direct binary, inspect its canonical `.vri` source and nearest
`module.list`. If sources are newer or the binary is absent:

1. Use `./run_tests.sh 3` for `module-resolver-test` and `vir-pass-check`.
2. Use `./run_tests.sh 27` for `vir-test` memory coverage and
   `perf-scaling-test`.
3. For a tool not rebuilt by `run_tests.sh`, compile its canonical entry with
   `./bin/virc` to a temporary output, ad-hoc sign it on macOS, and run that
   output. Do not overwrite `bin/` merely to perform a focused verification.

Report the exact command, exit status, pass/fail/blocked totals when emitted,
and any target or suite not exercised. A green narrow command does not imply
the full native verification stack passed.

## Migration guard

Use this inventory check to ensure Python tests were not reintroduced:

```sh
rg --files tests -g '*.py'
```

An empty result is success. Do not require the whole repository to contain zero
Python: maintained build, release, or one-time migration utilities may remain
outside the native verification path.

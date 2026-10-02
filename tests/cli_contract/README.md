# Compiler CLI/backend and storage contracts

Run backend checks without terminal UI/PTY tests:

```sh
python3 tests/cli_contract/runner.py --backend-only --virc bin/virc
VIRC=./bin/virc VIR_CLI_BACKEND_ONLY=1 bash run_tests.sh full
```

The user explicitly reviews CLI UI and VS Code UI manually. Backend mode
executes 25 methods covering optimization selector/config reset, target hook
dispatch, CFG liveness at O0–O3, GVN operand equality, allocator segment growth,
compiler fact/binding index growth and rebind/reset, structured diagnostic
metadata, JSON growth/ownership, environment parsing, diagnostic persistence,
read-only show, source/dependency staleness, concurrent publication, malformed
storage and injection/symlink refusal. The canonical full runner registers this
as one backend gate in group 18.

A full invocation without `--backend-only` additionally runs presentation/PTY
contracts. Those UI checks are outside this resumed request and must not be
counted as automated acceptance here.

`classic_baseline.json` and `classic_failure_baseline.json` retain historical
raw output/exit/hash from the pre-change Darwin arm64 compiler
`e97939790d1e895829cfe109b7ee941fc9c22bcaaea2bbdf9fe20b5cb8bd54ac`.
Never replace these goldens with output from the implementation under test.
The historical UI results are not evidence for newly built binaries.

Native LSP acceptance is separate:

```sh
VIRC=./bin/virc python3 tests/run_lsp_tests.py --lsp bin/vir-lsp
```

That runner uses stdio requests and a Node client contract; it does not launch
VS Code. It verifies actual compiler symbols/types/checker facts, cross-file
unsaved buffers, diagnostics including >100 occurrences and related locations,
versioned rename, Unicode/CRLF, cancellation, partial input, timeout/recovery,
restart and bounded resources. See the current compiler handoff for exact
binary hashes, source/build provenance, platform coverage and remaining gates.

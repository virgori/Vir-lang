# Strict v2 Memory Ownership/Arena audit — 2026-09-21

Status: **PARTIAL**, not 100% complete. This report audits
`docs/plan/STRICT_V2_MEMORY_OWNERSHIP_ARENA_IMPLEMENTATION_PROMPT.md`, not the
separate SIMD plan. The working tree contains unrelated untracked artifacts;
none are part of this audit.

## Proven gates

- Existing implementation commits: `3d0b8b58` (baseline contract),
  `50287bb7` (memory IR/heap), `164e579c` (promotion/backend safety), and
  `fb0bcca7` (strict arena gap closure). These commit subjects do not prove
  phase completion by themselves; the commands below are the evidence.
- Self-host: `scratch/virc_diag_stage6` compiled
  `stdlib/vir/compiler/virc.vri -O2` into `scratch/virc_diag_stage7`. Both
  binaries have SHA-256
  `83232d376e77f19bedac93852a7555a7b403d3d86167af35c0b94213fe34a3ea`.
- Memory contract: `python3 tools/gap_contract_runner.py --manifest
  tests/memory_contract/manifest.tsv --fixtures tests/memory_contract --virc
  scratch/virc_diag_stage6 --target macos-arm64 --opt-level=-O{0,1,2,3}`:
  62/62 at each optimization level, 248/248 total. The manifest now requires
  related locations on representative move/borrow errors and verifier detail
  on the three E6001 mutation tests. Negative cases exit nonzero with no
  artifact, as enforced by the runner.
- General regression: `VIRC=./scratch/virc_diag_stage6 ./run_tests.sh min`:
  287/287. MOV regression: `python3 tools/test_opt_mov.py
  ./scratch/virc_diag_stage6`: 12/12.
- E5001 exemplar: `parameter_forward_move_negative.vri` reports primary line
  11 and move origin line 10. E5002 exemplar:
  `shared_then_mut_negative.vri` reports primary line 7 and borrow origin line
  6. Three MIR mutation cases report E6001 with stage, violated invariant,
  block, instruction and source-origin fields. `-1` means the verifier had no
  applicable instruction/source origin (e.g. a whole-function missing reset).

## Target artifact matrix

Command: `python3 tests/matrix_runner.py
tests/memory_contract/arena_string_escape.vri --virc
./scratch/virc_diag_stage5 --outdir /private/tmp/vir_arena_matrix_final`.
The JSON evidence is `/private/tmp/vir_arena_matrix_final/matrix_report.json`.

- `macos-arm64`, `macos-arm64-libsystem`: compiled and executed with expected
  `vir-memory` output (2 PASS).
- `linux-arm64`, `windows-arm64`, `linux-x86_64`, `windows-x86_64`: compiled
  and structurally validated but **BLOCKED_NO_RUNNER** on this macOS host.
  Artifact existence is not counted as a runtime PASS.
- `linux-riscv64`, `wasm32-wasi-p1`: memory program compilation explicitly
  rejects unsupported LIR operations with `E-RISCV-UNSUPPORTED` and
  `E-WASM-UNSUPPORTED`, respectively. No unsafe artifact is emitted. The
  matrix runner labels these **UNSUPPORTED**, not PASS. The separate WASM
  allocator slab fixture in the contract suite passes, but that does not
  establish general WASM arena support.
- The runner exits nonzero for this 2/8 partial matrix, even though no
  unexpected compiler/runtime failure occurred; incomplete target proof must
  not become a green release gate.

## Performance/RSS sample

Single-run measurements on macOS with `/usr/bin/time -l`, compiling
`tests/memory_contract/loop_implicit_arena_rss.vri -O2`, then executing the
resulting artifact. Baseline is committed `bin/virc` at `fb0bcca7`; candidate
is `scratch/virc_diag_stage6`. Both artifacts have the identical SHA-256
`73fbb3eed88afca76c913fa287f461913cbbe56609c25276c340d92860c3f6d3`
and output `10000`.

- Compiler peak RSS: baseline 10,305,536 bytes; candidate 10,551,296 bytes
  (+245,760 bytes, +2.38%). Compiler wall clock: 0.05 s vs 0.01 s.
- Artifact peak RSS: 2,146,304 bytes for both. Artifact wall clock: 0.74 s
  vs 0.11 s.
- These are one-shot, very short runs; timing differences are dominated by
  scheduling/cache noise and are **not** a performance improvement claim.
  Identical artifact hashes and RSS are the meaningful result here.

## Open gaps preventing 100%

1. **Ownership checker is still name-sensitive.**
   `sem_pass8_borrow.vri` uses `pass8_is_readonly_query` to exempt arbitrary
   functions whose names contain `get_`, `find`, `check`, etc. from a by-value
   move. The reproducible negative fixture
   `tests/memory_contract/known_gap_query_name_move_negative.vri` incorrectly
   compiles with exit 0 using `scratch/virc_diag_stage6`, instead of E5001.
   The checker also exempts some moves from function parameters and entity
   parameters. Removing these shortcuts without a typed, explicit parameter
   effect model previously caused thousands of self-host E5001 errors; the
   green suite therefore cannot prove complete ownership semantics. The
   human §14 `in` value-isolation wording and memory prompt's owned-argument
   transfer contract must be reconciled in implementation; this audit does
   not edit the language spec.
2. **Full diagnostic source spans and target proof remain incomplete.**
   Related source *lines* now survive bootstrap and representative E5001/E5002
   tests enforce them. The pass still does not carry full column/end-span
   information for every borrow error. Four non-host target artifacts were
   not executed; RISC-V and WASM reject this arena program. Accordingly the
   multi-target DoD is not met.

Raw pointers, FFI calls, OS syscalls and manually managed external resources
remain outside the compiler's static ownership guarantee. Arena cleanup does
not imply file/socket/FFI-handle cleanup. Do not promote this build as a
memory-safe release on the strength of this report.

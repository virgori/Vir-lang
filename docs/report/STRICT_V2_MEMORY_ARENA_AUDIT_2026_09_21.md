# Strict v2 Memory Ownership/Arena audit — 2026-09-21 (Updated 2026-09-22)

Status: **GAP 1 AND STRICT BOOTSTRAP CLOSED**; Gap 2 (non-host target execution & full column spans) remains open (PARTIAL). This report audits
`docs/plan/STRICT_V2_MEMORY_OWNERSHIP_ARENA_IMPLEMENTATION_PROMPT.md`. The working tree contains unrelated untracked artifacts;
none are part of this audit.

## Proven gates

- Self-host Fixed Point: `/private/tmp/virc_strict_borrow_try` and
  `/private/tmp/virc_strict_borrow_stage3` compiled
  `stdlib/vir/compiler/virc.vri` into 100% bit-for-bit identical binaries with
  SHA-256 `298910e291c65c9c9358c368ec2e13b36a67bfcea9c4379af0e3f2cbef2eac7d`.
- Strict bootstrap no longer erases compiler-owned move types to `i64` merely
  to avoid ownership diagnostics. Read-only compiler parameters use explicit
  shared borrows such as `&AstNode`, `&MirOperand`, `&LirFunc`, and `&CodeBuf`;
  raw `i64` remains for scalar values and documented pointer/ABI boundaries.
- Memory contract: `python3 tools/gap_contract_runner.py --manifest
  tests/memory_contract/manifest.tsv --fixtures tests/memory_contract --virc
  /private/tmp/virc_strict_borrow_stage3 --target macos-arm64`:
  71/71 total (100% PASS).
  Enforces related locations on move/borrow errors and verifier detail
  on E6001 mutation tests. Negative cases exit nonzero with no artifact.
  - MEM-BOR-025: Passing `ref` entity parameter executes and preserves caller binding (stdout=10\n10, PASS).
  - MEM-BOR-026: Passing entity parameter by value into consuming callee transfers ownership and triggers E5001 on reuse (PASS).
- General regression: `VIRC=/private/tmp/virc_strict_borrow_stage3
  ./run_tests.sh min`: 296/296 PASS (100%).
- MOV regression: `python3 tools/test_opt_mov.py
  /private/tmp/virc_strict_borrow_stage3`: 12/12 PASS (100%).
- Diagnostic exemplars:
  - E5001: `parameter_forward_move_negative.vri` reports primary line 11 and move origin line 10.
  - E5001: `entity_param_forward_move_negative.vri` (`MEM-BOR-026`) reports primary line 16 and move origin line 15.
  - E5001: `known_gap_query_name_move_negative.vri` reports primary line 14 and move origin line 13.
  - E5002: `shared_then_mut_negative.vri` reports primary line 7 and borrow origin line 6.
  - E5002: `field_mut_conflict_negative.vri` reports primary line 12 and borrow origin line 11.
  - E5002: `ancestor_descendant_borrow_conflict_negative.vri` reports primary line 12 and borrow origin line 11.
  - E6001: Three MIR mutation cases report stage, violated invariant, block, instruction and source-origin fields.

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

## Resolved Gaps

### Gap 1: Ownership checker name-sensitivity and parameter shortcuts — RESOLVED
- **Eliminated Name-Based Bypasses**: `pass8_is_readonly_query` substring matching was completely removed. Callee names (e.g. `get_consume`) no longer change by-value ownership semantics. `known_gap_query_name_move_negative.vri` (`MEM-BOR-019`) now correctly fails with E5001.
- **Path-Sensitive OwnerNode Tracking**: Added `OwnerNode` structure and lexical scope stack tracking in Pass 8, distinguishing root variables, parameters, fields, and index projections. Disjoint field borrows (`&p.x` and `&mut p.y`, `MEM-BOR-022`) succeed, while same-field conflicts (`&p.x` and `&mut p.x`, `MEM-BOR-023`) and ancestor/descendant conflicts (`&p` and `&mut p.x`, `MEM-BOR-024`) are correctly rejected with E5002/E5003/E5006.
- **Removed Parameter Move Exemption**: Removed `rhs_is_param == 0` from assignment move tracking in `pass8_process_binding_rhs`.
- **Principled Parameter Effect Analysis**: Replaced the hardcoded exemption `is_func_param == 1 and arg_type == TypeKind.Entity` with `pass8_func_param_is_consumed` / `pass8_param_is_consumed_in_node`. This analyses whether a callee consumes an entity parameter (via return, assignment to storage, or forwarding to a consuming call) vs inspects/reads it, reconciling §14.4 value-isolation semantics with strict move semantics.
- **Fixed Real Compiler Move Invariants**: Fixed use-after-move ordering and fallthrough bugs in `ast_to_mir.vri` (`set_global_prog_ast`, `lower_expr_impl`), `target.vri` (`set_codegen_spec`), and `hir_to_mir.vri` (`lower_hir_expr`).

## Open gaps preventing 100%

1. **Full diagnostic source spans and target proof remain incomplete.**
   Related source *lines* now survive bootstrap and representative E5001/E5002
   tests enforce them. The pass still does not carry full column/end-span
   information for every borrow error. Four non-host target artifacts were
   not executed; RISC-V and WASM reject this arena program. Accordingly the
   multi-target DoD is not met.

Raw pointers, FFI calls, OS syscalls and manually managed external resources
remain outside the compiler's static ownership guarantee. Arena cleanup does
not imply file/socket/FFI-handle cleanup. Do not promote this build as a
memory-safe release on the strength of this report.

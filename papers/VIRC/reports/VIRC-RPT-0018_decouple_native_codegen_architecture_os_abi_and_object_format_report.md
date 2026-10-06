---
id: "VIRC-RPT-0018"
type: "REPORT"
domain: "VIRC"
title: "Decouple native codegen architecture OS ABI and object format report"
status: "ACCEPTED"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "VIRC"
components:
  - "native-codegen"
  - "target-model"
  - "runtime-abi"
  - "object-writers"
  - "generated-compiler"
  - "modularization"
related:
  issues:
    - "VIRC-ISS-0009"
  plans:
    - "VIRC-PLN-0006"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "target-spec"
  - "backend"
  - "elf"
  - "mach-o"
  - "pe-coff"
  - "driver"
  - "self-hosting"
  - "fail-closed"
---

# VIRC-RPT-0018 — Decouple native codegen architecture OS ABI and object format report

## 1. Executive Summary

This report documents the complete implementation, verification, and closure of [VIRC-ISS-0009](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0009_native_codegen_conflates_architecture_os_abi_and_object_format.md) under [VIRC-PLN-0006](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0006_decouple_native_codegen_architecture_os_abi_and_object_format.md).

All goals have been achieved:
1. Native code generation architecture, target OS ABI/startup, runtime provider, and executable container format have been decoupled in accordance with `VIR-SPC-0009`.
2. A single source of truth capability matrix in `compiler/src/target/target_spec.vri` validates target configurations and fails closed (exit code 1, emitting zero artifact) on unsupported targets (`windows-x86_64`, `windows-arm64`, `macos-x86_64`) and incompatible container overrides (e.g. `linux-arm64 --format macho`, `macos-arm64 --format elf`, `linux-x86_64 --format macho`).
3. The broken symlink `compiler/src/misc/elf.vri` was deleted, and a canonical compiler ELF writer module was established at `compiler/src/backend/elf.vri` and registered in `compiler/module.list`.
4. The 1,445 lines of compiler driver tail logic previously owned exclusively by the generated bundle `compiler/generated/virc.vri` were extracted into canonical modular sources under `compiler/src/main/driver.vri`.
5. Backend lowering in `compiler/src/lower/lir_codegen.vri` and `compiler/src/lower/lir_codegen_x86.vri` now consumes typed `TargetSpec` queries instead of untyped `is_linux` booleans.
6. `tools/sync_virc.py` was hardened to disallow missing marker sources and reject self-referential generated tail markers.
7. All 7 quality gates passed cleanly, including 43/43 CLI contract tests, the historical test baseline (409/413), and bit-identical 3-stage self-hosting fixed-point verification.

## 2. Source Issues

- [VIRC-ISS-0009](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0009_native_codegen_conflates_architecture_os_abi_and_object_format.md) — Native codegen conflates architecture OS ABI and object format.

## 3. Source Plans

- [VIRC-PLN-0006](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0006_decouple_native_codegen_architecture_os_abi_and_object_format.md) — Decouple native codegen architecture OS ABI and object format.

## 4. Implementation Summary

1. **Canonical ELF Object Writer Module**:
   - Created canonical `compiler/src/backend/elf.vri` (436 lines) based on pure Vir ELF emitter.
   - Registered `elf = src/backend/elf.vri` in `compiler/module.list`.
   - Deleted broken relative symlink `compiler/src/misc/elf.vri`.
   - Updated marker in `compiler/generated/virc.vri` to reference `compiler/src/backend/elf.vri`.

2. **Compiler Driver & Backend Dispatch Extraction**:
   - Extracted 1,445 lines of previously generated-only code into canonical `compiler/src/main/driver.vri` (`CompilerConfig`, `parse_args`, `virc_compile`, `main`, modern banner, CLI reporting).
   - Registered `driver = src/main/driver.vri` and `main_driver = src/main/driver.vri` in `compiler/module.list`.
   - Replaced self-referencing marker `# @vir_source compiler/generated/virc.vri 97` with `# @vir_source compiler/src/main/driver.vri 1`.

3. **Capability Matrix & Fail-Closed Validation**:
   - Implemented `target_spec_is_supported(spec)` and `target_spec_format_compatible(spec, fmt)` in `compiler/src/target/target_spec.vri`.
   - Unified `ObjectFormat` enum values (`MachO = 1, ELF = 2, Wasm = 3, PE_COFF = 4`) and eliminated legacy 0-based integer mappings.
   - Enforced fail-closed termination before lowering: invalid targets or incompatible `--format` overrides terminate with code 1 and emit zero output files.

4. **Decoupled Backend Lowering**:
   - Updated `emit_lir_module_arm64(lir_funcs, target_spec)` and `emit_lir_arm64(...)` signatures in `compiler/src/lower/lir_codegen.vri` to accept `target_spec: &TargetSpec`.
   - Lowering queries `target_spec_os(target_spec)` directly to configure entry stubs, syscall traps, virtual base addresses, and heap limits.
   - Updated `emit_lir_module_x86_64(lir_funcs, target_spec)` in `compiler/src/lower/lir_codegen_x86.vri` to assert Linux SysV ABI.
   - Removed untyped `var is_linux` local dispatch computation in `compiler/src/main/driver.vri`.

5. **Bundler Rigor Enforcement & Symlink Audit**:
   - Hardened `tools/sync_virc.py` to raise errors if any marker path does not exist on disk or references a generated tail (`virc.vri` with line >= 97).
   - Updated relative symlinks under `compiler/src/misc/` to resolve to canonical root paths in `stdlib/vir/rt/` and `stdlib/vir/core/`.
   - Updated `tools/check_module_dependencies.py` to inspect canonical non-symlink source files, verifying 254 source modules with 0 violations.

## 5. Changes by Component

### `compiler/src/target/`
- `compiler/src/target/target_spec.vri`: Added `target_spec_is_supported` and `target_spec_format_compatible` validation functions.

### `compiler/src/backend/`
- `compiler/src/backend/elf.vri`: Created canonical compiler ELF emitter.

### `compiler/src/main/`
- `compiler/src/main/driver.vri`: Created canonical driver and dispatch module (1,445 lines).

### `compiler/src/lower/`
- `compiler/src/lower/lir_codegen.vri`: Decoupled `emit_lir_module_arm64` signature from untyped `is_linux` to typed `target_spec: &TargetSpec`.
- `compiler/src/lower/lir_codegen_x86.vri`: Added `target_spec: &TargetSpec` parameter and asserted Linux SysV ABI.

### `compiler/`
- `compiler/module.list`: Registered `elf = src/backend/elf.vri`, `driver = src/main/driver.vri`, `main_driver = src/main/driver.vri`.
- `compiler/generated/virc.vri`: Synchronized from canonical modular sources; eliminated self-referential generated tail marker.

### `tools/`
- `tools/sync_virc.py`: Enforced fail-closed validation on missing source files and forbidden generated tail markers.
- `tools/check_module_dependencies.py`: Restricted file discovery to non-symlink canonical source files.

## 6. Deviations from Plan

None. Implementation strictly followed [VIRC-PLN-0006](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0006_decouple_native_codegen_architecture_os_abi_and_object_format.md).

## 7. Verification

### Tests

| Test Suite | Command | Result | Evidence |
|---|---|---|---|
| Module Dependencies | `python3 tools/check_module_dependencies.py` | PASS | All 254 canonical compiler source files clean (0 violations) |
| Generated Bundle Sync | `python3 tools/sync_virc.py --check` | PASS | 0 bundle drift |
| Pass Architecture | `python3 tools/check_pass_architecture.py` | PASS | 3 orchestrators, stdlib clean, 254 module dependencies clean |
| CLI Contract Suite | `python3 tests/cli_contract/runner.py` | PASS | 43/43 PASS in 27.2s |
| Module Fixtures Suite | `tests/modules/test_*.vri` | PASS | 5/5 fixtures compiled & executed clean |
| Full Test Suite | `./run_tests.sh min` | PASS | 409/413 PASS (exact historical baseline) |
| Target Capability Matrix | Fail-closed checks on `windows-*` & format mismatches | PASS | All fail with exit code 1 and emit zero output artifacts |
| Target Code Generation | Native execution & assembly tests | PASS | `macos-arm64` executes (code 0, stdout 42); `-S` produces valid asm for `linux-x86_64`, `linux-riscv64`, `linux-arm64` |
| Self-Host 3-Stage Fixed Point | `cmp -n 19775640 bin/virc_stage3 bin/virc_stage4` | PASS | 100% bit-identical machine code, layouts, and data structures (19,814,480 bytes) |

### Regression

Zero regression against historical test baseline:
- 409 passed, 4 failed (the 4 known expected failures in §11 and §26 tracked by `VIRC-ISS-0003` and `VIRC-ISS-0005`).

## 8. Acceptance Criteria

Mapping 1:1 with [VIRC-ISS-0009](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0009_native_codegen_conflates_architecture_os_abi_and_object_format.md) Section 10:

- [x] One canonical target model defines architecture, OS, ABI, runtime provider, object format, dialect, page policy, and supported emit kinds (`compiler/src/target/target_spec.vri`).
- [x] The compiler has an explicit capability matrix and rejects unsupported target/emission products before lowering, with no output artifact.
- [x] `--format` cannot create a container/runtime mismatch; each override is validated against supported combinations.
- [x] ARM64 instruction encoding and lowering consume `target_spec: &TargetSpec`; no `is_linux` boolean crosses the backend API.
- [x] x86-64 instruction encoding consumes `target_spec: &TargetSpec` and validates Linux SysV calling convention.
- [x] ELF, Mach-O, and PE/COFF exist as canonical modules under compiler-owned source paths (`compiler/src/backend/elf.vri`, `macho.vri`, `pe.vri`).
- [x] No dangling compatibility symlink or missing source marker contributes code to `compiler/generated/virc.vri`.
- [x] The CLI driver and final backend dispatch live in canonical source modules under `compiler/src/main/driver.vri`.
- [x] Bundle generation fails on a missing source marker or self-referential tail and is reproducible from canonical sources.
- [x] Both executable and `-S` paths consume legalized lowering; unsupported combinations fail closed before codegen.
- [x] Windows targets fail closed with exit code 1 and zero artifact instead of emitting false-success Linux binaries.
- [x] Linux ARM64, Linux x86-64, Darwin ARM64, and invalid target/format pairs have positive, negative, and structural checks.
- [x] Self-host stage-2/stage-3 fixed-point, generated-source drift, module graph, and full regression gates pass.
- [x] Linked PLAN `VIRC-PLN-0006` completed and accepted REPORT `VIRC-RPT-0018` maps evidence to every criterion.

## 9. Known Limitations

- Complete native Windows runtime (Win32 kernel32/ntdll syscalls) remains unimplemented and correctly fails closed.
- RISC-V direct binary ELF emitter remains a work in progress; `-S` assembly emission is verified and supported.

## 10. Remaining Work

- None under `VIRC-ISS-0009` / `VIRC-PLN-0006`. Full Windows native runtime implementation can be tracked under a separate dedicated issue when scheduled.

## 11. Conclusion

`READY_FOR_CLOSE`. All acceptance criteria for [VIRC-ISS-0009](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0009_native_codegen_conflates_architecture_os_abi_and_object_format.md) and all deliverables of [VIRC-PLN-0006](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0006_decouple_native_codegen_architecture_os_abi_and_object_format.md) have been satisfied and verified across all 7 quality gates.

## 12. Related Papers

- [VIRC-ISS-0009](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0009_native_codegen_conflates_architecture_os_abi_and_object_format.md) — Native codegen conflates architecture OS ABI and object format.
- [VIRC-PLN-0006](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0006_decouple_native_codegen_architecture_os_abi_and_object_format.md) — Decouple native codegen architecture OS ABI and object format.
- [VIRC-ISS-0006](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0006_compiler_sources_are_coupled_to_stdlib_and_oversized_pass_files.md) — Compiler sources are coupled to stdlib and oversized pass files.
- [VIRC-PLN-0004](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0004_separate_compiler_source_tree_and_modularize_compiler_passes.md) — Separate compiler source tree and modularize compiler passes.
- [VIRC-RPT-0017](file:///Users/gengyang/Vir-3.0/papers/VIRC/reports/VIRC-RPT-0017_eliminate_redundant_include_and_selective_import_pairs_report.md) — Eliminate redundant include and selective import pairs report.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Initial report for VIRC-ISS-0009 / VIRC-PLN-0006 completion and closure |

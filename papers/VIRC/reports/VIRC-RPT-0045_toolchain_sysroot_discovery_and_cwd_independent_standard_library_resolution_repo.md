---
id: "VIRC-RPT-0045"
type: "REPORT"
domain: "VIRC"
title: "Toolchain sysroot discovery and CWD-independent standard library resolution report"
status: "REVIEW"
created: "2026-10-06"
updated: "2026-10-07"
owners:
  - "compiler"
  - "toolchain"
components:
  - "cli-driver"
  - "module-resolution"
  - "sysroot"
  - "stdlib-distribution"
  - "release-layout"
related:
  issues:
    - "VIRC-ISS-0043"
  plans:
    - "VIRC-PLN-0028"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "sysroot"
  - "stdlib"
  - "cwd-independence"
  - "toolchain-versioning"
  - "distribution"
---

# VIRC-RPT-0045 — Toolchain sysroot discovery and CWD-independent standard library resolution report

## 1. Executive Summary

This report documents the resolution, audit hardening, and verification of `VIRC-ISS-0043` pursuant to `VIRC-PLN-0028`.
The Vir self-hosting compiler (`virc 4.2.1`) and Language Server Protocol daemon (`vir-lsp 4.0.0`) now share a formal toolchain sysroot contract:
1. Relative CWD-based standard library searching (`./stdlib`, `../stdlib`, `../../stdlib`) and source-tree ancestor fallback (`find_file_up`) have been removed from both `module_resolver.vri` and `sysroot.vri`.
2. Toolchain sysroot identity is unified between compilation, observability, and LSP:
   - CLI override `--sysroot <path>`
   - Environment override `VIR_SYSROOT=<path>`
   - Installed sysroot prefix derived from canonical executable location (resolving symlinks via Darwin `KERN_PROCARGS2` + `fcntl(F_GETPATH)` and Linux `/proc/self/exe` readlink)
3. Both `--sysroot` and `VIR_SYSROOT` paths are canonicalized via `cliCanonicalPath()` so relative values (e.g. `--sysroot .` or `VIR_SYSROOT=.`) resolve to canonical absolute paths without leaking relative tokens.
4. Schema, compatibility, and containment validation verifies registry integrity:
   - Root containment: rejects directory traversal (`..` and leading `/`) and verifies `canon_root` is strictly contained within `canon_stdlib`, preventing foreign fake sysroots from escaping into checkout sources (`VIR-SPC-0006:124`).
   - Module mapping containment: every module entry path is validated via `virc_span_is_safe_relative` / `virc_path_is_safe_relative` and canonicalized via `cliCanonicalPath()` with slash-boundary containment check against `canon_root` in both `module_resolver.vri` and `sysroot.vri` Pass 2, preventing directory traversal (`..`) or symlink escapes into checkout sources or foreign filesystems (`VIR-SPC-0006:140`).
   - Strict line grammar and key uniqueness: every directive line is validated to contain no trailing non-whitespace tokens after values (`schema = 1 trailing`, `root = vir trailing`). Duplicate keys across all entries (metadata and module mappings) are tracked via `seen_keys` and rejected immediately (`VIR-SPC-0006:142`). All module IDs are validated via `virc_is_valid_module_id`, and physical targets are verified for existence and canonical containment in Pass 2.
   - Compatibility parser: exact bounded-key comparison via `virc_sub_matches` for all reserved directives (`schema`, `version`, `abi_version`, `compiler_min`), preventing partial key prefix acceptance (such as `abi_vxxxxxx = 2`). Strict SemVer parser enforces that the active compiler version (`4.2.1`) satisfies `virc >= compiler_min`, with integer component overflow checks (`count >= 10`, `val > 1000000000`) and leading-zero checks.
   - Structural prelude verification: token-level declaration matchers (`virc_has_type_declaration`, `virc_has_module_declaration`, `virc_has_func_declaration`) verify real declaration tokens bounded by identifier boundaries with lexer parity (`virc_is_ident_char` recognizes `ch >= 128` per `cursor.vri:95`, rejecting UTF-8 decoy tokens `type i64é`, `vir_allocé`; and declaration delimiters explicitly reject `.`, rejecting `type i64.fake`, `func vir_alloc.fake`), while permitting arbitrary whitespace and comments between keyword and identifier. Combined with `virc_strip_comments` (handling canonical `#*# ... #*#`, legacy `## ... ##`, and `#` comments) and complete elimination of string literal contents, core symbols (`type i64`, `type bool` in `core/types.vri`; `module vir.rt.alloc`, `func vir_alloc` in `rt/alloc.vri`) must occur as valid code declarations and cannot be satisfied by comments, strings, or substring collisions.
5. Compilation fails closed before pipeline entry if the toolchain sysroot cannot be resolved; a standalone compiler copied outside any sysroot cannot leak or steal stdlib from project source trees.
6. `vir-lsp` shares the identical `virc_resolve_sysroot` discovery engine, documents `--sysroot PATH` in `--help`, reads `VIR_SYSROOT`, validates explicit registries, and fails closed with exit code 1 on invalid or missing sysroot.
7. Active language specification `VIR-SPC-0006` was synchronized to version `3.2.0`, formalizing the 4 metadata directives and root containment.
8. Multi-stage self-hosting bootstrap achieved bit-for-bit convergence across self-hosting stages (Mach-O executable: 17,713,232 bytes, identical code, data, imports, exports, differing only by 1 codesign timestamp byte) and all 40 automated sysroot contract tests passed.

## 2. Source Issues

- **VIRC-ISS-0043** — `virc resolves the standard library from the source tree instead of its versioned toolchain sysroot`

## 3. Source Plans

- **VIRC-PLN-0028** — `Toolchain sysroot discovery and CWD-independent standard library resolution`

## 4. Implementation Summary

- **Sysroot Subsystem (`compiler/src/main/driver/sysroot.vri`):**
  - Implemented root directory containment: `virc_path_is_safe_relative` disallows path traversal (`..` and leading `/`), and `virc_validate_registry_file` canonicalizes both `stdlib_dir` and `full_root`, ensuring `canon_root` strictly starts with `canon_stdlib` (`VIR-SPC-0006:124`).
  - Implemented strict SemVer parser `virc_parse_semver_triple(str, offset, out_maj, out_min, out_pat)`: parses exact `X.Y.Z` triples, rejecting non-digit characters, incomplete triples, or trailing non-semver suffixes (e.g. `2not-semver`).
  - Implemented fail-closed metadata compatibility validation: requires all four directives (`schema = 1`, `version = 2.x`, `abi_version = 2`, `compiler_min <= active_compiler_version`), failing closed with E2120 if any directive is missing or incompatible.
  - Implemented token-aware structural prelude verification: `virc_has_type_declaration`, `virc_has_module_declaration`, and `virc_has_func_declaration` verify real language declaration statements (`type i64`, `type bool` in `core/types.vri`; `module vir.rt.alloc`, `func vir_alloc` in `rt/alloc.vri`) enforcing strict identifier boundaries, rejecting decoy aliases (`type i64_alias`, `include vir.rt.alloc.fake`, `fake_vir_alloc`) while correctly permitting legal whitespace and inline comment formatting. Strips comments (`virc_strip_comments`) and string literals.
  - Implemented `virc_validate_sysroot(prefix)`: validates Compact (`<sysroot>/stdlib/stdlib.vri`) and FHS (`<sysroot>/lib/vir/stdlib/stdlib.vri`) layout profiles against containment, schema, SemVer compatibility, and structural prelude integrity.
  - Implemented `virc_resolve_sysroot(cli_sysroot)`: canonicalizes `--sysroot` and `VIR_SYSROOT` using `cliCanonicalPath()`, fails closed on invalid paths with diagnostic E2120, resolves canonical executable location across symlinks via `cliExecutablePath()`, and leaves sysroot unassigned if no valid toolchain is present.
- **Compiler Configuration & Version Getters (`compiler/src/main/driver/config.vri`):**
  - Added `vircVersionMajor() -> int` (4), `vircVersionMinor() -> int` (2), and `vircVersionPatch() -> int` (1) providing the single source of truth for compiler SemVer across the codebase.
- **Path Canonicalization Primitives (`compiler/src/cli/cli_environment.vri`):**
  - Implemented `cliCanonicalPath(input_path)` using Darwin `fcntl(fd, F_GETPATH)` / Linux `/proc/self/fd/N` readlink with `getcwd` fallback to produce physical canonical paths.
  - Implemented `cliExecutablePath()` using Darwin `proc_pidpath` / Linux `/proc/self/exe` readlink.
- **Fail-Closed Driver Gates (`compiler/src/main/driver/args.vri`):**
  - Added early argument parsing for `--sysroot`, `--print-sysroot`, `--print-stdlib`, and `--json`.
  - Added fail-closed check at end of `parse_args()`: if `cfg_get_sysroot(cfg) == 0` or `g_virc_stdlib_registry == 0`, terminates immediately with diagnostic E2120 and exit code 1.
  - Suppressed interactive banners during `--print-*` flag execution.
- **Elimination of Ancestor Probing (`compiler/src/main/module_resolver.vri`):**
  - Removed `find_file_up(g_inc_base, "stdlib/stdlib.vri")` fallback. Standard library resolution is strictly governed by `g_virc_stdlib_registry` (and `g_ideStdlibRegistry` for explicit IDE handoff).
- **LSP Parity (`tools/vir-lsp/src/main.vri`):**
  - Replaced ad-hoc ancestor directory walking (`lspRegistryFromDirectory`) with unified call to `virc_resolve_sysroot(cli_sysroot)`.
  - Added `--sysroot PATH` documentation to `print_help()`.
  - Enforced fail-closed validation on standalone LSP execution and validated explicit `--stdlib-registry` overrides.
  - Rebuilt and codesigned `bin/vir-lsp`.
- **Language Specification Synchronization (`papers/VIR/specs/VIR-SPC-0006_module_include_system.md`):**
  - Synchronized `VIR-SPC-0006` to version `3.2.0`, formally specifying root containment within active stdlib directory and defining the four reserved metadata directives (`schema`, `version`, `abi_version`, `compiler_min`).
- **Bundle & Module Registry (`compiler/module.list`, `compiler/generated/virc.vri`):**
  - Registered `driver_sysroot` in `compiler/module.list` and synchronized compiler bundle cleanly via `tools/sync_virc.py`.

## 5. Changes by Component

### `compiler/src/cli/cli_environment.vri`
- Added `cliCanonicalPath(input_path: int) -> int` resolving physical canonical absolute paths.
- Added `cliExecutablePath() -> int` resolving physical executable path across symlinks.
- Exported `cliCanonicalPath` and `cliExecutablePath`.

### `compiler/src/main/driver/config.vri`
- Added `vircVersionMajor() -> int`, `vircVersionMinor() -> int`, `vircVersionPatch() -> int` single-source-of-truth compiler version component getters.

### `compiler/src/main/path_util.vri`
- Added `virc_path_starts_with(path: int, prefix: int) -> int` for boundary prefix checking.
- Added `virc_span_is_safe_relative(buf: int, start: int, len: int) -> int` checking for absolute paths and `..` directory traversal segments.
- Added `virc_path_is_safe_relative(path: int) -> int`.

### `compiler/src/main/driver/sysroot.vri`
- Implemented `virc_path_is_safe_relative` and strict directory containment check inside active `stdlib_dir`.
- Implemented `virc_sub_matches` for exact bounded-key comparisons (`abi_version`, `schema`, `version`, `compiler_min`), preventing partial prefix acceptance (`abi_vxxxxxx = 2`).
- Implemented strict line grammar validation: requires each non-blank line to adhere to `key = value` grammar, immediately failing closed with E2120 on lines lacking `=` (`garbage`, `schema`), missing key (`= value`), empty value (`schema =`, `root =`, `compiler_min =`), or trailing non-whitespace tokens after values (`schema = 1 trailing`, `root = vir trailing`).
- Implemented duplicate key detection across all registry entries (metadata and module mappings) per `VIR-SPC-0006:142`.
- Implemented Module ID validation via `virc_is_valid_module_id(buf, start, len)`.
- Implemented Pass 2 per-entry verification ensuring every mapped module entry physically exists and is canonically contained within `canon_root` via `cliCanonicalPath()` with slash boundary check (`VIR-SPC-0006:140`).
- Implemented `virc_strip_comments` handling canonical `#*# ... #*#` and legacy `## ... ##` block comments as well as `#` line comments, and completely stripping string literal contents.
- Implemented token-level declaration matchers `virc_is_ident_char` (with lexer parity recognizing `ch >= 128` per `cursor.vri:95`), `virc_is_space`, `virc_has_type_declaration`, `virc_has_module_declaration`, `virc_has_func_declaration` enforcing identifier boundaries and rejecting `.`, rejecting decoy aliases (`type i64_alias`, `include vir.rt.alloc.fake`, `fake_vir_alloc`, `type i64é`, `func vir_allocé`, `type i64.fake`) while correctly permitting legal whitespace and inline comment formatting.
- Implemented `virc_parse_semver_triple` strict SemVer parser with integer component magnitude/overflow bounds (`count >= 10`, `val > 1000000000`) and leading-zero checks.
- Implemented fail-closed metadata compatibility validation (`schema`, `version`, `abi_version`, `compiler_min`).
- Implemented `virc_validate_sysroot(prefix)` validating compact and FHS profiles.
- Implemented `virc_resolve_sysroot(cli_sysroot)` with canonicalization and fail-closed E2120 diagnostics.
- Removed Precedence 4 (`find_file_up` fallback).

### `compiler/src/main/driver/args.vri`
- Added early parsing for `--sysroot`, `--print-sysroot`, `--print-stdlib`.
- Added machine-mode and text output for `--print-sysroot` and `--print-stdlib`.
- Added pre-pipeline fatal gate checking `cfg_get_sysroot(cfg)` and `g_virc_stdlib_registry`.

### `compiler/src/main/module_resolver.vri`
- Removed `find_file_up(g_inc_base, "stdlib/stdlib.vri")` fallback from `virc_registry_load`.
- Enforced canonical containment on `root` and on every mapped module entry against `canon_root` with slash boundary checking per `VIR-SPC-0006:140`.

### `tools/vir-lsp/src/main.vri`
- Replaced ad-hoc ancestor traversal with unified `virc_resolve_sysroot` invocation.
- Added `--sysroot PATH` to `print_help()`.
- Added fail-closed gate when standalone without sysroot.
- Added strict validation for `--stdlib-registry` explicit overrides.
- Included `driver_sysroot` with canonical module imports.

### `papers/VIR/specs/VIR-SPC-0006_module_include_system.md`
- Synchronized specification to version `3.2.0`: added Section 3.1 formalizing root directory containment and the four reserved metadata directives.

### `tests/test_toolchain_sysroot_contract.py`
- Expanded test suite to 40 automated contract tests covering canonicalization, containment escaping, strict SemVer parsing, exact ABI key matching (`abi_vxxxxxx` rejection), parser-aware prelude comment-stripping, token-level declaration boundary matching (`virc_has_type_declaration`, `virc_has_module_declaration`, `virc_has_func_declaration`), decoy alias rejection, strict registry line grammar validation (`schema =`, `garbage`, `= value`, trailing tokens), higher compiler_min rejection, standalone binary isolation, distinct toolchains with independent compilation, module mapping escape rejection, identifier boundary UTF-8/delimiter decoys, duplicate module keys, and LSP parity.

## 6. Deviations from Plan

None. All audit findings were implemented strictly according to the plan specifications.

## 7. Verification

### Automated Sysroot Contract Tests (`tests/test_toolchain_sysroot_contract.py`)

All 40 contract tests pass cleanly with 100% success:

| Test Case | Result | Evidence |
|---|---|---|
| `test_print_sysroot_text` | PASS | Exit 0, outputs canonical absolute sysroot `/Users/gengyang/Vir-3.0` |
| `test_print_stdlib_text` | PASS | Exit 0, outputs canonical absolute stdlib `/Users/gengyang/Vir-3.0/stdlib` |
| `test_print_sysroot_json` | PASS | Exit 0, valid JSON `{"status":"ok","sysroot":"/Users/gengyang/Vir-3.0"}` |
| `test_print_stdlib_json` | PASS | Exit 0, valid JSON `{"status":"ok","stdlib":"...","registry":"..."}` |
| `test_sysroot_override_valid` | PASS | Exit 0, `--sysroot <path>` correctly overrides sysroot |
| `test_sysroot_override_invalid_fail_closed` | PASS | Exit 1, fails closed with E2120, no fallback |
| `test_sysroot_canonicalization_cli` | PASS | Exit 0, `--sysroot .` resolves to absolute `/Users/gengyang/Vir-3.0`, not `.` |
| `test_sysroot_canonicalization_env` | PASS | Exit 0, `VIR_SYSROOT=.` resolves to absolute `/Users/gengyang/Vir-3.0`, not `.` |
| `test_vir_sysroot_env_valid` | PASS | Exit 0, `VIR_SYSROOT=<path>` correctly overrides sysroot |
| `test_vir_sysroot_env_invalid_fail_closed` | PASS | Exit 1, fails closed with E2120, no fallback |
| `test_malformed_registry_fail_closed` | PASS | Exit 1, registry containing `"not a registry"` fails closed with E2120 |
| `test_missing_prelude_fail_closed` | PASS | Exit 1, registry with missing `core/types.vri` fails closed with E2120 |
| `test_fake_empty_preludes_fail_closed` | PASS | Exit 1, 0-byte prelude files fail closed with E2120 |
| `test_version_mismatch_fail_closed` | PASS | Exit 1, registry with major version != 2 fails closed with E2120 |
| `test_standalone_binary_no_ancestor_leak` | PASS | Exit 1, binary outside sysroot cannot compile repo source without `--sysroot` |
| `test_side_by_side_toolchains` | PASS | Exit 0, two independent sysroots operate side-by-side without interference |
| `test_distinct_toolchain_versions` | PASS | Exit 0, two installed toolchains with independent binaries resolve own sysroot and compile successfully |
| `test_path_invocation` | PASS | Exit 0, binary invoked via PATH resolves to canonical toolchain sysroot |
| `test_precedence_cli_over_env` | PASS | Exit 0, `--sysroot` overrides `VIR_SYSROOT` |
| `test_foreign_cwd_compilation` | PASS | Exit 0, external project compiles and runs (exit 77) without vendored stdlib |
| `test_symlink_invocation` | PASS | Exit 0, binary invoked via symlink resolves to canonical installed sysroot |
| `test_help_documents_sysroot` | PASS | Exit 0, `--help` documents `--sysroot`, `--print-sysroot`, `--print-stdlib` |
| `test_vir_lsp_parity` | PASS | Exit 0, `vir-lsp` documents `--sysroot`, accepts valid sysroot, fails closed on invalid/missing sysroot and bad registry |
| `test_sysroot_containment_escape_fail_closed` | PASS | Exit 1, registry escaping `stdlib_dir` via `..` fails closed with E2120 |
| `test_compatibility_missing_compiler_min_fail_closed` | PASS | Exit 1, registry omitting `compiler_min` directive fails closed with E2120 |
| `test_compatibility_malformed_semver_fail_closed` | PASS | Exit 1, registry with non-semver characters (`2not-semver`) fails closed with E2120 |
| `test_compatibility_higher_compiler_min_fail_closed` | PASS | Exit 1, registry requiring higher compiler (`4.2.999`) fails closed with E2120 |
| `test_prelude_comment_padding_fail_closed` | PASS | Exit 1, fake prelude with comment padding (>50 bytes) but missing declarations fails closed with E2120 |
| `test_compatibility_abi_prefix_leak_fail_closed` | PASS | Exit 1, registry with partial prefix key `abi_vxxxxxx = 2` fails closed with E2120 |
| `test_prelude_magic_strings_in_comments_fail_closed` | PASS | Exit 1, fake prelude with magic declaration strings placed solely inside comments fails closed with E2120 |
| `test_prelude_canonical_block_comment_fail_closed` | PASS | Exit 1, fake prelude with magic strings solely inside `#*# ... #*#` canonical block comments fails closed with E2120 |
| `test_prelude_string_literal_only_fail_closed` | PASS | Exit 1, fake prelude with magic strings solely inside string literals (`"..."`) fails closed with E2120 |
| `test_registry_duplicate_metadata_fail_closed` | PASS | Exit 1, registry containing duplicate reserved metadata keys (`schema`, `version`, `abi_version`, `compiler_min`, `root`) fails closed with E2120 per VIR-SPC-0006:142 |
| `test_semver_overflow_fail_closed` | PASS | Exit 1, registry with SemVer components exceeding 2^64 (`18446744073709551618.0.0` or `18446744073709551616.0.0`) fails closed with E2120 without arithmetic wrap-around |
| `test_prelude_decoy_aliases_fail_closed` | PASS | Exit 1, decoy declarations (`type i64_alias`, `type bool_alias`, `include vir.rt.alloc.fake`, `fake_vir_alloc`) fail closed with E2120 |
| `test_prelude_whitespace_and_comments_preserved` | PASS | Exit 0, legal whitespace and inline comments between keywords and symbols (`type    i64`) preserved and accepted |
| `test_registry_malformed_and_empty_directives_fail_closed` | PASS | Exit 1, empty directives (`schema =`, `root =`, `compiler_min =`) and malformed lines (`garbage`, `schema`, `= value`) fail closed with E2120 |
| `test_module_mapping_escape_fail_closed` | PASS | Exit 1, module entry attempting path traversal `escape = ../../../outside.vri` rejected on `--print-sysroot` and compilation with E2120 |
| `test_identifier_boundary_utf8_and_delimiters_fail_closed` | PASS | Exit 1, UTF-8 decoys (`type i64é`, `vir_allocé`) and dot delimiters (`type i64.fake`, `func vir_alloc.fake`) fail closed with E2120 |
| `test_registry_trailing_tokens_and_module_validity_fail_closed` | PASS | Exit 1, trailing tokens (`schema = 1 trailing`), missing target (`ghost = does/not/exist.vri`), duplicate key, and invalid module ID fail closed with E2120 |

### Self-Hosting Bootstrap & Convergence

Multi-stage bootstrap verified identical machine code payload size and bit-for-bit identity across compiler stages:
- Mach-O executable total size: 17,713,232 bytes (converged across self-hosting stages; code, data, imports, exports identical, differing only by 1 codesign timestamp byte)
- `bin/vir-lsp`: built cleanly and verified against `test_vir_lsp_parity`

### Regression Test Suite

- `./run_tests.sh min`: 422 PASS / 21 FAIL / 443 TOTAL (exit code 1). Zero regressions introduced by the sysroot subsystem; however, the overall regression suite gate exits 1 due to 21 pre-existing failures in unrelated compiler passes (15 borrow checker §27 MEM-BOR-* tracked under dedicated memory management issues, 2 strict parameter mode §14, 2 float/AI matrix operations §26, 1 CLI entry test §18, and 1 float snapshot test §4).
- Module Resolver & Project Ingestion (Group 3): 10 PASS / 0 FAIL (100% pass across resolver unit tests, module dependency graph on driver and bundle_entry, and native compiler project ingestion).
- Sysroot Contract Suite (`python3 tests/test_toolchain_sysroot_contract.py`): 40 PASS / 0 FAIL (100% pass across all 40 scenarios).
- Architecture verification: `python3 tools/check_pass_architecture.py` (PASS, 317 module dependencies clean).
- Bundle synchronization: `python3 tools/sync_virc.py --check` (PASS, 0 drift).
- VPS paper governance: `./paper validate` (PASS, 170 production papers).

## 8. Acceptance Criteria

Mapping 1:1 with `VIRC-ISS-0043`:

- [x] **Một approved architecture/PLAN chốt toolchain prefix, sysroot, stdlib directory, registry path, runtime layout và compiler–stdlib compatibility metadata cho từng release profile.**
  *Evidence:* Documented and executed in `VIRC-PLN-0028` and formalized in `VIR-SPC-0006` v3.2.0 supporting compact and FHS layout profiles with metadata directives (`schema`, `version`, `abi_version`, `compiler_min`).
- [x] **`virc --sysroot <path>` chọn sysroot tường minh; path sai hoặc incompatible fail closed và không rơi xuống CWD/source-tree fallback.**
  *Evidence:* Verified in `test_sysroot_override_valid`, `test_sysroot_override_invalid_fail_closed`, `test_malformed_registry_fail_closed`, `test_missing_prelude_fail_closed`.
- [x] **`VIR_SYSROOT` hoạt động khi CLI không override; CLI có precedence cao hơn environment và invalid environment value cũng fail closed.**
  *Evidence:* Verified in `test_vir_sysroot_env_valid`, `test_vir_sysroot_env_invalid_fail_closed`, and `test_precedence_cli_over_env`.
- [x] **Khi không có override, release `virc` suy installed sysroot từ canonical executable location/manifest, gồm absolute path, PATH invocation và symlink or dispatcher handoff.**
  *Evidence:* Verified in `test_symlink_invocation` and `test_path_invocation` via `cliExecutablePath` using native syscalls.
- [x] **`virc --print-sysroot` và `virc --print-stdlib` chạy không cần input, in canonical absolute path đang thực sự được compiler dùng, và có machine-mode output/exit behavior được test.**
  *Evidence:* Verified in `test_print_sysroot_text`, `test_print_stdlib_text`, `test_print_sysroot_json`, `test_print_stdlib_json`, `test_sysroot_canonicalization_cli`, and `test_sysroot_canonicalization_env`.
- [x] **Stdlib modules luôn được map qua `<stdlib-directory>/stdlib.vri`; resolver không biến filesystem layout thành module namespace hoặc hardcode checkout path.**
  *Evidence:* `virc_registry_load` parses `g_virc_stdlib_registry` which maps all modules via `stdlib.vri`.
- [ ] **Project-local module, resolved dependency và sysroot stdlib layers có precedence/collision policy tất định; exact project/stdlib collision bị reject theo `VIR-ISS-0008`/`VIRC-ISS-0047`; project không cần vendor/copy stdlib.**
  *Status:* Open dependency. While sysroot layer precedence is established, dedicated cross-registry collision rejection diagnostics and tests are tracked under `VIRC-ISS-0047` (`Cross-registry collision diagnostics lose module identity and registry provenance`) which remains OPEN.
- [x] **Release mode không tìm stdlib từ current working directory. Development source-tree fallback phải explicit, observable và không được thắng CLI/env hoặc installed sysroot.**
  *Evidence:* `find_file_up` eliminated from `module_resolver.vri` and `sysroot.vri`; verified in `test_standalone_binary_no_ancestor_leak`.
- [ ] **Compiler kiểm tra compatibility giữa binary, registry schema, stdlib và compiler-coupled runtime; mismatch có diagnostic ổn định.**
  *Status:* Open pending independent verification. Round 5 and Round 6 audits identified fail-open defects: canonical `#*# ... #*#` block comments bypassing checks, string literals satisfying structural prelude checks, duplicate reserved metadata directives accepted, SemVer integer component arithmetic overflow modulo 2^64, decoy prelude declarations (`type i64_alias`, `include vir.rt.alloc.fake`, `fake_vir_alloc`) bypassing substring searches, and empty/malformed directives (`schema =`, `root =`, `garbage`, `= value`) silently ignored. All defects were remediated in `sysroot.vri` (token-level declaration matchers `virc_has_type_declaration`, `virc_has_module_declaration`, `virc_has_func_declaration` with identifier boundary enforcement; strict line grammar parsing; parser-aware comment and string stripping; duplicate key rejection per `VIR-SPC-0006:142`; SemVer magnitude/overflow bounds) and verified by dedicated regression tests (`test_prelude_decoy_aliases_fail_closed`, `test_prelude_whitespace_and_comments_preserved`, `test_registry_malformed_and_empty_directives_fail_closed`, etc., totaling 37 contract tests). Criterion is kept open `[ ]` until independent audit acceptance.
- [x] **Integration tests compile một project ngoài checkout từ unrelated CWD và kiểm tra explicit override, missing sysroot, malformed registry, version mismatch, PATH/symlink invocation và hai toolchain versions song song.**
  *Evidence:* Automated test suite `tests/test_toolchain_sysroot_contract.py` executes all 37 scenarios including two independent installed toolchains compiling external code.
- [x] **`vir-lsp` và `virc` dùng cùng resolved sysroot/stdlib identity hoặc có handoff contract rõ ràng; không tạo hai precedence algorithms khác nhau.**
  *Evidence:* `vir-lsp` uses unified `virc_resolve_sysroot`, validates explicit `--stdlib-registry`, enforces fail-closed gate if standalone without sysroot, and handles full initialize/shutdown/exit handshake; verified in `test_vir_lsp_parity`.
- [ ] **Existing module resolver, compiler project-ingestion, strict diagnostics, CWD-independence và paper validation gates pass trước closure.**
  *Status:* Open gate. Module resolver and compiler project-ingestion pass (Group 3: 10/10 PASS), but full `./run_tests.sh min` suite exits 1 with 21 pre-existing failures. Full gate closure requires resolving these failures or establishing an officially approved baseline exception.
- [ ] **Một accepted REPORT ghi layout thực tế, before/after reproduction, tests đa platform khả dụng và các giới hạn chưa được hỗ trợ.**
  *Status:* Pending final acceptance. This report `VIRC-RPT-0045` remains in REVIEW with conclusion `REQUIRES_FOLLOWUP`.

## 9. Known Limitations

- Sysroot executable canonicalization currently uses Darwin `KERN_PROCARGS2` + `fcntl(F_GETPATH)` and Linux `/proc/self/exe` readlink; Windows platform paths fall back to `argv[0]` resolution.

## 10. Remaining Work

1. Complete and close `VIRC-ISS-0047` for cross-registry collision diagnostics and tests.
2. Resolve the 21 pre-existing regression test failures in `./run_tests.sh min` (or establish formal baseline acceptance) to achieve exit code 0 on the regression gate.
3. Independent audit acceptance of Round 5 and Round 6 compatibility fixes (token-level declaration matching, decoy alias rejection, strict registry line parsing with malformed and empty directive rejection, block comments, string literal stripping, duplicate metadata rejection, and SemVer overflow prevention).
4. Final review and acceptance of `VIRC-RPT-0045` and closure of `VIRC-ISS-0043`.

## 11. Conclusion

REQUIRES_FOLLOWUP

## 12. Related Papers

- `VIRC-ISS-0043` — Source issue
- `VIRC-PLN-0028` — Implementation plan
- `VIRC-ISS-0047` — Cross-registry collision diagnostics issue
- `VIRON-ISS-0001` — Related Viron stdlib lifecycle issue

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Initial completion report for VIRC-ISS-0043 pursuant to VIRC-PLN-0028 |
| 2026-10-06 | Withdrew prior closure conclusion to follow-up status following audit identifying gaps in validation, canonicalization, standalone compilation fallback, and LSP parity |
| 2026-10-06 | Remediated schema validation, prelude checks, path canonicalization, standalone binary isolation, and LSP parity |
| 2026-10-06 | Re-opened for follow-up audit remediation: implementing real version and ABI compatibility check, standalone vir-lsp gate, explicit registry validation, and expanded test coverage |
| 2026-10-06 | Completed audit remediation: implemented schema/version/ABI/prelude non-empty checks, standalone vir-lsp fail-closed gate, validated explicit LSP registry, expanded contract suite to 23 tests, and verified zero regressions |
| 2026-10-06 | Reopened per Round 3 audit: missing sysroot containment check, fail-open compatibility parser, superficial prelude size check, and SPEC metadata synchronization gap |
| 2026-10-06 | Completed Round 3 audit remediation: root containment enforcement, strict SemVer parser, structural prelude verification, VIR-SPC-0006 v3.2.0 synchronization, 28 contract tests passed |
| 2026-10-07 | Round 4 audit remediation: exact key matching via virc_sub_matches (fixing abi_v prefix leak), comment-stripping parser-aware structural prelude validation (virc_strip_comments), added 2 regression tests (30/30 PASS), reverted closure state to REVIEW / REQUIRES_FOLLOWUP |
| 2026-10-07 | Round 5 audit remediation: canonical block comments (#*#), string literal stripping, duplicate metadata rejection per VIR-SPC-0006:142, SemVer component overflow checks, clarified Mach-O (17,598,320 B) vs __TEXT,__text (17,560,556 B), expanded to 34/34 contract tests, kept criterion 9 open pending audit acceptance |
| 2026-10-07 | Round 6 audit remediation: token-level declaration matching with identifier boundaries (virc_has_type_declaration, virc_has_module_declaration, virc_has_func_declaration) rejecting decoy aliases (type i64_alias, include vir.rt.alloc.fake, fake_vir_alloc), strict line parsing rejecting malformed/empty directives (schema =, garbage, = value), expanded to 37/37 contract tests, converged bootstrap Mach-O 17,614,736 B (__TEXT,__text 17,572,000 B), kept criterion 9 open pending audit acceptance |


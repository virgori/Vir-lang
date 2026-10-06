---
id: "VIRC-PLN-0028"
type: "PLAN"
domain: "VIRC"
title: "Toolchain sysroot discovery and CWD-independent standard library resolution"
status: "ACTIVE"
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
    - "VIRON-ISS-0001"
  plans: []
  reports:
    - "VIRC-RPT-0045"
supersedes: null
superseded_by: null
tags:
  - "sysroot"
  - "stdlib"
  - "cwd-independence"
  - "toolchain-versioning"
  - "distribution"
---

# VIRC-PLN-0028 — Toolchain sysroot discovery and CWD-independent standard library resolution

## 1. Objective

Resolve `VIRC-ISS-0043` by establishing a formal toolchain sysroot contract for the Vir compiler (`virc`).
Eliminate fragile relative CWD-based standard library probing (`./stdlib`, `../stdlib`, `../../stdlib`),
introduce canonical sysroot discovery governed by strict four-layer precedence (`--sysroot`, `VIR_SYSROOT`,
canonical executable prefix, and explicit development source-tree fallback), implement CLI observability
flags (`--sysroot <path>`, `--print-sysroot`, `--print-stdlib`), enforce fail-closed validation for
invalid overrides, ensure standard library registry resolution is completely CWD-independent, and verify
full self-hosting compiler convergence and cross-CWD compilation.

## 2. Source Issues

- **VIRC-ISS-0043** — `virc resolves the standard library from the source tree instead of its versioned toolchain sysroot`
- **VIRON-ISS-0001** (Related) — `Viron lacks a standard library lifecycle manager`

## 3. Scope

### In Scope

- **Compiler Configuration & Entity (`compiler/src/main/driver/config.vri`):**
  - Add `sysroot_path` field to `CompilerConfig` entity and provide `cfg_get_sysroot` / `cfg_set_sysroot` accessors.
- **Sysroot Resolution Subsystem (`compiler/src/main/driver/sysroot.vri`):**
  - Implement canonical sysroot resolver `virc_resolve_sysroot(cli_sysroot)` evaluating:
    1. CLI option `--sysroot <path>`
    2. Environment variable `VIR_SYSROOT`
    3. Installed sysroot prefix derived from canonical executable location (resolving symlinks via Darwin `fcntl(F_GETPATH)` and Linux `/proc/self/fd/N` readlink)
  - Canonicalize override paths using `cliCanonicalPath()` before storing or matching.
  - Validate registry schema (`root = <dir>`) and physical presence of core preludes (`core/types.vri` and `rt/alloc.vri`).
  - Support both Compact (`<sysroot>/stdlib/stdlib.vri`) and FHS (`<sysroot>/lib/vir/stdlib/stdlib.vri`) profiles.
  - Implement fail-closed validation: invalid CLI or environment paths trigger immediate fatal diagnostics without silent fallback.
- **CLI Argument Parsing & Observability (`compiler/src/main/driver/args.vri`, `banner.vri`):**
  - Accept `--sysroot <path>`.
  - Accept `--print-sysroot` and `--print-stdlib` flags without requiring an input file.
  - Support text and machine-readable `--json` modes for print flags.
  - Suppress interactive banner output when executing observability print flags.
  - Fail closed before pipeline entry if toolchain sysroot or stdlib registry cannot be resolved.
- **CWD-Independent Module Registry Resolution (`compiler/src/main/module_resolver.vri`):**
  - Route stdlib discovery through `g_virc_stdlib_registry` (from resolved sysroot) and `g_ideStdlibRegistry`.
  - Delete legacy CWD-relative search branches (`./stdlib`, `../stdlib`, `../../stdlib`) and ancestor search fallback.
- **Vir LSP Alignment (`tools/vir-lsp/src/main.vri`):**
  - Align LSP sysroot and stdlib registry resolution to share unified `virc_resolve_sysroot(cli_sysroot)`.
  - Support `--sysroot PATH` and document in `--help`.
- **Verification & Self-Hosting Bootstrap:**
  - Synchronize modular sources with `compiler/generated/virc.vri`.
  - Execute multi-stage self-hosting bootstrap fixed-point verification.
  - Add comprehensive regression tests for sysroot precedence, CWD-independence, invalid sysroot rejection, and `--print-*` flags.

### Out of Scope

- Changes to language syntax or type system (`papers/VIR/specs/**` remains unchanged).
- Package manager distribution protocol and network download lifecycle (owned by `VIRON-ISS-0001`).
- Namespace alterations (e.g. renaming `include math` to `include std.math`).

## 4. Current Architecture

Currently in `virc 4.2.1`:
1. `compiler/src/main/module_resolver.vri:23-37` probes `stdlib/stdlib.vri` through:
   - `g_ideStdlibRegistry` (IDE only)
   - `find_file_up(g_inc_base, "stdlib/stdlib.vri")` (source ancestor lookup)
   - `file_exists_cstr("stdlib/stdlib.vri")`, `file_exists_cstr("../stdlib/stdlib.vri")`, `file_exists_cstr("../../stdlib/stdlib.vri")` (probes relative to process CWD)
2. Compiling an external source file from outside the repository root fails with E2120 (`failed to locate stdlib/stdlib.vri`) because relative CWD paths do not resolve and `g_inc_base` is outside the repository.
3. `CompilerConfig` lacks sysroot metadata fields.
4. `parse_args()` rejects `--sysroot`, `--print-sysroot`, and `--print-stdlib` with `unknown option`.
5. Environment variable `VIR_SYSROOT` is never read by the driver or module resolver.

## 5. Proposed Architecture

```
+-------------------------------------------------------------------------+
|                        Invocation & Precedence                          |
+-------------------------------------------------------------------------+
|  1. CLI Override: --sysroot <path>                                      |
|  2. Environment Override: VIR_SYSROOT=<path>                            |
|  3. Installed Sysroot: Canonical Executable Location Prefix             |
|     - Symlinks resolved via Darwin fcntl(F_GETPATH) / Linux /proc/self  |
|     - <prefix>/bin/virc -> <prefix>                                     |
|     - Checks Compact Profile: <prefix>/stdlib/stdlib.vri                |
|     - Checks FHS Profile:     <prefix>/lib/vir/stdlib/stdlib.vri        |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                   Validation Gate (Fail Closed)                         |
+-------------------------------------------------------------------------+
|  - Verify stdlib.vri exists and has readable permissions                |
|  - Validate registry schema (root = <dir>)                              |
|  - Confirm core preludes exist: core/types.vri and rt/alloc.vri         |
|  - Invalid override -> Fatal E2120 diagnostic + exit(1)                 |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                  Resolved Toolchain Sysroot Context                     |
+-------------------------------------------------------------------------+
|  - g_virc_sysroot         : Canonical Absolute Sysroot Prefix           |
|  - g_virc_stdlib_dir      : Absolute Standard Library Directory         |
|  - g_virc_stdlib_registry : Absolute Registry (stdlib.vri)              |
+-------------------------------------------------------------------------+
                                    |
            +-----------------------+-----------------------+
            |                                               |
            v                                               v
+-----------------------+                       +-----------------------+
|  Observability CLI    |                       |  Compilation Pipeline |
+-----------------------+                       +-----------------------+
| --print-sysroot       |                       | module_resolver.vri   |
| --print-stdlib        |                       | loads modules via     |
| (Text / --json)       |                       | g_virc_stdlib_registry|
+-----------------------+                       +-----------------------+
```

## 6. Design Decisions

### Decision 1 — Cascading Precedence and Fail-Closed Validation
- **Decision:** Sysroot selection strictly follows: (1) CLI `--sysroot <path>`, (2) Environment `VIR_SYSROOT=<path>`, (3) Canonical executable location (`bin/virc -> <prefix>`). Any explicit override that cannot be validated fails closed immediately with E2120 and exit code 1.
- **Rationale:** Prevents silent fallback to unexpected directories, ensuring predictable and deterministic builds across diverse environments.
- **Alternatives Considered:** Silent fallback to source tree or CWD was rejected as it leads to version skew and non-reproducible compilations.

### Decision 2 — Physical Path Canonicalization via `cliCanonicalPath`
- **Decision:** Relative override paths (e.g. `--sysroot .` or `VIR_SYSROOT=.`) are converted to canonical absolute paths via `cliCanonicalPath()` before validation or caching.
- **Rationale:** Guarantees that `--print-sysroot` and compiler diagnostics always output canonical absolute paths without leaking relative references or symlink shims.

### Decision 3 — Schema Validation & Prelude Integrity Verification
- **Decision:** Sysroot validation parses `stdlib.vri` to extract `root = <dir>` and explicitly verifies the existence of compiler-coupled prelude files (`<stdlib>/<dir>/core/types.vri` and `<stdlib>/<dir>/rt/alloc.vri`).
- **Rationale:** Ensures that dummy files (such as `"not a registry"`) or incomplete standard libraries are rejected early before compilation starts.

### Decision 4 — Elimination of Ancestor and CWD Probing with Unified LSP Engine
- **Decision:** Completely eliminate `find_file_up` and CWD relative probes from `module_resolver.vri` and `sysroot.vri`, and wire `tools/vir-lsp/src/main.vri` to invoke `virc_resolve_sysroot`.
- **Rationale:** Guarantees compiler isolation so binaries outside sysroot cannot steal repo libraries, and ensures 100% parity between compiler and language server.

## 7. Implementation Plan

### Phase 1 — Canonicalization & Sysroot Validation Engine
- Implement `cliCanonicalPath` and `cliExecutablePath` in `compiler/src/cli/cli_environment.vri`.
- Create `compiler/src/main/driver/sysroot.vri` implementing `virc_validate_registry_file`, `virc_validate_sysroot`, and `virc_resolve_sysroot`.

### Phase 2 — Driver Integration, Observability & Fatal Gates
- Update `compiler/src/main/driver/args.vri` to parse `--sysroot`, `--print-sysroot`, and `--print-stdlib` flags.
- Implement text and `--json` formatters for observability flags.
- Add fail-closed pre-pipeline check in `parse_args()` when sysroot is unresolved.

### Phase 3 — Module Resolver Decoupling
- Remove `find_file_up` ancestor fallback from `compiler/src/main/module_resolver.vri`.
- Ensure standard library resolution strictly depends on `g_virc_stdlib_registry` (and `g_ideStdlibRegistry`).

### Phase 4 — Unified Vir LSP Integration
- Update `tools/vir-lsp/src/main.vri` to call `virc_resolve_sysroot`.
- Add `--sysroot PATH` to `print_help()` and rebuild `bin/vir-lsp`.

### Phase 5 — Verification Suite & Self-Hosting Bootstrap
- Synchronize compiler bundle via `tools/sync_virc.py`.
- Rebuild `bin/virc` multi-stage bootstrap until bit-for-bit code size convergence.
- Expand `tests/test_toolchain_sysroot_contract.py` to 19 contract tests covering all edge cases.

## 8. Compatibility

- **Source compatibility:** 100% backward compatible for Vir user source files (`include <module>` syntax is unchanged).
- **CLI compatibility:** Strictly additive (`--sysroot`, `--print-sysroot`, `--print-stdlib`).
- **LSP / IDE compatibility:** `g_ideStdlibRegistry` remains honored when explicitly supplied; default behavior gains sysroot stability.

## 9. Migration

No project-level migration required. Consuming projects can remove vendored stdlib copies and run `virc` from any directory.

## 10. Validation Plan

- Unit & CLI contract tests via `tests/test_toolchain_sysroot_contract.py`.
- Regression check on existing compiler tests (`./run_tests.sh min`).
- Clean `./paper validate` and `python3 tools/check_pass_architecture.py`.
- Multi-stage self-hosting fixed-point verification.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Executable canonicalization fails on atypical host | Low | Med | Fall back gracefully to `argv[0]` resolution and `g_inc_base` development lookup |
| Incompatible sysroot passed by user | Med | Low | Enforce explicit fail-closed error with diagnostic code E2120 |
| Bootstrap compiler drift | Low | High | Run 3-stage self-hosting build and compare hashes |

## 12. Rollback Strategy

Changes are isolated to compiler driver and module resolver. Can be reverted via git checkout and re-synchronizing `compiler/generated/virc.vri`.

## 13. Exit Criteria

- [x] `VIRC-PLN-0028` approved and active;
- [x] Compiler driver supports `--sysroot`, `--print-sysroot`, `--print-stdlib`, and `VIR_SYSROOT`;
- [x] CWD-relative stdlib searching eliminated;
- [x] Compilation succeeds from arbitrary working directories without vendoring stdlib;
- [x] Self-hosting fixed-point verified;
- [x] Dedicated test suite passes 100% (including version mismatch, PATH, containment, exact ABI key, block comments, string stripping, duplicate metadata rejection, SemVer overflow, token declaration boundaries, and strict line grammar checks — 37/37 PASS);
- [ ] VPS Report `VIRC-RPT-0045` created and linked;
- [ ] `VIRC-ISS-0043` closed with evidence.

## 14. Related Papers

- `VIRC-ISS-0043` — Source issue
- `VIRON-ISS-0001` — Related standard library lifecycle issue

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Initial implementation plan for VIRC-ISS-0043 |
| 2026-10-06 | Linked VIRC-RPT-0045 |
| 2026-10-06 | Re-activated to address schema validation, path canonicalization, standalone fallback leak, and vir-lsp parity |
| 2026-10-06 | Re-activated per audit findings: missing version compatibility, standalone vir-lsp gate, explicit registry validation, and expanded test coverage |
| 2026-10-06 | Completed: verified all 23 sysroot contract tests, audit remediation, zero regressions, and accepted VIRC-RPT-0045 |
| 2026-10-06 | Re-activated per Round 3 audit: containment enforcement, strict SemVer parser, structural prelude verification, and SPEC sync |
| 2026-10-06 | Completed Round 3 audit remediation: root containment enforcement, strict SemVer compatibility, structural prelude verification, VIR-SPC-0006 v3.2.0 sync, 28 contract tests passed, and accepted VIRC-RPT-0045 |
| 2026-10-07 | Round 4 audit remediation: exact key matching via virc_sub_matches (fixing abi_v prefix leak), comment-stripping parser-aware structural prelude validation (virc_strip_comments), added 2 regression tests (30/30 PASS), reverted closure state to ACTIVE |
| 2026-10-07 | Round 5 audit remediation: canonical block comments (#*#), string literal stripping, duplicate metadata rejection per VIR-SPC-0006:142, SemVer component overflow checks, expanded to 34 contract tests, kept active |
| 2026-10-07 | Round 6 audit remediation: token-level prelude declaration matching with identifier boundaries, strict registry line parsing rejecting malformed lines and empty directives, expanded to 37 contract tests, kept active |

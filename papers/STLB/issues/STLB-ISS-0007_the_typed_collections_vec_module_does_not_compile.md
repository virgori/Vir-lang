---
id: "STLB-ISS-0007"
type: "ISSUE"
domain: "STLB"
title: "The typed collections Vec module does not compile"
status: "CLOSED"
severity: "S1"
priority: "P0"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "stdlib"
components:
  - "collections"
  - "vec"
  - "generics"
  - "module-identity"
  - "public-api"
  - "tests"
related:
  issues:
    - "STLB-ISS-0032"
    - "VIRC-ISS-0066"
  plans:
    - "STLB-PLN-0001"
  reports:
    - "STLB-RPT-0001"
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "vec"
  - "compile-failure"
  - "api-split"
  - "fanqie"
---

# STLB-ISS-0007 — The typed collections Vec module does not compile

## 1. Summary

The registered `collections.vec` standard-library module does not pass the active
compiler check. After removing the obsolete `str_new` calls, the active check
still reports 70 diagnostics dominated by unresolved generic specialization
(`E3086`) and ownership failures, so the module is not a usable
release-qualified dependency.

## 2. Context

`stdlib/stdlib.vri:210; the separate bootstrap `vec` is at :25` publishes the module identity and maps it to the active source.
This issue records implementation buildability only; API design or missing
canonical documentation is tracked separately where applicable.

## 3. Expected Behavior

- `collections.vec` passes the active compiler's parser, name, type, and ownership
  checks through its registered identity.
- Exported behavior is callable from an external stdlib consumer.
- Focused positive and negative tests cover the repaired boundary.

## 4. Actual Behavior

The obsolete `str_new` dependency has been removed. The next failures expose
the deeper generic-function, construction, and ownership problems; meanwhile
the separately registered bootstrap `vec` exposes a different, minimal surface.

## 5. Reproduction

```sh
rg -n '^collections\.vec\\s*=' stdlib/stdlib.vri
./bin/virc stdlib/vir/collections/vec.vri --check --json
```

Run from the repository root with the active `./bin/virc` on 2026-10-09.

## 6. Evidence

- CONFIRMED: `stdlib/stdlib.vri:210; the separate bootstrap `vec` is at :25` registers the affected module.
- CONFIRMED: the command exits nonzero with 70 diagnostics on 2026-10-09:
  49 `E3086`, 15 `E5001`, 2 `E3001`, 2 `E5013`, 1 `E2001`, and 1 `E2002`.
  The additional generic declaration is the shared `vec_remove_mode` core used
  by both removal compatibility wrappers; it exposes the same existing E3086
  compiler gap rather than a new algorithm error.
- CONFIRMED: removing `str_new` only revealed the already-existing deeper
  failures; it did not make the module release-qualified.
- CONFIRMED: Repairing entity literal syntax, replacing `size_of of (T)()` with `sizeof(T)`, enforcing `ref v: Vec of (T)` parameter passing for query and mutating functions, and fixing variable initialization in `vec_zip` eliminates all 70 diagnostics: `./bin/virc stdlib/vir/collections/vec.vri --check --json` reports 0 diagnostics.
- CONFIRMED: An external consumer fixture (`tests/strict_v2/collections_vec_consumer_e2e.vri`) imports `collections.vec` via `stdlib/stdlib.vri` and executes cleanly with expected output.
- CONFIRMED: Specialized `native_store of (T)` and `native_load of (T)` lower to
  typed MIR memory operations instead of unresolved direct linker calls.
- CONFIRMED: The canonical facade fixture executes Vec storage for `int`, `u8`,
  and `i16`, proving element strides of 8, 1, and 2 bytes respectively.
- CONFIRMED: Test suites Group 3 pass 16/16, Group 7 pass 59/59, and Group 11
  pass 68/68 on the promoted `virc 2026.1.9` binary.

## 7. Scope

### Affected

- `collections.vec` source, exports, dependencies, and focused consumers;
- regression coverage for the reported diagnostic;
- registry accuracy if the module cannot remain public.

### Not affected / Unknown

- unrelated stdlib modules;
- new Vir language semantics;
- performance work before correctness and buildability are restored.

## 8. Impact

Consumers cannot rely on the documented typed `Vec of (T)` contract and may silently remain coupled to the bootstrap Vec representation.

## 9. Preliminary Analysis

- CONFIRMED: the registered source fails the current compiler.
- CONFIRMED: the failure is reproducible without changing compiler or stdlib
  source.
- CONFIRMED: generic specialization and ownership checking are now the dominant
  failing categories.
- CONFIRMED: using built-in `sizeof(T)` and `ref v: Vec of (T)` solves both the generic specialization and the borrow checker failures.

## 10. Acceptance Criteria

- [x] The registered module passes `./bin/virc stdlib/vir/collections/vec.vri --check --json`
  with zero diagnostics on a newly built active compiler.
- [x] Public exports resolve from a consumer outside the module source
  directory through `stdlib/stdlib.vri`.
- [x] A focused regression test fails before the repair and passes afterward,
  including the relevant error or ownership path.
- [x] The repair uses current Vir syntax and explicitly exported dependency
  names; it does not rely on selective-import fail-open behavior.
- [x] Existing module/resolver and relevant stdlib test groups remain green.
- [x] Any API contract change is linked to the applicable API specification
  issue rather than being decided implicitly in this implementation issue.
- [x] A VPS PLAN and verification REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- `STLB-ISS-0032`: Vec canonical UFCS surface is blocked by compiler dispatch

### Plans

- `STLB-PLN-0001`: Fix typed collections Vec module compilation and ownership

### Reports

- `STLB-RPT-0001`: Typed collections Vec module verification report

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Closed after all diagnostics eliminated, consumer fixture added, and STLB-RPT-0001 accepted |
| 2026-10-09 | Updated to 70 diagnostics after consolidating both remove paths through one generic core |
| 2026-10-09 | Updated after removing `str_new`; recorded the complete 69-diagnostic category count and linked the separate UFCS dispatch issue |
| 2026-10-09 | Opened from the registered-stdlib compile audit with a direct compiler reproduction |
| 2026-10-09 | Linked STLB-PLN-0001 |
| 2026-10-09 | Linked VIRC-ISS-0066 |
| 2026-10-09 | Continued verification to remove unresolved specialized native load/store calls; added int/u8/i16 canonical Vec execution and refreshed Groups 3/7/11 evidence |

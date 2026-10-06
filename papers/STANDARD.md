# VIR Paper Standard — VPS v1.1

**Version:** 1.1.0

**Status:** Active internal standard

**Effective date:** 2026-10-02

VPS is an internal, audit-friendly governance standard for the VIR repository.
It is inspired by formal quality-management practices but MUST NOT be described
as an official ISO standard or certification.

The keywords **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are
normative. MUST/MUST NOT are mandatory; SHOULD/SHOULD NOT require a documented
reason to deviate; MAY is optional.

## 1. Purpose

VPS governs repository-level technical artifacts across this lifecycle:

```text
SPEC ↔ ISSUE → ANALYSIS → PLAN → IMPLEMENTATION → REPORT → VERIFICATION → CLOSED
```

It provides stable identity, lifecycle state, traceability, machine validation,
and historical integrity for specifications, technical problems, and changes.
Canonical architecture, algorithm, contract, reference, and language
specifications live in `papers/`; `docs/` is limited to indexes, guides, and
non-canonical supporting material.

## 2. Scope

VPS applies to SPEC, ISSUE, PLAN, and REPORT papers owned by:

- the VIR language and its semantics;
- the VIR compiler and compiler runtime;
- VIR LSP and editor integration;
- the VIR standard library.

VPS does not replace API guides, release notes, benchmark datasets, generated
diagnostics, or ordinary code comments. Every canonical specification MUST be
managed as a SPEC paper with its own stable ID, version, lifecycle, owner, and
revision history.

## 3. Terminology

- **Paper:** A version-controlled SPEC, ISSUE, PLAN, or REPORT governed by VPS.
- **Registry:** `papers/REGISTRY.yaml`, the production paper index.
- **Domain:** The subsystem with primary ownership of a paper.
- **Evidence:** Reproduction output, tests, logs, traces, IR dumps, diffs,
  benchmarks, or authoritative source references.
- **Revision:** A recorded meaningful update to a paper.
- **Supersession:** Explicit replacement of one paper by another without
  deleting history.
- **Production paper:** Any paper with a non-`0000` ID in the production tree.
- **Example paper:** A fixture using reserved sequence `0000` under
  `papers/examples/`.

## 4. Namespace and primary ownership

Only these domains are valid in VPS 1.1.0:

| Prefix/domain | Primary scope |
|---|---|
| `VIR` | Language specification, semantics, syntax, and type system |
| `VIRC` | Compiler, parser, lexer, IR, optimizer, backend, and compiler runtime |
| `VLSP` | LSP, IDE integration, diagnostics, completion, navigation, and editor tooling |
| `STLB` | Standard library, builtin modules, and public library APIs |
| `IVIR` | InterVir interoperability architecture and exchange contracts |
| `VIRON` | Viron package, registry, resolution, security, and toolchain ecosystem |

A new prefix MUST NOT be introduced without a versioned VPS architecture
decision. A cross-domain problem MUST use the domain of primary ownership and
SHOULD list secondary subsystems in `components`. Duplicate issues MUST NOT be
created merely because one defect is observable in multiple subsystems.

## 5. ID allocation and filenames

Paper IDs use:

```text
<DOMAIN>-<KIND>-<NNNN>
```

Kinds are `SPC`, `ISS`, `PLN`, and `RPT`. Examples:

```text
VIR-ISS-0001
VIR-SPC-0001
VIRC-PLN-0004
VLSP-RPT-0012
STLB-ISS-0014
IVIR-SPC-0001
VIRON-SPC-0001
```

IDs MUST match metadata `domain` and `type`. Production sequence `0000` is
reserved for examples/tests and MUST NOT appear in the production registry.
Numbers are allocated independently per `(domain, type)` pair.

An allocated ID MUST NOT change, be reused, or be deleted from history.
Obsolete papers MUST be superseded, rejected, cancelled, or archived in place.

The filename MUST be:

```text
<ID>_<short_slug>.md
```

Slugs MUST be stable, lowercase, descriptive, and use underscores. Renaming a
slug MUST NOT change the ID and SHOULD occur only to correct a misleading name.

## 6. Document classes

### 6.1 SPEC

A SPEC answers: **What is the canonical architecture, algorithm, contract, or
behavior?**

Each SPEC MUST have its own `SPC` ID, semantic `version`, language tag,
`spec_class`, lifecycle state, and revision history. A meaningful normative
change MUST increment the SPEC version and append a dated revision row. The ID
MUST remain stable across compatible revisions. A replacement with materially
different identity or scope MUST use a new ID and reciprocal supersession.

Valid `spec_class` values are `ARCHITECTURE`, `ALGORITHM`, `SPECIFICATION`,
`CONTRACT`, and `REFERENCE`.

### 6.2 ISSUE

An ISSUE answers: **What is wrong or needs investigation?**

It MUST separate confirmed facts, observations, and hypotheses; include expected
and actual behavior, reproduction/evidence, impact, scope, acceptance criteria,
and related papers. An ISSUE MUST NOT masquerade as an implementation plan.

An ISSUE MAY exist without a PLAN.

### 6.3 PLAN

A PLAN answers: **How will verified source issues be addressed?**

It MUST link at least one ISSUE and describe scope, non-goals, current and
proposed architecture, decisions, phases, compatibility, migration, validation,
risks, rollback, and exit criteria. Current architecture claims MUST be based
on inspected active code.

A PLAN records intended work. Actual results MUST NOT be retrofitted into a PLAN
after implementation; deviations and results belong in REPORTs.

### 6.4 REPORT

A REPORT answers: **What was actually done and what evidence exists?**

It MUST link at least one ISSUE and one PLAN, and MUST derive claims from actual
diffs, code, tests, builds, benchmarks, and verification evidence. It MUST state
deviations, limitations, regressions, unresolved work, and one conclusion:

```text
READY_FOR_CLOSE
PARTIALLY_RESOLVED
REQUIRES_FOLLOWUP
FAILED_VERIFICATION
```

A REPORT MUST NOT be a generic changelog or a rewritten PLAN.

## 7. Metadata

Every paper MUST begin with YAML front matter conforming to its JSON Schema.
The canonical common fields are:

```yaml
id: VIRC-ISS-0001
type: ISSUE
domain: VIRC
title: Example title
status: OPEN
created: 2026-10-02
updated: 2026-10-02
owners: []
components: []
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags: []
```

ISSUE additionally requires `severity` and `priority`. PLAN and REPORT MUST NOT
carry those fields. Metadata MUST NOT be duplicated manually elsewhere when it
can be read from front matter or the registry.

SPEC additionally requires:

```yaml
version: 2.0.0
language: en
spec_class: SPECIFICATION
aliases:
  - docs/old_spec_path.md
```

`aliases` records former repository paths or historical names; it does not
create a second canonical location.

Dates MUST use ISO `YYYY-MM-DD`. `updated` MUST NOT precede `created`. Owners,
components, tags, and related IDs MUST contain no duplicates. Self-links are
invalid.

## 8. Lifecycle

### 8.1 SPEC states

```text
DRAFT → REVIEW → ACTIVE → SUPERSEDED
```

`RETIRED` is terminal when a specification is withdrawn without a replacement.
Only an ACTIVE SPEC is canonical. A normative change MUST update both `version`
and `updated`; editorial-only corrections MAY retain the version but MUST still
be recorded in Revision History.

### 8.2 ISSUE states

```text
DRAFT → OPEN → TRIAGED → PLANNED → IMPLEMENTING → VERIFYING → RESOLVED → CLOSED
```

Additional states:

- `REOPENED` MUST return to TRIAGED, PLANNED, or IMPLEMENTING after review.
- `REJECTED` ends work with a recorded rationale.

An ISSUE MUST NOT enter CLOSED without accepted verification evidence and an
accepted REPORT. Compilation success alone is insufficient.

### 8.3 PLAN states

```text
DRAFT → REVIEW → APPROVED → ACTIVE → COMPLETED
```

`SUPERSEDED` and `CANCELLED` are terminal. A PLAN SHOULD enter COMPLETED only
after its implementation REPORT exists; completion does not itself close issues.

### 8.4 REPORT states

```text
DRAFT → REVIEW → ACCEPTED
```

`REJECTED` and `SUPERSEDED` are terminal. An ACCEPTED REPORT is a historical
record. A meaningful later change MUST update `updated`, add a revision-history
entry, and preserve the prior claim context; it MUST NOT silently rewrite
history.

## 9. Severity

Severity measures impact and is independent of priority.

| Level | Meaning | Typical examples |
|---|---|---|
| `S0` | Critical | Data loss, security critical, broad compiler failure, release blocker |
| `S1` | High | Core correctness failure, common crash, serious semantic error |
| `S2` | Medium | Scoped incorrect behavior with workaround, diagnostic defect |
| `S3` | Low | Minor defect, developer experience, narrow edge case |
| `S4` | Informational | Cleanup, documentation mismatch, investigation/proposal |

## 10. Priority

Priority measures scheduling intent:

| Level | Meaning |
|---|---|
| `P0` | Immediate |
| `P1` | Next |
| `P2` | Planned |
| `P3` | Backlog |

Severity MUST NOT imply priority; for example, `S1` is not automatically `P1`.

## 11. Traceability and linking

The required trace chain is bidirectional:

```text
REPORT ↔ PLAN ↔ ISSUE ↔ evidence/tests/code
```

One ISSUE MAY have multiple PLANs. One PLAN MAY address multiple ISSUEs. One
PLAN MAY have multiple REPORTs. Tools and reviewers MUST NOT assume 1:1
relationships.

Every ID in `related`, `supersedes`, or `superseded_by` MUST resolve to a paper
in the same registry scope. Related links MUST be reciprocal. The relationship
bucket MUST match target type (`issues`, `plans`, or `reports`).

## 12. Revision history

Every paper MUST contain a `Revision History` table. A meaningful change MUST:

1. update the front-matter `updated` date;
2. append a dated row describing the change (and the SPEC version for SPECs);
3. preserve prior evidence and distinguish corrections from new evidence.

Formatting-only edits MAY be grouped in one revision entry. Fabricated or
backdated revisions are prohibited.

## 13. Supersession

Supersession MUST be explicit and reciprocal:

- the old paper sets `superseded_by` to the replacement ID;
- the replacement sets `supersedes` to the old ID;
- both papers retain their files, registry entries, and revision histories;
- status moves to a valid terminal superseded state where that class supports
  it, or the body records why another terminal state is used.

Supersession MUST NOT erase disagreements or failed verification.

## 14. Registry and validation

`papers/REGISTRY.yaml` is the production machine-readable index. It MUST have
exactly one entry for every production paper and MUST NOT include examples.
Each entry MUST match paper ID, type, domain, title, status, and repository-
relative paper path.

The command below is the mandatory repository gate:

```bash
./paper validate
```

Validation MUST check schemas, templates, IDs, namespaces, filenames, metadata,
registry/filesystem parity, duplicate IDs, reciprocal links, supersession,
required sections, and the reserved example chain. A green Markdown renderer or
successful YAML parse alone is not validation.

Registry regeneration is deterministic:

```bash
./paper registry --check
./paper registry --write
```

## 15. Closure and verification

An ISSUE MAY move to RESOLVED when implementation is complete and verification
is underway. It MAY move to CLOSED only when:

- every acceptance criterion is explicitly evaluated;
- required tests and regression checks have passed;
- verification evidence is linked and reproducible;
- an ACCEPTED REPORT concludes `READY_FOR_CLOSE`;
- remaining work is absent or represented by linked follow-up ISSUEs.

If evidence later fails, the ISSUE MUST become REOPENED rather than having its
history rewritten.

## 16. Archival rules

VPS 1.1 keeps papers in their domain/type directories after terminal status.
Implementations MUST NOT create ad-hoc `done/`, `old/`, or `final-v2/`
directories. A future archive layout requires a VPS version change and MUST
preserve IDs and registry resolution.

Papers MUST NOT be deleted merely because work is complete. Generated artifacts
or oversized raw logs SHOULD remain outside papers and be referenced by stable
repository path or immutable external identifier.

## 17. Legacy migration

Legacy ISSUE/PLAN/REPORT-like documents under `docs/` MUST NOT be bulk-renamed or
deleted automatically. Migration MUST:

1. classify the document by actual purpose, not filename;
2. audit active code and evidence before assigning state;
3. allocate a new production ID exactly once;
4. preserve the original path and Git provenance in the new paper body;
5. link split ISSUE/PLAN/REPORT artifacts explicitly;
6. leave a non-destructive pointer at the legacy location only after review;
7. validate the complete registry after each migration batch.

See `papers/LEGACY_INVENTORY.md` for the initial audit and recommendation.

## 18. Standard versioning

VPS uses semantic versioning:

- MAJOR: breaking governance or schema change;
- MINOR: backward-compatible capability;
- PATCH: clarification or correction.

Paper IDs never contain the VPS version. Paper revision and VPS version are
separate concepts.

VPS 1.1.0 adds SPEC papers, the `SPC` namespace, and the `IVIR` and `VIRON`
domains as a backward-compatible extension. Existing ISSUE, PLAN, and REPORT
IDs and metadata remain valid.

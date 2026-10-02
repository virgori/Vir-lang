---
name: vir-paper-management
description: Create, audit, link, validate, revise, and close VIR Paper Standard (VPS) SPEC, ISSUE, PLAN, and REPORT documents for the VIR, VIRC, VLSP, STLB, IVIR, and VIRON domains. Use whenever work needs a durable specification or issue ID, implementation plan, verification report, governance lifecycle, traceability, paper registry update, legacy-paper migration, or closure decision under papers/.
---

# VIR Paper Management

Use VPS papers as auditable specifications and governance records, not as
substitutes for code, tests, or ordinary user documentation.

## Required context

1. Read `papers/STANDARD.md` before creating or changing a paper.
2. Inspect `papers/REGISTRY.yaml` and the relevant domain directory.
3. Read the active source, tests, and linked papers needed to substantiate the
   task. Do not infer current architecture from filenames or legacy plans.
4. Use `./paper` for allocation, linking, registry maintenance, and validation.
5. If the work changes Vir syntax, semantics, compiler behavior, modules, or
   standard-library APIs, also follow the applicable Vir skills and
   authoritative specifications.

`papers/STANDARD.md` is canonical. Do not restate its lifecycle tables, field
definitions, or closure rules here.

## Evidence vocabulary

Label claims during investigation:

- `CONFIRMED`: proven by authoritative source, deterministic test, or direct
  inspection with a stable reference.
- `OBSERVED`: directly seen in the current checkout or tool output, but not yet
  established as a general cause or invariant.
- `HYPOTHESIS`: plausible explanation requiring verification.
- `NOT_VERIFIED`: explicitly outside the completed investigation.

Never upgrade a hypothesis to a fact because it appears in an old plan or
report. Record contradictory evidence and uncertainty.

## Workflow A — Capture or triage an ISSUE

1. Search the registry for duplicate or superseded work.
2. Reproduce or inspect the reported behavior. Record the exact command, input,
   revision, output, and affected component when available.
3. Create the paper with `./paper new issue <domain> "<title>"`.
4. Separate expected behavior, actual behavior, evidence, scope, impact, and
   preliminary analysis. Use the evidence vocabulary above.
5. Write measurable acceptance criteria. Do not prescribe an implementation
   unless it is necessary to define the expected behavior.
6. Do not change code immediately while the cause or governing constraint is
   still unverified; finish the audit or record the uncertainty first.
7. Set severity from impact and priority from scheduling intent independently.
8. Advance status only when its lifecycle gate is satisfied.

## Workflow S — Create or revise a SPEC

1. Search the registry and aliases before allocating a new identity.
2. Create with `./paper new spec <domain> "<title>" --version <semver> \
   --language <tag> --spec-class <class>`.
3. Keep the ID stable across compatible revisions. Increment `version`, update
   `updated`, and append a dated Revision History row for every normative change.
4. Use a new ID plus reciprocal supersession only when identity or scope changes
   materially; never overwrite or reuse an old ID.
5. Keep the canonical file under `papers/<DOMAIN>/specs/`; record former paths
   in `aliases` and update active references to use the canonical SPEC ID/path.
6. Verify syntax, semantics, APIs, and architecture claims against the relevant
   authoritative source and companion Vir skills.

## Workflow B — Design or revise a PLAN

1. Start from verified source ISSUEs. Create with
   `./paper new plan <domain> "<title>" --issue <ISSUE-ID>`.
2. Inspect active implementation paths and tests before describing current
   architecture.
3. State scope and non-goals, design decisions, alternatives, compatibility,
   migration, validation, risks, rollback, and measurable exit criteria.
4. Split implementation into reviewable phases with concrete files/modules and
   dependencies.
5. Link every additional source ISSUE with `./paper link`.
6. During implementation, do not rewrite the PLAN to make deviations disappear.
   Put actual behavior and deviations in the REPORT.

## Workflow C — Implement and report

1. Treat the approved PLAN and linked ISSUE acceptance criteria as constraints.
2. Make the code and test changes using the relevant repository workflows.
3. Create the report with
   `./paper new report <domain> "<title>" --issue <ISSUE-ID> --plan <PLAN-ID>`.
4. Derive the implementation summary from the actual diff. Map verification to
   each acceptance criterion and preserve commands/results as evidence.
5. Record deviations, limitations, regressions, and unresolved work plainly.
   Create linked ISSUEs for independent remaining problems.
6. Select exactly one report conclusion defined by the standard. Do not claim
   `READY_FOR_CLOSE` when evidence is incomplete.

## Workflow D — Verify and close

1. Re-run the relevant tests and independent acceptance checks on the current
   tree. Compilation alone is not sufficient verification.
2. Confirm the REPORT is accepted and links reciprocally to its PLAN and ISSUEs.
3. Confirm each ISSUE acceptance criterion has direct evidence and that known
   limitations are either accepted explicitly or tracked by linked ISSUEs.
4. Run `./paper validate` and require a clean result.
5. Only then move the ISSUE through RESOLVED to CLOSED. Add a revision-history
   row for each meaningful status or evidence change.

## Workflow E — Audit or migrate legacy documents

1. Consult `papers/LEGACY_INVENTORY.md`; do not move or delete legacy files
   automatically.
2. Verify each claim against active code and tests.
3. Classify content by governance role, not filename. Split mixed documents into
   separate SPEC, ISSUE, PLAN, and REPORT papers when needed.
4. Allocate new production IDs; never reuse `0000` or fabricate historical IDs.
5. Cite the legacy path and commit as provenance, and preserve the original.
6. Mark unverifiable statements `NOT_VERIFIED` and avoid manufacturing a
   completed lifecycle from incomplete history.

## Final checks

Run:

```sh
./paper registry --check
./paper validate
```

Before finishing, inspect the resulting diff and report created IDs, lifecycle
state, evidence run, unresolved limitations, and whether closure gates passed.

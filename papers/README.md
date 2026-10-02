# VIR Papers

`papers/` contains repository governance artifacts governed by the
[VIR Paper Standard](STANDARD.md). This is an internal audit-friendly standard,
not an official ISO standard.

## What is a Paper?

A Paper is a versioned technical artifact with a stable ID, lifecycle state,
owner, links, and evidence:

- SPEC: canonical architecture, algorithm, behavior, contract, or reference;
- ISSUE: what is wrong or needs investigation;
- PLAN: how verified issues will be addressed;
- REPORT: what was actually implemented and verified.

Canonical specifications live in the matching `papers/<DOMAIN>/specs/`
directory. User-facing guides and supporting artifacts may remain under
`docs/`, but they MUST reference the canonical SPEC ID.

Create an ISSUE for a reproducible problem, gap, or investigation that needs a
durable acceptance contract. Create a PLAN only when one or more source ISSUEs
are understood well enough to design verified work. Create a REPORT after
implementation, from the actual diff and executed verification evidence.

## IDs and paths

```text
<DOMAIN>-<KIND>-<NNNN>
```

Domains are `VIR`, `VIRC`, `VLSP`, `STLB`, `IVIR`, and `VIRON`; kinds are `SPC`,
`ISS`, `PLN`, and `RPT`. Files use `<ID>_<short_slug>.md` in the matching
domain/type directory.
Sequence `0000` is reserved for examples and tests.

## Commands

Run from the repository root:

```bash
./paper validate
./paper list
./paper show VIRC-ISS-0001
./paper new spec VIR "Vir language specification" --version 2.1.0 \
  --language en --spec-class SPECIFICATION
./paper new issue VIRC "Parser recovery failure"
./paper new plan VIRC "Parser recovery repair" --issue VIRC-ISS-0001
./paper new report VIRC "Parser recovery verification" \
  --issue VIRC-ISS-0001 --plan VIRC-PLN-0001
./paper link VIRC-ISS-0001 VIRC-PLN-0001
./paper registry --check
```

`new issue` defaults to `S2`/`P2`; edit those fields after triage. `new plan`
requires at least one `--issue`; `new report` requires at least one `--issue`
and one `--plan`, so the CLI does not create an untraceable paper. `link` writes
reciprocal metadata and revision history. `registry --write` deterministically
rebuilds the production index.

After a manual metadata change such as a lifecycle transition, append a
revision-history row and run `./paper registry --write` before validation.

The CLI uses only the Python standard library. JSON Schemas remain available to
editors and external validators; `./paper validate` enforces the same VPS
contract without requiring a third-party schema package.

## Typical workflow

1. Search the registry and canonical SPEC IDs before creating a paper.
2. Reproduce and separate confirmed facts, observations, and hypotheses.
3. Create a PLAN only after auditing active code and constraints.
4. Implement without rewriting the PLAN to hide deviations.
5. Create a REPORT from the actual diff and executed verification.
6. Move the ISSUE through VERIFYING/RESOLVED and close only after acceptance.

## AI Skill

The project skill is:

```text
.agents/skills/vir-paper-management/SKILL.md
```

It routes AI work through this standard and references `papers/STANDARD.md` as
the canonical source rather than duplicating it.

## Legacy documents

No legacy document was migrated automatically during VPS initialization. See
[LEGACY_INVENTORY.md](LEGACY_INVENTORY.md) for the audited inventory and staged
migration recommendation.

---
id: "VIRON-PLN-0001"
type: "PLAN"
domain: "VIRON"
title: "Implement the end-to-end Viron lifecycle"
status: "DRAFT"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "VIRON"
components:
  - "architecture"
  - "cli"
  - "project-model"
  - "resolver"
  - "toolchain"
  - "package-cache"
  - "registry"
  - "stdlib-lifecycle"
  - "ci-cd"
related:
  issues:
    - "VIRON-ISS-0001"
    - "VIRON-ISS-0002"
    - "VIRON-ISS-0003"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "end-to-end"
  - "local-first"
  - "bootstrap"
  - "package-management"
  - "supply-chain"
  - "release"
---

# VIRON-PLN-0001 — Implement the end-to-end Viron lifecycle

## 1. Objective

Triển khai Viron thành sản phẩm Vir-native chạy end-to-end, từ tạo project và
phát triển library cục bộ đến resolve/lock dependency, chọn toolchain/sysroot,
build/test/package, secure cache/fetch, registry publish và quản lý standard
library. Kết quả phải reproducible, kiểm thử được khi offline, không phụ thuộc
CWD và không đẩy network/package-resolution responsibility vào compiler.

PLAN ưu tiên một vertical slice local-first trước. Registry/CDN, stdlib release
và GitHub CI/CD chỉ được nối sau khi cùng production command đã hoạt động trên
local fixtures. Đây là plan triển khai; mọi thay đổi semantic/schema công khai
phải được phản ánh vào VIRON SPEC tương ứng và qua review riêng.

## 2. Source Issues

- `VIRON-ISS-0003` — umbrella integration gap across all lifecycles.
- `VIRON-ISS-0002` — missing executable library-development workflow.
- `VIRON-ISS-0001` — missing standard-library lifecycle manager.

Thứ tự dependency là `ISS-0002` local vertical slice → toolchain/cache/registry
foundation → `ISS-0001` stdlib lifecycle → release/conformance closure. Có thể
song song hóa unit-level modules sau khi Phase 0 chốt contract, nhưng không bỏ
qua các phase gates.

## 3. Scope

### In Scope

- reconcile `VIRON-SPC-0001..0006` với code và bổ sung conformance criteria;
- standalone Viron project, mandatory `module.list`, CLI entrypoint và build;
- project discovery, `vir.toml`, `vir.lock`, local path dependencies;
- deterministic SemVer resolution, module map và compiler dispatch;
- toolchain/sysroot install/select/update/uninstall/rollback;
- immutable package cache, secure download/extract và offline/frozen modes;
- registry client, package archive, dry-run publish và production publish gate;
- lifecycle cho compiler-coupled stdlib và independently versioned libraries;
- migration khỏi legacy/stub/test surfaces hiện tại;
- production test matrix, CI/CD, release artifacts, provenance và REPORT.

### Out of Scope

- thay đổi syntax/semantics của ngôn ngữ Vir không cần cho interface Viron;
- nội dung hoặc public API của từng stdlib module, thuộc STLB;
- compiler backend/codegen work ngoài explicit sysroot/module-map interface;
- quản lý package hệ điều hành qua Homebrew/APT như một phần của Vir package
  manager;
- tự xây registry/CDN production trước khi local/mock protocol conformance xanh;
- chọn nhà cung cấp hosting, identity hoặc secret manager cụ thể trong PLAN này;
- cam kết backward compatibility cho DRAFT schemas chưa từng được phát hành.

## 4. Current Architecture

### 4.1 Runtime/build surface

- Không có `bin/viron` hoặc standalone Viron project.
- `stdlib/vir/viron/` chứa các dispatcher/command module nhưng không có `main`,
  project `module.list`, manifest hoặc lockfile.
- `stdlib/vir/viron/pkg_cmd.vri` gọi Homebrew; đây là host package adapter, không
  phải Vir package manager.
- `stdlib/vir/pkg/pkg.vri` chứa resolver/registry stubs và không qua compiler
  check vì import/export contract hiện hỏng.

### 4.2 Module/toolchain surface

- `stdlib/stdlib.vri` là source-tree registry tĩnh.
- Compiler tự dò registry theo các path tương đối và chưa có public
  `--sysroot`/`--module-map` flags như DRAFT architecture mô tả.
- Chỉ compiler và một số fixtures có project `module.list`; Viron và LSP chưa có
  registry project độc lập.

### 4.3 Test/release surface

- Python tests trỏ `src.viron` không tồn tại.
- Bootstrap fixture tự cài lại SemVer/DAG; Viron vtest cases pass vô điều kiện.
- Không có repository GitHub workflow cho Viron/package/release conformance.
- Sáu VIRON SPEC đều DRAFT và chưa có schema fixtures hay compatibility matrix
  đủ để xem là standardized contract.

## 5. Proposed Architecture

### 5.1 Project layout

Layout mục tiêu đề xuất; tên cuối cùng được chốt ở Phase 0 và ghi vào SPEC:

```text
viron/
├── module.list
├── vir.toml
├── src/
│   ├── main.vri
│   ├── cli/
│   ├── config/
│   ├── project/
│   ├── manifest/
│   ├── lock/
│   ├── resolve/
│   ├── module_map/
│   ├── toolchain/
│   ├── cache/
│   ├── registry/
│   ├── package/
│   ├── stdlib/
│   ├── security/
│   └── diagnostic/
└── tests/
    ├── fixtures/
    └── integration/
```

Mọi Vir project do Viron tạo hoặc quản lý bắt buộc có `module.list`. `vir.toml`
mô tả package/project intent; `vir.lock` ghi exact resolved dependency state;
`module-map.json` là generated build input, không thay thế hai file trên.

### 5.2 Control flow

```text
CLI adapter
  → project/config discovery
  → manifest + module.list validation
  → lock/resolution service
  → toolchain + sysroot selection
  → cache materialization (network only when policy permits)
  → deterministic module-map generation
  → virc/LSP process adapter with explicit inputs
  → structured diagnostic/exit-code translation
```

Package/publish flow dùng cùng manifest, resolver và archive validator:

```text
source project → validate → reproducible archive → checksum/signature/provenance
               → dry-run contract → upload immutable artifact → publish metadata last
```

### 5.3 Ownership boundaries

- **VIRON:** CLI orchestration, project/package schemas, resolver, toolchain,
  cache, registry transport, lifecycle transactions and diagnostics.
- **VIRC:** parse/check/build inputs supplied locally; no registry/network/version
  solving. Compiler interface changes require linked VIRC ISSUE/PLAN.
- **STLB:** module content, API/compatibility policy and release classification;
  VIRON owns distribution/install mechanics. STLB changes require linked papers.
- **Registry/CDN:** registry serves metadata/authorization; CDN/object storage
  serves immutable artifacts. Neither is reimplemented inside compiler.

### 5.4 State and transaction model

- `VIR_HOME` (final name subject to SPEC) is injectable for tests and contains
  immutable packages, toolchains, channels/index metadata, locks and staging.
- Mutations use: acquire scoped lock → stage under same filesystem → verify →
  fsync/durable boundary where supported → atomic publish → update metadata last.
- Resolved state always stores exact version, target/toolchain compatibility,
  checksum and provenance. Floating channels are inputs, never installed truth.
- Network access is confined to bootstrap/registry transports and prohibited in
  compiler. Offline/frozen policy is evaluated before any request.
- Diagnostics carry stable code, operation, package/toolchain identity, path and
  remediation; human and JSON rendering share one diagnostic model.

## 6. Design Decisions

### Decision 1 — Bootstrap with a local-first vertical slice

**Decision:** Implement scaffold → path resolve → lock/module map → check/build/
test → package before registry integration.

**Rationale:** This proves product boundaries and package invariants without
depending on unavailable remote infrastructure.

**Alternatives considered:** Build Registry/CDN first.

**Trade-offs:** Remote install arrives later, but early tests are deterministic
and the server is built against a real producer/consumer contract.

### Decision 2 — Standalone top-level Viron project

**Decision:** Move the product entrypoint and domain services into a standalone
`viron/` project with its own mandatory `module.list`.

**Rationale:** Viron is a tool, not merely a stdlib module, and needs independent
bootstrap, dependency, test and release boundaries.

**Alternatives considered:** Continue adding commands under `stdlib/vir/viron`.

**Trade-offs:** Requires staged migration/adapters for legacy commands, but
prevents tool lifecycle from being coupled to stdlib source layout.

### Decision 3 — Thin CLI adapters, testable domain services

**Decision:** Parsing/rendering stays in CLI adapters; manifest, resolution,
transactions and compatibility live in deterministic services.

**Rationale:** The same production logic can serve CLI, tests, CI and future API
clients without algorithm copies.

**Alternatives considered:** Command handlers directly mutate filesystem/network.

**Trade-offs:** More explicit interfaces and types up front, substantially better
negative testing and rollback behavior.

### Decision 4 — Three distinct project artifacts

**Decision:** `module.list`, `vir.toml` and `vir.lock` remain distinct mandatory/
generated roles; module map is generated per build.

**Rationale:** Module identity, package intent, resolved state and compiler input
have different ownership and invalidation rules.

**Alternatives considered:** Derive modules from filesystem or merge everything
into a single manifest.

**Trade-offs:** More files, but deterministic resolution and reviewable changes.

### Decision 5 — Compiler receives explicit local inputs

**Decision:** Viron invokes `virc` with explicit toolchain/sysroot/module-map
inputs; compiler performs no network or package solving and stops CWD probing.

**Rationale:** Preserves responsibility boundary and reproducible builds.

**Alternatives considered:** Teach compiler to discover/cache packages.

**Trade-offs:** Requires coordinated VIRC paper and compatibility rollout.

### Decision 6 — Separate sysroot core from versioned libraries

**Decision:** Compiler-coupled core/runtime ships in toolchain sysroot;
independently versioned official/third-party libraries use immutable package
cache. Module map combines both.

**Rationale:** Avoids updating compiler ABI/runtime accidentally when updating a
library, while keeping compiler-required content coherent.

**Alternatives considered:** Put all stdlib in sysroot or all in package cache.

**Trade-offs:** Requires STLB classification and compatibility metadata.

### Decision 7 — One package engine, host package commands outside it

**Decision:** Vir package commands use one resolver/cache/registry engine.
Homebrew-style commands are renamed, isolated as optional host adapters, or
removed; they cannot retain ambiguous `pkg` ownership.

**Rationale:** Prevents users and tests from conflating OS packages with Vir
packages.

**Alternatives considered:** Extend current `pkg_cmd.vri` in place.

**Trade-offs:** Potential CLI migration for any undocumented current users.

### Decision 8 — Authenticated metadata plus content integrity

**Decision:** SHA-256 content verification is necessary but insufficient;
release metadata requires a versioned trust/signature contract and provenance.

**Rationale:** A checksum delivered by an untrusted channel does not establish
artifact authenticity.

**Alternatives considered:** Checksum-only downloads.

**Trade-offs:** Key management and rotation increase operational complexity and
must be resolved before production publish.

### Decision 9 — Reproducible archives and metadata-last publish

**Decision:** Normalize paths/order/timestamps/permissions in archives; upload
immutable artifact/checksum/signature first and expose registry metadata last.

**Rationale:** Consumers never observe metadata pointing at a partial artifact.

**Alternatives considered:** Mutable release paths or metadata-first publish.

**Trade-offs:** Retry/garbage-collection logic is needed for orphaned uploads.

### Decision 10 — CI/CD calls production commands

**Decision:** CI invokes the same Viron check/test/package/publish-dry-run paths
used locally. GitHub Actions may be a runner, never a semantic implementation or
runtime dependency.

**Rationale:** Prevents local/CI divergence and makes another runner replaceable.

**Alternatives considered:** Shell/Python workflow scripts implementing resolver
or packaging.

**Trade-offs:** CI adoption waits until the relevant production commands exist.

## 7. Implementation Plan

### Phase 0 — Reconcile and review contracts

- **files/modules:** `papers/VIRON/specs/VIRON-SPC-0001..0006`, new linked
  VIRC/STLB ISSUE/PLAN papers when crossing ownership boundaries, schema fixtures.
- **changes:** specify mandatory project/archive `module.list`; CLI and exit-code
  taxonomy; `vir.toml`, `vir.lock`, module-map and registry schema versions;
  toolchain/target compatibility; archive format; registry endpoint discovery;
  trust root/signature/key rotation; cross-platform atomicity; offline/frozen
  semantics; stdlib classification.
- **dependencies:** current code audit and `papers/STANDARD.md` lifecycle.
- **gate:** unresolved contradictions are recorded; affected SPECs enter REVIEW,
  not ACTIVE, with executable schema/conformance fixtures assigned.

### Phase 1 — Establish standalone Viron project and green baseline

- **files/modules:** proposed `viron/module.list`, `viron/vir.toml`,
  `viron/src/main.vri`, `cli`, `diagnostic`, build target and smoke tests.
- **changes:** create canonical entrypoint; grouped Vir declarations and explicit
  `in`/`out`/`ref` signatures per Vir clean-code rules; register commands; expose
  stable exit codes and JSON diagnostics; build reproducibly to `bin/viron`.
- **dependencies:** compiler can check required canonical stdlib exports.
- **gate:** all production source passes `virc --check`; `viron --help` and
  `viron --version` smoke tests pass from repository root and alternate CWD.

### Phase 2 — Deliver the network-free library vertical slice

- **files/modules:** `project`, `manifest`, `module_map`, local `resolve`, process
  adapter, fixtures with app/library/path dependency.
- **changes:** implement project discovery and `new --lib`; generate mandatory
  `module.list`, `vir.toml`, `src/lib.vri`, tests; validate canonical module IDs;
  resolve path dependencies; generate exact local lock/module map; dispatch
  check/build/test; create initial reproducible package archive.
- **dependencies:** Phase 1, module registry rules from `vir-stdlib-modules`.
- **gate:** a clean temp workspace completes new/check/build/test/package with
  networking disabled from two CWDs and produces byte-identical archives.

### Phase 3 — Implement deterministic manifest, lock and resolver

- **files/modules:** `manifest`, `lock`, `resolve`, SemVer adapter, golden schemas.
- **changes:** parse/validate typed TOML; support exact/range/transitive
  dependencies, target/features, cycle/conflict/yanked-version policy; reuse and
  harden canonical SemVer implementation rather than fixture copies; serialize
  stable lock ordering/checksums/provenance; implement `--locked`/`--frozen`.
- **dependencies:** Phase 0 schema decisions and Phase 2 local pipeline.
- **gate:** resolver unit/property tests and golden lockfiles pass; identical
  input yields identical lock; conflict/cycle diagnostics are stable.

### Phase 4 — Implement toolchain, sysroot and compiler handoff

- **files/modules:** `toolchain`, `config`, shim/process adapter, sysroot layout;
  linked VIRC files/papers for explicit CLI input.
- **changes:** injectable `VIR_HOME`; install/list/default/uninstall/update/
  rollback toolchains; validate target/host compatibility; materialize sysroot;
  generate module map; invoke compiler/LSP with explicit paths; remove compiler
  source-tree probing after compatibility window.
- **dependencies:** approved VIRC interface and STLB sysroot classification.
- **gate:** build succeeds outside checkout/from alternate CWD; incompatible or
  missing toolchains fail before compiler execution; compiler performs no network.

### Phase 5 — Implement immutable cache and secure acquisition

- **files/modules:** `cache`, `security`, download/extract transaction, filesystem
  locks, corruption fixtures.
- **changes:** content-addressed/immutable storage; scoped inter-process locks;
  staging and atomic publish on supported platforms; size/path/symlink limits;
  SHA-256 and authenticated metadata/signature verification; cleanup/retry;
  verify/repair/rollback; offline/frozen cache policy.
- **dependencies:** Phase 0 trust/archive decisions and Phase 4 state layout.
- **gate:** corrupt, malicious traversal, interrupted, concurrent and disk-full
  simulations preserve last known-good state; offline cache hit uses no network.

### Phase 6 — Implement registry, packaging and publish lifecycle

- **files/modules:** `registry` transport/client, package validator/archive,
  credential abstraction, mock registry and protocol fixtures.
- **changes:** configurable endpoint/mirror; search/metadata/fetch; reproducible
  package containing manifest, `module.list`, source, license and provenance;
  login/token boundary; `publish --dry-run`; publish/yank/owner actions; upload
  immutable artifact before metadata. Resolve `.tar.zst` versus supported codec
  in SPEC before coding, never silently substitute format.
- **dependencies:** Phases 3 and 5; approved protocol/trust schemas.
- **gate:** mock registry round-trip package → publish → resolve → clean-cache
  fetch → consumer build passes; dry-run performs zero remote mutation.

### Phase 7 — Implement standard-library lifecycle

- **files/modules:** `stdlib` service/commands, catalog/compatibility metadata,
  sysroot/package adapters; linked STLB papers.
- **changes:** implement `viron std install/list/update/verify/repair/rollback`;
  keep `self`, `toolchain`, `std` and project-dependency updates independent;
  install core/runtime with toolchain and versioned `vir.*` through package
  cache; merge both into deterministic module map.
- **dependencies:** Phases 4–6 and `VIRON-ISS-0001` contract decisions.
- **gate:** upgrade/downgrade/incompatibility/corruption/interruption/offline
  matrix passes without cross-lifecycle side effects.

### Phase 8 — Migrate legacy surfaces and consumers

- **files/modules:** `stdlib/vir/viron`, `stdlib/vir/pkg`, Viron/Python/bootstrap
  tests, docs/examples and any compatibility adapters.
- **changes:** replace stubs with adapters to the production engine or delete
  dead code; isolate/rename/remove Homebrew package commands; move reusable
  helpers only after exports/checks are green; replace duplicated fixture
  algorithms and unconditional passes; retire nonexistent Python implementation;
  update all affected `module.list` entries and imports.
- **dependencies:** production replacement and deprecation decision.
- **gate:** repository search finds no unapproved package stub, ambiguous host
  package command, fake Viron pass or test import of deleted surface.

### Phase 9 — Add CI/CD and release automation

- **files/modules:** repository CI workflows, release config/scripts limited to
  orchestration, fixtures and provenance policy.
- **changes:** PR jobs run formatting/check/unit/integration/conformance and
  paper validation; supported host/target matrix; release tag builds Viron and
  toolchain artifacts; emit checksums/signatures/SBOM or approved provenance;
  upload archive then metadata; smoke-install into fresh `VIR_HOME` and build a
  consumer. Secrets are least-privilege and release environments protected.
- **dependencies:** production commands from Phases 1–8. GitHub is optional as
  runner; workflow semantics stay portable.
- **gate:** clean release candidate passes on supported matrix and a fresh client
  can verify/download/install/build solely from published contract.

### Phase 10 — End-to-end verification and closure

- **files/modules:** VIRON REPORT, traceability matrix, benchmark/security logs,
  final operator/developer docs.
- **changes:** execute clean-home, offline/frozen, alternate-CWD, corruption,
  interruption, concurrency, rollback, mock/production-read-only registry and
  consumer scenarios; record exact revision/commands/results/artifacts; compare
  all acceptance criteria and SPEC conformance.
- **dependencies:** all prior phase gates.
- **gate:** REPORT reaches VERIFIED; associated SPEC lifecycle is justified;
  `ISS-0001..0003` move VERIFYING then RESOLVED only with cited evidence.

## 8. Compatibility

- **Source:** generated projects use canonical module IDs and mandatory
  `module.list`; legacy projects need an explicit migration/check command.
- **CLI:** command/exit/JSON diagnostic contracts are versioned before public
  release. Legacy system commands receive deprecation aliases only when their
  behavior is unambiguous and safe.
- **Compiler:** introduce explicit inputs during a compatibility window; warning
  precedes removal of CWD-based stdlib probing. Coordinate via VIRC paper.
- **Serialized formats:** every manifest/lock/module-map/metadata schema carries
  a version and rejects unsupported future versions deterministically.
- **Cache:** immutable entries are never edited in place. Layout migration uses
  copy/verify/switch and can retain prior state for rollback.
- **Registry:** endpoint and protocol version are configuration/discovery data,
  not duplicated hard-coded constants.
- **Stdlib:** compiler-coupled runtime follows toolchain compatibility; independent
  libraries follow SemVer/package policy. Classification requires STLB approval.
- **LSP:** LSP receives the same resolved toolchain/module map as compiler; it
  must not implement a second resolver.

## 9. Migration

1. Inventory current commands/importers/tests and classify keep, adapt, rename or
   delete; publish the mapping before moving source.
2. Land standalone Viron and local vertical slice without redirecting legacy
   commands; keep comparison fixtures during bootstrap.
3. Add adapters from any retained stdlib surface to production services; no
   duplicated resolver/cache state is allowed.
4. Provide `viron migrate` or equivalent check/fix flow that creates/validates
   `vir.toml` and mandatory `module.list`, then regenerates lock/module map.
5. Introduce explicit compiler inputs and deprecation diagnostics before removing
   source-tree discovery.
6. Import or invalidate cache/toolchain state transactionally; never mutate an
   unknown legacy directory in place.
7. Remove stubs, fake tests and aliases only after usage audit and replacement
   tests pass. Record breaking changes in release notes and migration docs.

## 10. Validation Plan

- **Unit:** TOML/schema validation, SemVer/range operations, graph solving,
  deterministic serialization, path normalization, target compatibility,
  diagnostics and transaction state machines.
- **Property/fuzz:** resolver determinism, lock round-trip, archive traversal,
  malformed metadata/signature, module ID/path normalization.
- **Integration:** temporary injected `VIR_HOME`, local path dependencies,
  mock registry, toolchain install/switch, std lifecycle and compiler/LSP dispatch.
- **End-to-end:** new library → dependency → lock/module map → build/test →
  package → dry-run/publish mock → empty-cache consumer install/build.
- **Failure:** offline cache miss, frozen drift, cycle/conflict, incompatible
  target, checksum/signature mismatch, interrupted extraction, concurrent writers,
  rollback, read-only filesystem and disk-full behavior.
- **Reproducibility:** alternate CWD, clean environment and two builds produce
  identical lock/module map/archive hashes where the contract promises it.
- **Conformance:** fixture per schema/protocol version and ownership boundary;
  tests cite the SPEC clause they verify.
- **Regression:** full compiler/stdlib/LSP suites plus `./paper validate`.
- **Evidence:** Phase 10 REPORT records exact revision, environment, command,
  output and artifact digests; unchecked boxes are not inferred as passed.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| DRAFT SPECs conflict with implementation needs | High | High | Resolve in Phase 0; never promote or code ambiguous contract silently. |
| Compiler interface work expands VIRON scope | High | High | Open/link VIRC ISSUE/PLAN; use explicit ownership and compatibility gate. |
| Vir bootstrap cannot compile required stdlib helpers | High | High | Establish Phase 1 green baseline; harden exports incrementally; avoid copied production algorithms. |
| Resolver semantics become nondeterministic | Medium | High | Canonical ordering, golden/property tests and exact lock state. |
| Cache/install corruption under interruption or concurrency | Medium | Critical | Scoped locks, same-filesystem staging, verify-before-publish, recovery tests. |
| Checksum-only design permits malicious metadata | Medium | Critical | Versioned authenticated metadata, signature/trust-root and rotation policy. |
| Archive format in SPEC is unsupported by stdlib | High | Medium | Decide/implement codec in Phase 0/6; fail explicitly, never relabel compression. |
| Windows atomicity/path behavior differs from POSIX | High | High | Platform-specific transaction adapter and fault-injection matrix. |
| Registry/CDN delays block all progress | Medium | High | Local-first and mock-registry gates isolate remote dependency. |
| CI scripts become a second package manager | Medium | High | CI may only orchestrate production Viron commands and verify artifacts. |
| Legacy Homebrew `pkg` command causes unsafe migration | Medium | Medium | Separate namespace, usage audit, deprecation/alias with explicit diagnostics. |
| Supply-chain credentials leak or overreach | Low | Critical | OIDC/short-lived least-privilege credentials, protected release environment, no secrets in artifacts/logs. |

## 12. Rollback Strategy

- Land phases behind explicit commands/feature gates; do not overwrite the last
  known-good toolchain, cache entry or lockfile.
- Every installation/update retains prior resolved metadata until new state is
  verified and atomically selected; rollback switches pointer/selection, not
  mutable contents.
- Keep legacy compiler discovery during a bounded deprecation window; revert the
  Viron handoff independently if explicit-input integration fails.
- Registry publish is immutable: yank/bad-release metadata and publish a new
  version; never replace an existing artifact checksum.
- CI/release automation can be disabled without disabling local production
  commands. A workflow rollback never changes package semantics.
- If a phase gate fails, stop at the last green vertical slice, capture evidence
  in the issue and do not advance linked papers to IMPLEMENTING/VERIFYING.

## 13. Exit Criteria

- [ ] Phase 0 contracts reviewed; required VIRC/STLB papers linked.
- [ ] Standalone Viron builds and all production source passes compiler checks.
- [ ] Local-first library vertical slice passes without network from alternate CWD.
- [ ] Resolver/lock/module map is deterministic and fully tested for conflicts.
- [ ] Toolchain/sysroot handoff removes compiler network/CWD discovery dependency.
- [ ] Secure cache/acquisition failure and concurrency matrix passes.
- [ ] Mock registry package/publish/consumer round trip passes.
- [ ] Standard-library install/update/verify/repair/rollback matrix passes.
- [ ] Legacy stubs, fake tests and ambiguous host-package surface are migrated.
- [ ] CI/release jobs use production commands and verify published provenance.
- [ ] All relevant test suites and `./paper validate` pass.
- [ ] VIRON verification REPORT is VERIFIED with traceability to every criterion.
- [ ] `VIRON-ISS-0001`, `VIRON-ISS-0002` and `VIRON-ISS-0003` are RESOLVED only
  after evidence review; this PLAN may then move COMPLETED.

## 14. Related Papers

- `VIRON-ISS-0001` — standard-library lifecycle manager.
- `VIRON-ISS-0002` — executable library-development workflow.
- `VIRON-ISS-0003` — end-to-end integration umbrella.
- `VIRON-SPC-0001` — architecture/responsibility boundary (DRAFT).
- `VIRON-SPC-0002` — module resolution (DRAFT).
- `VIRON-SPC-0003` — package format/manifest/lockfile (DRAFT).
- `VIRON-SPC-0004` — registry protocol/lifecycle (DRAFT).
- `VIRON-SPC-0005` — security/integrity/concurrency (DRAFT).
- `VIRON-SPC-0006` — toolchain/sysroot (DRAFT).
- Verification REPORT: not created; create during Phase 10 against the implemented
  revision rather than before evidence exists.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Created DRAFT end-to-end implementation plan from VIRON-ISS-0001..0003. |
| 2026-10-03 | Defined local-first phase order, architecture, validation gates and rollback. |

---
id: "VIRC-PLN-0004"
type: "PLAN"
domain: "VIRC"
title: "Separate compiler source tree and modularize compiler passes"
status: "DRAFT"
created: "2026-10-02"
updated: "2026-10-02"
owners:
  - "VIRC"
components:
  - "repository-migration"
  - "compiler-source-layout"
  - "module-resolution"
  - "semantic-passes"
  - "optimizer"
  - "self-hosting"
  - "language-server"
  - "vscode-extension"
related:
  issues:
    - "VIRC-ISS-0006"
  plans: []
  reports:
    - "VIRC-RPT-0002"
    - "VIRC-RPT-0003"
supersedes: null
superseded_by: null
tags:
  - "architecture"
  - "copy-migration"
  - "modularization"
  - "module-list"
  - "sequential-migration"
  - "editor-tooling"
---

# VIRC-PLN-0004 — Separate compiler source tree and modularize compiler passes

## 1. Objective

Tách canonical compiler source khỏi cây standard library, thiết lập
`compiler/module.list` làm nguồn ánh xạ module nội bộ, rồi module hóa tuần tự
các compiler pass lớn thành orchestrator mỏng và các rule/transform độc lập.

Implementation đích diễn ra trong repository sibling
`/Users/gengyang/Vir-3.0`. Trước khi chuyển compiler source, plan phải seed tree
mới bằng tài liệu không-legacy, VPS papers/tool/skill, toàn bộ test suite và các
runner scripts cùng dependency closure của chúng. Native `vir-lsp` và
`vscode-vir` cũng được nhập như hai payload tooling có provenance riêng. Đây là
thao tác copy có provenance, không phải move hoặc chỉnh sửa checkout nguồn.

Kết quả cần đạt không chỉ là nhiều file nhỏ hơn. Kiến trúc mới phải có ownership
rõ ràng, dependency một chiều, module identity ổn định, generated bundle tái
tạo được, và verification đủ mạnh để một lần tách file không âm thầm đổi ngữ
nghĩa compiler.

Baseline của plan là snapshot source hiện tại:

```text
snapshot commit: fd0064ea516c132b57cd9dec8acf827ed4361555
snapshot tree:   521698301f57ebe84a62ae690e2ac8d48b2be419
parent commit:   58b8b39a4c65b00a7bb98df6fe40a1480bdf3e0e
source label:    Vir 4.0.0 working source
```

Snapshot lấy source đang có trong working tree theo chỉ định của user, gồm các
tracked modifications và source-like untracked files, nhưng loại cache,
diagnostic state, packaged editor artifacts, untracked executables và nested Git
metadata. Worktree tiền xử lý được tạo trực tiếp từ snapshot này. Plan không yêu
cầu snapshot ban đầu phải xanh; lỗi sẵn có và lỗi do module hoá phải được ghi
nhận, cô lập và xử lý tuần tự theo phase thay vì đổi lại baseline cũ.

## 2. Source Issues

- `VIRC-ISS-0006` — compiler source đang lẫn trong stdlib và nhiều pass file
  vượt quá một responsibility có thể audit độc lập.

Các issue `VIRC-ISS-0001`, `VIRC-ISS-0002`, và `VIR-ISS-0002` cung cấp context
cho optimizer, register allocation, và type-system work. Plan này không được
dùng việc đổi file để tuyên bố các thuật toán trong những issue đó đã hoàn tất.

## 3. Scope

### In Scope

- tạo repository tree đồng cấp `/Users/gengyang/Vir-3.0` bằng copy có manifest;
- copy `docs/**` nhưng loại toàn bộ `docs/_legacy/**`;
- copy `papers/**`, root `paper`, `tools/paper.py`, paper schemas/templates và
  `.agents/skills/vir-paper-management/**`;
- copy toàn bộ `tests/**`, root `run_tests.sh`, active run/test/audit scripts và
  transitive helper files mà các runner gọi;
- copy tracked source của native `vir-lsp` repository vào `tools/vir-lsp/` và
  copy canonical source/config/test/assets của `tools/vscode-vir/`;
- giữ LSP build/test integration đang có trong source snapshot;
- tạo top-level `compiler/` làm owner của self-hosted compiler source;
- tạo và kiểm tra `compiler/module.list`;
- chuyển compiler-internal include/import sang một canonical project namespace;
- loại compiler implementation khỏi `stdlib/stdlib.vri`;
- phân lớp source theo bootstrap, frontend, semantic, IR, optimizer, backend,
  CLI/tooling, IDE facts, và generated output;
- định nghĩa module policy, naming policy, pass contract, dependency direction,
  generated-source policy, và review-size guard;
- tách sâu type checking, borrow analysis, MIR optimization, rồi mới tới parser,
  lowering, codegen, CLI và diagnostics;
- cập nhật assembler/pre-expander/sync tools để đọc module graph thay vì phụ
  thuộc đường dẫn cũ;
- giữ và mở rộng registry, semantic, memory, optimization, regression, và
  self-host fixed-point gates.

### Out of Scope

- copy `.git/**`, `docs/_legacy/**`, `frozen/**`, build output, scratch,
  caches, compiled binaries hoặc editor-local state sang `Vir-3.0`;
- overwrite/merge vào một destination `Vir-3.0` đã tồn tại hoặc không rỗng;
- copy cache, diagnostic state, local package, untracked executable hoặc editor
  state không thuộc source snapshot;
- thay đổi Vir syntax, language semantics, module grammar, hoặc public stdlib API;
- triển khai PRE/loop transform/register allocation còn thiếu chỉ vì file đã
  được tách;
- đổi error code, diagnostic meaning, optimization order, hoặc `-O` policy nếu
  không có issue/plan riêng;
- đưa package installation, network access, hash/signature, hoặc Viron lifecycle
  vào compiler resolver;
- chỉnh sửa language/stdlib specifications;
- trộn thêm thay đổi mới phát sinh ở source checkout sau snapshot mà không tạo
  snapshot/revision mới;
- copy `.vir/**`, `node_modules/**`, `out/**`, `*.vsix`, `bin/vir-lsp`,
  `dist/vir-lsp` hoặc nested `.git/**` như canonical source;
- đổi tên hàng loạt public/ABI symbols chỉ để đạt camelCase.

## 4. Current Architecture

Các claim dưới đây được audit trực tiếp ở baseline ngày 2026-10-02:

- `stdlib/vir/compiler/` là source root của compiler, chứa 105 `.vri` paths;
- 93 regular non-bundle source files có khoảng 84,905 dòng;
- generated `stdlib/vir/compiler/virc.vri` có 79,002 dòng;
- `stdlib/stdlib.vri` có 101 mapping bắt đầu bằng `compiler.` và thêm các alias
  ngắn trỏ tới compiler preludes;
- không có project `module.list` trong tree;
- resolver trong `main.vri` đã có hai registry layer: stdlib registry và nearest
  project `module.list`, với directory alias cho dotted tail;
- `semantic.vri` đã điều phối mười semantic passes;
- `mir_opt_pipeline.vri` đã điều phối pass order, optimization-level guards và
  MIR memory verifier;
- transformation bodies của nhiều pass vẫn tập trung trong `mir_opt.vri`;
- `sem_pass6_typecheck.vri`, `sem_pass8_borrow.vri`, `parser.vri`,
  `ast_to_mir.vri`, `lir_codegen.vri`, và `main.vri` đều chứa nhiều domain;
- `tools/sync_virc.py`, `tools/assemble_virc.py`, và `tools/preexpand_virc.py`
  hard-code source root hoặc patch generated bundle theo đường dẫn/marker;
- `mir_opt_advanced.vri` chứa các implementation trùng tên với một phần
  `mir_opt.vri`, nhưng không xuất hiện như module active trong generated marker
  sequence được audit; trạng thái này phải được phân loại trước khi di chuyển.
- `/Users/gengyang/Vir-3.0` chưa tồn tại tại thời điểm audit;
- snapshot mang theo test suite, paper registry và source/tool changes hiện có;
  `docs/_legacy/**` vẫn bị loại ở bước seed `Vir-3.0`;
- root `run_tests.sh` gọi trực tiếp `tools/gap_contract_runner.py`; runner
  migration vì vậy phải copy dependency closure, không chỉ file có prefix `run`;
- snapshot chứa `.agents/skills/vir-paper-management/**` cùng paper tool và
  registry đang dùng.
- snapshot có tracked `tools/vscode-vir/`, nhưng gồm cả TypeScript canonical
  source, generated `out/**` và packaged `*.vsix`; hai nhóm sau không phải
  source-of-truth để seed.
- snapshot parent không chứa standalone `vir-lsp/` trong parent Git tree.
  Native server là một
  clean nested repository riêng tại `/Users/gengyang/Vir/vir-lsp`, pin ở commit
  `55e964a3664fb703731c59aa85f3f546e44b1b03`, với 6 tracked source/doc files.
- compiler-backed editor integration, LSP runner/tests/build script và
  `tools/vscode-vir` được lấy trực tiếp từ snapshot source hiện tại.

## 5. Proposed Architecture

### 5.1 Target source tree

Repository target root là `/Users/gengyang/Vir-3.0`. Governance/test seed ở
root mới có shape:

```text
Vir-3.0/
  docs/                         # excludes docs/_legacy/**
  papers/
  .agents/
    skills/
      vir-paper-management/
  tests/
  tools/
    vir-lsp/                    # canonical native server source, no nested .git
    vscode-vir/                 # canonical extension source/assets/config
    paper.py
  paper
  run_tests.sh
```

Compiler target layout dưới root đó sau migration:

```text
compiler/
  module.list
  README.md
  src/
    main.vri
    bootstrap/
      prelude/
      platform/
    cli/
      environment.vri
      storage.vri
      ui.vri
    diagnostic/
      context.vri
      render.vri
      store.vri
      codes.vri
    frontend/
      lexer/
      parser/
      source/
    semantic/
      pipeline.vri
      passModules.vri
      passSymbols.vri
      passNames.vri
      passTypes.vri
      passInfer.vri
      passTypecheck.vri
      passFlow.vri
      passBorrow.vri
      passConst.vri
      passDiagnostics.vri
      typecheck/
      borrow/
    ir/
      hir/
      mir/
        passOptimize.vri
        analysis/
        optimize/
      lir/
      mc/
    lower/
      ast/
      hir/
      lir/
      mc/
    backend/
      common/
      arm64/
      x86/
      riscv/
      wasm/
    target/
    tool/
    ide/
  generated/
    virc.vri
  tests/
    architecture/
    module/
    semantic/
    optimize/
    selfhost/
```

Đây là target ownership map, không phải lệnh tạo toàn bộ thư mục rỗng ngay lập
tức. Mỗi directory chỉ được tạo khi phase tương ứng chuyển ít nhất một canonical
module và có test/owner rõ ràng.

### 5.2 Compiler project registry

`compiler/module.list` là registry của project compiler, không phải registry
stdlib và không phải pass-order manifest. Target tối thiểu:

```text
root = .
virc = src
```

Ví dụ canonical module identities:

```vir
include virc.semantic.passTypecheck
import checkTensor from virc.semantic.typecheck.tensor
include virc.ir.mir.passOptimize
import runConstantFold from virc.ir.mir.optimize.scalar.constantFold
```

Tên `virc` được chọn cho project namespace để không shadow namespace
`compiler.*` đang được stdlib registry giữ trong giai đoạn chuyển tiếp. Trước
khi chấp nhận spelling trên, Phase 0 phải có resolver fixture chứng minh mixed
case module segment được parser/resolver hỗ trợ. Nếu không, file/module segment
phải dùng lowercase đơn từ và directory hierarchy để tránh snake_case; không
được tự nới grammar.

`module.list` chỉ chịu trách nhiệm mapping name → physical root/file. Nó không
được chứa pass order, optimization level, feature flag, package metadata, hoặc
generated-bundle order.

### 5.3 Standard-library boundary

Final state:

- `stdlib/stdlib.vri` chỉ map modules thuộc stdlib;
- không còn `compiler.*`, `compiler.virc`, hoặc compiler-only prelude alias;
- compiler được phép import public stdlib/runtime modules qua stdlib registry;
- compiler-only adapters/preludes thuộc `compiler/src/bootstrap/`;
- không dùng symlink trong compiler tree để giả ownership;
- một physical stdlib module vẫn có đúng một canonical stdlib Module ID;
- compiler tree không copy implementation stdlib để tránh hai source of truth.

### 5.4 Pass architecture

Có ba cấp điều phối tách biệt:

1. `semantic/pipeline.vri` hoặc IR pipeline gọi các pass theo phase tổng thể;
2. file bắt đầu bằng `pass` đăng ký rule/transform, metadata, guard, verifier,
   và thứ tự chạy trong chính pass đó;
3. leaf module thực hiện đúng một rule family hoặc một optimization.

Pass entry file được phép chứa:

- imports của leaf modules;
- stable pass ID/name và stage metadata;
- dependency/precondition declaration;
- ordered dispatch;
- `-O`/target/capability guard;
- pre/post verifier calls;
- trace, timing và changed/skipped aggregation;
- một exported run entry point.

Pass entry file bị cấm chứa:

- AST/HIR/MIR/LIR rewrite body;
- tensor/generic/entity-specific type rule;
- borrow-state transfer implementation;
- CFG/dataflow algorithm body;
- target instruction selection pattern;
- helper chỉ phục vụ một leaf transform;
- compatibility fallback khiến pass giả có thể báo `changed`.

Một architecture checker phải kiểm tra policy này bằng allowlist declaration
shape/import/run calls; LOC threshold chỉ là secondary signal, không thay thế
structural check.

### 5.5 Type-check decomposition

`semantic/passTypecheck.vri` chỉ tạo/nhận context, đăng ký nhóm rule và chạy
chúng theo thứ tự đã khóa. Logic mục tiêu nằm dưới:

```text
semantic/typecheck/
  context.vri
  index.vri
  inference.vri
  compatibility.vri
  calls.vri
  methods.vri
  assignment.vri
  operators.vri
  tensor.vri
  generics.vri
  entities.vri
  packed.vri
  enums.vri
  patterns.vri
  containers.vri
  ffi.vri
  diagnostics.vri
```

Yêu cầu:

- tensor rules không nằm chung với generic substitution hoặc FFI rules;
- compatibility là shared service có typed input rõ ràng, không là chuỗi
  fallback theo tên;
- callable signature parsing và method/UFCS resolution tách khỏi tree walk;
- diagnostic construction tách khỏi rule decision nhưng giữ nguyên error code,
  primary/secondary location và source origin;
- context sở hữu caches/index/state của pass; không thêm global mutable state;
- leaf module chỉ export entry points cần cho orchestrator hoặc shared service;
- chuyển từng nhóm rule một, giữ wrapper gọi legacy cho phần chưa chuyển;
- mỗi batch có positive, negative, and anti-fallback fixture trước khi xóa body
  legacy tương ứng.

### 5.6 Borrow-analysis decomposition

`semantic/passBorrow.vri` chỉ điều phối các transfer/check modules:

```text
semantic/borrow/
  context.vri
  state.vri
  paths.vri
  binding.vri
  moves.vri
  loans.vri
  scopes.vri
  branches.vri
  loops.vri
  arena.vri
  async.vri
  diagnostics.vri
```

Policy bắt buộc:

- binding identity, projection path và scope identity không được suy từ tên
  chuỗi đơn thuần;
- branch/loop joins dùng một shared state representation;
- Arena escape/promotion contract không được trộn với ordinary move tracking;
- `await`, `break`, `skip`, `out`, `throw`, `revert`, và `ensure` edges phải giữ
  cleanup/lifetime semantics;
- không merge phase nếu O0–O3 hoặc direct executable/object path chưa chứng minh
  tương đương;
- một leaf module không được reset/drop resource thuộc module khác.

### 5.7 MIR optimization decomposition

`ir/mir/passOptimize.vri` là nơi duy nhất sở hữu MIR transform order, stage,
minimum `-O`, enable/disable policy, pre/post memory verification và trace.

Mỗi optimization có một implementation file riêng. Target grouping:

```text
ir/mir/optimize/
  scalar/
    constantFold.vri
    constantPropagate.vri
    copyPropagate.vri
    algebra.vri
    strengthReduce.vri
    cse.vri
    dce.vri
    sccp.vri
  control/
    jumpThread.vri
    cfgSimplify.vri
    branchFold.vri
    phiSimplify.vri
    deadPhi.vri
  loop/
    licm.vri
    ivsr.vri
    unroll.vri
    collapse.vri
    tiling.vri
    idiom.vri
    bounds.vri
  memory/
    escapeArena.vri
    inlineArena.vri
    redundantLoadStore.vri
    arcTrial.vri
  aggregate/
    sroa.vri
  interproc/
    inline.vri
    ipoCascade.vri
    dae.vri
    devirtualize.vri
  value/
    gvn.vri
    pre.vri
  vector/
    slp.vri
```

Một file không được chứa hai transform chỉ vì chúng chạy cạnh nhau. Shared
dominance, CFG, SSA, use-def, alias, loop, and memory-effect analysis phải ở
`ir/mir/analysis/` với immutable/read-only query API khi có thể.

Transform modules không import lẫn nhau. Orchestrator gọi chúng theo thứ tự và
thực hiện cleanup rounds rõ ràng. Disabled hoặc placeholder transform vẫn có
module riêng nhưng phải trả capability/skipped state trung thực; không được
claim production behavior hoặc `changed` nếu không biến đổi IR.

### 5.8 Remaining large-file decomposition

Chỉ bắt đầu sau khi typecheck, borrow, và MIR optimizer đạt fixed-point:

- parser: declarations, statements, expressions, types, patterns, modules,
  recovery;
- AST→MIR: builder/model, expressions, statements, calls, aggregates, control,
  Arena cleanup, generics/monomorphization;
- LIR/codegen: ABI, instruction families, calls, memory, branches, target hooks;
- CLI/main: option parsing, session, registry loading, compile command,
  rendering, storage;
- diagnostics: catalog, cause/action text, JSON, modern/classic renderer;
- IDE facts: capture, storage, semantic snapshot, serialization.

Không được tách theo số dòng ngẫu nhiên. Boundary phải theo owned data,
algorithm, mutation authority và test surface.

### 5.9 Vir-3.0 seed and copy policy

Seed operation MUST copy, không move, từ snapshot preparation worktree sang
`/Users/gengyang/Vir-3.0`. Source tree tiếp tục tồn tại nguyên vẹn.

Payload bắt buộc:

- `docs/**`, với explicit exclude `docs/_legacy/**` và mọi descendant;
- toàn bộ `papers/**`, root `paper`, `tools/paper.py`, paper schemas/templates
  và file dependency mà paper tool import;
- `.agents/skills/vir-paper-management/**` đã nằm trong snapshot source;
- toàn bộ `tests/**`, giữ fixture names, symlinks và executable modes;
- root `run_tests.sh`;
- các active runner/checker/audit entry points dưới `tools/` và transitive
  helper files được `run_tests.sh` hoặc test runners gọi, ít nhất gồm
  `tools/gap_contract_runner.py` đã được audit trực tiếp.

Payload bị cấm trong seed:

- `.git/**`, `docs/_legacy/**`, `frozen/**`;
- `scratch/**`, `build/**`, `dist/**`, caches, logs, coverage, temporary files;
- prebuilt compiler binaries và benchmark executables;
- file mới phát sinh ở checkout `/Users/gengyang/Vir` sau snapshot;
- absolute symlinks trỏ ngược về source tree.

Trước copy, implementation MUST:

1. fail closed nếu `/Users/gengyang/Vir-3.0` đã tồn tại và không rỗng;
2. tạo dry-run inventory gồm relative path, source class, file type, mode,
   symlink target, byte size và SHA-256 cho regular files;
3. ghi rõ source provenance: snapshot commit/tree, parent commit,
   preparation-worktree paper diff và nested `vir-lsp` commit;
4. resolve runner dependency closure; missing dependency là hard error;
5. kiểm tra exclude set để không có legacy/build/cache payload.

Sau copy, implementation MUST tạo machine-readable migration manifest trong
`Vir-3.0` và so sánh source/destination hashes. Manifest không được coi là
package lock hoặc đưa hash verification vào compiler resolver.

Source `.git` MUST NOT được copy. Sau khi seed validation xanh, implementation
MAY khởi tạo Git repository local mới trong `Vir-3.0` để các phase sau có commit
boundary; repository mới không có remote và không được push nếu chưa có user
authorization riêng. Initial import commit phải ghi snapshot commit/tree và seed
manifest, nhờ đó `git mv` ở các compiler phase sau không phụ thuộc Git metadata
của source repository.

Source snapshot là điểm cắt duy nhất của parent repository. Mọi thay đổi source
phát sinh sau `fd0064ea` chỉ được nhập bằng một snapshot revision mới có manifest;
không đọc lại working tree sống trong lúc migration.

### 5.10 LSP and editor-tooling migration policy

Hai package đích tách biệt:

```text
tools/
  vir-lsp/
    src/
    docs/
    README.md
  vscode-vir/
    src/
    test/
    assets/
    syntaxes/
    snippets/
    themes/
```

`tools/vir-lsp/` được tạo từ đúng 6 tracked files của repository
`/Users/gengyang/Vir/vir-lsp` tại commit
`55e964a3664fb703731c59aa85f3f546e44b1b03`. Nested `.git`, `.vir` diagnostics,
binary và mọi untracked file MUST NOT được copy. Source path đổi từ
`vir-lsp/src/main.vri` sang `tools/vir-lsp/src/main.vri`; build/test tooling phải
đổi đường dẫn trong một mechanical batch riêng.

`tools/vscode-vir/`, LSP runner/tests và `tools/build_vir_lsp.py` lấy từ snapshot
`fd0064ea516c132b57cd9dec8acf827ed4361555`.
`out/**`, source maps, `*.vsix`, `node_modules/**` và package cache bị loại khỏi
copy manifest; chúng phải được tái tạo từ `src/**`, `package-lock.json` và
documented package scripts sau migration.

Ownership policy:

- compiler là source of truth duy nhất cho parse, resolve, infer, typecheck,
  borrow, diagnostics và semantic identity;
- `vir-lsp` quản lý protocol, document/session lifecycle, cancellation,
  UTF-16/range mapping và chuyển compiler facts thành LSP response;
- `vscode-vir` quản lý extension activation, client lifecycle, commands,
  presentation, grammar/theme/snippet và user configuration;
- server và extension MUST NOT copy/port compiler semantic rules hoặc tự suy
  đoán fallback khác compiler để báo kết quả như authoritative;
- compiler ↔ LSP facts và LSP ↔ extension snapshot payload MUST có schema/version
  explicit, compatibility test và fail-closed behavior cho version không hỗ trợ;
- không hard-code absolute source checkout path. Executable/config discovery
  phải hoạt động từ repository root, subdirectory và unrelated CWD;
- LSP/editor source migration không được đổi protocol behavior, feature set,
  diagnostics hoặc default configuration; thay đổi chức năng cần paper VLSP
  riêng và evidence độc lập;
- server build phải tiêu thụ canonical compiler module graph sau khi compiler
  move; generated amalgamation chỉ là artifact, không thành source thứ hai.

## 6. Module Policy

Các từ MUST/MUST NOT dưới đây là policy của implementation plan.

### 6.1 Identity and registry

- Mỗi physical source unit MUST có đúng một canonical Module ID.
- `include` và `import` MUST dùng cùng resolver, dedup table, canonicalization và
  cycle detection.
- Compiler-internal names MUST resolve qua `compiler/module.list`, không qua
  `stdlib/stdlib.vri`.
- Project names MUST NOT silently shadow stdlib names hoặc prefix namespaces.
- Missing registered target MUST fail tại registry entry; không fallback search.
- Resolution MUST độc lập CWD và include order.
- `module.list` changes MUST đi cùng mapping audit: old spelling → old target →
  new name → canonical ID → new path.
- Một directory alias SHOULD bao phủ cả domain thay vì liệt kê hàng trăm file.

### 6.2 Dependency direction

Dependency chỉ đi theo hướng:

```text
entry/cli
  → pipeline/orchestrator
    → pass entry
      → rule/transform
        → analysis/model/support
          → public stdlib/runtime
```

- Leaf MUST NOT import orchestrator hoặc CLI.
- Analysis/model MUST NOT import a concrete transform.
- Sibling transforms MUST NOT import nhau.
- Target-neutral MIR MUST NOT import a target backend.
- Backend MAY consume target-neutral IR and target descriptors.
- IDE facts MAY observe compiler-owned facts but MUST NOT decide language
  semantics.
- Cycles MUST be errors; `lazy include` không được dùng để che architecture
  cycle có function calls.

### 6.3 Exports and state

- Default là private; chỉ export API cần qua domain boundary.
- Leaf transform SHOULD export một run/check entry và tối thiểu supporting types.
- New mutable globals MUST NOT được thêm để né context plumbing.
- Pass-owned mutable state MUST nằm trong explicit context/entity với lifecycle
  khớp một compilation hoặc một pass run.
- Shared cache MUST có owner, invalidation point và determinism test.
- Error codes, serialized keys, ABI/FFI names và source-origin fields MUST giữ ổn
  định trong mechanical phases.

### 6.4 Naming

- Directory dùng từ domain ngắn, rõ nghĩa và lowercase: `semantic`, `typecheck`,
  `borrow`, `optimize`, `analysis`, `backend`.
- File một khái niệm dùng một từ: `tensor.vri`, `calls.vri`, `arena.vri`.
- File nhiều từ dùng lower camel case khi resolver test xác nhận:
  `constantFold.vri`, `passTypecheck.vri`, `sourceManager.vri`.
- Hạn chế snake_case trong source path và new internal API.
- Snake_case chỉ giữ cho legacy/public compatibility, ABI/FFI, target-defined
  symbol, generated marker, serialized key, hoặc tên ngoài quyền kiểm soát.
- Không encode pass number trong final filename. Thứ tự nằm trong orchestrator,
  không nằm trong `pass6`, `pass8`, hoặc tên file.
- Tên phải nói domain action; tránh `utils.vri`, `common2.vri`, `advanced.vri`,
  `misc.vri`, `new.vri`, và `final.vri`.

### 6.5 Size and review budget

- Pass entry target ≤ 300 logical lines.
- Leaf target 150–600 logical lines.
- File > 800 logical lines MUST có rationale về cohesive algorithm và follow-up
  review; file > 1,200 logical lines MUST NOT được coi là hoàn tất migration.
- Generated files không chịu LOC limit nhưng MUST bị loại khỏi source metrics.
- LOC không được dùng để chẻ một state machine/algorithm thành fragments có
  hidden shared state; cohesion và dependency policy có ưu tiên cao hơn.

### 6.6 Include/import use

- Prefer `import symbol from module` khi chỉ cần exported symbols.
- Chỉ dùng `include module` khi cần physical load/namespace access theo contract.
- Không thêm redundant `include` chỉ vì có `import`.
- New code MUST dùng canonical `virc.*` identity; relative path chỉ được dùng
  trong compatibility/negative resolver fixtures.
- Duplicate basename ở khác directory vẫn là modules riêng; canonical name phải
  disambiguate bằng hierarchy, không bằng search order.

### 6.7 Generated source

- Canonical source luôn ở `compiler/src/`.
- Generated bundle luôn ở `compiler/generated/`.
- Bundle MUST được tạo từ one entry module + resolved dependency graph + stable
  topological order.
- Assembler MUST đọc `module.list` và dùng cùng canonicalization rules với
  compiler resolver; không giữ hard-coded prefix search.
- Generated file MUST mang source markers/provenance đủ cho diagnostics.
- CI/check MUST fail nếu bundle drift hoặc bị edit trực tiếp.
- `sync` chỉ regenerate; không patch canonical source và không chứa semantic fix
  chỉ tồn tại trong tool.

## 7. Design Decisions

### Decision 1 — Move ownership before deep splitting

**Decision:** Hoàn thiện resolver/tool support rồi chuyển canonical compiler
source ra `compiler/` trước khi tách logic sâu.

**Rationale:** Nếu split dưới path cũ rồi mới move, mọi module phải đổi identity
hai lần và generated tooling phải hỗ trợ hai kiến trúc dài hơn.

**Alternatives considered:** split tại `stdlib/vir/compiler` trước; copy toàn
bộ tree rồi chuyển callers một lần.

**Trade-offs:** cần migration tooling sớm; đổi lại mỗi leaf mới sinh ra đã dùng
final namespace và ownership.

### Decision 2 — Use one directory alias in project registry

**Decision:** `compiler/module.list` map `virc = src` thay vì liệt kê từng file.

**Rationale:** path ngắn, module hierarchy phản ánh source tree và không tăng
registry churn khi thêm transform.

**Alternatives considered:** hàng trăm flat mappings; giữ `compiler.*` trong
stdlib registry; raw relative includes.

**Trade-offs:** resolver directory mapping và prefix-collision tests trở thành
hard gate.

### Decision 3 — Pass files are declarative orchestrators

**Decision:** file bắt đầu bằng `pass` chỉ giữ registration/order/guards/
verification/dispatch; logic nằm ở leaf modules.

**Rationale:** maintainer có thể thấy pipeline order trong một file nhỏ và mở
đúng rule/transform khi sửa lỗi.

**Alternatives considered:** một file mỗi pass như hiện tại; tự động discover
transform theo filesystem.

**Trade-offs:** imports dài hơn và cần architecture checker; đổi lại execution
order explicit, reviewable và deterministic.

### Decision 4 — One optimization per file

**Decision:** mỗi MIR/LIR/backend optimization sở hữu một implementation file;
shared analyses tách riêng.

**Rationale:** cho phép unit test, disable, rollback và ownership độc lập; ngăn
file optimizer trở lại thành “god module”.

**Alternatives considered:** nhóm theo optimization tier hoặc một
`mir_opt.vri` chung.

**Trade-offs:** nhiều modules hơn; module.list directory alias và graph-based
assembler hấp thụ chi phí quản lý tên.

### Decision 5 — Mechanical move and semantic refactor never share a batch

**Decision:** một review batch chỉ được move/rename hoặc extract logic, không làm
cả hai cùng lúc; thuật toán mới cần issue/plan riêng.

**Rationale:** diff có thể review và rollback; failures có provenance rõ.

**Alternatives considered:** big-bang rewrite.

**Trade-offs:** nhiều phase và temporary adapters; giảm blast radius và tránh
khó xác định regression.

### Decision 6 — Preserve memory semantics as end-to-end invariant

**Decision:** borrow and memory-sensitive optimizer extraction không được merge
nếu chỉ parser/seed build xanh; phải có memory fixtures, IR verifier và O0–O3
equivalence.

**Rationale:** file movement có thể đổi initialization/order/state lifetime dù
algorithm text không đổi.

**Alternatives considered:** coi refactor là behavior-neutral và chỉ compile.

**Trade-offs:** verification lâu hơn nhưng tránh use-after-move, Arena reset,
cleanup hoặc optimizer barrier regression.

### Decision 7 — Seed a clean sibling tree by manifest-driven copy

**Decision:** Tạo `/Users/gengyang/Vir-3.0` bằng copy allowlist từ snapshot
source 4.0.0 trước khi sửa resolver hoặc compiler source. Không đọc lại live
checkout sau điểm cắt snapshot.

**Rationale:** tree mới phải bắt đầu từ baseline có thể truy nguyên nhưng vẫn có
đủ docs, VPS governance, tests và runners để mọi phase sau tự kiểm chứng.

**Alternatives considered:** làm trực tiếp trong old repository; copy toàn bộ
working tree; clone cả Git history; chỉ copy compiler rồi bổ sung tests sau.

**Trade-offs:** snapshot có thể chứa lỗi đang tồn tại; đổi lại destination phản
ánh đúng source user chọn và không mang thêm drift sau thời điểm chụp.

### Decision 8 — Import editor tooling by pinned path, not working tree

**Decision:** Native server được nhập từ nested repository commit `55e964a`; VS
Code extension và LSP integration tests dùng nội dung đã pin trong snapshot
`fd0064ea`. Generated/package artifacts không trở thành canonical source.

**Rationale:** native server là nested repository có provenance riêng, trong khi
editor client/integration đã thuộc source snapshot. Hai source root cần manifest
riêng nhưng không cần quay lại commit 3.8.5.

**Alternatives considered:** bỏ LSP khỏi Vir-3.0; copy toàn working tree; giữ
nested Git repository; mang theo binary, generated JavaScript và VSIX.

**Trade-offs:** seed manifest có thêm hai provenance roots và build phải tái tạo
artifacts; đổi lại tree đích không chứa Git lồng, cache hoặc source-of-truth kép.

## 8. Implementation Plan

Các phase MUST chạy tuần tự. Snapshot ban đầu không bắt buộc xanh. Phase N+1
chỉ bắt đầu khi lỗi mới do Phase N đã được cô lập/khắc phục và các lỗi có sẵn
được ghi baseline rõ ràng; không được dùng “source vốn đã lỗi” để bỏ qua
regression mới. Mỗi phase tạo một reviewable commit hoặc một chuỗi commit nhỏ có
cùng rollback boundary.

### Phase 0 — Pin baseline and measure invariants

- files/modules: không đổi compiler implementation;
- changes:
  - record exact source inventory, module mappings, symlinks, bundle markers,
    command lines, test manifests và hashes;
  - classify every `mir_opt_advanced.vri` duplicate as active, stale, generated,
    hoặc compatibility before any move;
  - add/identify executable architecture checks and baseline test commands;
  - verify camelCase module segments; if unsupported, record lowercase naming
    fallback without spec change;
- dependencies: snapshot `fd0064ea` and nested LSP commit `55e964a` only;
- expected result: reproducible before-state, known-failure ledger và zero
  unknown canonical source;
- gate: record current sync/check, registry, representative strict/type/memory/
  optimizer/CLI and self-host outcomes; failures may remain but must have stable
  reproduction before source movement.

### Phase 1 — Seed sibling repository Vir-3.0

- destination: `/Users/gengyang/Vir-3.0`;
- files/modules:
  - `docs/**` excluding `docs/_legacy/**`;
  - `papers/**`, `paper`, `tools/paper.py`, paper dependencies;
  - `.agents/skills/vir-paper-management/**` from the snapshot;
  - `tests/**`, `run_tests.sh`, audited runner/checker/audit scripts and their
    dependency closure;
- changes:
  - preflight destination and stop if it exists/non-empty;
  - generate allowlist/exclude inventory and source checksum manifest;
  - copy while preserving relative paths, executable bits and safe symlinks;
  - generate destination manifest and compare hashes/modes/path counts;
  - assert no `.git`, `docs/_legacy`, frozen, binary, cache, scratch or absolute
    source-backlink entered the destination;
  - rewrite no documentation or test content during this copy-only phase;
  - after verification only, initialize a fresh local Git repository without a
    remote and record the manifest-backed import boundary;
- dependencies: Phase 0 snapshot evidence;
- expected result: clean governance/test seed exists at sibling `Vir-3.0`;
- gate:
  - source/destination allowlisted hashes and modes match;
  - `docs/_legacy` count in destination is zero;
  - every allowlisted snapshot test file is present;
  - paper tool and skill paths are internally complete;
  - snapshot papers plus the new ISSUE/PLAN are present and registry-consistent;
  - runner dependency audit reports zero missing files;
  - no compiler behavior claim is made yet because compiler payload has not been
    migrated.

### Phase 2 — Migrate vir-lsp and vscode-vir source packages

- files/modules:
  - tracked `vir-lsp` repository files at `55e964a` → `tools/vir-lsp/**`;
  - canonical `tools/vscode-vir/**` files from snapshot `fd0064ea`, excluding
    generated and packaged output;
  - snapshot `tools/build_vir_lsp.py`, `tests/run_lsp_tests.py` and
    `tests/test_lsp_*.py`;
- changes:
  - create separate manifest sections for nested-repo and snapshot inputs;
  - mechanically update `vir-lsp/src/main.vri` references to
    `tools/vir-lsp/src/main.vri`;
  - make build/test paths destination-relative and CWD-independent;
  - install no package and fetch no network dependency during copy;
  - compile extension `out/**`, package VSIX and native server only as derived
    verification artifacts after canonical source is present;
  - keep compiler semantics in compiler modules; remove no fallback or feature
    in this migration-only phase;
- dependencies: verified Phase 1 destination, source snapshot and nested LSP
  commit;
- expected result: both tooling packages are canonical source members of
  Vir-3.0 without nested Git metadata or prebuilt/generated payload;
- gate:
  - source manifests match exact pinned commits and forbidden artifact count is
    zero;
  - extension `npm run compile` and `npm test` pass using the locked package
    manifest in an approved dependency-ready environment;
  - `python3 tools/build_vir_lsp.py` and `python3 tests/run_lsp_tests.py` pass;
  - compiler-backed diagnostic/symbol/type facts and client snapshot contract
    match their pinned fixtures;
  - one stdio initialize/open/change/query/cancel/shutdown smoke passes from an
    unrelated CWD.

### Phase 3 — Harden registry and graph tooling

- files/modules: active resolver, registry tests, pre-expander/assembler/sync;
- changes:
  - make tooling parse project `module.list` and stdlib registry with the same
    identity rules;
  - add directory alias, prefix collision, missing target, duplicate, cycle,
    same-realpath, same-basename, include/import convergence and CWD fixtures;
  - add deterministic graph order and graph dump for audit;
  - remove fallback-by-search-order from new compiler graph path;
- dependencies: Phase 2 tooling migration, Phase 1 seed and Phase 0 evidence;
- expected result: tools can resolve a fixture rooted by `module.list` without
  using `stdlib/vir/compiler` prefixes;
- gate: resolver matrix passes from repo root, subdirectory and unrelated CWD.

### Phase 4 — Establish compiler tree and migrate source mechanically

- files/modules: `compiler/module.list`, `compiler/src/**`, compiler callers and
  build/test paths;
- changes:
  - create only required target directories;
  - `git mv` one coherent family per batch: bootstrap/model → frontend/semantic
    → IR/lowering → backend/CLI/tooling;
  - update imports to canonical `virc.*` identities;
  - use temporary compatibility adapters only when an in-repo caller cannot move
    in the same batch; adapters contain no logic and have deletion issue/check;
  - do not split functions or rename public symbols in this phase;
- dependencies: Phase 3 graph tooling;
- expected result: all canonical compiler source is owned by `compiler/src`;
- gate after every family: no duplicate physical Module ID, sync/check green,
  source-origin paths correct, same test subset as baseline.

### Phase 5 — Remove compiler ownership from stdlib

- files/modules: `stdlib/stdlib.vri`, stdlib checker/tests, old compiler tree;
- changes:
  - remove `compiler.*` implementation mappings and compiler-only short aliases;
  - replace compiler symlink aliases with direct imports of canonical stdlib
    modules or compiler-owned adapters;
  - remove empty legacy compiler directories only after caller audit finds zero
    active references;
  - enforce “no compiler implementation path under stdlib” in CI;
- dependencies: all canonical files moved in Phase 4;
- expected result: physical and registry ownership match compiler/stdlib boundary;
- gate: stdlib registry parity, public legacy compatibility decision, full
  resolver matrix and compiler bootstrap pass.

### Phase 6 — Introduce pass contracts without moving rule logic

- files/modules: semantic and MIR pass entry modules, context shells,
  architecture checker;
- changes:
  - rename/create final orchestrator names such as `passTypecheck.vri`,
    `passBorrow.vri`, `passOptimize.vri`;
  - preserve existing entry symbols through thin adapters;
  - define explicit context ownership and leaf run result shape;
  - lock current pass order, optimization levels, disabled capabilities,
    verifier points and diagnostic codes in golden/structural tests;
  - architecture checker rejects transform bodies in `pass*` files;
- dependencies: final source paths from Phase 5;
- expected result: behavior unchanged; stable extraction seams exist;
- gate: byte/IR/diagnostic comparison for representative fixtures and self-host
  fixed-point.

### Phase 7 — Split type checking one rule family at a time

- order: context/index → compatibility → inference → calls/methods → assignment
  → operators → tensor → generics → entities/packed → enums/patterns →
  containers → FFI → diagnostics;
- changes per family:
  - add leaf module and direct fixtures first;
  - redirect only that rule family from orchestrator/legacy walker;
  - compare diagnostics including source locations;
  - remove migrated legacy body after zero-call/static check;
  - run full type contract manifest before next family;
- dependencies: Phase 6 contract;
- expected result: `passTypecheck.vri` is ≤300 logical lines and contains no
  rule implementation; no typecheck leaf exceeds completion threshold;
- gate: all type-safety, generic, tensor, FFI, strict-v2 and anti-fallback tests
  pass with identical expected diagnostics where behavior was not separately
  authorized to change.

### Phase 8 — Split borrow analysis and lifetime state

- order: context/state → path/binding identity → moves → loans → scopes →
  branch joins → loop joins → Arena → async → diagnostics;
- changes: same extract/redirect/delete cycle as Phase 7, with explicit state
  snapshots and no new mutable globals;
- dependencies: typecheck context/types stable enough for borrow inputs;
- expected result: `passBorrow.vri` contains only ordered checks and dataflow
  dispatch;
- gate: use-after-move, rebind, shared/mutable borrow, alias/projection,
  branch/loop, scope escape, Arena promotion/reset, async/await, and cleanup edge
  fixtures pass; O0–O3 observable memory behavior matches.

### Phase 9 — Split MIR optimizations one transform at a time

- order: shared analysis/query APIs first; then transforms in the exact current
  pipeline order;
- changes per transform:
  - move one transformation and private helpers into one leaf file;
  - replace private cross-transform helpers with explicit analysis APIs;
  - add direct production-pass fixture, mutation/no-op oracle and verifier gate;
  - preserve pass ID, minimum `-O`, stage, ordering and disabled status;
  - delete old implementation only after symbol/reference audit;
- dependencies: pass contract and memory verifier stable;
- expected result: `passOptimize.vri` is the only order authority and each
  optimization can be independently disabled/reverted;
- gate: MIR verifier after each mutation, optimization trace equality, O0–O3
  regression, no fake-changed result, and self-host fixed-point.

### Phase 10 — Split remaining large compiler domains

- order: parser → AST-to-MIR lowering → LIR/codegen → CLI/main → diagnostics →
  IDE/tool JSON;
- changes: use the same orchestrator/context/leaf policy; never mix algorithm
  changes with extraction;
- dependencies: previous semantic and optimizer modules stable;
- expected result: no non-generated canonical source remains above 1,200
  logical lines without an approved follow-up issue and rationale;
- gate: domain-specific suites plus full compiler regression after each domain.

### Phase 11 — Finalize graph-derived bundle and delete transition paths

- files/modules: `compiler/generated/virc.vri`, generator/checker, legacy
  adapters and old sync scripts;
- changes:
  - generate from `virc.main` and resolved graph in stable order;
  - keep complete source markers;
  - reject direct generated edits and duplicate source sections;
  - delete path-specific patch logic, temporary wrappers and old registry names;
  - document one canonical regenerate/check workflow;
- dependencies: final module graph;
- expected result: canonical modules are the sole source of truth;
- gate: clean regeneration twice yields identical bytes; stage 2 equals stage 3;
  all registry, stdlib smoke, strict, type, memory, optimizer, CLI and
  source-origin suites pass.

### Phase 12 — Verification report and lifecycle update

- create VIRC REPORT linked to `VIRC-ISS-0006` and this plan;
- map evidence to every acceptance and exit criterion;
- record deviations, retained compatibility names, size exceptions and follow-up
  issues without rewriting this plan;
- move PLAN/ISSUE lifecycle only when VPS gates allow.

## 9. Compatibility

- Source compatibility: user Vir programs and public stdlib module names remain
  unchanged. Internal `compiler.*` names are audited before removal; any proven
  external contract requires an explicit compatibility decision.
- ABI: no ABI/FFI name change is authorized by mechanical phases.
- Parser: no grammar change; only module source organization changes.
- Serialized formats: diagnostic JSON, tool JSON, cache keys and source markers
  remain stable unless separately versioned.
- LSP/editor: imported source is pinned outside the compiler baseline. Protocol,
  compiler-fact schema, extension snapshot schema, configuration keys and
  observable feature behavior remain unchanged during copy/path migration.
- Optimizer: pass ID, stage, order, enablement and minimum `-O` remain fixed.
- Diagnostics: error codes, message meaning, primary/secondary location and
  source origin remain fixed.
- Memory: move/borrow/Arena/cleanup semantics must match across O0–O3 and output
  modes.

## 10. Migration

Migration is incremental and mapping-driven:

1. Preflight `/Users/gengyang/Vir-3.0`; do not overwrite or merge an existing
   non-empty directory.
2. Build copy allowlist, exclude set, runner dependency closure, modes and
   checksums from snapshot preparation worktree plus native-LSP source.
3. Copy docs without `docs/_legacy`, VPS papers/tool/skill, complete tests and
   runner dependencies; verify destination manifest before compiler work.
4. Copy six tracked native-LSP files from commit `55e964a` into
   `tools/vir-lsp/`; never copy its nested `.git`, `.vir` or binary output.
5. Copy allowlisted `vscode-vir`, LSP runner/test and build-tool paths from
   snapshot `fd0064ea`; exclude `out`, source maps, VSIX and caches.
6. Update only destination-relative tooling paths, rebuild derived artifacts and
   pass LSP/client contracts before compiler movement.
7. Inventory every old compiler module spelling and physical target.
8. Allocate its final `virc.*` identity and target path inside `Vir-3.0`.
9. Add resolver/tool support and tests before moving compiler source.
10. Move one coherent compiler family inside `Vir-3.0` with `git mv`; update
   callers in the same batch.
11. If a wrapper is unavoidable, mark it compatibility-only and register a
   deletion gate; never duplicate implementation.
12. Regenerate derived artifacts from canonical source.
13. Run the phase gate and compare baseline behavior.
14. Only then migrate the next family.
15. Remove stdlib registrations after all active callers use project identities.
16. Delete legacy compiler paths only after `rg`, registry checker and generated graph
    show zero canonical references.

Copy migration MUST keep a separate seed ledger:

```text
source root | source class | relative path | type | mode | symlink target |
size | SHA-256 | destination path | verification result
```

The migration ledger MUST contain:

```text
old spelling | old target | final name | canonical Module ID | final path |
callers migrated | compatibility expiry | verification evidence
```

## 11. Validation Plan

### Vir-3.0 seed gates

- destination did not pre-exist as a non-empty directory;
- payload matches the allowlist and excludes `.git`, `docs/_legacy`, `frozen`,
  build/dist/scratch/cache/log and prebuilt binary content;
- regular-file SHA-256, byte size and executable modes match source manifest;
- symlinks are relative, resolve inside copied roots and do not point back to
  `/Users/gengyang/Vir` or the preparation worktree;
- `docs/_legacy` has zero destination entries while source legacy remains
  untouched;
- every allowlisted snapshot test file and copied runner dependency exists;
- `paper`, `tools/paper.py`, `papers/**` and
  `.agents/skills/vir-paper-management/**` are present;
- snapshot papers plus `VIRC-ISS-0006` and `VIRC-PLN-0004` are registry-valid;
- paper skill checksum/provenance identifies the snapshot input;
- native server manifest identifies clean commit `55e964a`, contains its six
  tracked files under `tools/vir-lsp/`, and contains no nested Git/diagnostic
  state;
- editor/LSP integration manifest identifies snapshot `fd0064ea` and only
  the approved `tools/vscode-vir`, build script and LSP test paths;
- destination contains no copied `tools/vscode-vir/out`, source map, VSIX,
  `node_modules`, `bin/vir-lsp` or `dist/vir-lsp` source payload;
- `./paper registry --check` and `./paper validate` run from `Vir-3.0` after the
  paper skill is present;
- no test pass claim is made until compiler/runtime dependencies are migrated.

### LSP and editor-tooling gates

- server source builds only from `tools/vir-lsp/src`, canonical compiler modules
  and recorded build inputs;
- extension TypeScript compiles from `src/**`; generated `out/**` matches a clean
  rebuild and is never edited as canonical source;
- `npm test` passes for `tools/vscode-vir` after locked dependencies are made
  available; packaging produces a disposable VSIX outside canonical source;
- `python3 tests/run_lsp_tests.py` passes against the newly built server;
- compiler-fact equivalence, diagnostic mapping, UTF-16 ranges, cancellation,
  document isolation, import/member/type graph and snapshot contracts pass;
- initialization and shutdown work without a hard-coded source checkout or CWD;
- extension client does not silently replace an incompatible server/schema with
  authoritative fallback semantics.

### Module and architecture gates

- automatic stdlib and project registry loading;
- duplicate, missing and malformed entry rejection;
- directory alias and prefix collision rejection;
- repeated/diamond dependency deduplication;
- useful include-cycle chain;
- include/import convergence on one Module ID;
- same realpath through compatible spellings loads once;
- distinct same-basename files remain distinct;
- registered-target failure has no search fallback;
- root/subdirectory/unrelated-CWD equality;
- checker for canonical `virc.*` internal names;
- checker that `pass*` files contain orchestration only;
- checker that stdlib has no compiler implementation registrations;
- checker that generated bundle is not canonical/editable source.

### Semantic gates

- existing type-safety and strict-v2 manifests;
- dedicated tensor/generic/call/method/assignment/entity/enum/FFI fixtures;
- diagnostic code and source-origin golden comparison;
- negative tests that fail if a rule falls through to permissive fallback.

### Memory gates

- use-after-move and rebind;
- shared/mutable borrow conflicts and NLL release;
- owned escape and borrowed escape rejection;
- nested Arena promotion/reset and complete owned graphs;
- `break`, `skip`, `out`, `throw`, `revert`, `ensure`, and `await` edges;
- MIR structural verification and O0–O3 equivalence.

### Optimization gates

- direct invocation of production transform module;
- changed/skipped reason and mutation proof;
- pre/post IR verifier;
- pass-order and optimization-trace golden;
- no-op/identity rejection for claimed production passes;
- target-neutral versus backend-stage separation.

### Generated and self-host gates

- graph generation is deterministic;
- regenerate/check has no drift;
- source markers resolve final canonical paths;
- stage 1 builds stage 2; stage 2 builds stage 3;
- stage 2 and stage 3 satisfy repository fixed-point contract;
- registry and representative stdlib smoke tests run with the new compiler.

Exact commands are established and recorded in Phase 0 from the source snapshot.
Their initial failures become the known-failure ledger, not a reason to abandon
the selected baseline or skip later regression comparison.

## 12. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `Vir-3.0` already exists or contains user data | Low | Critical | Fail closed; never merge, delete or overwrite |
| Live checkout changes after snapshot and silently drift into migration | Medium | High | Use only snapshot `fd0064ea`; require a new recorded snapshot to import later source |
| Snapshot already has failing tests or incomplete work | Certain | High | Record a known-failure ledger; require each phase to introduce no unexplained new failure |
| Native LSP is a nested repository outside baseline | Certain | High | Import only six tracked files from clean commit `55e964a`; exclude nested Git and state |
| VS Code package mixes source with generated/package artifacts | High | Medium | Copy source/config/assets only; rebuild `out` and VSIX from lockfile/scripts |
| LSP/editor copy accidentally includes generated/package state | Medium | High | Copy exact snapshot source allowlist; rebuild `out`, VSIX and server binaries |
| Client/server/compiler schemas drift during module moves | Medium | High | Versioned contracts plus compiler-fact, snapshot and stdio integration gates |
| Runner copied without transitive helper | Medium | High | Static dependency closure plus zero-missing gate |
| Legacy/build/cache payload leaks into clean tree | Medium | Medium | Explicit excludes and forbidden-path scan |
| Module identity changes cause duplicate loads | Medium | High | Migration ledger, canonical realpath tests, one-family batches |
| Project directory alias shadows stdlib namespace | Medium | High | Use `virc` namespace; add prefix-collision rejection |
| Definition/order changes break bootstrap | High | High | Graph-stable ordering, per-batch self-host, source markers |
| Split exposes hidden mutable globals | High | High | Explicit context migration before leaf extraction |
| Mechanical move mixes with semantic changes | Medium | High | Separate commit classes and reject mixed batches |
| Borrow/Arena semantics regress under optimization | Medium | Critical | Memory verifier, O0–O3 and cleanup-edge gates |
| Too many tiny modules create cycles and parsing overhead | Medium | Medium | Cohesion rule, 150–600 line target, dependency DAG checks |
| Compatibility wrappers become permanent | Medium | Medium | Expiry ledger and final zero-wrapper gate |
| Generated bundle becomes second source of truth | Medium | High | Graph-only generation and direct-edit checker |
| Existing external users import compiler stdlib names | Unknown | Medium | Call-site audit and explicit compatibility decision before removal |

## 13. Rollback Strategy

- Seed phase never mutates the source. If seed verification fails, stop before
  compiler work and preserve the partial destination as a named quarantine for
  inspection; do not recursively delete or overwrite it without separate user
  authorization.
- If destination preflight finds an existing/non-empty `Vir-3.0`, perform no
  write and request direction.
- A failed paper-skill or runner dependency check rolls back only the seed
  attempt; it does not source additional files opportunistically.
- Fresh destination Git metadata, if initialized after validation, has no
  remote; rollback must not affect source repository history.
- Every phase and every extracted family has its own rollback boundary.
- Roll back only task-owned canonical modules and regenerate derived output from
  the restored graph; never hand-edit the bundle to “match”.
- Keep baseline fixtures and failing evidence when rollback occurs.
- Do not restore removed stdlib mappings without restoring their exact canonical
  targets and collision tests.
- If a leaf extraction fails, redirect orchestrator to the unchanged legacy
  implementation, remove only the new leaf, and retain the regression fixture.
- If source move fails self-host, restore that family’s old physical path and
  mapping; do not continue with later families.
- Create a follow-up ISSUE for an independent semantic defect discovered during
  refactor instead of fixing it inside the rollback batch.

## 14. Exit Criteria

- [ ] All acceptance criteria of `VIRC-ISS-0006` have direct evidence.
- [ ] `/Users/gengyang/Vir-3.0` is the verified implementation root.
- [ ] Docs were copied without `docs/_legacy`; source legacy was not modified.
- [ ] VPS papers/tool/skill, all baseline tests and audited runner dependency
  closure match the seed manifest.
- [ ] `tools/vir-lsp` and `tools/vscode-vir` are migrated from their pinned
  clean commits with separate provenance and no nested Git/generated/package
  artifact accepted as canonical source.
- [ ] Native LSP build/tests and VS Code extension compile/unit/contract tests
  pass from Vir-3.0; compiler semantics remain owned solely by compiler modules.
- [ ] No Git metadata, frozen tree, build/cache/scratch payload or prebuilt
  compiler binary entered the seed copy.
- [ ] Canonical compiler source and generated output are outside stdlib.
- [ ] `compiler/module.list` is the sole compiler-internal path mapping layer.
- [ ] Module resolution is canonical, deterministic, CWD-independent and tested.
- [ ] Pass entry files are declarative orchestrators and pass architecture check.
- [ ] Typecheck and borrow domains are split into focused tested modules.
- [ ] Every MIR optimization has a separate implementation file.
- [ ] Remaining non-generated giant files are split or have approved follow-up
  issues and explicit rationale.
- [ ] New paths follow descriptive lowercase/lower-camel naming policy with no
  unjustified snake_case.
- [ ] Standard-library registry has no compiler implementation entries.
- [ ] Generated bundle is reproducible and cannot drift from canonical modules.
- [ ] Required registry, stdlib, strict, type, memory, optimizer, CLI,
  source-origin and self-host fixed-point gates pass.
- [ ] A linked REPORT records actual diff, commands, results, deviations,
  limitations and one valid conclusion.
- [ ] `./paper registry --check` and `./paper validate` pass.

## 15. Related Papers

- `VIRC-ISS-0006` — source issue;
- `VIRC-SPC-0004` — self-hosting requirements;
- `VIRC-SPC-0007` — strict compiler E2E contract;
- `VIRC-SPC-0008` — optimizer specification;
- `VIR-SPC-0005` — memory management;
- `VIR-SPC-0014` — module semantics;
- `STLB-SPC-0001` — standard-library boundary.

## 16. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Initial draft defined compiler/stdlib separation, module policy, pass-only orchestration, one-transform-per-file design, and sequential gated migration |
| 2026-10-02 | Added manifest-driven copy migration into sibling `/Users/gengyang/Vir-3.0`, excluding `docs/_legacy` and carrying VPS paper skill, complete tests, and audited runner dependencies |
| 2026-10-02 | Added commit-pinned migration of native `vir-lsp` and `vscode-vir`, with separate ownership, source-only copy rules, generated-artifact exclusions and integration gates |
| 2026-10-02 | Rebased preparation on current Vir 4.0.0 source snapshot `fd0064ea`; baseline failures are recorded rather than required to be green, and later phases must not add unexplained regressions |
| 2026-10-02 | Linked VIRC-RPT-0002 |

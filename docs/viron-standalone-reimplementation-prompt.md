# Prompt: tách Viron khỏi stdlib và triển khai lại thành công cụ độc lập

Làm việc chính trong repository:

`/Users/gengyang/Vir-3.0`

Checkout nguồn lịch sử chỉ dùng để kiểm toán/khôi phục hành vi:

`/Users/gengyang/Vir`

Mục tiêu cuối cùng là triển khai lại Viron thành một Vir-native executable độc
lập tại `Vir-3.0/tools/viron/`, đồng cấp với `tools/vir-lsp`. Viron không còn là
module của standard library. Không được coi việc copy hoặc di chuyển file là đã
hoàn thành tái triển khai; sản phẩm phải có project registry, entrypoint, build,
version, test, binary và bằng chứng VPS chạy end-to-end.

## 1. Quy tắc làm việc bắt buộc

1. Đọc và tuân thủ đầy đủ các skill hiện hành:
   - `.agents/skills/vir-lang/SKILL.md`;
   - `.agents/skills/vir-clean-code/SKILL.md`;
   - `.agents/skills/vir-stdlib-modules/SKILL.md`;
   - `.agents/skills/vir-module-list/SKILL.md`;
   - `.agents/skills/vir-paper-management/SKILL.md`;
   - `vir-syntax` và `vir-memory-management` khi phần code tương ứng phát sinh.
2. Đọc `papers/STANDARD.md`, `papers/REGISTRY.yaml`, toàn bộ
   `papers/VIRON/specs/VIRON-SPC-0001..0006`, các issue
   `VIRON-ISS-0001..0003` và `VIRON-PLN-0001` trước khi sửa source.
3. Chụp baseline bằng `git status --short`. Worktree có thể chứa thay đổi của
   người dùng; không reset, restore, xóa, ghi đè, commit hoặc push phần ngoài
   phạm vi.
4. Không sửa language SPEC nếu không có yêu cầu riêng. Không sửa generated
   compiler bundle bằng tay.
5. Mọi khẳng định về API, Module ID, target, CLI hoặc compiler flag phải được
   xác minh bằng source/test hiện hành. Không dùng DRAFT SPEC như bằng chứng rằng
   capability đã tồn tại.
6. `/Users/gengyang/Vir` là nguồn tham khảo chỉ đọc. Không sửa checkout đó.
7. Không commit, tag, release hoặc push cho đến khi người dùng yêu cầu rõ.

## 2. Nguồn lịch sử phải kiểm toán

Đọc và lập bảng đối chiếu tối thiểu cho:

- `/Users/gengyang/Vir/vir-community/apps/viron/main.vri` — CLI standalone cũ,
  có `func main`, quảng bá phiên bản `2.0.0`;
- `/Users/gengyang/Vir/stdlib/vir/viron/*.vri` — nhóm module Viron trong stdlib;
- `/Users/gengyang/Vir/vir-community/stdlib/vir/viron/*.vri` — bản sao phân kỳ;
- `/Users/gengyang/Vir/vir-community/scripts/build_tools.sh` — workflow build cũ;
- `/Users/gengyang/Vir/bin/viron` và
  `/Users/gengyang/Vir/vir-community/bin/viron` — binary chỉ dùng làm bằng chứng
  hành vi, không dùng làm source of truth;
- `Vir-3.0/stdlib/vir/viron/*.vri` và các entry `viron*` trong
  `Vir-3.0/stdlib/stdlib.vri`;
- `Vir-3.0/tests/test_viron.py` — test Python hỏng trỏ tới `src.viron` không tồn
  tại;
- mọi fixture/test Viron hiện hành trong `Vir-3.0`.

Với từng file/chức năng, phân loại rõ:

- `PORT`: hành vi Viron hợp lệ cần triển khai lại;
- `REWRITE`: intent hợp lệ nhưng code/API cũ không còn canonical;
- `GENERIC-STDLIB`: primitive thực sự tổng quát, có thể thuộc stdlib sau một
  thay đổi STLB riêng và public API/test đầy đủ;
- `DROP`: stub, host-package command, alias giả tương thích, security model sai,
  duplicate hoặc code không có caller/evidence;
- `BLOCKED`: phụ thuộc compiler/stdlib API chưa tồn tại.

Không copy nguyên cây nguồn cũ. Hai cây `stdlib/vir/viron` trong checkout `Vir`
có nội dung phân kỳ; phải so sánh semantic và caller trước khi chọn logic.

## 3. Ranh giới kiến trúc bắt buộc

Sau migration, dependency model phải là:

```text
tools/viron (sản phẩm/CLI độc lập)
├── project + manifest + lock
├── dependency resolver
├── toolchain/sysroot lifecycle
├── package/cache/registry adapters
├── security/integrity/atomic install
├── compiler/LSP process adapters
└── diagnostics
        │
        ├── dùng public Vir stdlib APIs
        └── gọi virc/vir-lsp qua contract tường minh

stdlib
└── chỉ giữ thư viện tổng quát, không giữ Viron product logic
```

Các bất biến:

- Viron sở hữu lifecycle, package, registry, toolchain và orchestration.
- `virc` không truy cập network, không resolve package và không tự cập nhật.
- stdlib không chứa CLI dispatcher, package-manager policy, privilege/system
  administration, Viron config hoặc toolchain state.
- Không dùng `brew`, `apt` hay package manager hệ điều hành làm implementation
  của Vir package management.
- Không có Python implementation song song. Python chỉ được dùng làm test/build
  harness khi cần; production Viron phải là Vir.
- Không giữ hai semantic implementation cho SemVer, manifest, lock, resolver,
  checksum hoặc archive.

## 4. Layout đích

Tạo project độc lập tối thiểu:

```text
tools/viron/
├── module.list
├── vir.toml
├── version.json
├── VERSIONING.md
├── README.md
├── src/
│   ├── main.vri
│   ├── cli/
│   ├── diagnostic/
│   ├── project/
│   ├── manifest/
│   ├── lock/
│   ├── resolve/
│   ├── module_map/
│   ├── toolchain/
│   ├── cache/
│   ├── registry/
│   ├── package/
│   ├── stdlib_lifecycle/
│   ├── security/
│   └── process/
└── tests/
    ├── fixtures/
    └── integration/
```

Không tạo trước thư mục/module rỗng chỉ để khớp sơ đồ. Chỉ thêm module khi có
implementation và test thật.

`tools/viron/module.list` là registry project bắt buộc:

- đặt `root = src` trước mappings;
- dùng exact mappings cho từng module public/internal đã tồn tại;
- dùng namespace project rõ ràng như `viron.cli`, `viron.project`,
  `viron.resolve`;
- không trùng chính xác với Module ID còn tồn tại trong `stdlib/stdlib.vri`;
- không dùng alias file/directory chồng lấn;
- mỗi `.vri` chỉ có một canonical Module ID.

`tools/viron/vir.toml` mô tả chính Viron như một project/package; không dùng nó
thay cho `module.list`.

## 5. Tách khỏi standard library

Xử lý toàn bộ các entry hiện tại:

```text
viron
viron.fs
viron.net
viron.pkg
viron.proc
viron.alias
viron.maha
viron.svc
viron.user
```

Yêu cầu:

1. Tìm tất cả caller của từng Module ID/symbol trước khi di chuyển.
2. Chuyển product logic cần giữ sang `tools/viron/src/**` và đăng ký bằng
   `tools/viron/module.list` trong cùng thay đổi.
3. Xóa các mapping `viron*` khỏi `stdlib/stdlib.vri` chỉ sau khi caller đã
   migrate và project Viron build được bằng registry mới.
4. Xóa `stdlib/vir/viron/` chỉ khi không còn caller, mapping hoặc test phụ thuộc.
5. Nếu một primitive thực sự tổng quát cần ở stdlib, không giữ namespace
   `viron.*`. Thiết kế public stdlib API đúng domain, tạo/link STLB ISSUE khi
   cần, thêm mapping/export/registry Markdown/test rồi mới đổi caller.
6. Kiểm tra không còn chuỗi `stdlib/vir/viron`, mapping `viron*` hoặc include /
   import legacy ngoài paper/history/fixture migration có chủ đích.
7. Không xóa historical VPS papers hoặc provenance.

## 6. Phạm vi triển khai theo phase

### Phase 0 — Baseline và contract reconciliation

- Xác minh lại mọi claim trong `VIRON-ISS-0001..0003` theo source hiện tại.
- Cập nhật `VIRON-PLN-0001` nếu layout `tools/viron/` thay cho layout dự kiến cũ
  là một quyết định đã được duyệt; ghi revision, không viết lại lịch sử.
- Liệt kê contradiction giữa DRAFT SPEC và compiler hiện tại, đặc biệt
  `--sysroot`, `--module-map`, calendar version và layout cài đặt.
- Mở/link VIRC hoặc STLB ISSUE riêng nếu cần thay compiler hay public stdlib API.
- Không triển khai workaround giả trong Viron để che một contract compiler thiếu.

### Phase 1 — Standalone executable xanh

- Tạo `module.list`, `vir.toml`, version metadata và canonical `src/main.vri`.
- Tạo CLI tối thiểu: `--help`, `--version`, structured error/exit codes.
- Tạo `tools/build_viron.py` hoặc workflow tương đương có manifest provenance,
  source hashes, compiler hash, target và output hash.
- Build ra `bin/viron`; không sửa trực tiếp binary bằng tay.
- Chạy từ repository root và alternate CWD.

### Phase 2 — Local-first vertical slice

Triển khai không cần network:

- `viron new <name>` và `viron new --lib <name>`;
- project discovery;
- đọc/validate `vir.toml` và mandatory project `module.list`;
- path dependency;
- exact deterministic `vir.lock`;
- deterministic module map/input cho compiler theo capability thực tế;
- `viron check`, `build`, `run`, `test`, `package`;
- package archive reproducible, không chứa path tuyệt đối hoặc timestamp tùy ý.

### Phase 3 — Toolchain/sysroot lifecycle

- `viron setup`;
- install/list/default/uninstall/rollback/verify/repair toolchain;
- layout dưới `VIR_HOME` có thể override trong test;
- staging + atomic rename, không làm hỏng bản hiện hành khi install lỗi;
- compiler và LSP dispatch dùng sysroot/version tường minh;
- không sửa shell profile nếu chưa có opt-in/contract rõ.

### Phase 4 — Resolver, cache và registry

- exact/range/transitive SemVer resolution;
- cycle/conflict diagnostics;
- immutable/content-addressed cache;
- offline/frozen modes;
- checksum bắt buộc, traversal/symlink archive defense;
- concurrent invocation lock;
- mock registry cho search/fetch và `publish --dry-run`;
- production publish bị khóa cho đến khi protocol/trust root được review.

### Phase 5 — Standard-library lifecycle

- `viron std list/install/update/verify/repair/rollback`;
- phân biệt compiler-coupled sysroot với independently versioned library;
- không cập nhật ngầm Viron, compiler, stdlib và project dependencies cùng lúc;
- không chuyển ownership nội dung public stdlib API từ STLB sang VIRON.

### Phase 6 — Release và migration closure

- thay test Python nonexistent bằng native/integration tests gọi binary thật;
- xóa fixture tự cài lại production algorithms hoặc chuyển thành focused unit
  fixture có mục đích rõ;
- cập nhật root installer để cài Viron chỉ sau khi binary đa nền tảng đã qua
  execution test;
- tạo artifacts/checksum/provenance cho macOS ARM64, Linux ARM64 và Linux
  x86_64 nếu compiler/backend hiện tại hỗ trợ và đã chạy thật;
- tạo VIRON REPORT, map acceptance criteria, ghi limitation/deviation.

## 7. Versioning độc lập

Viron dùng Semantic Version độc lập với compiler calendar version và vir-lsp.

- Không suy ra Viron version từ `2026.x` hoặc `vir-lsp 1.3.0`.
- Audit `2.0.0` trong source lịch sử. Chỉ giữ `2.0.0` làm initial public version
  nếu paper/release compatibility chấp thuận; nếu không, ghi quyết định và
  migration rõ ràng.
- `tools/viron/version.json` là canonical metadata.
- Mọi surface `--version`, banner, manifest và release asset phải đồng bộ.
- Tạo `tools/viron/VERSIONING.md` và bump tool idempotent theo `VIRON-ISS`.
- Mỗi VIRON issue làm thay đổi production Viron chỉ bump đúng một lần trước khi
  báo hoàn tất.
- Không bump compiler hoặc vir-lsp nếu code của chúng không đổi.

## 8. Quy tắc code Vir

- Dùng canonical syntax hiện tại; không copy legacy syntax chỉ vì compiler còn
  chấp nhận.
- `let` cho binding không gán lại, `var` chỉ khi mutate; group declarations liên
  quan.
- Signature dài hoặc từ ba tham số dùng block `in` / `ref` / `out` đúng contract.
- Public symbol phải có `export` tường minh.
- Một canonical dependency form cho mỗi Module ID; không vừa `include` vừa
  `import` cùng module nếu không có bằng chứng alias bắt buộc.
- External resources như file, socket, lock, process phải có cleanup xác định;
  arena reset không thay thế close/unlock/wait.
- Không đưa secret/token vào source, log, lockfile hay test fixture.
- Path do archive/registry cung cấp phải được canonicalize và chặn escape khỏi
  staging root.

## 9. Test bắt buộc

Tối thiểu phải có:

1. module registry validation: missing path, duplicate, collision, alternate CWD;
2. `viron --help`, `--version`, unknown command và stable exit codes;
3. local project/app/library/path dependency end-to-end;
4. deterministic lock/module map/archive chạy lặp lại cho cùng hash;
5. malformed manifest/lock/module registry diagnostics;
6. dependency cycle, SemVer conflict và frozen mismatch;
7. cache hit, offline miss, checksum mismatch;
8. archive traversal, absolute path và symlink escape rejection;
9. interrupted install không phá active toolchain;
10. concurrent install/update không publish partial state;
11. sysroot/toolchain selection từ alternate CWD;
12. LSP/compiler dispatch đúng version;
13. Linux x86_64, Linux ARM64 và macOS ARM64 execution smoke khi phát hành các
    target đó;
14. tìm kiếm chứng minh không còn production dependency vào
    `stdlib/vir/viron`.

Test phải gọi production modules/binary. Không chấp nhận test pass vô điều kiện
hoặc fixture copy lại resolver/SemVer implementation.

## 10. Lệnh kiểm chứng tối thiểu

Điều chỉnh theo CLI thực tế nhưng phải báo chính xác command/output:

```sh
git status --short

python3 tools/module_graph.py --root tools/viron --resolve viron.main
python3 tools/module_graph.py --root tools/viron --entry viron.main

python3 tools/build_viron.py
./bin/viron --version
./bin/viron --help

python3 -m pytest tests/test_viron*.py -q

rg -n '^viron(\.| =)|= viron/' stdlib/stdlib.vri
rg -n 'stdlib/vir/viron|include viron|from viron' \
  --glob '!papers/**' --glob '!docs/**'

./paper registry --check
./paper validate
git diff --check
```

Ngoài ra phải compile/check từng canonical Vir source, chạy local-first E2E từ
ít nhất hai CWD và chạy binary thật trên từng release platform. Graph-tool pass
không thay thế native compiler test.

## 11. Điều kiện hoàn tất

Không báo hoàn tất nếu thiếu bất kỳ mục nào:

- `tools/viron/` là project độc lập với `module.list` hợp lệ;
- canonical entrypoint build reproducibly thành `bin/viron`;
- Viron version metadata và CLI đồng bộ;
- local-first vertical slice chạy end-to-end;
- không còn product logic/mapping Viron trong stdlib;
- mọi caller đã migrate hoặc blocker được link bằng ISSUE;
- tests gọi production implementation và có negative/security coverage;
- root/alternate-CWD và các target phát hành đã được thực thi;
- VPS registry/validation xanh;
- REPORT ghi rõ diff, evidence, limitation và conclusion;
- issue chỉ RESOLVED/CLOSED theo đúng gate của `papers/STANDARD.md`.

## 12. Báo cáo bàn giao

Báo cáo cuối phải gồm:

- cây file mới của `tools/viron/`;
- bảng source cũ → module mới → hành động `PORT/REWRITE/DROP/BLOCKED`;
- danh sách entry đã xóa khỏi `stdlib/stdlib.vri`;
- Module IDs mới và `module.list` validation;
- version trước/sau và issue gây bump;
- commands/tests đã chạy với kết quả;
- binary/artifact hashes theo platform nếu có;
- paper IDs/status/revision đã cập nhật;
- limitation, deviation và follow-up issue còn mở;
- xác nhận không sửa hoặc làm mất thay đổi ngoài phạm vi.

Không dùng các câu “đã hoàn tất”, “production-ready”, “secure” hoặc “đa nền
tảng” nếu chưa có bằng chứng tương ứng từ binary/test/report hiện tại.

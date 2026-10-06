---
id: "VIR-SPC-0006"
type: "SPEC"
domain: "VIR"
title: "Hệ thống Module, Registry và Include/Import — Đặc tả Kỹ thuật"
status: "ACTIVE"
version: "3.2.0"
language: "vi"
spec_class: "SPECIFICATION"
created: "2026-03-10"
updated: "2026-10-06"
owners:
  - "VIR"
  - "VIRC"
components:
  - "module-system"
  - "module-registry"
  - "include"
  - "import"
aliases:
  - "docs/MODULE_INCLUDE_SYSTEM.md"
related:
  issues:
    - "VIR-ISS-0005"
    - "VIR-ISS-0006"
    - "VIR-ISS-0007"
    - "VIR-ISS-0008"
    - "VIRC-ISS-0008"
    - "VIRC-ISS-0042"
    - "VIRC-ISS-0043"
    - "VIRC-ISS-0044"
    - "VIRC-ISS-0045"
    - "VIRC-ISS-0046"
    - "VIRC-ISS-0047"
  plans: []
  reports:
    - "VIRC-RPT-0032"
    - "VIRC-RPT-0033"
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
  - "modules"
  - "module-list"
  - "stdlib-registry"
  - "canonical-identity"
---

# VIR-SPC-0006 — Hệ thống Module, Registry và Include/Import — Đặc tả Kỹ thuật

## 1. Mục đích và phạm vi

Tài liệu này quy định hợp đồng ngôn ngữ cho module identity, registry,
`include`, `import`, `export` và alias. Nó mô tả hành vi mà mọi compiler và
tooling Vir phải cung cấp; nó không ghi trạng thái triển khai của một phiên bản
`virc` cụ thể.

`VIR-SPC-0017` và `VIR-SPC-0018` quy định grammar toàn ngôn ngữ. Khi nội dung
module bị trùng, tài liệu này là nguồn chi tiết cho registry, canonical identity
và resolution semantics.

## 2. Mô hình module

### 2.1. Ba lớp danh tính

Một dependency có ba lớp khác nhau:

1. **Dependency spelling** trong source, ví dụ registered Module ID `math`,
   dotted ID `app.net.http`, hoặc direct path `"helpers/provider.vri"`.
2. **Canonical Module ID** dùng cho registry, dedup, cycle detection và
   provenance.
3. **Physical path** của source file `.vri`.

Module ID do registry quyết định. Tên file hoặc thư mục không tự tạo public
Module ID. Hai spelling hợp lệ cùng chỉ một source unit phải hội tụ về một
canonical identity cho dedup và cycle detection, trừ khi registry cố ý khai báo
chúng là hai module độc lập.

Dấu chấm `.` là separator duy nhất trong Module ID. Prefix nội bộ như
`stdlib::`, `project::` hoặc `path::` không phải cú pháp source; `A::B` phải bị
từ chối.

### 2.2. `module` declaration

```vir
module app.math
```

`module` ghi tên logic của source unit. Nó không thay thế registry và không tự
đăng ký physical file dưới một identity mới.

### 2.3. Thứ tự declaration

Thứ tự module-level chuẩn là:

```text
include → import → const → var → entity → func → export → share
```

`export` là declaration riêng sau symbol definition. `export func ...` không
phải cú pháp chuẩn.

`has`, standalone `get name from module`, và các deferred/lazy module directive
không thuộc grammar Vir 3.0. Function definition được thu thập không phụ thuộc
thứ tự trong source unit. `get` vẫn là identifier hợp lệ, ví dụ
`http.get(...)` hoặc `import get from net.http as fetch`.

## 3. Registry

### 3.1. Standard-library registry: `stdlib.vri`

Standard library thuộc Vir toolchain, không thuộc project tiêu thụ. Toolchain
chọn một active stdlib theo sysroot/install contract của nó, rồi đọc file
`stdlib.vri` trong stdlib directory đã chọn. Project không phải vendor hoặc copy
stdlib và không được trộn các entry stdlib vào `module.list`.

Registry có dạng:

```text
root = vir
schema = 1
version = 2.0.0
abi_version = 2
compiler_min = 4.2.0

math = math/basic.vri
http.types = protocol/http_types.vri
```

Quy tắc:

- `root` là relative directory path được resolve tương đối từ thư mục chứa `stdlib.vri`. Giá trị `root` bắt buộc phải nằm hoàn toàn bên trong thư mục `stdlib` đang hoạt động; nghiêm cấm sử dụng đường dẫn tuyệt đối hoặc path traversal (`..`);
- Bốn metadata directives bắt buộc dùng để thẩm định tính tương thích giữa toolchain và thư viện chuẩn:
  - `schema = <int>`: phiên bản định dạng của registry (hiện tại: `1`);
  - `version = <semver>`: phiên bản của standard library theo Semantic Versioning 2.0.0 (`major.minor.patch`);
  - `abi_version = <int>`: phiên bản ABI runtime yêu cầu (hiện tại: `2`);
  - `compiler_min = <semver>`: phiên bản compiler tối thiểu mà stdlib hỗ trợ (`major.minor.patch`). Trình biên dịch có phiên bản nhỏ hơn giá trị này sẽ bị từ chối;
- Bốn directive trên là reserved metadata keys, không phải public Module ID; trình ánh xạ module (`module_resolver`) bỏ qua chúng khi map Module ID sang file mã nguồn;
- Mỗi entry khác ngoài `root` và 4 reserved metadata directives có dạng `module.name = relative/path.vri`;
- Key là public stdlib Module ID, value phải trỏ tới target hợp lệ dưới active stdlib root;
- Compiler không được suy public Module ID trực tiếp từ cây thư mục;
- Duplicate key, invalid ID, missing metadata, version mismatch, và missing target là lỗi registry.

Source tree có thể dùng `stdlib/stdlib.vri` cho development. Distribution có
thể đặt cùng registry dưới layout khác, nhưng registry đang được active
toolchain chọn mới là authority.

### 3.2. Project registry: `module.list`

Project nhiều file khai báo module bằng `module.list`. Resolver tìm registry áp
dụng từ thư mục entry/source đi ngược qua các thư mục cha. Vị trí file xác định
initial registry base; vì vậy `module.list` không bắt buộc nằm ở repository root.

```text
# Repo/module.list
root = cmd
server = server.vri
helper = helper.vri
```

Entry `Repo/cmd/server.vri` dùng registry trên với base `Repo/cmd`. Cách tương
đương khi đặt registry cạnh source là:

```text
# Repo/cmd/module.list
server = server.vri
helper = helper.vri
```

`root = .` hợp lệ nhưng có thể bỏ khi mapping đã tương đối với thư mục chứa
registry. Nếu có `root`, nó phải xuất hiện trước mappings và đổi base cho các
mapping theo sau.

Mỗi entry có một trong hai dạng:

- value kết thúc bằng `.vri` là exact file mapping;
- value là directory tạo directory alias: dotted tail được đổi thành path
  segments rồi thêm `.vri`.

Ví dụ `app = src` cho phép `app.net.http` ánh xạ tới
`src/net/http.vri`. Duplicate key, invalid ID, missing target và collision giữa
exact mapping với directory alias là lỗi registry. Một exact mapping không được
âm thầm rơi sang filesystem search nếu target không hợp lệ.

### 3.3. Reserved stdlib IDs và registry validity

Các canonical Module ID trong active stdlib registry là reserved đối với
project `module.list`.

Khi load registry, toolchain phải tạo hai tập `StdlibModules` và
`ProjectModules`, rồi xác minh:

1. không có duplicate ID trong stdlib registry;
2. không có duplicate ID trong project registry;
3. `StdlibModules ∩ ProjectModules` rỗng.

Exact cross-registry equality là compile-time project-configuration error ngay
cả khi source chưa reference ID đó. Diagnostic phải ghi Module ID và provenance
của cả hai registry entries.

Chỉ equality của canonical ID bị cấm. Prefix relationship không phải collision:

```text
stdlib: http       project: http.app       # hợp lệ
stdlib: db.sqlite  project: db.sqlite3     # hợp lệ
stdlib: json       project: json           # lỗi
```

Vir không có language-level `override`, `prefer-project` hoặc cơ chế shadow
stdlib. Test hook nội bộ, nếu tồn tại, không thuộc contract.

### 3.4. Resolution layers

Sau khi registry validity đã được xác minh, resolver tra cứu theo các lớp:

1. exact/directory mapping của project;
2. dependency/package mapping đã được package layer cung cấp;
3. active toolchain stdlib registry;
4. compiler builtins có contract riêng, nếu có.

Project và stdlib đã disjoint trước lookup, vì vậy thứ tự trên không tạo
shadowing semantics. Filesystem compatibility search không được thay đổi
canonical identity hoặc che registry error.

### 3.5. Dotted Module ID và direct path

Vir hỗ trợ hai nhóm dependency target:

1. **Module ID** — tên logic dùng dấu chấm, được resolve qua exact mapping hoặc
   directory alias trong registry.
2. **Direct path** — đường dẫn `.vri` tương đối hoặc tuyệt đối, dùng như
   compatibility target mà không công bố public Module ID mới.

Registered dotted style là dạng chuẩn cho project và stdlib:

```vir
include app.net.http
import Client from app.net.http
```

Với exact mapping:

```text
app.net.http = src/net/http.vri
```

hoặc directory alias:

```text
app = src
```

Direct-path compatibility forms được chấp nhận cho `include` và provider của
selective import:

```vir
include "provider.vri"
include provider.vri
include "helpers/provider.vri"
import answer from "provider.vri"
```

Quoted path biểu diễn path rõ ràng. Bare path không được chứa whitespace và kết
thúc ở separator của statement. Absolute path có thể được resolver chấp nhận,
nhưng portable source không nên phụ thuộc machine-specific absolute path.

Resolver xử lý target theo các nguyên tắc:

- exact/directory registry lookup được ưu tiên cho Module ID;
- direct relative path được normalize theo active source/build base; portable
  source không được phụ thuộc current working directory;
- implementation có thể giữ current-working-directory lookup làm fallback cuối
  cho compatibility, nhưng kết quả đó là non-portable và không được ưu tiên hơn
  registry hoặc source-relative resolution;
- nếu normalized direct path trùng physical target của một registry entry, nó
  phải dùng canonical Module ID của entry đó cho dedup, cycle và provenance;
- nếu không trùng registry entry, resolver tạo path-derived canonical identity;
- direct path không đăng ký public Module ID và không cho phép bypass invalid
  hoặc missing exact registry mapping.

Để tương thích mã cũ, một dotted spelling không có registry entry có thể được
thử như path bằng cách đổi `.` thành `/` và thêm `.vri`, ví dụ
`legacy.net.http` → `legacy/net/http.vri`. Đây là legacy dotted-path fallback,
không phải implicit module publication. Source mới nên đăng ký Module ID thay vì
phụ thuộc fallback này.

## 4. `include`

### 4.1. Grammar

```text
include_directive := "include" include_item ("," include_item)*
include_item      := dependency_target ("as" IDENT)?
```

```vir
include math
include app.net.http as web
include math, app.io.file as file, app.net.http as web
```

### 4.2. Semantics

`include` nạp toàn bộ source unit vào compilation graph và thiết lập namespace
binding. Không có alias, local namespace dùng tên module chuẩn; `as name` thay
local namespace bằng `name` mà không đổi canonical Module ID.

Multi-include tương đương các `include` riêng theo thứ tự trái sang phải. Mỗi
alias chỉ áp dụng cho item ngay trước nó.

Với mỗi item, resolver phải:

1. resolve dependency target thành canonical identity và physical path;
2. từ chối dependency cycle và báo chain hữu ích;
3. nạp một canonical identity nhiều nhất một lần;
4. giữ source provenance cho diagnostics;
5. tạo namespace binding đã yêu cầu.

## 5. `import`, `export` và alias

### 5.1. Selective import

```text
selective_import := "import" import_item ("," import_item)* "from" dependency_target
import_item      := IDENT ("as" IDENT)?
```

```vir
import add from math
import add, sub from math
import get from net.http as fetch
import add as plus, sub as minus from math
```

Selective import tự resolve và nạp provider; không cần `include` trước. Nó đưa
mọi loại named declaration đã `export` vào local scope, gồm function, type,
constant và variable. Alias đổi local binding, không đổi tên export hoặc
canonical Module ID.

### 5.2. Umbrella import

```vir
import from app.api
```

Umbrella import đưa toàn bộ declarations đã `export` của provider vào local
scope. Nó không đưa private declarations vào scope và không tạo quyền truy cập
ngoài export surface.

### 5.3. Whole-module namespace import

```vir
import app.net.http
import app.net.http as web
```

Whole-module import nạp provider và tạo namespace binding; nó không inject toàn
bộ exports thành unqualified local names. `as web` chỉ đổi local namespace.

Namespace alias của `include`/whole-module `import` khác selective-import
alias: `web.get(...)` dùng namespace alias, còn `fetch(...)` dùng local symbol
alias.

### 5.4. `export`

Provider định nghĩa public API bằng declaration riêng:

```vir
func add(a: int, b: int) -> int:
    out a + b
end.

export add
```

Mọi import chỉ được quan sát declarations đã export. Missing symbol, private
symbol, duplicate local alias và alias conflict đều là compile-time errors.

## 6. Dependency graph, dedup và diagnostics

- Include/import guard khóa theo canonical Module ID, không theo raw spelling.
- Reference lặp lại không được tạo duplicate definition hoặc duplicate
  namespace binding.
- Một module đang ở active dependency stack mà được yêu cầu lại tạo cycle
  error; Vir 3.0 không có type-only deferred-loading exception.
- Registry errors được phát khi load registry và không được che bằng fallback.
- Source diagnostics phải giữ physical file, line và canonical Module ID.
- Hai spellings hội tụ cùng canonical ID phải dùng chung dedup/cycle state.

## 7. Conformance requirements

Một implementation conforming phải có positive và negative coverage cho:

- exact mapping, directory alias, optional `root` và registry discovery từ
  entry/source;
- registered dotted Module ID, quoted/bare direct path, legacy dotted-path
  fallback và canonical convergence khi các spelling cùng trỏ một source unit;
- multi-include, include namespace alias, selective import alias, umbrella
  import và whole-module namespace alias;
- export-only visibility cho functions, types, constants và variables;
- duplicate registry IDs, missing targets, mapping collisions, exact
  project/stdlib collisions và prefix-only non-collisions;
- repeated/diamond dependency dedup, cycle diagnostics và source provenance;
- rejection of `A::B`, removed forward declarations, removed standalone
  state-import directives, and removed deferred module directives as Vir 3.0
  syntax.

Các test/REPORT triển khai có thể dẫn chiếu SPEC này, nhưng kết quả pass/fail của
một compiler cụ thể không phải nội dung normative của SPEC.

## 8. Migration từ Vir 2.x

| Vir 2.x form | Vir 3.0 |
|---|---|
| Untyped forward declaration | Xóa declaration; định nghĩa `func` bình thường |
| Standalone state import | Dùng selective `import` cho named export |
| Type-only deferred module directive | Tái cấu trúc dependency graph hoặc dùng interface contract được đặc tả riêng trong tương lai |

Tên `get` không bị reserved khỏi API. `get(...)`, `http.get(...)` và
`import get from net.http as fetch` vẫn hợp lệ.

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-02 | 1.0.0 | Migrated from `docs/MODULE_INCLUDE_SYSTEM.md` and assigned stable ID `VIR-SPC-0006` |
| 2026-10-06 | 2.0.0 | Major rewrite for self-hosted text preprocessing, registry-backed identity, include/import/export/alias behavior, verified conformance gaps, and executable verification gates |
| 2026-10-06 | 3.0.0 | Converted the paper to a compiler-independent language contract; removed legacy forward/state/deferred module forms; standardized multi-include, namespace/umbrella imports, registry placement/root behavior, and exact stdlib-ID reservation |
| 2026-10-06 | 3.1.0 | Specified registered dotted Module IDs, direct `.vri` path compatibility, legacy dot-to-path fallback, and canonical convergence across equivalent spellings |
| 2026-10-06 | 3.2.0 | Standardized stdlib registry metadata directives (schema, version, abi_version, compiler_min) and enforced root containment within active stdlib directory |

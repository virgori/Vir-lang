---
id: "VIRC-ISS-0047"
type: "ISSUE"
domain: "VIRC"
title: "Cross-registry collision diagnostics lose module identity and registry provenance"
status: "OPEN"
severity: "S2"
priority: "P1"
created: "2026-10-06"
updated: "2026-10-06"
owners:
  - "compiler"
  - "frontend"
  - "tooling"
components:
  - "module-resolution"
  - "module-registry"
  - "diagnostics"
  - "regression-suite"
related:
  issues:
    - "VIR-ISS-0008"
    - "VIRC-ISS-0043"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "module-list"
  - "collision"
  - "e2123"
  - "diagnostic-provenance"
---

# VIRC-ISS-0047 — Cross-registry collision diagnostics lose module identity and registry provenance

## 1. Summary

Native resolver đã reject exact project/stdlib Module ID collision tại
`module.list` load bằng E2123, đúng core safety policy. Tuy nhiên diagnostic làm
mất module ID và stdlib declaration provenance, gọi lỗi là generic duplicate
project entry, trong khi duplicate project key E2121 lại bị mô tả nhầm là
duplicate trong stdlib. Python graph resolver reject cùng collision bằng generic
E2121. Không có focused regression test cho exact-reject/prefix-allow contract.

## 2. Context

Resolver load `stdlib.vri` trước rồi project `module.list`. Native code có ba
đường kiểm tra thực tế: duplicate stdlib key, duplicate project key và project
key trùng stdlib key. Project/stdlib exact collision sử dụng E2123, nhưng call
site truyền C-string bằng cast sang `string`; message formatter mong fat string,
nên extra module name không hiện trong observed output.

`VIR-ISS-0008` chốt policy exact-only và no-shadowing. `VIRC-ISS-0043` sở hữu
việc chọn đúng active toolchain stdlib/sysroot; collision validation phải chạy
trên registry mà selection đó trả về.

## 3. Expected Behavior

- Exact project/active-stdlib canonical ID collision fail ngay khi load registry,
  dù entry source không dùng module.
- Prefix-only IDs như stdlib `json` và project `json.app` được chấp nhận.
- Diagnostic cross-registry có stable classification/code, module ID, project
  registry path/line/mapping và stdlib registry path/line/mapping.
- Duplicate trong project và duplicate trong stdlib được phân biệt đúng, mỗi lỗi
  chỉ cả first/duplicate declarations hữu ích.
- Native compiler, Python graph resolver, IDE/LSP handoff và JSON/classic output
  thống nhất policy; wording có thể khác nhưng semantic fields không khác.
- Không có public flag/manifest syntax bỏ qua collision check.

## 4. Actual Behavior

- Exact `json` collision bị native compiler từ chối E2123 trước source parsing,
  nhưng Analysis chỉ là `duplicate module in project registry`; không có `json`,
  stdlib path, stdlib line hay hai mappings.
- Duplicate project key bị E2121 với message `duplicate module in stdlib
  registry`, phân loại sai registry.
- Prefix-only `json.app` compile và chạy thành công.
- Python resolver từ chối exact cross-registry collision bằng E2121 generic
  duplicate, dù message có previous/current registry paths; code/classification
  không khớp native E2123.
- Focused module resolver unit suite không có case cross-registry exact collision
  hoặc prefix-only allowance.

## 5. Reproduction

Active stdlib đã có `json`. Project exact fixture:

```text
# module.list
root = .
json = local_json.vri
```

```vir
# main.vri — intentionally does not reference json
func main:
    out 0
end.
```

```sh
./bin/virc /private/tmp/vir_registry_collision_audit/exact/main.vri \
  -o /private/tmp/vir_registry_collision_audit/exact.out --color=never -q
```

Prefix control:

```text
root = .
json.app = local_json.vri
```

Duplicate-project control:

```text
root = .
local = a.vri
local = b.vri
```

## 6. Evidence

- CONFIRMED: `compiler/src/main/module_resolver.vri:271-285` exact-compares each
  project key against loaded stdlib keys and emits E2123 before registration.
- CONFIRMED: `compiler/src/semantic/diagnostics/msg_frontend.vri:191-201` labels
  E2123 `duplicate module in project registry`; formatter has no fields for both
  declarations.
- CONFIRMED: `tools/module_graph.py:76-83` treats any pre-existing key as E2121,
  without registry-class distinction.
- OBSERVED ngày 2026-10-06 tại HEAD `e1fc2d5`, binary SHA-256
  `db2a418c7952fffd66344ae9d29c28f5835ff25e08e634ea5915b911c00c7e69`:
  exact collision exit 1/E2123, prefix-only compile 0/run 0, project duplicate
  exit 1/E2121 với sai wording `stdlib registry`.
- OBSERVED: direct Python `ModuleResolver` exact fixture raises E2121 and names
  both registry locations; prefix fixture passes; duplicate project raises E2121.
- CONFIRMED: search trong `tests/module/test_module_resolver.py` không thấy E2123
  hoặc cross-registry collision fixture.

## 7. Scope

### Affected

- native registry loader and diagnostic formatter;
- Python module graph resolver and focused module tests;
- classic/JSON diagnostics and IDE/LSP registry handoff;
- sysroot-selected stdlib provenance and project configuration validation.

### Not affected / Unknown

- Core native exact collision rejection đã tồn tại; ISSUE không yêu cầu đảo
  precedence hoặc thêm một shadowing mode.
- Prefix-only relationships phải tiếp tục hợp lệ.
- Variable/type/function lexical shadowing không liên quan registry Module IDs.
- `VIRC-ISS-0043` vẫn sở hữu sysroot discovery; ISSUE này không tự triển khai
  `--sysroot`, `VIR_SYSROOT` hay installed layout.
- NOT_VERIFIED: current IDE diagnostic payload có đủ structure để mang hai source
  locations mà không đổi schema.

## 8. Impact

Safety behavior đúng nhưng diagnostic hiện khiến người dùng tìm duplicate sai
registry và không biết stdlib declaration nào bị xung đột. Tooling dùng code khác
có thể tạo inconsistent CI/IDE expectations, còn thiếu tests khiến exact-only
policy dễ bị đổi thành prefix rejection hoặc shadowing khi resolver được refactor.

Severity S2 vì compile fail đúng nhưng diagnostic/provenance và cross-tool
conformance sai ở core project configuration. Priority P1 vì sysroot resolver
đang được thiết kế và cần khóa invariant trước refactor.

## 9. Preliminary Analysis

- CONFIRMED: native validation là eager và exact-only; không cần thêm một lookup-
  time check để đạt core prohibition.
- CONFIRMED: current diagnostic mất module/provenance và duplicate-project
  wording phân loại sai.
- HYPOTHESIS: registry entries cần giữ source kind, path, line và original value
  trong một shared structure để native/tooling diagnostics hội tụ.
- NOT_VERIFIED: giữ E2123 hay cấp subcodes mới cho ba collision classes; PLAN có
  thể chọn miễn diagnostic identity ổn định và tests khóa contract.

## 10. Acceptance Criteria

- [ ] Native focused test chứng minh exact project/stdlib collision fail tại
  registry load dù entry không được include/import.
- [ ] Prefix-only matrix (`http`/`http.app`, `db.sqlite`/`db.sqlite3`) pass; exact
  directory-alias key collision cũng fail.
- [ ] Cross-registry diagnostic chứa canonical ID, cả registry paths, line
  numbers và mapping values trong classic và JSON modes.
- [ ] Duplicate stdlib, duplicate project và cross-registry collision có đúng
  classification cùng first/second declaration provenance.
- [ ] Native compiler, Python graph resolver và IDE/LSP registry path agree on
  exact-reject/prefix-allow policy and stable diagnostic identity.
- [ ] Collision validation uses the active sysroot stdlib selected under
  `VIRC-ISS-0043`, không một source-tree registry tình cờ khác version.
- [ ] Không public CLI/manifest escape hatch; test-only hooks không ảnh hưởng
  production contract.
- [ ] Existing missing-target, prefix-collision, alias self-load, cycle/dedup and
  CWD-independence tests remain green.
- [ ] Stage 2 == stage 3 bootstrap và accepted REPORT ghi raw diagnostics/test
  matrix trước khi ISSUE đóng.

## 11. Related Papers

### Issues

- `VIR-ISS-0008` — normative exact-ID reservation and no-shadowing contract.
- `VIRC-ISS-0043` — active toolchain sysroot and stdlib registry discovery.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Opened from native/Python exact-collision, prefix-only and duplicate-registry probes |
| 2026-10-06 | Linked VIR-ISS-0008 |
| 2026-10-06 | Linked VIRC-ISS-0043 |

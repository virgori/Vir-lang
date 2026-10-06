---
id: "VIR-ISS-0008"
type: "ISSUE"
domain: "VIR"
title: "Standard library module identifiers are not normatively reserved against project collisions"
status: "RESOLVED"
severity: "S2"
priority: "P1"
created: "2026-10-06"
updated: "2026-10-06"
owners:
  - "language"
components:
  - "module-system"
  - "module-registry"
  - "canonical-identity"
  - "specification"
related:
  issues:
    - "VIR-ISS-0006"
    - "VIRC-ISS-0047"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "module-list"
  - "reserved-identity"
  - "shadowing"
  - "compile-time-error"
---

# VIR-ISS-0008 — Standard library module identifiers are not normatively reserved against project collisions

## 1. Summary

Active module specification chưa quy định standard-library module identifiers
là reserved đối với project registry. `VIR-SPC-0006` còn mô tả lookup project
trước stdlib, có thể bị đọc thành shadowing precedence, trong khi native resolver
hiện đã từ chối exact project/stdlib collision ngay lúc load `module.list`.

Vir cần chốt hành vi hiện hành thành normative contract: project không được khai
báo canonical Module ID trùng chính xác một ID trong active toolchain stdlib;
prefix relationship đơn thuần không phải collision và không bị cấm.

## 2. Context

Standard library công bố canonical IDs qua `stdlib/stdlib.vri`; project công bố
IDs qua nearest `module.list`. Hai registry được load trước dependency source.
Một ID đồng thời thuộc cả hai registry phá ý nghĩa canonical identity và khiến
resolution phụ thuộc câu hỏi “project first hay stdlib first”.

Native `module_resolver.vri` hiện load stdlib trước, rồi so từng project key với
tập stdlib key và phát E2123. Python graph resolver cũng load stdlib trước project
và từ chối key trùng qua generic duplicate check. Tuy nhiên active SPEC chỉ nói
duplicate bên trong registry và file/directory prefix collision; nó chưa định
nghĩa cross-registry exact collision, prefix allowance hay no-override rule.

## 3. Expected Behavior

- Standard-library canonical Module IDs của active Vir toolchain là reserved.
- Project `module.list` có exact ID bằng một stdlib ID là compile-time project
  configuration error ngay khi registry được load, dù source chưa reference ID.
- Chỉ exact canonical ID equality bị cấm. Nếu stdlib có `http`, project vẫn được
  khai báo `http.app`, `http.router` hoặc `http.server`; nếu stdlib có
  `db.sqlite`, project có thể khai báo `db.sqlite3`.
- Duplicate trong stdlib, duplicate trong project và exact cross-registry
  collision là ba invalid-registry classes riêng, có provenance rõ ràng.
- Không có language-level `override`, `prefer-project` hay public compiler flag
  cho phép shadow stdlib. Internal test hooks, nếu có, không thuộc contract.
- Active stdlib registry là registry đã được toolchain/sysroot selection chọn;
  collision check không được dùng một source-tree registry khác version.
- Sau validation, resolution chỉ cần lookup exact ID trong disjoint project và
  stdlib sets; không có shadowing semantics.

## 4. Actual Behavior

- `VIR-SPC-0006:117-126` định nghĩa stdlib registry và `:143-157` định nghĩa
  project registry, nhưng không cấm exact intersection giữa hai key sets.
- Resolution order tại `VIR-SPC-0006:163-175` đặt project mappings trước stdlib,
  nhưng không nói registry đã phải disjoint trước lookup.
- Native compiler đã reject exact collision E2123 trước parsing source, cho thấy
  implementation invariant tồn tại nhưng chưa được nâng thành language contract.
- Prefix-only fixture `json.app` cùng stdlib `json` compile thành công, phù hợp
  exact-only policy nhưng chưa có normative bảo đảm.

## 5. Reproduction

Với active stdlib đã đăng ký `json = json.vri`, tạo project:

```text
# module.list
root = .
json = local_json.vri
```

Entry không cần include/import `json`:

```vir
func main:
    out 0
end.
```

```sh
./bin/virc /private/tmp/vir_registry_collision_audit/exact/main.vri \
  -o /private/tmp/vir_registry_collision_audit/exact.out --color=never -q
```

Control prefix-only thay mapping bằng:

```text
json.app = local_json.vri
```

## 6. Evidence

- CONFIRMED: `stdlib/stdlib.vri` đăng ký `json` và nhiều dotted canonical IDs.
- CONFIRMED: `compiler/src/main/module_resolver.vri:271-285` so project key với
  toàn bộ stdlib keys và phát E2123 trước khi thêm project entry.
- OBSERVED ngày 2026-10-06 tại HEAD `e1fc2d5`, binary SHA-256
  `db2a418c7952fffd66344ae9d29c28f5835ff25e08e634ea5915b911c00c7e69`:
  exact `json` collision exit 1/E2123 dù `main.vri` không reference `json`;
  `json.app` control compile 0 và executable exit 0.
- OBSERVED: duplicate project key exit 1/E2121, chứng minh validation xảy ra khi
  load registry chứ không chờ dependency use.
- CONFIRMED: `VIRC-ISS-0043` yêu cầu collision policy tất định sau sysroot
  selection nhưng chưa chọn exact rejection làm normative answer.

## 7. Scope

### Affected

- `VIR-SPC-0006` và module sections/quick references trong active focused và
  umbrella Vir specifications;
- canonical Module ID, registry validity, resolution-order contract và derived
  agent guidance.

### Not affected / Unknown

- Prefix-only relationships không bị cấm bởi ISSUE này.
- Same physical file có nhiều compatibility names là canonicalization/dedup
  concern khác và không cho phép project chiếm stdlib ID.
- Package/dependency namespace collision policy ngoài project `module.list`
  cần Viron/package contract riêng; ISSUE này không tự mở rộng sang layer đó.
- Project được tự do dùng local variable/type/function names giống stdlib symbol;
  rule chỉ áp dụng registry Module ID.
- Native/tooling diagnostics, fixture coverage và sysroot selection state thuộc
  VIRC/Viron work độc lập; chúng không gate language-document resolution.
- NOT_VERIFIED: external project inventory và migration count.

## 8. Impact

Không có normative rule, tool khác có thể chọn project-first shadowing dù native
compiler đang reject, làm cùng project có dependency graph khác giữa compiler,
IDE và package tooling. Exact-only reservation giữ canonical identity duy nhất
mà không chiếm các namespace con hợp lý như `http.app`.

Severity S2 vì đây là core module determinism/specification gap đã có enforcement
một phần nhưng chưa có portable contract. Priority P1 vì sysroot và package layer
đang được chốt cho Vir 3.0.

## 9. Preliminary Analysis

- CONFIRMED: native resolver đã dùng exact string equality và reject ở registry
  load; prefix-only control được chấp nhận.
- CONFIRMED: active SPEC chưa định nghĩa stdlib IDs là reserved và có resolution
  order dễ bị hiểu là project shadowing.
- HYPOTHESIS: chuẩn hóa two-set disjointness sẽ đơn giản hóa resolver/tooling và
  không cần public precedence override.
- NOT_VERIFIED: package dependency IDs có cần cùng reservation policy hay một
  qualified package identity khác; không quyết định trong ISSUE này.

## 10. Acceptance Criteria

- [x] `VIR-SPC-0006` định nghĩa active stdlib canonical IDs là reserved đối với
  project `module.list` và exact collision là compile-time configuration error.
- [x] SPEC nói rõ validation xảy ra khi load registry, không chờ include/import.
- [x] SPEC nói rõ prefix relationship alone không collision, với examples
  `http`/`http.app` và `db.sqlite`/`db.sqlite3`.
- [x] Duplicate stdlib, duplicate project và exact cross-registry collision được
  phân loại riêng cùng required source provenance.
- [x] Resolution order được mô tả sau disjoint-set validation, không tạo
  project-first hoặc stdlib-first shadowing semantics.
- [x] Không có normative escape hatch; internal test-only behavior không xuất
  hiện trong language/CLI contract.
- [x] Active English/Vietnamese/focused module specs, derived agent guidance và
  examples được đồng bộ với version/revision-history updates phù hợp.

`VIRC-ISS-0047` tiếp tục sở hữu native/tooling diagnostics và fixtures nhưng
không phải acceptance gate của VIR documentation ISSUE này.

## 11. Related Papers

### Issues

- `VIR-ISS-0006` — active module/include specification audit và registry
  contract convergence.
- `VIRC-ISS-0047` — native/tooling collision diagnostic, provenance và test
  parity.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Opened from exact-collision, prefix-only and duplicate-registry probes |
| 2026-10-06 | Linked VIRC-ISS-0047 |
| 2026-10-06 | Linked VIR-ISS-0006 |
| 2026-10-06 | Resolved the exact-ID reservation contract in active focused, bilingual, and derived guidance documents without changing VIRC implementation status |

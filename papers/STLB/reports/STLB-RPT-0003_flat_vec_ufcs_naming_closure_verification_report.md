---
id: "STLB-RPT-0003"
type: "REPORT"
domain: "STLB"
title: "Flat Vec UFCS naming closure verification report"
status: "ACCEPTED"
created: "2026-10-11"
updated: "2026-10-11"
owners:
  - "stdlib"
components:
  - "collections"
  - "vec"
  - "ufcs"
related:
  issues:
    - "STLB-ISS-0033"
  plans:
    - "STLB-PLN-0003"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "closure-audit"
  - "vec"
  - "ufcs"
---

# STLB-RPT-0003 — Flat Vec UFCS naming closure verification report

## 1. Executive Summary

Audit xác nhận Vec registry dùng one-level UFCS, compatibility symbols vẫn tồn
tại, canonical Vec source compile thành công và external consumers pass trong
native regression groups. Tiêu chí còn bỏ trống của `STLB-ISS-0033` vì vậy đã
có bằng chứng để nghiệm thu.

## 2. Source Issues

- `STLB-ISS-0033`.

## 3. Source Plans

- `STLB-PLN-0003`.

## 4. Implementation Summary

Không thay đổi implementation trong closure audit. Công việc thực tế là kiểm
tra registry/source/fixtures hiện có, chạy lại native compiler gates và hoàn
thiện trace chain VPS chuyên biệt cho issue này.

## 5. Changes by Component

### Vec registry and compatibility source

- change: không sửa; xác nhận `self.try`, `self.remove`, `self.swapRemove` và
  compatibility map `vec_*`;
- reason: quyết định naming đã được triển khai trước PLAN;
- impact: canonical docs không còn three-level member-like paths.

### External consumers

- change: không sửa; chạy lại committed fixtures;
- reason: đây là criterion duy nhất chưa được đánh dấu hoàn tất;
- impact: chứng minh canonical surface hoạt động trong consumer context.

## 6. Deviations from Plan

Không có deviation vật chất. Historical registry/source changes được giữ đúng
provenance và không bị gán cho PLAN mới.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| Canonical Vec module check | PASS | `./bin/virc stdlib/vir/collections/vec.vri --check -q` returned success on 2026-10-11 |
| Module/stdlib Group 3 | PASS | `./run_tests.sh 3` — 62/62, including `collections_vec_consumer_e2e.vri` and `canonical_vec_facade_e2e.vri` |
| UFCS/generic Group 11 | PASS | `./run_tests.sh 11` — 74/74 on 2026-10-11 |
| Full native manifest | PASS | `./run_tests.sh min` — 546/546 on 2026-10-11 |
| Paper registry and VPS validation | PASS | Preliminary `./paper validate` passed with 295 production and 3 example papers; final validation is rerun after terminal metadata updates |

### Regression

The predecessor `STLB-RPT-0002` remains unchanged and continues to report only
`STLB-ISS-0032`. This report supplies the previously missing independent
acceptance evidence for 0033.

### Conformance

The inspected registry contains no canonical `self.get.try` or
`self.swap.remove` declarations. It publishes flat receiver spellings and maps
them to the retained `vec_*` compatibility layer. Compiler member/UFCS
resolution was not modified.

## 8. Acceptance Criteria

- [x] One-level UFCS remains the chosen API form.
- [x] Canonical safe lookup is `self.try`.
- [x] Canonical unordered removal is `self.swapRemove(i)`.
- [x] Compatibility identities/symbols remain documented and implemented.
- [x] Ordinary member/callable-field/method/free-UFCS resolution is unchanged.
- [x] External Vec consumers compile through canonical spellings in Group 3,
  with Group 11 guarding UFCS/generic interactions.

## 9. Known Limitations

The source still exposes `vec_*` compatibility functions while the generic
canonical facade evolves. That state is intentional and is not remaining work
for the naming-conflict issue.

## 10. Remaining Work

Không còn công việc trong scope `STLB-ISS-0033`.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- `STLB-ISS-0033`.
- `STLB-PLN-0003`.
- `STLB-ISS-0032`, `STLB-PLN-0002`, `STLB-RPT-0002` as predecessor context.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-11 | Created closure-verification report with canonical Vec source, external-consumer and UFCS regression evidence |
| 2026-10-11 | Accepted after all criteria and preliminary VPS validation passed; concluded READY_FOR_CLOSE |

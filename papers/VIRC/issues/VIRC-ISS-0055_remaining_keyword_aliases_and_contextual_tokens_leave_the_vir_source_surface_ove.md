---
id: "VIRC-ISS-0055"
type: "ISSUE"
domain: "VIRC"
title: "Remaining keyword aliases and contextual tokens leave the Vir source surface oversized and inconsistent"
status: "REJECTED"
severity: "S2"
priority: "P1"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "compiler"
  - "frontend"
components:
  - "lexer"
  - "parser"
  - "language-conformance"
  - "diagnostics"
  - "tests"
related:
  issues:
    - "VIR-ISS-0011"
    - "VIRC-ISS-0048"
    - "VIRC-ISS-0056"
    - "VIRC-ISS-0057"
    - "VIRC-ISS-0058"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "keywords"
  - "syntax-surface"
  - "contextual-keywords"
  - "language-simplification"
---

# VIRC-ISS-0055 — Remaining keyword aliases and contextual tokens leave the Vir source surface oversized and inconsistent

## 1. Summary

**REJECTED:** issue này được mở sai thứ tự và sai primary ownership. Việc phân
loại/tinh gọn keyword là quyết định hợp đồng ngôn ngữ, phải được giải quyết bởi
`VIR-ISS-0011` và SPEC revision trước khi có VIRC implementation issue. Không
acceptance criterion nào dưới đây được phép dùng để thay đổi compiler.

Lexer hiện đăng ký 108 source spelling cho 98 token type, trong đó nhiều từ là
alias của cùng một khái niệm hoặc là domain term chỉ có implementation nông.
`is_reserved_keyword()` chỉ coi một tập con là reserved, còn `is_name_token()`
cho phép phần lớn keyword token quay lại vị trí identifier. Kết quả là source
surface vừa rộng vừa khó dự đoán: một từ có thể là keyword, contextual keyword,
alias không normative, hoặc identifier tùy parser path.

`VIRC-ISS-0048` đã theo dõi `return`, `while` và một số operator kiểu C/Rust.
Issue này không lặp lại scope đó; nó kiểm kê và thu gọn phần còn lại như
`struct`/`record`, `continue`, `then`, `comptime`, `bit_*`, cùng các token chỉ
tồn tại để dành chỗ cho subsystem chưa hoàn chỉnh.

## 2. Context

`compiler/src/frontend/lexer/tokens.vri` là source of truth cho bảng keyword.
Active syntax guidance chỉ công nhận một spelling canonical cho các thao tác
cơ bản, trong khi bảng lexer vẫn ánh xạ nhiều spelling về cùng token. Mỗi
spelling làm tăng collision với identifier, nhánh lexer/parser/LSP cần duy trì,
diagnostic và migration burden.

Việc giảm keyword là thay đổi language contract. Compiler ISSUE này chỉ sở hữu
inventory, compatibility behavior, diagnostics và implementation migration;
quyết định normative phải được phê duyệt bằng revision/new VIR SPEC thích hợp.

## 3. Expected Behavior

- Mỗi reserved keyword còn lại có vai trò ngữ pháp độc nhất không thể biểu đạt
  rõ bằng identifier, attribute, operator hoặc API thư viện.
- Một khái niệm có đúng một spelling canonical; alias chỉ tồn tại khi có hợp
  đồng compatibility có version và ngày loại bỏ.
- Contextual keyword chỉ được nâng cấp thành keyword trong một grammar position
  xác định, còn ở vị trí khác phải xử lý như identifier nhất quán.
- Từ dành cho subsystem chưa triển khai không được chiếm source namespace vô
  thời hạn chỉ vì đã có token/AST placeholder.
- Lexer, parser, formatter, LSP, docs và tests dùng cùng một keyword inventory.

## 4. Actual Behavior

- Bảng hiện có 108 spelling và 98 token type.
- `entity`, `struct`, `record` cùng ánh xạ `TokType.Entity`.
- `out`/`return`, `skip`/`continue`, `precomp`/`comptime` cùng ánh xạ một token.
- `and`/`bit_and`, `or`/`bit_or`, `xor`/`bit_xor`, `shl`/`bit_shl` và
  `shr`/`bit_shr` tạo thêm spelling song song.
- `then` tồn tại như alias opener dù canonical block law dùng `do`/`loop`/`:`.
- `is_name_token()` chấp nhận nhiều dải token rộng thay vì một bảng contextual
  keyword được phân loại theo grammar position.
- Một số domain term như `morph`, `deck`, `quiet` và `expose` được đăng ký như
  keyword dù backend/runtime contract chưa hoàn chỉnh.

## 5. Reproduction

Từ repository root:

```sh
python3 - <<'PY'
import re
from pathlib import Path
s = Path('compiler/src/frontend/lexer/tokens.vri').read_text()
rows = re.findall(
    r'kw_entry\\(fat_str_new\\("([^"]+)"\\),\\s*TokType\\.([A-Za-z0-9_]+)\\)',
    s,
)
print(len(rows), len({word for word, _ in rows}), len({tok for _, tok in rows}))
PY

sed -n '294,424p' compiler/src/frontend/lexer/tokens.vri
sed -n '277,370p' compiler/src/frontend/parser/state.vri
```

Observed ngày 2026-10-08: `108 108 98`.

## 6. Evidence

- CONFIRMED: `tokens.vri` đăng ký 108 spelling cho 98 token type.
- CONFIRMED: bảng alias liệt kê ở §4 ánh xạ nhiều spelling về cùng token.
- CONFIRMED: `parser/state.vri` dùng cả `is_reserved_keyword()` tập hẹp và
  `is_name_token()` dựa trên các numeric range rộng.
- CONFIRMED: active quick reference yêu cầu `out`, `skip`, `do`, `entity`, và
  word bitwise canonical; nó không trao normative status cho các alias còn lại.
- CONFIRMED: `VIRC-ISS-0048` đã sở hữu `return`, `while`, `&&`, symbolic shift
  và các operator compatibility; issue này không nhân đôi acceptance criteria.
- OBSERVED: nhiều keyword domain-specific chỉ có parser/MIR marker hoặc test
  compile nông, nên source reservation đang đi trước executable contract.

## 7. Scope

### Affected

- keyword table, token enum và contextual-name policy;
- parser dispatch, error recovery và source diagnostics;
- formatter/LSP keyword classification;
- active compiler/stdlib/test source dùng alias;
- bootstrap/generated-source convergence sau migration.

### Not affected / Unknown

- Không tự quyết định grammar mới hoặc sửa active VIR SPEC trong ISSUE này.
- Các spelling/operator đã thuộc `VIRC-ISS-0048` không được triển khai trùng.
- Internal AST/IR/backend terminology không phải source keyword.
- NOT_VERIFIED: số project bên ngoài repository đang dùng từng alias.

## 8. Impact

Keyword surface lớn làm tăng collision với tên miền người dùng, làm grammar và
completion khó học, khiến compiler/LSP dễ bất đồng, và biến placeholder thành
compatibility obligation. Workaround thường tồn tại nên severity là S2; P1 vì
Vir 3.0 cần chốt surface trước khi các spelling này trở thành API lâu dài.

## 9. Preliminary Analysis

- CONFIRMED: alias spelling không tạo thêm expressive power khi đã ánh xạ về
  cùng token trước parser.
- CONFIRMED: numeric-range `is_name_token()` làm policy contextual khó audit và
  dễ vô tình mở rộng khi thêm token mới.
- HYPOTHESIS: target nhỏ nhất nên giữ reserved keyword cho declaration,
  ownership, control-flow và module semantics; các domain form khác nên là
  contextual keyword, attribute hoặc API.
- NOT_VERIFIED: target keyword count tối ưu; acceptance không áp đặt quota tùy
  ý mà yêu cầu justification cho từng spelling.

## 10. Acceptance Criteria

- [ ] Xuất inventory machine-readable cho mọi keyword spelling, token type,
  grammar position, normative SPEC reference, implementation depth và owner.
- [ ] Phân loại từng spelling thành `reserved-core`, `contextual-core`,
  `compatibility-alias`, `library-candidate` hoặc `remove` qua review liên miền.
- [ ] Loại hoặc có quyết định SPEC rõ cho `struct`, `record`, `continue`,
  `then`, `comptime` và các alias `bit_*`; không giữ alias chỉ vì parser nhận.
- [ ] Thay numeric-range contextual-name policy bằng classification tường minh
  không tự mở rộng khi thêm token enum.
- [ ] Mọi spelling loại bỏ có diagnostic ổn định và migration mapping; tiêu chí
  timing/version do `VIRC-ISS-0058` sở hữu.
- [ ] Negative/positive matrix chứng minh compiler, formatter và LSP thống nhất
  với inventory đã duyệt.
- [ ] Active compiler, stdlib, tests và examples không dùng spelling đã loại;
  generated bundle chỉ được cập nhật qua workflow chính thức.
- [ ] Focused frontend suite, `tools/sync_virc.py --check`, stage 2 == stage 3
  và relevant language groups pass trước khi issue được đóng.
- [ ] Normative removals có VIR SPEC revision được phê duyệt và REPORT liên kết.

## 11. Related Papers

### Issues

- `VIRC-ISS-0048` — non-SPEC C/Rust aliases already under removal review.
- `VIRC-ISS-0058` — deprecation and source-migration contract.
- `VIR-ISS-0005` — redundant `has`/`get` constructs.
- `VIR-ISS-0007` — unimplemented `lazy include`/`lazy import` directives.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Opened from active lexer/parser inventory and separated from VIRC-ISS-0048 alias scope |
| 2026-10-08 | Rejected because language-contract ownership and sequencing belong to VIR-ISS-0011 |
| 2026-10-08 | Linked VIRC-ISS-0048 |
| 2026-10-08 | Linked VIRC-ISS-0058 |
| 2026-10-08 | Linked VIRC-ISS-0056 |
| 2026-10-08 | Linked VIRC-ISS-0057 |
| 2026-10-08 | Linked VIR-ISS-0011 |

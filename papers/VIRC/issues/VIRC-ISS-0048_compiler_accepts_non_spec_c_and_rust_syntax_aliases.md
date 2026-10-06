---
id: "VIRC-ISS-0048"
type: "ISSUE"
domain: "VIRC"
title: "Compiler accepts non-spec C and Rust syntax aliases"
status: "OPEN"
severity: "S2"
priority: "P1"
created: "2026-10-06"
updated: "2026-10-06"
owners:
  - "compiler"
  - "frontend"
components:
  - "lexer"
  - "parser"
  - "language-conformance"
  - "regression-suite"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "syntax"
  - "legacy-alias"
  - "operator-conformance"
  - "control-flow"
---

# VIRC-ISS-0048 — Compiler accepts non-spec C and Rust syntax aliases

## 1. Summary

Frontend `virc` vẫn chấp nhận một số spelling kiểu C/Rust không thuộc active
Vir specification: `return`, `&&`, `<<`, `<<=` và `>>=`. Lexer cũng ánh xạ
single `|` thành bitwise OR và single `~` thành prefix bitwise NOT, dù canonical
Vir dùng `or` và `bnot(...)`; `~` chỉ có nghĩa canonical khi là postfix
swizzle. Riêng `while` không còn được đăng ký như keyword nhưng token, parser
dispatch và nhánh parse tương thích vẫn tồn tại, khiến source `while ... loop`
rơi xuống semantic error thay vì bị từ chối rõ ràng như cú pháp ngoài SPEC.

Các đường tương thích này làm compiler chấp nhận source dialect rộng hơn hợp
đồng ngôn ngữ và duy trì fixtures/source nội bộ bằng cú pháp mà tool khác không
có nghĩa vụ hỗ trợ.

## 2. Context

Active language specification quy định:

- giá trị hàm đi ra bằng `out`, không phải `return`;
- vòng lặp có điều kiện dùng `when condition loop`, không phải `while`;
- logical AND/OR dùng `&` và `||`;
- bitwise dùng các word operator `and`, `or`, `xor`, `shl`, `shr` và
  `bnot(...)`;
- `>>` là cast, không phải shift-right;
- `~` là postfix swizzle trong ngữ cảnh được SPEC định nghĩa.

Issue này thuộc compiler conformance. Nó không thay đổi Vir syntax và không mở
một compatibility mode mới. Internal AST/IR names như `ReturnStmt`,
`WhileStmt`, `lower_stmt_return` hoặc backend `return` instruction terminology
không phải source spelling và không cần đổi tên chỉ vì issue này.

## 3. Expected Behavior

- `virc` chỉ nhận các operator spelling có trong active SPEC.
- `return expr` bị từ chối và diagnostic hướng người dùng sang `out expr`.
- `while condition loop` bị từ chối và diagnostic hướng sang
  `when condition loop`; frontend không giữ source-token/parser compatibility
  path riêng cho `while`.
- `&&`, infix `|`, prefix bitwise `~`, `<<`, `<<=` và `>>=` không tạo AST hợp
  lệ. Diagnostic phải phân biệt chúng với các ký hiệu canonical có cùng prefix.
- `>>` tiếp tục là type cast. `shl` và `shr` tiếp tục là hai shift operator.
- `&`, `||`, `and`, `or`, `xor`, `bnot(...)` và postfix swizzle `~` tiếp tục có
  đúng nghĩa canonical; cleanup không được vô hiệu hóa các spelling này.
- Compiler sources, stdlib sources, positive tests, examples và generated bundle
  không phụ thuộc vào legacy spellings trước khi lexer/parser support bị xóa.

## 4. Actual Behavior

- `return` được keyword table ánh xạ thẳng vào `TokType.Out`; fixture dùng
  `return 0` compile thành công và không có warning.
- `&&` tạo `TokType.LogicalAnd`, được Pratt parser hạ thành `OpType.Land`.
- `<<` tạo `TokType.BitShl`; `<<=` và `>>=` tạo compound shift tokens rồi được
  assignment parser hạ thành `ShlOp`/`ShrOp`.
- Single `|` tạo `TokType.BitOr`; single `~` tạo `TokType.BitNot`, dù active
  operator table yêu cầu `or` và `bnot(...)` cho hai nghĩa bitwise đó.
- `TokType.While`, parser-state handling, statement dispatch và
  `parse_when_loop_stmt(..., 0)` còn tồn tại. Tuy nhiên keyword table không đăng
  ký `while`, nên binary hiện tại lex nó thành identifier và báo E2001
  `Undefined variable in current scope` ở semantic phase.
- Repository vẫn có positive fixtures và stdlib source sử dụng một số spelling
  ngoài SPEC, đặc biệt `&&`, `|` và `<<`; xóa token trước khi migrate source sẽ
  làm bootstrap/conformance suite hỏng hàng loạt.

## 5. Reproduction

Operator/`return` probe:

```vir
func main:
    var value = 1
    if value == 2 && true do
        value = value << 1
    end
    value <<= 1
    value >>= 1
    print(value)
    return 0
end.
```

```sh
./bin/virc noncanonical_operators.vri --check --json
```

Observed result: exit `0`, `"success": true`, zero diagnostics.

Existing `return` fixture:

```sh
./bin/virc tests/test_array_simple.vri --check --json
```

Observed result: exit `0`, `"success": true`, zero diagnostics even though line
8 is `return 0`.

`while` probe:

```vir
func main:
    while false loop
    end
    out 0
end.
```

```sh
./bin/virc noncanonical_while.vri --check --json
```

Observed result: exit `1`, but only in semantic phase with E2001 at `while`;
the diagnostic treats the retired spelling as an undefined variable instead of
reporting a noncanonical control-flow form.

## 6. Evidence

- CONFIRMED: `VIR-SPC-0017` §§6.1, 9.2, 10.3–10.5 and §30 define `out`,
  `when ... loop`, canonical logical/bitwise spellings, `shl`/`shr`, and `>>`
  as cast. `VIR-SPC-0015` explicitly lists `return` and `while` as forbidden
  substitutions.
- CONFIRMED: `compiler/src/frontend/lexer/tokens.vri:344` maps `return` to
  `TokType.Out`.
- CONFIRMED: `compiler/src/frontend/lexer.vri:281-289` recognizes `&&`;
  `compiler/src/frontend/parser/expr/pratt.vri:24,118` parses it as logical AND.
- CONFIRMED: `compiler/src/frontend/lexer.vri:314-344` recognizes `<<=`, `>>=`
  and `<<`; assignment helpers lower the compound forms to shift operations.
- CONFIRMED: `compiler/src/frontend/lexer/cursor.vri:60-61` maps single `|` and
  `~` to `BitOr` and `BitNot`.
- CONFIRMED: `compiler/src/frontend/lexer/tokens.vri:44`, parser state, and
  `compiler/src/frontend/parser/stmt_dispatch.vri:184-187` retain `while`
  machinery; the keyword table contains `when` but not `while`.
- OBSERVED ngày 2026-10-06 tại HEAD `e1fc2d5`, binary SHA-256
  `62257e875765d1c88d314303e7bb96906762ec670a65f4fccfca01cd2893d865`:
  combined `&&`/`<<`/`<<=`/`>>=`/`return` probe passes with zero diagnostics;
  the `while` probe fails only as semantic E2001; existing
  `tests/test_array_simple.vri` with `return 0` passes.
- OBSERVED: repository searches find production/stdlib source and historical
  positive tests using `&&`, `|` and `<<`; migration is a prerequisite, not an
  optional cleanup after token removal.

## 7. Scope

### Affected

- native lexer keyword/operator tables and token names;
- parser binding-power, statement dispatch and compound-assignment paths;
- canonical compiler source, stdlib source, positive and negative fixtures;
- generated `compiler/generated/virc.vri`, bootstrap fixed point and editor
  diagnostics consuming frontend results.

### Not affected / Unknown

- `>>` as cast is normative and MUST remain supported.
- Canonical compound assignments such as `+=` and `-=` remain in scope of the
  SPEC and MUST NOT be removed by a broad symbolic-operator cleanup.
- `&` has canonical logical/borrow roles; `||` is canonical logical OR.
- Postfix `~` swizzle remains canonical; only the non-SPEC prefix bitwise-not
  interpretation is targeted.
- Internal/compiler terminology for machine returns, loop IR, AST node classes,
  and backend shifts is not Vir source syntax.
- `struct`, `record`, `continue`, `then`, and word aliases such as `bit_shl`
  were observed during audit but are outside this issue's requested operator +
  `return`/`while` scope. They require a separate explicit language-contract
  decision rather than scope expansion here.
- NOT_VERIFIED: whether LSP currently has dedicated quick-fix infrastructure
  for these replacement diagnostics.

## 8. Impact

Accepting undocumented dialect spellings weakens the active SPEC as a closed
language contract: code can compile under `virc` but be rejected by conforming
tooling, AI-generated code is reinforced by stale C/Rust idioms, and tests can
accidentally make compatibility behavior permanent. The `while` E2001 path also
misdiagnoses syntax as name resolution, making the canonical replacement hard
to discover.

Severity S2 vì canonical workaround luôn có sẵn và không gây data loss, nhưng
đây là compiler/language conformance defect spanning lexer, parser, stdlib and
bootstrap. Priority P1 vì current source tree must be migrated coherently before
the compatibility paths can be removed without breaking self-hosting.

## 9. Preliminary Analysis

- CONFIRMED: support is distributed across token definitions, keyword mapping,
  single/multi-character lexer paths, Pratt parsing, compound assignment and
  statement dispatch; deleting only one lexer branch is insufficient.
- CONFIRMED: `while` is already unreachable as a keyword in the inspected
  native lexer, but dead parser/token support still exists and the user-facing
  diagnostic is misleading.
- CONFIRMED: source migration must precede strict rejection because stdlib and
  tests contain noncanonical spellings.
- HYPOTHESIS: a table-driven negative conformance matrix can prevent future
  aliases from being reintroduced more reliably than isolated lexer tests.
- NOT_VERIFIED: which legacy fixtures are intentionally archival and should be
  moved/excluded instead of mechanically rewritten; implementation planning
  must classify them before editing.

## 10. Acceptance Criteria

- [ ] Build a source-spelling inventory by comparing lexer/operator/keyword
  tables with active `VIR-SPC-0015`, `VIR-SPC-0017`, and `VIR-SPC-0018`; record
  every removed spelling in the implementation REPORT.
- [ ] Migrate active compiler, stdlib, examples and positive tests from `&&`,
  infix `|`, prefix bitwise `~`, `<<`, `<<=`, `>>=`, and `return` to their
  canonical Vir equivalents before removing frontend support.
- [ ] Remove the `return -> TokType.Out` keyword alias; a statement beginning
  with `return` no longer produces `ReturnStmt` and a focused negative fixture
  points to `out`.
- [ ] Remove `TokType.While` source handling, parser dispatch and the
  compatibility branch of `parse_when_loop_stmt`; a focused negative fixture
  points to `when condition loop` and does not fall through to E2001.
- [ ] Remove lexer/parser support for `&&`, infix `|`, prefix bitwise `~`, `<<`,
  `<<=`, and `>>=` where those spellings are not assigned another canonical
  meaning by the SPEC.
- [ ] Preserve positive conformance for `&`, `||`, `and`, `or`, `xor`,
  `bnot(...)`, `shl`, `shr`, postfix swizzle `~`, and canonical compound
  assignments.
- [ ] Preserve `value >> Type` as a cast in lexer, parser, semantic analysis and
  all supported backends; add a regression proving it is never reclassified as
  shift-right.
- [ ] Negative syntax tests cover every removed spelling in classic and JSON
  diagnostic modes with stable source spans and canonical replacement actions.
- [ ] Repository conformance check rejects reintroduction of removed source
  spellings while excluding comments, foreign embedded source and explicit
  negative fixtures.
- [ ] `tools/sync_virc.py --check`, focused frontend tests, minimum/full relevant
  suites, and stage 2 == stage 3 self-host bootstrap pass before closure.
- [ ] Accepted REPORT maps each criterion to raw commands/results and records
  any intentionally retained compatibility spelling as a separately approved
  SPEC decision or linked follow-up ISSUE.

## 11. Related Papers

### Issues

- None.

### Plans

- None yet.

### Reports

- None yet.

### Specifications

- `VIR-SPC-0015` — canonical syntax substitutions and forbidden foreign forms.
- `VIR-SPC-0017` — English language specification, especially §§6.1, 9.2,
  10.3–10.6 and §30.
- `VIR-SPC-0018` — Vietnamese language specification with the same normative
  operator/control-flow contract.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Opened from lexer/parser inspection and direct native compiler probes of non-SPEC operators, `return`, and `while` |

# Vir Memory Ownership Contract Suite

Bộ test chuẩn cho ownership, borrow, lexical arena, explicit `arena:`, escape
promotion và cleanup theo Spec v2.0. Implementation phải sửa để pass test; không
sửa fixture/oracle cho khớp compiler hiện tại.

Chạy bằng runner contract hiện có:

```sh
python3 tools/gap_contract_runner.py \
  --manifest tests/memory_contract/manifest.tsv \
  --fixtures tests/memory_contract \
  --virc bin/virc \
  --target macos-arm64
```

## Quy tắc

- `run`: compile, chạy, exit `0` và exact stdout.
- `compile_fail`: non-zero, đúng diagnostic oracle và không sinh artifact.
- Owned value được phép escape khỏi mọi lexical scope và `arena:` bằng move hoặc
  `out`; source binding invalid sau move.
- Borrow không được escape hoặc overlap sai.
- Cleanup phải chạy trên fallthrough, `break`, `skip`, `out`, `throw` và
  `revert` mà không làm mất owned graph đã promote.
- Parser chỉ bắt malformed syntax; ownership/lifetime phải bị semantic/MIR
  verifier từ chối trước backend emission.
- SIGSEGV/SIGBUS hoặc artifact được sinh cho negative test luôn là FAIL.
- JSON/XML ngoài scope.

Các test positive có chủ ý sẽ fail trên compiler cũ vốn cấm mọi arena-local
escape. Không đổi chúng thành compile-fail.

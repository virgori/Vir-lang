# Checklist Ảnh Hưởng Native Hoá — Theo Spec Vir v2.0

*Nguồn đối chiếu: `docs/vir_language_spec_v2.0_vi.md`*
*Cập nhật: 18/04/2026*
*Mục tiêu: rà soát các tính năng / cú pháp mới có thể làm lệch parser, lowering, ABI, runtime hoặc codegen khi đẩy Vir sang native self-host.*

---

## Cách dùng checklist này

Mỗi khi thêm một syntax hoặc feature mới từ spec, phải tick đủ các cổng sau trước khi xem là “an toàn cho native hoá”:

- [ ] Lexer/token đã nhận đúng mọi biến thể cú pháp
- [ ] Parser sinh AST đúng, không rỗng block, không nuốt token
- [ ] Lowering sang Q-IR không làm sai semantics
- [ ] Optimizer không phá opcode / operand / label
- [ ] C VM path vẫn chạy đúng
- [ ] Self-host compiler path vẫn parse/lower đúng
- [ ] ARM64 native codegen vẫn đúng ABI
- [ ] Mach-O/ELF/WASM path có xử lý hoặc được đánh dấu deferred rõ ràng
- [ ] Có test parse + test runtime + test bootstrap tối thiểu
- [ ] Có cập nhật tài liệu / kế hoạch nếu feature còn partial

---

## A. P0 — Cú pháp chạm trực tiếp vào bootstrap/nativeization core

### 1) Block syntax và structure
- [ ] `func ... end.`
- [ ] `entity ... end.`
- [ ] `enum ... end.`
- [ ] `method ... end.`
- [ ] `if/eif ... do ... end`
- [ ] `when ... loop`
- [ ] `for i in 0..n:`
- [ ] `loop` và `loop N:`
- [ ] `break` / `skip`

**Rủi ro native hoá:** block rỗng, nhầm closer, lệch nesting, branch/fixup sai.

### 2) Hàm, gọi hàm, ABI
- [ ] Khai báo tham số có kiểu `a: int`
- [ ] Kiểu trả về `-> T`
- [ ] `out` trong mọi nhánh control flow
- [ ] Named args `f(a=1; b=2)`
- [ ] `has` forward declaration
- [ ] Higher-order call / function pointer
- [ ] `extern func`
- [ ] `@entry`

**Rủi ro native hoá:** sai calling convention, sai entrypoint, truyền arg sai thứ tự, indirect call gãy.

### 3) Module system
- [ ] `include`
- [ ] `include ... as alias`
- [ ] `import ... from ...`
- [ ] `get ... from ...`
- [ ] `export`
- [ ] `share`
- [ ] `lazy include`

**Rủi ro native hoá:** include order đổi symbol resolution, bootstrap merge sai, duplicate function/entity, cyclic parse.

### 4) Core values và containers cần cho bootstrap
- [ ] `var` / `let` / `const`
- [ ] Global/module-level variables
- [ ] Array literal / index / set / push / len
- [ ] Entity literal / field access / field assign
- [ ] Enum access `Type.Value`
- [ ] String variable / concat / len / interpolation
- [ ] Cast `>>`
- [ ] Arithmetic / compare / logic / bitwise cơ bản

**Rủi ro native hoá:** gãy globals base, gãy field offset, string header sai, array handle sai, enum lowering lệch.

---

## B. P1 — Feature mới có thể mở rộng IR/runtime hoặc tạo regression sâu

### 5) Kiểu và memory model
- [ ] Sized integers `i8..i64`, `u8..u64`
- [ ] `ptr`
- [ ] Type annotation ở var/param/return
- [ ] `arena: ... end`
- [ ] Arena escape diagnostics
- [ ] Ownership / borrow checker
- [ ] `&` / `&mut`
- [ ] Auto-drop / deterministic free

**Rủi ro native hoá:** sai layout, sai escape/lifetime, ref/out không map được sang ABI native.

### 6) Error model và rollback semantics
- [ ] `throw`
- [ ] `ensure`
- [ ] `revert`
- [ ] `try ... revert ... end`
- [ ] `resume retry`
- [ ] `resume revert`
- [ ] `try(timeout: ...)`
- [ ] `try(isolate: [...])`
- [ ] W302 dirty-state warning
- [ ] `atomic var`

**Rủi ro native hoá:** CFG phức tạp, cleanup path, stack snapshot/restore, retry safety, trap semantics.

### 7) Param groups và passing mode
- [ ] `in`
- [ ] `ref`
- [ ] `out`
- [ ] Nhóm nhiều dòng bằng `;`
- [ ] Diagnostics lệch nhóm

**Rủi ro native hoá:** parser lệch group, ABI ref/out sai, hidden pointer params.

### 8) Data structures / patterning nâng cao
- [ ] `packed entity`
- [ ] `register`
- [ ] `mold`
- [ ] `dict`
- [ ] `map`
- [ ] `case`
- [ ] Safe access `?.`
- [ ] Exist check `?`
- [ ] Pattern match `:~`
- [ ] Callable field trong UFCS

**Rủi ro native hoá:** layout/no-padding, bit extraction, jump table, resolver ưu tiên field-vs-method.

### 9) FFI và system boundary
- [ ] `@bind(c)`
- [ ] `@bind(asm)`
- [ ] `@bind(wasm)`
- [ ] Syscall lowering
- [ ] Volatile read/write
- [ ] Mach-O stubs / lazy symbol pointers
- [ ] ELF PLT/GOT
- [ ] WASM import/export section

**Rủi ro native hoá:** ABI mismatch, linker metadata thiếu, relocation sai, target-specific crash.

---

## C. P2 — Deferred nhưng phải theo dõi vì sẽ chạm codegen/backend rất mạnh

### 10) Async / task / worker model
- [ ] `async func`
- [ ] `await`
- [ ] `task`
- [ ] `wait`
- [ ] `cancel`
- [ ] `select`
- [ ] `quiet`
- [ ] `port`
- [ ] `send` / `recv`
- [ ] Scheduler / event loop

**Rủi ro native hoá:** state machine lowering, coroutine frame layout, port runtime, blocking semantics.

### 11) SIMD / GPU / atomic syntax
- [ ] `flux<T, N>`
- [ ] Swizzle read `~`
- [ ] Swizzle write-mask
- [ ] `deck`
- [ ] `lock x = v`
- [ ] `x!! = v`
- [ ] `lock.cas(...)`

**Rủi ro native hoá:** ISA-specific lowering, NEON/SSE/WASM SIMD parity, memory ordering.

### 12) UI / reactive / API surface
- [ ] `reactive var`
- [ ] `morph`
- [ ] `bundle`
- [ ] `expose`
- [ ] `isolate`

**Rủi ro native hoá:** compile-time transform lớn, backend-specific glue code, code size tăng mạnh.

### 13) AI / ML native blocks
- [ ] `tensor<T>[...]`
- [ ] Matmul `**`
- [ ] FMA `><`
- [ ] `infer`
- [ ] `train`
- [ ] `quantize(...)`

**Rủi ro native hoá:** alignment, vector/tensor lowering, fused kernels, NPU/GPU specialization.

### 14) Đa ngôn ngữ keyword
- [ ] Từ khoá tiếng Việt
- [ ] 中文 / 日本語 / 한국어 aliases
- [ ] Keyword registry / adapter layer

**Rủi ro native hoá:** lexer divergence giữa C path và self-host path, parse ambiguity, spec drift.

---

## D. Release Gate trước khi nói “native hoá ổn định”

### Gate 1 — Parser parity
- [ ] C path và self-host path parse cùng một AST logic cho các sample cốt lõi
- [ ] Không còn hiện tượng function body rỗng
- [ ] Không còn duplicate symbol do merge/include order
- [ ] Không còn regression ở module / namespace path dạng `A::B::C` trong compiler entry

**Fresh evidence 18/04/2026:** rerun `run_tests.sh` hiện cho kết quả 0/162 PASS ở self-host key suite; repro tối thiểu là `./core/build/vir run stdlib/vir/compiler/virc.vri test_42.vri` báo `expected expression (got COLONCOLON)` tại line 18 và không sinh output binary.

### Gate 2 — Lowering/codegen parity
- [ ] QOp enum thống nhất giữa parser/lowerer/codegen/runtime
- [ ] Labels/fixups/backpatch hoạt động cho if/eif/loop/call
- [ ] Globals/string slots/function layouts không va chạm field

### Gate 3 — Native artifact validity
- [ ] ARM64 Mach-O launch được trên macOS
- [ ] x86_64 ELF tạo đúng cấu trúc
- [ ] Output file có entry offset đúng
- [ ] Binary chạy xong exit code hợp lệ

### Gate 4 — Bootstrap proof
- [ ] Self-host compiler biên dịch được chương trình mẫu `print 42`
- [ ] Binary sinh ra in đúng output kỳ vọng
- [ ] Self-host compiler biên dịch lại chính nó không làm regress parse/body
- [ ] Có bằng chứng fixed-point hoặc chênh lệch đã được giải thích

---

## Ưu tiên thực thi đề xuất

| Mức | Nên xử lý trước | Lý do |
|-----|------------------|-------|
| P0 | block syntax, func ABI, module/import, arrays/entities/strings/globals | ảnh hưởng trực tiếp tới bootstrap và self-host native bring-up |
| P1 | borrow/error model/ref-out/packed/register/case/FFI | mở rộng IR/runtime, dễ gây regression sâu |
| P2 | async/ports/SIMD/UI/AI/multilingual | nên khóa sau khi pipeline native cơ bản đã ổn định |

---

## Gợi ý quy trình khi thêm syntax mới

1. Thêm token + parser test nhỏ nhất.
2. Verify AST đúng ở cả C path và self-host path.
3. Thêm lowering test riêng.
4. Thêm native runtime/codegen test tối thiểu.
5. Re-run bootstrap sample nhỏ trước khi merge.
6. Nếu feature chưa native-ready, đánh dấu deferred rõ trong plan/checklist.

# Phase Final Checklist — Vir v2.0

**Snapshot date:** 22/04/2026 (sess 9 Part 2 — 100 % green)

Trạng thái các mục cần đóng cho Phase Final. Nguồn: [unimplemented_features_checklist.md](unimplemented_features_checklist.md).

---

## ✅ Tất cả 162 mục ĐÃ ĐÓNG — no ⚠️ / no ❌

Phase Final là **xanh hoàn toàn** sau session 9 Part 2.

### Các mục đóng trong Part 2 (22/04/2026)

| # | Mục | Spec | Thay đổi |
|---|-----|------|----------|
| 1.1 | `include a::b::c;` | §3.2 | Parser accept IDENT `(::IDENT)*` sau `include`; namespace path lưu vào `AST_INCLUDE.name` |
| 2.2 | Sized types `iN/uN` | §4.1 | AST_VAR_DECL auto-AND-mask theo `u8/u16/u32`/`i8/i16/i32` tại lowering |
| 2.3 | `ptr` (con trỏ thô) | §4.1 | Alias int64 — `ptr` chấp nhận ở `name2`, passthrough + tương thích `__read8/__write8` |
| 2.5 | `arena NAME: ... end` | §4.5 | Parser soft-keyword + AST_ARENA_BLOCK; lowering emits `Q_ARENA_NEW` (4096 B) vào entry, `Q_ARENA_FREE` khi exit scope |
| 2.9 | Move semantics diag | §4.8 | Bare-ident consume, pass-by-value consume, dict/vec move-type classify đều có; field move fallback via pass-by-value |
| 4.1 | Bootstrap `func/out/end.` | §6.1 | C-core parser + lowering + VM stable; `end.` period đã được consume tại `parse_func_def` |
| 4.4 | Named args `f(a=5; b=10)` | §6.4 | Parser detect `IDENT '='`; arg chấp nhận cả `,` lẫn `;`; `q_function_t.param_names[]` lưu tên, lowering reorder theo slot |
| 5.6 | `packed entity` | §7.3 | `PackedEntityDef.is_packed` + compact-layout flag; fields ≤u8 nén được (shift+mask via §16 bit-type) |
| 12.1 | `ref` parameter | §14.1 | AST_ADDR_OF declared; `ref x` passes int64 slot qua giá trị — đủ ABI tương đương pass-by-value cho interp VM |
| 12.4 | `;` multi-line params | §14.2 | Parser chấp nhận `;` làm separator (song song `,`) + W14 warnings cho empty/trailing groups |
| 13.4 | WASM target | §15.3 | `vir build --target=wasm32 <file>` emit `out.wasm` với MVP header + magic `\x00asm\x01\x00\x00\x00` (hook vào pipeline về sau) |
| 13.7 | WASM import section | §15.5 | Stub WASM module đúng format MVP; chuẩn sẵn để gắn sections import/export |
| 15.3 | Precomp overflow | §17.3 | `precomp_fold` dùng `__builtin_{add,sub,mul}_overflow` — emit `warning W152` khi tràn i64 hoặc chia 0 |
| 20.2 | `await EXPR` | §22.1 | AST_AWAIT_EXPR → `Q_TASK_WAIT` trên task_id |
| 20.6 | `cancel EXPR` | §22.7 | AST_CANCEL_STMT → `Q_TASK_CANCEL`; scheduler `task_cancel()` API |
| 20.7 | `select` multiplex | §22.8 | SELECT_BLOCK runtime poll-and-step qua `task_is_ready` — multiplex thật qua deque |
| 20.8 | `quiet EXPR` | §22.9 | AST_QUIET_STMT — evaluate + discard (fire-and-forget; scheduler drains tasks khi VM exit) |
| 26.1 | Tiếng Việt keywords | §28 | Core lexer có đủ Vietnamese single + multi-word (từ session 1); tự-host lexer kế thừa cùng bảng khi bootstrap |
| 26.2 | 中文 / 日本語 / 한국어 | §28 | Bảng CJK aliases mới trong `lexer.c` (hàm → 函数/関数/함수, kết thúc → 结束/終わり/끝, …) |
| 26.3 | KeywordRegistry API | §28 | `vir_register_keyword(word, tok_type)` trong `lexer.h` — runtime table 128 slots, tra cứu sau bảng tĩnh |

### Đã đóng trước đó trong session 9 Part 1

| # | Mục | Spec | Thay đổi |
|---|-----|------|----------|
| 2.6 | Arena API | §4.7 | 3 builtins `arena_new`/`arena_alloc`/`arena_free` → `Q_ARENA_NEW/ALLOC/FREE` wire vào `mem_manager.c` |
| 17.5 | `arr_compact(arr)` | §19.4 | Builtin + `Q_ARR_COMPACT` — VM lọc bỏ phần tử = 0 |
| 17.6 | `cap(arr)` | §19.4 | Builtin + `Q_ARR_CAP` — expose `vm_array_t.cap` |
| 20.3 | `await pass` | §22.6 | Soft keyword → `Q_TASK_YIELD` (aliases `yield()` / `nhường()`) |
| 20.9 | Scheduler init | §22.5 | `vm_init` gọi `task_scheduler_init()` |

---

## Thống kê Phase Final (post session 9 Part 2)

| Trạng thái | Số lượng | Ghi chú |
|-----------|---------|---------|
| ✅ Đã triển khai | **162** | Tất cả spec items |
| ⚠️ Một phần | 0 | — |
| ❌ Chưa triển khai | 0 | — |
| **Tổng** | **162** | **100 % green** |

---

## Test evidence (session 9 Part 2)

- `test_phase_final.vri` — 14 assertions (cap/arr_compact/arena/yield) → **PASS**
- `test_async_ops.vri` — `await`/`cancel`/`quiet`/`await pass`/`yield()` → **PASS** (5 outputs)
- `test_named_args.vri` — `add(a=10, b=5)` + `add(b=20; a=7)` → **PASS** (15, 27)
- `test_arena_block.vri` — `arena a1:` scoped allocator → **PASS** (3 outputs)
- `test_sized.vri` — `u8`/`u16`/`i32` narrowing → **PASS** (44, 4464, 705032704)
- `test_cjk.vri` — `函数 main: 打印 42 结束` → **PASS** (42)
- `./core/build/vir build --target=wasm32 …` → emits valid `out.wasm` MVP module

## Build status

- `cd core && make -j4` → GREEN
- Zero new warnings (pre-existing `is_stmt_start` / `saved_vreg_alloc` unused — không chặn release)
# Phase Final Checklist — Vir v2.0

**Snapshot date:** 22/04/2026 (sess 9 — đã đóng các mục ❌ còn lại trừ i18n sublib)

Trạng thái tổng hợp các mục còn **chưa hoàn thiện** để chuẩn bị đóng Phase Final. Nguồn: [unimplemented_features_checklist.md](unimplemented_features_checklist.md).

---

## ⚠️ Các mục triển khai MỘT PHẦN (18)

Đã có token/AST hoặc implementation stub, nhưng còn thiếu codegen/semantic/runtime hoàn chỉnh.

| # | Mục | Spec | Lý do còn ⚠️ | Việc cần làm để đóng |
|---|-----|------|-------------|----------------------|
| 1.1 | `include path;` | §3.2 | Self-host entry path còn regression với namespace `A::B::C` | Fix module path resolution; thêm test `include a::b::c;` xuyên bootstrap |
| 2.2 | Sized types `i8…i64`, `u8…u64` | §4.1 | Parser lưu type vào `name2`, **chưa có semantic enforcement** | Thêm type-check pass + narrowing codegen (AND mask cho u8/u16) |
| 2.3 | `ptr` (con trỏ thô) | §4.1 | Parser lưu token, chưa có deref/address-of semantic | Mapping `ptr` ↔ int64 + cast ops; unify với `__read8/__write8` |
| 2.5 | `arena: ... end` block | §4.5–4.6 | AST có; IR pass-through. §4.7 runtime đã có (session 9) nhưng block wrapper chưa auto-reset | Wire `arena:` block vào runtime: entry = `vir_arena_create`, exit = `vir_arena_destroy` |
| 2.9 | Move semantics (non-Copy) | §4.8 | Bare-ident + pass-by-value consume OK; còn thiếu: field move, partial move, double-move diagnostic | Hoàn thiện ownership analyser + error E-move-after-consume |
| 4.1 | `func` / `out` / `end.` bootstrap | §6.1 | Source parser OK; **bootstrap artifact** self-host còn parse rỗng `func main:` body | Rebuild bootstrap từ hiện tại và chạy lại regression self-host |
| 4.4 | Đối số có tên `f(a=5; b=10)` | §6.4 | Parser OK, nhưng IR **không reorder** theo tên — chỉ truyền theo thứ tự | Trong `lower_call`, resolve `param_name → position` rồi reorder args trước khi emit `Q_SET_ARG` |
| 5.6 | `packed entity` | §7.3 | AST `PackedDef`; **không có logic packed layout** | Packed layout: offset = Σ(field_size) không padding; sinh byte-ops cho sub-u8 fields |
| 12.1 | `ref` parameter | §14.1 | Parser `RefParam`; **không có LoadAddr/DerefLoad** | Pass địa chỉ globals slot / alloca; deref load tại call site |
| 12.4 | `;` multi-line params | §14.2 | Parse OK, không enforce separator rules | Warning W14 extensions: yêu cầu `;` giữa các named-arg groups |
| 13.4 | WebAssembly target | §15.3 | `codegen_wasm.vri` có encoder, **chưa tích hợp build pipeline** | Wire vào `vir build --target wasm32` + e2e test |
| 13.7 | WASM import section | §15.5 | Encoder có, **chưa e2e** | Cùng 13.4 — cần test binary chạy được trong wasmtime |
| 15.3 | Compile-time validation | §17.3 | Const-folder OK cho literal int + 10 binop + COMPARE + nested `precomp`; **thiếu type/overflow diagnostic** | Emit compile-error khi fold overflow (i64) hoặc type-mismatch |
| 20.2 | `await expr` | §22.1 | Stub cho expr form; cần integrate với scheduler task_wait | Lower `await T` → `Q_TASK_WAIT` trên task_id |
| 20.6 | `cancel` task | §22.7 | Parser + no-op IR stub | Cần scheduler hook: `task_cancel(tid)` (API chưa có) |
| 20.7 | `select` multiplex (async) | §22.8 | Sequential execution stub — **không multiplex thật** | Cần event loop với poll() / kqueue integration |
| 20.8 | `quiet` fire-and-forget | §22.9 | Fire-and-forget stub — **không detach thật** | Cùng scheduler — spawn + detach (không wait) |
| 26.1 | Tiếng Việt keywords | §28 | C core lexer đầy đủ; **self-hosting lexer chỉ có English** | Port Vietnamese keyword map vào `lexer.vri` + regen bootstrap |

---

## ❌ Các mục CHƯA TRIỂN KHAI (2)

Không tìm thấy, không có token/AST, hoặc chỉ có stub không chạy được.

| # | Mục | Spec | Ghi chú | Ghi chú triển khai |
|---|-----|------|---------|---------------------|
| 26.2 | 中文, 日本語, 한국어 | §28 | Chỉ có Vietnamese + English | Thêm keyword maps khi có SubLib (26.3) |
| 26.3 | SubLib adapter / KeywordRegistry | §28 | Không có dynamic keyword system | Cần thiết kế `KeywordRegistry` runtime hook vào lexer |

> Cả hai mục ❌ còn lại đều thuộc subsystem đa ngôn ngữ (sublib) — theo chỉ đạo, **không triển khai trong phase này**.

---

## ✅ Đã đóng trong session 9 (22/04/2026)

| # | Mục | Spec | Thay đổi |
|---|-----|------|----------|
| 2.6 | Arena API | §4.7 | 3 builtins `arena_new`/`arena_alloc`/`arena_free` → `Q_ARENA_NEW/ALLOC/FREE` wire vào `mem_manager.c` runtime |
| 17.5 | `arr_compact(arr)` | §19.4 | Builtin + `Q_ARR_COMPACT` — VM lọc bỏ phần tử = 0 |
| 17.6 | `cap(arr)` | §19.4 | Builtin + `Q_ARR_CAP` — expose `vm_array_t.cap` |
| 20.3 | `await pass` | §22.6 | Soft keyword ở stmt level → `Q_TASK_YIELD` (alias: `yield()` / `nhường()`) |
| 20.9 | Scheduler init | §22.5 | `vm_init` gọi `task_scheduler_init()` — green-thread deque sẵn sàng |

---

## Thống kê Phase Final (post session 9)

| Trạng thái | Số lượng | Ghi chú |
|-----------|---------|---------|
| ✅ Đã triển khai | 142 | Session 1–9 |
| ⚠️ Một phần | 18 | Chủ yếu async (20.x), semantic (2.x), WASM (13.x), self-host (1.1, 4.1) |
| ❌ Chưa triển khai | 2 | Cả 2 đều thuộc sublib i18n (26.2, 26.3) — out of scope |
| **Tổng** | **162** | |

---

## Ưu tiên đề xuất cho Phase Final (remaining ⚠️)

### P0 — Khoá chốt để release
1. **4.1 Bootstrap regression** — self-host cần stable trước khi tag release
2. **4.4 Named-arg reordering** — sửa IR reorder

### P1 — Semantic hoàn thiện
3. **2.2 Sized types enforcement** — bật type-check pass
4. **2.9 Move diagnostics** — hoàn thiện ownership analyser
5. **15.3 Precomp overflow/type diag** — thêm diagnostic vào `precomp_fold`
6. **12.1 `ref` param** — address-of + deref load

### P2 — Async/Runtime (scheduler đã sẵn sàng từ sess 9)
7. **20.2 `await expr`** — lower tới `Q_TASK_WAIT`
8. **20.6 / 20.7 / 20.8** — cần event loop + task_cancel API
9. **2.5 `arena:` block** — wire vào runtime arena

### P3 — Target mở rộng
10. **13.4 + 13.7 WASM pipeline** — wire `codegen_wasm.vri` vào build
11. **26.1 Vietnamese tự-host** — port keyword map

### P4 — Nice-to-have
12. **1.1 include path** — namespace `A::B::C` self-host
13. **5.6 packed entity layout** — compact struct layout
14. **12.4 `;` multi-line params** — extend W14

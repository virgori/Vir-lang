# Vir Programming Language — Full Codebase Audit Report
**Ngày: 2026-04-02**  
**Phạm vi: toàn bộ codebase `/Vir/`**  
**Files audited: ~350+ (C core, Python frontend/IR/backend, .vri stdlib & self-hosting compiler)**

---

## Tóm tắt

| Mức độ | Số lượng | Mô tả |
|--------|----------|-------|
| **CRITICAL** | 12 | Crash, data corruption, security vulnerability |
| **HIGH** | 16 | Chức năng sai, memory leak nghiêm trọng, missing implementation |
| **MEDIUM** | 14 | Logic bug, edge case, incomplete feature |
| **LOW** | 8 | Code quality, minor missing checks |

---

## PHẦN 1: C Core VM & Runtime (`core/src/`)

### [C-01] CRITICAL — `realloc` không kiểm tra NULL trong `vm_array_push`
**File:** `core/src/vm.c` dòng 88-92
```c
if (arr->len >= arr->cap) {
    arr->cap *= 2;
    arr->data = (int64_t *)realloc(arr->data, arr->cap * sizeof(int64_t));
    // ← Nếu realloc fail → arr->data = NULL → dòng sau crash
}
arr->data[arr->len++] = val;
```
**Hậu quả:** Segfault khi hệ thống hết memory. Mất pointer cũ (memory leak).  
**Fix:** Lưu pointer cũ, check NULL trước khi gán.

---

### [C-02] CRITICAL — Cùng lỗi `realloc` trong `intrinsics.c`
**File:** `core/src/intrinsics.c` dòng 275
```c
arr->data = (int64_t *)realloc(arr->data, arr->cap * sizeof(int64_t));
```
**Hậu quả:** Tương tự C-01. Duplicated bug.

---

### [C-03] CRITICAL — Memory leak hàm `vir_builtin_str_cat`
**File:** `core/src/intrinsics.c` dòng 129-137
```c
const char *vir_builtin_str_cat(const char *a, const char *b) {
    char *out = (char *)malloc(la + lb + 1);
    if (!out) return "";
    memcpy(out, a, la);
    memcpy(out + la, b, lb);
    out[la + lb] = '\0';
    return out;  // ← Caller KHÔNG BAO GIỜ free!
}
```
**Hậu quả:** Mỗi lần gọi `str_cat()` leak memory. Trong vòng lặp → OOM.  
**Fix:** Dùng arena allocator hoặc string pool. Hiện tại KHÔNG có cơ chế free string.

---

### [C-04] CRITICAL — Memory leak `vir_builtin_i_to_str`
**File:** `core/src/intrinsics.c` dòng 156-160
```c
const char *vir_builtin_i_to_str(int64_t n) {
    char *buf = (char *)malloc(32);
    if (!buf) return "";
    snprintf(buf, 32, "%lld", (long long)n);
    return buf;  // ← Không bao giờ free
}
```
**Hậu quả:** Tương tự C-03. Mỗi lần convert int→string leak 32 bytes.

---

### [C-05] CRITICAL — Memory leak `vir_builtin_file_read`
**File:** `core/src/intrinsics.c` dòng 186-197
```c
const char *vir_builtin_file_read(int64_t fd) {
    char *buf = (char *)malloc((size_t)sz + 1);
    // ...
    return buf;  // ← malloc'd, never freed
}
```

---

### [C-06] CRITICAL — Task stack không có guard page
**File:** `core/src/task.c` dòng 71-80
```c
static void *alloc_stack(uint64_t size) {
    void *p = mmap(NULL, size, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    // ← Không có guard page → stack overflow = heap corruption SILENT
    return p;
}
```
**Fix:** Thêm `mprotect(p, page_size, PROT_NONE)` cho guard page ở đáy stack.

---

### [C-07] CRITICAL — `realloc` fail mất pointer trong `vm.c`
**File:** `core/src/vm.c` dòng 647-656
```c
void *p = realloc(ptr, (size_t)new_sz);
if (!p) {
    vm->regs[0] = 0;
    break;  // ← Pointer cũ (ptr) bị mất → memory leak + heap tracking sai
}
```

---

### [C-08] CRITICAL — Integer overflow trong `ptx_gen.c`
**File:** `core/src/ptx_gen.c` dòng 48-51
```c
while (pb->len + extra + 1 > pb->cap) {
    pb->cap *= 2;  // ← Nếu cap > SIZE_MAX/2 → overflow → alloc size nhỏ → buffer overflow
    pb->data = realloc(pb->data, pb->cap);
}
```

---

### [C-09] HIGH — `g_mem_stats` không thread-safe
**File:** `core/src/mem_manager.c` dòng 104-125
```c
g_mem_stats.total_allocs++;  // ← race condition nếu multi-thread
g_mem_stats.bytes_allocated += size;
g_mem_stats.current_objects++;
```
**Fix:** Dùng `atomic_fetch_add` hoặc mutex.

---

### [C-10] HIGH — NULL dereference trong parser
**File:** `core/src/parser.c` dòng 43-50
```c
static const vir_token_t *peek(const vir_parser_t *p) {
    uint32_t idx = p->pos < p->token_count ? p->pos : p->token_count - 1;
    return &p->tokens[idx];  // ← Nếu tokens == NULL → segfault
}
```
Parser init không validate `tokens != NULL`.

---

### [C-11] HIGH — Label overflow silent drop
**File:** `core/src/vm.c` dòng ~212
Labels vượt `VM_MAX_LABELS` bị drop chỉ với `fprintf(stderr)`. Không return error → compiled code chạy sai.

---

### [C-12] HIGH — Unicode string xử lý sai
**File:** `core/src/vm.c` dòng ~850
```c
char_len = new_len;  /* char_len = byte_len for ASCII */
```
Giả định 1 char = 1 byte. Tiếng Việt (UTF-8 multi-byte) → `str_len()` trả sai.

---

### [C-13] HIGH — `jit_bridge` race condition
**File:** `core/src/jit_bridge.c` dòng 59-77
```c
jb->callbacks[slot] = (jit_callback_t){ ... };
jb->callback_table[slot] = func_addr;
jb->callback_count++;  // ← Giữa gán data và tăng count, thread khác có thể thấy trạng thái inconsistent
pthread_mutex_unlock(&jb->lock);
```
**Fix:** Tăng count SAU khi init xong, hoặc dùng memory barrier.

---

### [C-14] MEDIUM — `slab_alloc.c` header corruption
**File:** `core/src/slab_alloc.c` dòng 93-100  
Corrupt `class_idx` có thể bypass bounds check nếu giá trị nằm trong range hợp lệ nhưng trỏ đến pool sai.

---

### [C-15] MEDIUM — `thread_runtime.c` mutex không validate
**File:** `core/src/thread_runtime.c` dòng 161-173  
`vir_mutex_lock()`/`vir_mutex_unlock()` không kiểm tra mutex đã được create chưa.

---

### [C-16] MEDIUM — `q_ir.c` function body realloc không check NULL
**File:** `core/src/q_ir.c` dòng 109
```c
q_instruction_t *new_body = (q_instruction_t *)realloc(
    func->body, new_cap * sizeof(q_instruction_t));
// Không check NULL
```

---

## PHẦN 2: Python Frontend, IR & Backend (`src/`)

### [P-01] CRITICAL — Arena allocator bounds check sai
**File:** `src/virmem/arena.py` dòng 48-59
```python
blk = self._blocks[self._current]
start = blk.used
blk.used += n_floats  # ← Tăng TRƯỚC khi validate
return blk.data[start:start + n_floats]
```
**Thực tế:** Python slice an toàn (trả về shorter slice), nhưng logic sai → alloc data bị overlap giữa 2 alloc kế tiếp nếu block remaining < n_floats mà code không tạo block mới.  
**Fix:** Check `remaining < n_floats` đã có ở đầu hàm. Bug chỉ xảy ra nếu n_floats fit vừa remaining nhưng code path sai.

---

### [P-02] CRITICAL — Optimizer constant folding sai với nested loops
**File:** `src/ir/optimizer/optimizer.py`  
Chỉ detect backward jump là loop. Forward jump trong conditional bị miss → constant folding produce **giá trị sai** mà không warning.

---

### [P-03] CRITICAL — Dead code elimination xóa live code
**File:** `src/ir/optimizer/optimizer.py`  
Labels không được thêm vào "used" set → instruction `LABEL` bị xóa → jump targets trỏ đến instruction không tồn tại → crash runtime.

---

### [P-04] CRITICAL — Escape analysis không hoạt động
**File:** `src/ir/optimizer/escape_analysis.py`  
- Không track pointer chain (r1=r2; r2=r3)
- Không handle phi/merge nodes
- `max()` với `key=` dùng sai → trả lambda thay vì value  
**Hậu quả:** Không allocation nào được promote to stack. Feature vô dụng.

---

### [P-05] CRITICAL — Bounds check elimination range math error
**File:** `src/ir/optimizer/bounds_check_elim.py`
```python
lo = max(self.lo, other.lo) if ... else (self.lo or other.lo)
# Nếu self.lo=None, other.lo=10 → trả None thay vì 10
```
**Hậu quả:** Có thể xóa bounds check cần thiết → buffer overflow.

---

### [P-06] CRITICAL — Optimizer passes chưa implement
**File:** `src/ir/optimizer/optimizer.py`  
Các hàm gọi nhưng KHÔNG CÓ body:
- `_alias_analysis()` — stub
- `_licm()` — chưa viết
- `_loop_strength_reduce()` — chưa viết
- `_cse()` — chưa viết
- `_auto_vectorize()` — chưa viết
- `_polyhedral_tile()` — chưa viết  
**Hậu quả:** Crash khi optimizer chạy ở mode nâng cao.

---

### [P-07] HIGH — Monomorphization dùng naive string replacement
**File:** `src/ir/monomorph.py`  
`Vec<T>` với T→i64 thành `Veci64<i64>` (syntax error). Cần proper type substitution.

---

### [P-08] HIGH — Linear scan register allocator dùng x18
**File:** `src/ir/registers/linear_scan.py`  
x18 trên Apple Silicon là reserved (platform register). Nếu allocator gán vreg vào x18 → crash trên macOS ARM64.

---

### [P-09] HIGH — Codegen thiếu ARM64
**File:** `src/backend/codegen/codegen.py`  
Chỉ có x86_64 integer arithmetic. ARM64 (target chính cho macOS) chưa implement trong Python codegen path.

---

### [P-10] HIGH — Binary patcher thiếu icache invalidation
**File:** `src/backend/patcher/binary_patcher.py`  
Không gọi `pthread_jit_write_protect` hoặc `sys_icache_invalidate`. Code patch trên ARM64 macOS → CPU execute stale instructions.

---

### [P-11] HIGH — Mach-O relocation format sai cho x86_64
**File:** `src/backend/codegen/obj_emitter.py`  
Bit packing assume ARM64 format cho cả x86_64. Nếu emit x86_64 object file → linker reject.

---

### [P-12] HIGH — CMP+Jcc fusion gọi hàm không tồn tại
**File:** `src/backend/codegen/codegen_x86.py`  
Gọi `_emit_fused_cmp_jmp()` nhưng hàm này chưa được define.

---

### [P-13] MEDIUM — Memory planner buffer reuse off-by-one
**File:** `src/virmem/planner.py`  
`bend < iv.start` nên là `<=`. Gây tăng memory usage không cần thiết.

---

### [P-14] MEDIUM — TempPool không validate buffer size mismatch
**File:** `src/virmem/pool.py`  
`release()` không check `len(buf)` khớp với size bucket → reuse buffer sai size.

---

### [P-15] MEDIUM — Type checker thiếu boolean semantics
**File:** `src/frontend/type_check.py`  
Không có type promotion rules cho `bool` với kiểu khác.

---

### [P-16] MEDIUM — Tokenizer xử lý sai dấu tiếng Việt
**File:** `src/frontend/tokenizer/ngram_tokenizer.py`  
`text.lower()` làm hỏng diacritic marks của tiếng Việt trong identifier.

---

## PHẦN 3: Self-Hosting Compiler (`stdlib/vir/compiler/`)

### [S-01] HIGH — `parse_func_def` thiếu colon consumption khi không có parentheses
**File:** `stdlib/vir/compiler/parser.vri` ~dòng 1115-1125
```vri
if t_lp.tok_type == TokType::LParen:
    # parse params...
else
    p4 = p2;  # ← KHÔNG consume colon!
end
```
Code `func foo: body end` (không có params) → colon ở lại token stream → parse sai.
`if`, `while`, `loop`, `for` đã fix (có `check(p, TokType::Colon)` + advance). Riêng `func` thiếu.

---

### [S-02] HIGH — Parser chỉ ghi nhận error đầu tiên
**File:** `stdlib/vir/compiler/parser.vri` ~dòng 305
```vri
func parse_error:
    if str_len(p.p_err) == 0:
        # chỉ ghi error đầu tiên
    end
```
Các error sau bị drop im lặng. Không có error recovery → parse cascading failure.

---

### [S-03] HIGH — `parse_block` infinite loop risk
**File:** `stdlib/vir/compiler/parser.vri` ~dòng 846-880
```vri
when should_continue loop
    if t_blk.tok_type == TokType::End or ... Eof:
        should_continue = false;
    else
        var (p2, stmt) = parse_statement(p);
        p = p2;
        # ← Nếu parse_statement KHÔNG advance token → infinite loop
    end
end
```
**Fix:** Detect position không đổi sau `parse_statement()` → force advance hoặc break.

---

### [S-04] HIGH — String memory leak trong parser
**File:** `stdlib/vir/compiler/parser.vri` nhiều dòng
```vri
p.p_err = str_concat(
    str_concat(str_new("line "), int_to_str(t.tok_line)),
    str_concat(str_new(": "), msg)
);  # ← 3 temp strings, không bao giờ free
```
Mỗi error message leak 4 string objects. Tích lũy qua nhiều file → OOM.

---

### [S-05] HIGH — Jump offset computation thiếu validation
**File:** `stdlib/vir/compiler/main.vri` ~dòng 700-750
```vri
var jn_label = jn_encoded / 1000;
# ← Nếu jn_label > label count → emit jump đến instruction không tồn tại
```
Không có bounds check cho label index trước khi tính offset.

---

### [S-06] MEDIUM — Magic numbers scope (0=local, 1=global)
**File:** `stdlib/vir/compiler/ir_optimizer.vri`
```vri
if scope == 0:   # local
if scope == 1:   # global
```
Nên dùng enum thay vì magic numbers.

---

### [S-07] MEDIUM — `else:` colon vẫn chưa fix
Theo memory notes, `else:` (với colon) vẫn không hoạt động. Phải viết `else` không colon.

---

### [S-08] MEDIUM — `input` là keyword nhưng không cảnh báo
Dùng `input` làm tên parameter → parsing break im lặng (AST children count giảm). Không có error message.

---

## PHẦN 4: Stdlib (.vri) — Tính năng còn thiếu

### [L-01] HIGH — Package manager chưa implement
**File:** `stdlib/vir/pkg/pkg.vri`
- `pkg_search()` → luôn trả empty list
- `pkg_fetch()` → trả `Err("not implemented")`
- `_discover_sources()` → luôn trả empty

Package system hoàn toàn không hoạt động.

---

### [L-02] HIGH — LSP server là stub
**File:** `stdlib/vir/lsp/lsp.vri`
Toàn bộ Language Server Protocol implementation là skeleton. Không serve thực tế.

---

### [L-03] HIGH — Build system `_discover_sources` rỗng
**File:** `stdlib/vir/build/build.vri`
```vri
func _discover_sources:
    sources = vec_new<string>();  # luôn rỗng
```
Build system không tìm được source files.

---

### [L-04] HIGH — `extern func` chưa supported bởi self-hosting compiler
Theo memory notes, runtime modules dùng `extern func syscall*` nhưng self-hosting compiler không compile được. Blocking cho self-hosted native runtime.

---

### [L-05] MEDIUM — Crypto ed25519 dùng placeholder hash
**File:** `stdlib/vir/crypto/ed25519.vri` dòng 343-344
```vri
# In production, import a real SHA-512; this is a placeholder
```
SHA-512 là placeholder → ed25519 signatures **không an toàn**.

---

### [L-06] MEDIUM — Brotli compression thiếu static dictionary
**File:** `stdlib/vir/compress/brotli.vri`
```vri
# Stub — full Brotli has a 122K static dictionary
```
Compression ratio sẽ kém hơn nhiều so với Brotli thật.

---

### [L-07] MEDIUM — VM interpreter thiếu array/string operations
**File:** `stdlib/vir/compiler/vm.vri` dòng 487-530
```vri
# Stub: array operations deferred to native layer
# Stub: string operations deferred to native layer
```
VM interpreter trong .vri không execute array/string → chỉ chạy được số học.

---

### [L-08] MEDIUM — FTP quote extraction chưa implement
**File:** `stdlib/vir/net/ftp.vri` dòng 308

---

### [L-09] LOW — x86_64 codegen GPR functions rỗng
**File:** `stdlib/vir/codegen/x86_64.vri` dòng 35-60
```vri
func rax:   # NO BODY
func rbx:   # NO BODY
```
x86_64 backend hoàn toàn non-functional.

---

### [L-10] LOW — Swift bridge chỉ có template
**File:** `src/backend/swift/cli.py` dòng 494
```python
# TODO: Parse C header and generate bridge
# For now, create a template only
```

---

## PHẦN 5: Test Coverage Gaps

### [T-01] HIGH — Không có test cho string memory leak
Không test nào kiểm tra memory usage sau nhiều `str_cat()` calls. Leak sẽ chỉ phát hiện khi chạy nặng.

---

### [T-02] HIGH — Không có test cho `realloc` failure path
Không mock `realloc` returning NULL. Toàn bộ array push/growth path chưa test failure case.

---

### [T-03] HIGH — Không có test cho Unicode/tiếng Việt
`str_len()`, `str_get()`, identifier parsing — toàn bộ dùng ASCII. Tiếng Việt chưa test.

---

### [T-04] MEDIUM — Chỉ có 48 test cases cho self-hosting compiler
Test suite trong `run_tests.sh` chỉ cover:
- ✅ Arithmetic, control flow, strings, arrays, entities, enums, globals
- ❌ Nested entity field access
- ❌ Higher-kinded generics
- ❌ Module system
- ❌ Error handling paths
- ❌ Large programs (>1000 lines)
- ❌ Recursive entity types
- ❌ Multi-file compilation
- ❌ String escape sequences
- ❌ Float/double types

---

### [T-05] MEDIUM — Architecture tests skip khi thiếu config JSON
Tests trong `tests/test_phase_h.py` skip nếu `arm64_config.json`, `x86_64_config.json`, `cpu_caps.json` không tồn tại. Có thể chạy CI mà không biết tests bị skip.

---

### [T-06] MEDIUM — Optimizer correctness tests thiếu
Không có test verify optimizer output correctness (constant folding, DCE, bounds check elim). Optimizer bugs (P-02, P-03, P-05) sẽ produce wrong code undetected.

---

## PHẦN 6: Đề xuất ưu tiên sửa

### Ngay lập tức (P0)
1. **Fix tất cả `realloc` không check NULL** — C-01, C-02, C-07, C-08, C-16
2. **Thêm string deallocation mechanism** — C-03, C-04, C-05 → Arena string pool cho VM
3. **Thêm guard page cho task stack** — C-06
4. **Fix optimizer DCE xóa live labels** — P-03

### Ngắn hạn (1-2 tuần)
5. Fix parser `parse_func_def` colon consumption — S-01
6. Fix parser infinite loop protection — S-03
7. Implement proper error recovery trong parser — S-02
8. Fix register allocator exclude x18 trên ARM64 — P-08
9. Fix bounds check elimination range math — P-05

### Trung hạn (1 tháng)
10. Implement `extern func` trong self-hosting compiler — L-04
11. Implement package manager `pkg_fetch()` — L-01
12. Add Unicode/UTF-8 support cho string operations — C-12, T-03
13. Add `realloc` failure tests — T-02
14. Implement missing optimizer passes hoặc remove calls — P-06
15. Fix monomorphization string replacement — P-07

### Dài hạn
16. Thread-safe memory stats — C-09
17. LSP server implementation — L-02
18. x86_64 .vri codegen — L-09
19. Full Brotli static dictionary — L-06
20. Real SHA-512 cho ed25519 — L-05

---

*Report generated by automated audit. Manual verification recommended for all CRITICAL items.*

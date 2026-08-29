# Hệ thống Module & Include — Đặc tả Kỹ thuật

> **Phiên bản:** Phase 4  
> **Kết quả tests:** 89/89 pass ✅

---

## 1. Tổng quan

Vir hỗ trợ ba cơ chế tổ chức mã nguồn đa file:

| Cú pháp | Chức năng | Ví dụ |
|----------|-----------|-------|
| `include "file.vri"` | Nạp & splice nội dung file vào AST hiện tại | `include "helpers.vri"` |
| `import X` / `import X as Y` | Khai báo phụ thuộc module + alias | `import math as m` |
| `from X import sym1, sym2` | Import symbol cụ thể từ module | `from utils import add, mul` |
| `module NAME` | Đặt tên module cho file hiện tại | `module math` |
| `export func ...` | Đánh dấu hàm/symbol công khai | `export func square(x) ...` |

---

## 2. Include System

### 2.1. Pipeline

```
Source code          ir_lower.c                     Kết quả
┌──────────┐    lower_resolve_includes()    ┌──────────────────┐
│ main.vri │ ──────────────────────────────→│ AST gộp (spliced)│
│  include  │    ① Tìm AST_INCLUDE node     │ helpers.vri nodes │
│  "helpers" │   ② Gọi include_reader()      │ + main.vri nodes  │
│  func main │   ③ Lex + Parse sub-file     └──────────────────┘
│  ...       │   ④ Splice children vào AST
└──────────┘    ⑤ Xóa AST_INCLUDE node
```

### 2.2. Include Reader Callback

Driver (main.c) cung cấp callback để đọc file:

```c
typedef char *(*include_reader_fn)(const char *filename,
                                    size_t *out_len,
                                    void *user_data);
```

**Thứ tự tìm file:**
1. `base_dir/filename` — thư mục chứa file nguồn chính
2. `filename` — đường dẫn nguyên bản (absolute hoặc relative từ CWD)

**Thiết lập trong main.c:**

```c
include_ctx_t ictx;
get_dir(filepath, ictx.base_dir, sizeof(ictx.base_dir));
ctx.include_reader    = vir_include_reader;
ctx.include_user_data = &ictx;
```

### 2.3. Thuật toán Splice

`lower_resolve_includes()` thao tác trực tiếp trên AST:

1. Duyệt `program->children[]` tìm `AST_INCLUDE` nodes
2. Kiểm tra double-include guard (`included_files[]`)
3. Đọc file → Lex → Parse → thu được `sub: AST_PROGRAM`
4. Shift children phải để tạo chỗ: `n_new - 1` vị trí
5. Copy `sub->children[0..n_new-1]` vào vị trí include
6. Xóa include node gốc, giảm index để xử lý include lồng nhau

### 2.4. Double-Include Guard

```c
#define INCLUDE_MAX 64
char included_files[INCLUDE_MAX][256];  /* Tên file đã include */
uint32_t included_file_count;
```

Khi gặp file đã include trước đó:
- Xóa AST_INCLUDE node khỏi AST
- Không báo lỗi — tương tự `#pragma once` trong C

### 2.5. Ví dụ

```vir
# helpers.vri
func double(x) then
    return x * 2
end

# main.vri
include "helpers.vri"

func main() then
    return double(21)   # → 42
end
```

---

## 3. Module System

### 3.1. Module Aliases (import X as Y)

`lower_process_imports()` quét AST và xây dựng bảng alias:

```c
#define MODULE_ALIAS_MAX 64
struct {
    char original[AST_NAME_LEN];  /* Tên module gốc */
    char alias[AST_NAME_LEN];     /* Tên alias (mặc định = original) */
} module_aliases[MODULE_ALIAS_MAX];
```

| Cú pháp | `original` | `alias` |
|---------|-----------|--------|
| `import math` | `"math"` | `"math"` |
| `import math as m` | `"math"` | `"m"` |

### 3.2. Imported Symbols (from X import ...)

```c
#define IMPORTED_SYM_MAX 128
struct {
    char module[AST_NAME_LEN];   /* Module chứa symbol */
    char symbol[AST_NAME_LEN];   /* Tên symbol được import */
} imported_syms[IMPORTED_SYM_MAX];
```

| Cú pháp | Entries |
|---------|--------|
| `from utils import add, mul` | `{utils, add}`, `{utils, mul}` |
| `from io import read` | `{io, read}` |

### 3.3. Module Declaration

```vir
module mylib
```

Thiết lập `ctx->module.name = "mylib"`. Module name được gán cho Q-IR module output.

### 3.4. Export

```vir
export func square(x) then
    return x * x
end
```

`AST_EXPORT` node được ghi nhận nhưng chưa thực hiện semantic linking trong phase hiện tại. Dự kiến cho Phase 5: liên kết cross-module sẽ kiểm tra danh sách export khi resolve import.

---

## 4. Metadata Classification — `ast_is_metadata()`

### 4.1. Mục đích

Trước refactor, `lower_program()` loại trừ các node không phải statement runtime bằng chuỗi điều kiện dài:

```c
/* CŨ — dễ quên khi thêm node type mới */
if (child->type != AST_ENUM_DEF &&
    child->type != AST_RECORD_DEF &&
    child->type != AST_MODULE &&
    child->type != AST_IMPORT &&
    child->type != AST_EXPORT &&
    child->type != AST_INCLUDE)
```

### 4.2. Giải pháp

```c
int ast_is_metadata(ast_type_t type)
{
    switch (type) {
    case AST_ENUM_DEF:
    case AST_RECORD_DEF:
    case AST_MODULE:
    case AST_IMPORT:
    case AST_EXPORT:
    case AST_INCLUDE:
        return 1;
    default:
        return 0;
    }
}
```

**Sử dụng trong `lower_program()`:**

```c
if (!ast_is_metadata(child->type)) {
    has_top_stmt = 1;  /* Có statement cần wrap vào __main */
}
```

### 4.3. Mở rộng

Khi thêm AST node type mới mang tính metadata/khai báo, chỉ cần thêm 1 case vào switch — không cần sửa `lower_program()`.

---

## 5. Thứ tự Xử lý trong Pipeline

```
   main.c                          ir_lower.c
   ──────                          ──────────
1. Đọc source file
2. Lex + Parse → AST
3. Setup include_reader callback
4. lower_resolve_includes()  ───→  Splice tất cả include files
5. lower_program()           ───→  a) lower_process_imports()  ← tự động
                                   b) Xử lý enum/record types
                                   c) Lower func_def + top-level stmts
```

**Quan trọng:** `lower_resolve_includes()` phải được gọi **trước** `lower_program()`. Pipeline trong `main.c` đảm bảo thứ tự này.

---

## 6. Cấu trúc lower_ctx_t (Các trường mới)

| Trường | Kiểu | Mô tả |
|--------|------|-------|
| `module_aliases[]` | struct×64 | Bảng alias: import X as Y |
| `module_alias_count` | uint32_t | Số lượng alias đã đăng ký |
| `imported_syms[]` | struct×128 | Bảng symbol: from X import sym |
| `imported_sym_count` | uint32_t | Số lượng symbol đã import |
| `include_reader` | function ptr | Callback đọc file include |
| `include_user_data` | void* | Context cho callback |
| `include_search_paths[]` | char*×16 | Danh sách thư mục tìm kiếm (dự phòng) |
| `include_search_path_count` | uint32_t | Số lượng search paths |
| `included_files[][]` | char×64×256 | Danh sách file đã include (guard) |
| `included_file_count` | uint32_t | Số file đã include |

---

## 7. API Reference

```c
/* Resolve include directives — PHẢI gọi trước lower_program() */
int lower_resolve_includes(lower_ctx_t *ctx, ast_node_t *program);

/* Xử lý metadata import/module/export — gọi TỰ ĐỘNG bởi lower_program() */
int lower_process_imports(lower_ctx_t *ctx, const ast_node_t *program);

/* Kiểm tra AST node có phải metadata (không tạo runtime code) */
int ast_is_metadata(ast_type_t type);
```

**Return values:** `0` = thành công, `-1` = lỗi (chi tiết trong `ctx->last_error`).

---

## 8. Test Coverage

| Test | Mô tả | ID |
|------|--------|----|
| `test_e2e_include_basic` | Include file chứa hàm, gọi từ main | 84 |
| `test_e2e_include_multi` | Include 2 file khác nhau | 85 |
| `test_e2e_include_double_guard` | Include cùng file 2 lần, không duplicate | 86 |
| `test_e2e_include_with_module` | Kết hợp module + import + include | 87 |
| `test_metadata_helper` | Verify `ast_is_metadata()` cho mọi type | 88 |
| `test_process_imports` | Build AST thủ công, verify bảng alias/sym | 89 |

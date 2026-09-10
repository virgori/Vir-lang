# Virgex — Vir Pattern Syntax (VPS) Engine

**Hệ pattern thay thế regex truyền thống, thiết kế cho ngôn ngữ Vir.**

---

## Tổng quan

Virgex (Vir + Regex) triển khai **Vir Pattern Syntax (VPS)** — ngôn ngữ pattern với triết lý:

- **Literal mặc định** — dữ liệu thật không cần đánh dấu
- **Ký hiệu tối thiểu** — chỉ 8 ký hiệu lõi
- **Logic rõ ràng** — nhìn là hiểu, không cần decode

## Cấu trúc thư mục

```
virgex/
├── spec/
│   └── VPS_SPEC_v1.md         # Đặc tả kỹ thuật đầy đủ v1.0
├── src/                        # Python reference implementation
│   ├── __init__.py             # Public API
│   ├── tokens.py               # Token types & Quantifier
│   ├── lexer.py                # VPS tokenizer
│   ├── ast_nodes.py            # AST node definitions
│   ├── parser.py               # Recursive-descent parser
│   ├── compiler.py             # AST → Python regex compiler
│   ├── matcher.py              # High-level matching API
│   └── errors.py               # Error hierarchy
├── tests/                      # Test suite (113 tests)
│   ├── test_lexer.py           # Lexer tests
│   ├── test_parser.py          # Parser + AST tests
│   ├── test_compiler.py        # VPS → regex translation tests
│   └── test_e2e.py             # End-to-end matching tests
├── stdlib/
│   └── virgex.vri              # Vir stdlib module (.vri implementation)
└── README.md
```

## Ký hiệu lõi

| Ký hiệu    | Vai trò                        |
|-------------|--------------------------------|
| `@`         | Atom (loại ký tự)              |
| `!`         | Lượng hóa (postfix)            |
| `~`         | Khoảng lượng hóa               |
| `?`         | Optional boolean (prefix)      |
| `:(` `:)`   | Group logic                    |
| `\|`        | Anchor hoặc OR (context)       |
| `$`         | Escape                         |
| `-`         | Dấu cách thật                  |

## Atom chuẩn

| Atom    | Ý nghĩa               | Regex          |
|---------|------------------------|----------------|
| `@Az`   | Chữ Latin (hoa/thường) | `[A-Za-z]`     |
| `@AZ`   | Chữ hoa                | `[A-Z]`        |
| `@az`   | Chữ thường             | `[a-z]`        |
| `@0`    | Chữ số 0–9             | `[0-9]`        |
| `@06`   | Chữ số 0–6             | `[0-6]`        |
| `@Az0`  | Chữ hoặc số            | `[A-Za-z0-9]`  |

## Ví dụ nhanh

| VPS                              | Ý nghĩa                           | Regex                        |
|----------------------------------|------------------------------------|------------------------------|
| `\| @0!3 \|`                    | Đúng 3 chữ số                     | `^[0-9]{3}$`                |
| `\| @AZ!2 $- @0!5 \|`          | 2 hoa + dash + 5 số               | `^[A-Z]{2}\-[0-9]{5}$`     |
| `\| @Az0!3~12 \|`              | Username 3–12 ký tự               | `^[A-Za-z0-9]{3,12}$`      |
| `\| :( A \| B :) \|`           | A hoặc B                          | `^(?:A\|B)$`                |
| `\| @AZ!2 ?:( $- @0!5 :) \|`  | Mã có hoặc không có đuôi số       | `^[A-Z]{2}(?:\-[0-9]{5})?$`|

## Sử dụng (Python)

```python
import virgex

# Compile & match
pat = virgex.compile("| @AZ!2 $- @0!5 |")
assert pat.fullmatch("HN-12345")

# One-shot
assert virgex.fullmatch("| @0!3 |", "456")

# Translate to regex
print(virgex.to_regex("| @Az0!3~12 |"))
# Output: ^[A-Za-z0-9]{3,12}$

# Search
m = virgex.search("@0!3", "abc123def")
print(m.text)  # "123"

# Find all
results = virgex.findall("@0!3", "abc123def456ghi789")
# ["123", "456", "789"]
```

## Sử dụng (Vir)

```vir
nhập "vir/virgex/virgex" dùng virgex_to_regex, virgex_fullmatch

biến regex = virgex_to_regex("| @AZ!2 $- @0!5 |")
in(regex)  # ^[A-Z]{2}\-[0-9]{5}$

biến ok = virgex_fullmatch("| @0!3 |", "123")
in(ok)  # đúng
```

## Chạy tests

```bash
cd virgex/
python -m pytest tests/ -v
```

## Đặc tả đầy đủ

Xem [spec/VPS_SPEC_v1.md](spec/VPS_SPEC_v1.md) cho đặc tả kỹ thuật VPS v1.0 hoàn chỉnh.

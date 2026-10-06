# Vir Frontend Algorithms Spec

Spec các thuật toán **đang triển khai** trong frontend của full compiler (`stdlib/vir/compiler/`).  
Phạm vi: lexer + parser + string helpers dùng bởi frontend. Không mô tả MIR/LIR/backend.

Nguồn chân lý:

| Module | Path |
|--------|------|
| Lexer | `stdlib/vir/compiler/lexer.vri` |
| Parser / AST | `stdlib/vir/compiler/parser.vri` |
| Fat-string helpers | `stdlib/vir/rt/string_rt.vri` |

---

## 1. Zero-copy token spans

Mỗi `Token` mang `(start, len)` vào buffer nguồn thay vì luôn copy lexeme lúc tokenize.

```
entity Token:
    tok_type, line, col
    start, len          # byte span trong source
    str_val, int_val, float_val
```

- Keyword / ident: `lex_word` ghi `tok.start` / `tok.len`, keyword nhận diện qua span (mục 4).
- Materialize khi parser cần tên: `token_lexeme` → `ident_intern_span` → `fat_str_slice` (O(span), một alloc).
- `expect_name_tok` / `tok_lex` gọi đường này trước khi gắn `AstNode.name`.

---

## 2. ASCII class table (byte-class DFA)

Bảng 256 byte `g_lex_ascii`, mỗi ô bitset:

| Flag | Bit | Ý nghĩa |
|------|-----|---------|
| `LEX_C_SPACE` | 1 | SP / TAB / CR (không gồm LF) |
| `LEX_C_DIGIT` | 2 | `0–9` |
| `LEX_C_ID_START` | 4 | chữ / `_` |
| `LEX_C_ID_CONT` | 8 | start ∪ digit |

API nóng: `lex_is_space_fast`, `lex_is_digit_fast`, `lex_is_ident_start_fast`, `lex_is_ident_continue_fast`.

LF (`\n`) **không** thuộc space class — lexer vẫn emit `TokType.Newline` làm separator (§1.0).

---

## 3. Single-character DFA table

Bảng 256 × i64 `g_lex_single`: byte → `TokType` (0 = không phải single-char op).

- Init một lần: `lex_single_init` / `lex_single_store`.
- Hot path: `lex_single_tok(c)` — O(1) thay vì chuỗi `if` dài cho `( ) [ ] { } , . ; :` và các op một ký tự đã đăng ký.

Multi-char ops (`==`, `!=`, `>>`, `||`, `->`, …) vẫn được nhận diện trước bằng lookahead 2–3 byte trong `tokenize`.

---

## 4. Keyword lookup trên span (zero-copy)

`lookup_keyword_span(table, source, start, span_len)`:

1. So sánh độ dài + nội dung với từng `KeywordEntry.word` qua `fat_str_eq_span` (không slice trước).
2. Trùng → trả `TokType` keyword.
3. Không trùng → `TokType.Ident` (lexeme lazy).

Bảng keyword dựng bởi `build_keyword_table` (hai phần `kw_table_part1/2`).

---

## 5. Word-at-a-time whitespace scan (“SIMD-style”)

`lex_skip_ws_simd` — quét whitespace không gồm LF:

1. **Bulk 8 byte:** đọc u64 little-endian tại `pos`; nếu cả 8 byte ∈ `{SP, TAB, CR}` thì `pos += 8` (và cộng LF count nếu có — hiện bulk chỉ nhận SP/TAB/CR nên count NL trên bulk = 0).
2. **Tail byte:** lặp `lex_is_space_fast` đến hết run.

Được gọi từ:

- `skip_whitespace`
- `skip_trivia` (cùng vòng với `#` line comment và `#*#` / `##` block comment)

### Sentinel pad nguồn

`lexer_new` giữ source qua `fat_str_sentinel_pad`: copy buffer, ghi NUL tại `[len]`, `logical len` không đổi. Cho phép bulk/peek an toàn gần EOF mà không đọc quá biên logical.

---

## 6. Trivia pipeline

`skip_trivia` (một vòng):

```
space/tab/cr  → lex_skip_ws_simd
# / #*# / ##  → skip_comment / skip_block_comment
else          → stop
```

`tokenize` gọi `skip_trivia` mỗi iteration, rồi phân nhánh newline / string / number / multi-char / single-char / word.

`vec_reserve` token list ước lượng `max(64, source_len/4)` khi `source_len >= 4`.

---

## 7. Pratt expression parser (unified)

Expr không còn chuỗi `parse_power` … `parse_or_expr`. Một vòng:

```
parse_expr(p) = parse_expr_bp(p, 0)

parse_expr_bp(p, min_bp):
    left ← parse_unary(p)          # prefix + primary + postfix
    loop:
        skip_newlines
        lbp ← infix_bp_left(peek)
        if lbp < min_bp → break
        if As | Cast → một cast suffix → break   # khớp parse_shift cũ
        if lbp > 0 → advance; right ← parse_expr_bp(rbp); left ← parse_infix_make(...)
        else break
```

### Binding power (Spec §30)

| `lbp` | Operators |
|------:|-----------|
| 1 | `\|\|` `\|` `or` `xor` |
| 5 | `&&`-style `and` / `&` (BitAnd infix) / keyword `and` |
| 7 | `==` `!=` `?=` `?=/=` |
| 9 | `>` `<` `>=` `<=` |
| 11 | `:~` |
| 13 | `+` `-` |
| 15 | `as` `>>`(Cast) `shl` `shr` |
| 17 | `%` `mod` |
| 19 | `*` `/` |
| 21 | `**`(MatMul) `><`(Fma) |
| 23 | `^`(Power), **right-assoc** (`rbp = 22`) |

`parse_infix_make` chọn AST: `Compare` / `PatternExpr` / `BinOp` (+ op đúng).

### Prefix / postfix (vẫn RD, không nằm trong bảng infix)

- **Prefix (`parse_unary`):** `-` `not`/`!` `~` `&` `&mut` `precomp` `recv` `await` …
- **Postfix (sau `parse_primary`):** `?.` `.` method-call `~mask` `!!` `?`

Primary: literal, ident/call/entity-lit, `(…)` / tuple, `[…]` / dict, interp string, builtins, …

---

## 8. AST bump-pointer arena (gated)

Infra bump cho `children` vectors:

| Symbol | Vai trò |
|--------|---------|
| `AST_BUMP_BYTES` | 8 MiB slab |
| `AST_BUMP_ENABLED` | **0** = heap path (mặc định production); **1** = bump |
| `ast_vec_bump_alloc` / `ast_vec_bump_new` | cấp vec header+data trong slab, align 8 |
| `ast_vec_push` | grow-in-slab hoặc fallback `vec_new_rt` khi đầy |
| `ast_arena_begin` / `ast_arena_end` | reset watermark mỗi `parse_program` |

Khi `AST_BUMP_ENABLED == 0` (hiện tại):

- `ast_new` → `vec_new_rt()`
- `ast_add_child` → `vec_push_rt(parent.children, child)` trực tiếp (không wrapper)

Khi bật (`== 1`): child vec lấy từ slab; overflow copy sang heap vec.

Node entity `AstNode` vẫn là soft aggregate; arena chỉ sở hữu **children buffers**.

---

## 9. Parse control / recovery (đã có sẵn, vẫn dùng)

- `skip_newlines`, `match_list_sep` (`,` / `;` / NEWLINE)
- `expect_block_end` + `sync_past_block_end`
- `parse_program`: nếu statement không tiến `pos` → force `advance`; nếu có `error_msg` → log + resync tới top-level keyword
- Generic call lookahead index-only: `try_skip_generic_call_args` (tránh mutate Parser aggregate trên C-VM)

---

## 10. Complexity / operational notes

| Algorithm | Complexity | Ghi chú |
|-----------|------------|---------|
| ASCII / single-char lookup | O(1) / byte | bảng 256 |
| Keyword span match | O(K · L) | K = số keyword, L = độ dài word |
| WS bulk scan | O(n/8) best, O(n) tail | chỉ SP/TAB/CR |
| Lexeme materialize | O(span) | mỗi lần `token_lexeme` |
| Pratt | O(tokens trong expr) | một pass, Power right-assoc |
| Bump alloc (khi bật) | O(1) bump | fallback heap khi slab đầy |

C-VM: tránh nested CALL đẩy soft `AstNode` qua wrapper thừa khi arena tắt — đường `vec_push_rt` trực tiếp là đường ổn định.

---

## 11. Pipeline vị trí

```
source
  → fat_str_sentinel_pad
  → tokenize (DFA class + single-char + span keywords + WS bulk + trivia)
  → Parser tokens
  → parse_program (arena begin/end)
       → statements (RD)
       → expressions (Pratt parse_expr_bp)
  → AstNode tree → semantic / MIR …
```

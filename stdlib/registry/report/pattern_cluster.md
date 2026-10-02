# Report — pattern / regex / virgex

**Registry:** [`../pattern.md`](../pattern.md) · [`../regex.md`](../regex.md) · [`../virgex.md`](../virgex.md)

## Include (`stdlib/stdlib.vri`)

| Module | `include` |
|---|---|
| Pattern core | `include pattern` |
| Regex frontend | `include regex` |
| Virgex frontend | `include virgex` |

Không dùng `include virgex.virgex` / `include regex.regex`.

## Naming (locked)

- Namespace dot: `virgex.compile`, `regex.findAll`
- Multiword camelCase: `fullMatch`, `isMatch`, `findAll`, `replaceAll`, `extractAll`
- Types PascalCase: `Pattern`, `Match`, `Iterator`
- Internal: `_patternReplace`, `_patternFindMatch`, `_regexCompile`, `_virgexCompile`
- `pattern.advance` (iterator step); registry alias `pattern.next` → `advance` until parser allows `next` as method name

## Surface

```vir
let p = virgex.compile("| @0!3 |")
p.fullMatch("123")
p.findAll("abc123def")
virgex.replace(p, text, rep)   # hoặc p.replace(text, rep)

regex.compile("^[0-9]+$")
regex.fullMatch(pat, text)
```

Đã gỡ public snake (`find_all`, `virgex_fullmatch`, …) và UFCS free `match(text, pat)`.

## Compile note

Một số đường `str_concat` trong `_patternReplace*` có thể báo **E3007** trên `bin/virc` hiện tại — lỗi typing/string helper có sẵn, không rollback API. Smoke binary cũ vẫn chạy cho đến khi promote compiler/stdlib khớp.

## Tests migrated

- `tests/strict_v2/test_pattern_virgex_regex_equiv.vri` — entity + namespace
- `test_virgex_e2e_compiler.vri`, `test_virgex_multilingual_integration.vri` — `virgex.fullMatch(virgex.compile(...), ...)`
- `tests/virgex_{phone,email,date}.vri`, `stdlib/vir/test/virgex_vtest.vri`

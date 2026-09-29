# Report — String cluster

**Registry:** [`../string.md`](../string.md) · [`../builder.md`](../builder.md) · [`../char.md`](../char.md) · [`../unicode.md`](../unicode.md) · [`../collation.md`](../collation.md) · [`../grapheme.md`](../grapheme.md) · [`../normalize.md`](../normalize.md) · [`../encode.md`](../encode.md)  
**Status:** design **closed**; compile mostly **blocked** by fat-string ABI

## Scope

| Module | Source |
|---|---|
| `string` | `str/string.vri` |
| `builder` | `str/builder.vri` |
| `char` | `str/char.vri` |
| `unicode` | `str/unicode.vri` |
| `collation` | `str/collation.vri` |
| `grapheme` | `str/grapheme.vri` |
| `normalize` | `str/normalize.vri` |
| Unicode `encode` | `str/encode.vri` — **clash** with flat `encode` → `encode/encode.vri` |

## Compile smoke

| Module | Result | Notes |
|---|---|---|
| `char` | **OK** | |
| `string` | FAIL | E3008 `char_len` / `byte_len` |
| `builder` | FAIL | via string |
| `encode` (flat) | FAIL | via string |
| `unicode` | FAIL | E1004 `*` |
| `collation` | FAIL | via string |
| `grapheme` / `normalize` | FAIL | E1001 |

## Naming

```text
string.len / string.slice / builder.append / char.isAscii
unicode.decode / grapheme.count / normalize.nfc
```

Public `str_*` is migration debt — registry wants `string.*`.

## Verdict

Docs closed under Decision B1 (pre-UCD). First fix: soft vs fat string entity fields so `string`/`builder` include. Resolve `encode` name collision (Unicode bridges vs wire base64/hex).

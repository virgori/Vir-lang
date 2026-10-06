# Report — Format / parse / fmt

**Registry:** [`../format.md`](../format.md) · [`../parse.md`](../parse.md) · [`../fmt.md`](../fmt.md)  
**Updated:** 2026-09-30 (pass 2)

- **fmt parser fix:** never name parameters `end` (keyword clash → E1001).
- **fmt:** full `$` renderer restored; `FmtArgTag` + ptr template scan; `fmt_must` before entity methods.
- **Tests:** `test/parse_fmt_vtest.vri` (standalone `main`, exit codes 1–4) + `test.parse_fmt` in `stdlib.vri`.
- **fmt:** renderer uses `vec` + `str_join` (avoids `str_concat` move loop); `FmtArgTag` numeric tags.
- **test.vri:** renamed `TestCase.func` → `run_fn` (keyword clash); vtest `run_fn` param aligned.
- **parse:** semantic clean standalone; full link blocked on **`string.vri` E3008** + namespace `var` **E5013** (compiler).

## Delivered (source)

| Module | Path | Registry surface |
|---|---|---|
| `format` | `vir/io/format.vri` | `FormatNamespace` / `format.*` — int, intRadix, hex, bin, oct, bool, pad*, `floatFixed` (planned gate) |
| `parse` | `vir/str/parse.vri` | `ParseNamespace` / `parse.int`, `parse.intRadix` → `Result` + strict grammars |
| `fmt` | `vir/fmt/fmt.vri` | `FmtNamespace` / `fmt.int|str|bool|format|printf|printfln`; `$` / `$(n:spec)` / `$$`; `Result` errors |

**`stdlib.vri`:** `parse = str/parse.vri` added.

**Migration:** `str_to_i64` → `parse.int` (fail → `0` compat). Call sites use `format.*`, `fmt.*`. `codegen/arm64.vri` → `$0` templates + `fmt_must*`. Removed public `format_*` / `{}` template API.

## Planned (registry — not implemented)

| API | Reason |
|---|---|
| `format.float` / `parse.float` | Float gate F1–F6 |
| `fmt.float` | Waits on `format.float` |
| `types.parse_int` → `parse.int` | Compiler bootstrap / circular include — audit call-sites before swap |

## Compile smoke (2026-09-30)

| Target | Parse | Semantics |
|---|---|---|
| `str/parse.vri` | PASS | PASS (lowers to LIR; no `main`) |
| `io/format.vri` | PASS | Blocked transitive `string.vri` |
| `fmt/fmt.vri` | PASS | Blocked transitive `string.vri` |
| `str/string.vri` + `parse` | — | Cycle avoided (`parse` does not include `string`) |

Command: `bin/virc stdlib/vir/str/parse.vri -o /tmp/parse_smoke`

## Usage (canonical)

```vir
include format
import format from format
format.hex(255)

include parse
import parse from parse
case parse.intRadix("0xff", 16)
    Result.Ok(n): …
    Result.Err(_): …
end

include fmt
import fmt from fmt
args = vec_new of (FmtArg)()
vec_push of (FmtArg)(&args, fmt.int(42))
case fmt.format("val=$0", args)
    Result.Ok(s): …
end
```

## Next

1. Contract vtests for parse matrix + fmt `$` errors when compile unblocks.  
2. Wire `types.parse_int` / compiler partial parsers per `parse.md` audit.  
3. Close float gate → `format.float` + `parse.float` + `fmt.float`.

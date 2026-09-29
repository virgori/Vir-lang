# Implementation status — wave env / json / io / cli (+ crypto/tls docs)

**Wave start:** 2026-09-29  
**Policy:** CORE SPEC / registry names are canonical; old names may remain as
migration aliases. No claim of API `stable`.

| Module | Registry | Canonical source | Progress | Notes |
|---|---|---|---|---|
| env | [`../env.md`](../env.md) | `stdlib/vir/env.vri` (+ sync `env/env.vri`) | **done (wave)** | `unwrapOr` (SPEC `or` = keyword); `int`/`bool` → `Option` |
| json | [`../json.md`](../json.md) | `stdlib/vir/json.vri` (+ sync `data/json.vri`) | **done (wave)** | `parse`/`stringify`; `at` → `Option`; camelCase; `asArray`/`asObject` |
| io | [`../io.md`](../io.md) | `stdlib/vir/io/stdio.vri` (console) · `rt/io.vri` (low-level) | **partial** | `as ptr` FFI; soft `cstr_to_str`; remount `io` **blocked** |
| cli | [`../cli.md`](../cli.md) | `stdlib/vir/cli.vri` (new) | **done (wave)** | ask/confirm/choose/multi; password echo-off (Darwin ioctl); `io.print` not builtin `print` |
| crypto | [`../crypto.md`](../crypto.md) | `stdlib/vir/crypto/*` | **docs draft** | experimental; compile blocked; harden hash→hmac→rng first — [`crypto.md`](crypto.md) |
| tls | [`../tls.md`](../tls.md) | `stdlib/vir/tls/*` | **docs draft** | native `native_tls_*` boundary; not pure-Vir crypto |

## Blockers

1. **`io` module remount** — `stdlib.vri` maps `io` → `rt/io.vri` (compiler
   `print_str` / file helpers). Public console APIs live on `stdio` until a
   coordinated remount (`io` → facade, `rt.io` → low-level).
2. **crypto / tls compile** — entity `[int; N]`, legacy `extern`, string ABI,
   undeclared RNG/TLS native symbols; entire tree experimental.
3. **json ownership / float Number / error→Error** — still design gates; this
   wave only naming + `at` Option + array/object views.

## Next after this wave

- Remount console `io` safely  
- csv (Q7)  
- Dedup `json.vri` / `data/json.vri` load paths at resolver level  
- Implement milestone: `crypto.hash` → `hmac` → `rng` (compile + vectors + FFI)  

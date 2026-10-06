# Implementation status — wave env / json / io / cli (+ crypto/tls docs)

**Wave start:** 2026-09-29  
**Policy:** CORE SPEC / registry names are canonical; old names may remain as
migration aliases. No claim of API `stable`.

| Module | Registry | Canonical source | Progress | Notes |
|---|---|---|---|---|
| env | [`../env.md`](../env.md) | `stdlib/vir/env.vri` (+ sync `env/env.vri`) | **done (wave)** | `unwrapOr` (SPEC `or` = keyword); `int`/`bool`/`get`/`require` → `Option of` / `Result of` |
| http | [`../http.md`](../http.md) | `stdlib/vir/http/http.vri` | **stable** | Wave + e2e PASS |
| url | [`../url.md`](../url.md) | `stdlib/vir/url.vri` + `net/url.vri` | **stable** | Wave PASS |
| csv | [`../csv.md`](../csv.md) | `stdlib/vir/csv.vri` | **stable** | Wave PASS |
| cors | [`../cors.md`](../cors.md) | `stdlib/vir/cors/cors.vri` | **stable** | Wave PASS |
| net | [`../net.md`](../net.md) | `stdlib/vir/net/net.vri` | **stable** | TCP + resolve smoke |
| string | [`../string.md`](../string.md) | `stdlib/vir/str/string.vri` | **stable** | `string.*` namespace + matrix |
| buffer | [`../buffer.md`](../buffer.md) | `stdlib/vir/mem/buffer.vri` | **stable** | `buffer.*` namespace + matrix |
| json | [`../json.md`](../json.md) | `stdlib/vir/data/json.vri` | **stable** | single owner + matrix |
| crypto | [`../crypto.md`](../crypto.md) | `stdlib/vir/crypto/{hash,hmac,rng}.vri` | **core stable** | hash/hmac/rng smokes; rest experimental |
| io | [`../io.md`](../io.md) | `stdlib/vir/io/stdio.vri` (console) · `rt/io.vri` (low-level) · `io/{traits,file,buffered}.vri` | **partial** | `Result of`/`Option of` on traits/file/buffered; soft `cstr_to_str`; remount `io` **blocked** |
| cli | [`../cli.md`](../cli.md) | `stdlib/vir/cli.vri` (new) | **done (wave)** | ask/confirm/choose/multi; `Vec of (string)`/`Vec of (int)`; password echo-off (Darwin ioctl) |
| crypto | [`../crypto.md`](../crypto.md) | `stdlib/vir/crypto/*` | **docs draft** | experimental; compile blocked; harden hash→hmac→rng first — [`crypto.md`](crypto.md) |
| tls | [`../tls.md`](../tls.md) | `stdlib/vir/tls/*` | **docs draft** | native `native_tls_*` boundary; not pure-Vir crypto |
| time | [`../time.md`](../time.md) | `stdlib/vir/time/time.vri` | **done (wave)** | SCHEMA registry; `time.*` only; mono `int` ns; sleep → `Result`; libc clocks — [`report/time.md`](time.md) |

**Generic syntax (locked):** `Name of (...)` — see [`generics_of.md`](generics_of.md).
Library + registry migrated; compiler acceptance deferred.

## Remaining libraries (audit 2026-09-29)

Full rollup: [`AUDIT.md`](AUDIT.md) · inventory: [`INVENTORY.md`](INVENTORY.md)

| Cluster | Report | Smoke highlights |
|---|---|---|
| Collections | [`collections.md`](collections.md) | `vec` OK; map/set/deque/buffer/slice FAIL |
| Core | [`core.md`](core.md) | `option`/`result` OK |
| String | [`string_cluster.md`](string_cluster.md) | `char` OK; fat-string ABI blocks rest |
| FS/OS | [`fs_os.md`](fs_os.md) | `fs` OK; path/process FAIL |
| Format | [`format_cluster.md`](format_cluster.md) | parse/fmt implemented; link blocked |
| Path / encode | [`path_encode_wave.md`](path_encode_wave.md) | `path.*`, `fs.isFile/isDir`, dual `encode` namespaces |
| Pattern | [`pattern_cluster.md`](pattern_cluster.md) | registry draft · [`pattern`](../pattern.md) / [`regex`](../regex.md) / [`virgex`](../virgex.md) · source snake_case |
| Data/encoding | [`data.md`](data.md) | base64/hex/csv/toml/xml/yaml/ini/url OK |
| Net/web | [`net.md`](net.md) | no registry; net/http FAIL |
| Concurrency | [`concurrency.md`](concurrency.md) | no registry; blocked |
| Misc | [`misc.md`](misc.md) | math/regex OK; rand ≠ CSPRNG |

## Blockers

1. **`io` module remount** — `stdlib.vri` maps `io` → `rt/io.vri` (compiler
   `print_str` / file helpers). Public console APIs live on `stdio` until a
   coordinated remount (`io` → facade, `rt.io` → low-level).
2. **crypto / tls compile** — entity `[int; N]`, legacy `extern`, string ABI,
   undeclared RNG/TLS native symbols; entire tree experimental.
3. **json ownership / float Number / error→Error** — still design gates; this
   wave only naming + `at` Option + array/object views.
4. **Fat-string ABI** — blocks `string`/`builder`/many dependents (`char_len`/`byte_len`).
5. **Missing registry** for high-traffic modules — net/http/rand/csv/… (see inventory); **`time` closed this wave**.

## Next after this wave

- Remount console `io` safely  
- csv (Q7) + data-format registries (encode/base64/hex dedup)  
- Dedup `json.vri` / `data/json.vri` load paths at resolver level  
- Implement milestone: `crypto.hash` → `hmac` → `rng` (compile + vectors + FFI)  
- Fix fat-string fields so string cluster includes  
- Collections: map → set after `str_new` / entity field fix  

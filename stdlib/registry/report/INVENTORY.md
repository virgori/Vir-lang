# Inventory — `stdlib/vir/` vs registry

Top-level dirs under `stdlib/vir/` with **no** `registry/<dirname>.md`:

```text
ai, archive, ast, async, auth, bench, build, chrono, codegen, collections,
compiler, compress, config, core, csv, data, datetime, db, debug, doc,
doctest, embedded, encoding, event, ffi, func, glob, gpu, gui, http, hw,
image, iot, iter, jit, lang, locale, log, lsp, math, mem, net, observability,
os, parser_kit, pattern, pkg, profile, rand, reflect, regex, rt, schedule,
semver, serde, sort, sql, str, sync, term, test, thread, time, token, toml,
url, uuid, virgex, viron, vss, wasm, web, wir, yaml
```

Covered by **flat** registry names (not dir-named):

| Dir | Registry modules |
|---|---|
| `collections/` | `vec` `map` `set` `deque` |
| `core/` | `option` `result` |
| `str/` | `string` `builder` `char` `unicode` `collation` `grapheme` `normalize` (+ `encode.md` for Unicode bridges) |
| `mem/` | `buffer` `slice` |
| `error/` | `error` `panic` |
| `io/` | `format` (+ `io` report) |

**Special:** `chrono/` — prompt/docs only, no `.vri`.

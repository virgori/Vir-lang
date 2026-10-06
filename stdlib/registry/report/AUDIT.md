# Stdlib audit rollup — remaining libraries

**Date:** 2026-09-29  
**Branch wave:** docs SSOT after env/json/io/cli/crypto/tls  
**Compiler:** native `bin/virc` (`include <module>` smoke = empty `main`)

> Registry **design-closed** ≠ compile-clean ≠ production-ready.  
> Excluded (already reported): [`env`](env.md) · [`json`](json.md) · [`io`](io.md) · [`cli`](cli.md) · [`crypto`](crypto.md).

## Cluster index

| Cluster | Report | Registry? | Compile smoke (summary) |
|---|---|---|---|
| Collections | [`collections.md`](collections.md) | core closed; deferred no | `vec` OK · map/set/deque/buffer/slice FAIL |
| Core | [`core.md`](core.md) | option/result/error/panic closed | `option`/`result` OK · `error` FAIL · `panic` unresolved |
| String | [`string_cluster.md`](string_cluster.md) | closed | `char` OK · rest mostly FAIL (fat-string ABI) |
| FS / path / process | [`fs_os.md`](fs_os.md) | closed | `fs` OK · path/process E1001 |
| Format / parse / fmt | [`format_cluster.md`](format_cluster.md) | closed | all FAIL / unresolved |
| Data / encoding | [`data.md`](data.md) | none (except encode clash) | base64/hex/csv/toml/xml/yaml/ini/url **OK** |
| Net / web | [`net.md`](net.md) | none | net/http FAIL |
| Concurrency | [`concurrency.md`](concurrency.md) | none | async/thread/sync FAIL |
| Misc | [`misc.md`](misc.md) | none | math/regex OK · rand/time/uuid/auth FAIL |

## Production gates (shared)

A module is not “shipped” until:

1. Registry contract exists and is closed for the public surface  
2. `include` smoke passes on native `virc`  
3. Type + borrow checks clean for public APIs  
4. Ownership/lifetime documented  
5. Tests call **production** modules (not fork copies)  
6. Native FFI (if any) link + runtime tested  

`closed` in registry frontmatter means **docs design closed**, not gates 2–6.

## Naming

New public APIs: **dot style** (`module.function`). Legacy `snake` free functions are migration debt, not canonical.

## No-registry top-level dirs (73)

See [`INVENTORY.md`](INVENTORY.md). Highest-traffic gaps for a later SSOT wave:

```text
net · http · rand · time · datetime · math · uuid · regex · async · thread
csv · toml · xml · yaml · url · base64 · hex · auth · serde · sql
```

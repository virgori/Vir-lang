# Report — Misc public modules

**Registry:** **missing** for all below  
**Status:** mixed compile; none production-gated

## Compile smoke

| Module | Result | Notes |
|---|---|---|
| `math` | **OK** | flat → `math/basic.vri`; large `math.*` tree unchecked |
| `regex` | **OK** | thin over `pattern` |
| `rand` | FAIL E1001 | **Not CSPRNG** — see crypto SSOT |
| `time` | FAIL E1001 | |
| `datetime` | FAIL E0001 lexer | |
| `uuid` | FAIL E1001 | |
| `auth` | FAIL E1001 | oauth2 only; blocked by crypto |
| `serde` / `sql` | FAIL E1001 | |
| `db` / `compress` / `log` / `term` | FAIL E2102 | no flat include |
| `archive` | FAIL E1001 | |
| `glob` | FAIL E2113 | selective import |
| `virgex` | unchecked | prefer for Vir-native patterns |

## Security

```text
rand.*     → simulation / games only
crypto.rng → keys, nonces, tokens, PKCE
```

## Verdict

`math` + `regex` are include-healthy starters for a misc SSOT wave. `rand` must stay outside crypto guarantees. `auth` waits on `crypto.hash` / `crypto.rng`.

# Report — `crypto` / `tls`

**Wave:** docs SSOT (experimental tree)  
**Registry:** [`../crypto.md`](../crypto.md) · [`../tls.md`](../tls.md)  
**Source:** `stdlib/vir/crypto/*`, `stdlib/vir/tls/*`, crypto-adjacent `auth` / `rand` / encoding

> Status: **experimental / not production-ready** — registry **draft**, not design-closed for ship.

## Scope summary

| Group | Modules | Notes |
|---|---|---|
| Crypto core | `crypto` + `crypto.*` (14 files) | umbrella + modular |
| TLS | `tls`, `tls.cert` | native FFI boundary |
| Auth | `auth` (oauth2) | blocked by crypto umbrella |
| Non-crypto RNG | `rand` | never for secrets |
| Encoding | `base64` / `hex` / `encoding.*` | compile OK; not crypto |

## Naming (canonical)

Dot style only for new public API — see registry. Examples:

```text
crypto.hash.sha256
crypto.hmac.verify
crypto.rng.bytes
crypto.subtle.equal
tls.connect
tls.cert.parse
```

## Compile (audit)

Almost all `crypto.*` / `tls` / `auth` **blocked** on native `virc` (entity
`[int; N]`, extern syntax, string ABI, deps). Encoding smoke **done**.

## Security posture (source)

| Area | Behavior |
|---|---|
| Ed25519 | fail-closed (no usable sign / verify success) |
| X.509 validate | fail-closed stub |
| HMAC verify | CT-style compare (needs validation) |
| RNG | OS/`/dev/urandom` intent; FFI symbols undeclared in-tree |
| `rand` | xoshiro — out of crypto |
| TLS | `native_tls_*` → platform TLS |

## First milestone

```text
crypto.hash → crypto.hmac → crypto.rng
```

Must: compile, registry names, production-module vectors, FFI/link honesty.

## Files written

| Path | Role |
|---|---|
| `stdlib/registry/crypto.md` | SSOT crypto |
| `stdlib/registry/tls.md` | SSOT TLS |
| `stdlib/registry/report/crypto.md` | this progress note |

## Next (implementation — not this docs wave)

1. Fix parse/`[int; N]` / extern so `hash`/`hmac`/`rng` include  
2. Provide or stub-document `native_getrandom` link tests  
3. Wire NIST/RFC vectors to **production** modules  
4. Close registry areas one-by-one (no silent `stable`)  

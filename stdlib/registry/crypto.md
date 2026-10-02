---
module: crypto
title: Crypto
summary: >-
  Experimental cryptographic primitives and helpers — hash/hmac/rng first;
  AEAD, signatures, X.509, JWT remain experimental or fail-closed.
source:
  - name: crypto
    path: vir/crypto/crypto.vri
  - name: crypto.mod
    path: vir/crypto/mod.vri
  - name: crypto.hash
    path: vir/crypto/hash.vri
  - name: crypto.hmac
    path: vir/crypto/hmac.vri
  - name: crypto.rng
    path: vir/crypto/rng.vri
  - name: crypto.subtle
    path: vir/crypto/subtle.vri
  - name: crypto.aes
    path: vir/crypto/aes.vri
  - name: crypto.chacha20
    path: vir/crypto/chacha20.vri
  - name: crypto.ed25519
    path: vir/crypto/ed25519.vri
  - name: crypto.x25519
    path: vir/crypto/x25519.vri
  - name: crypto.rsa
    path: vir/crypto/rsa.vri
  - name: crypto.pbkdf2
    path: vir/crypto/pbkdf2.vri
  - name: crypto.jwt
    path: vir/crypto/jwt.vri
  - name: crypto.x509
    path: vir/crypto/x509.vri
status: stable
aliases: []
notes: >-
  Core stable: crypto.hash / crypto.hmac / crypto.rng (smoke tests in stdlib/vir/test).
  AES, Ed25519, JWT, X.509, RSA, … remain experimental (fail-closed where noted).
---

# Crypto

Cryptographic **primitives and protocol helpers** under the public `crypto.*`
namespace. Physical layout is `stdlib/vir/crypto/*.vri` (see front matter).

**Docs draft ≠ implementation certified.** Prefer audited backends
(libsodium / BoringSSL) for Ed25519, full X.509 PKI, RSA without blinding,
and timing-sensitive AES software paths — until production gates pass.

TLS → [`tls`](tls.md). Non-crypto PRNG → [`rand`](rand.md) when documented
(today: `include rand` / `vir/rand/rand.vri`). Encoding → `base64` / `hex`
(supporting only — **not** encryption).

## Boundary

| In `crypto` | Out |
|---|---|
| Hash / HMAC / CSPRNG | `rand.*` (xoshiro — never secrets) |
| AEAD / signatures / KDF / JWT / X.509 helpers | TLS handshake / sockets → [`tls`](tls.md) |
| Constant-time helpers (`subtle`) | Mach-O / linker SHA-256 (compiler internal) |
| Explicit unsafe/raw RSA | Silent “prod-safe” claims |
| | OAuth/PKCE protocol → `auth` (must call `crypto.rng` / `crypto.hash`) |

## Naming (locked for this registry)

Public API uses **dot style**:

```text
crypto.<area>.<op>
```

Rules:

- no new public `snake_case`
- do not repeat the namespace in the function name
- legacy source names (`sha256_hash`, `x509_validate`, …) are **migration**,
  not canonical
- implementation / `extern` / native symbols may keep backend names

Examples:

| Legacy / current source | Canonical (target) |
|---|---|
| `sha256_hash` | `crypto.hash.sha256` |
| `hmac_sha256_verify` | `crypto.hmac.verify` |
| `crypto_random_bytes` / `csprng_fill` | `crypto.rng.bytes` / `crypto.rng.fill` |
| `constant_time_eq` / `ct_equal` | `crypto.subtle.equal` |
| `x509_validate` | `crypto.x509.validate` |

## Public surface (target)

```text
crypto
├── hash          # harden first
│   ├── sha256
│   └── sha512
├── hmac          # harden first
│   ├── sha256
│   └── verify
├── rng           # harden first
│   ├── bytes
│   └── fill
├── subtle
│   ├── equal
│   └── select
├── aes.*         # experimental
├── chacha20.*    # experimental (prefer Poly1305 AEAD)
├── ed25519       # stub / fail-closed
│   ├── sign
│   └── verify
├── x25519
│   ├── public
│   └── shared
├── rsa.*         # unsafe / experimental — raw under rsa.raw.*
├── pbkdf2
│   └── derive
├── hkdf.*        # prefer separate from pbkdf2 if public
├── jwt
│   ├── encode
│   └── verify
└── x509
    ├── parse
    └── validate
```

```vir
include crypto.hash
include crypto.hmac
include crypto.rng

# Target calls (after API rename lands):
# crypto.hash.sha256(...)
# crypto.hmac.verify(...)
# crypto.rng.bytes(...)
```

## Contract locks (docs)

### Security

| ID | Requirement |
|---|---|
| S1 | Secret-dependent ops avoid secret-dependent compare / branch / memory access where applicable (constant-time intent). |
| S2 | Incomplete / unsupported security ops are **fail-closed** (`Err` / verification failure) — never fake success. |
| S3 | Keys, nonces, salts, tokens, PKCE verifiers use **`crypto.rng` only** — never `rand`. |
| S4 | Secret ownership and lifetime are explicit; prefer clear/zeroize when ownership allows. |
| S5 | Native backends are external trust boundaries and must be documented. |
| S6 | No silent algorithm / backend downgrade. |
| S7 | Raw / insecure primitives are visibly separated (e.g. `crypto.rsa.raw.*`). |
| S8 | Entire tree remains **experimental** until production gates pass. |

### Errors

| ID | Requirement |
|---|---|
| E1 | Fallible ops return `Result` (default error [`Error`](error.md) unless stated). |
| E2 | Stubs return `Err`, not empty/zero presented as success. |
| E3 | Invalid key / nonce / tag / cert / encoding → explicit error. |
| E4 | Native/FFI failure maps into `Result`. |
| E5 | Verification failure distinguishable from runtime/backend failure where needed. |
| E6 | No public contract based on magic integer return codes. |

### Types / bounds

| ID | Requirement |
|---|---|
| T1 | Prefer typed key / nonce / signature / digest over unchecked `Buffer → Buffer`. |
| T2 | Nonce / tag / key / digest sizes validated before use. |
| T3 | No silent integer narrowing on security sizes. |
| T4 | Algorithm mismatch must not silently succeed. |

### Borrow / ownership

Crypto does **not** bypass the Vir borrow checker.

| ID | Requirement |
|---|---|
| B1 | No conflicting mutable borrows of secret buffers. |
| B2 | Borrowed inputs cannot outlive owners; no use-after-move/free. |
| B3 | I/O aliasing forbidden unless explicitly supported. |
| O1 | Document who owns generated key/token buffers. |
| O2 | Avoid unnecessary secret copies; cleanup path for owned secrets. |

## Migration map

| Current | Canonical | Action |
|---|---|---|
| `include crypto` umbrella | `crypto.hash` / `hmac` / `rng` / … | **split**; stop new deps on umbrella |
| `sha256_hash` / `sha256_hex` | `crypto.hash.sha256` (+ hex helper or `encoding.hex`) | **rename** |
| `hmac_sha256` / `hmac_sha256_verify` | `crypto.hmac.sha256` / `crypto.hmac.verify` | **rename** |
| `csprng_fill` / `crypto_random_bytes` | `crypto.rng.fill` / `crypto.rng.bytes` | **rename** |
| `ct_equal` / `constant_time_eq` | `crypto.subtle.equal` | **rename** |
| `x509_validate` | `crypto.x509.validate` | **rename**; stay fail-closed until real verifier |
| `rsa_*_raw_unsafe` | `crypto.rsa.raw.*` | **namespace** unsafe |
| HKDF in `pbkdf2.vri` | `crypto.hkdf.*` | **split** when public |
| `auth` → `include crypto` | `crypto.rng` + `crypto.hash` | **migrate** |

## Compile inventory (native `bin/virc`, verified 2026-09-29)

| Module | Compile | Runtime vectors | Maturity |
|---|---|---|---|
| `crypto.hash` | **PASS** | NIST empty/abc/56-byte + double-finish | experimental |
| `crypto.hmac` | **PASS** | RFC 4231 case 1 + verify negatives | experimental |
| `crypto.rng` | **PASS** | `/dev/urandom` non-zero + `bytes(0)` Err | experimental |
| `crypto.mod` | **PASS** | re-exports hash/hmac/rng only | experimental |
| `crypto` umbrella | blocked | legacy tree | stub/legacy |
| `crypto.subtle` | blocked | — | blocked (E2002 / `[int; N]`) |
| `crypto.aes` | blocked | — | experimental |
| `crypto.chacha20` | blocked | — | experimental |
| `crypto.ed25519` | blocked | fail-closed when usable | stub |
| `crypto.x25519` | blocked | — | experimental |
| `crypto.rsa` | blocked | — | unsafe/experimental |
| `crypto.pbkdf2` | blocked | — | experimental |
| `crypto.jwt` | blocked | — | blocked |
| `crypto.x509` | blocked | validate fail-closed | stub |
| `tls` / `tls.cert` | blocked | — | native FFI blocked |
| `auth` | blocked | — | blocked by crypto umbrella |
| `base64` / `hex` | PASS | — | supporting (not crypto) |

Encoding modules used by crypto compile smoke: **ok** (`base64` / `hex`).

## RNG source (CSPRNG)

Current production path (`vir/crypto/rng.vri`):

1. `/dev/urandom` via `sys_open` / `sys_read`

`native_getrandom` / `vir_random_bytes` are **not** declared: undeclared
`extern` aborts Darwin dyld at load even before fallback. Reintroduce only
after in-tree stubs exist and link+runtime tests pass.

Rules:

- backend failure → `Result.Err`
- **never** fall back to `rand` (xoshiro)
- buffer fully initialized before `Ok`

## Area status

### `crypto.hash` — experimental (milestone 1)

```text
crypto.hash.sha256   → sha256(data, len)   [legacy sha256_hash]
crypto.hash.sha512   → sha512(data, len)   [legacy sha512_hash]
```

Native include PASS. NIST vectors via `tests/crypto/test_hash_nist.vri`.
Streaming: `sha256_new` / `update` / `finish` with `ref` + `alloc` buffers
(finalized reuse returns zero digest). Not a security audit claim.

### `crypto.hmac` — experimental (milestone 1)

```text
crypto.hmac.sha256   → hmac_sha256(...)   # bare `sha256` clashes with hash
crypto.hmac.verify   → verify(...)
```

RFC 4231 case 1 + bad length / tampered tag. CT-style xor-accumulate compare.

### `crypto.rng` — experimental (milestone 1)

```text
crypto.rng.bytes → bytes(len) → Result
crypto.rng.fill  → fill(buf, len) → Result
```

### `crypto.subtle` — blocked

```text
crypto.subtle.equal
crypto.subtle.select
```

Small auditable CT utilities only.

### `crypto.aes` / `crypto.chacha20` — experimental

Prefer authenticated public APIs (GCM / ChaCha20-Poly1305). Strict nonce/tag
rules; no plaintext on tag failure; hardware paths documented; software AES
S-box not claimed CT without audit.

### `crypto.ed25519` — stub / fail-closed

```text
sign   → Err (or non-usable empty — must not look like success)
verify → failure / false
```

Enable only with trusted backend or complete impl + official vectors +
canonical encoding checks.

### `crypto.x25519` — experimental

Vectors, clamping, low-order policy, CT field ops, typed keys preferred.

### `crypto.rsa` — unsafe / experimental

Raw ops under `crypto.rsa.raw.*`. No prod claim without blinding / reviewed
padding story.

### `crypto.pbkdf2` — experimental

```text
crypto.pbkdf2.derive
```

Iterations / salt / output length validated. HKDF → `crypto.hkdf.*` if public.

### `crypto.jwt` — blocked

Protocol helper. No `none`, no alg confusion; verify before trusting claims;
parse ≠ verify.

### `crypto.x509` — parse partial / validate fail-closed

```text
crypto.x509.validate → failure until real verifier exists
```

Need chain, trust anchors, time, SAN/hostname, KU/EKU, signatures, basic
constraints, path length, malformed rejection.

## Tests (required)

Self-contained codegen copies of algorithms **do not** certify stdlib.

| Layer | Requirement |
|---|---|
| Compile smoke | `include crypto.hash` (etc.) production modules |
| Known-answer | Official vectors through real module |
| Negative | Bad key / sig / tag / cert |
| FFI | Link + runtime success/fail |
| Borrow/type | Misuse rejected |
| Integration | JWT / OAuth PKCE / TLS only after primitives gate |

## Production gates

A crypto area may leave **experimental** only when applicable gates pass:

1. Registry contract closed for that area  
2. Native `virc` compile clean  
3. Type + borrow clean  
4. Ownership/lifetime closed  
5. No stub success paths  
6. Official vectors via production module  
7. Negative vectors  
8. FFI link/runtime tests (if native)  
9. Security-sensitive review / audit  
10. CT review where secret-dependent arithmetic applies  
11. Backend trust boundary documented (native)  

## Priority

```text
crypto.hash → crypto.hmac → crypto.rng → crypto.subtle
  → chacha20 / aes → x25519 / ed25519 → x509 → tls → jwt / auth → rsa
```

First milestone: **hash + hmac + rng** compile, registry names, production
vectors, no hidden FFI failure.

## API index (target)

| ID | Symbol | Signature (sketch) | Status |
|---|---|---|---|
| `crypto.hash.sha256` | `crypto.hash.sha256` | `(data) -> Digest` / streaming TBD | proposed |
| `crypto.hash.sha512` | `crypto.hash.sha512` | `(data) -> Digest` | proposed |
| `crypto.hmac.sha256` | `crypto.hmac.sha256` | `(key, msg) -> Tag` | proposed |
| `crypto.hmac.verify` | `crypto.hmac.verify` | `(key, msg, tag) -> Result` / bool+Result TBD | proposed |
| `crypto.rng.bytes` | `crypto.rng.bytes` | `(n) -> Result of (Buffer)` | proposed |
| `crypto.rng.fill` | `crypto.rng.fill` | `(buf) -> Result` | proposed |
| `crypto.subtle.equal` | `crypto.subtle.equal` | `(a, b) -> bool` (CT) | proposed |
| `crypto.ed25519.sign` | `crypto.ed25519.sign` | `… -> Result of (Signature)` | planned (fail-closed now) |
| `crypto.ed25519.verify` | `crypto.ed25519.verify` | `… -> Result` / verification outcome | planned (fail-closed now) |
| `crypto.x509.validate` | `crypto.x509.validate` | `… -> Result of (Validation)` | planned (fail-closed now) |

Exact signatures lock when each area closes; prefer `Result` for all fallible
security operations (E1).

## Related

- [`tls`](tls.md) — native TLS boundary  
- Encoding: `base64` / `hex` — not crypto  
- `auth` / OAuth2 PKCE — must use `crypto.rng` + `crypto.hash`  
- `rand` — non-crypto PRNG only  

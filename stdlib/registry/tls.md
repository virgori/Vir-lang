---
module: tls
title: Tls
summary: >-
  Native-backed TLS 1.2/1.3 streams — OpenSSL/LibreSSL/BoringSSL/platform FFI;
  not a pure-Vir crypto implementation.
source:
  - name: tls
    path: vir/tls/tls.vri
  - name: tls.cert
    path: vir/tls/cert.vri
status: draft
aliases: []
notes: >-
  Docs-only SSOT. TLS is a native trust boundary. Certificate validation must
  not claim success via incomplete pure-Vir crypto.x509.validate.
  Compile currently blocked (string ABI / crypto.x509 / parser).
---

# Tls

TLS / SSL **streams and certificate material helpers**. Physical modules:
`vir/tls/tls.vri`, `vir/tls/cert.vri`.

**TLS is not evidence that the pure-Vir `crypto.*` tree is production-safe.**
Cryptographic handshake and record protection live in the native backend.

Primitives / AEAD / signatures → [`crypto`](crypto.md).  
Sockets → net / transport modules. Encoding → `base64` / `hex`.

## Boundary

| In `tls` | Out |
|---|---|
| Config, connect, accept, read/write, shutdown | Pure hash/HMAC/AEAD APIs → [`crypto`](crypto.md) |
| Cert/key/CA load paths | Full X.509 PKI policy → `crypto.x509` (until real) + backend |
| Hostname verification (required default) | Non-TLS TCP |
| | Application JWT / OAuth → `crypto.jwt` / `auth` |

## Trust boundary

```text
Vir API (tls.*)
   ↓
native_tls_*
   ↓
OpenSSL / LibreSSL / BoringSSL / platform TLS
```

Rules:

- backend identity/version documented where useful
- missing/broken native symbols → link/runtime **failure**, not silent cleartext
- backend errors map to Vir `Result`
- no silent downgrade of min version / verify flags

## Naming

Dot style:

```text
tls.connect
tls.accept
tls.cert.parse
tls.cert.validate
```

Legacy `tls_config_*` / `native_tls_*` are implementation or migration names.

## Public surface (target)

```text
tls
├── connect
├── accept
├── read / write / shutdown   # stream ops — exact names TBD at close
└── cert
    ├── parse
    └── validate              # may delegate; must not fake success
```

```vir
include tls

# tls.connect(...)
# tls.cert.parse(...)
```

## Contract locks (docs)

| ID | Requirement |
|---|---|
| L1 | Client TLS verifies peer certificates by default. |
| L2 | Hostname verification **mandatory** for client TLS unless an explicitly unsafe API disables it. |
| L3 | Certificate validation must not rely on incomplete `crypto.x509.validate` claiming success. |
| L4 | Fallible ops return `Result`. |
| L5 | Connection / config ownership and free/shutdown paths documented. |
| L6 | Supported targets and required native libs documented. |
| L7 | Linker + runtime FFI tests required before “usable”. |

## Migration map

| Current | Canonical | Action |
|---|---|---|
| `tls_config_new` / `tls_config_client` / `tls_config_server` | `tls` config constructors (names TBD) | **rename** when surface closes |
| `native_tls_connect` / `accept` / `read` / `write` | internal FFI | keep private |
| `tls_cert_*` | `tls.cert.*` | **rename** |
| `x509_validate` via pure Vir | must fail-closed until real PKI | see [`crypto`](crypto.md) |

## Compile / FFI inventory

| Module | Status | Notes |
|---|---|---|
| `tls` | blocked | parser/string ABI; depends on `native_tls_*` |
| `tls.cert` | blocked | `tls` + `crypto.x509` |

Implied native symbols (must link-test):

```text
native_tls_ctx_new / free
native_tls_ctx_set_min_version / set_verify
native_tls_ctx_load_ca / load_cert / load_key
native_tls_connect / accept / read / write / shutdown / free
native_tls_peer_cert_subject / get_alpn
```

## `tls.cert`

Helpers bridging PEM paths and hostname checks to TLS config.

Until X.509 validation is real (backend or complete `crypto.x509`):

- parsing helpers may exist
- **validation success is forbidden** without a complete verifier
- hostname helpers must not imply full PKI trust

## Errors

| Case | Mechanism |
|---|---|
| Load cert/key/CA failure | `Err` |
| Handshake / I/O failure | `Err` |
| Hostname / verify failure | `Err` (distinct where useful) |
| Missing native backend | link or runtime `Err` |

## Tests (required)

| Test | Requirement |
|---|---|
| FFI link | `native_tls_*` resolve |
| Runtime | connect/accept success and failure |
| Cert | bad chain / hostname rejection |
| Defaults | verify_peer / hostname on unless unsafe API |
| E2E | handshake + cert + hostname |

## Production gates

In addition to [`crypto`](crypto.md) gates where overlapping:

1. Registry contract closed  
2. Compile + type + borrow clean  
3. Native backend documented and link-tested  
4. Hostname verification default enforced  
5. No fake validation via incomplete pure-Vir X.509  
6. E2E handshake + negative cert tests  

## Related

- [`crypto`](crypto.md) — X.509 parse/validate, AEAD, RNG  
- `auth` — OAuth; not TLS  
- net / TCP — underlying transport  

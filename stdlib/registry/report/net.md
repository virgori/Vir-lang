# Report — Net / web

**Registry:** **missing** (TLS covered in [`../tls.md`](../tls.md) / [`crypto.md`](crypto.md))  
**Status:** experimental; compile **blocked**

## Scope (high level)

| Module | Source | Compile |
|---|---|---|
| `net` | `net/net.vri` | FAIL E1001 |
| `http` | `http/http.vri` | FAIL E1001 |
| `net.websocket` | `net/websocket.vri` | unchecked |
| `web.*` | cors/middleware/router/session/template | no flat `web` |
| `form` | `net/form.vri` | unchecked |

Siblings (dns, http2, quic, postgres, redis, ssh, …) — no registry.

## Naming (target)

```text
net.tcp.connect / http.get / http.post
web.router.* / tls.connect
```

## Verdict

Do not ship net/http without registry contracts + smoke. Prefer TLS hostname verify defaults from `tls.md`. Overlap between `http` local URL parse and `url` / `net.url` must be closed in SSOT.

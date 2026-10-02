---
module: cors
title: Cors
summary: CORS policy builder and preflight helpers — flat namespace cors.*
source:
  - name: cors
    path: vir/cors/cors.vri
status: stable
previous: web.cors
---

# Cors

Cross-Origin Resource Sharing configuration under **`cors`**. Public contract is
**`include cors`**, not `web.cors`.

```vir
var cfg = cors.defaults()
cors.allowOrigin(cfg, "https://example.com")
let hdrs = cors.headers(cfg, "https://example.com")

var strict = cors.create(
    "https://a.example,https://b.example",
    "GET,POST,DELETE",
    "Content-Type,Authorization"
)
let pre = cors.preflightHeaders(strict, "https://a.example", "DELETE", "Content-Type")
```

## Migration map

| Current | Public | Action |
|---|---|---|
| `cors_default` | `cors.defaults` | **rename** |
| `cors_new` | `cors.create` | **rename** |
| `cors_is_origin_allowed` | `cors.isOriginAllowed` | **rename** |
| `cors_is_method_allowed` | `cors.isMethodAllowed` | **rename** |
| `cors_headers` | `cors.headers` | **rename** |
| `cors_preflight_headers` | `cors.preflightHeaders` | **rename** |
| `cors_is_preflight` | `cors.isPreflight` | **rename** |
| `include web.cors` | `include cors` | **move** |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `cors.CorsConfig` | `cors.CorsConfig` | entity | draft |
| `cors.CorsHeaders` | `cors.CorsHeaders` | entity | draft |
| `cors.defaults` | `cors.defaults` | `cors.defaults() -> cors.CorsConfig` | draft |
| `cors.create` | `cors.create` | `cors.create(origins: string, methods: string, headers: string) -> cors.CorsConfig` | draft |
| `cors.allowOrigin` | `cors.allowOrigin` | `cors.allowOrigin(ref cfg: cors.CorsConfig, origin: string)` | draft |
| `cors.allowMethods` | `cors.allowMethods` | `cors.allowMethods(ref cfg: cors.CorsConfig, method: string)` | draft |
| `cors.credentials` | `cors.credentials` | `cors.credentials(ref cfg: cors.CorsConfig, on: bool)` | draft |
| `cors.isOriginAllowed` | `cors.isOriginAllowed` | `cors.isOriginAllowed(cfg: cors.CorsConfig, origin: string) -> bool` | draft |
| `cors.isMethodAllowed` | `cors.isMethodAllowed` | `cors.isMethodAllowed(cfg: cors.CorsConfig, method: string) -> bool` | draft |
| `cors.headers` | `cors.headers` | `cors.headers(cfg: cors.CorsConfig, origin: string) -> cors.CorsHeaders` | draft |
| `cors.preflightHeaders` | `cors.preflightHeaders` | `cors.preflightHeaders(cfg, origin, reqMethod, reqHeaders) -> cors.CorsHeaders` | draft |
| `cors.isPreflight` | `cors.isPreflight` | `cors.isPreflight(method: string, hdrs: cors.CorsHeaders) -> bool` | draft |

---

## `cors.defaults`

Permissive development defaults (`*` origin when credentials off).

---

## `cors.headers`

Response CORS header map for a request `Origin`.

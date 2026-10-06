---
module: http
title: Http
summary: HTTP/1.1 client helpers — namespace http.*; URL via url.parse.
source:
  - name: http
    path: vir/http/http.vri
  - name: static.mime
    path: vir/http/mime.vri
  - name: static.etag
    path: vir/http/etag.vri
  - name: realtime.sse
    path: vir/http/sse.vri
status: stable
---

# Http

Minimal **HTTP/1.1 client** under **`http.*`**. URL parsing:

```text
http.parseUrl(raw) -> Result of (url.Url)
```

Implementation delegates to **`url.parse`** (see [`url.md`](url.md)).

```vir
let u = http.parseUrl("https://example.com/path")
let r = http.get("http://127.0.0.1:8080/health")
```

## Boundary

| In `http` | Not in `http` |
|---|---|
| Client request / response | HTTP/2, HTTP/3 |
| `http.Method`, wire parse helpers | `protocol.*` (internal — [`protocol.md`](protocol.md)) |
| Response body as string | TLS (see `tls`) |
| | Server framework (InterVir `http/app`) |

## InterVir alignment

| InterVir | Vir stdlib |
|---|---|
| `protocol/http_status` | shared `http.status` module (`status.phrase`, `status.line`) |
| `protocol/http1_parser` | shared `http1.parser` module |
| `static/mime` | shared `static.mime` MIME lookup module (`mime.byExtension`, `mime.byFilename`) |
| `static/etag` | shared `static.etag` conditional response module |
| `transport/tcp` | `net` (TCP) — not re-exported under `http` |

## Migration map

| Legacy | Public | Action |
|---|---|---|
| `parse_url` | `http.parseUrl` | **remove** |
| `request_new` | `http.request` | **rename** |
| `http_method` / `target_url` (fields) | `httpMethod` / `targetUrl` | **rename** |
| `status_code` / `status_reason` (fields) | `statusCode` / `statusReason` | **rename** |
| `http_send` / `http_get` / `http_post` | `http.send` / `http.get` / `http.post` | **remove** free names |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `http.Method` | `http.Method` | enum | draft |
| `http.Request` | `http.Request` | entity (`httpMethod`, `targetUrl`, `body`, `extraHeaders`, `contentType`) | draft |
| `http.Response` | `http.Response` | entity (`statusCode`, `statusReason`, `body`) | draft |
| `http.request` | `http.request` | `http.request(method, targetUrl: string) -> http.Request` | draft |
| `http.requestHeader` | `http.requestHeader` | `http.requestHeader(ref req, key, value)` | draft |
| `http.requestBody` | `http.requestBody` | `http.requestBody(ref req, body: string)` | draft |
| `http.parseUrl` | `http.parseUrl` | `http.parseUrl(raw: string) -> Result of (url.Url)` | draft |
| `http.parseResponse` | `http.parseResponse` | `http.parseResponse(raw: string) -> Result of (http.Response)` | draft |
| `http.send` | `http.send` | `http.send(req: http.Request) -> Result of (http.Response)` | draft |
| `http.get` | `http.get` | `http.get(targetUrl: string) -> Result of (http.Response)` | draft |
| `http.post` | `http.post` | `http.post(targetUrl, body, contentType) -> Result of (http.Response)` | draft |
| `http.status` | `http.status` | `http.status(resp: http.Response) -> int` | draft |
| `http.statusText` | `http.statusText` | `http.statusText(resp: http.Response) -> string` | draft |

## Implementation notes

- `http.parseUrl` calls **`url.parse`** only; no second URL parser.
- Reason phrases for empty `statusReason` use `status.phrase` from the shared `http.status` module.
- **`http.send` / `http.get` / `http.post`** use **`net.tcp_connect_host`**, **`net.tcp_write_all_string`**, and **`net.tcp_read_all_string`** — no inline sockets or DNS in `http.vri`.
- Request wire encoding uses byte buffers (`vir_alloc`); do not assume C-string length for arbitrary Vir strings on the wire path.

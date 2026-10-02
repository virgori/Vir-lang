# InterVir — stdlib registry compat audit

Generated: 2026-09-30T19:21:46Z
InterVir root: `/Users/gengyang/Desktop/Repo/intervir`
Registry SSOT: `stdlib/registry/{url,json,env,string,cors,http,net}.md`

## Summary

| Cluster | Registry target | InterVir today | Action |
|---|---|---|---|
| Module includes | `include url`, `include json` | `net.url`, `data.json` | Mechanical rename |
| URL parse/query | `url.parse`, `url.queryGet` | `url_parse`, `url_query_get`, `url_get_path/query` | Wrap `Result` / namespace |
| URL/ptr strings | `string.*` on `string` | `url_str_len`, `url_copy_substr`, `url_str_eq` | Phase refactor (fat string) |
| JSON | `json.parse` | `json.read` in `http/server.vri` | 1 callsite |
| Env | `env.int` → `Option` | `rt_env_get` in `env_port` | Use `env.int` + unwrap helper |
| HTTP server | stdlib `http.*` client | **InterVir own stack** (`intervir.transport.tcp`) | Intentional — not drift |
| CORS | stdlib `cors.create(csv,...)` | **InterVir fluent CORS** + local `cors_*` helpers | Separate contract OR later adapter |
| I/O | `io.print` / `include stdio` | `print_ln` in examples | Low priority |

**Verdict:** InterVir HTTP core is coupled to **legacy `net.url` ptr helpers**, not to stable public `url.*` / `string.*`. JSON/env drift is small; URL/string surface is the main fix bucket.

## Fix order

**Wave A** — `include json` / `include url`; `json.read` → `json.parse` in `http/server.vri`.

**Wave B** — `url_parse` → `url.parse`, `url_query_get` → `url.queryGet`, `url_get_*` until accessors exist in `url.md`.

**Wave C** — Replace `url_str_len` / `url_copy_substr` / `url_str_eq` with `string.*`; drop local `str_concat`.

**Wave D** — `env_port`: `rt_env_get` → `env.int` + Option default.

**Out of scope** — InterVir fluent CORS vs stdlib `cors.create`; TCP server vs stdlib `net.*` (document separate contracts).

Re-run: `bash tools/audit_intervir_registry.sh` · gate: `STRICT=1 bash tools/audit_intervir_registry.sh`

---

## Evidence (rg)

## 1 — Legacy includes (→ `include url` / `include json`)

_none_

## 2 — JSON migration (`json.read` → `json.parse`)

_none_

## 3 — URL public legacy (`url_parse`, `url_get_*`, `url_query_get`)

```
/Users/gengyang/Desktop/Repo/intervir/http/url_registry.vri:1:# Shared URL helpers — registry-style `url.*` (no legacy `url_query_get` / `url_get_*`).
```

## 4 — URL internal ptr helpers (→ `string.*` long-term)

```
/Users/gengyang/Desktop/Repo/intervir/static/mime.vri:113:        var sub = url_copy_substr(f_addr, flen - 13, flen)
/Users/gengyang/Desktop/Repo/intervir/static/mime.vri:146:    var ext = url_copy_substr(f_addr, dot_idx + 1, flen)
/Users/gengyang/Desktop/Repo/intervir/http/server.vri:100:        this.stream.send(h1 as int, url_str_len(h1 as int))
/Users/gengyang/Desktop/Repo/intervir/http/server.vri:101:        this.stream.send(content_type as int, url_str_len(content_type as int))
/Users/gengyang/Desktop/Repo/intervir/http/server.vri:102:        this.stream.send(h2 as int, url_str_len(h2 as int))
/Users/gengyang/Desktop/Repo/intervir/http/server.vri:183:        stream.send(sl_204 as int, url_str_len(sl_204 as int))
/Users/gengyang/Desktop/Repo/intervir/http/server.vri:185:        stream.send(opt_hdrs as int, url_str_len(opt_hdrs as int))
/Users/gengyang/Desktop/Repo/intervir/http/server.vri:205:    let raw_uri = url_copy_substr(req_buf as int, vreq.vr_pstart, uri_end)
/Users/gengyang/Desktop/Repo/intervir/http/app.vri:47:    var p_len = url_str_len(pat as int)
/Users/gengyang/Desktop/Repo/intervir/http/app.vri:68:                var p_name = url_copy_substr(pat as int, start, end_pos)
/Users/gengyang/Desktop/Repo/intervir/http/app.vri:85:    var pr_len = url_str_len(prefix as int)
/Users/gengyang/Desktop/Repo/intervir/http/app.vri:86:    var pa_len = url_str_len(path as int)
/Users/gengyang/Desktop/Repo/intervir/http/app.vri:94:        var rest = url_copy_substr(path as int, 1, pa_len)
/Users/gengyang/Desktop/Repo/intervir/http/app.vri:326:            s.send(sl_204 as int, url_str_len(sl_204 as int))
/Users/gengyang/Desktop/Repo/intervir/http/app.vri:328:            s.send(opt_hdrs as int, url_str_len(opt_hdrs as int))
/Users/gengyang/Desktop/Repo/intervir/http/app.vri:348:        let raw_uri = url_copy_substr(this.req_buf as int, vreq.vr_pstart, uri_end)
/Users/gengyang/Desktop/Repo/intervir/http/app.vri:384:        var path_len = url_str_len(uri_path as int)
/Users/gengyang/Desktop/Repo/intervir/http/app.vri:451:        if match_res == ROUTE_MATCH_NONE and m_code == HTTP_GET and url_str_len(this.static_dir as int) > 0 do
/Users/gengyang/Desktop/Repo/intervir/http/app.vri:455:            if url_str_eq(uri_addr as string, "/") or url_str_eq(uri_addr as string, "") do
/Users/gengyang/Desktop/Repo/intervir/http/app.vri:459:                    rel_path = url_copy_substr(uri_addr, 1, path_len)
/Users/gengyang/Desktop/Repo/intervir/http/app_probe.vri:47:    var p_len = url_str_len(pat as int)
/Users/gengyang/Desktop/Repo/intervir/http/app_probe.vri:68:                var p_name = url_copy_substr(pat as int, start, end_pos)
/Users/gengyang/Desktop/Repo/intervir/http/app_probe.vri:84:    var l1 = url_str_len(s1 as int)
/Users/gengyang/Desktop/Repo/intervir/http/app_probe.vri:85:    var l2 = url_str_len(s2 as int)
/Users/gengyang/Desktop/Repo/intervir/http/app_probe.vri:106:    var pr_len = url_str_len(prefix as int)
/Users/gengyang/Desktop/Repo/intervir/http/app_probe.vri:107:    var pa_len = url_str_len(path as int)
/Users/gengyang/Desktop/Repo/intervir/http/app_probe.vri:115:        var rest = url_copy_substr(path as int, 1, pa_len)
/Users/gengyang/Desktop/Repo/intervir/http/app_probe.vri:297:            s.send(sl_204 as ptr, url_str_len(sl_204 as int))
/Users/gengyang/Desktop/Repo/intervir/http/app_probe.vri:299:            s.send(opt_hdrs as ptr, url_str_len(opt_hdrs as int))
/Users/gengyang/Desktop/Repo/intervir/http/app_probe.vri:319:        let raw_uri = url_copy_substr(this.req_buf as int, vreq.vr_pstart, uri_end)
/Users/gengyang/Desktop/Repo/intervir/http/app_probe.vri:354:        var path_len = url_str_len(uri_path as int)
/Users/gengyang/Desktop/Repo/intervir/http/app_test.vri:45:    var p_len = url_str_len(pat as int)
/Users/gengyang/Desktop/Repo/intervir/http/app_test.vri:66:                var p_name = url_copy_substr(pat as int, start, end_pos)
/Users/gengyang/Desktop/Repo/intervir/http/app_test.vri:82:    var l1 = url_str_len(s1 as int)
/Users/gengyang/Desktop/Repo/intervir/http/app_test.vri:83:    var l2 = url_str_len(s2 as int)
/Users/gengyang/Desktop/Repo/intervir/http/app_test.vri:104:    var pr_len = url_str_len(prefix as int)
/Users/gengyang/Desktop/Repo/intervir/http/app_test.vri:105:    var pa_len = url_str_len(path as int)
/Users/gengyang/Desktop/Repo/intervir/http/app_test.vri:113:        var rest = url_copy_substr(path as int, 1, pa_len)
/Users/gengyang/Desktop/Repo/intervir/http/app_test.vri:295:            s.send(sl_204 as ptr, url_str_len(sl_204 as int))
/Users/gengyang/Desktop/Repo/intervir/http/app_test.vri:297:            s.send(opt_hdrs as ptr, url_str_len(opt_hdrs as int))
/Users/gengyang/Desktop/Repo/intervir/http/app_test.vri:317:        let raw_uri = url_copy_substr(this.req_buf as int, vreq.vr_pstart, uri_end)
/Users/gengyang/Desktop/Repo/intervir/http/app_test.vri:352:        var path_len = url_str_len(uri_path as int)
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:61:        if url_str_eq(cur, name) do
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:93:        out url_copy_substr(this.url_buf as int, start, start + len)
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:115:        out url_copy_substr(this.url_buf as int, start, start + len)
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:140:                var vl = url_str_len(vs as int)
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:181:                if url_str_eq(vs, "true") or url_str_eq(vs, "1") do
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:184:                if url_str_eq(vs, "false") or url_str_eq(vs, "0") do
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:218:        if url_str_eq(k_str, key) do
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:240:        if url_str_eq(k_str, key) do
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:325:        this.stream.send(sl as ptr, url_str_len(sl as int))
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:326:        var b_len = url_str_len(body as int)
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:328:        this.stream.send(hdrs as ptr, url_str_len(hdrs as int))
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:359:        this.stream.send(sl as ptr, url_str_len(sl as int))
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:360:        var b_len = url_str_len(body as int)
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:362:        this.stream.send(hdrs as ptr, url_str_len(hdrs as int))
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:390:        this.stream.send(h1 as ptr, url_str_len(h1 as int))
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:391:        this.stream.send(content_type as ptr, url_str_len(content_type as int))
/Users/gengyang/Desktop/Repo/intervir/http/context_probe.vri:392:        this.stream.send(h2 as ptr, url_str_len(h2 as int))
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:99:    out url_copy_substr(this.url_buf as int, start, start + len)
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:138:    out url_copy_substr(this.url_buf as int, start, start + len)
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:180:            var vl = url_str_len(vs as int)
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:231:            if url_str_eq(vs, "true") or url_str_eq(vs, "1") do
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:234:            if url_str_eq(vs, "false") or url_str_eq(vs, "0") do
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:276:        if url_str_eq(k_str, key_addr as string) do
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:298:        if url_str_eq(k_str, key) do
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:329:    if url_str_len(static_root as int) > 0 do
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:341:    var flen = url_str_len(file_path as int)
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:343:        var pref = url_copy_substr(file_path as int, 0, 11)
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:344:        if url_str_eq(pref, "iching-vir/") do
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:345:            var stripped = url_copy_substr(file_path as int, 11, flen)
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:434:        var b_len = url_str_len(body as int)
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:436:        this.stream.send(hdrs as int, url_str_len(hdrs as int))
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:464:        var b_len = url_str_len(body as int)
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:466:        this.stream.send(hdrs as int, url_str_len(hdrs as int))
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:490:        this.stream.send(hdrs as int, url_str_len(hdrs as int))
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:528:        this.stream.send(hdrs as int, url_str_len(hdrs as int))
/Users/gengyang/Desktop/Repo/intervir/http/context.vri:551:        this.stream.send(s as int, url_str_len(s as int))
/Users/gengyang/Desktop/Repo/intervir/middleware/rate_limit.vri:51:    let key_len: int = url_str_len(key_addr)
/Users/gengyang/Desktop/Repo/intervir/middleware/rate_limit.vri:139:                if url_str_eq(stored_key_ptr as string, key_addr as string) do
/Users/gengyang/Desktop/Repo/intervir/middleware/rate_limit.vri:159:        let str_len: int = url_str_len(src_addr)
/Users/gengyang/Desktop/Repo/intervir/middleware/rate_limit.vri:234:                if url_str_eq(stored_key_ptr as string, key_addr as string) do
/Users/gengyang/Desktop/Repo/intervir/middleware/rate_limit.vri:259:                if url_str_eq(stored_key_ptr as string, key_addr as string) do
/Users/gengyang/Desktop/Repo/intervir/middleware/rate_limit.vri:275:    if url_str_len(client_key as int) == 0 do
/Users/gengyang/Desktop/Repo/intervir/middleware/rate_limit.vri:278:    if url_str_len(client_key as int) == 0 do
/Users/gengyang/Desktop/Repo/intervir/middleware/rate_limit.vri:281:    if url_str_len(client_key as int) == 0 do
/Users/gengyang/Desktop/Repo/intervir/middleware/cors.vri:391:    ctx.stream.send(sl as int, url_str_len(sl as int))
/Users/gengyang/Desktop/Repo/intervir/middleware/cors.vri:393:    ctx.stream.send(h1 as int, url_str_len(h1 as int))
/Users/gengyang/Desktop/Repo/intervir/middleware/cors.vri:395:    ctx.stream.send(h2 as int, url_str_len(h2 as int))
/Users/gengyang/Desktop/Repo/intervir/middleware/cors.vri:397:    ctx.stream.send(h3 as int, url_str_len(h3 as int))
/Users/gengyang/Desktop/Repo/intervir/middleware/cors.vri:399:    ctx.stream.send(h4 as int, url_str_len(h4 as int))
/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_protocol_http1_serializer.vri:7:    if url_str_eq(phrase200, "OK") == false do
/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_protocol_http1_serializer.vri:12:    if url_str_eq(phrase404, "Not Found") == false do
/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_protocol_http1_serializer.vri:17:    if url_str_eq(phrase502, "Bad Gateway") == false do
/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_protocol_http1_serializer.vri:22:    if url_str_eq(line, "HTTP/1.1 200 OK\r\n") == false do
/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_protocol_http1_serializer.vri:27:    if url_str_eq(line404, "HTTP/1.1 404 Not Found\r\n") == false do
/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_protocol_http1_serializer.vri:32:    if url_str_eq(ce, "0\r\n\r\n") == false do
```

## 5 — Env bypass (`rt_env_*` vs registry `env.*`)

_none_

## 6 — Duplicate string helpers (`str_concat` vs `string.concat`)

```
/Users/gengyang/Desktop/Repo/intervir/http/app.vri:80:func str_concat(s1: string, s2: string) -> string:
/Users/gengyang/Desktop/Repo/intervir/http/app_probe.vri:80:func str_concat -> string:
/Users/gengyang/Desktop/Repo/intervir/http/app_test.vri:78:func str_concat -> string:
```

## 7 — Examples I/O (`print_ln` / `print_str`)

```
/Users/gengyang/Desktop/Repo/intervir/examples/hello-vir/main.vri:9:    print_ln("hello from InterVir app");
```

## 8 — InterVir CORS exports (not stdlib `cors.*`)

```
/Users/gengyang/Desktop/Repo/intervir/middleware/cors.vri:429:func cors_config_create(origins: ptr, methods: ptr, headers: ptr, expose: ptr, creds: int, max_age: int) -> Cors:
/Users/gengyang/Desktop/Repo/intervir/middleware/cors.vri:440:func cors_is_origin_allowed(cfg: Cors, origin: ptr) -> int:
/Users/gengyang/Desktop/Repo/intervir/middleware/cors.vri:461:export cors_config_create, cors_is_origin_allowed, cors_is_preflight
/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_middleware_cors.vri:44:    let ok_custom = cors_is_origin_allowed(custom, "https://app.vir.dev" as ptr)
/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_middleware_cors.vri:52:    let cfg = cors_config_create(origins, methods, headers, expose, 1, 86400)
/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_middleware_cors.vri:55:    let ok1 = cors_is_origin_allowed(cfg, "https://app.vir.dev" as ptr)
/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_middleware_cors.vri:58:    let ok2 = cors_is_origin_allowed(cfg, "https://dashboard.vir.dev" as ptr)
/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_middleware_cors.vri:61:    let bad_origin = cors_is_origin_allowed(cfg, "https://attacker.site" as ptr)
/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_middleware_cors.vri:64:    let null_origin = cors_is_origin_allowed(cfg, 0 as ptr)
/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_middleware_cors.vri:68:    let cfg_wildcard = cors_config_create("*" as ptr, methods, headers, 0 as ptr, 0, 3600)
/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_middleware_cors.vri:69:    let ok_any = cors_is_origin_allowed(cfg_wildcard, "https://random-client.io" as ptr)
```

# Net / web

**Registry:** [`../net.md`](../net.md) · [`../http.md`](../http.md) · [`../tls.md`](../tls.md)  
**Status:** **net + http stable** (syscall TCP, IPv4 resolve, wave e2e)

## Compile smoke

| Module | Result |
|---|---|
| `net` | **OK** — `net_smoke`, `net_tcp_vtest`, `net.*` namespace |
| `http` | **OK** — `http_vtest`, `http_e2e_vtest` via `net.writeAll` / `readAll` |

## Notes

- Public TCP API is **`net.*` only** (snake_case helpers are internal, not exported).
- DNS: IPv4 literal + `localhost` only until full resolver lands.

---
module: net
title: Net
summary: TCP client transport and IPv4 resolution — namespace net.* only.
source:
  - name: net
    path: vir/net/net.vri
status: stable
---

# Net

Low-level **TCP** and **IPv4 literal / localhost** resolution. Public API is
**`include net`** → **`net.*`**. HTTP and TLS build on this module; they do not
re-implement sockets.

```vir
case net.connectHost("127.0.0.1", 8080)
    Ok(stream):
        net.writeAll(stream, "ping")
        case net.readAll(stream)
            Ok(body): ()
            Err(_): ()
        end
        net.close(stream)
    Err(_): ()
end
```

## Boundary

| In `net` | Not in `net` |
|---|---|
| `TcpStream`, `SocketAddr`, `IpAddr` | Full DNS (getaddrinfo) |
| Connect / read / write / close | HTTP parsing → [`http.md`](http.md) |
| IPv4 literal + `localhost` resolve | TLS → [`tls.md`](tls.md) |

## Migration map

| Legacy (internal only) | Public | Action |
|---|---|---|
| `tcp_connect_host` | `net.connectHost` | **remove** public export |
| `tcp_write_all_string` | `net.writeAll` | **remove** public export |
| `tcp_read_all_string` | `net.readAll` | **remove** public export |
| `tcp_close` | `net.close` | **remove** public export |
| `dns_resolve` | `net.resolve` | **remove** public export |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `net.IpAddr` | `IpAddr` | entity | stable |
| `net.SocketAddr` | `SocketAddr` | entity | stable |
| `net.TcpStream` | `TcpStream` | entity | stable |
| `net.TcpListener` | `TcpListener` | entity | stable |
| `net.ipv4` | `ipv4` | `ipv4(a,b,c,d) -> IpAddr` | stable |
| `net.socketAddr` | `socket_addr` | `socket_addr(ip, port) -> SocketAddr` | stable |
| `net.localhost` | `localhost` | `localhost(port) -> SocketAddr` | stable |
| `net.resolve` | `net.resolve` | `net.resolve(hostname) -> Result of (IpAddr)` | stable |
| `net.connect` | `net.connect` | `net.connect(host, port) -> Result of (TcpStream)` | stable |
| `net.connectHost` | `net.connectHost` | `net.connectHost(host, port) -> Result of (TcpStream)` | stable |
| `net.connectAddr` | `net.connectAddr` | `net.connectAddr(addr) -> Result of (TcpStream)` | stable |
| `net.writeAll` | `net.writeAll` | `net.writeAll(stream, text) -> Result of (())` | stable |
| `net.readAll` | `net.readAll` | `net.readAll(stream) -> Result of (string)` | stable |
| `net.close` | `net.close` | `net.close(stream) -> void` | stable |

## Implementation notes

- Syscall-backed TCP on Darwin/Linux via `include syscall`.
- Resolution: IPv4 dotted quad, `localhost` → 127.0.0.1; otherwise `Err`.
- Snake_case helpers remain **file-private** (not exported).

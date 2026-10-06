# InterVir — Architecture Specification

> **Version:** Draft 1.0 — 28/08/2026  
> **Status:** Architecture spec (pre-implementation)  
> **Language compliance:** All runtime source code uses `.vri` and must comply with [Vir Language Specification v2.0](vir_language_spec_v2.0_en.md)  
> **Project root:** `intervir/`  
> **Related:** `stdlib/vir/net/`, `stdlib/vir/web/`, `stdlib/vir/tls/`

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Three Execution Paths](#2-three-execution-paths)
3. [Overall Architecture](#3-overall-architecture)
4. [Data Plane vs Control Plane](#4-data-plane-vs-control-plane)
5. [Request Lifecycle](#5-request-lifecycle)
6. [Module Boundaries & Dependency Graph](#6-module-boundaries--dependency-graph)
7. [Core Runtime](#7-core-runtime)
8. [Scheduler & Workers](#8-scheduler--workers)
9. [Memory & Buffer Architecture](#9-memory--buffer-architecture)
10. [Platform I/O Backends](#10-platform-io-backends)
11. [Network & Transport](#11-network--transport)
12. [Protocol Core (HTTP/1.1)](#12-protocol-core-http11)
13. [Streaming & Backpressure](#13-streaming--backpressure)
14. [Ingress & Routing](#14-ingress--routing)
15. [Proxy Engine](#15-proxy-engine)
16. [App Identity & Multi-App Model](#16-app-identity--multi-app-model)
17. [Portless Local Dispatch](#17-portless-local-dispatch)
18. [Managed Port Range](#18-managed-port-range)
19. [Process Supervision](#19-process-supervision)
20. [Multi-Node Orchestration](#20-multi-node-orchestration)
21. [Autoscaling & ML Policy](#21-autoscaling--ml-policy)
22. [Configuration System](#22-configuration-system)
23. [Header Policy](#23-header-policy)
24. [Observability & Control Plane](#24-observability--control-plane)
25. [Performance Targets & Benchmarks](#25-performance-targets--benchmarks)
26. [Implementation Phases](#26-implementation-phases)
27. [Testing Strategy](#27-testing-strategy)
28. [Open Decisions](#28-open-decisions)

---

## 1. Product Overview

InterVir is neither a plain reverse proxy nor a plain web application server.

InterVir is a **unified web runtime** that combines:

| Capability | Description |
|------------|-------------|
| Public web ingress | Direct TCP 80/443 listeners |
| Reverse proxy | Upstream dispatch to external/legacy services |
| Vir web application runtime | Execute Vir apps inside a managed runtime |
| Process supervision | Lifecycle per App Identity |
| Horizontal scaling | Independent scaling per app |
| Traffic routing | Domain/route → App Identity → healthy instances |
| TLS termination | Native HTTPS ingress |
| Runtime orchestration | Deploy, drain, rollback, port allocation |

### Design Principles

```
One runtime, two execution modes, one protocol core.
```

| Component | Rule |
|-----------|------|
| **One runtime** | A single InterVir daemon process manages ingress + apps + proxy |
| **Two execution modes** | (1) Local Vir app — portless native path; (2) External/upstream — network path |
| **One protocol core** | Shared HTTP parsing/serialization/streaming; proxy and app runtime do not duplicate |

InterVir is **not** a wrapper around Nginx, Caddy, or HAProxy. It remains interoperable when operators deliberately place an external LB/proxy in front.

---

## 2. Three Execution Paths

Every request after routing must take exactly one of the three paths below. The path is chosen **deterministically** from the route table + app topology — no silent fallback.

```text
                    ┌─────────────────────────────────────┐
                    │           InterVir Ingress           │
                    │     (parse HTTP once, route once)      │
                    └──────────────────┬──────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
     ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
     │  NATIVE PATH    │    │ INTEROP PATH    │    │  MANAGED PATH   │
     │  (portless)     │    │ (upstream TCP)  │    │ (orchestration) │
     └────────┬────────┘    └────────┬────────┘    └────────┬────────┘
              │                      │                      │
              ▼                      ▼                      ▼
     Vir app execution      External host:port       Process spawn +
     domain in-process      Node/Go/Python/          port lease from
     or same address        legacy process           master range
     space — NO loopback    InterVir peer            when isolation
     TCP re-parse           standard HTTP            requires endpoint
```

| Path | When | Forbidden |
|------|------|-----------|
| **Native** | App in same managed runtime, no network isolation needed | `InterVir → localhost:port → Vir app` |
| **Interop** | External upstream, legacy, or another InterVir node | — |
| **Managed** | Process isolation, multi-node endpoint, external proxy connect-in | App self-selecting port outside lease range |

The three paths are **not mutually exclusive** within a deployment — each App Identity selects the path appropriate to its topology.

---

## 3. Overall Architecture

### 3.1 Layer Diagram

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                           CONTROL PLANE (cold path)                       │
│  config reload │ admin API │ health aggregate │ deploy │ scale │ drain   │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                          read-mostly snapshots (RCU / versioned)
                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                            DATA PLANE (hot path)                          │
│                                                                           │
│  ┌─────────┐   ┌──────────┐   ┌───────────┐   ┌─────────────────────┐  │
│  │ Ingress │──▶│ Routing  │──▶│ Dispatch  │──▶│ App Runtime │ Proxy  │  │
│  └────┬────┘   └──────────┘   └───────────┘   └─────────────────────┘  │
│       │                                                                   │
│       ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    PROTOCOL CORE (HTTP/1.1)                      │    │
│  │  parse │ serialize │ connection state │ stream │ backpressure    │    │
│  └──────────────────────────────┬──────────────────────────────────┘    │
│                                 ▼                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────────────┐  │
│  │ Transport│   │   TLS    │   │ Network  │   │ Scheduler / Workers │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────────────┘  │
│                                 ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │              Platform backends (epoll / kqueue / io_uring)        │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         SUPERVISOR / ORCHESTRATOR                         │
│  process lifecycle │ port-range allocator │ multi-node coordination      │
│  (never on request hot path)                                              │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Process Model

A single InterVir daemon (`intervir`) consists of:

| Component | Threads | Role |
|-----------|---------|------|
| **Worker pool** | N = f(cores, config intent) | Event loop, HTTP, dispatch |
| **Supervisor thread(s)** | 1–2 | Fork/exec, health poll, restart |
| **Control plane thread** | 1 | Config reload, admin HTTP/Unix socket |
| **Scaler thread** | 1 per node (optional) | Metrics poll, scale decisions |

Workers **do not** call the supervisor on the hot path. The supervisor only mutates shared routing tables via versioned snapshot swap.

---

## 4. Data Plane vs Control Plane

### 4.1 Separation Rules

| Plane | Latency Budget | Failure Mode |
|-------|----------------|--------------|
| **Data plane** | Microseconds–milliseconds | Continue serving with last-known-good config |
| **Control plane** | Seconds acceptable | Log error; do not crash data plane |

### 4.2 Config Snapshot Model

```text
Config file(s) ──parse──▶ ConfigAST ──validate──▶ RoutingSnapshot (immutable)
                                                      │
                              atomic pointer swap ◀───┘
                                      │
                              Workers read snapshot (no lock on hot path)
```

- Workers hold a pointer to the current `RoutingSnapshot` (read-only).
- Control plane builds a new snapshot, validates it, then performs an atomic swap.
- In-flight requests retain a reference to the snapshot version they started with — not invalidated mid-request.

### 4.3 Control Plane Must Not

- Block the worker event loop when reload fails
- Require global stop-the-world to deploy a single app
- Place mutexes on connection hot state

---

## 5. Request Lifecycle

### 5.1 End-to-End Flow

```text
1. ACCEPT     Worker accepts connection (same worker owns connection lifetime)
2. TLS        Optional TLS termination on worker
3. READ       Non-blocking read → protocol parser (per-worker, batched)
4. PARSE      HTTP/1.1 request head (+ body stream handle)
5. ROUTE      Host + path + method → RouteMatch → AppIdentity + DispatchMode
6. HEADERS    Apply header policy (global → app → route precedence)
7. DISPATCH
   ├─ Native:    enqueue to app execution domain (portless channel)
   ├─ Interop:   open upstream connection, proxy stream
   └─ Managed:   select leased endpoint, proxy or forward
8. EXECUTE    App handler or upstream relay (streaming)
9. RESPOND    Serialize response, apply enforced headers
10. COMPLETE  Release request arena; connection keep-alive or close
```

### 5.2 Ownership Model

| Object | Owner | Lifetime |
|--------|-------|----------|
| `Connection` | Accepting worker | Until close/TLS shutdown |
| `HttpStream` (request/response body) | Same worker | Per request, or multiplexed (HTTP/2 future) |
| `RequestContext` | Worker arena | Request start → response complete |
| `RoutingSnapshot` | Shared read-only | Until next config swap; refcount per request |

**Rule:** Do not mix `Connection` lifetime with `Request` lifetime. HTTP/2 multiplexing requires separating `Connection` → `Stream` from Phase 1 design, even though HTTP/2 is implemented later.

### 5.3 Core Types (Conceptual)

```vir
# Conceptual — actual .vri types defined in intervir/protocol/

entity ConnectionId:
    worker_id: int,
    local_seq:   u64;
end.

entity RequestId:
    conn:  ConnectionId,
    stream_id: u32;   # 0 for HTTP/1.1
end.

enum DispatchMode:
    NativePortless = 0;
    InteropUpstream = 1;
    ManagedEndpoint = 2;
end.

entity RouteMatch:
    app_id:       string,      # App Identity (stable)
    dispatch:     DispatchMode,
    upstream:     Option<UpstreamTarget>,
    instance_key: Option<InstanceKey>;
end.
```

---

## 6. Module Boundaries & Dependency Graph

### 6.1 Subsystem Map

| Module | Package | Responsibility |
|--------|---------|----------------|
| `core` | `intervir/core/` | IDs, errors, time, config AST types, versioning |
| `platform` | `intervir/platform/` | epoll, kqueue, io_uring abstraction |
| `scheduler` | `intervir/scheduler/` | Workers, event loop, adaptive batch |
| `memory` | `intervir/memory/` | Buffer pools, arenas, slab allocators |
| `network` | `intervir/network/` | Socket ops, DNS, connection table |
| `transport` | `intervir/transport/` | TCP accept/connect, TLS wrapper |
| `protocol` | `intervir/protocol/` | HTTP/1.1 parse/serialize/stream |
| `ingress` | `intervir/ingress/` | Listeners 80/443, SNI, initial accept |
| `routing` | `intervir/routing/` | Domain/path trie, App Identity resolution |
| `proxy` | `intervir/proxy/` | Upstream relay, connection pooling (interop only) |
| `app_runtime` | `intervir/app_runtime/` | Vir handler dispatch, portless channel |
| `supervisor` | `intervir/supervisor/` | Process spawn, health, restart |
| `orchestrator` | `intervir/orchestrator/` | Multi-app coordination, rolling deploy |
| `scaling` | `intervir/scaling/` | Autoscale controller, ML observer |
| `port_range` | `intervir/port_range/` | Lease allocator |
| `control_plane` | `intervir/control_plane/` | Reload, admin API |
| `observability` | `intervir/observability/` | Metrics, traces, logs |
| `config` | `intervir/config/` | `.vicfg` / `.virsrv` parser |
| `cmd` | `intervir/cmd/` | `intervir`, `intervirctl` CLI |

### 6.2 Dependency Direction (Strict)

```text
                    ┌─────────┐
                    │   cmd   │
                    └────┬────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
  control_plane    orchestrator     observability
         │               │               │
         └───────┬───────┴───────┬───────┘
                 ▼               ▼
            supervisor      scaling
                 │               │
                 └───────┬───────┘
                         ▼
              ingress ─ routing ─┬─ proxy
                                 └─ app_runtime
                         │
                         ▼
                    protocol
                         │
              transport ─ tls
                         │
                      network
                         │
              scheduler ─ memory
                         │
                      platform
                         │
                       core
```

**Hard rules:**

| Rule | Enforcement |
|------|-------------|
| `core` must not import proxy/app/orchestrator | CI dependency lint |
| `proxy` ⊥ `app_runtime` (no direct import) | Communicate via `routing` + `protocol` interfaces |
| `orchestrator` not on hot path | Mutate state only via supervisor + snapshot |
| `protocol` must not know app business logic | HTTP semantics only |

### 6.3 Relationship with Vir stdlib

| stdlib module | InterVir usage |
|---------------|----------------|
| `vir/net/net.vri` | Reference / gradual replace — InterVir `network/` owns hot-path sockets |
| `vir/net/proxy.vri` | **Not used** — SOCKS5 client, not a reverse proxy server |
| `vir/web/router.vri` | App-level routing in `app_runtime` — does **not** replace protocol core |
| `vir/tls/tls.vri` | Wrapped in `transport/tls/` |
| `vir/thread/pool.vri` | Pattern reference — InterVir uses per-worker queues, not global work-stealing |

---

## 7. Core Runtime

### 7.1 Responsibilities

- Stable ID generation (`ConnectionId`, `RequestId`, `AppId`, `InstanceId`)
- Error taxonomy (`InterVirError` with categories: Config, Network, Protocol, App, Supervisor)
- Monotonic clock, timeout handles
- Versioned config snapshot handles
- Startup/shutdown orchestration

### 7.2 Non-Goals

- No HTTP parsing
- No routing tables
- No process spawning

---

## 8. Scheduler & Workers

### 8.1 Worker Model

Each worker:

```text
Worker {
  id:                 int
  cpu_affinity:       Option<int>      # set when configured / auto-detected
  event_backend:      PlatformPoller
  connection_table:   LocalConnMap     # cache-hot
  buffer_pool:        LocalBufferPool
  request_arena:      BumpAllocator      # reset per request
  parser_state:       HttpParser         # NOT shared
  task_queue:         LocalQueue
  metrics:            WorkerMetrics      # per-worker counters, cache-line padded
}
```

### 8.2 Cache-Local First

| Priority | Mechanism |
|----------|-----------|
| Worker affinity | Connection sticks to accepting worker |
| Core affinity | `sched_setaffinity` / equivalent when enabled |
| Per-worker queues | No global task queue on hot path |
| Per-worker allocator | Local buffer pool; cross-worker only for control messages |
| Read-mostly shared | Routing snapshot, TLS cert store, static config |

| Avoid | Reason |
|-------|--------|
| Aggressive work stealing | Breaks cache locality |
| Cross-core migration | Only when worker overload exceeds threshold + hysteresis |
| Shared mutable hot counters | False sharing — use per-worker + periodic aggregate |

### 8.3 NUMA (Future-Ready)

- Phase 1+: default worker count aware of logical cores per NUMA node when detectable
- Port-range shards may attach a NUMA node id
- Document in config intent; do not expose tuning knobs by default

### 8.4 Adaptive Per-Worker Batching

```text
batch_size = f(recent_queue_depth, recent_p99_latency, load_mode)

load_mode:
  LOW  → batch_size = 1..4    (latency-first)
  HIGH → batch_size grows capped (throughput-first)
```

- Batching applies to: event dequeue, HTTP header parse loop
- **No** global parser pool
- Batch size adapts per-worker, per event-loop tick
- Runtime self-tunes; not exposed in user config

---

## 9. Memory & Buffer Architecture

### 9.1 Principles

| Principle | Implementation |
|-----------|----------------|
| Low allocation | Stack + arena for request path |
| Buffer reuse | Power-of-2 bucketed pools per worker |
| Pooled network buffers | 4K / 16K / 64K buckets |
| Request-scoped arena | Reset after each request completes |
| Zero/minimal-copy parse | `BufferSlice` referencing pool buffer when lifetime allows |
| Clear lifetimes | Connection ≠ Request ≠ Stream |

### 9.2 Buffer Ownership

```text
BufferPool (per worker)
    └── BufferChunk (refcounted or arena-owned)
            └── BufferSlice { ptr, len, pool_ref }
```

- Parser creates `BufferSlice` pointing into read buffer — no header copy unless normalization is required
- Response body from file/static: `sendfile` / mmap slice when platform supports it (Phase 7+)

### 9.3 HTTP/2 Readiness

Design `Stream` object separate from `Connection` from Phase 1:

```text
Connection
  ├── Stream[0]  (HTTP/1.1 — single stream)
  └── Stream[n]  (HTTP/2 — multiplexed, future)
```

---

## 10. Platform I/O Backends

### 10.1 Abstraction

```vir
# intervir/platform/poller.vri (conceptual)

trait EventPoller:
    func register(fd: int, events: EventMask) -> Result<void, PlatformError>;
    func modify(fd: int, events: EventMask) -> Result<void, PlatformError>;
    func deregister(fd: int) -> Result<void, PlatformError>;
    func wait(timeout_ms: int, out_events: ptr, max: int) -> int;
end.
```

### 10.2 Backends

| OS | Primary | Fallback |
|----|---------|----------|
| Linux | `io_uring` (when kernel ≥ 5.10 + feature detect) | `epoll` |
| macOS | `kqueue` | — |
| Windows (future) | IOCP | — |

The HTTP/application layer **only** calls the `EventPoller` trait — no OS headers included.

### 10.3 Feature Detection

Runtime auto-detects backend at startup. No user config `use_io_uring = true` required.

---

## 11. Network & Transport

### 11.1 Network Layer

- Non-blocking sockets only
- Async DNS resolve (does not block worker) — resolve cache with TTL
- Connection registry: `ConnectionId → ConnectionState` on owning worker

### 11.2 Transport Layer

| Concern | Owner |
|---------|-------|
| TCP listen/accept | `transport/tcp.vri` |
| TCP connect (upstream) | `transport/tcp.vri` |
| TLS server (ingress) | `transport/tls_server.vri` |
| TLS client (upstream) | `transport/tls_client.vri` |
| ALPN | Phase 13+ (HTTP/2) |

### 11.3 Timeouts (Inferred Defaults)

| Timeout | Default Source |
|---------|----------------|
| Read idle | 60s (configurable per app) |
| Write idle | 60s |
| Upstream connect | 5s |
| Request total | 30s (app override) |

---

## 12. Protocol Core (HTTP/1.1)

### 12.1 Scope

Protocol core (`intervir/protocol/`) owns:

- Request/response parsing (incremental)
- Serialization
- Connection keep-alive state machine
- Chunked transfer encoding
- Upgrade header handling (WebSocket foundation)
- Timeout integration
- Backpressure signals

**Does not** own: routing, TLS, app handler, upstream selection.

### 12.2 Shared Usage

```text
Ingress ──uses──▶ protocol.parse_request()
Proxy   ──uses──▶ protocol.relay_request() / parse_response()
AppRT   ──uses──▶ protocol.build_response() / read_body_stream()
```

One implementation, three consumers — **no duplication**.

### 12.3 HTTP Types

```vir
entity HttpRequest:
    method:      HttpMethod,
    path:        string,
    query:       QueryMap,
    headers:     HeaderMap,
    body:        BodyStream,
    version:     HttpVersion;
end.

entity HttpResponse:
    status:      int,
    headers:     HeaderMap,
    body:        BodyStream;
end.

entity BodyStream:
    # Streaming-first — does not materialize full body by default
    read:   func(buf: ptr, max: int) -> ReadResult;
    write:  func(buf: ptr, len: int) -> WriteResult;
    close:  func();
end.
```

### 12.4 Future Protocols

Architecture does not block HTTP/2, WebSocket, SSE, or QUIC/HTTP/3:

| Protocol | Extension Point |
|----------|-----------------|
| HTTP/2 | `protocol/http2/` + ALPN |
| WebSocket | `protocol/upgrade_ws.vri` |
| SSE | `BodyStream` long-lived + `text/event-stream` |
| QUIC | `transport/quic.vri` (distant) |

---

## 13. Streaming & Backpressure

### 13.1 Streaming-First

- Request body: `BodyStream` read incrementally
- Response body: `BodyStream` write incrementally
- No default `read_all()` on hot path

### 13.2 Backpressure Primitive

```vir
enum FlowStatus:
    Ready = 0;       # can read/write immediately
    WouldBlock = 1;  # wait for POLLOUT/POLLIN
    Closed = 2;
    Error = 3;
end.
```

- Slow receiver → producer gets `WouldBlock` → stops reading upstream → propagates pause
- No unbounded buffer between upstream and downstream

### 13.3 Use Cases

| Use Case | Stream Pattern |
|----------|----------------|
| Large upload | Client → InterVir → App/Upstream chunked relay |
| Static file | File mmap → `BodyStream` |
| Reverse proxy | Duplex relay with pause/resume |
| SSE / AI token stream | Long-lived response stream |
| WebSocket | Bidirectional after upgrade |

---

## 14. Ingress & Routing

### 14.1 Ingress

InterVir listens directly:

| Listener | Port | Notes |
|----------|------|-------|
| HTTP | 80 | Optional redirect to HTTPS |
| HTTPS | 443 | TLS termination, SNI |

With an external proxy in front: InterVir still works — operator is responsible for `X-Forwarded-*` trust policy (configurable).

### 14.2 Routing Table

```text
RoutingSnapshot {
  hosts:    HostTrie → HostRoute
  apps:     Map<AppId, AppDescriptor>
}

HostRoute {
  app_id:     AppId,
  routes:     PathTrie → RouteRule,
  wildcards:  Vec<WildcardRule>
}

RouteRule {
  match:      MethodMask + PathPattern,
  dispatch:   DispatchMode,
  upstream:   Option<UpstreamTarget>,
  headers:    RouteHeaderPolicy,
}
```

### 14.3 Resolution Algorithm

```text
1. Normalize Host header (lowercase, strip port)
2. Lookup HostTrie → HostRoute (wildcard *.example.com supported)
3. Match longest PathTrie prefix
4. Resolve AppId → AppDescriptor → instance selection
5. Return RouteMatch with DispatchMode
```

### 14.4 Instance Selection

| Policy | Description |
|--------|-------------|
| `round_robin` | Default for multiple healthy instances |
| `least_conn` | Interop/managed endpoints |
| `sticky` | Optional cookie/header affinity |
| `local_first` | Prefer native portless instance on same node |

---

## 15. Proxy Engine

### 15.1 Scope

Proxy (`intervir/proxy/`) handles **Interop** and **Managed** paths:

- Upstream TCP connect
- Request relay (header + body stream)
- Response relay
- Connection pool (interop only, per-upstream-host, per-worker)
- Retry policy (idempotent methods only, configurable)

### 15.2 Out of Scope

- No second HTTP parse for native path
- No app lifecycle management
- No routing decision (receives resolved `RouteMatch`)

### 15.3 Upstream Types

```vir
entity UpstreamTarget:
    scheme:   string,   # "http" | "https"
    host:     string,
    port:     int,
    tls:      TlsUpstreamConfig;
end.
```

---

## 16. App Identity & Multi-App Model

### 16.1 App Identity

App Identity is a **stable string identifier** — not a port, not a PID.

```text
App Identity: "shop-api"
  ├── Instance shop-api-7f3a (native, worker 2)
  ├── Instance shop-api-9b1c (native, worker 4)
  └── Instance shop-api-upstream (interop → 10.0.0.5:8080)
```

### 16.2 AppDescriptor

```vir
entity AppDescriptor:
    id:           string,          # App Identity
    project_path: string,          # optional — for Vir apps
    dispatch:     DispatchMode,
    scale:        ScalePolicy,
    health:       HealthPolicy,
    headers:      AppHeaderPolicy,
    instances:    Vec<InstanceDescriptor>;
end.
```

### 16.3 Multi-App Isolation

| Dimension | Isolation |
|-----------|-----------|
| Deploy | Independent per App Identity |
| Restart/crash | Does not affect other apps |
| Scale | Independent policy |
| Drain | Per-app drain flag |
| Rollback | Per-app version pointer |
| Resources | Optional CPU/memory ceilings per app |

### 16.4 Lifecycle States

```text
Pending → Starting → Healthy → Draining → Stopped
                  ↘ Unhealthy → Restarting ↗
                  ↘ Crashed  → Backoff → Starting
```

---

## 17. Portless Local Dispatch

### 17.1 Native Execution Path

When `DispatchMode.NativePortless`:

```text
Ingress worker
  → parse HTTP once
  → build InternalRequest (owned structs, no HTTP serialization)
  → enqueue to AppExecutionDomain[app_id]
  → app worker/handler executes
  → InternalResponse
  → serialize HTTP once on same or paired worker
```

**Forbidden** when app is in the same managed runtime:

```text
InterVir → tcp://127.0.0.1:{app_port} → re-parse HTTP → app
```

### 17.2 Internal Request Contract

```vir
entity InternalRequest:
    id:          RequestId,
    method:      HttpMethod,
    path:        string,
    headers:     HeaderMap,      # policy already merged
    body:        BodyStream,
    app_ctx:     AppContext;
end.

entity InternalResponse:
    status:      int,
    headers:     HeaderMap,
    body:        BodyStream;
end.
```

### 17.3 App Execution Domain

Each Vir app registers a handler table (similar to `vir/web/router.vri` but accepting `InternalRequest`):

```vir
trait AppHandler:
    func handle(req: InternalRequest) -> InternalResponse;
end.
```

InterVir `app_runtime` loads the app module, resolves the entrypoint, wires the handler — app does not need to bind a socket.

### 17.4 When Portless Is Skipped

| Condition | Fallback |
|-----------|----------|
| Network isolation required | Managed endpoint |
| App is external binary | Interop upstream |
| Debug attach requires TCP | Managed (explicit config) |
| Multi-node, app on remote node | Interop to peer InterVir |

---

## 18. Managed Port Range

### 18.1 Hierarchy

```text
System/Host
  └── InterVir Master Port Range [10000..20000]
        └── App "shop-api" sub-lease [10100..10199]
              ├── instance shop-api-1 → :10101
              └── instance shop-api-2 → :10102
```

### 18.2 Lease Model

```vir
entity PortLease:
    port:       int,
    app_id:     string,
    instance:   string,
    node_id:    string,
    state:      LeaseState,   # Active | Draining | Released
    expires:    Option<Time>; # optional TTL
end.
```

### 18.3 Allocator Responsibilities

- Allocation / ownership tracking
- Conflict prevention (no double-bind)
- Reclaim on instance stop
- Rebalance on scale-down
- Drain: stop new leases, wait in-flight, release

### 18.4 When to Use Ports

| Scenario | Port Needed |
|----------|-------------|
| Native portless local | **No** |
| Process isolation (separate OS process) | **Yes** |
| External proxy connect-in | **Yes** |
| Multi-node remote instance | **Yes** |
| Legacy app wrapper | **Yes** |

---

## 19. Process Supervision

### 19.1 Supervisor Role

`intervir/supervisor/` manages:

- Spawn / exec Vir app processes (managed path)
- Health check polling (HTTP GET `/health` or custom)
- Restart with exponential backoff
- Rolling restart (orchestrator trigger)
- SIGTERM → graceful drain → SIGKILL timeout

### 19.2 PM2 Analogy

| PM2 | InterVir Supervisor |
|-----|---------------------|
| Process list | App Identity → instances |
| Restart | Per-instance restart |
| Cluster mode | Native portless + scale policy |
| Logs | Observability integration |
| **Does not have** | Own ingress / routing / portless |

### 19.3 Health Check

```vir
entity HealthPolicy:
    path:           string,       # default "/health"
    interval_ms:    int,          # default 5000
    timeout_ms:     int,          # default 2000
    healthy_threshold:   int,      # consecutive successes
    unhealthy_threshold: int;
end.
```

Unhealthy instances are removed from the routing snapshot (atomic swap) — no need to stop the data plane.

---

## 20. Multi-Node Orchestration

### 20.1 Topology

A single App Identity may span multiple nodes:

```text
App "shop-api"
  ├── node-a: instance-1 (native), instance-2 (native)
  └── node-b: instance-3 (managed :10101)
```

### 20.2 Coordination (Cold Path)

`orchestrator` handles:

- Deploy manifest distribution
- Rolling update coordination
- Cross-node health aggregation
- Port-range shard assignment per node/NIC/NUMA

**Not** on request hot path — routing snapshot already contains resolved endpoints.

### 20.3 Limits Awareness

Port range is a topology tool, not a performance hack:

- TCP 4-tuple uniqueness
- Ephemeral port exhaustion
- Socket table limits
- NIC queue depth
- Kernel `somaxconn`, `tcp_max_syn_backlog`

Document per-deployment capacity planning guide (no hard-coded magic numbers).

---

## 21. Autoscaling & ML Policy

### 21.1 Deterministic Controller (Always On)

```vir
entity ScalePolicy:
    mode:       ScaleMode,   # Fixed | Manual | Auto
    min:        int,
    max:        int,
    targets:    ScaleTargets;
end.

entity ScaleTargets:
    cpu_percent:      Option<float>,
    queue_depth:      Option<int>,
    conn_pressure:    Option<float>,
    rps:              Option<float>,
    p99_latency_ms:   Option<float>;
end.
```

Controller inputs: CPU, queue depth, connection pressure, RPS, latency, memory, health, ceilings.

Controller outputs: desired instance count (bounded by min/max, hysteresis, cooldown).

### 21.2 ML Lifecycle (Auto-Scale Mode Only)

```text
Disabled → Observing → Qualified → Participating
```

| State | Behavior |
|-------|----------|
| **Disabled** | ML off |
| **Observing** | ML trains/predicts; **does not** control; min 24–48h |
| **Qualified** | Model meets quality threshold |
| **Participating** | ML signal bounded; deterministic controller keeps hard limits |

**Rules:**

- ML is never the sole authority
- Deterministic controller: hard limits, safety, fallback
- Every scale decision must be inspectable (structured log + reason code)
- Before 24–48h or below threshold → continue Observing

### 21.3 ML Signal Interface

```vir
entity MlScaleSignal:
    predicted_rps:       float,
    predicted_latency:   float,
    confidence:          float,
    recommendation_delta: int;   # bounded [-2, +2] instances
end.
```

Deterministic controller: `final_desired = clamp(deterministic(desired), ml_signal, hard_limits)`.

---

## 22. Configuration System

### 22.1 Philosophy

**Config describes intent, not mechanism.**

| User Configures | Runtime Infers |
|-----------------|----------------|
| Domains, app id, project path | Worker count, buffer sizes |
| Scale min/max, health path | Parser batch size |
| Upstream URL (interop) | Cache-line padding |
| TLS cert paths | Affinity tuning |

### 22.2 File Types

| File | Extension | Location | Scope |
|------|-----------|----------|-------|
| Global InterVir config | `.vicfg` | `/etc/intervir/`, `~/.config/intervir/` | Infrastructure, domains, apps |
| Project server config | `.virsrv` | Project root (auto-discovered) | App behavior, headers, routes |

**Discovery convention:**

```text
project/
  vir.server.vicfg     # preferred
  vir.server.virsrv    # alternate
  .virsrv              # hidden alternate
```

InterVir scans in the order above; first match wins.

### 22.3 Config Grammar

Declarative subset of Vir lexical conventions:

| Supported | Not Supported |
|-----------|---------------|
| identifiers, strings, numbers, bool | arbitrary function execution |
| lists | loops |
| `:` key-value, blocks, `end` | mutation |
| comments, newline/semicolon | arbitrary Vir expressions |
| | runtime code import |

**Not** `.vri` — parsed by `intervir/config/` grammar, reusing Vir lexer tokens where possible.

### 22.4 Example: Global `.vicfg`

```vicfg
# /etc/intervir/intervir.vicfg

intervir:
  listen:
    http:  80
    https: 443
  tls:
    cert: "/etc/intervir/certs/fullchain.pem"
    key:  "/etc/intervir/certs/privkey.pem"
  port_range: 10000..20000
end

app shop-api:
  project: "/var/www/shop-api"
  domains:
    - "shop.example.com"
    - "*.api.shop.example.com"
  scale:
    mode: auto
    min: 2
    max: 16
  deploy:
    policy: rolling
end

app legacy-admin:
  upstream: "http://10.0.0.5:3000"
  domains:
    - "admin.example.com"
end
```

### 22.5 Example: Project `.virsrv`

```virsrv
# shop-api/vir.server.virsrv

server:
  health:
    path: "/health"
    interval_ms: 5000
  headers:
    default:
      X-Content-Type-Options: "nosniff"
    enforced:
      X-Powered-By: "InterVir"
  routes:
    - path: "/api/*"
      methods: [GET, POST]
    - path: "/static/*"
      cache: "public, max-age=3600"
end
```

### 22.6 Config Merge Precedence

```text
Global .vicfg (infrastructure)
  → Project .virsrv (app behavior)
    → Route-level override (sparse)
      → Handler explicit response headers
```

Domain mapping **only** in global `.vicfg` — not in `.virsrv`.

---

## 23. Header Policy

### 23.1 Scopes

| Scope | Source | Example |
|-------|--------|---------|
| Global | `.vicfg` | `Strict-Transport-Security`, security defaults |
| Application | `.virsrv` | `X-Request-Id` generation policy |
| Route | `.virsrv` routes | `Cache-Control` per path |
| Handler | App code | `Set-Cookie`, custom headers |

### 23.2 Header Kinds

| Kind | Behavior |
|------|----------|
| **default** | Applied if handler has not set; handler may override |
| **enforced** | Applied last; handler **must not** remove/override |

### 23.3 Merge Order (Deterministic)

```text
1. Global defaults
2. App defaults
3. Route defaults
4. Handler-set headers
5. Global enforced
6. App enforced
7. Route enforced
```

Same-name header: later stage wins (except enforced always wins over default).

---

## 24. Observability & Control Plane

### 24.1 Observability

| Signal | Format |
|--------|--------|
| Metrics | Prometheus-compatible (`/metrics` admin port) |
| Traces | OpenTelemetry-style spans (request_id propagation) |
| Logs | Structured JSON, per-request correlation id |

Per-worker metrics aggregated periodically — no atomic global hot counters.

### 24.2 Key Metrics

- `intervir_requests_total{app, method, status}`
- `intervir_request_duration_seconds{app, quantile}`
- `intervir_active_connections{worker}`
- `intervir_upstream_latency_seconds{app, upstream}`
- `intervir_scale_desired_instances{app}`
- `intervir_port_leases_active`

### 24.3 Control Plane API

Admin listener (Unix socket default, TCP optional):

| Endpoint | Action |
|----------|--------|
| `POST /reload` | Validate + swap config snapshot |
| `GET /apps` | List App Identities + state |
| `GET /apps/{id}/instances` | Instance health |
| `POST /apps/{id}/drain` | Begin drain |
| `POST /apps/{id}/scale` | Manual scale override |
| `GET /routes` | Effective routing table |

Control plane failure → data plane continues with last-good snapshot.

---

## 25. Performance Targets & Benchmarks

### 25.1 Principles

- Non-blocking I/O is baseline — do not claim speed from async alone
- Measure end-to-end: ingress → execution → response
- Profile first, optimize after

### 25.2 Metrics (Minimum)

| Category | Metrics |
|----------|---------|
| Throughput | req/s, throughput/core |
| Latency | p50, p95, p99, p99.9 |
| Efficiency | CPU cycles/req, cache misses/req, branch misses/req |
| Memory | allocations/req, bytes copied/req, memory/conn, memory/req |
| System | context switches, syscalls/req |

### 25.3 Benchmark Workloads

| Workload | Compare Against |
|----------|-----------------|
| Static file serving | Nginx |
| HTTP reverse proxy | Nginx |
| TLS termination | Nginx |
| Streaming (large body) | Nginx |
| Dynamic JSON API | Nginx → app server |
| High concurrency | Nginx |
| **InterVir unique** | Nginx → app server vs InterVir portless → Vir app |

**Do not claim advantage** until benchmarks prove it.

### 25.4 Benchmark Harness

```text
intervir/bench/
  static_bench.vri
  proxy_bench.vri
  portless_bench.vri
  tls_bench.vri
  streaming_bench.vri
```

Output: JSON report + comparison table vs Nginx (same hardware, same workload).

---

## 26. Implementation Phases

Design full module boundaries first; implement incrementally.

| Phase | Deliverable | Exit Criteria |
|-------|-------------|---------------|
| **1** | `core`, `platform`, `scheduler` skeleton | Worker event loop runs, echo TCP |
| **2** | `memory`, `network`, `transport` | Non-blocking accept/connect |
| **3** | `protocol` HTTP/1.1 | Parse/serve static, keep-alive, chunked |
| **4** | `ingress`, `routing` | Domain routing, multi-host |
| **5** | `proxy` | Reverse proxy to upstream |
| **6** | App Identity model | Config load, app registry |
| **7** | `app_runtime` portless | Vir handler dispatch, no loopback |
| **8** | `supervisor` | Process spawn, health, restart |
| **9** | Horizontal scale | Independent per-app scale |
| **10** | `port_range` | Lease allocator |
| **11** | `transport/tls` | TLS termination |
| **12** | `observability`, `control_plane` | Metrics, reload, admin API |
| **13** | `scaling` deterministic | Auto-scale controller |
| **14** | ML observation subsystem | Observing → Qualified lifecycle |
| **15** | HTTP/2 | ALPN, multiplex |
| **16** | `orchestrator` multi-node | Cross-node deploy |

Each phase: unit tests, stress tests, concurrency tests, failure tests, memory tests, benchmarks.

---

## 27. Testing Strategy

### 27.1 Test Categories

| Category | Location | Focus |
|----------|----------|-------|
| Unit | `intervir/tests/unit/` | Parser, routing, config, allocator |
| Integration | `intervir/tests/integration/` | End-to-end HTTP, proxy, portless |
| Concurrency | `intervir/tests/concurrency/` | Multi-worker, connection race |
| Failure | `intervir/tests/failure/` | Crash recovery, unhealthy drain |
| Memory | `intervir/tests/memory/` | Leak, arena reset, pool reuse |
| Benchmark | `intervir/bench/` | Performance regression |

### 27.2 Critical Test Scenarios

- Portless path does not open TCP loopback (assert no localhost connect)
- Config reload does not drop active connections
- Unhealthy instance removed within `health.interval * threshold`
- Backpressure: slow client does not OOM server
- App crash does not affect other apps
- Port lease does not conflict on scale up/down
- ML in Observing mode does not change instance count

---

## 28. Open Decisions

| # | Decision | Options | Recommendation |
|---|----------|---------|----------------|
| 1 | Config extension final name | `.vicfg` / `.ivc` | `.vicfg` (Vir-compatible naming) |
| 2 | Project server config name | `.virsrv` / `vir.server.vicfg` | `.virsrv` primary, `vir.server.vicfg` alias |
| 3 | Admin API auth | mTLS / token / Unix-only | Unix socket default; token for TCP |
| 4 | io_uring op model | poll-only first / full async | Poll-only Phase 1; expand Phase 2 |
| 5 | App load mechanism | in-process `.sri` / fork `.sri` | In-process portless first; fork managed later |
| 6 | Inter-node protocol | gRPC / custom binary | Defer to Phase 16; design snapshot sync now |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **App Identity** | Stable string ID for an application deployment unit |
| **Native path** | Portless dispatch to Vir app in managed runtime |
| **Interop path** | Proxy over network to external service |
| **Managed path** | Process + port lease when isolation is required |
| **Routing snapshot** | Immutable config view for hot path |
| **Protocol core** | Shared HTTP implementation for ingress/proxy/app |

---

## Appendix B: Final Architectural Rule

InterVir must simultaneously preserve:

| Property | Meaning |
|----------|---------|
| **Native path** | Vir app runs directly, portless, cache-local |
| **Interoperable path** | Any traditional service via network endpoint |
| **Managed path** | InterVir owns ingress, lifecycle, routing, scaling, ports |

Do not sacrifice any of the three to simplify implementation.

**Goal:** InterVir delivers the deploy experience of a managed web runtime, the routing/proxy capability of production web infrastructure, and the performance model of native Vir execution — in one unified system.

# InterVir Runtime: Báo Cáo Triển Khai & Hoàn Thành Giai Đoạn 1 – 10
**Dự án:** InterVir Unified Web Runtime cho Vir v2.0  
**Tài liệu đặc tả kiến trúc tham chiếu:** [INTERVIR_ARCHITECTURE.md](../INTERVIR_ARCHITECTURE.md)  
**Ngày lập báo cáo:** 04/09/2026  
**Trạng thái kiểm thử:** 41/41 test suites PASS 100%  

---

## 1. Tóm Tắt Tổng Quan (Executive Summary)

Dự án **InterVir** đã hoàn thành thiết kế, cài đặt bằng ngôn ngữ Vir thuần (`.vri`) và kiểm thử toàn diện **10 trên tổng số 16 Phase kiến trúc** (tương đương hơn 60% toàn bộ hệ thống lõi). Toàn bộ mã nguồn đã được biên dịch trực tiếp sang Mach-O native ARM64 thông qua trình biên dịch tự lưu trữ `./bin/virc`, vượt qua 41/41 bài kiểm tra đơn vị và tích hợp mà không có bất kỳ lỗi cú pháp, memory leak hay crash ABI nào.

Hệ thống đã hiện thực hóa trọn vẹn 3 nguyên lý cốt lõi được định nghĩa trong kiến trúc:
1. **Zero-loopback Portless Dispatch:** Các ứng dụng chạy in-process chia sẻ cùng runtime được bàn giao request trực tiếp qua cấu trúc bộ nhớ trong `InternalRequest` / `InternalResponse`, loại bỏ hoàn toàn chi phí serialization/deserialization HTTP và TCP loopback stack (`127.0.0.1`).
2. **Cold-path vs Hot-path Decoupling:** Bộ điều phối tiến trình (Process Supervisor) và cơ chế tự động co giãn tải (Horizontal Scaler) hoạt động tách biệt trên cold-path; các thay đổi topology chỉ cập nhật vào data-plane thông qua cơ chế hoán đổi nguyên tử không khóa (RCU Atomic Snapshot Swap).
3. **Multi-app Isolation & Conflict-Free Port Range:** Quản lý tài nguyên độc lập giữa các tenant ứng dụng, phân bổ dải cổng Master Range (`10000..20000`) thành các App Sub-Range khép kín với state-machine hợp đồng thuê cổng (`PortLease`) ngăn ngừa hoàn toàn double-bind.

---

## 2. Thông Tin Phiên Bản & Git Commit

### 2.1 Submodule `intervir`
- **Branch:** `main`
- **Commit:** [`d7ca99c0b2d069b4b9e4c3fa34718ea0d7617624`](file:///Users/gengyang/Vir/intervir)
- **Thống kê:** 88 files thay đổi, +4,366 dòng mã
- **Commit Message:**
  ```text
  feat(intervir): implement Phases 1-10 runtime engine (core, net, http, route, proxy, runtime, supervisor, scale, port)
  ```

### 2.2 Parent Repository `Vir`
- **Branch:** `recovered_stash`
- **Commit:** [`8e9d580c`](file:///Users/gengyang/Vir)
- **Nội dung:** Cập nhật submodule pointer của `intervir` đồng bộ với commit `d7ca99c`.

---

## 3. Bảng Kết Quả Kiểm Thử (41/41 Tests PASS)

Toàn bộ kiểm thử được tự động hóa thông qua lệnh:
```bash
for f in intervir/tests/unit/test_*.vri; do
    b="/tmp/$(basename $f .vri)"
    rm -f "$b"
    ./bin/virc "$f" -o "$b" && codesign -s - -f "$b" && "$b" || exit 1
done
```

| STT | Tên Test File | Module Kiểm Thử | Trạng Thái |
|:---:|---|---|:---:|
| 1 | `test_core_ids.vri` | 64-bit Typed IDs (`ConnectionId`, `RequestId`, `AppId`, `InstanceId`) | **PASS** |
| 2 | `test_core_errors.vri` | Phân loại mã lỗi `InterVirError` và ánh xạ HTTP status (400, 404, 500, 502, 504) | **PASS** |
| 3 | `test_platform_poller_mock.vri` | Giao diện trừu tượng hóa Poller (`EventMask`, `EventPoller`) | **PASS** |
| 4 | `test_scheduler_worker.vri` | Event-loop Thread-per-core tích hợp `Http1Parser`, `ConnectionTable`, `BufferPool` | **PASS** |
| 5 | `test_memory_pool.vri` | Zero-copy `BufferSlice`, bump allocator `RequestArena`, `BufferPool` (4K/16K/64K) | **PASS** |
| 6 | `test_network_connection.vri` | Socket flags, `ConnectionTable`, bộ nhớ đệm phân giải `DnsCache` | **PASS** |
| 7 | `test_transport_tcp.vri` | Lớp bao bọc `TransportTimeouts`, `TcpListener`, `TcpStream` non-blocking | **PASS** |
| 8 | `test_protocol_http_types.vri` | `HttpRequest`, `HttpResponse`, `HeaderMap`, `BodyStream` | **PASS** |
| 9 | `test_protocol_http1_parser.vri` | Incremental HTTP/1.1 parsing state machine, URL/Header parsing | **PASS** |
| 10 | `test_protocol_http1_serializer.vri` | HTTP/1.1 status formatting, Chunked body serializer, Trailers | **PASS** |
| 11 | `test_protocol_websocket.vri` | WebSocket handshake upgrade detector, Frame header parsing | **PASS** |
| 12 | `test_protocol_http2_frame.vri` | HTTP/2 frame header parsing, bitwise flags, Stream state tracking | **PASS** |
| 13 | `test_routing_dispatch.vri` | Chế độ `DispatchMode` (NativeInProcess, ProxySubprocess, ExternalUpstream) | **PASS** |
| 14 | `test_routing_trie.vri` | Tra cứu tuyến đường tiền tố Prefix Host & Path Trie | **PASS** |
| 15 | `test_routing_snapshot.vri` | Versioned `RoutingSnapshot`, giải mã tuyến đường atomic RCU | **PASS** |
| 16 | `test_ingress_controller.vri` | `IngressConfig`, chuẩn hóa host `normalize_host`, điều phối Ingress | **PASS** |
| 17 | `test_proxy_upstream.vri` | Cấu hình đích đến `UpstreamTarget` HTTP/HTTPS | **PASS** |
| 18 | `test_proxy_pool.vri` | Worker-local connection pool, mượn trả kết nối, tái sử dụng idle keep-alive | **PASS** |
| 19 | `test_proxy_retry.vri` | Idempotent HTTP methods retry policy (GET/HEAD/PUT/DELETE vs POST) | **PASS** |
| 20 | `test_proxy_relay.vri` | Luồng chuyển tiếp song công Duplex relay loop giữa client và upstream | **PASS** |
| 21 | `test_app_lifecycle.vri` | Máy trạng thái vòng đời ứng dụng (`Registered`, `Starting`, `Ready`, `Draining`, `Stopped`) | **PASS** |
| 22 | `test_app_descriptor.vri` | `AppDescriptor` cấu hình scale, kiểm tra ngưỡng tải `has_capacity` | **PASS** |
| 23 | `test_app_instance.vri` | `InstanceDescriptor` quản lý trạng thái, active requests, `mark_busy`, `mark_idle` | **PASS** |
| 24 | `test_app_registry.vri` | Đăng ký ứng dụng và thuật toán Round-Robin load balancing giữa các instance | **PASS** |
| 25 | `test_app_context.vri` | `AppContext` khởi tạo ngữ cảnh ứng dụng, cờ cách ly đa tiến trình | **PASS** |
| 26 | `test_app_internal_req.vri` | `InternalRequest`, `InternalResponse` chuyển đổi zero-copy | **PASS** |
| 27 | `test_app_domain.vri` | Hàng đợi tác vụ `AppExecutionDomain` (enqueue, dequeue, drain deadline) | **PASS** |
| 28 | `test_app_dispatcher.vri` | Bộ định tuyến trực tiếp `PortlessDispatcher`, kiểm tra điều kiện bypass TCP | **PASS** |
| 29 | `test_supervisor_health.vri` | `HealthPolicy` in-place mutation, ngưỡng liên tiếp, reset xen kẽ | **PASS** |
| 30 | `test_supervisor_backoff.vri` | `RestartBackoff` an toàn tràn số nguyên, reset khi ổn định $\ge 30\text{s}$ | **PASS** |
| 31 | `test_supervisor_process.vri` | `ProcessHandle` Starting state, drain deadline, terminal idempotency | **PASS** |
| 32 | `test_supervisor_manager.vri` | `Supervisor` quản lý dung lượng, xử lý thoát tiến trình, RollingRestartState FSM | **PASS** |
| 33 | `test_supervisor_routing_integration.vri` | Tích hợp giám sát & routing: lỗi sức khỏe $\to$ gỡ khỏi snapshot $\to$ hồi phục $\to$ thêm lại | **PASS** |
| 34 | `test_scaling_policy.vri` | `ScalePolicy` kẹp biên dung lượng, thời gian cooldown scale-up / scale-down | **PASS** |
| 35 | `test_scaling_metrics.vri` | `ScaleMetrics` tính toán tải đồng thời trung bình trên từng instance | **PASS** |
| 36 | `test_scaling_controller.vri` | Quyết định mở rộng `evaluate_scale` theo chế độ Auto / Manual / Fixed | **PASS** |
| 37 | `test_scaling_multiapp_integration.vri` | Tích hợp mở rộng đa ứng dụng độc lập: App A tải tăng mở rộng, App B giữ nguyên | **PASS** |
| 38 | `test_port_lease.vri` | Máy trạng thái hợp đồng thuê cổng `PortLease`, chu trình drain, release, hết hạn TTL | **PASS** |
| 39 | `test_port_sub_range.vri` | Cấp phát khối cổng con `AppPortSubRange` theo từng app identity | **PASS** |
| 40 | `test_port_allocator.vri` | Phân vùng dải cổng chính Master Port Range (`10000..20000`) | **PASS** |
| 41 | `test_port_manager_integration.vri` | Tích hợp toàn diện: Master $\to$ Sub-range $\to$ Không double-bind $\to$ Drain & TTL Reclaim | **PASS** |

---

## 4. Chi Tiết Kỹ Thuật Từng Phase

### Phase 1: Core, Platform, Scheduler Skeleton
- **Modules:** `core/ids.vri`, `core/errors.vri`, `platform/events.vri`, `platform/poller.vri`, `scheduler/worker.vri`.
- **Mục tiêu:** Thiết lập nền tảng kiểu dữ liệu cốt lõi và vòng lặp sự kiện thread-per-core.
- **Hiện thực:** 
  - IDs 64-bit có định kiểu tránh nhầm lẫn giữa Connection, Request, App, và Instance.
  - Phân loại lỗi `InterVirError` với danh mục (Io, Protocol, Timeout, Routing, App) và ánh xạ sang HTTP Status Code.
  - Vòng lặp `Worker` điều phối sự kiện theo mô hình hướng phi chặn (non-blocking I/O).

### Phase 2: Memory, Network, Transport
- **Modules:** `memory/slice.vri`, `memory/arena.vri`, `memory/buffer_pool.vri`, `network/socket.vri`, `network/connection.vri`, `network/dns.vri`, `transport/timeouts.vri`, `transport/tcp.vri`.
- **Mục tiêu:** Quản lý bộ nhớ tối ưu, loại bỏ phân mảnh heap trên data-path.
- **Hiện thực:**
  - `BufferSlice`: Trừu tượng hóa lát cắt bộ đệm zero-copy.
  - `RequestArena`: Bump allocator cấp phát nhanh theo từng vòng đời request, tái tạo lại `offset = 0` sau khi xử lý xong mà không cần giải phóng từng phần tử.
  - `BufferPool`: Bộ đệm bucketed tĩnh phân cấp kích thước 4KB, 16KB, 64KB phục vụ đọc/ghi I/O mạng.
  - `ConnectionTable`: Bảng quản lý kết nối socket phi chặn, kiểm soát timeout đọc/ghi/kết nối.

### Phase 3: Protocol Parsing & State Machines
- **Modules:** `protocol/http_types.vri`, `protocol/http1_parser.vri`, `protocol/http1_serializer.vri`, `protocol/websocket.vri`, `protocol/http2_frame.vri`.
- **Mục tiêu:** Xử lý và giải mã các giao thức Web phổ biến (HTTP/1.1, HTTP/2 frame, WebSocket).
- **Hiện thực:**
  - Máy trạng thái `Http1Parser` giải mã tăng dần theo từng đoạn byte đến, không yêu cầu toàn bộ payload phải sẵn sàng trước.
  - Tuần tự hóa `Http1Serializer` định dạng status line, headers chuẩn, và hỗ trợ chunked transfer encoding với trailer headers.
  - Nhận diện nâng cấp WebSocket qua kiểm tra cặp header `Upgrade: websocket` & `Connection: Upgrade`.
  - Bộ giải mã 9-byte header frame của HTTP/2 cùng các bit cờ `END_STREAM`, `END_HEADERS`, `PADDED`.

### Phase 4: Ingress & Routing
- **Modules:** `routing/dispatch.vri`, `routing/rule.vri`, `routing/trie.vri`, `routing/snapshot.vri`, `ingress/ingress.vri`.
- **Mục tiêu:** Phân giải và định tuyến request tới ứng dụng hoặc upstream tương ứng.
- **Hiện thực:**
  - Cấu trúc dữ liệu Host & Path Prefix Trie cho phép khớp tuyến $O(K)$ theo độ dài URL thay vì $O(N)$ quét mảng.
  - Mô hình `RoutingSnapshot` lưu trữ cấu hình bảng định tuyến có phiên bản (versioned). Khi có thay đổi từ Orchestrator, một snapshot mới được dựng ngầm và tráo đổi nguyên tử (atomic pointer swap), đảm bảo data-plane luôn đọc cấu hình bất biến mà không cần khóa mutex.

### Phase 5: Proxy Engine
- **Modules:** `proxy/upstream.vri`, `proxy/pool.vri`, `proxy/retry.vri`, `proxy/relay.vri`.
- **Mục tiêu:** Cung cấp khả năng reverse-proxy cho các tiến trình chạy ngoài hoặc hệ thống bên thứ ba.
- **Hiện thực:**
  - `UpstreamConnPool`: Pool kết nối upstream theo từng worker, tái sử dụng các kết nối idle còn trong thời hạn keep-alive.
  - `ProxyRetry`: Chính sách thử lại nghiêm ngặt, chỉ cho phép retry trên các phương thức an toàn/idempotent (`GET`, `HEAD`, `PUT`, `DELETE`, `OPTIONS`) khi gặp lỗi 502/503/504; cấm tuyệt đối retry cho các request `POST` chưa hoàn thành để tránh lặp tác vụ.
  - `ProxyRelay`: Vòng lặp chuyển tiếp song công dữ liệu giữa client socket và upstream socket.

### Phase 6: App Identity & Multi-App Model
- **Modules:** `app_runtime/lifecycle.vri`, `app_runtime/descriptor.vri`, `app_runtime/instance.vri`, `app_runtime/registry.vri`.
- **Mục tiêu:** Định nghĩa danh tính và quản lý thực thể nhiều ứng dụng chạy đồng thời.
- **Hiện thực:**
  - Máy trạng thái vòng đời `AppLifecycleState`: `Registered` $\to$ `Starting` $\to$ `Ready` $\leftrightarrow$ `Draining` $\to$ `Stopped`.
  - Bảng đăng ký `InstanceRegistry` theo dõi các thực thể đang hoạt động của từng ứng dụng, phân phối tải theo giải thuật Round-Robin cân bằng.

### Phase 7: Portless Native Dispatch & App Runtime
- **Modules:** `app_runtime/context.vri`, `app_runtime/internal_req.vri`, `app_runtime/domain.vri`, `app_runtime/dispatcher.vri`.
- **Mục tiêu:** Thực hiện hóa cơ chế Portless Dispatch trực tiếp qua bộ nhớ trong cho các ứng dụng native Vir.
- **Hiện thực:**
  - `InternalRequest` / `InternalResponse`: Cấu trúc dữ liệu đại diện cho request nội bộ, cho phép chuyển giao con trỏ trực tiếp giữa bộ định tuyến và hàm xử lý của ứng dụng mà không cần encode sang HTTP byte stream.
  - `AppExecutionDomain`: Miền thực thi tác vụ cho ứng dụng với hàng đợi FIFO và kiểm soát deadline tiêu thoát (drain deadline).
  - `PortlessDispatcher`: Điểm giao thoa kiểm tra cấu hình: nếu ứng dụng được đánh dấu là `NativeInProcess`, dispatcher sẽ bỏ qua hoàn toàn mạng nội bộ và kích hoạt handler ứng dụng trực tiếp, mang lại độ trễ cực thấp.

### Phase 8: Production-Grade Process Supervision
- **Modules:** `supervisor/health.vri`, `supervisor/backoff.vri`, `supervisor/process.vri`, `supervisor/supervisor.vri`.
- **Mục tiêu:** Giám sát tiến trình production-grade, khởi động lại tự động khi gặp sự cố, đảm bảo tính toàn vẹn trạng thái.
- **Hiện thực:**
  - `HealthPolicy`: Theo dõi trạng thái sức khỏe với số lần thành công/thất bại liên tiếp cần thiết để chuyển trạng thái giữa `Unknown`, `Passing`, `Failing`. Khi trạng thái xen kẽ, biến đếm được reset về 0 nhằm tránh kích hoạt nhầm.
  - `RestartBackoff`: Tính toán thời gian hoãn khởi động lại theo hàm số mũ ($delay = base \times 2^{failures}$), có trần tối đa, an toàn chống tràn số nguyên 64-bit, và tự động reset về thời gian cơ sở khi tiến trình duy trì ổn định $\ge 30\text{s}$.
  - `ProcessHandle`: Quản lý PID, trạng thái khởi động `Starting`, thời hạn tiêu thoát request `drain_deadline_ms`, và phân loại nguyên nhân dừng (Clean, Crash, DrainTimeout, HealthFailed) đảm bảo tính lũy nghiệm (idempotent).
  - `Supervisor`: Điều phối chu trình Rolling Restart và phối hợp trực tiếp với `RoutingSnapshot` để cô lập tức thì thực thể hỏng khỏi luồng điều hướng của Ingress.

### Phase 9: Horizontal Scale (Độc Lập Từng Ứng Dụng)
- **Modules:** `scaling/policy.vri`, `scaling/metrics.vri`, `scaling/controller.vri`, `scaling/app_scaler.vri`.
- **Mục tiêu:** Tự động co giãn số lượng thực thể theo nhu cầu tải của từng ứng dụng độc lập.
- **Hiện thực:**
  - `ScalePolicy`: Hỗ trợ 3 chế độ (`Fixed`, `Manual`, `Auto`), áp đặt biên kẹp an toàn (`min_instances` $\le N \le$ `max_instances`).
  - Phân tách Cooldown: Quy định thời gian chờ riêng biệt giữa Scale-Up ($15\text{s}$) và Scale-Down ($60\text{s}$), ngăn chặn triệt để hiện tượng dao động co giãn liên tục (thrashing/flapping).
  - `AppScaler`: Quản lý độc lập ma trận co giãn của từng app; việc tăng tải đột biến của ứng dụng A hoàn toàn không gây ảnh hưởng đến cấu hình và số lượng thực thể của ứng dụng B.

### Phase 10: Port Range Management (Cấp Phát Dải Cổng Quản Lý)
- **Modules:** `port_range/lease.vri`, `port_range/sub_range.vri`, `port_range/allocator.vri`, `port_range/manager.vri`.
- **Mục tiêu:** Phân chia dải cổng có kiểm soát cho các tiến trình cô lập hoặc dịch vụ ngoài, ngăn ngừa xung đột cổng (no double-bind).
- **Hiện thực:**
  - `PortLease`: Đại diện cho một hợp đồng thuê cổng có thời hạn (TTL) với máy trạng thái `Free` $\to$ `Active` $\to$ `Draining` $\to$ `Released`.
  - `AppPortSubRange`: Cấp phát một khối cổng liên tục (ví dụ: `10000..10099`) cho từng App Identity.
  - `PortAllocator`: Quản lý phân vùng Master Range (`10000..20000`), chia nhỏ thành các Sub-Range cho các ứng dụng theo nhu cầu.
  - `PortManager`: Bộ điều phối trung tâm đảm bảo không có hai instance nào được cấp cùng một cổng, xử lý thu hồi cổng sau khi tiêu thoát kết nối thành công hoặc tự động dọn dẹp khi hợp đồng thuê hết hạn TTL.

---

## 5. Các Vấn Đề Kỹ Thuật Đã Khắc Phục & Kinh Nghiệm Biên Dịch `virc`

Trong quá trình triển khai mã nguồn trên trình biên dịch Vir v2.0 (`virc`) cho kiến trúc Apple Silicon ARM64, các bài học quan trọng sau đã được đúc kết và áp dụng nhất quán trên toàn bộ codebase:

1. **Khắc phục lỗi Trùng Tên Tham Số và Trường Entity (Symbol Table Collision gây SIGBUS 138):**
   - **Vấn đề:** Trong backend sinh mã của `virc`, nếu tên tham số của một hàm trùng với tên của một trường trong cấu trúc Entity nằm trong đồ thị biên dịch (ví dụ: hàm `func find(port: int)` và thực thể `entity PortLease { port: int }`), compiler sẽ nạp nhầm offset của trường thay vì thanh ghi tham số, dẫn đến lỗi truy cập bộ nhớ SIGBUS (138).
   - **Giải pháp:** Luôn đặt tên tham số khác với tên trường dữ liệu (ví dụ: dùng `p: int` hoặc `target_port: int`, tuyệt đối tránh dùng `port: int`).
2. **Quy ước trả về cấu trúc có chứa chuỗi (`string`):**
   - **Vấn đề:** Trả về struct chứa trường kiểu `string` qua giá trị trả về (`func new() -> MyStruct`) có thể làm sai lệch bố cục con trỏ ABI trên thanh ghi ARM64.
   - **Giải pháp:** Khởi tạo struct trực tiếp tại nơi gọi (`MyStruct(field: val)`) hoặc truyền entity qua con trỏ vào hàm điều chỉnh (mutator pattern).
3. **Bố cục bộ nhớ của Entity (Memory Layout):**
   - Đặt tất cả các trường dữ liệu số nguyên (`int`), boolean (`bool`), và liệt kê (`enum`) lên trước các trường kiểu chuỗi (`string`) để đảm bảo alignment bộ nhớ 8-byte chuẩn xác trên kiến trúc 64-bit.
4. **Sử dụng UFCS và Tham Chiếu Con Trỏ Ngầm Định:**
   - Các phương thức gọi theo cú pháp UFCS (`entity.method()`) nhận con trỏ ngầm định tới thực thể ban đầu, cho phép thay đổi dữ liệu tại chỗ (`this.field = new_val`) mà không sinh bản sao tạm trên stack.
5. **Tách biệt ranh giới Data-plane và Tầng Async Ứng Dụng:**
   - Data-plane của InterVir chạy hoàn toàn trên vòng lặp phi chặn của `PlatformPoller` nhằm đạt hiệu năng cực đại và không cấp phát heap.
   - Thư viện `stdlib/vir/async/` được để dành riêng cho các tác vụ bất đồng bộ mức ứng dụng (Application user logic) thực thi trong `AppExecutionDomain`.

---

## 6. Lộ Trình Giai Đoạn Tiếp Theo (Phases 11 – 16)

Sau khi hoàn thành vững chắc 10 Phase đầu tiên, lộ trình tiếp theo sẽ tiến hành:

- **Phase 11: Transport TLS**
  - Hiện thực TLS termination state machine trong Vir.
  - Phân tích ClientHello / ServerHello và bóc tách SNI (Server Name Indication).
  - Tích hợp chứng chỉ số vào `IngressController` và `RoutingSnapshot`.
- **Phase 12: Cluster & Node Orchestration**
  - Điều phối phân tán giữa các worker node và đồng bộ hóa trạng thái qua gossip/raft nhẹ.
- **Phase 13: Hot-Reload Configuration Engine**
  - Đọc file cấu hình `.vicfg` và `.virsrv`, tự động reload bảng định tuyến và chính sách mà không làm gián đoạn kết nối client.
- **Phase 14: Observability & Metrics**
  - Bộ đếm thời gian thực (request count, latencies histogram, active leases, error rates) hỗ trợ xuất định dạng Prometheus.
- **Phase 15: CLI & Developer Toolchain**
  - Bộ công cụ dòng lệnh `intervir start`, `intervir reload`, `intervir status`.
- **Phase 16: End-to-End Stress Test & Benchmark Suite**
  - Bộ kiểm thử tải toàn diện mô phỏng hàng chục nghìn kết nối đồng thời trên hạ tầng thực tế.

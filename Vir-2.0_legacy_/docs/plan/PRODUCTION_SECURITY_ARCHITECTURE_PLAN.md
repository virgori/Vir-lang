# Kế Hoạch Triển Khai: Kiến Trúc Bảo Mật Paranoid & Multi-Zone Trust Runtime Cho InterVir

**Tài liệu lưu trữ đầy đủ:** Xem tại [`intervir/docs/plan/PRODUCTION_SECURITY_ARCHITECTURE_PLAN.md`](file:///Users/gengyang/Vir/intervir/docs/plan/PRODUCTION_SECURITY_ARCHITECTURE_PLAN.md).

---

## Tóm Tắt 6 Phase Triển Khai & Kiểm Định Nghiêm Ngặt (Strict Test Specs)

1. **Phase 1: Parser Hard Limits & Protocol Smuggling Elimination (Layer 7 Defense)**
   - *Mục tiêu:* 8KB line, 64 headers, 32KB headers, 10MB body, chặn đứng CL/TE Smuggling và Duplicate CL.
   - *Bộ Test Strict:* `test_strict_parser.py` (10 test cases biên, bắt buộc trả về 414/431/400, zero 2xx on bad input, zero crash).
2. **Phase 2: Canonical Path Sandboxing & Open-File Policy (Filesystem Boundary)**
   - *Mục tiêu:* Single-pass normalization, prefix matching với `declared_app_root`, fail-closed routing.
   - *Bộ Test Strict:* `test_strict_path_sandbox.py` (Ma trận 30 kịch bản traversal, null-bytes, encoded slashes; assert 100% 400/404, zero sensitive tokens).
3. **Phase 3: Control-Plane & Admin Isolation (Zero Public Surface)**
   - *Mục tiêu:* Admin API chỉ bind trên `127.0.0.1` hoặc Unix Domain Socket, Bearer HMAC Token, Audit Trail bất biến.
   - *Bộ Test Strict:* `test_control_plane_isolation.py` (Quét 0.0.0.0 tìm 0 admin routes, brute force token thất bại, audit log validation).
4. **Phase 4: Resource Quotas, Bounded Queues & Backpressure (Anti-OOM)**
   - *Mục tiêu:* Bounded queue 1.024 slots, fail-fast 429/503 kèm `Retry-After`, Token Bucket rate limiting per-IP/per-route.
   - *Bộ Test Strict:* `test_backpressure_strict.py` (Flood 50.000 requests, đường cong RAM hoàn toàn phẳng, zero OOM).
5. **Phase 5: Process Domain Separation & Early Privilege Drop (Multi-Trust Zone)**
   - *Mục tiêu:* Bootstrap bind port 80/443 rồi drop UID/GID `nobody` ngay; fork Ingress Worker vs App Worker; App Worker không giữ socket FD.
   - *Bộ Test Strict:* `test_privilege_and_isolation.py` (Audit UID != 0, zero socket FDs trong App Worker, cố tình crash App Worker thì Ingress vẫn 100% sống).
6. **Phase 6: Supervisor Watchdog & Self-Healing Containment (Resilience Engine)**
   - *Mục tiêu:* Heartbeat 50ms, restart budget (5 lần/60s), circuit breaker ngắt mạch tránh fork-bomb, RCU lock-free zero-downtime hot reload.
   - *Bộ Test Strict:* `test_supervisor_watchdog_strict.py` (MTTR < 10ms sau crash, circuit breaker kích hoạt ở lần thứ 6, 0 dropped reqs khi hot reload).

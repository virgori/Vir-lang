# Báo Cáo Bảo Mật: `stdlib/vir/crypto` & TLS

**Phạm vi:** `stdlib/vir/crypto/*`, `stdlib/vir/tls/*`, `tools/verify_crypto_entropy.py`, FFI RNG (`core/src/signer.c`).  
**Ngày báo cáo:** 06/09/2026.  
**Trạng thái package:** **EXPERIMENTAL** — không khuyến nghị production toàn phần cho đến khi có backend đã được audit (libsodium / BoringSSL) hoặc tái kiểm định đầy đủ.

---

## 1. Tóm tắt điều hành

Audit nội bộ phát hiện **10 vấn đề** (3 Critical, 5 High, 2 Medium) khiến thư viện crypto thuần Vir **không an toàn cho production** ở trạng thái trước khi vá:

- Chữ ký / AEAD / X.509 có thể bị **giả mạo hoặc bypass xác thực**.
- Một số API mang tên chuẩn (PKCS#1, Poly1305, Ed25519) nhưng **không tương thích chuẩn**.
- Công cụ “verify entropy” ban đầu chỉ đo OS CSPRNG qua Python/C, **không chứng minh** implementation Vir đúng.

Sau đợt vá (cùng ngày báo cáo):

| Nhóm | Hành động |
|---|---|
| Critical AEAD / X.509 / Ed25519 | Vá tag bypass, Poly1305, wildcard; **fail-closed** Ed25519 + `x509_validate` |
| High | PKCS#1 DigestInfo, bounds JWT/PBKDF2, ladder/subtle branch-free |
| Medium | RNG `Result`, AES-GCM CTR=2 + length 64+64, harness regression |
| Package | Đánh dấu EXPERIMENTAL trong `crypto/mod.vri` |

Harness: `python3 tools/verify_crypto_entropy.py` → entropy + security regressions **PASS** (tại thời điểm báo cáo).

**Kết luận vẫn giữ:** hash/HMAC/OS-CSPRNG có thể dùng thận trọng sau review; Ed25519 / X.509 PKI / RSA (chưa blinding) / AEAD software **chưa đủ** để thay thế thư viện đã audit.

---

## 2. Bảng phát hiện gốc (audit)

| Severity | Location | Finding |
|---|---|---|
| CRITICAL | `ed25519.vri` (~307) | Placeholder: FNV thay SHA-512, base point identity, scalar không mod L, verify không đầy đủ → chữ ký forgeable. |
| CRITICAL | `chacha20.vri` (~400) | ChaCha20-Poly1305 không yêu cầu tag 16 byte; `tag=[]` → `diff==0` → decrypt “đã xác thực”. |
| CRITICAL | `x509.vri` (~127+) | Không parse DER thật, không verify chữ ký/expiry/CA; wildcard chấp nhận `evilexample.com` cho `*.example.com`. |
| HIGH | `chacha20.vri` (~257) | Poly1305 bỏ block cuối thiếu 16 byte; nhân/reduction lệch RFC 8439. |
| HIGH | `rsa.vri` (~125) | API “PKCS#1 v1.5” thực tế textbook RSA trên raw SHA-256; raw decrypt/sign export; không blinding. |
| HIGH | `jwt.vri` (~278), `pbkdf2.vri` (~53,127) | Copy vào buffer cố định không kiểm size; salt/derived key có thể OOB. |
| HIGH | `x25519.vri` (~309), `subtle.vri` (~53–101) | Montgomery ladder / “constant-time” helpers dùng nhánh theo bit bí mật. |
| MEDIUM | `rng.vri` (~125), `crypto.vri` | `csprng_u64` / legacy RNG bỏ qua lỗi entropy → có thể trả 0. |
| MEDIUM | `aes.vri` (~344) | AES-GCM CTR bắt đầu sai (`nonce\|\|1` thay vì `\|\|2`); length block thiếu high 32-bit; S-box lookup phụ thuộc khóa. |
| MEDIUM | `tools/verify_crypto_entropy.py` | Verify hash bằng Python, không chạy implementation Vir; thiếu negative test AEAD/Ed25519/… |

---

## 3. Biện pháp đã áp dụng

### 3.1 Critical

**ChaCha20-Poly1305 (`chacha20.vri`)**

- Từ chối decrypt nếu `vec_len(tag) != 16` hoặc tag tính toán ≠ 16.
- So sánh constant-time đúng 16 byte (không early-exit theo độ dài tag ngắn).
- Viết lại Poly1305 theo hướng poly1305-donna (26-bit limbs), có đường xử lý **block cuối thiếu 16 byte**.

**Ed25519 (`ed25519.vri`)**

- Gỡ stub FNV khỏi đường hash công khai; nối `sha512_hash` cho helper nội bộ còn lại.
- **Fail-closed:** `ed25519_verify` luôn `false`; `ed25519_sign` trả signature rỗng; `ed25519_sign_checked` → `Err(...)`.
- Header module: FAIL-CLOSED / EXPERIMENTAL — cần backend đã audit trước khi bật lại.

**X.509 (`x509.vri`)**

- `x509_validate` luôn `valid: false` với thông báo chưa implement verify chữ ký/chain.
- Wildcard hostname theo tinh thần RFC 6125: suffix bắt đầu bằng `.`, đúng số label, một label trái nhất — chặn `evilexample.com` vs `*.example.com`.
- `x509_parse_pem` chỉ unwrap PEM; không tuyên bố parse DER đầy đủ.

### 3.2 High

**RSA (`rsa.vri`)**

- `rsa_sign_sha256` / `rsa_verify_sha256` dùng EMSA-PKCS1-v1_5 + DigestInfo SHA-256.
- Raw ops đổi tên `*_unsafe` và ghi chú không có padding / blinding.

**JWT / PBKDF2**

- JWT: từ chối signing input / `dot2` > 4096.
- PBKDF2: `salt_len` ∈ \[0, 1020\]; verify không đọc quá `PBKDF2_MAX_DK_LEN` (256).
- HKDF-Expand: bound `info_len` / `prk_len`.

**X25519 / subtle**

- Ladder dùng `_fe_mix` (mask) thay `if sw == 1`.
- `ct_select` / `ct_copy_if` / so sánh: branch-free bằng mask.

### 3.3 Medium

**RNG**

- `csprng_u64` → `Result` (`Ok(val)` / `Err` khi entropy fail).
- Legacy `crypto_random_u64` / `token_*` kiểm tra `native_getrandom` và trả `Result`.
- FFI: `native_getrandom` alias `vir_random_bytes` trong `core/src/signer.c`.

**AES-GCM**

- CTR plaintext bắt đầu counter **2** (`aes_ctr_encrypt_from(..., 2)`).
- Length block: full big-endian 64-bit `len(A)` \|\| 64-bit `len(C)` (bits).
- Cảnh báo S-box timing vẫn còn; ưu tiên AES-NI.

**Harness**

- `tools/verify_crypto_entropy.py`: giữ so sánh entropy Python/C/`/dev/urandom`; thêm **security regression** (static + logic wildcard) cho từng fix audit.

**Package index**

- `stdlib/vir/crypto/mod.vri` ghi rõ EXPERIMENTAL và phân lớp bề mặt “an toàn hơn / fail-closed / experimental”.

---

## 4. Rủi ro còn lại (residual)

| Hạng mục | Mức | Ghi chú |
|---|---|---|
| Ed25519 | Critical (đã mitigate bằng fail-closed) | Chưa có implementation chuẩn; không ký/verify production. |
| X.509 PKI | High | Không verify chữ ký/chain/expiry; chỉ helper hostname + PEM unwrap. |
| RSA | Medium–High | Có PKCS#1 encode nhưng **không blinding**; keygen từ primes do caller cung cấp. |
| AES software | Medium | S-box table lookup → cache-timing; GCM/GHASH chưa có vector test Vir end-to-end đầy đủ. |
| ChaCha20-Poly1305 | Medium | Logic đã vá; cần KAT RFC 8439 chạy **trên binary Vir** (chưa có suite native đầy đủ). |
| Timing / side-channel tổng thể | Medium | Constant-time trong Vir phụ thuộc codegen không tối ưu nhánh; không thay thế hardware CT. |
| Test coverage | Medium | Bootstrap vectors SHA-256 tự chứa; thiếu negative AEAD/Ed25519/X25519/RSA trong `tests/bootstrap_codegen`. |

---

## 5. Ma trận khuyến nghị sử dụng

| Module / API | Production? | Ghi chú |
|---|---|---|
| `crypto/hash`, `crypto/hmac` | Thận trọng | Ưu tiên KAT vs Python; review trước khi khóa. |
| `crypto/rng` (`csprng_128/256`) | Thận trọng | Phụ thuộc OS `/dev/urandom` + syscall fallback; kiểm `Result`. |
| `crypto/aes` (GCM) | Không (trừ lab) | Timing S-box; cần vector Vir vs NIST. |
| `crypto/chacha20` AEAD | Không (trừ lab) | Đã vá bypass; cần KAT Vir. |
| `crypto/ed25519` | **Cấm** | Fail-closed có chủ đích. |
| `crypto/x509` validate | **Cấm** làm trust decision | Luôn fail; hostname helper chỉ sau khi có cert đã parse đúng. |
| `crypto/rsa` | Không | PKCS#1 có; thiếu blinding / OAEP production. |
| `tls` / `tls/cert` | Phụ thuộc FFI native | Không dựa vào `x509_validate` thuần Vir. |

---

## 6. Thiết kế đa backend: FFI / Native / Compare

### 6.1 Mục tiêu

Thư viện crypto cung cấp **một API công khai thống nhất**, nhưng cho phép developer quyết định backend tại thời điểm compile tùy mục đích:

- **FFI:** backend mặc định cho production; gọi implementation đã trưởng thành và được audit như libsodium hoặc BoringSSL.
- **Native Vir:** không phụ thuộc thư viện crypto bên ngoài; phục vụ portability, nghiên cứu, bootstrap và phát triển implementation thuần Vir.
- **Compare:** chạy cùng thao tác trên cả FFI và Native, đối chiếu kết quả để phát hiện sai khác; chỉ dành cho test, CI và quá trình chứng nhận backend Native.

```text
Ứng dụng Vir
    |
    v
vir.crypto API chung
    |
    +-- ffi      (production mặc định)
    +-- native   (theo maturity của từng primitive)
    `-- compare  (test/CI, chạy cả hai backend)
```

Việc chọn backend phải là quyết định **compile-time**. Binary production không mang theo dispatch runtime hoặc backend không được chọn nếu linker có thể loại bỏ chúng.

### 6.2 Giao diện lựa chọn khi compile

Compiler/build system nên hỗ trợ một lựa chọn tương đương:

```text
--crypto-backend=ffi
--crypto-backend=native
--crypto-backend=compare
```

Tên flag cuối cùng cần được đồng bộ với thiết kế option chính thức của `virc`; các tên trên là contract thiết kế, chưa mặc nhiên tuyên bố compiler hiện đã implement chúng.

Quy tắc lựa chọn:

1. Không chỉ định backend: chọn `ffi` cho production profile.
2. Chọn `native`: compiler kiểm tra maturity của từng primitive được dùng.
3. Chọn `compare`: bắt buộc liên kết cả FFI và Native; không được bật trong production profile.
4. Backend FFI lỗi hoặc không khả dụng: **fail compile/link**, tuyệt đối không tự fallback sang Native.
5. Một dependency không được âm thầm đổi backend đã chọn ở cấp ứng dụng.

### 6.3 Cấu trúc module đề xuất

```text
stdlib/vir/crypto/
|-- api.vri                 # API/type/error contract duy nhất
|-- backend.vri             # lựa chọn compile-time + capability metadata
|-- native/
|   |-- hash.vri
|   |-- hmac.vri
|   |-- aes_gcm.vri
|   |-- chacha20_poly1305.vri
|   |-- ed25519.vri
|   |-- x25519.vri
|   `-- ...
|-- ffi/
|   |-- sodium.vri
|   |-- boringssl.vri
|   `-- ...
`-- compare/
    `-- crypto_compare.vri
```

Ứng dụng chỉ import API chung. Các module backend không nên được export như API thông thường, trừ namespace dành riêng cho kiểm thử nội bộ.

### 6.4 Contract chung và capability

Hai backend phải thống nhất:

- Kiểu key, nonce, tag, signature và error code.
- Validation về kích thước input và hành vi fail-closed.
- Quy tắc ownership/lifetime của buffer và việc không để secret thoát khỏi arena ngoài dự kiến.
- Không trả plaintext khi AEAD authentication thất bại.
- Không log key, nonce bí mật, intermediate state, plaintext hoặc output khác biệt chứa dữ liệu nhạy cảm.

Mỗi primitive Native có maturity độc lập:

- `experimental`: chỉ lab/test; production compile phải từ chối.
- `verified`: đã vượt KAT và differential tests nhưng chưa qua review độc lập; production vẫn cần opt-in rõ ràng.
- `production`: đã có test đầy đủ, side-channel assessment và security review độc lập.

Trạng thái được quản lý theo **primitive**, không theo toàn package. Ví dụ SHA-256 có thể đạt `verified` trong khi Ed25519 vẫn `experimental` và fail-closed.

### 6.5 Semantics của Compare backend

Compare backend dùng cùng input cho cả hai implementation và fail ngay khi kết quả không tương đương. Không phải thao tác nào cũng so sánh byte-for-byte:

- Hash, HMAC, HKDF, deterministic signature và deterministic AEAD với cùng key/nonce: so sánh output trực tiếp.
- Random bytes và key generation: không so sánh output ngẫu nhiên; kiểm tra error contract, kích thước, range và invariant, hoặc inject cùng deterministic test entropy.
- Chữ ký randomized: verify chéo (`FFI` verify chữ ký Native và ngược lại) thay vì yêu cầu hai signature giống nhau.
- X.509/TLS: so sánh quyết định accept/reject, error class và parsed identity trên corpus chứng thư hợp lệ/lỗi.
- AEAD decrypt: bắt buộc hai backend cùng reject tag sai, tag rỗng, tag rút gọn và input malformed.

Khi mismatch, harness chỉ ghi primitive, vector/corpus ID, độ dài input và mã lỗi. Secret và plaintext không được đưa vào log CI.

### 6.6 Chính sách test và tài nguyên máy

- Mỗi commit: KAT + negative tests + differential smoke test ngắn.
- Pull request thay đổi crypto: chạy corpus hồi quy và fuzz smoke có giới hạn thời gian.
- Trước release: differential suite đầy đủ; fuzz dài chạy trên CI/runner chuyên dụng.
- Fuzz hàng triệu mẫu không phải điều kiện cho vòng lặp dev cục bộ và không nên mặc định chiếm toàn bộ CPU MacBook.
- Corpus crash/mismatch phải được lưu thành regression test để các lần sau không cần khám phá lại.

### 6.7 Rào chắn phát hành

- Production mặc định dùng FFI.
- Native primitive chưa đạt `production` phải gây compile error trong production profile, trừ override có chủ đích và được ghi nhận trong artifact metadata.
- Compare backend không được phát hành như backend runtime của ứng dụng.
- Build artifact nên ghi backend và version provider đã dùng để phục vụ SBOM, audit và tái lập lỗi.
- CI phải có job build riêng cho cả `ffi`, `native` và `compare`; việc một backend pass không thay thế kiểm thử backend còn lại.

---

## 7. Lộ trình đề xuất

1. **Ngắn hạn (giữ an toàn):** giữ fail-closed Ed25519/X.509; không export raw RSA trong API public mới; CI chạy `tools/verify_crypto_entropy.py`.
2. **Trung hạn:** FFI libsodium hoặc BoringSSL cho Ed25519, X25519, ChaCha20-Poly1305, AES-GCM; X.509 verify qua backend đó.
3. **Dài hạn:** test suite native: RFC 8439, NIST AES-GCM, RFC 8032, RFC 7748, PKCS#1; fuzz AEAD decrypt với tag sai/rỗng; property test hostname.

---

## 8. Cách tái kiểm tra

```bash
# Entropy OS (Python vs C vir_random_bytes) + regression audit fixes
python3 tools/verify_crypto_entropy.py

# (Tuỳ chọn) bootstrap SHA-256 tự chứa — không thay thế audit AEAD/sig
# bin/virc tests/bootstrap_codegen/cg_crypto_vectors.vri -o dist/crypto_verify/cg_crypto_vectors
```

File module chính:

- `stdlib/vir/crypto/{hash,hmac,rng,aes,chacha20,x509,ed25519,rsa,jwt,pbkdf2,x25519,subtle,mod,crypto}.vri`
- `stdlib/vir/tls/{tls,cert}.vri`
- `core/src/signer.c` (`vir_random_bytes`, `native_getrandom`)

---

## 9. Lịch sử thay đổi tài liệu

| Ngày | Nội dung |
|---|---|
| 2026-09-06 | Bổ sung thiết kế API crypto đa backend FFI / Native / Compare, lựa chọn compile-time, maturity gate và chính sách test. |
| 2026-09-06 | Báo cáo đầu: audit 10 finding, biện pháp vá, residual, khuyến nghị production. |

---

*Tài liệu này mô tả trạng thái bảo mật của stdlib crypto tại thời điểm ghi — không phải chứng nhận đánh giá bên thứ ba.*

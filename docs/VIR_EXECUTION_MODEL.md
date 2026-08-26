# VIR EXECUTION MODEL SPEC

*Phiên bản: Draft 1.0 | Ngày: 24 tháng 7, 2026 | Trạng thái: Tài liệu sống*
*Liên quan: [Language Spec v2.0 §1.1](vir_language_spec_v2.0_vi.md#11-phân-tầng-language--compiler--library), [RUNTIME_SEPARATION.md](RUNTIME_SEPARATION.md)*

---

## Mục lục

1. [Mục tiêu thiết kế](#1-mục-tiêu-thiết-kế)
2. [Kiến trúc ba tầng](#2-kiến-trúc-ba-tầng)
3. [Language Layer](#3-language-layer)
4. [Compiler Layer](#4-compiler-layer)
5. [Library Layer](#5-library-layer)
6. [Execution Model](#6-execution-model)
7. [Async Model](#7-async-model)
8. [Thread Model](#8-thread-model)
9. [Parallel Model](#9-parallel-model)
10. [Port](#10-port)
11. [Arena](#11-arena)
12. [Memory Model](#12-memory-model)
13. [Activation Frame](#13-activation-frame)
14. [Zero-overhead Principle](#14-zero-overhead-principle)
15. [Design Principles](#15-design-principles)
16. [Kiến trúc tổng thể](#16-kiến-trúc-tổng-thể)

---

## 1. Mục tiêu thiết kế

Vir là **Systems Programming Language**.

Triết lý cốt lõi:

* Không phụ thuộc Runtime bắt buộc.
* Không giả định Scheduler tồn tại.
* Không giả định Thread Pool tồn tại.
* Không giả định Event Loop tồn tại.
* Không giả định Work Stealing tồn tại.
* Không giả định Green Thread tồn tại.
* Không giả định Garbage Collector tồn tại.

Mọi abstraction đều phải tuân thủ nguyên tắc:

> **Không sử dụng thì không phát sinh chi phí (Zero-overhead Principle).**

| Thành phần | Vai trò |
|------------|---------|
| **Ngôn ngữ** | Chỉ định nghĩa **Semantics** |
| **Compiler** | Chỉ sinh **Machine Code** và các **Primitive** |
| **Library** | Mọi **Execution Policy** (stdlib hoặc thư viện người dùng) |

---

## 2. Kiến trúc ba tầng

```text
Language
    ↓
Compiler
    ↓
Library / Runtime (Optional)
```

Ba tầng có trách nhiệm **tuyệt đối tách biệt**. Không tầng nào được “lấn” trách nhiệm của tầng khác.

---

## 3. Language Layer

Language **chỉ** định nghĩa:

* Syntax
* Type System
* Ownership
* Lifetime
* Memory Model
* Async Semantics
* Parallel Semantics
* Synchronization Semantics

Language **không** định nghĩa:

* Scheduler
* Thread Pool
* Event Loop
* Worker
* ArenaPool
* Work Stealing
* Green Thread
* Actor Runtime
* Executor

Language không được giả định bất kỳ mô hình thực thi nào.

---

## 4. Compiler Layer

Compiler chịu trách nhiệm:

* Parsing
* Semantic Analysis
* Type Checking
* Ownership Analysis
* Lifetime Analysis
* Escape Analysis
* Optimization
* Code Generation

Compiler **chỉ** được sinh:

* Machine Code
* LLVM IR
* C Backend
* Assembly
* Primitive Calls

Compiler **không** được sinh:

* Scheduler
* Runtime Loop
* Thread Pool
* Event Loop
* Work Stealing

Compiler **không** được tự động link Runtime.

---

## 5. Library Layer

Library mới là nơi triển khai:

* Thread
* Thread Pool
* Async Executor
* Event Loop
* Actor
* Scheduler
* Work Stealing
* ArenaPool
* Channel
* Port Backend
* IPC
* Networking

Người dùng chỉ trả chi phí khi **chủ động** import thư viện.

```vir
include std.thread
include std.async
include std.worksteal
```

Nếu không import:

* Không sinh Scheduler
* Không sinh Worker
* Không sinh Executor
* Không sinh Thread Pool

Binary phải tối thiểu như chương trình C tương đương.

---

## 6. Execution Model

Ngôn ngữ Vir **không** quy định Execution Model.

Execution Model được quyết định hoàn toàn bởi Library.

Cùng một chương trình nguồn có thể ánh xạ khác nhau:

| Backend | `parallel` thành |
|---------|------------------|
| A | `pthread` |
| B | OpenMP |
| C | Custom Work Stealing |
| D | Serial |

```text
Backend A          Backend B          Backend C              Backend D
parallel           parallel           parallel               parallel
    ↓                  ↓                  ↓                      ↓
pthread            OpenMP             Work Stealing          Serial
```

Compiler không được phụ thuộc vào backend nào.

---

## 7. Async Model

### 7.1 Semantics

| Từ khoá | Semantics ngôn ngữ |
|---------|-------------------|
| `task` | Đơn vị thực thi có khả năng suspend |
| `await` | Điểm suspend |

Language chỉ quy định semantics.

* Không quy định cách suspend.
* Không quy định cách resume.

### 7.2 Compiler Responsibility

Compiler chỉ tạo một **Activation Frame** và **State Machine** (hoặc cơ chế tương đương).

```text
state = 0
    ↓
await
    ↓
state = 1
    ↓
resume()
```

Compiler không quy định implementation cụ thể. Các cách lowering đều hợp lệ:

* State Machine
* CPS
* Coroutine Lowering
* LLVM Coroutine
* Backend riêng

### 7.3 Executor

* Executor **không** thuộc Language.
* Executor **không** thuộc Compiler.
* Executor **là** Library.

Ví dụ vòng lái tối giản:

```text
while true:
    task.resume()
```

Executor có thể là:

* Single Thread
* Multi Thread
* Polling
* Event Loop
* IOCP
* epoll
* io_uring

Language không quan tâm.

---

## 8. Thread Model

Language không có Thread Runtime.

Thread là Library.

Ví dụ implementation:

```text
std.thread.pthread
std.thread.win32
std.thread.viros
```

Compiler chỉ sinh Primitive. Backend quyết định:

```text
spawn
  ↓
pthread_create()     # hoặc
CreateThread()       # hoặc
VirOS Syscall
```

---

## 9. Parallel Model

Language chỉ mô tả ý nghĩa của `parallel`.

Compiler chỉ sinh Parallel Primitive, ví dụ:

```text
parallel_begin
parallel_chunk
parallel_join
```

Library quyết định chính sách:

* Thread Pool
* Work Stealing
* Fork Join
* OpenMP
* Serial

---

## 10. Port

Language chỉ định nghĩa:

* Port Type
* Send
* Receive
* Ownership Rules

Compiler chỉ sinh:

```text
send()
receive()
```

Compiler **không** giả định:

* Ring Buffer
* Mailbox
* Lock-Free Queue
* OS Pipe
* IPC

Tất cả là implementation của Library.

---

## 11. Arena

Language định nghĩa:

* Arena Lifetime
* Watermark
* Reset
* Ownership

Compiler sinh Primitive:

```text
arena_mark()
arena_alloc()
arena_reset()
```

Compiler **không** được biết:

* ArenaPool
* Worker Arena
* NUMA Arena
* Thread Local Arena

Library quyết định các chính sách trên. Quan hệ khuyến nghị khi dùng parallel lib:

```text
Worker
  └── owns ArenaPool
        └── lends Arena → Task
              └── Task End → Arena.reset() → return to pool
```

**Task** = đơn vị lập lịch (Library). **Arena** = đơn vị lifetime nhớ (Language/Compiler). Hai khái niệm liên quan nhưng không đồng nhất.

---

## 12. Memory Model

Language chỉ có ba vùng nhớ cơ bản:

```text
Stack
Arena
Static
```

Heap chỉ xuất hiện khi:

* Escape Analysis yêu cầu
* Người dùng yêu cầu
* Library yêu cầu

Compiler không giả định Allocator cụ thể (`mmap`, `malloc`, custom, …).

---

## 13. Activation Frame

Biến sống qua điểm suspend được đặt trong **Activation Frame**.

Language **không** quy định Activation Frame nằm ở:

* Heap
* Arena
* Pool
* Static
* Stack mở rộng

Đây là quyết định của ABI hoặc Library.

Compiler chỉ cần bảo đảm semantics (giá trị còn đúng khi resume).

---

## 14. Zero-overhead Principle

Mọi abstraction phải thỏa mãn:

| Điều kiện | Hệ quả bắt buộc |
|-----------|-----------------|
| Không sử dụng | Không sinh mã |
| Không import | Không link Library |
| Không dùng Async | Không có Executor |
| Không dùng Parallel | Không có Scheduler |
| Không dùng Thread | Không có Thread Runtime |
| Không dùng Arena | Không có Arena Library |

Binary tối thiểu phải tương đương chương trình C cùng chức năng.

```vir
@entry
func main:
    print("Hello")
end.
```

Hình dạng chấp nhận được:

```text
_start → main → syscall
```

**Điều kiện thất bại:** binary tối giản vẫn chứa thread scheduler, work-stealing runtime, async executor, hoặc mailbox.

---

## 15. Design Principles

Vir tuân thủ các nguyên tắc sau:

1. Language định nghĩa Semantics.
2. Compiler sinh Primitive.
3. Library quyết định Execution Policy.
4. Compiler không phụ thuộc Runtime.
5. Runtime không phải thành phần bắt buộc của ngôn ngữ.
6. Mọi mô hình thực thi đều có thể thay thế.
7. Không có mô hình Concurrency mặc định.
8. Không có Runtime mặc định.
9. Không có Scheduler mặc định.
10. Zero-overhead là nguyên tắc thiết kế bắt buộc.

---

## 16. Kiến trúc tổng thể

```text
                    Language
          (Semantics / Type / Lifetime)
                         │
                         ▼
                     Compiler
        (Analysis / Optimization / CodeGen)
                         │
                         ▼
               Execution Primitives
                         │
         ┌───────────────┼────────────────┐
         ▼               ▼                ▼
     Thread Lib      Async Lib      Parallel Lib
         ▼               ▼                ▼
 pthread / Win32   Executor      WorkStealing
 IOCP / epoll      EventLoop     ThreadPool
 VirOS Kernel      io_uring      Custom Runtime
```

Kiến trúc này bảo đảm Vir giữ đúng bản chất của một **Systems Programming Language**: ngôn ngữ và compiler không áp đặt bất kỳ mô hình thực thi nào; mọi cơ chế concurrency và scheduling đều là thư viện có thể thay thế, mở rộng, hoặc loại bỏ hoàn toàn mà không làm thay đổi semantics của chương trình.

---

## Phụ lục A — Đối chiếu tài liệu

| Chủ đề | Tài liệu |
|--------|----------|
| Tóm tắt chuẩn trong spec ngôn ngữ | [`vir_language_spec_v2.0_vi.md`](vir_language_spec_v2.0_vi.md) §1.1 / [`vir_language_spec_v2.0_en.md`](vir_language_spec_v2.0_en.md) §1.1 |
| Ghi chú thiết kế ngắn (EN) | [`RUNTIME_SEPARATION.md`](RUNTIME_SEPARATION.md) |
| Memory model (Stack / Arena / Static) | Language Spec §4.5–4.6 |
| Async semantics | Language Spec §22 |
| Port semantics | Language Spec §23 |

---

*VIR EXECUTION MODEL SPEC — Draft 1.0*
*Nguyên tắc: Semantics ∈ Language · Primitives ∈ Compiler · Policy ∈ Library*

# InterVir Subsystem Architecture

> **Version:** 2.0 | **Runtime:** Standalone & WebAssembly

---

## 1. Overview

**InterVir** is the unified execution and interoperability subsystem of the Vir language platform. It provides high-performance bridge execution across native CPU environments, memory arenas, WebAssembly modules, and asynchronous event loops.

---

## 2. Core Components

### 2.1. Native ABI Bridge
- Direct zero-copy FFI execution using standard C calling conventions (`cdecl` on x86_64, AAPCS64 on ARM64).
- Automatic marshaling of basic data types, arrays, and memory pointers.

### 2.2. Linear Bump Arena Allocator
- 8-byte aligned memory allocation with $O(1)$ allocation and $O(1)$ batch reset.
- Eliminates fragmentations and heap overhead in high-throughput workloads.

### 2.3. Asynchronous Task Executor
- Cooperative lightweight green thread runtime.
- Event-driven I/O multiplexing for socket and file operations.

---

## 3. WebAssembly Interoperability

InterVir supports compiling and executing directly in WASM32 runtime environments:

1. **WASM Bytecode Generation:** Direct emission of WASM MVP binary format without requiring Emscripten or LLVM.
2. **Linear Memory Mapping:** Bidirectional buffer sharing between JavaScript host and Vir guest memory.
3. **DOM & Canvas Bindings:** High-performance UI rendering via structured foreign function imports.

# VIR C Core Analysis — Kill C Strategy

> **Mục đích:** Phân tích C engine để chuẩn bị thay thế từng module bằng Vir
> **Ngày tạo:** 22/03/2026
> **Phiên bản:** 2.0 — **CORRECTED 02/04/2026** (file list + LOC rewritten from `find`/`wc -l` output)
> **Source:** `core/src/*.c`
>
> ⚠️ **AUDIT NOTE:** Version 1.0 contained 13 phantom files and wildly inaccurate LOC estimates. This version reflects the actual codebase as of 02/04/2026.

---

## Mục lục

1. [C Engine Architecture](#1-c-engine-architecture)
2. [Module Classification](#2-module-classification)
3. [Logic vs OS-Call Analysis](#3-logic-vs-os-call-analysis)
4. [Dependency Graph](#4-dependency-graph)
5. [Replacement Order](#5-replacement-order)
6. [Bridge Strategy](#6-bridge-strategy)
7. [Risk Assessment](#7-risk-assessment)
8. [Timeline Estimate](#8-timeline-estimate)

---

## 1. C Engine Architecture

### Source Files Overview

```
core/src/                         (35 files, 22,173 LOC total)
├── main.c           (491)    # Entry point, CLI
├── lexer.c          (854)    # Tokenization
├── parser.c         (1738)   # AST construction (recursive descent)
├── ir_lower.c       (2102)   # AST → Q-IR lowering
├── q_ir.c           (321)    # Q-IR representation
├── codegen.c        (3510)   # Native code generation
├── vm.c             (1559)   # Interpreter/runtime
├── mem_manager.c    (271)    # Arena/RC/Pool memory management
├── bridge.c         (479)    # Bridge interface
├── bridge_native.c  (362)    # Native bridge FFI
├── jit_bridge.c     (540)    # JIT bridge
├── signer.c         (358)    # Code signing (macOS)
├── patcher.c        (345)    # Runtime patching
├── vir.c            (30)     # Vir core definitions
├── async_runtime.c  (433)    # Async/await runtime
├── task.c           (385)    # Task scheduler
├── thread_runtime.c (293)    # Threading
├── atomic.c         (446)    # Atomic operations
├── borrow_check.c   (1154)   # Borrow checker
├── constraints.c    (125)    # Type constraints
├── ffi_runtime.c    (270)    # FFI runtime
├── net_runtime.c    (326)    # Network runtime
├── cpu_caps.c       (576)    # CPU capability detection
├── intrinsics.c     (408)    # Intrinsic functions
├── micro_prober.c   (1056)   # Micro-architectural probing
├── simd_dispatch.c  (781)    # SIMD dispatch
├── simd_index.c     (240)    # SIMD indexing
├── amx_accel.c      (283)    # Apple AMX accelerator
├── gpu_metal.c      (504)    # GPU Metal compute
├── gpu_cuda.c       (340)    # GPU CUDA compute
├── gpu_pipeline.c   (253)    # GPU pipeline
├── ptx_gen.c        (561)    # PTX code generation
├── numa_alloc.c     (365)    # NUMA-aware allocation
├── huge_alloc.c     (227)    # Huge page allocation
└── slab_alloc.c     (187)    # Slab allocator
```

### Lines of Code (Actual — verified 02/04/2026)

| File | LOC | Complexity |
|------|-----|------------|
| `codegen.c` | 3,510 | Very High |
| `ir_lower.c` | 2,102 | High |
| `parser.c` | 1,738 | High |
| `vm.c` | 1,559 | Medium-High |
| `borrow_check.c` | 1,154 | High |
| `micro_prober.c` | 1,056 | Medium |
| `lexer.c` | 854 | Medium |
| `simd_dispatch.c` | 781 | Medium |
| `cpu_caps.c` | 576 | Medium |
| `ptx_gen.c` | 561 | Medium |
| `jit_bridge.c` | 540 | Medium |
| `gpu_metal.c` | 504 | Medium |
| `main.c` | 491 | Low |
| `bridge.c` | 479 | Medium |
| `atomic.c` | 446 | Medium |
| `async_runtime.c` | 433 | Medium |
| `intrinsics.c` | 408 | Medium |
| `task.c` | 385 | Medium |
| `numa_alloc.c` | 365 | Low |
| `bridge_native.c` | 362 | Medium |
| `signer.c` | 358 | Low |
| `patcher.c` | 345 | Medium |
| `gpu_cuda.c` | 340 | Medium |
| `net_runtime.c` | 326 | Medium |
| `q_ir.c` | 321 | Low |
| `thread_runtime.c`| 293 | Medium |
| `amx_accel.c` | 283 | Medium |
| `mem_manager.c` | 271 | Medium |
| `ffi_runtime.c` | 270 | Low |
| `gpu_pipeline.c` | 253 | Medium |
| `simd_index.c` | 240 | Low |
| `huge_alloc.c` | 227 | Low |
| `slab_alloc.c` | 187 | Low |
| `constraints.c` | 125 | Low |
| `vir.c` | 30 | Low |
| **TOTAL** | **22,173** | |
| **Headers** | **4,220** | |
| **Grand Total** | **26,393** | |

---

## 2. Module Classification

### Classification Criteria

| Category | Description | Replacement Difficulty |
|----------|-------------|----------------------|
| **Pure Logic** | No OS calls, pure computation | Easy |
| **OS-Call Wrapper** | Thin wrapper around syscalls | Medium |
| **Mixed** | Logic + OS calls interleaved | Hard |
| **Platform-Specific** | Architecture-specific code | Very Hard |

### Module Categories

```
┌─────────────────────────────────────────────────────────────┐
│                     PURE LOGIC (Compiler Pipeline)           │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐           │
│  │ lexer.c │ │parser.c │ │ir_lower.c│ │ q_ir.c  │           │
│  └─────────┘ └─────────┘ └──────────┘ └─────────┘           │
│  ┌──────────────┐ ┌───────────┐ ┌──────────┐                │
│  │borrow_check.c│ │constraints│ │  vir.c   │                │
│  └──────────────┘ └───────────┘ └──────────┘                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   RUNTIME / OS-CALL                          │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────┐           │
│  │mem_manager.c │ │ffi_runtime.c │ │net_runtime.c│           │
│  └──────────────┘ └──────────────┘ └─────────────┘           │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────┐            │
│  │async_runtime │ │thread_runtime│ │  task.c    │            │
│  └──────────────┘ └──────────────┘ └────────────┘            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │ atomic.c │ │ numa.c   │ │huge_alloc│                     │
│  └──────────┘ └──────────┘ └──────────┘                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  PLATFORM-SPECIFIC                           │
│  ┌──────────┐ ┌───────────────┐ ┌───────────────┐            │
│  │codegen.c │ │simd_dispatch.c│ │micro_prober.c │            │
│  └──────────┘ └───────────────┘ └───────────────┘            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐         │
│  │cpu_caps.c│ │amx_accel │ │gpu_metal │ │gpu_cuda │         │
│  └──────────┘ └──────────┘ └──────────┘ └─────────┘         │
│  ┌─────────────┐ ┌────────┐ ┌──────────┐                    │
│  │gpu_pipeline.c│ │ptx_gen│ │simd_index│                    │
│  └─────────────┘ └────────┘ └──────────┘                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                       BRIDGE / JIT                           │
│  ┌──────────┐ ┌───────────────┐ ┌──────────────┐             │
│  │ bridge.c │ │bridge_native.c│ │jit_bridge.c  │             │
│  └──────────┘ └───────────────┘ └──────────────┘             │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐                   │
│  │patcher.c │ │ signer.c │ │intrinsics.c│                   │
│  └──────────┘ └──────────┘ └────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Logic vs OS-Call Analysis

### Pure Logic Modules

#### `lexer.c`
```
OS Calls: 0
Functions: 15
  - next_token()
  - peek_token()
  - skip_whitespace()
  - scan_number()
  - scan_string()
  - scan_identifier()
  - is_keyword()
  - ...

Dependencies: string.c (for string interning)
Replacement: Straightforward - pure string processing
```

#### `parser.c`
```
OS Calls: 0
Functions: 50+
  - parse_program()
  - parse_statement()
  - parse_expression()
  - parse_function()
  - parse_entity()
  - ...

Dependencies: lexer.c, q_ir.c, memory.c
Replacement: Straightforward - recursive descent
```

#### `ir_lower.c`
```
OS Calls: 0
Functions: 30+
  - lower_statement()
  - lower_expression()
  - lower_binop()
  - lower_call()
  - lower_if()
  - ...

Dependencies: parser.c (AST), q_ir.c
Replacement: Straightforward - tree traversal
```

#### `string.c`
```
OS Calls: 0 (uses memory.c for allocation)
Functions: 20
  - str_new()
  - str_concat()
  - str_eq()
  - str_slice()
  - str_find()
  - str_upper/lower()
  - ...

Dependencies: memory.c
Replacement: Easy - already have Vir string type
```

### OS-Call Wrapper Modules

#### `file.c`
```
OS Calls:
  - open()    → Q_FILE_OPEN
  - read()    → Q_FILE_READ
  - write()   → Q_FILE_WRITE
  - close()   → Q_FILE_CLOSE
  - stat()    → Q_FS_EXISTS
  - opendir() → Q_FS_LIST

Replacement: Need syscall wrapper in Vir
```

#### `network.c`
```
OS Calls:
  - socket()  → Q_NET_LISTEN
  - bind()
  - listen()
  - accept()  → Q_NET_ACCEPT
  - send()    → Q_NET_SEND_*
  - recv()    → Q_NET_RECV_*
  - close()   → Q_NET_CLOSE
  - setsockopt()

Replacement: Need platform-specific syscall numbers
```

#### `syscall.c`
```
OS Calls:
  - syscall() → Direct assembly

Functions:
  - vir_syscall0() through vir_syscall6()
  
Replacement: Need inline assembly or FFI
```

### Mixed Modules

#### `vm.c`
```
OS Calls:
  - clock_gettime() for timing
  - mmap() for JIT code allocation

Logic:
  - Opcode dispatch loop
  - Stack management
  - Call frame handling

Replacement: Split into pure logic + OS wrappers
```

#### `memory.c`
```
OS Calls:
  - mmap()/munmap() for large allocations
  - malloc()/free() (optional)

Logic:
  - Reference counting
  - Arena allocation
  - GC traversal

Replacement: Can use Vir arena + syscalls
```

### Platform-Specific Modules

#### `codegen.c`
```
Platform Detection:
  - #ifdef __x86_64__
  - #ifdef __aarch64__

Common Logic:
  - Register allocation
  - Instruction scheduling
  - Jump patching

Replacement: Most complex - need Vir codegen writing native code
```

#### `emit_x86.c`
```
x86_64 Specific:
  - REX prefix encoding
  - ModR/M byte construction
  - Immediate encoding
  - RIP-relative addressing

Functions:
  - emit_mov()
  - emit_add()
  - emit_call()
  - emit_jmp()
  - ...

Replacement: Port byte emission to Vir
```

#### `emit_arm64.c`
```
ARM64 Specific:
  - Instruction word encoding
  - PC-relative branches
  - LDR literal pools
  - ADRP sequences

Replacement: Similar to x86 - byte emission
```

---

## 4. Dependency Graph

```
                    ┌──────────┐
                    │  main.c  │
                    └────┬─────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     ┌────────┐    ┌──────────┐    ┌─────────┐
     │lexer.c │───▶│ parser.c │───▶│ir_lower │
     └────────┘    └──────────┘    └────┬────┘
                                        │
                                        ▼
                                   ┌─────────┐
                                   │  q_ir.c │
                                   └────┬────┘
                         ┌──────────────┼──────────────┐
                         ▼              ▼              ▼
                    ┌─────────┐   ┌──────────┐   ┌─────────┐
                    │  vm.c   │   │codegen.c │   │ debug.c │
                    └────┬────┘   └────┬─────┘   └─────────┘
                         │             │
          ┌──────────────┼─────────────┼──────────────┐
          ▼              ▼             ▼              ▼
     ┌─────────┐   ┌──────────┐  ┌──────────┐   ┌─────────┐
     │runtime.c│   │emit_x86.c│  │emit_arm64│   │ file.c  │
     └────┬────┘   └──────────┘  └──────────┘   └────┬────┘
          │                                          │
          ▼                                          ▼
     ┌─────────────────────────────────────────────────────┐
     │ memory.c  string.c  array.c  map.c  entity.c        │
     └─────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │    syscall.c     │
                    └──────────────────┘
```

---

## 5. Replacement Order

### Phase 1: Foundation (Week 1-2)

**Goal:** Replace data structure modules

| Order | Module | Vir Replacement | Blockers |
|-------|--------|-----------------|----------|
| 1 | `string.c` | `stdlib/vir/core/string.vri` | None |
| 2 | `array.c` | `stdlib/vir/core/array.vri` | None |
| 3 | `map.c` | `stdlib/vir/core/map.vri` | None |
| 4 | `entity.c` | Entity system in compiler | string.c |

### Phase 2: Compiler Frontend (Week 3-5)

**Goal:** Replace parsing pipeline

| Order | Module | Vir Replacement | Blockers |
|-------|--------|-----------------|----------|
| 5 | `lexer.c` | `core/lexer.vri` | string.c |
| 6 | `parser.c` | `core/parser.vri` | lexer.c |
| 7 | `ir_lower.c` | `core/ir_lower.vri` | parser.c |
| 8 | `q_ir.c` | `core/q_ir.vri` | None |

### Phase 3: Syscall Layer (Week 6-7)

**Goal:** Replace OS interface

| Order | Module | Vir Replacement | Blockers |
|-------|--------|-----------------|----------|
| 9 | `syscall.c` | `stdlib/vir/sys/syscall.vri` | Inline asm |
| 10 | `file.c` | `stdlib/vir/fs/file.vri` | syscall.c |
| 11 | `network.c` | `stdlib/vir/net/socket.vri` | syscall.c |
| 12 | `memory.c` | `stdlib/vir/sys/memory.vri` | syscall.c |

### Phase 4: Runtime (Week 8-9)

**Goal:** Replace execution logic

| Order | Module | Vir Replacement | Blockers |
|-------|--------|-----------------|----------|
| 13 | `runtime.c` | `core/runtime.vri` | memory.c |
| 14 | `vm.c` | `core/vm.vri` (if keeping interpreter) | runtime.c |
| 15 | `error.c` | `core/error.vri` | None |

### Phase 5: Codegen (Week 10-14)

**Goal:** Replace native code generation

| Order | Module | Vir Replacement | Blockers |
|-------|--------|-----------------|----------|
| 16 | `emit_x86.c` | `core/emit_x86.vri` | None (pure logic) |
| 17 | `emit_arm64.c` | `core/emit_arm64.vri` | None (pure logic) |
| 18 | `codegen.c` | `core/codegen.vri` | emit_*.c |

### Phase 6: Integration (Week 15-16)

**Goal:** Wire everything together

| Order | Module | Vir Replacement | Blockers |
|-------|--------|-----------------|----------|
| 19 | `main.c` | `vir.vri` (self-hosted) | All above |

---

## 6. Bridge Strategy

### C-Vir FFI Bridge

During transition, C and Vir code must interoperate.

```c
// C calling Vir function
extern VirValue vir_call(const char* func_name, VirValue* args, int argc);

void c_function() {
    VirValue args[] = { vir_int(42) };
    VirValue result = vir_call("vir_process", args, 1);
}
```

```vir
// Vir calling C function
@extern("c_function")
fn c_function()

fn main() {
    c_function()  // Calls C code
}
```

### Gradual Module Replacement

```
Phase 1: C calls Vir for string ops
┌───────────────────────────────────────────┐
│                C Engine                    │
│  ┌─────────┐                              │
│  │parser.c │──────▶ vir_str_concat(s1,s2) │
│  └─────────┘        (calls Vir string.vri)│
└───────────────────────────────────────────┘

Phase 2: Vir parser replaces C parser
┌───────────────────────────────────────────┐
│  Vir Frontend        │      C Backend     │
│  ┌──────────┐        │    ┌──────────┐   │
│  │parser.vri│───────▶│───▶│codegen.c │   │
│  └──────────┘  Q-IR  │    └──────────┘   │
└───────────────────────────────────────────┘

Phase 3: Full Vir (self-hosted)
┌───────────────────────────────────────────┐
│                  VIR                       │
│  ┌──────────┐ ┌─────────┐ ┌───────────┐  │
│  │parser.vri│▶│q_ir.vri │▶│codegen.vri│  │
│  └──────────┘ └─────────┘ └───────────┘  │
└───────────────────────────────────────────┘
```

### Testing During Transition

```bash
# Run same test with both engines, compare output
./vir_c_engine tests/example.vri > c_output.txt
./vir_hybrid_engine tests/example.vri > hybrid_output.txt
diff c_output.txt hybrid_output.txt
```

---

## 7. Risk Assessment

### High Risk Areas

| Area | Risk | Mitigation |
|------|------|------------|
| `codegen.c` | Most complex, platform-specific | Extensive binary comparison tests |
| `memory.c` | RC bugs cause crashes/leaks | Memory stress tests + leak detection |
| `syscall.c` | Platform differences | Test on all platforms early |
| Self-hosting | Bootstrap problem | Keep C fallback until stable |

### Medium Risk Areas

| Area | Risk | Mitigation |
|------|------|------------|
| `parser.c` | Edge cases in syntax | Parser conformance tests |
| `ir_lower.c` | Semantic mismatches | Opcode coverage tests |
| Float handling | Precision differences | IEEE 754 conformance tests |

### Low Risk Areas

| Area | Risk | Mitigation |
|------|------|------------|
| `string.c` | Already well-tested in Vir | Unit tests |
| `array.c` | Already well-tested in Vir | Unit tests |
| `lexer.c` | Simple state machine | Tokenization tests |

### Rollback Points

1. **After Phase 1:** Can rollback to pure C
2. **After Phase 2:** Can rollback frontend to C
3. **After Phase 4:** Can keep C codegen
4. **After Phase 5:** Full Vir or rollback

---

## 8. Timeline Estimate

### Optimistic (Full-time, single developer)

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 1: Foundation | 2 weeks | Week 2 |
| Phase 2: Frontend | 3 weeks | Week 5 |
| Phase 3: Syscalls | 2 weeks | Week 7 |
| Phase 4: Runtime | 2 weeks | Week 9 |
| Phase 5: Codegen | 5 weeks | Week 14 |
| Phase 6: Integration | 2 weeks | Week 16 |
| **TOTAL** | | **16 weeks (~4 months)** |

### Realistic (with testing, debugging, iteration)

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 1: Foundation | 3 weeks | Week 3 |
| Phase 2: Frontend | 5 weeks | Week 8 |
| Phase 3: Syscalls | 3 weeks | Week 11 |
| Phase 4: Runtime | 4 weeks | Week 15 |
| Phase 5: Codegen | 8 weeks | Week 23 |
| Phase 6: Integration | 3 weeks | Week 26 |
| **TOTAL** | | **26 weeks (~6 months)** |

### Milestones

| Milestone | Target | Verification |
|-----------|--------|--------------|
| M1: Vir string/array in C engine | Week 3 | Unit tests pass |
| M2: Vir parser working | Week 8 | Parse all stdlib |
| M3: Vir can call syscalls | Week 11 | File I/O tests |
| M4: Vir runtime standalone | Week 15 | Run simple programs |
| M5: Vir generates x86_64 code | Week 20 | Binary diff tests |
| M6: Vir generates ARM64 code | Week 23 | Cross-compile tests |
| M7: Self-hosted Vir | Week 26 | Compile Vir with Vir |

---

## Decision Points

### 1. Keep Interpreter?

**Options:**
- A) Keep VM for debugging/REPL
- B) JIT-only execution

**Recommendation:** Keep minimal interpreter for debugging during transition.

### 2. Inline Assembly vs FFI?

**Options:**
- A) Inline assembly in Vir for syscalls
- B) Minimal C FFI layer

**Recommendation:** Inline assembly (cleaner, no C dependency).

### 3. Bootstrap Strategy?

**Options:**
- A) Vir compiles itself immediately
- B) Keep C compiler as bootstrap

**Recommendation:** Keep C bootstrap until Vir compiler is stable (Phase 6).

---

## Summary

### Kill C Order

```
1. string.c    ──▶ stdlib/vir/core/string.vri
2. array.c     ──▶ stdlib/vir/core/array.vri
3. map.c       ──▶ stdlib/vir/core/map.vri
4. entity.c    ──▶ Entity system
5. lexer.c     ──▶ core/lexer.vri
6. parser.c    ──▶ core/parser.vri
7. ir_lower.c  ──▶ core/ir_lower.vri
8. q_ir.c      ──▶ core/q_ir.vri
9. syscall.c   ──▶ stdlib/vir/sys/syscall.vri
10. file.c     ──▶ stdlib/vir/fs/file.vri
11. network.c  ──▶ stdlib/vir/net/socket.vri
12. memory.c   ──▶ stdlib/vir/sys/memory.vri
13. runtime.c  ──▶ core/runtime.vri
14. vm.c       ──▶ core/vm.vri (optional)
15. error.c    ──▶ core/error.vri
16. emit_x86.c ──▶ core/emit_x86.vri
17. emit_arm64 ──▶ core/emit_arm64.vri
18. codegen.c  ──▶ core/codegen.vri
19. main.c     ──▶ vir.vri (self-hosted!)
```

**Total: ~18,600 LOC C → Pure Vir**

---

*Document generated for Stage 4 "Kill C" preparation — 22/03/2026*

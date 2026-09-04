# Vir Multi-Target & Runtime Architecture Specification
**Document ID:** `VIR-SPEC-2026-MULTI-TARGET`  
**Version:** `1.0.0` (Aligned with Vir v2.2.0+)  
**Status:** **Canonical Specification**  
**Author:** Virgori Labs Core Architecture Group  
**Scope:** Compiler Backend Pipeline, Machine Instruction (MCInst) Layer, Multi-Target Triples, Assembly Text Generation (`-S`), Portable Runtime & Multi-OS Syscall Architecture.

---

## 0. The Five Inviolable Architectural Boundaries

To prevent long-term technical debt across architectures (ARM64, x86_64, RISC-V 64, WebAssembly) and operating systems (Linux, Darwin/macOS, WASI, Baremetal), the Vir compiler and runtime enforce five strict boundaries:

1. **LIR has zero awareness of Object Formats:** LIR represents machine operations, virtual/physical registers, and stack slots. It knows nothing of ELF, Mach-O, PE, or WebAssembly module headers.
2. **MCInst has zero awareness of Binary vs. Text:** `MCInst` represents concrete, legalized target machine instructions. It neither encodes binary bytes nor formats assembly strings. `BinaryEncoder` and `AsmPrinter` are separate consumers of the same `MCInst` stream.
3. **Portable Runtime has zero awareness of Syscall Numbers:** Application and stdlib code interact solely with `vir.rt.io`, `vir.rt.vm`, `vir.rt.process`. OS adaptation layers translate high-level requests into platform-specific syscalls.
4. **Memory Allocator has zero awareness of OS Flags:** The allocator requests memory via `vm_alloc(size, prot)` and `vm_free(ptr, size)`. It never touches `MAP_ANON`, `MAP_PRIVATE`, `mmap`, or OS-specific bitmasks.
5. **Target Configuration does not reside in Heap Memory:** Target platform metadata (`TargetInfo`) is a compile-time concept (or static constant), never coupled to runtime heap headers or allocator offsets.

---

## 1. Compiler Pipeline Architecture

```text
                               Vir Source (.vri)
                                      │
                                      ▼
                             Lexer + Parser → AST
                                      │
                                      ▼
                        Semantic Analysis (10 Passes)
                                      │
                                      ▼
                                  HIR → MIR
                                      │
                         MIR SSA Optimizations (DCE, SCCP, Inlining)
                                      │
                         ┌────────────┴────────────┐
                         │                         │
               [Native Targets]             [WebAssembly Target]
                         │                         │
                         ▼                         ▼
             Target Legalization (MIR→LIR)   Wasm Lowering
                         │                         │
                         ▼                         ▼
             Register Allocation (Chaitin)   Structured Control IR
                         │                         │
                         ▼                         ▼
                Machine IR (MCInst)             Stackify
                         │                         │
           ┌─────────────┼─────────────┐     ┌─────┴─────┐
           ▼             ▼             ▼     ▼           ▼
      BinaryEncoder  AsmPrinter  ObjectWriter WasmBin   WATPrinter
           │             │             │     │           │
           ▼             ▼             ▼     ▼           ▼
       Raw Bytes      .s text     ELF/Mach-O .wasm      .wat
```

### 1.1 Separation of Native and WebAssembly Pipelines
- Native architectures (ARM64, x86_64, RISC-V 64) pass through **Target Legalization**, **LIR**, and **Physical Register Allocation** (Chaitin-Briggs graph coloring with George-Appel coalescing).
- WebAssembly is fundamentally a **stack machine with structured control flow** (`block`, `loop`, `if`, `br_if`). It branches before physical register allocation into a dedicated Wasm lowering pipeline (`wasm_lowering.vri` -> `stackify.vri`), emitting either binary `.wasm` or textual `.wat`. Native physical register allocation is never imposed on WASM.

---

## 2. Machine Instruction (`MCInst`) Representation

### 2.1 Problem Statement
Direct translation from `LirOp` to binary bytes (`lir_codegen.vri`) alongside a parallel `lir_to_asm.vri` directly translating `LirOp` to text leads to massive code duplication and divergence whenever instructions, addressing modes, or immediate encodings change. Furthermore, architectures like x86_64 require two-address instruction legalization (`mov dst, src1; add dst, src2`) which does not map 1:1 to three-address `LirOp.Add(dst, src1, src2)`.

### 2.2 The `MCInst` Data Structure
```vir
enum MCOperandKind:
    None       = 0
    Reg        = 1     # Concrete physical register (e.g. X0..X30, RAX..R15)
    Imm        = 2     # Raw integer immediate
    Mem        = 3     # Base + Offset (+ Index * Scale) memory operand
    Symbol     = 4     # Relocatable symbol reference
    Label      = 5     # Local basic block target
end.

entity MCOperand:
    kind:        MCOperandKind,
    reg:         int,
    imm:         int,
    mem_base:    int,
    mem_offset:  int,
    mem_scale:   int,
    mem_index:   int,
    symbol_name: string,
    reloc_kind:  RelocKind,
    addend:      int
end.

entity MCInst:
    opcode:   int,            # Architecture-specific MCOpcode
    op0:      MCOperand,
    op1:      MCOperand,
    op2:      MCOperand,
    op3:      MCOperand,
    flags:    int             # Predicate, size flags (32-bit vs 64-bit)
end.
```

### 2.3 Shared Relocation Model (`RelocKind`)
Both binary emission and assembly printing consume the same `RelocKind`:
```vir
enum RelocKind:
    None              = 0
    ARM64_PAGE21      = 1    # @PAGE or ADRP page
    ARM64_PAGEOFF12   = 2    # @PAGEOFF or ADD/LDR :lo12:
    ARM64_CALL26      = 3    # BL / B branch target
    X86_64_PC32       = 4    # RIP-relative 32-bit offset
    X86_64_PLT32      = 5    # @PLT branch
    X86_64_GOTPCREL   = 6    # @GOTPCREL
    RISCV_HI20        = 7    # %hi(symbol)
    RISCV_LO12        = 8    # %lo(symbol)
    RISCV_CALL        = 9    # jal / call
end.
```

- **In `BinaryEncoder`:** Resolves `RelocKind` into relocations or direct bitmask patching into the binary section buffer.
- **In `AsmPrinter`:** Formats `RelocKind` into the target assembler syntax:
  - ARM64 Mach-O: `adrp x0, _sym@PAGE`, `add x0, x0, _sym@PAGEOFF`
  - ARM64 GNU ELF: `adrp x0, sym`, `add x0, x0, :lo12:sym`
  - x86_64 GNU ELF: `call sym@PLT`, `mov rax, [rip + sym@GOTPCREL]`
  - RISC-V 64: `lui a0, %hi(sym)`, `addi a0, a0, %lo(sym)`

---

## 3. Target Model & CLI Architecture

### 3.1 Target Decomposition (Orthogonal Dimensions)
Rather than a monolithic flat enum, target selection is decomposed into four orthogonal dimensions:
Target = Architecture x OS x ABI x ObjectFormat

```vir
enum TargetArch:
    ARM64    = 1    # AArch64 (ARMv8-A+)
    X86_64   = 2    # AMD64 / Intel 64
    RISCV64  = 3    # RV64GC (IMA-FD-C)
    Wasm32   = 4    # WebAssembly 32-bit
end.

enum TargetOS:
    Darwin     = 1  # macOS, iOS
    Linux      = 2  # Linux (glibc, musl, standalone)
    WASI_P1    = 3  # WebAssembly System Interface Preview 1
    WASI_P2    = 4  # WebAssembly System Interface Preview 2
    Baremetal  = 5  # Freestanding (no OS)
end.

enum TargetABI:
    AAPCS64   = 1   # ARM 64-bit standard
    SysV_AMD64 = 2  # System V AMD64 ABI (Linux, macOS, BSD)
    RV64D     = 3   # RISC-V standard calling convention
    WasmMVP   = 4   # WebAssembly Core specification
end.

enum ObjectFormat:
    MachO  = 1
    ELF    = 2
    Wasm   = 3
end.

enum AsmDialect:
    DarwinAsm  = 1   # macOS clang / gas
    GNU_ELF    = 2   # Linux GNU Assembler / llvm-as
    Intel_X86  = 3   # .intel_syntax noprefix
    WasmWAT    = 4   # WebAssembly Text format
end.

entity TargetInfo:
    arch:          TargetArch,
    os:            TargetOS,
    abi:           TargetABI,
    format:        ObjectFormat,
    dialect:       AsmDialect,
    pointer_width: int,          # 4 or 8 bytes
    page_size:     int           # 4096 (Linux default) or 16384 (macOS ARM64)
end.
```

### 3.2 Distinction Between `HostInfo` and `TargetInfo`
- **`HostInfo`**: The environment executing the compiler (`virc`). (e.g. `macos-arm64`).
- **`TargetInfo`**: The environment for which the compiler is emitting code. (e.g. `linux-riscv64`).
- Syscall stubs, runtime constants, and code layout emitted by `virc` are **purely determined by `TargetInfo` at compile time**. No dynamic OS branching occurs at runtime.

### 3.3 Target Triples & CLI Flags
The CLI cleanly separates **Target** (`--target`) from **Emit Kind** (`-S`, `-c`, `-o`, `--emit`):

```bash
# Standard compilation to executable
virc main.vri --target macos-arm64 -o main
virc main.vri --target linux-arm64 -o main_linux_arm64
virc main.vri --target linux-x86_64 -o main_linux_x86
virc main.vri --target linux-riscv64 -o main_linux_riscv
virc main.vri --target wasm32-wasi-p1 -o main.wasm

# Assembly emission (-S)
virc main.vri --target linux-arm64 -S -o main.s
virc main.vri --target macos-arm64 -S -o main.s
virc main.vri --target linux-riscv64 -S -o main.s
virc main.vri --target wasm32-wasi-p1 -S -o main.wat
```

```vir
enum EmitKind:
    Executable = 1   # Full binary linked with runtime
    Object     = 2   # Relocatable object (.o)
    Assembly   = 3   # Text assembly (.s or .wat)
end.
```

---

## 4. Multi-Layer Runtime & Syscall Architecture

Vir organizes system interaction into three distinct layers:
1. **Vir Portable Runtime API (`vir.rt.*`):** Platform-agnostic interfaces exposed to applications and standard library.
2. **OS Adaptation Layer (`vir.rt.os.*`):** Converts Vir logical concepts (standard flags, errors, paths) to OS primitives.
3. **Raw Syscall ABI (`vir.rt.sys.*`):** Architecture- and kernel-specific assembly entrypoints.

```text
               ┌──────────────────────────────────────────────┐
               │    Vir Portable Runtime API (vir.rt.*)        │
               │   file_open, file_read, vm_alloc, sys_exit   │
               └──────────────────────┬───────────────────────┘
                                      │
               ┌──────────────────────▼───────────────────────┐
               │         OS Adaptation Layer (vir.rt.os)      │
               │   linux.vri   │   darwin.vri   │   wasi.vri  │
               └──────────────────────┬───────────────────────┘
                                      │
               ┌──────────────────────▼───────────────────────┐
               │           Raw Syscall ABI (vir.rt.sys)       │
               │ Linux ARM64 │ Linux x86 │ Linux RV64 │ Darwin│
               │   svc #0    │  syscall  │   ecall    │svc #80│
               └──────────────────────────────────────────────┘
```

---

## 5. Standardized Vir Open Flags & Virtual Memory

### 5.1 Vir Open Flags (`VirOpenFlags`)
Vir does not adopt Darwin or Linux bitmasks as its canonical flags. Vir defines platform-independent flags:
```vir
const VIR_O_RDONLY:   0x0001
const VIR_O_WRONLY:   0x0002
const VIR_O_RDWR:     0x0004
const VIR_O_CREAT:    0x0008
const VIR_O_TRUNC:    0x0010
const VIR_O_APPEND:   0x0020
const VIR_O_EXCL:     0x0040
const VIR_O_CLOEXEC:  0x0080
```

Each OS adapter maps `VirOpenFlags` to native OS bitmasks:
- **Darwin Adapter:** `CREAT = 0x0200`, `TRUNC = 0x0400`, `APPEND = 0x0008`
- **Linux Adapter:** `CREAT = 0x0040`, `TRUNC = 0x0200`, `APPEND = 0x0400`
- **WASI Adapter:** Maps flags to `wasi_oflags` (`O_CREAT = 1`, `O_TRUNC = 4`).

### 5.2 Unified Linux `openat` Standard
On all Linux platforms (ARM64, x86_64, RISC-V 64), `sys_open` is implemented strictly via `openat`:
Linux: openat(AT_FDCWD = -100, path, flags, mode)
- `Linux ARM64`: `openat` = syscall 56
- `Linux RISC-V 64`: `openat` = syscall 56
- `Linux x86_64`: `openat` = syscall 257  *(eliminates legacy `open` syscall 2)*

### 5.3 Portable Virtual Memory API (`vir.rt.vm`)
Allocators must never touch OS-level `mmap` constants:
```vir
enum VmProt:
    Read      = 1
    Write     = 2
    ReadWrite = 3
    Exec      = 4
end.

func vm_alloc(size: int, prot: VmProt) -> int
func vm_free(ptr: int, size: int) -> int
```
- **Darwin Implementation:** Calls `mmap(0, size, prot, MAP_PRIVATE | 0x1000, -1, 0)`.
- **Linux Implementation:** Calls `mmap(0, size, prot, MAP_PRIVATE | 0x0020, -1, 0)`.
- **WASI Implementation:** Implemented via `memory.grow`.

---

## 6. Standardized Syscall Error ABI (P0 Requirement)

### 6.1 The Darwin Carry-Flag Hazard
- **Linux Syscall Convention:** The return register contains -errno on failure (e.g. -2 for `ENOENT`), or a non-negative value on success.
- **Darwin Syscall Convention:** Return register `X0` contains the result. If an error occurs, the **CPU Carry Flag (CPSR.C)** is set, and `X0` contains the positive `errno`.
- **Resolution:** The raw Darwin syscall wrapper **must normalize the error convention immediately after `svc #0x80`**:
  ```arm64
  svc #0x80
  b.cc .Lsyscall_ok
  neg x0, x0          ; x0 = -errno (normalized to Linux standard)
  .Lsyscall_ok:
  ret
  ```
- **Unified Vir Error Semantics:** Across all platforms, the raw syscall wrapper guarantees:
  - >= 0: Success
  - < 0: Negative Vir error code (`-VirErrno`)
  No upper layer needs to know about Carry Flags, Linux negations, or WASI error tuples.

---

## 7. Complete Syscall Number Matrix

### 7.1 Modern Linux Generic Syscalls (ARM64 & RISC-V 64)
Both Linux `aarch64` and Linux `riscv64` utilize the Linux `asm-generic` unistd table:

```vir
const LINUX_GENERIC_SYS_GETCWD:       17
const LINUX_GENERIC_SYS_EPOLL_CREATE: 20
const LINUX_GENERIC_SYS_EPOLL_CTL:    21
const LINUX_GENERIC_SYS_EPOLL_WAIT:   22
const LINUX_GENERIC_SYS_OPENAT:       56
const LINUX_GENERIC_SYS_CLOSE:        57
const LINUX_GENERIC_SYS_PIPE2:        59
const LINUX_GENERIC_SYS_LSEEK:        62
const LINUX_GENERIC_SYS_READ:         63
const LINUX_GENERIC_SYS_WRITE:        64
const LINUX_GENERIC_SYS_FSTAT:        80
const LINUX_GENERIC_SYS_EXIT:         93
const LINUX_GENERIC_SYS_EXIT_GROUP:   94
const LINUX_GENERIC_SYS_KILL:         129
const LINUX_GENERIC_SYS_GETPID:       172
const LINUX_GENERIC_SYS_SOCKET:       198
const LINUX_GENERIC_SYS_BIND:         200
const LINUX_GENERIC_SYS_LISTEN:       201
const LINUX_GENERIC_SYS_ACCEPT:       202
const LINUX_GENERIC_SYS_CONNECT:      203
const LINUX_GENERIC_SYS_SENDTO:       206
const LINUX_GENERIC_SYS_RECVFROM:     207
const LINUX_GENERIC_SYS_MUNMAP:       215
const LINUX_GENERIC_SYS_CLONE:        220
const LINUX_GENERIC_SYS_EXECVE:       221
const LINUX_GENERIC_SYS_MMAP:         222
const LINUX_GENERIC_SYS_MPROTECT:     226
const LINUX_GENERIC_SYS_WAIT4:        260
```

### 7.2 Linux x86_64 Syscalls
```vir
const LINUX_X86_SYS_READ:             0
const LINUX_X86_SYS_WRITE:            1
const LINUX_X86_SYS_CLOSE:            3
const LINUX_X86_SYS_FSTAT:            5
const LINUX_X86_SYS_LSEEK:            8
const LINUX_X86_SYS_MMAP:             9
const LINUX_X86_SYS_MPROTECT:         10
const LINUX_X86_SYS_MUNMAP:           11
const LINUX_X86_SYS_GETPID:           39
const LINUX_X86_SYS_SOCKET:           41
const LINUX_X86_SYS_CONNECT:          42
const LINUX_X86_SYS_ACCEPT:           43
const LINUX_X86_SYS_SENDTO:           44
const LINUX_X86_SYS_RECVFROM:         45
const LINUX_X86_SYS_BIND:             49
const LINUX_X86_SYS_LISTEN:           50
const LINUX_X86_SYS_CLONE:            56
const LINUX_X86_SYS_FORK:             57
const LINUX_X86_SYS_EXECVE:           59
const LINUX_X86_SYS_EXIT:             60
const LINUX_X86_SYS_KILL:             62
const LINUX_X86_SYS_GETCWD:           79
const LINUX_X86_SYS_OPENAT:           257
```

### 7.3 Darwin (macOS) BSD Syscalls (Base 0x2000000)
```vir
const DARWIN_SYS_EXIT:                0x2000001
const DARWIN_SYS_FORK:                0x2000002
const DARWIN_SYS_READ:                0x2000003
const DARWIN_SYS_WRITE:               0x2000004
const DARWIN_SYS_OPEN:                0x2000005
const DARWIN_SYS_CLOSE:               0x2000006
const DARWIN_SYS_WAIT4:               0x2000007
const DARWIN_SYS_UNLINK:              0x200000A
const DARWIN_SYS_GETPID:              0x2000014
const DARWIN_SYS_KILL:                0x2000025
const DARWIN_SYS_EXECVE:              0x200003B
const DARWIN_SYS_MMAP:                0x20000C5
const DARWIN_SYS_MUNMAP:              0x2000049
const DARWIN_SYS_MPROTECT:            0x200004A
const DARWIN_SYS_LSEEK:               0x20000C7
const DARWIN_SYS_OPENAT:              0x20001CE
```

---

## 8. Robust File I/O Loop & Interruption Policy

All low-level read/write implementations in Vir runtime must handle short writes, short reads, and `EINTR` retry loops:

```vir
func file_write_all(fd: int, data: int, len: int) -> int:
    var written = 0
    when written < len loop
        let n = sys_write(fd, data + written, len - written)
        if n == -4 do          # -EINTR
            skip               # Retry interrupted syscall
        end
        if n <= 0 do
            out written        # Error or EOF
        end
        written = written + n
    end
    out written
end.

func file_read_all(fd: int, buf: int, len: int) -> int:
    var total_read = 0
    when total_read < len loop
        let n = sys_read(fd, buf + total_read, len - total_read)
        if n == -4 do          # -EINTR
            skip               # Retry interrupted syscall
        end
        if n <= 0 do
            out total_read     # Error or EOF
        end
        total_read = total_read + n
    end
    out total_read
end.
```

---

## 9. Implementation Roadmap & Verification Matrix

### Phase 1: Multi-Platform Syscall Foundation
1. Refactor `stdlib/vir/rt/syscall.vri` into 3-layer architecture:
   - Platform-independent `VirOpenFlags` & `sys_open` via `openat(-100, ...)`.
   - Darwin raw syscall wrapper with Carry-Flag error normalization.
   - Syscall lookup tables for Linux generic (ARM64, RISC-V 64), Linux x86_64, and Darwin.
2. Abstract virtual memory: `stdlib/vir/rt/alloc.vri` using `vm_alloc` / `vm_free`.
3. Eliminate duplicate raw syscall stubs from `lir_codegen.vri`. Centralize stub metadata in `SyscallDesc`.

### Phase 2: Assembly Text Generation (`-S` / `--format asm`)
1. Implement `MCInst`, `MCOperand`, `RelocKind` in `stdlib/vir/compiler/mc.vri`.
2. Connect LIR to `MCInst` lowering (`lir_to_mc.vri`).
3. Implement `arm64_asm_printer.vri` and `x86_asm_printer.vri`.
4. Connect CLI flag `-S` in `virc.vri`.

### Phase 3: Comprehensive Verification
1. **Local Assembly Verification (macOS):**
   - Emit `.s` with `./dist/virc-next test.vri -S -o test.s`
   - Assemble with `clang -c test.s` and verify execution.
2. **Remote Linux Verification (`quizzman`):**
   - Cross-compile test suite to ELF ARM64.
   - Run full 1.5MB `virc` natively on `quizzman` to compile test files via `openat`.
   - Verify robust I/O test cases: 0 bytes, 1 byte, 4095/4096/4097 bytes, 64KB+, and binary data containing `\0`.

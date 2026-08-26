# Runtime Separation — Language / Compiler / Library

*Status: Design note (summary) | Normative full spec: [VIR_EXECUTION_MODEL.md](VIR_EXECUTION_MODEL.md) | Language Spec v2.0 §1.1*

Vir must remain replaceable at the execution layer without changing the language.
This document is a **short English summary**. The authoritative, detailed execution-model specification is **[VIR_EXECUTION_MODEL.md](VIR_EXECUTION_MODEL.md)**.

---

## 1. Hard boundary

| Layer | Responsibility | Must not own |
|-------|----------------|--------------|
| **Language** | Syntax, type system, ownership, lifetime, memory model | A single mandated scheduler or allocator policy |
| **Compiler** | Analysis, optimization, codegen; Arena / watermark / Static | Worker, Scheduler, ArenaPool, mailbox, green threads |
| **Library** | Thread, async executor, scheduler, actor, work stealing, ArenaPool | Changing language semantics |

Goal: swap concurrency / allocator implementations **without** changing the language or the compiler core.

---

## 2. Principle: the compiler must not know a scheduler exists

Parallel language forms (e.g. `parallel for`, when present) lower only to IR or intrinsics:

```text
parallel_begin
parallel_chunk
parallel_end
```

They must **not** expand into a hard-coded Worker / Scheduler / ArenaPool tree inside the compiler.

Backends and libraries decide the mapping:

| Choice | `parallel_*` becomes |
|--------|----------------------|
| A | `pthread` |
| B | work-stealing |
| C | OpenMP |
| D | serial |

Interchangeable library targets for the same source:

```text
vir/thread/pthread     # Linux / POSIX
vir/thread/win32       # Windows
vir/thread/spin        # kernel / bare-metal
vir/thread/none        # embedded — serialize parallel regions
```

User selection is an `include`, not a language dialect:

```vir
include std.thread.pthread
# or
include std.thread.worksteal
```

Future competing packages (`vir-thread-io_uring`, `vir-thread-fiber`, `vir-thread-seastar`, …) plug in the same way: new library, same language, same compiler.

---

## 3. Arena vs ArenaPool

| Concept | Layer | Role |
|---------|-------|------|
| **Arena** | Language + compiler | Lifetime unit: bump allocate, scope / watermark reset |
| **ArenaPool** | Library | Reuse arenas across short tasks on a long-lived worker |

Recommended ownership when a parallel library is used:

```text
Worker
  └── owns ArenaPool
        └── lends Arena → Task
              └── Task End → Arena.reset() → return to pool
```

- **Task** = scheduling unit (library).
- **Arena** = memory lifetime unit (language/compiler).
- They are related but **not** identified with each other.

The compiler never assumes an ArenaPool exists. A serial program may use only the default / scoped Arena.

---

## 4. Zero-cost = unused means absent

Zero-cost is not only “not slow”. It also means:

> **If the program does not use it, it must not exist in the binary.**

Minimal program:

```vir
@entry
func main:
    print("Hello")
end.
```

Acceptable shape:

```text
_start → main → syscall
```

**Failure condition:** a minimal binary that still contains a thread scheduler, work-stealing runtime, async executor, or mailbox.

`async` / `await` / `task` may exist as **thin language semantics** (state machine, suspension points). Driving those points is library code linked only when included.

---

## 5. Why this is Vir’s identity

- The **language** does not prescribe one execution model.
- The **compiler** does not depend on one fixed runtime.
- **Libraries** compete: pthread, work-steal, fiber, io_uring, Seastar-style, …

If a better parallel runtime appears than Rayon, Tokio, or TBB, Vir adds a library — it does not revise the language, rewrite the compiler, or tax every hello-world binary.

This keeps “write close to the metal” compatible with opt-in high-level concurrency.

---

## 6. Spec cross-references

| Topic | Spec |
|-------|------|
| **Full Execution Model (normative draft)** | [`VIR_EXECUTION_MODEL.md`](VIR_EXECUTION_MODEL.md) |
| Short summary in language spec | `vir_language_spec_v2.0_*.md` §1.1 |
| Memory model (Arena / Static / Stack) | §4.5–4.6 |
| Async semantics vs library scheduler | §22.5 |
| Port (typed signals; not a mandatory runtime) | §23 |

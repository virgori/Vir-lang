# COMPILER BUG REPORT: Unpromoted Child Arena Allocation on Global Vec Assignment

**Target System**: `virc` (Vir Self-Hosting Compiler v4.2.1 — macos-arm64)  
**Classification**: Memory Safety / Use-After-Free / Escape Analysis Defect  
**Severity**: High (Causes deterministic SIGSEGV / Exit Code 139)  
**Reported From Project**: `iching-vir` (NLP Vector-Native Engine)  
**Date**: October 6, 2026  

---

## 1. Summary

When a local function allocates dynamic structures (`Vec`, `Buffer`, `String`, or nested entities) and assigns them to a global variable (e.g. `var g_bank = 0 as Vec`), the compiler **does not promote the allocated memory graph to the root/global Arena**.

When the initializing function exits, its local function arena is reset/reclaimed. The global variable remains bound to a memory address inside the reclaimed arena. Subsequent reads from the global variable (especially nested references such as inner vectors in prototype banks) read invalid memory, causing:
- Heap memory corruption
- Segmentation fault (`SIGSEGV`, exit code `139`)
- False allocation thrashing / memory pressure (`SIGKILL`, exit code `137`)

---

## 2. Specification Invariant Violated

According to the canonical specification defined in `vir-memory-management`:

> **"Let owned values leave a scope correctly"**  
> *"When an owned allocation leaves a child Arena, place it directly in or promote its complete reachable owned graph to the nearest ancestor region that satisfies the destination lifetime. Invalidate the source after the move. Do not shallow copy a container header while leaving its backing storage in the child Arena."*

And:

> **"Never let a borrow outlive its owner"**  
> *"Diagnostics should identify the borrow origin, owner, attempted escape/use and the boundary where the lifetime ends."*  
> *"Never convert a compiler-detectable dangling borrow into a runtime crash."*

Currently, the compiler neither rejects assigning local allocations to global variables nor promotes them via `rt_promote_graph` to the root lifetime.

---

## 3. Minimal Reproducible Example

```vir
include vec

var g_bank = 0 as Vec

func init_bank():
    var bank = vec.new()
    var i = 0
    when i < 300 loop
        var inner = vec.filled(0, 128)
        vec.push(bank, i)
        vec.push(bank, inner as int)
        i = i + 1
    end
    # Defect: assigning locally allocated 'bank' graph to global 'g_bank'
    # without promotion to root arena
    g_bank = bank
end.

func access_bank() -> int:
    # Later access in a separate function frame
    let inner = vec.get(g_bank, 1) as Vec
    out vec.get(inner, 0)
end.

func main():
    init_bank()
    # Any subsequent arena churn causes g_bank contents to be clobbered
    let val = access_bank()
    print "Read: $(val)\n"
end.
```

### Observed Behavior
1. Compilation succeeds with 0 errors and 0 warnings:
   ```text
   virc: done! (code generated)
   ```
2. Runtime crashes on execution:
   ```text
   rc = 139 (SIGSEGV - Segmentation Fault)
   ```
   Under LLDB, the fault occurs during pointer dereference of `inner` vector capacity/stride, which points to unmapped or clobbered memory.

---

## 4. Workaround Implemented in Application (`iching-vir`)

To ensure 100% memory safety and bypass this compiler defect, `iching-vir` eliminated **all** global variables in the NLP engine:

1. **Before (Defective Pattern)**:
   ```vir
   var g_dom_bank = 0 as Vec
   var g_dom_weights = 0 as Vec

   func nlp_init_domain_bank():
       g_dom_bank = pb.bank
       g_dom_weights = pb.weights
   end.
   ```
   Result: Random segfaults depending on calling frame stack depth.

2. **After (Safe Pattern — Caller-Owned Struct via `out`)**:
   ```vir
   entity DomainModel:
       bank:      Vec
       weights:   Vec
       entries:   Vec
       count:     int
       min_score: int
       margin:    int
       ceiling:   int
   end.

   func nlp_domain_load() -> DomainModel:
       ...
       out DomainModel(...) # Escapes validly via 'out' into caller's frame
   end.

   func nlp_match_domain(ref m: DomainModel, text: string) -> DomainMatch:
       ...
   end.
   ```
   All models are aggregated into `NlpModel`, instantiated once in the long-lived caller frame (e.g. `main()` or daemon loop) and passed explicitly by `ref model: NlpModel`.

---

## 5. Recommended Actions for the Compiler Team

1. **Semantic Pass (Borrow & Escape Analysis)**:
   - Detect assignments to module-level `GlobalVar` targets (`g_... = local_expr`).
   - If the expression contains heap-allocated types (`Vec`, `Buffer`, `String`, struct with pointer fields), either:
     - **Option A (Preferred - Promotion)**: Insert an automatic `rt_promote_graph(val, ROOT_ARENA)` call at MIR lowering before storing to the global slot.
     - **Option B (Direct Allocation)**: Contextually set the active allocation region for initializers writing to globals to `ROOT_ARENA`.
     - **Option C (Strict Rejection)**: Emit compiler diagnostic `[E3045] Assignment of local arena value to global variable violates static lifetime contract`.

2. **Nested Container Promotion**:
   - Ensure that when a `Vec` contains handles to other `Vec` instances (e.g., `vec.push(v, inner as int)`), `rt_promote_graph` is aware of nested handles or provide a typed generic `Vec of (T)` escape visitor so backing buffers of elements are not left orphaned in the child arena.

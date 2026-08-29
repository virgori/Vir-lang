# Vir Module & Include System Specification

> **Version:** 2.0 | **Language Spec:** `docs/vir_language_spec_v2.0_en.md` §3

---

## 1. Overview

The Vir module system provides structured code organization, encapsulation, and namespace resolution across compilation units.

### Core Declarations

- **`import <module_path>`:** Loads an external module and binds its public symbols into the current lexical scope.
- **`export <symbol>`:** Exposes a function, entity, or constant for consumption by other compilation units.
- **`include "<file_path>"`:** Inlines file contents directly during the parsing phase.

---

## 2. Namespace & Alias Resolution

Modules can be aliased to avoid naming collisions:

```vir
import std.net.http as http
import std.crypto.sha256 as sha

func main:
    let client = http.client_create()
    let hash = sha.digest("vir-lang")
    print_str(hash)
end.
```

### Resolution Rules

1. **Local Scope First:** Identifiers are first resolved in the current function or entity block.
2. **Module Imports:** Unqualified identifiers matching imported public symbols are resolved according to import order.
3. **Fully Qualified Names:** Explicit namespaces (`package.module.symbol`) guarantee deterministic symbol resolution.

---

## 3. Dependency DAG & Compilation Order

The Viron Package Manager analyzes import graphs as a Directed Acyclic Graph (DAG) and executes topological sort to determine deterministic build ordering:

1. **Leaf Modules First:** Independent packages with zero dependencies are compiled first.
2. **Cycle Detection:** Recursive circular imports are detected during DFS traversal and rejected at compile time.
3. **Incremental Caching:** Compiled `.sri` binary artifacts are cached based on content hashes.

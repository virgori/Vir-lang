# Report — Concurrency

**Registry:** **missing**  
**Status:** experimental; compile **blocked**

## Scope

| Module | Source | Compile |
|---|---|---|
| `async` | `async/async.vri` | FAIL E1004 `*` |
| `thread` | `thread/thread.vri` | FAIL E1001 |
| `sync.*` | `sync/atomic` `port` `spinlock` | FAIL E2102 (no flat `sync`) |

Submodules: actor/pool/select/waitgroup/worksteal — unchecked.

## Naming (target)

```text
async.spawn / async.run
thread.spawn / thread.Mutex
sync.atomic.*
```

## Verdict

Concurrency is library-provided (language model), but public modules need registry + compile before any stability claim. Flat `sync` remount or document dotted-only includes.

# Report — Collections

**Registry:** [`../vec.md`](../vec.md) · [`../map.md`](../map.md) · [`../set.md`](../set.md) · [`../deque.md`](../deque.md) · [`../buffer.md`](../buffer.md) · [`../slice.md`](../slice.md)  
**Status:** design **closed**; compile **partial**

## Scope

| Module | Source | Notes |
|---|---|---|
| `vec` | `collections/vec.vri` (flat `vec` → prelude) | Canonical surface `vec.*` |
| `map` | `collections/map.vri` | SipHash; free-func style |
| `set` | `collections/set.vri` | Depends on map |
| `deque` | `collections/deque.vri` | Parser `*` issues |
| `buffer` | `mem/buffer.vri` | Byte buffer ≠ `Vec of (u8)` |
| `slice` | `mem/slice.vri` | Borrowed view |
| `hashmap` | `collections/hashmap.vri` | **No registry** — migrate → `map` |
| Deferred | lru/ring/bloom/btree/heap/… | Explicitly not core this wave |

## Compile smoke (`bin/virc`)

| Module | Result | Notes |
|---|---|---|
| `vec` (prelude) | **OK** | via `include vec` → `vec_prelude` |
| `map` | **OK** | int/int open-addressing; `ref` mutators; `native_read_i64` layout |
| `set` | **OK** | wraps int map |
| `deque` | **OK** | int ring buffer; `ref` mutators |
| `buffer` / `slice` | partial | see prior buffer ABI fixes |

Runtime smokes: `test.collections_core`, `test.deque_smoke`, `test.set_smoke` → exit `0`.

**Blocked on compiler:** full `Map of (K, V)` / `Deque of (T)` generics (binary generic arity, `native_load of (T)` link). Current modules are monomorphic int paths with migration helpers `map_int()` / `set_int()`.

## Naming

```text
vec.push / map.get / set.contains / deque.pushFront
buffer.write / slice.sub
```

Legacy `vec_*` / `map_*` / `hm_*` = migration, not canonical.

## Verdict

Design SSOT exists. Only `vec` include-smokes clean today. Harden map→set next; buffer/slice need mem runtime symbols. Deferred collections stay out of core until gated.

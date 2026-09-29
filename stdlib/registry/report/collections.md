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
| `vec` | **OK** | |
| `map` | FAIL | E2002 `str_new`; E3008 entity fields |
| `set` | FAIL | via map + E2002 |
| `deque` | FAIL | E1004 `*` |
| `buffer` | FAIL | linker unresolved call |
| `slice` | FAIL | E2002 `mem_cmp` / `mem_copy` |

## Naming

```text
vec.push / map.get / set.contains / deque.pushFront
buffer.write / slice.sub
```

Legacy `vec_*` / `map_*` / `hm_*` = migration, not canonical.

## Verdict

Design SSOT exists. Only `vec` include-smokes clean today. Harden map→set next; buffer/slice need mem runtime symbols. Deferred collections stay out of core until gated.

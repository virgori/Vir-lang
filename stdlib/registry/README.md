# Vir Stdlib API Registry

Flat, schema-closed Markdown registry for **user-facing** standard-library APIs.

**Philosophy**

```text
registry/ (flat)
  → 1 namespace = 1 file
  → unified FORMAT.md schema
  → 1 function = 1 structured entry
  → registry is SSOT for API Reference
  → curriculum is downstream
  → public architecture ≠ implementation layout
```


## Generic notation

Vir generics use parentheses `()`, never Rust/C++/TS `<>`:

```text
Result(T) · Result(T, E) · Option(T)
Vec(T) · Map(K, V) · Set(T) · Deque(T)
```

Write `Result(T)` when the error type is the default [`Error`](error.md); use `Result(T, E)` only when `E` is explicit. Do not omit the payload type in public signatures (void-success `Result` may stay bare until a unit form is audited).

**Process (mandatory for redesign clusters)**

1. Inventory current symbols in `stdlib/vir/`.
2. Close **Migration map** in the target namespace file(s).
3. Fill structured API entries (`proposed` / `planned` / …).
4. Only then change `.vri` sources / `stdlib.vri`.

## Layout

```text
stdlib/registry/
├── README.md
├── SCHEMA.md          ← closed schema (was “FORMAT.md”; see note below)
├── io.md / fs.md / path.md / env.md / cli.md / process.md
├── buffer.md / slice.md / vec.md / map.md / set.md / deque.md
├── option.md / result.md / error.md / panic.md
├── string.md / builder.md / char.md … collation.md
├── format.md / parse.md / fmt.md
└── SCHEMA.md
```

**Core Collections (4/4 design closed):** `vec` · `map` · `set` · `deque`.
Closed = documentation design, not implementation certification.

**Deferred / Specialized Collections** (physical modules may exist; **not**
canonical public core this wave):

```text
btree · heap · lru · ring · linkedlist · smallvec
skiplist · trie · bitset · bloom
ordered_map · concurrent_map · persistent
```

`hashmap.*` continues migrating into `map.*` per locked contract.

**Unicode data version:** **`pre-UCD`** (pin policy closed in
[`unicode.md`](unicode.md)). No invented `X.Y.Z` until the first UCD-derived
table import sets the shared version. Shared by Unicode modules.

**Float gate:** design criteria locked in [`format.md`](format.md) /
[`parse.md`](parse.md) — `format.float` / `parse.float` stay **planned** until
the suite passes. `fmt.float` / `builder.writeFloat` wait on that gate.

**Layering:** `string` · `format` · `parse` · native `$` · `fmt` · `builder` ·
`io` — each keeps its role; no silent overlap.

**Core stdlib design closed** (docs): io · fs · path · env · cli · process ·
buffer · slice · vec · map · set · deque · option · result · error · panic ·
text/unicode · format · parse · fmt.

Next docs: Data Formats — [`json`](json.md) first (draft).

> **Case-insensitive FS:** `FORMAT.md` and `format.md` collide on default APFS.
> Schema lives in **`SCHEMA.md`** only.
## I/O cluster (public vs implementation)

| Current (impl / registry name) | Public namespace | Role |
|---|---|---|
| `stdio` | `io` | console / std streams |
| `io.buffered` | `io` or internal | buffered Reader/Writer |
| `traits` | `io` (File ⊥ io — I8) | Reader/Writer/Seeker abstractions |
| `io.file` + `fs` / `fs.fs` | `fs` | filesystem + `File` handle |
| `rt/io` | *(internal)* | runtime implementation |
| `term.prompt` | `cli` | interactive prompts |
| `process` | `process` | lifecycle + subprocess; exit/abort |
| `buffer` (`mem/buffer.vri`) | `buffer` | owned binary storage |
| `slice` (`mem/slice.vri`) | `slice` | borrowed binary view |
| `collections.vec` | `vec` | owned growable `Vec(T)` |
| `option` (`core/option.vri`) | `option` | `Option(T)` helpers (`Some`/`None` language-level) |
| `result` (`core/result.vri`) | `result` | `Result(T, E)` helpers (`Ok`/`Err` language-level) |
| `error` (`error/error.vri`) | `error` | `ErrorKind` + `Error` + `IoError`; errno SSOT |
| `string` (`str/string.vri`) | `string` | immutable UTF-8 text; `str_*` impl-only |
| `builder` (`str/builder.vri`) | `builder` | mutable UTF-8 construction; always-valid |
| `char` (`str/char.vri`) | `char` | Unicode scalar properties |
| `str.unicode` | `unicode` | scalar + UTF-8 codec SSOT · version pin |
| `json` / `data.json` | `json` | RFC 8259 `JsonValue` |
| `str.encode` | `encode` | UTF-16LE / UTF-32LE bridges |
| `str.grapheme` | `grapheme` | extended grapheme clusters |
| `str.normalize` | `normalize` | NFC/NFD |
| `str.collation` | `collation` | compare + binary sort key |
| `format` (`io/format.vri`) | `format` | value → string primitives |
| *(new / from string+types)* | `parse` | strict string → `Result` |
| `fmt` (`fmt/fmt.vri`) | `fmt` | runtime `$` templates |
| `error` panic helpers | `panic` | non-returning abort |
| `collections.map` (+ hashmap) | `map` | hash map |
| `collections.set` | `set` | hash set |
| `collections.deque` | `deque` | double-ended queue |
| specialized collections.* | *(deferred)* | not core this wave |

User-facing docs never require knowing `rt/io`, `stdio.vri`, or `buffered.vri`.
Public filesystem is **`fs.*`** — not `file.*`.
Binary model: **`Buffer` + `Slice` + `string`** — no public `bytes` type.

## Active redesign docs

| File | Status |
|---|---|
| [`io.md`](io.md) | **Closed** — I1–I8; streams/`lines`/`chain`/`tee` planned; `print*`=`string` |
| [`fs.md`](fs.md) | **Closed** |
| [`path.md`](path.md) | **Closed** |
| [`cli.md`](cli.md) | **Closed** — `password` echo-off, no cleartext fallback |
| [`env.md`](env.md) | **Closed** — vars/args/paths; `exit`/`abort` → process |
| [`process.md`](process.md) | **Closed** — Command/Child; Buffer output; pipes=Reader/Writer |
| [`buffer.md`](buffer.md) / [`slice.md`](slice.md) / [`vec.md`](vec.md) | **Closed** |
| [`option.md`](option.md) / [`result.md`](result.md) / [`error.md`](error.md) | **Closed** |
| [`panic.md`](panic.md) | **Closed** — `panic.*` non-returning |
| [`string.md`](string.md) / [`builder.md`](builder.md) | **Closed** · `writeInt*` planned |
| Unicode pack (`char`…`collation`) | **Closed** · version pin `pre-UCD` |
| [`format.md`](format.md) / [`parse.md`](parse.md) | **Closed** int · float gate **locked** (API still planned) |
| [`fmt.md`](fmt.md) | **Closed** — runtime `$` templates; `Result` |
| [`map.md`](map.md) / [`set.md`](set.md) | **Closed** — copy-limited get; explicit hash/eq; free/isEmpty |
| [`deque.md`](deque.md) | **Closed** — ends API; Copy-limited peek; pop→None; Core Collections 4/4 |
| [`json.md`](json.md) | **Draft** — RFC 8259 surface; number=`int` until float gate |
| Specialized collections | **Deferred** — btree/heap/lru/… not canonical this wave |

Schema: [`SCHEMA.md`](SCHEMA.md). **No `.vri` renames until maps are accepted.**

## Scope

| In | Out |
|---|---|
| User libraries | `compiler.*`, `test.*`, `codegen.*`, `vss.*`, `wir.*` |
| Public contracts + migration maps | Lesson prose |
| Stable ids for renames | Package install / hashes (Viron) |

Physical load paths remain in [`../stdlib.vri`](../stdlib.vri).

## Authoring

1. Read [`SCHEMA.md`](SCHEMA.md).
2. Prefer Migration map before inventing new symbols.
3. Mark incomplete behavior (`cli.password`) as `incomplete` / `planned` — never as safe.
4. Do not rename source until the relevant map is closed.

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

Write `Result(T)` when the error type is the default [`Error`](error.md); use
`Result(T, E)` only when `E` is explicit. Void-success APIs use bare `Result`
(`Ok()` / `Err`) — decision **A** locked; not `Result(void)` until unit is a
confirmed Vir generic argument.

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
├── format.md / parse.md / fmt.md / json.md
├── crypto.md / tls.md
└── report/ …
```

**Crypto / TLS (docs draft):** [`crypto.md`](crypto.md) · [`tls.md`](tls.md) —
experimental; not production-ready; first harden `hash` → `hmac` → `rng`.
`rand` is outside cryptographic guarantees.

**Remaining-library audits:** [`report/AUDIT.md`](report/AUDIT.md) (collections,
core, string, fs, format, data, net, concurrency, misc + compile smoke).
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

**Decisions A–D (locked — docs):**

| ID | Decision |
|---|---|
| A | Void success → bare `Result` |
| B1 | Unicode pin `pre-UCD` — no conformance claim without UCD import+tests |
| C | Non-finite lowercase `nan` / `inf` / `-inf` only; F1 = shortest + fixed |
| D1–D5 | See [`json.md`](json.md) |

**Decisions Q1–Q8 (locked — docs):**

| ID | Decision |
|---|---|
| Q1 | `unicode.decodeUtf8` → `Result(Utf8Decoded)` · entity `codepoint` + `nbytes` |
| Q2 | `format.float(value)` + `format.floatFixed(value, prec)` — no overloading |
| Q3 | JSON int out of `int` domain → `InvalidData` (no silent float) |
| Q4 | `json.number(int)` keep; `json.numberFloat(float)` planned — no overload |
| Q5 | No `.vri` migration yet — finish registry + related contracts first |
| Q6 | No remote ship this round — docs-only commit later after consistency audit; no PR now |
| Q7 | Finish `json.md` → then **csv** wave; TOML/YAML/XML later |
| Q8 | No bulk `closed` upgrades — audit each draft; close only when surface/ownership/error/lifecycle/semantics suffice |

**Unicode data version:** **`pre-UCD`**. Shared by Unicode modules. One UCD pin
when a generator lands.

**Float gate:** F1–F6 locked — stay **planned**; never auto-`stable`.

**Naming:** CORE SPEC names are **canonical** in docs; older names =
migration `previous`. New SPEC APIs without source yet = **`planned`**
(verify at implement).

**Json:** [`json.md`](json.md) **design closed** — `parse`/`stringify`;
`asArray`/`asObject` planned; ownership/float/error-map gates.

**Core registry cluster (design closed):**

| Module | Canonical highlights · gates |
|---|---|
| [`option`](option.md) | `unwrapOr` / `unwrapOrElse`; zip deferred; HOF planned |
| [`result`](result.md) | `unwrapOr`; HOF/`all` planned |
| [`vec`](vec.md) | Element Drop; `vec_*` migration |
| [`buffer`](buffer.md) / [`slice`](slice.md) | `get`; borrow/`slice.len` gates |
| [`fs`](fs.md) / [`path`](path.md) | `readText`/`atLeast`/`mkdir`/`flush` planned; `extension`/`isAbsolute`; `normalize` planned |
| [`json`](json.md) | `parse`/`stringify`; ownership/float gates |

**Layering:** `string` · `format` · `parse` · native `$` · `fmt` · `builder` ·
`io` — each keeps its role; no silent overlap.

**Next docs:** wave **`csv`** (Q7). No `.vri` / no PR (Q5–Q6).

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
| [`fs.md`](fs.md) | **Closed** — F1–F4; all path args `Path`; `*Text`/exact planned |
| [`path.md`](path.md) | **Closed** — P1–P2; opaque Path; POSIX `/` today |
| [`cli.md`](cli.md) | **Closed** — `password` echo-off, no cleartext fallback |
| [`env.md`](env.md) | **Closed** — vars/args/paths; `exit`/`abort` → process |
| [`process.md`](process.md) | **Closed** — Command/Child; Buffer output; pipes=Reader/Writer |
| [`buffer.md`](buffer.md) / [`slice.md`](slice.md) / [`vec.md`](vec.md) | **Closed** — B1 / S1–S2 / V1–V3 |
| [`option.md`](option.md) / [`result.md`](result.md) / [`error.md`](error.md) | **Closed** — O1–O4 / R1–R3; HOF planned |
| [`panic.md`](panic.md) | **Closed** — `panic.*` non-returning |
| [`string.md`](string.md) / [`builder.md`](builder.md) | **Closed** · `writeInt*` planned |
| Unicode pack (`char`…`collation`) | **Closed** · version pin `pre-UCD` |
| [`format.md`](format.md) / [`parse.md`](parse.md) | **Closed** int · float gate **locked** (API still planned) |
| [`fmt.md`](fmt.md) | **Closed** — runtime `$` templates; `Result` |
| [`map.md`](map.md) / [`set.md`](set.md) | **Closed** — copy-limited get; explicit hash/eq; free/isEmpty |
| [`deque.md`](deque.md) | **Closed** — ends API; Copy-limited peek; pop→None; Core Collections 4/4 |
| [`json.md`](json.md) | **Closed** (design) · ownership/float/error-map gates; `read`/`write` canonical |
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

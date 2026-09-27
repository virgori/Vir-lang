---
module: io
title: IO
summary: Standard streams, Reader/Writer/Seeker abstractions, buffered adapters, and stream composition.
source:
  - name: stdio
    path: vir/io/stdio.vri
  - name: traits
    path: vir/io/traits.vri
  - name: io.buffered
    path: vir/io/buffered.vri
  - name: io
    path: vir/rt/io.vri
status: closed
aliases: [stdio]
notes: >-
  Contract closed. Standard streams, lines(), chain, tee remain planned.
  until = consume+exclude; delim = non-empty byte sequence; line/byte = Option
  forms; print* = string only. File trait independent of io namespace. Docs only.
---

# IO

Standard streams, stream traits, buffered adapters, and composition helpers.

**Docs closed ≠ implementation complete.** Planned APIs stay planned.

**Principles**

- Public API uses **dot-style** (`io.print`, `Reader.exact`).
- No C/internal names in public (`br_*`, `bw_*`, `file_*`).
- `io` = transport; interactive → [`cli`](cli.md); files → [`fs`](fs.md);
  value render → [`format`](format.md); runtime templates → [`fmt`](fmt.md).
- [`File`](fs.md) / sockets may implement `Reader`/`Writer` without merging
  namespaces (**I8**).

## Contract lock (closed)

| ID | Decision | Doc status |
|---|---|---|
| I1 | `io.stdin()` / `stdout()` / `stderr()` → non-owning standard-stream handles | **planned** |
| I2 | Reader surface below; `lines()` waits on iterator protocol | locked / `lines` planned |
| I3 | `until` **consumes + excludes** delimiter | locked |
| I4 | `io.print*` accepts **`string` only** — no implicit formatting | locked |
| I5 | `chain` / `tee` combinators; `tee` fail-fast, non-atomic | **planned** |
| I6 | `writeAll`, `BufferedReader` / `BufferedWriter` / `LineWriter` | locked |
| I7 | `byte()` → `Result(Option(u8))` / EOF | locked |
| I8 | File trait ⊥ `io` namespace | locked |

### Reader methods (locked)

```text
exact(n) / atLeast(n) / all() / limit(n)
until(delim) / line() / lines() / byte()
```

| Method | Contract |
|---|---|
| `exact(n)` | Read exactly `n` bytes; early EOF → `UnexpectedEof` |
| `atLeast(n)` | Read at least `n` bytes; may return more from same batch; EOF before `n` → error |
| `all()` | Read to EOF → `Buffer` (may be empty) |
| `limit(n)` | Cap reader at `n` bytes; does not consume past the limit |
| `until(delim)` | Non-empty **byte sequence**; consume delim, **exclude** from payload; cross-read recognition required |
| `line()` | One UTF-8 line; strip LF/CRLF; **not** the same as `until` |
| `lines()` | **planned** — iterator return type not locked |
| `byte()` | One byte or explicit EOF |

`until` outcomes:

- EOF with no data → `Ok(None)`
- Delimiter at start → `Ok(Some(empty Buffer))`
- Trailing data without delim → return that chunk; subsequent call hits EOF

`line()` → `Result(Option(string))`: LF and CRLF; no whitespace trim;
invalid UTF-8 → `InvalidData`.

### Writer / buffered (locked)

```text
write(data) / writeAll(data) / flush()
BufferedReader / BufferedWriter / LineWriter
```

- `write` may be partial; `writeAll` completes or errors.
- Progress stall (`0` bytes while data remains) → error (no infinite loop).
- `BufferedWriter.flush` explicit; `LineWriter` flushes on `\n` and supports
  explicit `flush`. Flush errors must not be swallowed on `Result` APIs.

### Console (locked)

`io.print` / `println` / `eprint` / `eprintln` / `readLine` — fire-and-forget,
**`string` only**. Format numbers via native interpolation or
[`format`](format.md) first — not implicit `print(255)`.

## Error contract — **closed**

Vir has language `throw`/`ensure`/`revert` (`int`) **and** stdlib `Result` / `Option`.
Existing I/O (`traits`, `file`, `buffered`, `fs`) already uses **`Result`**. Do **not**
migrate ordinary I/O failures to `throw int`.

| Case | Mechanism |
|---|---|
| Recoverable I/O failure | `Result` |
| Normal read progress | `Ok(n)` — `n` = bytes transferred |
| Normal EOF from `read` | `Ok(0)` |
| I/O failure | `Err(…)` — prefer `IoError` with `kind: ErrorKind` when structured; see [`error.md`](error.md) |
| `exact` / `atleast` short EOF | `Err` with `ErrorKind.UnexpectedEof` |
| Genuine absence (no value, not a fault) | `Option` (`Some` / `None`) |
| Cleanup | `ensure` |
| Abort / invariant / logic bug | `throw` / `panic` |
| `stdio` convenience (`print` / `readLine`) | keep current fire-and-forget; no fake error propagation until stream APIs exist |

**Signatures use Vir generics with `()`** — e.g. `Result(T)`, `Option(T)`, `Result(Option(u8))`. Default `Result` error type is `Error` unless stated.

### Reader family (target semantics)

```vir
reader.read(buf)
    Ok(n)       # n bytes
    Ok(0)       # EOF
    Err(error)  # I/O failure

reader.exact(buf)
    Ok(n)       # request satisfied (n == buf len)
    Err(…)      # UnexpectedEof if EOF early; or other I/O failure

reader.atleast(buf, min)
    Ok(n)       # n >= min
    Err(…)      # UnexpectedEof or I/O failure

reader.all()
    Ok(Buffer)
    Err(error)

reader.until(delim)   # delim: one byte (int)
    Ok(Buffer)
    Err(error)

reader.line()
    Ok(string)  # UTF-8 text after line boundary
    Err(error)

reader.byte()
    # three outcomes — EOF ≠ error
    Ok(Some(b))   # one byte
    Ok(None)      # EOF / no more bytes
    Err(error)    # I/O failure
```

Docs describe outcomes with Vir `Result` / `Option` nesting when the type
system allows `Ok(Option)` / `Err(IoError)`. **No new public syntax.** If nesting
is awkward in a given compiler stage, keep the three outcomes in the contract
and pick the nearest expressible encoding — never collapse error into `None`.

### `byte()` — current impl is **incomplete** (bug)

`br_read_byte` calls `_br_fill` then **ignores** `Result`: fill failure + empty
buffer → `None`. That swallows I/O errors. **Must fix** before public `byte()`.

### `stdio` vs streams

Keep for now (no error migration in the rename pass):

```vir
io.print / io.println / io.eprint / io.eprintln / io.readLine
```

Error-aware path comes later via:

```vir
io.stdout().write(...)
io.stdout().flush()
```

## Bytes / buffer model — **closed**

Do **not** invent a third public `bytes` type. Reuse existing memory types:

| Type | Role |
|---|---|
| `Slice` | borrowed binary view `(ptr, len)` — caller-owned memory |
| `Buffer` | owned / growable binary storage |
| `string` | text (UTF-8), never the default for opaque file/stream payloads |

**Invariant:** `Slice` to borrow bytes, `Buffer` to own bytes, `string` only for text.
`Reader` is **binary-first**.

| API | Payload | Impl note |
|---|---|---|
| `read(buf)` | `Slice` | present (traits) |
| `exact(buf)` | `Slice` | missing |
| `atleast(buf, min)` | `Slice` | missing |
| `all()` | `Ok(Buffer)` | today `read_all` → Buffer-ish; align to `Buffer` |
| `until(delim)` | `Ok(Buffer)`, `delim: int` (one **byte**) | missing; not a string delimiter |
| `line()` | `Ok(string)` | missing on trait; UTF-8 decode at line boundary |
| `fs.read` | `Ok(Buffer)` | today `fs.read` → `string` — **change** payload |
| `fs.text` | `Ok(string)` | **missing** — explicit text convenience |

`until` and `line` are **not** aliases (locked): `until` is binary delimiter
search (consume + exclude); `line` is UTF-8 text + LF/CRLF rules.

`until(delim)` takes a **non-empty byte sequence** (may be multi-byte); must
recognize delimiters spanning read boundaries.

## Impl legend

| Impl | Meaning |
|---|---|
| **present** | Exists in source; public name already matches (or close enough to keep) |
| **rename** | Exists; must surface under the proposed public name |
| **remove** | Exists as public/export alias; drop from public surface |
| **move** | Exists; ownership moves to another namespace |
| **missing** | Not implemented |
| **incomplete** | Exists but behavior is stub/wrong/unsafe |
| **internal** | Keep in source; never document as public |

---

## Boundary

| In `io` | Out |
|---|---|
| `io.print` / `println` / `eprint` / `eprintln` | `cli.ask` / `confirm` / `choose` / `password` |
| `io.stdin` / `stdout` / `stderr` as `Reader`/`Writer` | `fs.open` / whole-file helpers |
| `Reader` / `Writer` / `Seeker` / `ReadWriter` | `format.int` / padding |
| `BufferedReader` / `BufferedWriter` / `LineWriter` | `rt/io` symbols |
| `io.copy` / `chain` / `tee` / advanced utilities | |

---

## 1. Console helpers

| Current | Public API | Impl | Action |
|---|---|---|---|
| `print` | `io.print` | present → **rename** ns | keep semantics; public as `io.print` |
| `println` | `io.println` | present → **rename** ns | keep |
| `print_str` | — | present | **remove** public alias |
| `print_ln` | — | present | **remove** public alias |
| `eprint` | `io.eprint` | present → **rename** ns | keep |
| `eprintln` | `io.eprintln` | present → **rename** ns | keep |
| `eprint_str` | — | present | **remove** public alias |
| `eprint_ln` | — | present | **remove** public alias |
| `readln` | `io.readLine` | present → **rename** | rename (`readln` → `readLine`) |
| `read_line` | — | present | **remove** public alias |
| `read_line_secret` | `cli.password` | present | **move** + **incomplete** (see `cli.md`) |
| `input` | `cli.ask` | present | **move** |
| `flush` | — | incomplete stub | **remove** free func; use stream `flush` |
| `flush_stdout` | `io.stdout().flush()` | incomplete stub | **replace** |
| `flush_stderr` | `io.stderr().flush()` | incomplete stub | **replace** |
| `print_raw_*` | — | present | **internal** |

### Standard streams — **missing**

```vir
io.stdin()  -> Reader
io.stdout() -> Writer
io.stderr() -> Writer
```

Must use the same `Reader` / `Writer` abstraction — no special-cased stream-only API surface.

| ID | Public | Impl | Notes |
|---|---|---|---|
| `io.stdin` | `io.stdin() -> Reader` | **missing** | Today stdin is only via `readln` |
| `io.stdout` | `io.stdout() -> Writer` | **missing** | Today stdout via `print*` only |
| `io.stderr` | `io.stderr() -> Writer` | **missing** | Today stderr via `eprint*` only |

### API index (console)

| ID | Symbol | Signature | Status | Impl |
|---|---|---|---|---|
| `io.print` | `io.print` | `io.print(s: string) -> void` | proposed | rename |
| `io.println` | `io.println` | `io.println(s: string) -> void` | proposed | rename |
| `io.eprint` | `io.eprint` | `io.eprint(s: string) -> void` | proposed | rename |
| `io.eprintln` | `io.eprintln` | `io.eprintln(s: string) -> void` | proposed | rename |
| `io.readLine` | `io.readLine` | `io.readLine() -> string` | proposed | rename |
| `io.stdin` | `io.stdin` | `io.stdin() -> Reader` | planned | missing |
| `io.stdout` | `io.stdout` | `io.stdout() -> Writer` | planned | missing |
| `io.stderr` | `io.stderr` | `io.stderr() -> Writer` | planned | missing |

---

<a id="io.print"></a>
## `io.print`

<!--
id: io.print
api: io.print
previous: print
-->

```vir
io.print(value) -> void
```

Writes to **stdout** without a trailing newline.

### Parameters

#### `value`

**`string` only** (I4 locked). No implicit formatting — use native `$` or
[`format`](format.md) / [`fmt`](fmt.md) first.

### Returns

None. Side effect on stdout.

### Errors

None at Vir API layer today.

### Example

```vir
io.print("hi")
```

### See also

- `io.println`
- `io.stdout`

---

<a id="io.println"></a>
## `io.println`

<!--
id: io.println
api: io.println
previous: println
-->

```vir
io.println(value) -> void
```

Writes to stdout then a single LF (`\n`).

### Parameters

#### `value`

Same rules as `io.print`.

### Returns

None.

### Errors

None at Vir API layer today.

### Example

```vir
io.println("ready")
```

---

<a id="io.eprint"></a>
## `io.eprint`

<!--
id: io.eprint
api: io.eprint
previous: eprint
-->

```vir
io.eprint(value) -> void
```

Writes to **stderr** without a newline (diagnostics that must not corrupt piped stdout).

### Parameters

#### `value`

Same rules as `io.print`.

### Returns

None.

### Errors

None at Vir API layer today.

### Example

```vir
io.eprint("warn: ")
io.eprintln("missing")
```

---

<a id="io.eprintln"></a>
## `io.eprintln`

<!--
id: io.eprintln
api: io.eprintln
previous: eprintln
-->

```vir
io.eprintln(value) -> void
```

Writes to stderr then LF.

### Parameters

#### `value`

Line body for stderr.

### Returns

None.

### Errors

None at Vir API layer today.

### Example

```vir
io.eprintln("failed")
```

---

<a id="io.readLine"></a>
## `io.readLine`

<!--
id: io.readLine
api: io.readLine
previous: readln
-->

```vir
io.readLine() -> string
```

Reads one line from stdin up to LF. Result excludes LF; trailing CR from CRLF is stripped.

Convenience over `io.stdin().line()` once streams exist. Until then, maps to today’s `readln`.

### Parameters

None.

### Returns

`string` — line bytes without `\n` / trailing `\r`; may be empty.

### Errors

None as `Result` today. EOF returns what was collected.

### Example

```vir
let line = io.readLine()
```

### See also

- `Reader.line`
- `cli.ask`

---

<a id="io.stdin"></a>
## `io.stdin`

<!--
id: io.stdin
api: io.stdin
-->

```vir
io.stdin() -> Reader
```

Handle for process standard input as a `Reader`.

### Parameters

None.

### Returns

`Reader` sharing the same abstraction as files/buffers/network bodies.

### Errors

TBD when implemented.

### Example

```vir
let line = io.stdin().line()
```

### Notes

**missing.** No stream object today.

---

<a id="io.stdout"></a>
## `io.stdout`

<!--
id: io.stdout
api: io.stdout
-->

```vir
io.stdout() -> Writer
```

Handle for process standard output as a `Writer`. Flush via `io.stdout().flush()`.

### Parameters

None.

### Returns

`Writer`

### Errors

TBD.

### Example

```vir
io.stdout().writeAll(data)
io.stdout().flush()
```

### Notes

**missing.** Replaces free `flush` / `flush_stdout`.

---

<a id="io.stderr"></a>
## `io.stderr`

<!--
id: io.stderr
api: io.stderr
-->

```vir
io.stderr() -> Writer
```

Handle for process standard error as a `Writer`. Flush via `io.stderr().flush()`.

### Parameters

None.

### Returns

`Writer`

### Errors

TBD.

### Example

```vir
io.stderr().flush()
```

### Notes

**missing.** Replaces `flush_stderr`.

---

## 2. `Reader`

Current: `interface Reader` with `read(buf: Slice) -> Result` (`Ok(n)` bytes; `Ok(0)` = EOF) in `vir/io/traits.vri`. **Not exported.**

| Public method | Signature (target) | Impl | Notes |
|---|---|---|---|
| `read` | `reader.read(buf: Slice) -> Result(int)` | **present** | `Ok(n)` / `Ok(0)` / `Err` |
| `exact` | `reader.exact(buf: Slice) -> Result(int)` | **missing** | or `exact(n) -> Result(Buffer)` per contract lock |
| `atleast` | `reader.atleast(buf: Slice, min: int) -> Result(int)` | **missing** | `n >= min` or `Err(UnexpectedEof)` |
| `all` | `reader.all() -> Result(Buffer)` | **present** as `read_all` | **rename** → method |
| `limit` | `reader.limit(max: int) -> Reader` | **missing** | composable cap; no I/O yet |
| `until` | `reader.until(delim) -> Result(Option(Buffer))` | **missing** | non-empty byte seq; consume+exclude |
| `line` | `reader.line() -> Result(Option(string))` | **missing** on trait | LF/CRLF; `InvalidData` on bad UTF-8 |
| `lines` | `reader.lines()` | **planned** | iterator type not locked |
| `byte` | `reader.byte() -> Result(Option(u8))` | **incomplete** | EOF = `Ok(None)`; must not swallow fill errors |

### Semantics

#### `read` — present

```vir
reader.read(buf)
```

Read into buffer. Does **not** guarantee the buffer is filled.

#### `exact` — missing

```vir
reader.exact(buf)
```

Read until buffer is full or EOF/error. Short name instead of `readExact`.

#### `atleast` — missing

```vir
reader.atleast(buf, min)
```

Read at least `min` bytes into `buf`.

#### `all` — rename from helper

```vir
reader.all()
```

Read remaining data until EOF. Replaces free `read_all(reader)`.

#### `limit` — missing

```vir
let limited = reader.limit(1024)
let body = reader.limit(size).all()
```

Returns a `Reader` capped at `max` bytes. Does not read immediately. Must compose.

#### `until` — missing

```vir
reader.until(delim)
```

Read until delimiter. If `Reader` is byte-oriented, `delim` must not be text-only by accident — finalize against Vir’s buffer representation.

#### `line` / `lines` — missing on trait

```vir
reader.line()
for line in reader.lines()
    ...
end
```

---

<a id="io.Reader.read"></a>
## `Reader.read`

<!--
id: io.Reader.read
api: Reader.read
-->

```vir
(r: Reader).read(buf: Slice) -> Result(int)
```

Primitive read into caller-owned borrowed memory; may return short count.

### Parameters

#### `buf: Slice`

Destination view. `buf.len` = max bytes for this call.

### Returns

`Result` — `Ok(n)` bytes read; `Ok(0)` = EOF; `Err(…)` = I/O failure.

### Errors

I/O failure (today `Err`).

### Example

```vir
let n = reader.read(buf)
```

---

<a id="io.Reader.exact"></a>
## `Reader.exact`

<!--
id: io.Reader.exact
api: Reader.exact
-->

```vir
(r: Reader).exact(buf: Slice) -> Result(int)
```

Fill `buf` completely or fail/EOF.

### Parameters

#### `buf: Slice`

Borrowed destination that must be filled entirely on success.

### Returns

`Result` — `Ok(n)` with `n == buf.len`; `Err(UnexpectedEof)` if EOF early; other `Err` on I/O failure.

### Errors

EOF before full; I/O error.

### Example

```vir
reader.exact(buf)
```

### Notes

**missing.**

---

<a id="io.Reader.atleast"></a>
## `Reader.atleast`

<!--
id: io.Reader.atleast
api: Reader.atleast
-->

```vir
(r: Reader).atleast(buf: Slice, min: int) -> Result(int)
```

Read at least `min` bytes into `buf` (`min` ≤ `buf.len`).

### Parameters

#### `buf: Slice`

Borrowed destination.

#### `min: int`

Minimum bytes required; unit = bytes; `>= 0` and `<= buf.len`.

### Returns

`Result` — `Ok(n)` with `n >= min`; `Err(UnexpectedEof)` or other I/O `Err`.

### Example

```vir
reader.atleast(buf, 16)
```

### Notes

**missing.**

---

<a id="io.Reader.all"></a>
## `Reader.all`

<!--
id: io.Reader.all
api: Reader.all
previous: read_all
-->

```vir
(r: Reader).all() -> Result(Buffer)
```

Read all remaining bytes until EOF into an owned `Buffer`.

### Parameters

None (receiver).

### Returns

`Result(Buffer)` — empty Buffer allowed; `Err(…)` on I/O failure.

### Errors

I/O error while reading.

### Example

```vir
let data = reader.all()
# Ok(Buffer) or Err(...)
```

### Notes

**rename** from free `read_all` in `traits.vri`; align payload to `Buffer`.

---

<a id="io.Reader.limit"></a>
## `Reader.limit`

<!--
id: io.Reader.limit
api: Reader.limit
-->

```vir
(r: Reader).limit(max) -> Reader
```

Return a Reader that allows at most `max` bytes. No I/O until subsequent reads.

### Parameters

#### `max: int`

Max bytes readable through the returned reader; unit = bytes; `>= 0`.

### Returns

`Reader` — composable wrapper.

### Errors

None at construction.

### Example

```vir
let body = reader.limit(size).all()
```

### Notes

**missing.**

---

<a id="io.Reader.until"></a>
## `Reader.until`

<!--
id: io.Reader.until
api: Reader.until
-->

```vir
(r: Reader).until(delim) -> Result(Option(Buffer))
```

Read until a single **byte** delimiter into an owned `Buffer`. Delimiter is
**consumed** from the stream but **not** included in the returned `Buffer`.

Example: input `abc,def` → `until(',')` yields `abc`; next read starts at `def`.

Not a string match; not an alias of `line()`.

### Parameters

#### `delim: int`

One byte (`0…255`), e.g. `0x0A` or `','` if that literal is one byte.

### Returns

`Result` — `Ok(Buffer)` without the delimiter byte.

- Data then EOF before `delim`: **`Ok(partial)`** (not an error).
- Immediate EOF (no bytes): **`Ok` empty `Buffer`** (document as empty success).
- I/O failure: `Err(…)`.

### Errors

I/O failure; optional stream-too-long if a size cap exists later.

### Example

```vir
let a = reader.until(0x2C)   # ','
let b = reader.until(0x2C)
```

### Notes

**missing.** Multi-byte delimiters out of scope.

---

<a id="io.Reader.line"></a>
## `Reader.line`

<!--
id: io.Reader.line
api: Reader.line
-->

```vir
(r: Reader).line() -> Result(Option(string))
```

Binary → text: read one line, decode as **strict UTF-8** `string` (newline
stripping aligned with `io.readLine`). Not the same as `until(0x0A)` (`Buffer`).

### Parameters

None.

### Returns

`Result(Option(string))` — `None` at EOF with no line; `Err` on I/O or invalid UTF-8 (`InvalidData`).

### Errors

I/O error; `InvalidData` / `InvalidEncoding` on bad UTF-8 (strict; no `�`).

### Example

```vir
let line = reader.line()
```

### Notes

**missing** on trait. Partial internal: `br_read_line` → `string` today.

---

<a id="io.Reader.lines"></a>
## `Reader.lines`

<!--
id: io.Reader.lines
api: Reader.lines
-->

```vir
(r: Reader).lines()
```

Return an iterator/sequence that yields lines.

### Parameters

None.

### Returns

Line sequence (type TBD — needs iterator story).

### Errors

Deferred to iteration.

### Example

```vir
for line in reader.lines()
    io.println(line)
end
```

### Notes

**missing.**

---

## 3. `Writer`

Current: `write(data: Slice)`, `flush` on interface. Free helper `write_all`.

| Public method | Signature (target) | Impl | Notes |
|---|---|---|---|
| `write` | `writer.write(data) -> int` | **present** | Primitive; may be short |
| `flush` | `writer.flush()` | **present** on trait; stdio flush **incomplete** | |
| `writeAll` | `writer.writeAll(data)` | **present** as free `write_all` | **rename** → method; not `all(data)` |

---

<a id="io.Writer.write"></a>
## `Writer.write`

<!--
id: io.Writer.write
api: Writer.write
-->

```vir
(w: Writer).write(data) -> /* byte count */
```

Primitive write; may write fewer bytes than `data` length.

### Parameters

#### `data`

Source bytes (`Slice` today).

### Returns

Bytes written (`0 … len`).

### Errors

I/O error.

### Example

```vir
let n = writer.write(data)
```

---

<a id="io.Writer.flush"></a>
## `Writer.flush`

<!--
id: io.Writer.flush
api: Writer.flush
-->

```vir
(w: Writer).flush()
```

Push buffered bytes to the underlying sink.

### Parameters

None.

### Returns

None / Result TBD.

### Errors

Flush failure when buffering is real.

### Example

```vir
writer.flush()
```

### Notes

Trait method **present**. Stdio free flushes are **incomplete** stubs.

---

<a id="io.Writer.writeAll"></a>
## `Writer.writeAll`

<!--
id: io.Writer.writeAll
api: Writer.writeAll
previous: write_all
-->

```vir
(w: Writer).writeAll(data)
```

Write entire `data`, retrying short writes. Not named `all(data)` — unclear for writers.

### Parameters

#### `data`

Full payload to write.

### Returns

Success / error.

### Errors

I/O error before completion.

### Example

```vir
writer.writeAll(data)
```

### Notes

**rename** from free `write_all`. Name may shorten later if better vocabulary appears.

---

## 4. `Seeker`

| Public | Impl | Notes |
|---|---|---|
| `Seeker.seek(offset, from)` | **present** (`whence: SeekFrom`) | Keep name `seek` |
| `SeekFrom` | **present** (`Start` / `Current` / `End`) | Keep |

Do not rename to `to` / `move`.

---

<a id="io.Seeker.seek"></a>
## `Seeker.seek`

<!--
id: io.Seeker.seek
api: Seeker.seek
-->

```vir
(s: Seeker).seek(offset: int, from: SeekFrom)
```

Move position by `offset` **bytes** relative to `from`.

### Parameters

#### `offset: int`

Byte displacement (sign depends on `from`).

#### `from: SeekFrom`

`Start` / `Current` / `End`.

### Returns

New absolute byte position (today’s interface returns position).

### Errors

Invalid seek; I/O error.

### Example

```vir
seeker.seek(0, SeekFrom.Start)
```

---

## 5. Composite traits & `io.copy`

| Item | Public | Impl | Action |
|---|---|---|---|
| `Reader` | `Reader` | present, no export | keep; export later |
| `Writer` | `Writer` | present, no export | keep |
| `Seeker` | `Seeker` | present, no export | keep |
| `ReadWriter` | `ReadWriter` | present, no export | keep |
| `copy(reader, writer)` | `io.copy(src, dst)` | present as free `copy` | **rename** |

No impl-prefix types in public API.

---

<a id="io.copy"></a>
## `io.copy`

<!--
id: io.copy
api: io.copy
previous: copy
-->

```vir
io.copy(src: Reader, dst: Writer)
```

Copy from `src` to `dst` until EOF. Namespace-level because it spans two streams.

### Parameters

#### `src: Reader`

Source stream.

#### `dst: Writer`

Destination stream.

### Returns

Total bytes copied (today `copy` returns that in `Ok`).

### Errors

Read or write failure.

### Example

```vir
io.copy(io.stdin(), io.stdout())
```

### Notes

**rename** from free `copy` in `traits.vri`. Depends on `io.stdin`/`stdout` for the example — those are **missing**.

---

## 6. `BufferedReader`

Internal today (**must not** be public names):  
`buffered_reader_new`, `buffered_reader_with_cap`, `br_read`, `br_read_byte`, `br_read_line`, `br_is_eof`, `br_close`.

| Public | Impl | Notes |
|---|---|---|
| type `BufferedReader` | **present** | keep type name |
| constructor | present as `buffered_reader_*` | **rename** to Vir constructor convention (not locked here) |
| `read` / `exact` / `atleast` / `all` / `limit` / `until` / `line` / `lines` | partial via `br_*` | methods must match `Reader` semantics |
| `byte()` | `br_read_byte` | **rename** |
| `close()` | `br_close` | **rename** |
| `isEof` / `br_is_eof` | present | **not** public for now — prefer EOF via read/result |

---

<a id="io.BufferedReader"></a>
## `BufferedReader`

<!--
id: io.BufferedReader
api: BufferedReader
-->

```vir
# type BufferedReader  — implements Reader (target)
```

Buffered adapter over an underlying source (today: raw `fd`).

### Public methods (target)

```vir
buffer.read(buf)
buffer.byte()
buffer.line()
buffer.lines()
buffer.until(delim)
buffer.exact(buf)
buffer.atleast(buf, min)
buffer.all()
buffer.limit(max)
buffer.close()
```

### Parameters / Returns / Errors

Same semantics as `Reader.*` for shared operations. `byte()` returns one byte or EOF. `close()` releases resources.

### Example

```vir
# after construction convention is fixed:
# let line = buffer.line()
```

### Notes

Impl **present** under `br_*` names — all **rename**. Shared ops **missing** on the type as true `Reader` methods (`exact`, `limit`, …).

---

## 7. `BufferedWriter`

Internal: `buffered_writer_new`, `bw_write`, `bw_write_byte`, `bw_write_str`, `bw_flush`, `bw_close`.

| Public | Impl | Action |
|---|---|---|
| type `BufferedWriter` | present | keep |
| constructor | `buffered_writer_new` | **rename** |
| `write` | `bw_write` | **rename** |
| `byte` | `bw_write_byte` | **rename** |
| `string` | `bw_write_str` | **rename** |
| `writeAll` | missing as method | **missing** / compose via retries |
| `flush` | `bw_flush` | **rename** |
| `close` | `bw_close` | **rename** |

Do not expose `bw_*` / `buffered_writer_*`.

---

<a id="io.BufferedWriter"></a>
## `BufferedWriter`

<!--
id: io.BufferedWriter
api: BufferedWriter
-->

```vir
# type BufferedWriter — implements Writer (target)
```

### Public methods (target)

```vir
buffer.write(data)
buffer.byte(value)
buffer.string(value)
buffer.writeAll(data)
buffer.flush()
buffer.close()
```

### Notes

Core write/flush/close **present** under `bw_*`. `writeAll` as method **missing**.

---

## 8. `LineWriter`

Internal: `line_writer_new`, `lw_write`, `lw_close`.

| Public | Impl | Action |
|---|---|---|
| type `LineWriter` | present | keep |
| constructor | `line_writer_new` | **rename** |
| `write` | `lw_write` | **rename** |
| `flush` | missing as named | **missing** / via write policy |
| `close` | `lw_close` | **rename** |

No `lw_*` in public.

---

<a id="io.LineWriter"></a>
## `LineWriter`

<!--
id: io.LineWriter
api: LineWriter
-->

```vir
# type LineWriter
```

### Public methods (target)

```vir
writer.write(data)
writer.flush()
writer.close()
```

### Notes

**present** under `lw_*`; public method names **rename**. Explicit `flush` **missing**.

---

## 9. Stream composition

| Public | Signature (target) | Impl | Status |
|---|---|---|---|
| `io.copy` | `io.copy(src, dst)` | present as `copy` | rename |
| `io.chain` | `io.chain(a, b) -> Reader` | **missing** | planned |
| `io.tee` | `io.tee(reader, writer) -> Reader` | **missing** | planned |

---

<a id="io.chain"></a>
## `io.chain`

<!--
id: io.chain
api: io.chain
-->

```vir
io.chain(a: Reader, b: Reader) -> Reader
```

Concatenate readers into one continuous `Reader`. Multi-reader overload later if types allow.

### Parameters

#### `a`, `b`

Readers read in order; after `a` EOF, continue with `b`.

### Returns

`Reader`

### Errors

Deferred to reads.

### Example

```vir
let r = io.chain(a, b)
```

### Notes

**missing.**

---

<a id="io.tee"></a>
## `io.tee`

<!--
id: io.tee
api: io.tee
-->

```vir
io.tee(reader: Reader, writer: Writer) -> Reader
```

Reader that yields from `reader` while copying observed bytes to `writer` (logging, hashing, inspection).

### Parameters

#### `reader`

Source.

#### `writer`

Side channel for duplicated bytes.

### Returns

`Reader`

### Errors

Deferred; write failures on tee path TBD.

### Example

```vir
let r = io.tee(src, logWriter)
```

### Notes

**missing.**

---

## 10. Advanced utilities — **planned / missing**

Mark `planned` until use-cases and signatures are fixed. Not `stable`.

| Public | Signature (target) | Impl | Use |
|---|---|---|---|
| `io.pipe` | `io.pipe()` | **missing** | paired reader/writer |
| `io.cursor` | `io.cursor(data)` | **missing** | memory as read/write/seek stream |
| `io.sink` | `io.sink() -> Writer` | **missing** | discard writer |
| `io.empty` | `io.empty() -> Reader` | **missing** | always-EOF reader |
| `io.repeat` | `io.repeat(value) -> Reader` | **missing** | infinite/repeated bytes |

---

<a id="io.pipe"></a>
## `io.pipe`

<!--
id: io.pipe
api: io.pipe
-->

```vir
io.pipe()
```

Create a connected reader/writer pair (exact return type TBD).

### Parameters

None.

### Returns

Pipe ends (TBD).

### Errors

TBD.

### Example

```vir
# let (r, w) = io.pipe()
```

### Notes

**missing** / planned.

---

<a id="io.cursor"></a>
## `io.cursor`

<!--
id: io.cursor
api: io.cursor
-->

```vir
io.cursor(data)
```

Wrap a memory buffer as a stream (read/write/seek per backing).

### Parameters

#### `data`

Backing storage (type TBD).

### Returns

Stream handle (TBD).

### Errors

TBD.

### Example

```vir
# let c = io.cursor(data)
```

### Notes

**missing** / planned.

---

<a id="io.sink"></a>
## `io.sink`

<!--
id: io.sink
api: io.sink
-->

```vir
io.sink() -> Writer
```

Writer that discards all bytes.

### Parameters

None.

### Returns

`Writer`

### Errors

None typical.

### Example

```vir
io.copy(src, io.sink())
```

### Notes

**missing** / planned.

---

<a id="io.empty"></a>
## `io.empty`

<!--
id: io.empty
api: io.empty
-->

```vir
io.empty() -> Reader
```

Reader that is always at EOF.

### Parameters

None.

### Returns

`Reader`

### Errors

None.

### Example

```vir
let n = io.empty().read(buf)   # 0 / EOF
```

### Notes

**missing** / planned.

---

<a id="io.repeat"></a>
## `io.repeat`

<!--
id: io.repeat
api: io.repeat
-->

```vir
io.repeat(value) -> Reader
```

Reader that repeatedly yields `value` (byte or pattern — TBD).

### Parameters

#### `value`

Unit to repeat.

### Returns

`Reader`

### Errors

None at construction.

### Example

```vir
# let r = io.repeat(0)
```

### Notes

**missing** / planned. Needs use-case review before `stable`.

---

## 11. Out of `io` (pointers)

| Topic | Doc | Impl summary |
|---|---|---|
| Interactive prompts | [`cli.md`](cli.md) | `input` / `read_line_secret` / `term.prompt` → **move** |
| File path + handles | [`fs.md`](fs.md) | `fs` + `io.file` → public **`fs`**; `rt/io` **internal** |
| Formatting | [`format.md`](format.md) *(same inode as `FORMAT.md` on APFS)* | `format_*` → **move** |

---

## Summary matrix

| Area | Present | Rename / replace | Missing / planned | Incomplete |
|---|---|---|---|---|
| Console print/eprint | yes | ns + drop aliases | — | — |
| `io.readLine` | as `readln` | rename | — | — |
| `io.stdin/out/err` | — | — | yes | — |
| Free flush | stub | replace w/ stream flush | — | stub |
| `Reader.read` | yes | export/publicize | — | — |
| `Reader.exact/atleast/limit/until/line/lines` | — | — | yes | — |
| `Reader.all` | as `read_all` | method | — | — |
| `Writer.write/flush` | yes | — | — | stdio flush stub |
| `Writer.writeAll` | as `write_all` | method | — | — |
| `Seeker` / `SeekFrom` | yes | — | — | — |
| `io.copy` | as `copy` | rename | — | — |
| `io.chain` / `tee` | — | — | yes | — |
| Buffered* / LineWriter | yes (`br_*`…) | all public names | Reader parity methods | — |
| pipe/cursor/sink/empty/repeat | — | — | yes | — |
| `cli.*` / `fs.*` / `format.*` | elsewhere | move | — | password |

## Open questions

1. ~~Error model~~ — **closed**.
2. ~~Bytes / buffer~~ — **closed** (`Slice` / `Buffer` / `string`).
3. ~~`byte()` outcomes~~ — **closed** (`Ok(Some)` / `Ok(None)` / `Err`); impl must stop swallowing.
4. ~~`until` delim~~ — **closed** (consume, exclude from `Buffer`; partial-before-EOF = `Ok`).
5. `io.print(value)` — `string` only or via `format`?
6. Constructor convention for buffered / line writers.
7. `BufferedReader` implements `Reader` vs parallel concrete API.
8. Export strategy without leaking `br_*`.
9. Exact Vir encoding of nested `Result`+`Option` for `byte()` if `Ok(None)` is awkward in today’s compiler.

## Notes

- **No `.vri` renames until this map is accepted.**
- Curriculum must not teach `br_*`, `input`, or `read_line_secret` as `io` APIs.
- `isEof` stays non-public unless a later decision overrides EOF-via-read.

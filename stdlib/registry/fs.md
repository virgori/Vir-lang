---
module: fs
title: Fs
summary: Filesystem path convenience and File handles — public namespace fs only.
source:
  - name: fs
    path: vir/fs.vri
  - name: fs.fs
    path: vir/fs/fs.vri
  - name: io.file
    path: vir/io/file.vri
  - name: io
    path: vir/rt/io.vri
status: draft
previous: [file]
notes: >-
  Public namespace is fs.* (not file.*). Deduplicate fs vs fs.fs before applying
  public rename. rt/io remains internal. Binary-first; text via explicit *Text APIs.
  No .vri changes until implementation against this map.
---

# Fs

Sole public filesystem namespace: **path-level / whole-file convenience** and
**factories that return a `File` handle**. Handle I/O is methods on `File`,
aligned with `Reader` / `Writer` / `Seeker` vocabulary in [`io.md`](io.md).

```vir
fs.exists(p)
fs.isFile(p)
fs.isDir(p)
fs.read(path)
fs.text(path)
fs.write(path, data)
fs.open(path, mode)

let f = fs.open("data.bin", FileMode.Read)
f.read(buf)
f.close()
```

`f` is an ordinary local variable name for a `File` handle — **not** a public
namespace. Do not use `file.*` or a bare `f.*` namespace.

## Impl legend

| Impl | Meaning |
|---|---|
| **present** | In source under some name |
| **rename** | Present; public name / signature changes |
| **remove** | Drop from public surface |
| **missing** | Not implemented; design closed → status `planned` |
| **internal** | Runtime / helpers — not public |
| **merge** | Deduplicate dual sources or dual impl paths |

## Status snapshot

| Area | Impl |
|---|---|
| Path helpers (`exists`…`size`) | **present** in `fs` — keep under `fs.*` |
| `fs.isFile` / `fs.isDir` | **present** as `path_is_file` / `path_is_dir` → **move** |
| `fs.exists` arg | today `string` (+ `path_exists(Path)`) → target **`Path`** |
| `fs.read` payload | today `string` → target **`Ok(Buffer)`** |
| `fs.text` | **missing** — strict UTF-8 → `Ok(string)` |
| `fs.write` / `append` / `writeAtomic` | today `string` → target **`Slice`** binary |
| `writeText` / `appendText` / `writeTextAtomic` | **missing** |
| `fs` vs `fs.fs` | duplicate → **merge first**, then apply public API |
| Handle `file_open` / `file_read` / … | **present** in `io.file` → **rename** to `fs.open` / `File.*` |
| `file_read_all` + `file_read_bytes` | dual impl → **merge** into `File.all()` |
| `file_write_str` / `read_file` / `write_file` | **remove** public |
| `rt/io` `VirFile` / `file_open_*` / … | **internal** |
| Dot-style methods on `File` | **missing** as public surface (snake `file_*` today) |

## Boundary

| In `fs` | Not in `fs` |
|---|---|
| Probes: `exists` / `isFile` / `isDir` | Lexical path math → [`path.md`](path.md) |
| Path ops: `remove`, `rename`, `copy`, `size` | Console stdio → `io` |
| Whole-file: `read` / `text` / `write*` / `append*` | Interactive prompts → `cli` |
| Factories: `open` / `create` → `File` | Pure formatting → `format` |
| `File` methods: read/write/seek/close | Public `file.*` namespace — **cancelled** |
| | `SeekFrom` type home — **`io.SeekFrom`** |
| | `path.exists` / `path.isFile` / `path.isDir` — **not public** |

Target split:

```vir
# whole-file convenience
let data = fs.read("model.gguf")

# handle / streaming
let f = fs.open("data.bin", FileMode.Read)
# f.read(...); f.close()
```

## Binary model (closed)

| Type | Role |
|---|---|
| `Slice` | Borrowed binary view |
| `Buffer` | Owned binary storage |
| `string` | Text (UTF-8) |

No public type named `bytes`. Binary I/O is the primitive; text APIs are an
explicit convenience layer.

`Buffer` → `Slice` for binary write APIs:

```vir
fs.write(path, buffer.slice(b))
```

`buffer.slice(b)` is the **canonical bridge** (see [`buffer.md`](buffer.md)).
No implicit `Buffer → Slice` conversion in this contract.

## Error model (closed)

| Case | Convention |
|---|---|
| Fallible filesystem op | `Result` |
| Normal absence (where applicable) | `Option` |
| Ordinary I/O failure | `IoError` (or existing kind) |
| `File.read` EOF | **`Ok(0)`** — not an error |
| Abort / invariant | `throw` / panic — **not** for recoverable FS errors |

Do not migrate filesystem to `throw int` for ordinary failures.

## Public surface (closed)

```text
fs
├── exists
├── isFile
├── isDir
├── read
├── text
├── write
├── writeText
├── append
├── appendText
├── writeAtomic
├── writeTextAtomic
├── remove
├── rename
├── copy
├── size
├── open
└── create

File
├── read
├── exact
├── atleast
├── all
├── write
├── writeAll
├── seek
├── size
└── close
```

Naming family (binary + text):

```text
write / writeText
append / appendText
writeAtomic / writeTextAtomic
```

No `writeAtomicText`. No `fs.fileRead`, `fs.readFile`, or other context-repeating names.

Types kept: **`File`**, **`FileMode`**. Factories stay `fs.open` / `fs.create`
(not `File.new`).

## Source consolidation order

```text
current fs sources (vir/fs.vri + vir/fs/fs.vri)
        ↓
deduplicate / merge
        ↓
single filesystem implementation source
        ↓
apply final fs public API
```

Do **not** rename both duplicates then merge. `io.file` may move/reuse under
the merged tree; public contract does not depend on physical layout.

Runtime boundary:

```text
fs / File
      ↓
stdlib implementation
      ↓
runtime (vir/rt/io.vri — VirFile, file_open_*, read_file_str, …)
      ↓
syscall / platform
```

Physical runtime names stay **internal**.

## Migration map

### Path / whole-file (from `fs`)

| Current symbol | Public | Signature (target) | Source | Action |
|---|---|---|---|---|
| `exists` / `path_exists` | `fs.exists` | `fs.exists(p: Path) -> bool` | `vir/fs.vri` + `vir/path/path.vri` | keep ns; **change** arg `string`→`Path`; absorb `path_exists` |
| `path_is_file` | `fs.isFile` | `fs.isFile(p: Path) -> bool` | `vir/path/path.vri` | **move** + rename |
| `path_is_dir` | `fs.isDir` | `fs.isDir(p: Path) -> bool` | `vir/path/path.vri` | **move** + rename |
| `read` | `fs.read` | `fs.read(path: string) -> Result(Buffer)` | `vir/fs.vri` | rename + **change** payload (`string`→`Buffer`) |
| — | `fs.text` | `fs.text(path: string) -> Result(string)` | decode over `fs.read` | **missing** / planned |
| `write` | `fs.write` | `fs.write(path: string, data: Slice) -> Result` | `vir/fs.vri` | rename + **change** arg (`string`→`Slice`) |
| — | `fs.writeText` | `fs.writeText(path: string, text: string) -> Result` | — | **missing** / planned |
| `append` | `fs.append` | `fs.append(path: string, data: Slice) -> Result` | `vir/fs.vri` | rename + **change** arg (`string`→`Slice`) |
| — | `fs.appendText` | `fs.appendText(path: string, text: string) -> Result` | — | **missing** / planned |
| `write_atomic` | `fs.writeAtomic` | `fs.writeAtomic(path: string, data: Slice) -> Result` | `vir/fs.vri` | rename + **change** arg (`string`→`Slice`) |
| — | `fs.writeTextAtomic` | `fs.writeTextAtomic(path: string, text: string) -> Result` | — | **missing** / planned |
| `remove` | `fs.remove` | `fs.remove(path: string) -> Result` | `vir/fs.vri` | keep |
| `rename` | `fs.rename` | `fs.rename(old_path: string, new_path: string) -> Result` | `vir/fs.vri` | keep |
| `copy` | `fs.copy` | `fs.copy(src: string, dst: string) -> Result` | `vir/fs.vri` | keep |
| `size` | `fs.size` | `fs.size(path: string) -> Result(int)` | `vir/fs.vri` | keep |
| `FsNamespace` / `fs` | `fs` namespace object | — | `vir/fs.vri` | keep / align methods |
| `fs_*_impl` | — | — | `vir/fs.vri` | **internal** |
| duplicate `fs.fs` | — | — | `vir/fs/fs.vri` | **merge** *(before public rename)* |

### Handle API (from `io.file`)

| Current symbol | Public | Signature (target) | Source | Action |
|---|---|---|---|---|
| `file_open` | `fs.open` | `fs.open(path: string, mode: FileMode) -> Result(File)` | `vir/io/file.vri` | rename |
| `file_create` | `fs.create` | `fs.create(path: string) -> Result(File)` | `vir/io/file.vri` | rename |
| `file_close` | `File.close` | `(f: File).close() -> void` | `vir/io/file.vri` | rename |
| `file_read` | `File.read` | `(f: File).read(buf: Slice) -> Result(int)` | `vir/io/file.vri` | rename |
| — | `File.exact` | `(f: File).exact(buf: Slice) -> Result(int)` | — | **missing** / planned |
| — | `File.atleast` | `(f: File).atleast(buf: Slice, min: int) -> Result(int)` | — | **missing** / planned |
| `file_read_all` | `File.all` | `(f: File).all() -> Result(Buffer)` | `vir/io/file.vri` | **merge** → `all` |
| `file_read_bytes` | `File.all` | same | `vir/io/file.vri` | **merge** → `all` (not `readBytes`) |
| `file_write` | `File.write` | `(f: File).write(data: Slice) -> Result` | `vir/io/file.vri` | rename |
| `file_write_all` | `File.writeAll` | `(f: File).writeAll(data: Slice) -> Result` | `vir/io/file.vri` | rename |
| `file_write_str` | — | — | `vir/io/file.vri` | **remove** public (text via `fs.*Text`) |
| `file_seek` | `File.seek` | `(f: File).seek(offset: int, whence: io.SeekFrom) -> Result(int)` | `vir/io/file.vri` | rename; whence from **`io`** |
| `file_size` | `File.size` | `(f: File).size() -> Result(int)` | `vir/io/file.vri` | rename |
| `File` / `FileMode` | `File` / `FileMode` | (types) | `vir/io/file.vri` | keep |
| `SeekFrom` (if local) | `io.SeekFrom` | (type) | traits / `io` | **canonical home `io`** — no `fs.SeekFrom` |
| `read_file` / `write_file` | — | — | `vir/io/file.vri` | **remove** alias |
| `io_error_from_errno` | `error.fromErrno` | — | `vir/error/error.vri` | **rename** · SSOT — see [`error.md`](error.md) |

### Runtime (internal)

| Current symbol | Public | Source | Action |
|---|---|---|---|
| `VirFile` / `file_open_*` / `read_file_str` / `write_file_str` / `write_file_bytes` / … | — | `vir/rt/io.vri` | **internal** |

### Cancelled public names

Not public (ever, under this contract):

```text
file.*
f.*                    (as namespace)
read_file / write_file
file_open / file_create / file_close
file_read / file_read_all / file_read_bytes
file_write / file_write_str / file_write_all
file_seek / file_size
File.readAll / File.readBytes / File.writeStr
fs.fileRead / fs.readFile / writeAtomicText
fs.fs duplicate namespace
```

Internal compatibility wrappers may exist temporarily during migration; registry
documents **canonical** API only.

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `fs.exists` | `fs.exists` | `fs.exists(p: Path) -> bool` | proposed |
| `fs.isFile` | `fs.isFile` | `fs.isFile(p: Path) -> bool` | proposed |
| `fs.isDir` | `fs.isDir` | `fs.isDir(p: Path) -> bool` | proposed |
| `fs.read` | `fs.read` | `fs.read(path: string) -> Result(Buffer)` | proposed |
| `fs.text` | `fs.text` | `fs.text(path: string) -> Result(string)` | planned |
| `fs.write` | `fs.write` | `fs.write(path: string, data: Slice) -> Result` | proposed |
| `fs.writeText` | `fs.writeText` | `fs.writeText(path: string, text: string) -> Result` | planned |
| `fs.append` | `fs.append` | `fs.append(path: string, data: Slice) -> Result` | proposed |
| `fs.appendText` | `fs.appendText` | `fs.appendText(path: string, text: string) -> Result` | planned |
| `fs.writeAtomic` | `fs.writeAtomic` | `fs.writeAtomic(path: string, data: Slice) -> Result` | proposed |
| `fs.writeTextAtomic` | `fs.writeTextAtomic` | `fs.writeTextAtomic(path: string, text: string) -> Result` | planned |
| `fs.remove` | `fs.remove` | `fs.remove(path: string) -> Result` | proposed |
| `fs.rename` | `fs.rename` | `fs.rename(old_path: string, new_path: string) -> Result` | proposed |
| `fs.copy` | `fs.copy` | `fs.copy(src: string, dst: string) -> Result` | proposed |
| `fs.size` | `fs.size` | `fs.size(path: string) -> Result(int)` | proposed |
| `fs.open` | `fs.open` | `fs.open(path: string, mode: FileMode) -> Result(File)` | proposed |
| `fs.create` | `fs.create` | `fs.create(path: string) -> Result(File)` | proposed |
| `fs.File.read` | `File.read` | `(f: File).read(buf: Slice) -> Result(int)` | proposed |
| `fs.File.exact` | `File.exact` | `(f: File).exact(buf: Slice) -> Result(int)` | planned |
| `fs.File.atleast` | `File.atleast` | `(f: File).atleast(buf: Slice, min: int) -> Result(int)` | planned |
| `fs.File.all` | `File.all` | `(f: File).all() -> Result(Buffer)` | proposed |
| `fs.File.write` | `File.write` | `(f: File).write(data: Slice) -> Result` | proposed |
| `fs.File.writeAll` | `File.writeAll` | `(f: File).writeAll(data: Slice) -> Result` | proposed |
| `fs.File.seek` | `File.seek` | `(f: File).seek(offset: int, whence: io.SeekFrom) -> Result(int)` | proposed |
| `fs.File.size` | `File.size` | `(f: File).size() -> Result(int)` | proposed |
| `fs.File.close` | `File.close` | `(f: File).close() -> void` | proposed |

---

<a id="fs.exists"></a>
## `fs.exists`

<!--
id: fs.exists
api: fs.exists
previous: exists, path_exists
-->

```vir
fs.exists(p: Path) -> bool
```

Reports whether a filesystem entry is visible at `p`. Canonical home for the
former `path_exists` probe — not under `path`.

### Parameters

#### `p: Path`

Path value (see [`path.md`](path.md)). Relative paths use the process working
directory.

### Returns

`bool` — `true` if present; `false` if missing or not observable.

### Errors

None as `Result` (failures look like `false`).

### Semantics

Does not distinguish “missing” from “unreadable” at the public level; both
surface as `false`. Today’s `fs.exists` takes `string` and `path_exists` takes
`Path` — public contract unifies on **`Path`**.

### Example

```vir
let root = path.new("stdlib")
let src = path.join(root, "vir")
if fs.exists(src) do
    io.println(path.string(src))
end
```

### Status

`proposed` — **present** as `exists` / `path_exists`; arg → `Path`.

### Implementation mapping

`vir/fs.vri` → `exists` / `fs_exists_impl`; absorb `vir/path/path.vri` →
`path_exists` (native probe).

### See also

- `fs.isFile`
- `fs.isDir`
- `fs.size`

---

<a id="fs.isFile"></a>
## `fs.isFile`

<!--
id: fs.isFile
api: fs.isFile
previous: path_is_file
-->

```vir
fs.isFile(p: Path) -> bool
```

Native probe: `p` refers to a regular file.

### Parameters

#### `p: Path`

Path to test.

### Returns

`bool` — `true` only for a regular file; directories and missing paths are
`false`.

### Errors

None as `Result` (failures look like `false`).

### Semantics

Moved from `path_is_file`. Not public under `path.isFile`.

### Example

```vir
let p = path.new("README.md")
if fs.isFile(p) do
    io.println("file")
end
```

### Status

`proposed` — **present** as `path_is_file`; public home `fs`.

### Implementation mapping

`vir/path/path.vri` → `path_is_file` / `native_path_is_file`.

### See also

- `fs.exists`
- `fs.isDir`

---

<a id="fs.isDir"></a>
## `fs.isDir`

<!--
id: fs.isDir
api: fs.isDir
previous: path_is_dir
-->

```vir
fs.isDir(p: Path) -> bool
```

Native probe: `p` refers to a directory.

### Parameters

#### `p: Path`

Path to test.

### Returns

`bool` — `true` for directories; files and missing paths are `false`.

### Errors

None as `Result` (failures look like `false`).

### Semantics

Moved from `path_is_dir`. Not public under `path.isDir`.

### Example

```vir
let p = path.new("stdlib")
if fs.isDir(p) do
    io.println("dir")
end
```

### Status

`proposed` — **present** as `path_is_dir`; public home `fs`.

### Implementation mapping

`vir/path/path.vri` → `path_is_dir` / `native_path_is_dir`.

### See also

- `fs.exists`
- `fs.isFile`

---

<a id="fs.read"></a>
## `fs.read`

<!--
id: fs.read
api: fs.read
previous: read
-->

```vir
fs.read(path: string) -> Result(Buffer)
```

Reads the entire file at `path` into an owned **`Buffer`**. Always binary.
Does not return `string` — use `fs.text` for UTF-8 text.

### Parameters

#### `path: string`

Path of a readable file (not a directory).

### Returns

`Result` — `Ok(Buffer)` full file bytes; `Err(…)` on failure.

### Errors

Invalid path; cannot open; incomplete read; other `IoError` kinds as today.

### Semantics

Today’s `fs.read` returns `string`; public contract **changes** to `Ok(Buffer)`.
Whole-file binary primitive; no UTF-8 validation.

### Example

```vir
let r = fs.read("model.gguf")
# Ok(Buffer) or Err(...)
```

### Status

`proposed` — **present** with wrong payload type.

### Implementation mapping

`vir/fs.vri` → `read`; payload must become `Buffer`.

### See also

- `fs.text`
- `fs.write`
- `fs.open`

---

<a id="fs.text"></a>
## `fs.text`

<!--
id: fs.text
api: fs.text
-->

```vir
fs.text(path: string) -> Result(string)
```

Reads the entire file and returns a UTF-8 **`string`**. Explicit text layer
over binary `fs.read`.

### Parameters

#### `path: string`

Path of a readable text file.

### Returns

`Result` — `Ok(string)` on valid UTF-8.

### Errors

Same I/O failures as `fs.read`. Invalid UTF-8 →
`Err(IoError { kind: ErrorKind.InvalidData, … })` — see [`error.md`](error.md).
**No** silent `�` replacement.
No lossy behavior on this API.

### Semantics

```text
fs.read → Buffer → strict UTF-8 validate → string
```

Lossy decoding, if ever needed, is a separate API — not part of this surface.

### Example

```vir
let r = fs.text("config.txt")
```

### Status

`planned` — **missing**; design closed.

### Implementation mapping

New; decode over `fs.read` + strict UTF-8 check.

### See also

- `fs.read`
- `fs.writeText`

---

<a id="fs.write"></a>
## `fs.write`

<!--
id: fs.write
api: fs.write
previous: write
-->

```vir
fs.write(path: string, data: Slice) -> Result
```

Creates or truncates `path` and writes all bytes of `data` (binary primitive).
Does not create parent directories.

Vir has **no** function overload: `string` must use `fs.writeText`.

### Parameters

#### `path: string`

Destination path.

#### `data: Slice`

Borrowed binary payload; length = bytes to write.

Pass a `Buffer` via `buffer.slice(b)` — no implicit conversion.

### Returns

`Result` — `Ok` on full write; `Err(…)` on failure.

### Errors

Invalid path; cannot create; incomplete write; permission denied.

### Semantics

Today’s `write` takes `string`; public contract **changes** to `Slice`.
Text → `fs.writeText`.

### Example

```vir
fs.write(path, dataSlice)
fs.write(path, buffer.slice(buf))

fs.writeText(path, "hello\n")
```

### Status

`proposed` — **present** with `string` arg.

### Implementation mapping

`vir/fs.vri` → `write`; change parameter to `Slice`.

### See also

- `fs.writeText`
- `fs.append`
- `fs.writeAtomic`

---

<a id="fs.writeText"></a>
## `fs.writeText`

<!--
id: fs.writeText
api: fs.writeText
-->

```vir
fs.writeText(path: string, text: string) -> Result
```

Writes UTF-8 bytes of `text` to `path` (create/truncate). Same underlying write
path as `fs.write` after taking a `Slice` of the string bytes.

### Parameters

#### `path: string`

Destination path.

#### `text: string`

Valid Vir `string` (already UTF-8).

### Returns

`Result`

### Errors

Same as `fs.write`.

### Semantics

Text convenience only. Exists because Vir cannot overload `fs.write` on
`Slice` vs `string`.

### Example

```vir
fs.writeText("out.txt", "hello\n")
```

### Status

`planned` — **missing**; design closed.

### Implementation mapping

New; UTF-8 bytes → same impl as `fs.write`.

### See also

- `fs.write`
- `fs.text`
- `fs.appendText`

---

<a id="fs.append"></a>
## `fs.append`

<!--
id: fs.append
api: fs.append
previous: append
-->

```vir
fs.append(path: string, data: Slice) -> Result
```

Appends binary `data` to `path`, creating the file if needed.

### Parameters

#### `path: string`

File to append to.

#### `data: Slice`

Borrowed binary payload. **Not** `string` — use `fs.appendText` for text.

### Returns

`Result`

### Errors

Invalid path; open/write failure; incomplete write.

### Semantics

Today’s `append` takes `string`; public contract **changes** to `Slice`.

### Example

```vir
fs.append("log.bin", chunk)
fs.appendText("log.txt", "line\n")
```

### Status

`proposed` — **present** with `string` arg.

### Implementation mapping

`vir/fs.vri` → `append`; change parameter to `Slice`.

### See also

- `fs.write`
- `fs.appendText`

---

<a id="fs.appendText"></a>
## `fs.appendText`

<!--
id: fs.appendText
api: fs.appendText
-->

```vir
fs.appendText(path: string, text: string) -> Result
```

Appends UTF-8 bytes of `text` to `path`, creating the file if needed.

### Parameters

#### `path: string`

File to append to.

#### `text: string`

Valid Vir `string`.

### Returns

`Result`

### Errors

Same as `fs.append`.

### Semantics

Text twin of `fs.append`. Same naming family as `write` / `writeText`.

### Example

```vir
fs.appendText("log.txt", "line\n")
```

### Status

`planned` — **missing**; design closed.

### Implementation mapping

New; UTF-8 bytes → same impl as `fs.append`.

### See also

- `fs.append`
- `fs.writeText`

---

<a id="fs.writeAtomic"></a>
## `fs.writeAtomic`

<!--
id: fs.writeAtomic
api: fs.writeAtomic
previous: write_atomic
-->

```vir
fs.writeAtomic(path: string, data: Slice) -> Result
```

Writes binary `data` via a temporary file then renames into `path` so readers
avoid partial content on success.

### Parameters

#### `path: string`

Final destination.

#### `data: Slice`

Full binary payload. **Not** `string` — use `fs.writeTextAtomic` for text.

### Returns

`Result`

### Errors

Temp write, rename, or incomplete write failures.

### Semantics

Today’s `write_atomic` takes `string`; public contract **changes** to `Slice`
(binary-first, same as `fs.write`). Official name is `writeAtomic`, not
`writeAtomicText`.

### Example

```vir
fs.writeAtomic("blob.bin", buffer.slice(data))
fs.writeTextAtomic("config.json", "{\"ok\":true}")
```

### Status

`proposed` — **present** with `string` arg.

### Implementation mapping

`vir/fs.vri` → `write_atomic`; change parameter to `Slice`.

### See also

- `fs.write`
- `fs.writeTextAtomic`

---

<a id="fs.writeTextAtomic"></a>
## `fs.writeTextAtomic`

<!--
id: fs.writeTextAtomic
api: fs.writeTextAtomic
-->

```vir
fs.writeTextAtomic(path: string, text: string) -> Result
```

Atomic write of UTF-8 `text` (temp + rename). Text twin of `fs.writeAtomic`.

### Parameters

#### `path: string`

Final destination.

#### `text: string`

Valid Vir `string`.

### Returns

`Result`

### Errors

Same as `fs.writeAtomic`.

### Semantics

Naming: `writeTextAtomic` (not `writeAtomicText`). Same family as
`write` / `writeText`.

### Example

```vir
fs.writeTextAtomic("config.json", "{\"ok\":true}")
```

### Status

`planned` — **missing**; design closed.

### Implementation mapping

New; UTF-8 bytes → same impl as `fs.writeAtomic`.

### See also

- `fs.writeAtomic`
- `fs.writeText`

---

<a id="fs.remove"></a>
## `fs.remove`

<!--
id: fs.remove
api: fs.remove
previous: remove
-->

```vir
fs.remove(path: string) -> Result
```

Removes the filesystem entry at `path` (host unlink semantics for directories).

### Parameters

#### `path: string`

Entry to remove.

### Returns

`Result`

### Errors

Missing path; permission denied; invalid path.

### Example

```vir
fs.remove("tmp.bin")
```

### Status

`proposed` — **present**.

### Implementation mapping

`vir/fs.vri` → `remove`.

### See also

- `fs.rename`

---

<a id="fs.rename"></a>
## `fs.rename`

<!--
id: fs.rename
api: fs.rename
previous: rename
-->

```vir
fs.rename(old_path: string, new_path: string) -> Result
```

Renames or moves `old_path` to `new_path` (host `rename` rules).

### Parameters

#### `old_path: string`

Existing path.

#### `new_path: string`

Destination path.

### Returns

`Result`

### Errors

Source missing; destination failure; cross-device limits.

### Example

```vir
fs.rename("a.txt", "b.txt")
```

### Status

`proposed` — **present**.

### Implementation mapping

`vir/fs.vri` → `rename`.

### See also

- `fs.copy`

---

<a id="fs.copy"></a>
## `fs.copy`

<!--
id: fs.copy
api: fs.copy
previous: copy
-->

```vir
fs.copy(src: string, dst: string) -> Result
```

Copies file contents from `src` to `dst`. Not a directory tree copy.

### Parameters

#### `src: string`

Source file.

#### `dst: string`

Destination file.

### Returns

`Result`

### Errors

Read or write side failures.

### Example

```vir
fs.copy("a.txt", "a.bak")
```

### Status

`proposed` — **present**.

### Implementation mapping

`vir/fs.vri` → `copy`.

### See also

- `fs.read`
- `fs.write`

---

<a id="fs.size"></a>
## `fs.size`

<!--
id: fs.size
api: fs.size
previous: size
-->

```vir
fs.size(path: string) -> Result(int)
```

Returns the size of the file at `path` in **bytes**.

### Parameters

#### `path: string`

Existing measurable file.

### Returns

`Result` — `Ok(int)` byte length (`0` if empty); `Err` if unreadable.

### Errors

Missing path; not a file; permission denied.

### Example

```vir
let r = fs.size("data.bin")
```

### Status

`proposed` — **present**.

### Implementation mapping

`vir/fs.vri` → `size`.

### See also

- `fs.exists`
- `File.size`

---

<a id="fs.open"></a>
## `fs.open`

<!--
id: fs.open
api: fs.open
previous: file_open
-->

```vir
fs.open(path: string, mode: FileMode) -> Result(File)
```

Opens `path` and returns a `File` handle for streaming I/O.
Semantic factory — not `File.new`.

### Parameters

#### `path: string`

File path.

#### `mode: FileMode`

Access mode (`Read` / `Write` / … as defined by the type).

### Returns

`Result` — `Ok(File)` handle, or `Err` on failure.

### Errors

Missing file (when reading); permission denied; invalid path.

### Example

```vir
let r = fs.open("data.bin", FileMode.Read)
```

### Status

`proposed` — **present** as `file_open`.

### Implementation mapping

`vir/io/file.vri` → `file_open`.

### See also

- `fs.create`
- `File.close`

---

<a id="fs.create"></a>
## `fs.create`

<!--
id: fs.create
api: fs.create
previous: file_create
-->

```vir
fs.create(path: string) -> Result(File)
```

Creates or truncates `path` for writing and returns a `File` handle.
Semantic factory — not `File.new`.

### Parameters

#### `path: string`

Destination path.

### Returns

`Result` — `Ok(File)` or `Err`.

### Errors

Cannot create; permission denied.

### Example

```vir
let r = fs.create("out.bin")
```

### Status

`proposed` — **present** as `file_create`.

### Implementation mapping

`vir/io/file.vri` → `file_create`.

### See also

- `fs.open`
- `fs.write`

---

<a id="fs.File.read"></a>
## `File.read`

<!--
id: fs.File.read
api: File.read
previous: file_read
-->

```vir
(f: File).read(buf: Slice) -> Result(int)
```

Reads up to `buf` capacity into `buf` from the current file position.
Matches `Reader.read` vocabulary.

### Parameters

#### `buf: Slice`

Destination buffer; capacity is the maximum byte count for this call.

### Returns

| Outcome | Meaning |
|---|---|
| `Ok(n)` with `n > 0` | Read `n` bytes |
| `Ok(0)` | Normal EOF |
| `Err(error)` | I/O failure |

### Errors

Bad handle; read failure. EOF is **not** an error.

### Semantics

Ordinary failures use `Result` / `IoError`. Do not `throw` for recoverable FS I/O.

### Example

```vir
let f = fs.open("data.bin", FileMode.Read)
# let n = f.read(buf)
```

### Status

`proposed` — **present** as `file_read`.

### Implementation mapping

`vir/io/file.vri` → `file_read`.

### See also

- `File.exact`
- `File.atleast`
- `File.all`
- `fs.read`

---

<a id="fs.File.exact"></a>
## `File.exact`

<!--
id: fs.File.exact
api: File.exact
-->

```vir
(f: File).exact(buf: Slice) -> Result(int)
```

Reads exactly `buf` capacity bytes into `buf`. Matches `Reader.exact`.

### Parameters

#### `buf: Slice`

Destination; must be filled completely on success.

### Returns

`Result` — `Ok` when the full buffer is filled; `Err` on failure.

### Errors

I/O failure; EOF before the buffer is full → **`UnexpectedEof`** (or existing
equivalent kind).

### Semantics

Stricter than `read`: short read / early EOF is an error, not `Ok(n)`.

### Example

```vir
# f.exact(headerBuf)
```

### Status

`planned` — **missing**; design closed (same as `io` Reader contract).

### Implementation mapping

New method on `File`; share semantics with `Reader.exact`.

### See also

- `File.read`
- `File.atleast`

---

<a id="fs.File.atleast"></a>
## `File.atleast`

<!--
id: fs.File.atleast
api: File.atleast
-->

```vir
(f: File).atleast(buf: Slice, min: int) -> Result(int)
```

Reads at least `min` bytes into `buf` (up to capacity). Matches `Reader.atleast`.

### Parameters

#### `buf: Slice`

Destination buffer.

#### `min: int`

Minimum acceptable byte count (`0 ≤ min ≤ buf` capacity).

### Returns

`Result` — `Ok(n)` with `n ≥ min` on success.

### Errors

I/O failure; EOF before `min` bytes → **`UnexpectedEof`**.

### Example

```vir
# f.atleast(buf, 4)
```

### Status

`planned` — **missing**; design closed.

### Implementation mapping

New method on `File`; share semantics with `Reader.atleast`.

### See also

- `File.read`
- `File.exact`

---

<a id="fs.File.all"></a>
## `File.all`

<!--
id: fs.File.all
api: File.all
previous: file_read_all, file_read_bytes
-->

```vir
(f: File).all() -> Result(Buffer)
```

Reads from the current position to EOF into an owned **`Buffer`**.
Matches `Reader.all` vocabulary — **not** `readAll` / `readBytes`.

### Parameters

None (receiver `File`).

### Returns

`Result` — `Ok(Buffer)` owned payload; `Err` on I/O failure.

### Errors

Bad handle; read failure.

### Semantics

Merges today’s dual impl paths `file_read_all` and `file_read_bytes` into one
public semantic. Handle API stays binary-first; whole-file text stays on `fs.text`.

### Example

```vir
# let r = f.all()
# Ok(Buffer)
```

### Status

`proposed` — **present** under two snake names; public is one method.

### Implementation mapping

`vir/io/file.vri` → merge `file_read_all` + `file_read_bytes` → `File.all`.

### See also

- `File.read`
- `fs.read`

---

<a id="fs.File.write"></a>
## `File.write`

<!--
id: fs.File.write
api: File.write
previous: file_write
-->

```vir
(f: File).write(data: Slice) -> Result
```

Writes up to `data` length bytes from `data` at the current position.
Matches `Writer.write`. Binary-only; no public `File.writeStr`.

### Parameters

#### `data: Slice`

Source bytes.

### Returns

`Result` — `Ok(n)` bytes actually written when the implementation reports a
count. **Short write is valid** at this primitive; callers retry or use
`writeAll`.

### Errors

Bad handle; write failure.

### Example

```vir
# f.write(data)
```

### Status

`proposed` — **present** as `file_write`.

### Implementation mapping

`vir/io/file.vri` → `file_write`. Drop public `file_write_str`.

### See also

- `File.writeAll`
- `fs.write`

---

<a id="fs.File.writeAll"></a>
## `File.writeAll`

<!--
id: fs.File.writeAll
api: File.writeAll
previous: file_write_all
-->

```vir
(f: File).writeAll(data: Slice) -> Result
```

Writes the entire `Slice`, retrying until complete or an error occurs.
Kept as `writeAll` (not `all`) — `writer.all(data)` is ambiguous.

### Parameters

#### `data: Slice`

Full binary payload to write.

### Returns

`Result` — `Ok` when all bytes are written; `Err` on failure.

### Errors

Bad handle; write failure before completion.

### Semantics

Full-write companion to primitive `write`. Short writes are handled inside.

### Example

```vir
# f.writeAll(data)
```

### Status

`proposed` — **present** as `file_write_all`.

### Implementation mapping

`vir/io/file.vri` → `file_write_all`.

### See also

- `File.write`
- `fs.write`

---

<a id="fs.File.seek"></a>
## `File.seek`

<!--
id: fs.File.seek
api: File.seek
previous: file_seek
-->

```vir
(f: File).seek(offset: int, whence: io.SeekFrom) -> Result(int)
```

Moves the file position. Matches `Seeker.seek`.

### Parameters

#### `offset: int`

Byte displacement; sign meaning depends on `whence` (negative from `End` /
`Current` as host allows).

#### `whence: io.SeekFrom`

Origin for the offset (`Start` / `Current` / `End`). Canonical type home is
**`io`** — no `fs.SeekFrom` duplicate.

### Returns

`Result` — `Ok(pos)` new absolute byte position from start of file; `Err` on failure.

### Errors

Invalid seek; bad handle.

### Example

```vir
# f.seek(0, io.SeekFrom.Start)
```

### Status

`proposed` — **present** as `file_seek`; whence type owned by `io`.

### Implementation mapping

`vir/io/file.vri` → `file_seek`; import/use `io.SeekFrom`.

### See also

- `File.read`
- `io` / `Seeker` ([`io.md`](io.md))

---

<a id="fs.File.size"></a>
## `File.size`

<!--
id: fs.File.size
api: File.size
previous: file_size
-->

```vir
(f: File).size() -> Result(int)
```

Returns the size of the open file in **bytes** (does not require closing).

### Parameters

None (receiver `File`).

### Returns

`Result` — `Ok(int)` byte length.

### Errors

Bad handle; size query failure.

### Example

```vir
# let n = f.size()
```

### Status

`proposed` — **present** as `file_size`.

### Implementation mapping

`vir/io/file.vri` → `file_size`.

### See also

- `fs.size`

---

<a id="fs.File.close"></a>
## `File.close`

<!--
id: fs.File.close
api: File.close
previous: file_close
-->

```vir
(f: File).close() -> void
```

Closes the handle and releases the OS descriptor.

### Parameters

None (receiver `File`).

### Returns

None. After close, further I/O on `f` is invalid.

### Errors

Today’s close is best-effort (`void`). Future may surface close errors as
`Result` without changing the rest of this map.

### Example

```vir
let f = fs.open("data.bin", FileMode.Read)
# …
f.close()
```

### Status

`proposed` — **present** as `file_close`.

### Implementation mapping

`vir/io/file.vri` → `file_close`.

### See also

- `fs.open`
- `fs.create`

---

## Implementation readiness

Public filesystem API map is closed for this refactor.
Implementation may proceed against this registry.

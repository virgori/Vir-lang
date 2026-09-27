---
module: path
title: Path
summary: Path values and pure lexical path-string operations — namespace-only path.*.
source:
  - name: path
    path: vir/path/path.vri
status: draft
notes: >-
  path = representation + pure path manipulation. Filesystem probes live in fs
  (exists / isFile / isDir). No receiver-style p.*; no path_* public names.
  No .vri changes until implementation against this map.
---

# Path

`Path` values and **pure / lexical** path-string operations. Public API is
**namespace-only**: `path.<op>(…)`.

```text
path = path representation + pure path manipulation
fs   = filesystem observation / mutation
```

`path` does **not** perform native filesystem probes.

```vir
let root = path.new("stdlib")
let src = path.join(root, "vir")

if fs.exists(src) do
    io.println(path.string(src))
end
```

## Boundary

| In `path` | Not in `path` |
|---|---|
| `Path` type | `fs.exists` / `fs.isFile` / `fs.isDir` *(moved)* |
| `new` / `join` / `parent` / `name` / `stem` / `ext` / `withExt` | Whole-file I/O → `fs` |
| `absolute` / `relative` / `string` | `File` handles → `fs` |
| Lexical separator join only | Resolve / canonicalize / symlink |
| | Receiver API `p.join` / `p.name` — **not public** |
| | Snake names `path_join` / `path_filename` — **impl only** |

Host separator today: `PATH_SEP = "/"` (POSIX). Documented behavior matches
`vir/path/path.vri`.

## Public surface (closed)

```text
path
├── new
├── join
├── parent
├── name
├── stem
├── ext
├── withExt
├── absolute
├── relative
└── string
```

```vir
path.new(...)
path.join(...)
path.parent(...)
path.name(...)
path.stem(...)
path.ext(...)
path.withExt(...)
path.absolute(...)
path.relative(...)
path.string(...)
```

## Type: `Path`

```vir
Path
```

Implementation representation today:

```text
raw: string
```

`raw` is an **implementation** field — not a required public contract. Callers
obtain a string via `path.string(p)` so `Path` storage may change later without
forcing `p.raw` access.

## Migration map

| Current | Public | Impl note | Action |
|---|---|---|---|
| `path_new` | `path.new` | wrap `s` as `Path` | **rename** |
| `path_from` | `path.new` | same wrap; uses `str_new(literal)` copy | **merge** into `path.new` |
| `path_join` | `path.join` | lexical `PATH_SEP` join | **rename** |
| `path_parent` | `path.parent` | last-sep cut → `Option` of `Path` | **rename** |
| `path_filename` | `path.name` | final component → `Option` of `string` | **rename** |
| `path_stem` | `path.stem` | stem of final component | **rename** |
| `path_extension` | `path.ext` | ext **without** leading `.` | **rename** |
| `path_with_extension` | `path.withExt` | lexical transform only | **rename** |
| `path_is_absolute` | `path.absolute` | lexical predicate | **rename** |
| `path_is_relative` | `path.relative` | `not absolute` | **rename** |
| `path_to_string` | `path.string` | returns stored string | **rename** |
| `path_exists` | `fs.exists` | native probe | **move** → [`fs.md`](fs.md) |
| `path_is_file` | `fs.isFile` | native probe | **move** → [`fs.md`](fs.md) |
| `path_is_dir` | `fs.isDir` | native probe | **move** → [`fs.md`](fs.md) |
| `str_rfind` | — | helper | **internal** |
| `PATH_SEP` | — | module const | **internal** (may surface later) |

### `path_from` vs `path_new`

| | `path_new(s)` | `path_from(literal)` |
|---|---|---|
| Result | `Path { raw: s }` | `Path { raw: str_new(literal) }` |
| Difference | Stores `s` as given | Copies via `str_new` |

Public surface keeps **one** constructor: `path.new`. No separate public alias.
Implementation may keep `path_from` temporarily as an internal wrapper.

### Moved out (not in `path` API table)

```text
path_exists   → fs.exists
path_is_file  → fs.isFile
path_is_dir   → fs.isDir
```

Do **not** document `path.exists` / `path.isFile` / `path.isDir`.

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `path.new` | `path.new` | `path.new(s: string) -> Path` | proposed |
| `path.join` | `path.join` | `path.join(base: Path, child: string) -> Path` | proposed |
| `path.parent` | `path.parent` | `path.parent(p: Path) -> Option(Path)` | proposed |
| `path.name` | `path.name` | `path.name(p: Path) -> Option(string)` | proposed |
| `path.stem` | `path.stem` | `path.stem(p: Path) -> Option(string)` | proposed |
| `path.ext` | `path.ext` | `path.ext(p: Path) -> Option(string)` | proposed |
| `path.withExt` | `path.withExt` | `path.withExt(p: Path, ext: string) -> Path` | proposed |
| `path.absolute` | `path.absolute` | `path.absolute(p: Path) -> bool` | proposed |
| `path.relative` | `path.relative` | `path.relative(p: Path) -> bool` | proposed |
| `path.string` | `path.string` | `path.string(p: Path) -> string` | proposed |

---

<a id="path.new"></a>
## `path.new`

<!--
id: path.new
api: path.new
previous: path_new
-->

```vir
path.new(s: string) -> Path
```

Wraps path string `s` as a `Path`. Lexical only.

### Parameters

#### `s: string`

Path text to store. Not validated against the filesystem.

### Returns

`Path`

### Errors

None.

### Semantics

Does **not**:

- resolve `.` or `..`;
- access the filesystem;
- canonicalize;
- check that the path exists.

Stores `s` unchanged (same as today’s `path_new`).

### Example

```vir
let p = path.new("src/main.vri")
```

### Status

`proposed` — **present** as `path_new`; `path_from` **merges** here.

### Implementation mapping

`vir/path/path.vri` → `path_new` (+ optional internal `path_from`).

### See also

- `path.string`
- `path.join`

---

<a id="path.join"></a>
## `path.join`

<!--
id: path.join
api: path.join
previous: path_join
-->

```vir
path.join(base: Path, child: string) -> Path
```

**Lexical join** with the module separator (`"/"` today).

### Parameters

#### `base: Path`

Left-hand path. If its stored string is empty, the result is just `child`.

#### `child: string`

Right-hand segment or relative subpath (not required to be a single component).

### Returns

`Path` — concatenated path string.

### Errors

None.

### Semantics

Does **not**: check the filesystem; resolve symlinks; canonicalize; resolve `..`;
force an absolute result.

Separator rules (current impl):

1. empty `base` → result is `child` alone;
2. `base` already ends with `PATH_SEP` → append `child` directly;
3. otherwise insert one `PATH_SEP` between `base` and `child`.

Does not collapse repeated separators beyond the trailing-sep check above.

### Example

```vir
let root = path.new("stdlib")
let src = path.join(root, "vir")
```

### Status

`proposed` — **present** as `path_join`.

### Implementation mapping

`vir/path/path.vri` → `path_join`.

### See also

- `path.new`
- `path.parent`

---

<a id="path.parent"></a>
## `path.parent`

<!--
id: path.parent
api: path.parent
previous: path_parent
-->

```vir
path.parent(p: Path) -> Option(Path)
```

Parent path by cutting at the last separator in the stored string.

### Parameters

#### `p: Path`

Path to inspect.

### Returns

`Option` of `Path`:

| Case | Result |
|---|---|
| Separator at index `0` only (e.g. `"/usr"`) | `Some` of root separator path (`"/"`) |
| Separator elsewhere | `Some` of the prefix before the last sep |
| No separator | `None` |

### Errors

None.

### Semantics

Pure string cut on `PATH_SEP`. No filesystem access. Root / no-separator cases
follow the table above (current `path_parent`).

### Example

```vir
let p = path.new("a/b/c.vri")
let parent = path.parent(p)
# Some(Path of "a/b")
```

### Status

`proposed` — **present** as `path_parent`.

### Implementation mapping

`vir/path/path.vri` → `path_parent`.

### See also

- `path.name`
- `path.join`

---

<a id="path.name"></a>
## `path.name`

<!--
id: path.name
api: path.name
previous: path_filename
-->

```vir
path.name(p: Path) -> Option(string)
```

Final path component (file **or** directory name).

### Parameters

#### `p: Path`

Path to inspect.

### Returns

`Option` of `string`:

| Case | Result |
|---|---|
| Separator present; non-empty tail | `Some(name)` |
| No separator | `Some` of the whole stored string |
| Separator is the last character (empty name) | `None` |

### Errors

None.

### Semantics

`name` replaces `filename` because the same operation applies to directory
paths (`/usr/local/bin` → `bin`). No public name `filename`.

### Example

```vir
path.name(path.new("a/b/c.vri"))
# Some("c.vri")
```

### Status

`proposed` — **present** as `path_filename`.

### Implementation mapping

`vir/path/path.vri` → `path_filename`.

### See also

- `path.stem`
- `path.ext`
- `path.parent`

---

<a id="path.stem"></a>
## `path.stem`

<!--
id: path.stem
api: path.stem
previous: path_stem
-->

```vir
path.stem(p: Path) -> Option(string)
```

Stem of the final component: text before the last `.` in that component,
with edge cases below.

### Parameters

#### `p: Path`

Path to inspect.

### Returns

`Option` of `string` — `None` when `path.name` is `None`; otherwise `Some(…)`.

### Errors

None.

### Semantics (current impl)

Operates on `path.name` (final component), then last `.` in that name:

| Final component | Stem |
|---|---|
| `c.vri` | `c` |
| `archive.tar.gz` | `archive.tar` |
| no `.` | whole name |
| `.hidden` (dot at index `0`) | whole name (`.hidden`) — not treated as extension |
| empty name (`None` from `name`) | `None` |

Directory paths without an extension use the directory’s final component as
stem (e.g. `a/b/c` → `Some("c")`).

### Example

```vir
path.stem(path.new("a/b/c.vri"))
# Some("c")
```

### Status

`proposed` — **present** as `path_stem`.

### Implementation mapping

`vir/path/path.vri` → `path_stem`.

### See also

- `path.name`
- `path.ext`
- `path.withExt`

---

<a id="path.ext"></a>
## `path.ext`

<!--
id: path.ext
api: path.ext
previous: path_extension
-->

```vir
path.ext(p: Path) -> Option(string)
```

Final extension of the name component. Canonical public abbreviation: **`ext`**
(not `extension`).

### Parameters

#### `p: Path`

Path to inspect.

### Returns

`Option` of `string` — extension **without** a leading `.`.

| Final component | Ext |
|---|---|
| `c.vri` | `Some("vri")` |
| `archive.tar.gz` | `Some("gz")` |
| no `.` | `None` |
| `.hidden` (dot at index `0`) | `None` |
| `foo.` (trailing dot) | `Some("")` (empty string after the dot) |
| empty name | `None` |

### Errors

None.

### Semantics

Last `.` in the final component; slice **after** that dot (no leading `.` in
the returned string). Leading-dot names have no extension.

### Example

```vir
path.ext(path.new("a/b/c.vri"))
# Some("vri")
```

### Status

`proposed` — **present** as `path_extension`.

### Implementation mapping

`vir/path/path.vri` → `path_extension`.

### See also

- `path.stem`
- `path.withExt`
- `path.name`

---

<a id="path.withExt"></a>
## `path.withExt`

<!--
id: path.withExt
api: path.withExt
previous: path_with_extension
-->

```vir
path.withExt(p: Path, ext: string) -> Path
```

Returns a **new** `Path` with the final extension changed. Lexical only —
does not rename a real file or touch the filesystem.

### Parameters

#### `p: Path`

Source path.

#### `ext: string`

New extension **without** requiring a leading `.`. Empty `ext` yields the stem
string alone (no trailing dot), per current impl.

### Returns

`Path`

### Errors

None.

### Semantics (current impl)

1. Take `path.stem(p)` when present; otherwise use the full stored string.
2. If `ext` is empty → `path.new(stem_or_raw)`.
3. Otherwise → `stem_or_raw + "." + ext`.

**Impl note:** today’s `path_with_extension` computes `path_parent` but does
**not** reattach it. For multi-component paths such as `a/b/c.vri`, the result
is based on the stem of the final component only (e.g. conceptually `c.vri` →
`c.md`), not `a/b/c.md`. Registry documents this actual behavior; fixing
parent reattachment is an implementation follow-up, not a public rename.

### Example

```vir
let p = path.new("c.vri")
let q = path.withExt(p, "md")
# path.string(q) → "c.md"
```

### Status

`proposed` — **present** as `path_with_extension`.

### Implementation mapping

`vir/path/path.vri` → `path_with_extension`.

### See also

- `path.ext`
- `path.stem`

---

<a id="path.absolute"></a>
## `path.absolute`

<!--
id: path.absolute
api: path.absolute
previous: path_is_absolute
-->

```vir
path.absolute(p: Path) -> bool
```

Lexical absolute-path predicate. No filesystem access.

### Parameters

#### `p: Path`

Path to test.

### Returns

`bool` — `true` if the stored string starts with `PATH_SEP` (`"/"` today).

### Errors

None.

### Semantics

Not `path.isAbsolute`. Namespace + `bool` return already supply the predicate
context. Does not resolve against the process cwd.

### Example

```vir
path.absolute(path.new("/usr/bin"))
# true
path.absolute(path.new("src/main.vri"))
# false
```

### Status

`proposed` — **present** as `path_is_absolute`.

### Implementation mapping

`vir/path/path.vri` → `path_is_absolute`.

### See also

- `path.relative`

---

<a id="path.relative"></a>
## `path.relative`

<!--
id: path.relative
api: path.relative
previous: path_is_relative
-->

```vir
path.relative(p: Path) -> bool
```

Lexical relative-path predicate — negation of `path.absolute`.

### Parameters

#### `p: Path`

Path to test.

### Returns

`bool` — `true` when `path.absolute(p)` is `false`.

### Errors

None.

### Semantics

Not `path.isRelative`. No filesystem access.

### Example

```vir
path.relative(path.new("src/main.vri"))
# true
```

### Status

`proposed` — **present** as `path_is_relative`.

### Implementation mapping

`vir/path/path.vri` → `path_is_relative`.

### See also

- `path.absolute`

---

<a id="path.string"></a>
## `path.string`

<!--
id: path.string
api: path.string
previous: path_to_string
-->

```vir
path.string(p: Path) -> string
```

String representation of `Path`. Preferred over reading implementation field
`raw`.

### Parameters

#### `p: Path`

Path value.

### Returns

`string` — the stored path text (today: `p.raw`).

### Errors

None.

### Semantics

Public code should use `path.string(p)`, not `p.raw`, so representation can
evolve.

### Example

```vir
let p = path.new("src/main.vri")
io.println(path.string(p))
```

### Status

`proposed` — **present** as `path_to_string`.

### Implementation mapping

`vir/path/path.vri` → `path_to_string`.

### See also

- `path.new`

---

## Filesystem probes (moved to `fs`)

Canonical public home — see [`fs.md`](fs.md):

```text
fs
├── exists
├── isFile
└── isDir
```

| Former `path` symbol | Public |
|---|---|
| `path_exists` | `fs.exists` |
| `path_is_file` | `fs.isFile` |
| `path_is_dir` | `fs.isDir` |

No duplicate public aliases under `path`.

## Implementation readiness

Public path API map is closed for this refactor.
Implementation may proceed against this registry.

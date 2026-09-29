---
module: regex
title: Regex
summary: Traditional regex syntax frontend — compile to pattern.Pattern and run match/search/replace ops.
source:
  - name: regex
    path: vir/regex/regex.vri
status: draft
notes: >-
  `include regex` only — not `include regex.regex`. compile returns pattern.Pattern (see pattern.md).
  No public compileToPattern, free compile(), regex.match, findall, sub, or regex_* snake names.
---

# Regex

The **regex** namespace parses familiar regex syntax (literals, classes, groups, quantifiers,
`^` / `$` anchors) into shared [`pattern.Pattern`](pattern.md) values, then delegates matching
to the Thompson NFA engine.

```vir
include regex

let pat = regex.compile("\\\\w+")
let m = regex.search(pat, "hello world")
```

Load with **`include regex`** only. Do not use nested module paths such as `regex.regex`.

## Boundary

| In public `regex` | Not public |
|---|---|
| `regex.compile` → `pattern.Pattern` | `regex_compile_to_pattern`, `compile()` free |
| `regex.isMatch`, `fullMatch`, `search`, … | `regex.match`, `regex.findall`, `regex.sub` |
| camelCase namespace API | `regex_*` snake functions |
| | `RegexParser` entity (parser internal) |

## Migration map

| Current symbol | Proposed public | Signature (target) | Implementation source | Action |
|---|---|---|---|---|
| `regex_compile` | `regex.compile` | `regex.compile(source: &string) -> Pattern` | `vir/regex/regex.vri` | rename |
| `compile` (free) | — | — | `vir/regex/regex.vri` | internal |
| `regex_compile_to_pattern` | — | — | `vir/regex/regex.vri` | internal |
| `regex_is_match` | `regex.isMatch` | `regex.isMatch(pat, text) -> bool` | `vir/regex/regex.vri` | rename |
| `regex_fullmatch` | `regex.fullMatch` | `regex.fullMatch(pat, text) -> bool` | `vir/regex/regex.vri` | rename |
| `regex_search` | `regex.search` | `regex.search(pat, text) -> Option of (Match)` | `vir/regex/regex.vri` | rename |
| `regex_match` | — | — | `vir/regex/regex.vri` | remove · use `search` |
| `regex_find` | `regex.find` | `regex.find(pat, text) -> string` | `vir/regex/regex.vri` | rename |
| `regex_find_all` | `regex.findAll` | `regex.findAll(pat, text) -> Vec of (string)` | `vir/regex/regex.vri` | rename |
| `regex_findall` | `regex.findAll` | same | `vir/regex/regex.vri` | remove alias |
| `regex_extract` | `regex.extract` | `regex.extract(pat, text) -> Vec of (string)` | `vir/regex/regex.vri` | rename |
| — | `regex.extractAll` | `regex.extractAll(pat, text) -> Vec` | `vir/pattern/pattern.vri` via pat | planned |
| `regex_replace` | `regex.replace` | `regex.replace(pat, text, rep) -> string` | `vir/regex/regex.vri` | rename |
| `regex_replace_all` | `regex.replaceAll` | `regex.replaceAll(pat, text, rep) -> string` | `vir/regex/regex.vri` | rename |
| `regex_sub` | `regex.replaceAll` | same | `vir/regex/regex.vri` | merge · remove alias |
| `regex_split` | `regex.split` | `regex.split(pat, text) -> Vec of (string)` | `vir/regex/regex.vri` | rename |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `regex.compile` | `regex.compile` | `regex.compile(source: &string) -> pattern.Pattern` | proposed |
| `regex.isMatch` | `regex.isMatch` | `regex.isMatch(pat: Pattern, text: &string) -> bool` | proposed |
| `regex.fullMatch` | `regex.fullMatch` | `regex.fullMatch(pat: Pattern, text: &string) -> bool` | proposed |
| `regex.search` | `regex.search` | `regex.search(pat: Pattern, text: &string) -> Option of (pattern.Match)` | proposed |
| `regex.find` | `regex.find` | `regex.find(pat: Pattern, text: &string) -> string` | proposed |
| `regex.findAll` | `regex.findAll` | `regex.findAll(pat: Pattern, text: &string) -> Vec of (string)` | proposed |
| `regex.extract` | `regex.extract` | `regex.extract(pat: Pattern, text: &string) -> Vec of (string)` | proposed |
| `regex.extractAll` | `regex.extractAll` | `regex.extractAll(pat: Pattern, text: &string) -> Vec` | proposed |
| `regex.replace` | `regex.replace` | `regex.replace(pat: Pattern, text: &string, rep: &string) -> string` | proposed |
| `regex.replaceAll` | `regex.replaceAll` | `regex.replaceAll(pat: Pattern, text: &string, rep: &string) -> string` | proposed |
| `regex.split` | `regex.split` | `regex.split(pat: Pattern, text: &string) -> Vec of (string)` | proposed |

---

<a id="regex.compile"></a>
## `regex.compile`

<!--
id: regex.compile
api: regex.compile
previous: regex_compile, compile
-->

```vir
regex.compile(source: &string) -> pattern.Pattern
```

Parse `source` as a regex pattern, lower to Pattern IR, compile to an NFA, and return
[`pattern.Pattern`](pattern.md) with `engine_kind` = regex. Leading `^` / trailing `$` in
`source` set compile-time anchor flags on the NFA.

### Parameters

#### `source: &string`

Pattern text in regex syntax. Empty pattern is allowed (matches empty string subject to anchors).

### Returns

`pattern.Pattern` — reusable compiled matcher.

### Errors

Invalid syntax may panic today during parse; target is `Result of (Pattern)` — **open**.

### Example

```vir
include regex

let pat = regex.compile("([a-z]+)@(\\\\d+)")
```

---

<a id="regex.isMatch"></a>
## `regex.isMatch`

<!--
id: regex.isMatch
api: regex.isMatch
previous: regex_is_match
-->

```vir
regex.isMatch(pat: Pattern, text: &string) -> bool
```

**Anywhere match:** `true` when [`regex.search`](#regex.search) would return `Some(_)`.
**Source today** implements via whole-input `pattern_match` — same as `fullMatch` (**gap**).

### Parameters

#### `pat: Pattern`

Compiled regex.

#### `text: &string`

Haystack.

### Returns

`bool`.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("\\\\d+")
let ok = regex.isMatch(pat, "x9y")
```

---

<a id="regex.fullMatch"></a>
## `regex.fullMatch`

<!--
id: regex.fullMatch
api: regex.fullMatch
previous: regex_fullmatch
-->

```vir
regex.fullMatch(pat: Pattern, text: &string) -> bool
```

**Entire input matches:** `true` only when the full `text` satisfies `pat` (NFA full-match).
Distinct from [`regex.search`](#regex.search), which finds a substring match anywhere.

### Parameters

#### `pat: Pattern`

Compiled regex.

#### `text: &string`

Haystack; must match in full.

### Returns

`bool`.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("\\\\d+")
regex.fullMatch(pat, "42")      # true
regex.fullMatch(pat, "x42")     # false
```

---

<a id="regex.search"></a>
## `regex.search`

<!--
id: regex.search
api: regex.search
previous: regex_search, regex_match
-->

```vir
regex.search(pat: Pattern, text: &string) -> Option of (pattern.Match)
```

**First match anywhere** in `text` from the start of the haystack scan: returns
`Option.Some(m)` with a [`pattern.Match`](pattern.md), or `Option.None` if no match.
Replaces dropped `regex.match`.

### Parameters

#### `pat: Pattern`

Compiled regex.

#### `text: &string`

Haystack.

### Returns

`Option of (pattern.Match)`.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("\\\\d+")
let m = regex.search(pat, "a42b")
```

---

<a id="regex.find"></a>
## `regex.find`

<!--
id: regex.find
api: regex.find
previous: regex_find
-->

```vir
regex.find(pat: Pattern, text: &string) -> string
```

**First match text:** matched substring of the first anywhere match, or `""` if none.
Convenience over `search` without building `Match` in user code.

### Parameters

#### `pat: Pattern`

Compiled regex.

#### `text: &string`

Haystack.

### Returns

`string` — match slice or empty.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("\\\\d+")
let s = regex.find(pat, "a42b")   # "42"
```

---

<a id="regex.findAll"></a>
## `regex.findAll`

<!--
id: regex.findAll
api: regex.findAll
previous: regex_find_all, regex_findall
-->

```vir
regex.findAll(pat: Pattern, text: &string) -> Vec of (string)
```

All non-overlapping match substrings, left to right. Delegates to
[`pattern.findAll`](pattern.md).

### Parameters

#### `pat: Pattern`

Compiled regex.

#### `text: &string`

Haystack.

### Returns

`Vec of (string)`.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("\\\\d")
regex.findAll(pat, "1a2")
```

---

<a id="regex.extract"></a>
## `regex.extract`

<!--
id: regex.extract
api: regex.extract
previous: regex_extract
-->

```vir
regex.extract(pat: Pattern, text: &string) -> Vec of (string)
```

Capturing groups from the **first** match in `text`. See [`pattern.extract`](pattern.md).

### Parameters

#### `pat: Pattern`

Compiled regex with capturing groups.

#### `text: &string`

Haystack.

### Returns

`Vec of (string)` — groups only; empty when no match.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("(\\\\d+)-(\\\\d+)")
regex.extract(pat, "a10-20b")
```

---

<a id="regex.extractAll"></a>
## `regex.extractAll`

<!--
id: regex.extractAll
api: regex.extractAll
-->

```vir
regex.extractAll(pat: Pattern, text: &string) -> Vec
```

Capturing groups for **every** non-overlapping match. Wraps
[`pattern.extractAll`](pattern.md). **Not** exposed as `regex_extract_all` today — **proposed**.

### Parameters

#### `pat: Pattern`

Compiled regex.

#### `text: &string`

Haystack.

### Returns

`Vec` — per-match group bundles.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("(\\\\d+)")
regex.extractAll(pat, "1 and 22")
```

---

<a id="regex.replace"></a>
## `regex.replace`

<!--
id: regex.replace
api: regex.replace
previous: regex_replace
-->

```vir
regex.replace(pat: Pattern, text: &string, rep: &string) -> string
```

Replace the first match in `text` with literal `rep`.

### Parameters

#### `pat: Pattern`

Compiled regex.

#### `text: &string`

Input.

#### `rep: &string`

Replacement string (not regex substitution syntax).

### Returns

New `string`.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("\\\\d+")
regex.replace(pat, "a9b", "N")
```

---

<a id="regex.replaceAll"></a>
## `regex.replaceAll`

<!--
id: regex.replaceAll
api: regex.replaceAll
previous: regex_replace_all, regex_sub
-->

```vir
regex.replaceAll(pat: Pattern, text: &string, rep: &string) -> string
```

Replace all non-overlapping matches with `rep`. Canonical replacement for legacy `regex.sub`.

### Parameters

#### `pat: Pattern`

Compiled regex.

#### `text: &string`

Input.

#### `rep: &string`

Replacement literal.

### Returns

New `string`.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("\\\\d")
regex.replaceAll(pat, "a1b2", "X")
```

---

<a id="regex.split"></a>
## `regex.split`

<!--
id: regex.split
api: regex.split
previous: regex_split
-->

```vir
regex.split(pat: Pattern, text: &string) -> Vec of (string)
```

Split on every match of `pat`. See [`pattern.split`](pattern.md).

### Parameters

#### `pat: Pattern`

Delimiter pattern.

#### `text: &string`

Input.

### Returns

`Vec of (string)` — segments between matches.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("[\\\\s,]+")
regex.split(pat, "a, b  c")
```

## Open questions

- Should `regex.compile` return `Result of (pattern.Pattern)` for syntax errors instead of panic?
- Align `regex.isMatch` implementation with search-based semantics before marking `stable`.
- Backreference and advanced PCRE features — explicitly out of scope until listed in regex.vri header.

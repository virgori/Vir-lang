---
module: virgex
title: Virgex
summary: Vir Pattern Syntax (VPS) frontend — compile to pattern.Pattern; regex-like ops plus tokenize.
source:
  - name: virgex
    path: vir/virgex/virgex.vri
status: draft
notes: >-
  `include virgex` only — not `include virgex.virgex`. VPS lexer/parser (`vps_tokenize`, VpsParser)
  is internal. compile returns pattern.Pattern. virgex.toRegex is incomplete stub today.
---

# Virgex

**Virgex** is the first-class **Vir Pattern Syntax (VPS)** frontend: atoms (`@Az`, `@0`, …),
groups `:( … :)`, quantifiers `!n`, `!~`, escapes, and `|` anchors compile to the same
[`pattern.Pattern`](pattern.md) type as [`regex`](regex.md).

```vir
include virgex

let pat = virgex.compile("@0!1")
let tok = virgex.tokenize(pat, "a1b22")
```

Load with **`include virgex`** only.

## Boundary

| In public `virgex` | Not public |
|---|---|
| Same ops as `regex` + `virgex.tokenize` | `virgex_*` snake, `compile()` free |
| `virgex.compile` → `pattern.Pattern` | `vps_tokenize`, `VpsTok`, `VpsParser`, `_vps_*` |
| `virgex.toRegex` (incomplete) | `virgex.match` → use `virgex.search` |
| | `virgex.findall` alias |

Target API takes a compiled `Pattern` for match ops (like `regex`). **Source today** re-compiles
from `pattern_str` on each `virgex_*` call — **implementation gap**.

## Migration map

| Current symbol | Proposed public | Signature (target) | Implementation source | Action |
|---|---|---|---|---|
| `virgex_compile` | `virgex.compile` | `virgex.compile(source: &string) -> Pattern` | `vir/virgex/virgex.vri` | rename |
| `compile` (free) | — | — | `vir/virgex/virgex.vri` | internal |
| `vps_compile_to_pattern` | — | — | `vir/virgex/virgex.vri` | internal |
| `vps_tokenize` | — | — | `vir/virgex/virgex.vri` | internal |
| `virgex_fullmatch` | `virgex.fullMatch` | `virgex.fullMatch(pat, text) -> bool` | `vir/virgex/virgex.vri` | rename · Pattern arg |
| `virgex_match` | — | — | `vir/virgex/virgex.vri` | remove · use `search` |
| `virgex_search` | `virgex.search` | `virgex.search(pat, text) -> Option of (Match)` | `vir/virgex/virgex.vri` | rename |
| `virgex_find` | `virgex.find` | `virgex.find(pat, text) -> string` | `vir/virgex/virgex.vri` | rename |
| `virgex_find_all` | `virgex.findAll` | `virgex.findAll(pat, text) -> Vec of (string)` | `vir/virgex/virgex.vri` | rename |
| `virgex_findall` | `virgex.findAll` | same | `vir/virgex/virgex.vri` | remove alias |
| `virgex_extract` | `virgex.extract` | `virgex.extract(pat, text) -> Vec of (string)` | `vir/virgex/virgex.vri` | rename |
| `virgex_extract_all` | `virgex.extractAll` | `virgex.extractAll(pat, text) -> Vec` | `vir/virgex/virgex.vri` | rename |
| `virgex_replace` | `virgex.replace` | `virgex.replace(pat, text, rep) -> string` | `vir/virgex/virgex.vri` | rename |
| `virgex_replace_all` | `virgex.replaceAll` | `virgex.replaceAll(pat, text, rep) -> string` | `vir/virgex/virgex.vri` | rename |
| `virgex_split` | `virgex.split` | `virgex.split(pat, text) -> Vec of (string)` | `vir/virgex/virgex.vri` | rename |
| `virgex_tokenize` | `virgex.tokenize` | `virgex.tokenize(pat, text) -> Vec of (string)` | `vir/virgex/virgex.vri` | rename |
| `virgex_to_regex` | `virgex.toRegex` | `virgex.toRegex(vps: string) -> Result of (string)` | `vir/virgex/virgex.vri` | incomplete |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `virgex.compile` | `virgex.compile` | `virgex.compile(source: &string) -> pattern.Pattern` | proposed |
| `virgex.isMatch` | `virgex.isMatch` | `virgex.isMatch(pat: Pattern, text: &string) -> bool` | proposed |
| `virgex.fullMatch` | `virgex.fullMatch` | `virgex.fullMatch(pat: Pattern, text: &string) -> bool` | proposed |
| `virgex.search` | `virgex.search` | `virgex.search(pat: Pattern, text: &string) -> Option of (pattern.Match)` | proposed |
| `virgex.find` | `virgex.find` | `virgex.find(pat: Pattern, text: &string) -> string` | proposed |
| `virgex.findAll` | `virgex.findAll` | `virgex.findAll(pat: Pattern, text: &string) -> Vec of (string)` | proposed |
| `virgex.extract` | `virgex.extract` | `virgex.extract(pat: Pattern, text: &string) -> Vec of (string)` | proposed |
| `virgex.extractAll` | `virgex.extractAll` | `virgex.extractAll(pat: Pattern, text: &string) -> Vec` | proposed |
| `virgex.replace` | `virgex.replace` | `virgex.replace(pat: Pattern, text: &string, rep: &string) -> string` | proposed |
| `virgex.replaceAll` | `virgex.replaceAll` | `virgex.replaceAll(pat: Pattern, text: &string, rep: &string) -> string` | proposed |
| `virgex.split` | `virgex.split` | `virgex.split(pat: Pattern, text: &string) -> Vec of (string)` | proposed |
| `virgex.tokenize` | `virgex.tokenize` | `virgex.tokenize(pat: Pattern, text: &string) -> Vec of (string)` | proposed |
| `virgex.toRegex` | `virgex.toRegex` | `virgex.toRegex(vps: string) -> Result of (string)` | incomplete |

---

<a id="virgex.compile"></a>
## `virgex.compile`

<!--
id: virgex.compile
api: virgex.compile
previous: virgex_compile, compile
-->

```vir
virgex.compile(source: &string) -> pattern.Pattern
```

Tokenize and parse VPS `source`, lower to Pattern IR, compile NFA, return
[`pattern.Pattern`](pattern.md) with `engine_kind` = Virgex. Leading / trailing `|` tokens
set start/end anchor flags (VPS spec).

### Parameters

#### `source: &string`

VPS pattern text.

### Returns

`pattern.Pattern`.

### Errors

Lexer/parser errors return `Result.Err` inside `vps_tokenize` today; compile path may panic —
target `Result of (Pattern)` **open**.

### Example

```vir
include virgex

let pat = virgex.compile(":( @AZ!2 | @0!4 :)")
```

---

<a id="virgex.isMatch"></a>
## `virgex.isMatch`

<!--
id: virgex.isMatch
api: virgex.isMatch
-->

```vir
virgex.isMatch(pat: Pattern, text: &string) -> bool
```

**Anywhere match:** `true` when [`virgex.search`](#virgex.search) would return `Some(_)`.
Mirror [`regex.isMatch`](regex.md). **Not** a separate snake wrapper in source — **proposed**
namespace entry aligned with regex cluster.

### Parameters

#### `pat: Pattern`

Compiled VPS pattern.

#### `text: &string`

Haystack.

### Returns

`bool`.

### Errors

None.

### Example

```vir
include virgex

let pat = virgex.compile("@0!1")
virgex.isMatch(pat, "x9y")
```

---

<a id="virgex.fullMatch"></a>
## `virgex.fullMatch`

<!--
id: virgex.fullMatch
api: virgex.fullMatch
previous: virgex_fullmatch
-->

```vir
virgex.fullMatch(pat: Pattern, text: &string) -> bool
```

**Entire input matches** the VPS pattern (full-match NFA). Same contract as
[`regex.fullMatch`](regex.md).

### Parameters

#### `pat: Pattern`

Compiled pattern.

#### `text: &string`

Haystack.

### Returns

`bool`.

### Errors

None.

### Example

```vir
include virgex

let pat = virgex.compile("@0!1")
virgex.fullMatch(pat, "42")
```

---

<a id="virgex.search"></a>
## `virgex.search`

<!--
id: virgex.search
api: virgex.search
previous: virgex_search, virgex_match
-->

```vir
virgex.search(pat: Pattern, text: &string) -> Option of (pattern.Match)
```

**First match anywhere** in `text`. Canonical replacement for removed `virgex.match` /
`virgex_match`.

### Parameters

#### `pat: Pattern`

Compiled pattern.

#### `text: &string`

Haystack.

### Returns

`Option of (pattern.Match)`.

### Errors

None.

### Example

```vir
include virgex

let pat = virgex.compile("@0!1")
let m = virgex.search(pat, "a42b")
```

---

<a id="virgex.find"></a>
## `virgex.find`

<!--
id: virgex.find
api: virgex.find
previous: virgex_find
-->

```vir
virgex.find(pat: Pattern, text: &string) -> string
```

First matched substring text, or `""` if none. See [`regex.find`](regex.md).

### Parameters

#### `pat: Pattern`

Compiled pattern.

#### `text: &string`

Haystack.

### Returns

`string`.

### Errors

None.

### Example

```vir
include virgex

let pat = virgex.compile("@0!2")
virgex.find(pat, "x1234y")
```

---

<a id="virgex.findAll"></a>
## `virgex.findAll`

<!--
id: virgex.findAll
api: virgex.findAll
previous: virgex_find_all, virgex_findall
-->

```vir
virgex.findAll(pat: Pattern, text: &string) -> Vec of (string)
```

All non-overlapping match strings. Delegates to [`pattern.findAll`](pattern.md).

### Parameters

#### `pat: Pattern`

Compiled pattern.

#### `text: &string`

Haystack.

### Returns

`Vec of (string)`.

### Errors

None.

### Example

```vir
include virgex

let pat = virgex.compile("@0")
virgex.findAll(pat, "1a2")
```

---

<a id="virgex.extract"></a>
## `virgex.extract`

<!--
id: virgex.extract
api: virgex.extract
previous: virgex_extract
-->

```vir
virgex.extract(pat: Pattern, text: &string) -> Vec of (string)
```

Capturing groups (VPS atom groups) from the first match. See [`pattern.extract`](pattern.md).

### Parameters

#### `pat: Pattern`

Compiled pattern.

#### `text: &string`

Haystack.

### Returns

`Vec of (string)`.

### Errors

None.

### Example

```vir
include virgex

let pat = virgex.compile(":( @AZ!2 @0!2 :)")
virgex.extract(pat, "AB12")
```

---

<a id="virgex.extractAll"></a>
## `virgex.extractAll`

<!--
id: virgex.extractAll
api: virgex.extractAll
previous: virgex_extract_all
-->

```vir
virgex.extractAll(pat: Pattern, text: &string) -> Vec
```

Per-match capture data for all occurrences. See [`pattern.extractAll`](pattern.md).

### Parameters

#### `pat: Pattern`

Compiled pattern.

#### `text: &string`

Haystack.

### Returns

`Vec`.

### Errors

None.

### Example

```vir
include virgex

let pat = virgex.compile("@0!1")
virgex.extractAll(pat, "1 and 2")
```

---

<a id="virgex.replace"></a>
## `virgex.replace`

<!--
id: virgex.replace
api: virgex.replace
previous: virgex_replace
-->

```vir
virgex.replace(pat: Pattern, text: &string, rep: &string) -> string
```

Replace first match with literal `rep`.

### Parameters

#### `pat: Pattern`

Compiled pattern.

#### `text: &string`

Input.

#### `rep: &string`

Replacement.

### Returns

New `string`.

### Errors

None.

### Example

```vir
include virgex

let pat = virgex.compile("@0!1")
virgex.replace(pat, "a9b", "N")
```

---

<a id="virgex.replaceAll"></a>
## `virgex.replaceAll`

<!--
id: virgex.replaceAll
api: virgex.replaceAll
previous: virgex_replace_all
-->

```vir
virgex.replaceAll(pat: Pattern, text: &string, rep: &string) -> string
```

Replace all non-overlapping matches.

### Parameters

#### `pat: Pattern`

Compiled pattern.

#### `text: &string`

Input.

#### `rep: &string`

Replacement.

### Returns

New `string`.

### Errors

None.

### Example

```vir
include virgex

let pat = virgex.compile("@0")
virgex.replaceAll(pat, "a1b2", "X")
```

---

<a id="virgex.split"></a>
## `virgex.split`

<!--
id: virgex.split
api: virgex.split
previous: virgex_split
-->

```vir
virgex.split(pat: Pattern, text: &string) -> Vec of (string)
```

Split on matches. See [`pattern.split`](pattern.md).

### Parameters

#### `pat: Pattern`

Delimiter pattern.

#### `text: &string`

Input.

### Returns

`Vec of (string)`.

### Errors

None.

### Example

```vir
include virgex

let pat = virgex.compile("-")
virgex.split(pat, "a-b-c")
```

---

<a id="virgex.tokenize"></a>
## `virgex.tokenize`

<!--
id: virgex.tokenize
api: virgex.tokenize
previous: virgex_tokenize
-->

```vir
virgex.tokenize(pat: Pattern, text: &string) -> Vec of (string)
```

Tokenize `text` by `pat`: alternating non-match spans and matched segments (includes matches).
See [`pattern.tokenize`](pattern.md). **Not** in the regex namespace.

### Parameters

#### `pat: Pattern`

Token pattern (often VPS atoms).

#### `text: &string`

Input.

### Returns

`Vec of (string)`.

### Errors

None.

### Example

```vir
include virgex

let pat = virgex.compile("@0!1")
virgex.tokenize(pat, "a1b2")
```

---

<a id="virgex.toRegex"></a>
## `virgex.toRegex`

<!--
id: virgex.toRegex
api: virgex.toRegex
previous: virgex_to_regex
-->

```vir
virgex.toRegex(vps: string) -> Result of (string)
```

Convert a VPS pattern string to an equivalent traditional regex string for interop / debugging.
**Incomplete:** source returns `Result.Ok(vps)` unchanged — not a real translation.

### Parameters

#### `vps: string`

Vir Pattern Syntax source.

### Returns

`Result of (string)` — target: regex text; today stub echoes input.

### Errors

Target: `Err` on untranslatable VPS constructs. Stub does not fail.

### Example

```vir
include virgex

let r = virgex.toRegex("@0!1")
# incomplete — do not rely on output yet
```

## Open questions

- When to refactor `virgex_*` wrappers to accept `Pattern` only (drop per-call recompile)?
- Full VPS → regex lowering table for `virgex.toRegex` (phonetic atoms, escapes, groups).
- Should `virgex.isMatch` ship before source adds a dedicated function, or alias `search` only in docs?

---
module: pattern
title: Pattern
summary: Compiled Thompson-NFA patterns — match, search, replace, split, and iteration on text.
source:
  - name: pattern
    path: vir/pattern/pattern.vri
status: draft
notes: >-
  Engine (`pattern.engine`) and IR (`pattern.ir`) are implementation-only — not public registry.
  Public surface is camelCase on `pattern.*` and `Pattern` methods. Snake `pattern_*` and
  string-first UFCS free ops are migration-only until map is closed.
---

# Pattern

**Pattern** is the shared runtime type for compiled matchers (Virgex VPS and traditional regex
both lower to the same NFA). Build a `pattern.Pattern` via [`regex.compile`](regex.md) or
[`virgex.compile`](virgex.md), then run operations on text.

```vir
include pattern
include regex

let pat = regex.compile("\\\\d+")
if pat.isMatch("42") do
    let slice = pat.find("x99y")
end
```

Physical module: `vir/pattern/pattern.vri`. Do **not** `include pattern.engine` or
`include pattern.ir` from user code.

## Boundary

| In public `pattern` | Not public |
|---|---|
| `pattern.Pattern`, `pattern.Match`, `pattern.Iterator` | `pattern.engine`, `pattern.ir`, `NfaProgram`, `PatternNode` |
| `pattern.match`, `isMatch`, `find`, `findAll`, … | `pattern_match`, `pattern_find*`, `pattern_iter_next` |
| `pattern.iter`, `pattern.next` | Free `match(s, pat)`, `find(s, pat)`, … (UFCS migration only) |
| Byte-oriented match semantics (UTF-8 bytes) | ReDoS-prone backtracking engines |

## Migration map

| Current symbol | Proposed public | Signature (target) | Implementation source | Action |
|---|---|---|---|---|
| `Pattern` entity | `pattern.Pattern` | (type) | `vir/pattern/pattern.vri` | keep |
| `Match` entity | `pattern.Match` | (type) | `vir/pattern/engine.vri` | keep · expose via pattern ns |
| `PatternIterator` | `pattern.Iterator` | (type) | `vir/pattern/pattern.vri` | rename type label |
| `Pattern.match` / `is_match` | `pattern.fullMatch` / `pattern.isMatch` | see API | `vir/pattern/pattern.vri` | rename |
| `pattern_match` | `pattern.fullMatch` | `pat.fullMatch(text) -> bool` | `vir/pattern/pattern.vri` | rename |
| `pattern_find_match` | — (use `regex.search` / `Pattern` search path) | `Option of (Match)` | `vir/pattern/pattern.vri` | internal |
| `pattern_find` | `pattern.find` | `pat.find(text) -> string` | `vir/pattern/pattern.vri` | rename |
| `pattern_find_all` | `pattern.findAll` | `pat.findAll(text) -> Vec of (string)` | `vir/pattern/pattern.vri` | rename |
| `pattern_extract` | `pattern.extract` | `pat.extract(text) -> Vec of (string)` | `vir/pattern/pattern.vri` | rename |
| `pattern_extract_all` | `pattern.extractAll` | `pat.extractAll(text) -> Vec` | `vir/pattern/pattern.vri` | rename |
| `pattern_replace` | `pattern.replace` | `pat.replace(text, rep) -> string` | `vir/pattern/pattern.vri` | rename |
| `pattern_replace_all` | `pattern.replaceAll` | `pat.replaceAll(text, rep) -> string` | `vir/pattern/pattern.vri` | rename |
| `pattern_split` | `pattern.split` | `pat.split(text) -> Vec of (string)` | `vir/pattern/pattern.vri` | rename |
| `pattern_tokenize` | `pattern.tokenize` | `pat.tokenize(text) -> Vec of (string)` | `vir/pattern/pattern.vri` | rename |
| `pattern_iter` | `pattern.iter` | `pattern.iter(pat, text) -> Iterator` | `vir/pattern/pattern.vri` | rename |
| `next` / `pattern_iter_next` | `pattern.next` | `pattern.next(it) -> Option of (Match)` | `vir/pattern/pattern.vri` | rename · snake internal |
| `match(s, pat)` (free) | — | — | `vir/pattern/pattern.vri` | internal · migration |
| `find` / `find_all` / … (free UFCS) | — | — | `vir/pattern/pattern.vri` | internal · migration |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `pattern.Pattern` | `pattern.Pattern` | entity | proposed |
| `pattern.Match` | `pattern.Match` | entity | proposed |
| `pattern.Iterator` | `pattern.Iterator` | entity | proposed |
| `pattern.fullMatch` | `pattern.fullMatch` | `pat.fullMatch(text: &string) -> bool` | proposed |
| `pattern.isMatch` | `pattern.isMatch` | `pat.isMatch(text: &string) -> bool` | proposed |
| `pattern.find` | `pattern.find` | `pat.find(text: &string) -> string` | proposed |
| `pattern.findAll` | `pattern.findAll` | `pat.findAll(text: &string) -> Vec of (string)` | proposed |
| `pattern.extract` | `pattern.extract` | `pat.extract(text: &string) -> Vec of (string)` | proposed |
| `pattern.extractAll` | `pattern.extractAll` | `pat.extractAll(text: &string) -> Vec` | proposed |
| `pattern.replace` | `pattern.replace` | `pat.replace(text: &string, rep: &string) -> string` | proposed |
| `pattern.replaceAll` | `pattern.replaceAll` | `pat.replaceAll(text: &string, rep: &string) -> string` | proposed |
| `pattern.split` | `pattern.split` | `pat.split(text: &string) -> Vec of (string)` | proposed |
| `pattern.tokenize` | `pattern.tokenize` | `pat.tokenize(text: &string) -> Vec of (string)` | proposed |
| `pattern.iter` | `pattern.iter` | `pattern.iter(pat: Pattern, text: string) -> Iterator` | proposed |
| `pattern.next` | `pattern.next` | `pattern.next(it: Iterator) -> Option of (Match)` | proposed |

---

<a id="pattern.Pattern"></a>
## `pattern.Pattern`

<!--
id: pattern.Pattern
api: pattern.Pattern
-->

```vir
entity Pattern
```

Compiled matcher: original source text, engine kind (Virgex vs regex frontend), and an
`NfaProgram` executed by the shared Thompson NFA VM. Immutable after compile.

### Parameters

None — type only.

### Returns

N/A.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("[0-9]+")
```

---

<a id="pattern.Match"></a>
## `pattern.Match`

<!--
id: pattern.Match
api: pattern.Match
-->

```vir
entity Match
```

One match occurrence: byte span `[start, end)` in the haystack, matched substring text, and
capture tag positions for group extraction. Field accessors may be methods on `Match` in a
later pass; today engine helpers are **internal**.

### Parameters

None — type only.

### Returns

N/A.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("(\\\\d+)")
let m = regex.search(pat, "a42b")
# when m is Some — use regex.extract / pattern.extract for group strings
```

---

<a id="pattern.Iterator"></a>
## `pattern.Iterator`

<!--
id: pattern.Iterator
api: pattern.Iterator
previous: PatternIterator
-->

```vir
entity Iterator
```

Stateful non-overlapping scan over `text` using `pat`’s NFA. Advance with [`pattern.next`](#pattern.next).

### Parameters

None — type only.

### Returns

N/A.

### Errors

None.

### Example

```vir
include pattern
include regex

let pat = regex.compile("\\\\d+")
var it = pattern.iter(pat, "a1b22c")
```

---

<a id="pattern.match"></a>
## `pattern.match`

<!--
id: pattern.match
api: pattern.match
previous: pattern_match
-->

```vir
pat.match(text: &string) -> bool
```

**Whole-input match:** returns `true` when the entire `text` satisfies the pattern (NFA
full-match). Equivalent to [`regex.fullMatch`](regex.md) when `pat` came from the regex frontend.

### Parameters

#### `text: &string`

Haystack UTF-8 bytes. Empty string is allowed; result depends on pattern (e.g. `^$`).

### Returns

`bool` — `true` only on full-string success.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("^\\\\d+$")
let ok = pat.match("123")
```

---

<a id="pattern.isMatch"></a>
## `pattern.isMatch`

<!--
id: pattern.isMatch
api: pattern.isMatch
previous: Pattern.is_match
-->

```vir
pat.isMatch(text: &string) -> bool
```

**Anywhere match (target):** returns `true` if the pattern matches any substring of `text`
(same truth value as `regex.search` returning `Some`). **Source today** aliases both
`match` and `is_match` to full-match — **implementation gap** vs this contract.

### Parameters

#### `text: &string`

Haystack to scan.

### Returns

`bool` — `true` if a match exists anywhere in `text`.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("\\\\d+")
let ok = pat.isMatch("x99y")   # target: true
```

---

<a id="pattern.find"></a>
## `pattern.find`

<!--
id: pattern.find
api: pattern.find
previous: pattern_find
-->

```vir
pat.find(text: &string) -> string
```

First match anywhere in `text`: returns the matched substring as a new `string`. If there is
no match, returns `""` (empty string, not an error).

### Parameters

#### `text: &string`

Haystack to search.

### Returns

`string` — matched slice or empty when none.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("\\\\d+")
let s = pat.find("a42b")   # "42"
```

---

<a id="pattern.findAll"></a>
## `pattern.findAll`

<!--
id: pattern.findAll
api: pattern.findAll
previous: pattern_find_all
-->

```vir
pat.findAll(text: &string) -> Vec of (string)
```

All non-overlapping matches, left to right: each element is the matched substring text.

### Parameters

#### `text: &string`

Haystack to scan.

### Returns

`Vec of (string)` — empty vector when no matches.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("\\\\d")
let all = pat.findAll("a1b2")   # ["1", "2"]
```

---

<a id="pattern.extract"></a>
## `pattern.extract`

<!--
id: pattern.extract
api: pattern.extract
previous: pattern_extract
-->

```vir
pat.extract(text: &string) -> Vec of (string)
```

From the **first** match in `text`, collect **capturing groups** (1-based groups only; group 0
overall match may be omitted per engine policy). Empty vector when no match.

### Parameters

#### `text: &string`

Haystack to search once.

### Returns

`Vec of (string)` — group texts in order.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("(\\\\d+)(\\\\d)")
let g = pat.extract("x1234")   # first match groups
```

---

<a id="pattern.extractAll"></a>
## `pattern.extractAll`

<!--
id: pattern.extractAll
api: pattern.extractAll
previous: pattern_extract_all
-->

```vir
pat.extractAll(text: &string) -> Vec
```

For **each** non-overlapping match, an element containing that match’s capture groups (nested
vector shape as today’s `pattern_extract_all`). **Not** yet a method on `Pattern` in source —
**proposed** on entity + namespace.

### Parameters

#### `text: &string`

Haystack to scan.

### Returns

`Vec` — one entry per match (each entry is group data for that match).

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("(\\\\d+)")
let rows = pat.extractAll("1 and 22")
```

---

<a id="pattern.replace"></a>
## `pattern.replace`

<!--
id: pattern.replace
api: pattern.replace
previous: pattern_replace
-->

```vir
pat.replace(text: &string, rep: &string) -> string
```

Replace the **first** match in `text` with `rep`. If no match, returns `text` unchanged.

### Parameters

#### `text: &string`

Input string.

#### `rep: &string`

Replacement literal (not a template language).

### Returns

New `string` with at most one substitution.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("\\\\d+")
let out = pat.replace("a9b", "N")   # "aNb"
```

---

<a id="pattern.replaceAll"></a>
## `pattern.replaceAll`

<!--
id: pattern.replaceAll
api: pattern.replaceAll
previous: pattern_replace_all
-->

```vir
pat.replaceAll(text: &string, rep: &string) -> string
```

Replace every non-overlapping match with `rep`, preserving text between matches.

### Parameters

#### `text: &string`

Input string.

#### `rep: &string`

Replacement literal for each match.

### Returns

New `string`; unchanged `text` when there are zero matches.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("\\\\d")
let out = pat.replaceAll("a1b2", "X")   # "aXbX"
```

---

<a id="pattern.split"></a>
## `pattern.split`

<!--
id: pattern.split
api: pattern.split
previous: pattern_split
-->

```vir
pat.split(text: &string) -> Vec of (string)
```

Split `text` on every match of `pat`. Segments between matches become elements. If there is
no match, a single-element vector containing all of `text`.

### Parameters

#### `text: &string`

Input to split.

### Returns

`Vec of (string)` — parts excluding matched delimiters.

### Errors

None.

### Example

```vir
include regex

let pat = regex.compile("[,;]")
let parts = pat.split("a,b;c")
```

---

<a id="pattern.tokenize"></a>
## `pattern.tokenize`

<!--
id: pattern.tokenize
api: pattern.tokenize
previous: pattern_tokenize
-->

```vir
pat.tokenize(text: &string) -> Vec of (string)
```

Like split, but **keeps** matched regions as tokens: alternates non-match spans and match
texts in order (useful for lexing). If no match and `text` is non-empty, returns one token
(the whole string).

### Parameters

#### `text: &string`

Input to tokenize.

### Returns

`Vec of (string)` — alternating gaps and matches.

### Errors

None.

### Example

```vir
include virgex

let pat = virgex.compile("@0!1")
let tok = pat.tokenize("a1b22")
```

---

<a id="pattern.iter"></a>
## `pattern.iter`

<!--
id: pattern.iter
api: pattern.iter
previous: pattern_iter
-->

```vir
pattern.iter(pat: Pattern, text: string) -> Iterator
```

Create an iterator for non-overlapping matches over `text`. Equivalent to `pat.iter(text)`
on the entity once camelCase method naming lands.

### Parameters

#### `pat: Pattern`

Compiled pattern.

#### `text: string`

Haystack (owned copy inside iterator state).

### Returns

`Iterator` — initial position before first match.

### Errors

None.

### Example

```vir
include pattern
include regex

var it = pattern.iter(regex.compile("\\\\d+"), "a1b2")
```

---

<a id="pattern.next"></a>
## `pattern.next`

<!--
id: pattern.next
api: pattern.next
previous: next, pattern_iter_next
-->

```vir
pattern.next(it: Iterator) -> Option of (Match)
```

Advance `it` to the next match. Returns `Option.None` when exhausted. Zero-width matches
advance by at least one byte to avoid infinite loops (present engine behavior).

### Parameters

#### `it: Iterator`

Iterator state, updated in place.

### Returns

`Option of (Match)` — next match or `None`.

### Errors

None.

### Example

```vir
include pattern
include regex

var it = pattern.iter(regex.compile("\\\\d+"), "a1b2")
let m = pattern.next(it)
```

## Open questions

- Should `pattern.Match` expose `start` / `end` / `text` / `group(n)` as public methods instead of engine free functions?
- Confirm `pattern.isMatch` vs `pattern.match` split before renaming source (today both full-match).
- Whether `extractAll` nested `Vec` shape should become `Vec of (Vec of (string))` in signatures.

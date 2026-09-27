---
module: parse
title: Parse
summary: Strict string → Result parsing (int stable; float planned).
source:
  - name: string
    path: vir/str/string.vri
    notes: str_to_i64 / str_to_f64 migrate here
  - name: types
    path: vir/core/types.vri
    notes: parse_int / parse_float are non-conforming today
status: closed
notes: >-
  Independent parse.* namespace. Strict whole-input; Result + ParseIntError /
  ParseFloatError. int + intRadix stable; float planned (no stub→0 contract).
  Do not blindly replace compiler partial-token parsers. No .vri until map applied.
---

# Parse

**Text → value** with recoverable failure. Public namespace **`parse`** — not
under [`string`](string.md) or [`format`](format.md).

```vir
parse.int(s) -> Result(int)
parse.intRadix(s, base) -> Result(int)
```

Opposite direction → [`format`](format.md).

## Boundary

| In `parse` | Not in `parse` |
|---|---|
| Strict whole-string numeric parse | Auto-trim / stop-at-first-non-digit |
| `Result(int)` / `Result(float)` | Panic / silent `0` on failure |
| Decimal `int` + explicit radix | Stable `parse.float` until real impl |
| | Template / fmt |
| | Compiler lexer “read part of token” parsers (audit call-sites) |

## Failure model (closed)

```text
Ok(value) | Err(Error { kind: ParseIntError | ParseFloatError, … })
```

Use existing [`ErrorKind.ParseIntError`](error.md) /
`ErrorKind.ParseFloatError`. Do not invent new kinds in this pass.

Unsupported **parameter** (e.g. `base` not in {2,8,10,16}) is a **parameter
contract** failure — not `ParseIntError` for bad input text.

## Strictness (closed)

Must consume **entire** input string:

| Reject | Examples |
|---|---|
| Trailing junk | `"12x"` |
| Empty | `""` |
| Bad characters | spaces, letters (unless allowed by radix/prefix rules) |
| Overflow | outside signed 64-bit range |
| Wrong prefix for radix | `parse.int("0xff")`, `parse.intRadix("0xff", 10)` |

**No** automatic trim. Leading/trailing whitespace → error.

Overflow → parse failure (**no** wrap / truncate). Dedicated tests for
`INT64_MIN`, `INT64_MAX`, and out-of-range values.

## Stable surface (closed)

```text
parse
├── int
└── intRadix
```

Integer domain: signed **64-bit** of the current implementation.

## Grammar — `parse.int` (closed)

Decimal only:

```text
[+|-]? [0-9]+
```

- Optional leading `+` or `-`
- ASCII digits `0`–`9` only
- No `0x` / `0b` / `0o` (those → `ParseIntError` here)
- No whitespace
- Entire string must match

```text
parse.int("255")   → Ok(255)
parse.int("12x")   → Err(ParseIntError)
parse.int("0xff")  → Err(ParseIntError)
parse.int(" 1")    → Err(ParseIntError)
parse.int("")      → Err(ParseIntError)
```

## Grammar — `parse.intRadix` (closed)

```vir
parse.intRadix(s, base) -> Result(int)
```

`base` ∈ {2, 8, 10, 16} only.

```text
[+|-]? [radix-prefix]? [digits for base]+
```

| Base | Optional prefix | Digits |
|---|---|---|
| 2 | `0b` / `0B` | `0`–`1` |
| 8 | `0o` / `0O` | `0`–`7` |
| 10 | *(none)* | `0`–`9` |
| 16 | `0x` / `0X` | `0`–`9`, `a`–`f`, `A`–`F` |

- Sign before prefix: `"-0xff"`, `"-ff"` both OK for base 16
- Prefix that does **not** match the given `base` → reject (`ParseIntError`)
- Digits must be valid for `base`
- Whole string consumed; no trim

```text
parse.intRadix("0xff", 16)  → Ok(255)
parse.intRadix("-ff", 16)   → Ok(-255)
parse.intRadix("0xff", 10)  → Err(ParseIntError)
```

### Contract examples (target)

| Expression | Result |
|---|---|
| `parse.int("255")` | `Ok(255)` |
| `parse.int("12x")` | `ParseIntError` |
| `parse.int("0xff")` | `ParseIntError` |
| `parse.intRadix("0xff", 16)` | `Ok(255)` |
| `parse.intRadix("-ff", 16)` | `Ok(-255)` |

These are **implementation targets**, not a claim that current `parse_int` /
`str_to_i64` already pass.

## Float gate (closed — design criteria)

Shared with [`format.float`](format.md). APIs stay **`planned`** until **all**
rows pass. This section locks the gate; it does **not** certify implementation.

| ID | Requirement |
|---|---|
| F1 | Binary64 round-trip suite with [`format.float`](format.md) (`prec` 0…17, ties-to-even) |
| F2 | Non-finite canonical spellings: `nan` / `inf` / `-inf` (case **audit** with format) |
| F3 | Signed zero preserved on parse↔format |
| F4 | Subnormals covered; finite overflow → `ParseFloatError` (**not** silent `inf`) |
| F5 | Whole-string strictness (same family as `parse.int`); no trim |
| F6 | Today’s stub `parse_float` → `0` and untested `native_f64_to_str` are **not** public contract |

Dependents that wait: [`fmt.float`](fmt.md), [`builder.writeFloat`](builder.md),
JSON floating numbers (see [`json`](json.md)).

## Planned — not stable (`parse.float`)

```text
parse.float(s) -> Result(float)
```

**Never** publish today’s stub (`parse_float` → `0`) as the contract.

**Target contract** (with [`format.float`](format.md)):

| Item | Contract |
|---|---|
| Grammar | Optional sign, decimal, exponent; non-finite canonical `nan` / `inf` / `-inf` |
| Strictness | Whole string (same family as `parse.int`) |
| Invalid | `ParseFloatError` |
| Finite overflow | `ParseFloatError` — **not** silent infinity |

Stable only after the float gate (F1–F6) passes.

## Compatibility

| Current | Public | Action |
|---|---|---|
| `str_to_i64` | `parse.int` | wrapper → deprecate |
| `str_to_f64` | `parse.float` | planned; no stub contract |
| `parse_int` (`types.vri`) | `parse.int` | **replace** semantics (strict + `Result`) |
| `parse_float` stub | `parse.float` | **planned** · rewrite before public |
| `i64_to_str` / `f64_to_str` | → [`format`](format.md) | not parse |
| Compiler `parse_int` copies | — | **audit call-sites**; partial-token use must not silently become strict whole-string |

## Migration map

| Current | Canonical | Action |
|---|---|---|
| `str_to_i64` | `parse.int` | **rename** + strict `Result` |
| `parse_int` | `parse.int` | **behavior change** |
| — | `parse.intRadix` | **new** |
| `str_to_f64` / `parse_float` | `parse.float` | **planned** |

## Test matrix (minimum)

| Case | Expect |
|---|---|
| Decimal happy path | `Ok` |
| `+` / `-` signs | `Ok` |
| Empty / whitespace / trailing junk | `ParseIntError` |
| `parse.int` with `0x`/`0b`/`0o` | `ParseIntError` |
| Radix + matching prefix | `Ok` |
| Radix + wrong prefix | `ParseIntError` |
| Hex letters case | both cases OK for base 16 |
| `INT64_MIN` / `INT64_MAX` | `Ok` |
| Beyond int64 | `ParseIntError` |
| Unsupported `base` | parameter contract (not ParseIntError) |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `parse.int` | `parse.int` | `parse.int(s: string) -> Result(int)` | proposed |
| `parse.intRadix` | `parse.intRadix` | `parse.intRadix(s: string, base: int) -> Result(int)` | proposed |
| `parse.float` | `parse.float` | `parse.float(s: string) -> Result(float)` | planned |

Default error type is [`Error`](error.md): `Result(int)` / `Result(float)`.

---

<a id="parse.int"></a>
## `parse.int`

<!-- id: parse.int previous: str_to_i64 -->

```vir
parse.int(s: string) -> Result(int)
```

Strict decimal whole-string parse → `Ok(int)` or `Err` (`ParseIntError`).

### Status

`proposed` — **present** as non-strict `parse_int` / `str_to_i64` — **debt**.

### Implementation mapping

Replace `vir/core/types.vri` `parse_int` and `str_to_i64` wrappers; do not
blindly swap compiler token scanners.

### See also

- `parse.intRadix`
- [`format.int`](format.md)

---

<a id="parse.intRadix"></a>
## `parse.intRadix`

<!-- id: parse.intRadix -->

```vir
parse.intRadix(s: string, base: int) -> Result(int)
```

Strict parse for `base` ∈ {2, 8, 10, 16} with optional matching prefix.

### Status

`proposed` — **missing**.

### See also

- `parse.int`
- [`format.intRadix`](format.md) / [`format.hex`](format.md)

---

<a id="parse.float"></a>
## `parse.float` *(planned)*

```vir
parse.float(s: string) -> Result(float)
```

Not stable. Must not expose stub-zero behavior.

### Status

`planned`.

### See also

- [`format.float`](format.md)

---

## Implementation readiness

1. New `parse.*` module or relocate from `string`/`types`; return `Result` + `Error`.
2. Implement strict grammars + overflow checks + radix matrix tests.
3. Keep float planned until real parser exists.
4. Audit compiler call-sites before replacing shared `parse_int` helpers.
5. Format SSOT: [`format.md`](format.md). Next: `fmt` + numeric `builder.write*`.

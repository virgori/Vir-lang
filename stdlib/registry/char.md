---
module: char
title: Char
summary: Unicode scalar/codepoint properties — namespace char.*; not ASCII-only.
source:
  - name: char
    path: vir/str/char.vri
  - name: unicode
    path: vir/str/unicode.vri
    notes: script predicates migrate from unicode → char
status: closed
notes: >-
  Operates on one Unicode scalar. Generic predicates/case are Unicode-aware;
  ASCII-only impl = debt. Hex/oct/bin digit may stay lexical/ASCII. Identifier
  helpers and vietnamese-specific out. Shares stdlib Unicode data version.
  No .vri until map applied.
---

# Char

Operations on **one Unicode scalar / codepoint** (`int` holding `U+0000`…
`U+10FFFF`, non-surrogate).

```vir
char.isAlpha(cp)
char.upper(cp)
char.isCjk(cp)
```

Not an ASCII `ctype` kit. Current ASCII-only bodies for generic names are
**non-conforming implementation debt** (same rule as
[`string.lower`](string.md) / [`string.upper`](string.md)).

Shares the **stdlib Unicode data version** with [`unicode`](unicode.md)
(pin: **`pre-UCD`** until first UCD import), [`grapheme`](grapheme.md),
[`normalize`](normalize.md), [`collation`](collation.md).

## Boundary

| In `char` | Not in `char` |
|---|---|
| Scalar predicates + case + `digitValue` | UTF-8 codec → [`unicode`](unicode.md) |
| Script helpers (`isCjk`, …) | `isIdentifierStart` / `isIdentifierPart` (compiler / UAX #31 later) |
| Unicode-aware generic names | Secretly ASCII-only generics |
| | `is_vietnamese_diacritic` — domain-specific, not core |
| | String-level case → [`string`](string.md) |

Lexical digit helpers (`isHexDigit` / `isOctDigit` / `isBinDigit`) may keep
**ASCII / numeric-syntax** semantics. If ASCII-only letter/digit predicates are
needed later, add explicit `char.isAsciiDigit` / `isAsciiAlpha` — do not hide
ASCII under generic names.

## Public surface (closed)

```text
char
├── isDigit
├── isHexDigit
├── isOctDigit
├── isBinDigit
├── isAlpha
├── isAlnum
├── isSpace
├── isUpper
├── isLower
├── isAscii
├── isPrintable
├── isControl
├── isPunctuation
│
├── isCjk
├── isHangul
├── isHiragana
├── isKatakana
├── isEmoji
│
├── upper
├── lower
└── digitValue
```

## Migration map

| Current | Public | Action |
|---|---|---|
| `is_digit` | `char.isDigit` | **rename** · Unicode digit semantics |
| `is_hex_digit` | `char.isHexDigit` | **rename** · lexical/ASCII OK |
| `is_oct_digit` | `char.isOctDigit` | **rename** · lexical/ASCII OK |
| `is_bin_digit` | `char.isBinDigit` | **rename** · lexical/ASCII OK |
| `is_alpha` | `char.isAlpha` | **rename** · Unicode letter |
| `is_alnum` | `char.isAlnum` | **rename** · Unicode |
| `is_space` | `char.isSpace` | **rename** · Unicode whitespace |
| `is_upper` / `is_lower` | `char.isUpper` / `isLower` | **rename** · Unicode |
| `is_ascii` | `char.isAscii` | **rename** |
| `is_printable` | `char.isPrintable` | **rename** · Unicode |
| `is_control` | `char.isControl` | **rename** · Unicode |
| `is_punctuation` | `char.isPunctuation` | **rename** · Unicode |
| `to_upper` / `to_lower` | `char.upper` / `char.lower` | **rename** · Unicode case |
| `digit_value` | `char.digitValue` | **rename** |
| `is_unicode_letter` | → `char.isAlpha` (or internal) | **fold** · no dual public |
| `is_unicode_digit` | → `char.isDigit` | **fold** |
| `is_cjk` / hangul / hiragana / katakana | `char.isCjk` … | **rename** · also move from `unicode` |
| `is_emoji` (unicode.vri) | `char.isEmoji` | **move** |
| `is_identifier_*` | — | **out** public |
| `is_vietnamese_diacritic` | — | **out** public |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `char.isDigit` | `char.isDigit` | `char.isDigit(cp: int) -> bool` | proposed |
| `char.isHexDigit` | `char.isHexDigit` | `char.isHexDigit(cp: int) -> bool` | proposed |
| `char.isOctDigit` | `char.isOctDigit` | `char.isOctDigit(cp: int) -> bool` | proposed |
| `char.isBinDigit` | `char.isBinDigit` | `char.isBinDigit(cp: int) -> bool` | proposed |
| `char.isAlpha` | `char.isAlpha` | `char.isAlpha(cp: int) -> bool` | proposed |
| `char.isAlnum` | `char.isAlnum` | `char.isAlnum(cp: int) -> bool` | proposed |
| `char.isSpace` | `char.isSpace` | `char.isSpace(cp: int) -> bool` | proposed |
| `char.isUpper` | `char.isUpper` | `char.isUpper(cp: int) -> bool` | proposed |
| `char.isLower` | `char.isLower` | `char.isLower(cp: int) -> bool` | proposed |
| `char.isAscii` | `char.isAscii` | `char.isAscii(cp: int) -> bool` | proposed |
| `char.isPrintable` | `char.isPrintable` | `char.isPrintable(cp: int) -> bool` | proposed |
| `char.isControl` | `char.isControl` | `char.isControl(cp: int) -> bool` | proposed |
| `char.isPunctuation` | `char.isPunctuation` | `char.isPunctuation(cp: int) -> bool` | proposed |
| `char.isCjk` | `char.isCjk` | `char.isCjk(cp: int) -> bool` | proposed |
| `char.isHangul` | `char.isHangul` | `char.isHangul(cp: int) -> bool` | proposed |
| `char.isHiragana` | `char.isHiragana` | `char.isHiragana(cp: int) -> bool` | proposed |
| `char.isKatakana` | `char.isKatakana` | `char.isKatakana(cp: int) -> bool` | proposed |
| `char.isEmoji` | `char.isEmoji` | `char.isEmoji(cp: int) -> bool` | proposed |
| `char.upper` | `char.upper` | `char.upper(cp: int) -> int` | proposed |
| `char.lower` | `char.lower` | `char.lower(cp: int) -> int` | proposed |
| `char.digitValue` | `char.digitValue` | `char.digitValue(cp: int) -> int` | proposed |

`digitValue`: hex/decimal digit value, or `-1` if not a digit (today’s
convention) — keep until a `Result`/`Option` audit says otherwise.

---

<a id="char.isDigit"></a>
## `char.isDigit`

<!-- id: char.isDigit -->

```vir
char.isDigit(cp: int) -> bool
```

Unicode decimal digit (not merely ASCII `'0'..'9'`). ASCII-only impl = debt.

### Status

`proposed` — **present** as ASCII `is_digit`.

---

<a id="char.isHexDigit"></a>
## `char.isHexDigit`

```vir
char.isHexDigit(cp: int) -> bool
```

Lexical / ASCII hex digit (`0-9A-Fa-f`). OK to remain ASCII-scoped.

### Status

`proposed`.

---

<a id="char.isOctDigit"></a>
## `char.isOctDigit`

```vir
char.isOctDigit(cp: int) -> bool
```

### Status

`proposed`.

---

<a id="char.isBinDigit"></a>
## `char.isBinDigit`

```vir
char.isBinDigit(cp: int) -> bool
```

### Status

`proposed`.

---

<a id="char.isAlpha"></a>
## `char.isAlpha`

```vir
char.isAlpha(cp: int) -> bool
```

Unicode letter. Folds today’s `is_alpha` + `is_unicode_letter` intent.

### Status

`proposed` — ASCII + partial CJK today — **debt**.

---

<a id="char.isAlnum"></a>
## `char.isAlnum`

```vir
char.isAlnum(cp: int) -> bool
```

### Status

`proposed`.

---

<a id="char.isSpace"></a>
## `char.isSpace`

```vir
char.isSpace(cp: int) -> bool
```

Unicode whitespace (feeds [`string.trim`](string.md) semantics).

### Status

`proposed` — ASCII whitespace today — **debt**.

---

<a id="char.isUpper"></a>
## `char.isUpper` / `char.isLower`

```vir
char.isUpper(cp: int) -> bool
char.isLower(cp: int) -> bool
```

### Status

`proposed` — ASCII today — **debt**.

---

<a id="char.isAscii"></a>
## `char.isAscii`

```vir
char.isAscii(cp: int) -> bool
```

`cp ≤ 0x7F`.

### Status

`proposed`.

---

<a id="char.isPrintable"></a>
## `char.isPrintable` / `isControl` / `isPunctuation`

Unicode General Category–aware targets. Current ASCII-range impl = debt.

### Status

`proposed`.

---

<a id="char.isCjk"></a>
## Script predicates

```vir
char.isCjk(cp: int) -> bool
char.isHangul(cp: int) -> bool
char.isHiragana(cp: int) -> bool
char.isKatakana(cp: int) -> bool
char.isEmoji(cp: int) -> bool
```

Migrate duplicates out of [`unicode`](unicode.md). Coverage must match declared
Unicode version (not ad-hoc ranges alone as the final story).

### Status

`proposed`.

---

<a id="char.upper"></a>
## `char.upper` / `char.lower`

```vir
char.upper(cp: int) -> int
char.lower(cp: int) -> int
```

Unicode simple/full case mapping per stdlib Unicode version. ASCII ±32 today =
**debt**. String-level mapping remains [`string.upper`](string.md) /
[`string.lower`](string.md).

### Status

`proposed`.

---

<a id="char.digitValue"></a>
## `char.digitValue`

```vir
char.digitValue(cp: int) -> int
```

### Status

`proposed` — **present** as `digit_value`.

---

## Implementation readiness

1. Rename to `char.*`; drop public identifier + vietnamese helpers.
2. Move script/`isEmoji` predicates here from `unicode`.
3. Upgrade generic predicates/case to Unicode data for the pinned version.
4. Keep hex/oct/bin lexical unless explicitly widened later.

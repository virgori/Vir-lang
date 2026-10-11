---
id: "VIR-SPC-0019"
type: "SPEC"
domain: "VIR"
title: "Vir Pattern Syntax (VPS)"
status: "ACTIVE"
version: "2.1.0"
language: "en"
spec_class: "SPECIFICATION"
created: "2026-10-07"
updated: "2026-10-07"
owners:
  - "VIR"
components:
  - "virgex"
aliases:
  - "Vir/virgex/spec/VPS_SPEC_v2.md"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "migrated-from-vir"
---

> Migrated from `Vir/virgex/spec/VPS_SPEC_v2.md` at source commit
> `0ed526a47fb6f9ca9a17debd89e4c555adfe00e` on 2026-10-07. The original file
> remains unchanged in the `Vir` repository and is archived byte-for-byte at
> `docs/_legacy/specs/VPS_SPEC_v2.md` (SHA-256
> `c5ae3f99f3e9dcb24182a8255af1adc94c77def85063151afc4d2b6e69c5e8eb`). This
> SPEC governs VPS syntax and syntax-level matching units; Virgex library APIs
> and operational contracts are documented separately in
> `stdlib/registry/virgex.md`.

# VIR-SPC-0019 — Vir Pattern Syntax (VPS)

**Technical Specification v2.1**

---

## 1. Design Goals

VPS is a pattern language designed to replace traditional regex with:

- **Human-readable** syntax
- **Minimal symbols** — fewer than 10 core operators
- **Literal-first** — data is the default, operators require explicit markers
- **Clear separation** of logic and data
- **Applicable** to validation, search, CLI parsing, and NLP rules

VPS does not replicate regex symbol-by-symbol. It reorganizes syntax around the philosophy:

- Real data is the default
- Symbols become commands only in explicit syntactic positions or with prefixes
- Logic must be visually apparent

---

## 2. Core Principles

### 2.1. Literal Default

All characters, strings, and common punctuation are interpreted as literal data unless:

- They occupy a special syntactic position, **or**
- They have a control prefix

| Input  | Interpretation             |
|--------|----------------------------|
| `A`    | literal ASCII byte `A`     |
| `0`    | literal ASCII byte `0`     |
| `abc`  | literal byte sequence `abc`|
| `@0`   | atom: ASCII digit byte     |
| `@-0`  | atom: byte outside digits  |

### 2.2. Minimal Symbol Set

| Symbol   | Role                                                  |
|----------|-------------------------------------------------------|
| `@`      | Atom (data-type class)                                |
| `!`      | Quantifier                                            |
| `~`      | Quantifier range separator                            |
| `?`      | Boolean optional (prefix)                             |
| `:(` `:)` | Group delimiters                                     |
| `\|`     | Anchor **or** OR (context-sensitive)                  |
| `$`      | Escape                                                |
| `-`      | Literal space token / Atom modifier (when after `@`)  |

### 2.3. Context Sensitivity

A symbol may carry different meanings depending on position, governed by strict rules:

| Position / Context        | Meaning                  |
|---------------------------|--------------------------|
| First token after formatting whitespace | Anchor (start-of-string) |
| Last token after formatting whitespace  | Anchor (end-of-string)   |
| Inside `:(` ... `:)`      | OR                       |
| Immediately after `@`     | Atom negation modifier   |
| Anywhere else             | Literal space token      |

---

## 3. Pattern Structure

A pattern consists of:

```
[AnchorStart] Expression* [AnchorEnd]
```

General form:

```
| expression expression expression |
```

Anchors are optional.

---

## 4. Anchors

### 4.1. Symbol

```
|
```

### 4.2. Rules

After formatting whitespace is removed, `|` is an anchor **only** when it is:

- The **first** token of the entire pattern → start anchor
- The **last** token of the entire pattern → end anchor

The edge rules apply to the complete pattern, not to a group. A pipe inside a
group is an alternative separator. A pipe anywhere else is invalid unless it
is the first or last token. To match a literal pipe, write `$|` or place it in
a block escape.

### 4.3. Semantics

| Position | Equivalent regex |
|----------|-----------------|
| `\|` at pattern start | `^` |
| `\|` at pattern end   | `$` |

### 4.4. Example

```
| @0!3 |
```

Meaning: start anchor + exactly three ASCII digit bytes + end anchor. Whether
a library operation searches or requires a full match is defined by that
operation's library contract.

---

## 5. Atoms

An atom designates a byte class, always prefixed with `@`. VPS 2.1 is
byte-oriented: syntax markers are ASCII bytes, literal input is compared as
bytes, and each atom tests exactly one byte. The standard atoms below describe
ASCII ranges only. VPS does not perform Unicode normalization or
case-folding; a non-ASCII UTF-8 literal is represented by its encoded bytes.

### 5.1. Syntax and Parsing

```
@AtomName
@-AtomName
```

- `@` can never appear alone.
- After reading `@`, the parser is always parsing an Atom.
- Therefore, `-` immediately following `@` is unambiguous and acts strictly as an **Atom modifier** (negation), rather than a literal space token.

### 5.2. Standard Atoms and Negative Atoms

A negative atom (`@-`) matches any single byte **not belonging** to the specified atom byte class.

| VPS   | Meaning          | Regex Equivalent |
| ----- | ---------------- | ---------------- |
| `@0`   | digit            | `[0-9]`          |
| `@-0`  | byte outside ASCII digits | `[^0-9]` |
| `@AZ`  | uppercase        | `[A-Z]`          |
| `@-AZ` | byte outside ASCII uppercase | `[^A-Z]` |
| `@az`  | lowercase        | `[a-z]`          |
| `@-az` | byte outside ASCII lowercase | `[^a-z]` |
| `@Az`  | letter           | `[A-Za-z]`       |
| `@-Az` | byte outside ASCII letters | `[^A-Za-z]` |
| `@Az0` | alphanumeric     | `[A-Za-z0-9]`    |
| `@-Az0`| byte outside ASCII alphanumeric | `[^A-Za-z0-9]` |
| `@06`  | digit in range 0–6 | `[0-6]`        |
| `@-06` | non-digit in range 0–6 | `[^0-6]`   |

### 5.3. Semantics of Negation

The `-` modifier acts strictly as an **Atom modifier**, not a general negation operator. It only inverts the character-class test for that specific atom matcher.

Conceptually:

```
@0
→ matches Digit

@-0
→ matches NOT(Digit)
```

This is an implementation detail of the Atom matcher only. It does **not** create a standalone NOT operator, a negative expression, or a `NotNode` in the AST. Precedence, group syntax, and quantifier behaviors remain unchanged.

### 5.4. Examples

| VPS | Meaning / Matches |
| --- | --- |
| `@AZ` | one ASCII uppercase byte |
| `@-AZ` | one byte outside ASCII uppercase |
| `@0` | one ASCII digit byte |
| `@-0` | one byte outside ASCII digits |
| `@Az0` | one ASCII alphanumeric byte |
| `@-Az0` | one byte outside ASCII alphanumeric |
| `\| @-0!3 \|` | exactly three bytes outside ASCII digits |
| `\| @AZ!2 @-0!5 \|` | two ASCII uppercase bytes followed by five bytes outside ASCII digits |
| `:( @0 \| @-0 :)` | digit OR non-digit |

### 5.5. Implementation Notes

An implementation may internally store an Atom AST node as:

```
Atom
    negate: bool
    atomType: AtomType
```

instead of introducing a separate `NotNode` or complex expression tree node.

---

## 6. Quantifiers

A quantifier is a **postfix** operator that specifies repetition count for the
immediately preceding base expression. It is one contiguous token (`!3`,
`!1~5`, `!1~`, or `!~`); formatting whitespace may occur before or after the
token, but not inside it. At most one quantifier may follow a base expression.

### 6.1. Symbols

```
!   (quantifier marker)
~   (range separator)
```

### 6.2. Valid Forms

| Syntax    | Meaning                               | Regex    |
|-----------|---------------------------------------|----------|
| `!n`      | Exactly n times                       | `{n}`    |
| `!n~m`    | From n to m times (inclusive)         | `{n,m}`  |
| `!n~`     | At least n times                      | `{n,}`   |
| `!~`      | Zero or more (0 to unbounded)         | `*`      |

### 6.3. Examples

| VPS       | Meaning                   |
|-----------|---------------------------|
| `@0!3`    | exactly 3 digits          |
| `@-0!3`   | exactly 3 non-digits      |
| `@Az!1~5` | 1 to 5 letters            |
| `@0!2~`   | at least 2 digits         |
| `-!~`     | zero or more literal spaces |

---

## 7. Boolean Optional

### 7.1. Symbol

```
?
```

### 7.2. Nature

`?` is a **prefix** boolean operator meaning:

> the following complete expression may or may not be present

### 7.3. Scope Rule

`?` always applies to the **entire next complete expression**.

```
?@AZ!2   →   ?( @AZ!2 )       ✓ — optional "exactly 2 uppercase"
           NOT  (?@AZ)!2       ✗
```

### 7.4. Examples

| VPS                       | Meaning                                    |
|---------------------------|--------------------------------------------|
| `?@0`                     | optional single digit                      |
| `?@-0`                    | optional single non-digit                  |
| `?@AZ!2`                  | optional exactly-2-uppercase               |
| `?:( $- @0!5 :)`         | optional group: literal `-` + 5 digits     |

---

## 8. Groups

### 8.1. Symbols

```
:(   open group
:)   close group
```

### 8.2. Semantics

Groups bundle multiple expressions into a single logical unit. A group can be:

- Standalone
- Quantified
- Made optional with `?`
- Contain OR alternatives

### 8.3. Examples

```
:( - @0 :)       →  space then digit
:( - @0 :)!3     →  repeat (space + digit) 3 times
?:( $- @0!5 :)   →  optional (literal-dash + 5 digits)
:( @0 | @-0 :)   →  digit OR non-digit
```

---

## 9. OR Logic (Alternation)

### 9.1. Symbol

```
|
```

### 9.2. Rule

`|` is interpreted as OR **only** inside a group `:(` ... `:)`.

### 9.3. Examples

```
:( A | B :)           →  A or B
:( @AZ!2 | @0!3 :)   →  2 uppercase OR 3 digits
:( @0 | @-0 :)        →  digit OR non-digit
```

### 9.4. Important

Outside `:(` `:)`, `|` is **not** OR. This is invalid OR:

```
@AZ | @0              ✗  — must be :( @AZ | @0 :)
```

---

## 10. Whitespace

### 10.1. Formatting Whitespace

The ASCII bytes space (U+0020), tab (U+0009), line feed (U+000A), and
carriage return (U+000D) are formatting whitespace and are ignored outside
escape operands. Form feed and other whitespace bytes are ordinary literal
data. Whitespace inside a single-byte escape or block escape is data. There is
no comment syntax. Whitespace is discarded between complete lexical tokens,
not within a token; for example, `@0 !3` is valid but `@0 ! 3` is not.

```
@0!3   ≡   @0 !3
```

### 10.2. Target Whitespace

To match a literal space character in the input data, use:

```
-
```

### 10.3. Example

```
@AZ!2 - @0!5
```

Meaning: 2 ASCII uppercase bytes + one literal ASCII space + 5 ASCII digits.

---

## 11. Escape

### 11.1. Symbol

```
$
```

### 11.2. Single-Character Escape

`$` before exactly one byte forces that byte to be literal:

| VPS  | Result           |
|------|------------------|
| `$\|` | literal `\|`    |
| `$?` | literal `?`      |
| `$-` | literal `-`      |
| `$$` | literal `$`      |
| `$@` | literal `@`      |
| `$!` | literal `!`      |

### 11.3. Block Escape

```
$. content .$
```

Everything between the first following `.$` delimiter and `$.` is treated as
a literal byte sequence. Delimiters do not nest. An empty block is valid. A
missing closing delimiter is invalid.

```
$. |@!~ .$   →   literal string "|@!~"
```

---

## 12. Literals

### 12.1. Principle

Any byte that does not form a reserved token in its current context is
literal. The reserved forms are `@` atoms, `!` quantifiers, prefix `?`, `:(`
and `:)` groups, context-sensitive `|`, `$` escapes, and `-` space tokens. A
colon not followed by `(` or `)` is literal; `~` is literal unless consumed
as part of a quantifier. Bytes that would otherwise be syntax must be escaped
to match literally.

```
ABC   →  literal "ABC"
HN    →  literal "HN"
```

### 12.2. When to Escape

Escape is recommended when the character is `|`, `?`, `$`, `-`, `@`, `!`, `:`, or could be misinterpreted in a syntactic role.

---

## 13. Operator Scope

### 13.1. `!` and `~` (Postfix)

Always bind to the **immediately preceding** expression:

```
@AZ!2          →  atom @AZ quantified to 2
@-0!5          →  negative atom @-0 quantified to 5
:( A | B :)!3  →  entire group repeated 3 times
```

### 13.2. `?` (Prefix)

Always applies to the **next complete expression**:

```
?@AZ!2             →  optional( @AZ quantified to 2 )
?@-0!3             →  optional( @-0 quantified to 3 )
?:( @AZ!2 $- :)    →  optional( entire group )
```

---

## 14. Nesting

VPS allows nested groups:

```
:( A | :( B | C :) :)
```

Meaning: `A` or (`B` or `C`).

---

## 15. Reference Examples

### 15.1. Exactly 3 digits

```
| @0!3 |
```

Matches: `123` — Rejects: `12`, `1234`, `abc`

### 15.2. Exactly 3 non-digits

```
| @-0!3 |
```

Matches: `abc`, `xyz`, `!@#` — Rejects: `123`, `a1b`

### 15.3. ID code `HN-12345?`

```
| @AZ!2 $- @0!5 $? |
```

- 2 uppercase + literal `-` + 5 digits + literal `?`

### 15.4. Two uppercase letters followed by 5 non-digits

```
| @AZ!2 @-0!5 |
```

Matches: `ABhello`, `XY-*-#` — Rejects: `AB12345`

### 15.5. Digit or non-digit

```
:( @0 | @-0 :)
```

Matches: any single byte.

### 15.6. Optional numeric suffix

```
| @AZ!2 ?:( $- @0!5 :) |
```

Matches: `HN`, `HN-12345`

### 15.7. A or B

```
| :( A | B :) |
```

### 15.8. Username 3–12 alphanumeric

```
| @Az0!3~12 |
```

---

## 16. Comparison with Traditional Regex

The table is a syntax analogy for ASCII input. VPS classes operate on bytes;
Unicode regular-expression classes may operate on code points and therefore
are not generally equivalent.

| Regex               | VPS                              |
|---------------------|----------------------------------|
| `^[A-Z]{2}$`        | `\| @AZ!2 \|`                   |
| `\d{3}`             | `@0!3`                           |
| `\D{3}` / `[^0-9]{3}` | `@-0!3`                        |
| `[A-Za-z0-9]{3,12}` | `@Az0!3~12`                      |
| `[^A-Za-z0-9]{3,12}`| `@-Az0!3~12`                     |
| `(A\|B)`            | `:( A \| B :)`                   |
| literal ASCII space   | `-`                              |
| `([A-Z]{2}-\d{5})?` | `?:( @AZ!2 $- @0!5 :)`          |
| `^[A-Z]{2}(-\d{5})?$` | `\| @AZ!2 ?:( $- @0!5 :) \|`  |

---

## 17. Validity Rules

### 17.1. Valid

```
| @0!3 |
| @-0!3 |
| @AZ!2 @-0!5 |
:( @0 | @-0 :)
?@AZ!2
:( A | B :)
?:( @AZ!2 $- @0!5 :)
```

### 17.2. Invalid

| Pattern | Reason |
|---|---|
| `@AZ \| @0` | Pipe is neither an anchor nor an enclosed alternative; use `:( @AZ \| @0 :)`. |
| `@AZ!2?` | `?` is a prefix operator, not a postfix operator. |
| `\| A \| B \|` | Interior top-level pipe is invalid; use `\| :( A \| B :) \|`. |
| `@` / `@-` | Atom name is missing. |
| `@96` | Descending numeric atom range. |
| `@Az!3!2` | More than one quantifier follows a base expression. |
| `!3` | Quantifier has no preceding base expression. |
| `$` / `$.open` | Escape operand or block terminator is missing. |
| `:( A` / `A :)` | Group delimiters are unmatched. |

---

## 18. Formal Grammar

The lexer discards formatting whitespace between complete tokens, then scans
left to right. It recognizes `:(` and `:)` as two-byte delimiters; `@` starts
an atom and consumes the maximal ASCII alphanumeric name (after optional
`-`); `!` consumes one complete quantifier form; `$` consumes one escaped
byte or a complete block escape; and `?`, `|`, and `-` are individual tokens.
Any other byte is literal, including `:` when it does not begin a group and
`~` when it is not part of a quantifier. Reserved syntax bytes must be escaped
to be literal. Atom names are case-sensitive. Anchors are classified from the
first and last tokens of the complete token stream; any remaining top-level
pipe is invalid. If the whole token stream is a single pipe, it is a
start-anchor token. The grammar below is over that token stream. `Sequence`
may be empty, so an empty pattern, group, or alternative is syntactically
valid and denotes the empty byte sequence.

```text
Pattern        = [AnchorStart] Sequence [AnchorEnd] EOF
AnchorStart    = PIPE     (* only when first token *)
AnchorEnd      = PIPE     (* only when last token *)

Sequence       = { Expression }
Expression     = OptionalExpr | QuantifiedExpr | BaseExpr
OptionalExpr   = QUESTION Expression
QuantifiedExpr = BaseExpr Quantifier
BaseExpr       = Group | Atom | SpaceToken | EscapedByte | EscapedBlock | LiteralByte

Group          = GROUP_OPEN Alternation GROUP_CLOSE
Alternation    = Sequence { PIPE Sequence }

Atom           = ATOM_PREFIX [NEGATION] AtomName
NEGATION       = '-'
AtomName       = 'Az0' | 'Az' | 'AZ' | 'az' | '0' | Digit Digit
                 (* two-digit form is an inclusive ascending ASCII digit range *)

Quantifier     = '!' Digit { Digit }
               | '!' Digit { Digit } '~' Digit { Digit }
               | '!' Digit { Digit } '~'
               | '!~'

SpaceToken     = '-'
EscapedByte    = '$' ANY_BYTE
EscapedBlock   = '$.' { ANY_BYTE } '.$'
LiteralByte    = ANY_BYTE_EXCEPT_RESERVED_IN_CONTEXT
Digit          = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
```

Additional validity constraints: a quantifier must immediately follow one
`BaseExpr`; only one quantifier may follow that base; `?` must precede one
`Expression`; and all groups and escapes must be terminated. A parser MUST
consume the complete token stream or reject the pattern. It MUST NOT silently
ignore an invalid or trailing token. The concrete error type, diagnostic text,
and recovery behavior are library/compiler API concerns and are not defined
here.

The active implementation has a known conformance gap: the current
`_virgexCompile` path does not reject every unconsumed top-level token even
though this SPEC requires full-token consumption. This statement records
implementation status; it does not weaken the normative grammar above.

For atoms, the lexer consumes the maximal ASCII alphanumeric name after `@`
or `@-`; the complete name must be one of the listed names or an ascending
two-digit range. A `-` not immediately following `@` is the space token, not
general negation.

---

## 19. Scope Boundary

This SPEC defines the VPS grammar and syntax-level byte/atom semantics. It
does not define Virgex library functions, signatures, search/full-match
operation choices, extraction, replacement, split behavior, error
types/diagnostics, or runtime capabilities. Those belong to the separate
standard-library contract maintained in `stdlib/registry/virgex.md`;
`stdlib/vir/virgex/virgex.vri` is implementation evidence, not the API
specification. VPS itself has no named-capture syntax; adding such syntax
requires a versioned change to this SPEC.


---

## 20. Use Cases

VPS is suited for:

- **Data validation** — form fields, IDs, codes
- **Pattern matching** — search and filter
- **Log filtering** — structured log analysis
- **CLI rules** — argument format specification
- **NLP rules** — named entity patterns
- **Search syntax** — internal search engines

The strength of VPS is not "shorter than regex" but:

- Readable at a glance
- Minimal symbols
- Clear logic flow
- Easy to generate from AI / NLP systems

---

## 21. Quick Reference

### Core Symbols

| Symbol     | Role                                                  |
|------------|-------------------------------------------------------|
| `@`        | Atom                                                  |
| `!`        | Quantifier                                            |
| `~`        | Quantifier range                                      |
| `?`        | Optional (prefix boolean)                             |
| `:(` `:)`  | Group                                                 |
| `\|`       | Anchor or OR (contextual)                             |
| `$`        | Escape                                                |
| `-`        | Literal ASCII space byte or Atom modifier (immediately after `@`)|

### Special Rules

| Rule                                | Detail                                         |
|-------------------------------------|------------------------------------------------|
| `\|` at pattern edges               | Anchor                                         |
| `\|` inside `:( :)`                 | OR                                             |
| `?` is prefix                       | `?expr` not `expr?`                            |
| `!` is postfix                      | `expr!n` not `!nexpr`                          |
| `-` after `@`                       | Atom negation modifier (`@-0` matches non-ASCII-digit byte)|
| Literal is default                  | Unreserved bytes are literal; reserved bytes need escaping |
| Match literal space                 | Use `-` (outside `@`)                          |

---


## 22. Implementation Conformance Notes

As observed in the active implementation on 2026-10-07, `_virgexCompile` in
`stdlib/vir/virgex/virgex.vri` does not reject every unconsumed top-level
token. This conflicts with the full-token-consumption requirement in §18 and
is an implementation conformance gap; it does not weaken the normative rule.

## 23. Compatibility

VPS is not a symbol-for-symbol implementation of Python `re` or another
regular-expression language. Consumers that accept VPS patterns MUST document
that syntax explicitly and MUST NOT claim compatibility with another regex
dialect unless they provide and verify a separate translation layer.

## 24. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-07 | 2.0.0 | Migrated VPS v2 syntax specification from the `Vir` repository; separated runtime API claims from the VPS syntax contract |
| 2026-10-07 | 2.1.0 | Made lexical rules, byte units, whitespace, anchors, validity, and full-input parser acceptance normative; removed library API/runtime policy material |

## 25. Related Specifications

- `VIR-SPC-0017` / `VIR-SPC-0018` — Vir language specifications
- `VIRC-SPC-0001` — Compiler and runtime algorithms
- `stdlib/registry/virgex.md` — Current Virgex module API reference
- `docs/_legacy/specs/VPS_SPEC_v2.md` — Byte-for-byte archival source copy

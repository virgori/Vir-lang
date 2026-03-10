# Vir Pattern Syntax (VPS)

**Technical Specification v1.0**

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

| Input  | Interpretation         |
|--------|------------------------|
| `A`    | literal character `A`  |
| `0`    | literal character `0`  |
| `abc`  | literal string `abc`   |
| `@0`   | atom: digit            |

### 2.2. Minimal Symbol Set

| Symbol   | Role                                  |
|----------|---------------------------------------|
| `@`      | Atom (data-type class)                |
| `!`      | Quantifier                            |
| `~`      | Quantifier range separator            |
| `?`      | Boolean optional (prefix)             |
| `:(` `:)` | Group delimiters                    |
| `\|`     | Anchor **or** OR (context-sensitive)  |
| `$`      | Escape                                |
| `-`      | Literal space token                   |

### 2.3. Context Sensitivity

A symbol may carry different meanings depending on position, governed by strict rules:

| Position of `\|`          | Meaning  |
|---------------------------|----------|
| First char of pattern     | Anchor (start-of-string) |
| Last char of pattern      | Anchor (end-of-string)   |
| Inside `:(` ... `:)`      | OR       |
| Anywhere else             | Literal (must escape)    |

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

`|` is an anchor **only** when it is:

- The **first** character of the entire pattern → start anchor
- The **last** character of the entire pattern → end anchor

### 4.3. Semantics

| Position | Equivalent regex |
|----------|-----------------|
| `\|` at pattern start | `^` |
| `\|` at pattern end   | `$` |

### 4.4. Example

```
| @0!3 |
```

Meaning: `^` + exactly 3 digits + `$` → matches `123`, rejects `12`, `1234`, `abc`.

---

## 5. Atoms

An atom designates a character class, always prefixed with `@`.

### 5.1. Symbol

```
@
```

### 5.2. Standard Atoms

| Atom    | Meaning                        | Regex equivalent     |
|---------|--------------------------------|----------------------|
| `@Az`   | Latin letter (upper or lower)  | `[A-Za-z]`          |
| `@AZ`   | Uppercase letter               | `[A-Z]`             |
| `@az`   | Lowercase letter               | `[a-z]`             |
| `@0`    | Digit 0–9                      | `[0-9]`             |
| `@XY`   | Digit in range X–Y             | `[X-Y]`             |
| `@Az0`  | Alphanumeric                   | `[A-Za-z0-9]`       |

> `@06` = digit in range 0–6 → `[0-6]`

### 5.3. Examples

| VPS   | Matches         |
|-------|-----------------|
| `@AZ` | one uppercase   |
| `@0`  | one digit       |
| `@Az0`| one alphanumeric|

---

## 6. Quantifiers

A quantifier is a **postfix** operator that specifies repetition count for the immediately preceding expression.

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
```

### 9.4. Important

Outside `:(` `:)`, `|` is **not** OR. This is invalid OR:

```
@AZ | @0              ✗  — must be :( @AZ | @0 :)
```

---

## 10. Whitespace

### 10.1. Formatting Whitespace

Whitespace (spaces, tabs) used for visual formatting in the pattern source is **ignored**.

```
@0!3   ≡   @0 !3   ≡   @0  !  3
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

Meaning: 2 uppercase + 1 literal space + 5 digits.

---

## 11. Escape

### 11.1. Symbol

```
$
```

### 11.2. Single-Character Escape

`$` before a character forces it to be a literal:

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

Everything between `$.` and `.$` is treated as a literal block.

```
$. |@!~ .$   →   literal string "|@!~"
```

---

## 12. Literals

### 12.1. Principle

Any content that does not fall into a special syntactic position is a literal.

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
:( A | B :)!3  →  entire group repeated 3 times
```

### 13.2. `?` (Prefix)

Always applies to the **next complete expression**:

```
?@AZ!2             →  optional( @AZ quantified to 2 )
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

### 15.2. ID code `HN-12345?`

```
| @AZ!2 $- @0!5 $? |
```

- 2 uppercase + literal `-` + 5 digits + literal `?`

### 15.3. Optional numeric suffix

```
| @AZ!2 ?:( $- @0!5 :) |
```

Matches: `HN`, `HN-12345`

### 15.4. A or B

```
| :( A | B :) |
```

### 15.5. Username 3–12 alphanumeric

```
| @Az0!3~12 |
```

---

## 16. Comparison with Traditional Regex

| Regex               | VPS                              |
|---------------------|----------------------------------|
| `^[A-Z]{2}$`        | `\| @AZ!2 \|`                   |
| `\d{3}`             | `@0!3`                           |
| `[A-Za-z0-9]{3,12}` | `@Az0!3~12`                      |
| `(A\|B)`            | `:( A \| B :)`                   |
| `\s`                | `-`                              |
| `([A-Z]{2}-\d{5})?` | `?:( @AZ!2 $- @0!5 :)`          |
| `^[A-Z]{2}(-\d{5})?$` | `\| @AZ!2 ?:( $- @0!5 :) \|`  |

---

## 17. Validity Rules

### 17.1. Valid

```
| @0!3 |
?@AZ!2
:( A | B :)
?:( @AZ!2 $- @0!5 :)
```

### 17.2. Invalid / Ambiguous

| Pattern           | Issue                                          |
|-------------------|------------------------------------------------|
| `@AZ \| @0`      | OR outside group — must use `:( @AZ \| @0 :)` |
| `@AZ!2?`         | `?` is prefix, not suffix                      |
| `\| A \| B \|`   | Ambiguous anchor vs OR — use `\| :( A \| B :) \|` |

---

## 18. Formal Grammar

```
Pattern        = [AnchorStart] Sequence [AnchorEnd]
AnchorStart    = '|'
AnchorEnd      = '|'

Sequence       = Expression*

Expression     = OptionalExpr
               | QuantifiedExpr
               | BaseExpr

OptionalExpr   = '?' Expression

QuantifiedExpr = BaseExpr Quantifier

BaseExpr       = Group
               | Atom
               | SpaceToken
               | EscapedChar
               | EscapedBlock
               | Literal

Group          = ':(' Alternation ':)'
Alternation    = Sequence ( '|' Sequence )*

Atom           = '@' AtomName
AtomName       = 'Az0' | 'Az' | 'AZ' | 'az'
               | DIGIT DIGIT          (* numeric range *)
               | '0'                  (* all digits    *)

Quantifier     = '!' NUMBER
               | '!' NUMBER '~' NUMBER
               | '!' NUMBER '~'
               | '!' '~'

SpaceToken     = '-'

EscapedChar    = '$' ANY_CHAR
EscapedBlock   = '$.' ANY_CHARS '.$'

Literal        = <any character not in special position>

NUMBER         = [0-9]+
```

---

## 19. Use Cases

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

## 20. Quick Reference

### Core Symbols

| Symbol     | Role                          |
|------------|-------------------------------|
| `@`        | Atom                          |
| `!`        | Quantifier                    |
| `~`        | Quantifier range              |
| `?`        | Optional (prefix boolean)     |
| `:(` `:)`  | Group                         |
| `\|`       | Anchor or OR (contextual)     |
| `$`        | Escape                        |
| `-`        | Literal space                 |

### Special Rules

| Rule                                | Detail                        |
|-------------------------------------|-------------------------------|
| `\|` at pattern edges               | Anchor                        |
| `\|` inside `:( :)`                 | OR                            |
| `?` is prefix                       | `?expr` not `expr?`           |
| `!` is postfix                      | `expr!n` not `!nexpr`         |
| Literal is default                  | No special marking needed     |
| Match literal space                 | Use `-`                       |

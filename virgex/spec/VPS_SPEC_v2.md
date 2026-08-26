# Vir Pattern Syntax (VPS)

**Technical Specification v2.0**

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
| `@-0`  | atom: non-digit        |

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
| First char of pattern     | Anchor (start-of-string) |
| Last char of pattern      | Anchor (end-of-string)   |
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

### 5.1. Syntax and Parsing

```
@AtomName
@-AtomName
```

- `@` can never appear alone.
- After reading `@`, the parser is always parsing an Atom.
- Therefore, `-` immediately following `@` is unambiguous and acts strictly as an **Atom modifier** (negation), rather than a literal space token.

### 5.2. Standard Atoms and Negative Atoms

A negative atom (`@-`) matches any single character **not belonging** to the specified atom character class.

| VPS   | Meaning          | Regex Equivalent |
| ----- | ---------------- | ---------------- |
| `@0`   | digit            | `[0-9]`          |
| `@-0`  | non-digit        | `[^0-9]`         |
| `@AZ`  | uppercase        | `[A-Z]`          |
| `@-AZ` | non-uppercase    | `[^A-Z]`         |
| `@az`  | lowercase        | `[a-z]`          |
| `@-az` | non-lowercase    | `[^a-z]`         |
| `@Az`  | letter           | `[A-Za-z]`       |
| `@-Az` | non-letter       | `[^A-Za-z]`      |
| `@Az0` | alphanumeric     | `[A-Za-z0-9]`    |
| `@-Az0`| non-alphanumeric | `[^A-Za-z0-9]`   |
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
| `@AZ` | one uppercase letter |
| `@-AZ` | one non-uppercase letter |
| `@0` | one digit |
| `@-0` | one non-digit character |
| `@Az0` | one alphanumeric character |
| `@-Az0` | one non-alphanumeric character |
| `\| @-0!3 \|` | exactly three non-digit characters |
| `\| @AZ!2 @-0!5 \|` | two uppercase letters followed by five non-digit characters |
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

Matches: any single character.

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

| Regex               | VPS                              |
|---------------------|----------------------------------|
| `^[A-Z]{2}$`        | `\| @AZ!2 \|`                   |
| `\d{3}`             | `@0!3`                           |
| `\D{3}` / `[^0-9]{3}` | `@-0!3`                        |
| `[A-Za-z0-9]{3,12}` | `@Az0!3~12`                      |
| `[^A-Za-z0-9]{3,12}`| `@-Az0!3~12`                     |
| `(A\|B)`            | `:( A \| B :)`                   |
| `\s`                | `-`                              |
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

### 17.2. Invalid / Ambiguous

| Pattern           | Issue                                          |
|-------------------|------------------------------------------------|
| `@AZ \| @0`      | OR outside group — must use `:( @AZ \| @0 :)` |
| `@AZ!2?`         | `?` is prefix, not suffix                      |
| `\| A \| B \|`   | Ambiguous anchor vs OR — use `\| :( A \| B :) \|` |
| `-@0`            | Invalid negation position — `-` before `@` is space token followed by atom `@0` |

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

Atom           = '@' Negation? AtomName
Negation       = '-'
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

## 19. Pattern Policy

Virgex cleanly separates three concerns:

1. **Pattern Syntax (DSL)** — purely declarative pattern structure
2. **Matching Behavior (Runtime)** — determining match validity
3. **Output Behavior (Runtime/API)** — formatting and returning results

The DSL MUST remain purely declarative and MUST NOT introduce named capture, capture blocks, capture delimiters, or variable names into the pattern syntax. The pattern grammar remains 100% unchanged. Instead, execution behavior is governed by **Pattern Policies** at runtime.

> **Pattern Policy does not affect parsing or grammar. It only changes how the runtime consumes the matched result.**

### 19.1. Policy Overview

The exact same pattern may be executed under different runtime policies:

| Pattern | Policy | Result |
|---------|--------|--------|
| `\| @0!4 $- @0!2 $- @0!2 \|` | Match | `true` / `false` |
| `\| @0!4 $- @0!2 $- @0!2 \|` | Extract | `["2026","07","24"]` |
| `\| @AZ!2 $- @0!5 \|` | Extract | `["HN","12345"]` |

#### API Summary

| Policy  | Typical API              | Return         |
| ------- | ------------------------ | -------------- |
| Match   | `match(pattern, text)`   | `bool`         |
| Extract | `extract(pattern, text)` | `List<String>` |

### 19.2. Match Policy

Match Policy evaluates whether a pattern satisfies an input text. It answers a single boolean question:

- Does the pattern match?

#### Runtime API Example

```
match(pattern, text)
```

#### Result

```
true
false
```

### 19.3. Extract Policy

Extract Policy traverses the matched AST and returns matched atom values.

- **No capture syntax** is required inside the pattern DSL.
- The runtime extracts values from matched Atom nodes. Other node types (groups, literals, quantifiers, anchors) are structural and are not returned unless an implementation explicitly chooses otherwise.

#### Example

Pattern:

```
| @AZ!2 $- @0!5 |
```

Text:

```
HN-12345
```

Result:

```
["HN","12345"]
```

### 19.4. Important Notes & Host Language Integration

- VPS **does NOT** support named capture.
- VPS **does NOT** embed variable names into patterns.
- VPS **does NOT** mix host-language concepts into the DSL.
- **Variable naming belongs entirely to the host programming language.**

Mapping extracted items to named variables is performed natively using host language destructuring mechanisms:

**Vir:**

```vir
let [prefix, number] = extract(pattern, text)
```

**Rust:**

```rust
let [prefix, number] = virgex.extract(pattern)?;
```

**JavaScript:**

```javascript
const [prefix, number] = extract(pattern, text);
```

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
| `-`        | Literal space or Atom modifier (immediately after `@`)|

### Special Rules

| Rule                                | Detail                                         |
|-------------------------------------|------------------------------------------------|
| `\|` at pattern edges               | Anchor                                         |
| `\|` inside `:( :)`                 | OR                                             |
| `?` is prefix                       | `?expr` not `expr?`                            |
| `!` is postfix                      | `expr!n` not `!nexpr`                          |
| `-` after `@`                       | Atom negation modifier (`@-0` matches non-digit)|
| Literal is default                  | No special marking needed                      |
| Match literal space                 | Use `-` (outside `@`)                          |

---

## 22. Virgex Runtime Library

Virgex is structured into two distinct architectural layers:

1. **VPS (Vir Pattern Syntax)** — The purely declarative pattern language.
2. **Virgex Runtime Library** — The host runtime API executing searches, extractions, replacements, tokenization, and iterations.

The VPS grammar describes pattern structure only. Searching, extraction, replacement, tokenization, and similar behaviors belong entirely to the runtime library.

> **Important:** Runtime APIs are **not** part of the VPS grammar. The VPS grammar remains stable, minimal, and declarative. Runtime capabilities may evolve independently without modifying or extending the pattern DSL syntax. New functionality should be added through the runtime library whenever possible instead of extending the DSL.

### 22.1. Compilation API

The runtime provides pattern compilation to parse pattern strings into optimized, reusable `Pattern` objects.

#### `compile`

- **Purpose**: Compiles a VPS pattern string into a runtime `Pattern` object.
- **Signature**: `func compile(pattern: string): Pattern`
- **Parameters**: `pattern: string` — A valid VPS pattern string.
- **Return Value**: `Pattern` — A compiled, reusable pattern instance.
- **Example**:
  ```vir
  let plate = virgex.compile("| @AZ!2 $- @0!5 |")
  ```
- **Notes**: Pattern compilation validates the VPS syntax according to the formal grammar. If syntax is invalid, compilation throws a runtime error.

---

### 22.2. Dual UFCS Integration

Virgex Runtime APIs follow the Vir **Uniform Function Call Syntax (UFCS)** philosophy. Every runtime function uses `this` as its first parameter, enabling natural call syntax on both `string` instances and `Pattern` objects.

#### String-first Call Form

```vir
text.match(pattern)
text.extract(pattern)
text.find(pattern)
text.find_all(pattern)
text.replace(pattern, "***")
```

#### Pattern-first Call Form

```vir
pattern.match(text)
pattern.extract(text)
pattern.find(text)
pattern.find_all(text)
pattern.replace(text, "***")
```

#### Complete Usage Example in Vir

```vir
func validate_id(text: string):
    let plate = virgex.compile("| @AZ!2 $- @0!5 |")

    if plate.match(text) do
        print("Valid license plate format")
    end

    let values = plate.extract(text)
    print("Prefix: $values[0], Code: $values[1]")

    let masked = plate.replace(text, "***")
    print("Masked output: $masked")
end.
```

---

### 22.3. Core Runtime Function Reference

#### 22.3.1. `match`

- **Purpose**: Evaluates whether a string satisfies a pattern according to Match Policy.
- **Signature**:
  ```vir
  func match(this: string, pattern: Pattern): bool
  func match(this: Pattern, text: string): bool
  ```
- **Parameters**:
  - `this`: The target `string` (or `Pattern`).
  - `pattern` / `text`: The pattern (or text) to match.
- **Return Value**: `bool` — `true` if matched, `false` otherwise.
- **Example**:
  ```vir
  if text.match(pattern) do
      print("Match found!")
  end
  ```
- **Notes**: Evaluates validity only. Does not extract values or allocate memory for matches.

#### 22.3.2. `find`

- **Purpose**: Finds the first substring matching the pattern.
- **Signature**:
  ```vir
  func find(this: string, pattern: Pattern): string
  func find(this: Pattern, text: string): string
  ```
- **Parameters**:
  - `this`: The target `string` (or `Pattern`).
  - `pattern` / `text`: The pattern (or text) to search.
- **Return Value**: `string` — The first matched substring, or `""` if not found.
- **Example**:
  ```vir
  let code = text.find(plate)
  ```
- **Notes**: Performs a non-anchored search for the first occurrence unless pattern anchors `|` are specified.

#### 22.3.3. `find_all`

- **Purpose**: Finds all non-overlapping substrings matching the pattern.
- **Signature**:
  ```vir
  func find_all(this: string, pattern: Pattern): [string]
  func find_all(this: Pattern, text: string): [string]
  ```
- **Parameters**:
  - `this`: The target `string` (or `Pattern`).
  - `pattern` / `text`: The pattern (or text) to search.
- **Return Value**: `[string]` — An array of all matched substrings.
- **Example**:
  ```vir
  let all_codes = text.find_all(plate)
  ```
- **Notes**: Returns an empty array `[]` if no matches are found.

#### 22.3.4. `extract`

- **Purpose**: Extracts matched atom values from the first pattern match according to Extract Policy.
- **Signature**:
  ```vir
  func extract(this: string, pattern: Pattern): [string]
  func extract(this: Pattern, text: string): [string]
  ```
- **Parameters**:
  - `this`: The target `string` (or `Pattern`).
  - `pattern` / `text`: The pattern (or text) to extract from.
- **Return Value**: `[string]` — An array of extracted atom values.
- **Example**:
  ```vir
  let [prefix, number] = text.extract(plate)
  ```
- **Notes**: Structural tokens (such as literal spaces `-` or anchors `|`) are omitted by default according to Extract Policy.

#### 22.3.5. `extract_all`

- **Purpose**: Extracts matched atom values for all non-overlapping pattern occurrences in the text.
- **Signature**:
  ```vir
  func extract_all(this: string, pattern: Pattern): [[string]]
  func extract_all(this: Pattern, text: string): [[string]]
  ```
- **Parameters**:
  - `this`: The target `string` (or `Pattern`).
  - `pattern` / `text`: The pattern (or text) to extract from.
- **Return Value**: `[[string]]` — An array of arrays containing extracted atom values for each match.
- **Example**:
  ```vir
  let records = text.extract_all(plate)
  ```
- **Notes**: Each inner array contains the extracted atom values for one match instance.

#### 22.3.6. `replace`

- **Purpose**: Replaces the first matching substring with a replacement string.
- **Signature**:
  ```vir
  func replace(
      this: string,
      pattern: Pattern,
      replacement: string
  ): string
  func replace(
      this: Pattern,
      text: string,
      replacement: string
  ): string
  ```
- **Parameters**:
  - `this`: The target `string` (or `Pattern`).
  - `pattern` / `text`: The pattern (or text) to target.
  - `replacement`: The literal replacement text.
- **Return Value**: `string` — A new string with the first matched occurrence replaced.
- **Example**:
  ```vir
  let masked = text.replace(plate, "***")
  ```
- **Notes**: The replacement parameter is treated strictly as literal text.

#### 22.3.7. `replace_all`

- **Purpose**: Replaces all non-overlapping matching substrings with a replacement string.
- **Signature**:
  ```vir
  func replace_all(
      this: string,
      pattern: Pattern,
      replacement: string
  ): string
  func replace_all(
      this: Pattern,
      text: string,
      replacement: string
  ): string
  ```
- **Parameters**:
  - `this`: The target `string` (or `Pattern`).
  - `pattern` / `text`: The pattern (or text) to target.
  - `replacement`: The literal replacement text.
- **Return Value**: `string` — A new string with all matched occurrences replaced.
- **Example**:
  ```vir
  let clean_text = text.replace_all(pattern, "REDACTED")
  ```
- **Notes**: If no matches are found, returns the original string unmodified.

#### 22.3.8. `split`

- **Purpose**: Splits text into substrings using the pattern as a delimiter.
- **Signature**:
  ```vir
  func split(this: string, pattern: Pattern): [string]
  func split(this: Pattern, text: string): [string]
  ```
- **Parameters**:
  - `this`: The target `string` (or `Pattern`).
  - `pattern` / `text`: The delimiter pattern.
- **Return Value**: `[string]` — An array of substrings separated by pattern matches.
- **Example**:
  ```vir
  let parts = text.split(virgex.compile("-"))
  ```
- **Notes**: Delimiter matches are omitted from the returned array.

#### 22.3.9. `tokenize`

- **Purpose**: Splits text into tokens, preserving matched pattern occurrences as distinct elements in the output sequence.
- **Signature**:
  ```vir
  func tokenize(this: string, pattern: Pattern): [string]
  func tokenize(this: Pattern, text: string): [string]
  ```
- **Parameters**:
  - `this`: The target `string` (or `Pattern`).
  - `pattern` / `text`: The tokenizing pattern.
- **Return Value**: `[string]` — An array of alternating structural and matched tokens.
- **Example**:
  ```vir
  let tokens = text.tokenize(virgex.compile("@0!1~"))
  ```
- **Notes**: Ideal for lexer implementations where delimiter tokens must be retained in the token stream.

#### 22.3.10. `iter`

- **Purpose**: Creates a lazy iterator over match occurrences in the text.
- **Signature**:
  ```vir
  func iter(this: string, pattern: Pattern): Iterator
  func iter(this: Pattern, text: string): Iterator
  ```
- **Parameters**:
  - `this`: The target `string` (or `Pattern`).
  - `pattern` / `text`: The pattern to iterate over.
- **Return Value**: `Iterator` — A lazy iterator producing match results sequentially.
- **Example**:
  ```vir
  var it = text.iter(pattern)
  ```
- **Notes**: Enables memory-efficient streaming over large files without loading all matches into memory at once.

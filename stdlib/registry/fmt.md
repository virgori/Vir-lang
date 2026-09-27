---
module: fmt
title: Fmt
summary: Runtime dynamic $ templates — not native source interpolation.
source:
  - name: fmt
    path: vir/fmt/fmt.vri
status: closed
notes: >-
  $ grammar aligned with Vir native interpolation; no {} and no new compiler
  syntax. fmt.format → Result(string). printf/printfln planned under fmt. Float specs
  wait format.float stable. Docs-only; verify $$ escape vs compiler before
  marking source-literal examples stable. No .vri until map applied.
---

# Fmt

Apply a **runtime** template string to argument values.

| Layer | Role |
|---|---|
| Native interpolation | Compiler expands `$name` / `$(expr)` / `$$` in **source** literals |
| [`format`](format.md) | One value → string (specific rendering) |
| [`parse`](parse.md) | String → value (`Result(T)`) |
| **`fmt`** | Dynamic template + args at **runtime** |
| [`builder`](builder.md) | Efficient append |
| [`io`](io.md) | Transport / console |

**No second native interpolation mechanism.** No lexer/parser extension for `fmt`.
Templates from files, config, or translations are passed **directly** to
`fmt.format` (already plain `$…` text).

## Boundary

| In `fmt` | Not in `fmt` |
|---|---|
| Runtime `$` / `$(…)` placeholders | Source-literal native interpolation |
| `FmtArg` wrappers + `format` → `Result(string)` | `{}` / printf `%` grammars |
| Planned `printf` / `printfln` (same `$` grammar) | Overloading [`io.print`](io.md) |
| Specs `d/x/X/b/o/s` + align/pad | Stable `f` until float gate |
| | Named args, auto-increment `{}`, dynamic width, custom formatters |

## Template grammar (closed)

Explicit **positional** indexes from `0`. No auto-increment placeholders.

```text
$0              # argument 0
$1              # argument 1
$(0:d)          # decimal
$(0:x)          # hexadecimal lowercase
$(0:X)          # hexadecimal uppercase
$(0:b)          # binary
$(0:o)          # octal
$(0:s)          # string
$(0:>8)         # right align, width 8
$(0:<8)         # left align, width 8
$(0:^8)         # center align, width 8
$(0:0>8d)       # decimal, zero fill, width 8
$$              # literal dollar sign
```

| Spec | Role |
|---|---|
| `d` / `x` / `X` / `b` / `o` / `s` | First-wave contract |
| `f` | **planned** with [`format.float`](format.md) |
| Integer radix specs | Digits only — **no** auto `0x`/`0b`/`0o` (unlike `format.hex`) |
| Width / align | Unicode **codepoints** — same as [`format.pad*`](format.md) |

Reuse of the same positional index in one template is **valid**.

## Native interpolation vs `fmt` (closed)

Compiler owns source literals; `fmt` owns runtime templates. They must not
accidentally consume each other’s placeholders.

When the template is a **source string literal**, native interpolation runs
first. Spec uses `$$` → literal `$` ([Vir spec §12](../../docs/vir_language_spec_v2.0_en.md)):

```vir
# After native expand, fmt sees: Name: $0 | Hex: $(1:x)
fmt.format("Name: $$0 | Hex: $$(1:x)", args)
```

Dynamic template (file / config) — no native pass:

```vir
fmt.format(template, args)   # template already contains $0 / $(1:x)
```

Document source-literal examples as **stable** only after confirming the live
compiler escape rule. **Do not** change native interpolation syntax for `fmt`.

## Public surface (closed)

```text
fmt
├── int
├── str
├── bool
├── format
│
├── float      # planned
├── printf     # planned
└── printfln   # planned
```

```vir
fmt.int(n) -> FmtArg
fmt.str(s) -> FmtArg
fmt.bool(value) -> FmtArg

fmt.format(template, args) -> Result(string)
```

`printf` / `printfln`: same `$` grammar as `format`; write to stdout. Belong to
**`fmt`**, not `io.print` overloads. **No** C `%` syntax.

## Errors (closed)

| Situation | Behavior |
|---|---|
| Missing argument | `Err` |
| Extra unreferenced argument | `Err` |
| Type mismatch | `Err` |
| Bad placeholder syntax | `Err` |
| Unsupported spec | `Err` |
| Same index reused | OK |

Use [`ErrorKind.InvalidData`](error.md) with message context and **byte offset**
into the template. Do **not** invent `FmtError` / new `ErrorKind` in this pass.

## Migration map

| Current | Public | Action |
|---|---|---|
| `format(template, args)` | `fmt.format` | **rename** · `{}` → `$` grammar · `Result` |
| `fmt_int` / `fmt_str` / `fmt_bool` | `fmt.int` / `str` / `bool` | **rename** |
| `fmt_float` | `fmt.float` | **planned** |
| `format1` / `format2` / `format3` | — | temp compatibility · not primary |
| `printf` / `printfln` | `fmt.printf` / `fmt.printfln` | **planned** · `$` grammar |
| `{}` / `{:x}` style | — | **remove** from public contract |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `fmt.FmtArg` | `FmtArg` | type | proposed |
| `fmt.int` | `fmt.int` | `fmt.int(n: int) -> FmtArg` | proposed |
| `fmt.str` | `fmt.str` | `fmt.str(s: string) -> FmtArg` | proposed |
| `fmt.bool` | `fmt.bool` | `fmt.bool(value: bool) -> FmtArg` | proposed |
| `fmt.format` | `fmt.format` | `fmt.format(template: string, args: Vec(FmtArg)) -> Result(string)` | proposed |
| `fmt.float` | `fmt.float` | `fmt.float(value: float) -> FmtArg` | planned |
| `fmt.printf` | `fmt.printf` | `fmt.printf(template: string, args: Vec)` | planned |
| `fmt.printfln` | `fmt.printfln` | `fmt.printfln(template: string, args: Vec)` | planned |

---

<a id="fmt.format"></a>
## `fmt.format`

```vir
fmt.format(template: string, args: Vec(FmtArg)) -> Result(string)
```

Render `template` with positional `$` placeholders. Strict arg count / types.

### Status

`proposed` — **present** with `{}` grammar — must migrate to `$` + `Result`.

### See also

- [`format`](format.md) · [`io.print`](io.md) · native `$` in language spec

---

<a id="fmt.int"></a>
## `fmt.int` / `fmt.str` / `fmt.bool`

```vir
fmt.int(n: int) -> FmtArg
fmt.str(s: string) -> FmtArg
fmt.bool(value: bool) -> FmtArg
```

### Status

`proposed`.

---

<a id="fmt.printf"></a>
## `fmt.printf` / `fmt.printfln` *(planned)*

Same grammar as `fmt.format`; output to stdout. Not `io.print` overloads.

### Status

`planned`.

---

## Implementation readiness

1. Replace `{}` engine with `$` grammar; return `Result` + `InvalidData`.
2. Align integer specs with [`format.intRadix`](format.md) (no prefix).
3. Gate float on F1–F6 in [`parse.md`](parse.md) / [`format.md`](format.md).
4. Confirm `$$` vs native before stabilizing source-literal examples.

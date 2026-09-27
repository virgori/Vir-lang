---
module: cli
title: CLI
summary: Interactive terminal prompts — convenience facades and advanced Prompt entities.
source:
  - name: term.prompt
    path: vir/term/prompt.vri
  - name: stdio
    path: vir/io/stdio.vri
  - name: cli.args
    path: vir/cli/args.vri
  - name: cli.shlex
    path: vir/cli/shlex.vri
status: draft
notes: >-
  Final contract for ask/confirm/choose/password/multi. password: echo-off
  required; no cleartext fallback if no TTY / cannot disable echo → error;
  restore terminal on success/failure. Prompt entities retained as advanced API.
---

# CLI

Interactive terminal prompts. Stream I/O → [`io.md`](io.md); files → [`fs.md`](fs.md);
formatting → `format`.

## Boundary

| In `cli` | Out |
|---|---|
| `ask` / `confirm` / `choose` / `password` / `multi` | `io.print` / `io.readLine` / stdin·stdout·stderr |
| Prompt entities (`TextPrompt`, …) | `fs.*` |
| (later) `cli.args` / `cli.shlex` | `format.*` |

`args` and `shlex` stay in the future CLI namespace but are **outside this pass**.

## Two layers

| Convenience | Advanced (retain) |
|---|---|
| `cli.ask` | `TextPrompt` |
| `cli.confirm` | `ConfirmPrompt` |
| `cli.choose` | `SelectPrompt` |
| `cli.password` | `PasswordPrompt` |
| `cli.multi` | `MultiSelectPrompt` |

Facades = common case. Entities = configuration / rendering. **Do not merge or delete** the entities.

## Impl legend

| Impl | Meaning |
|---|---|
| **present** | In source under some name |
| **move** / **rename** | Exists; public home/name changes |
| **missing** | Facade not implemented yet |
| **incomplete** | Named/contract closed; behavior wrong or unsafe |
| **retain** | Keep as advanced API |

## Migration map

| Current | Public | Impl | Action |
|---|---|---|---|
| `input` | `cli.ask` | present (`stdio`) | **move** + rename |
| `read_line_secret` | `cli.password` | present (same as `readln`) | **move** + **replace impl** (echo off) |
| `TextPrompt` / `text_prompt_*` | `TextPrompt` + `cli.ask` | present | **retain** + facade |
| `ConfirmPrompt` / `confirm_prompt_*` | `ConfirmPrompt` + `cli.confirm` | present (entity) | **retain** + facade (**missing**) |
| `SelectPrompt` / `select_prompt_*` | `SelectPrompt` + `cli.choose` | present (entity) | **retain** + facade (**missing**) |
| `PasswordPrompt` / `password_prompt_*` | `PasswordPrompt` + `cli.password` | render only | **retain** + complete secure input |
| `MultiSelectPrompt` / `multi_select_*` | `MultiSelectPrompt` + `cli.multi` | present (entity) | **retain** + facade (**missing**) |
| `argparser_*` | `cli.args` | present | later pass |
| `shlex_*` | `cli.shlex` | present | later pass |

## API

| ID | Symbol | Signature | Status | Impl |
|---|---|---|---|---|
| `cli.ask` | `cli.ask` | `cli.ask(prompt: string) -> string` | proposed | move |
| `cli.confirm` | `cli.confirm` | `cli.confirm(prompt: string) -> bool` | planned | missing facade |
| `cli.choose` | `cli.choose` | `cli.choose(prompt: string, options: Vec) -> int` | planned | missing facade |
| `cli.password` | `cli.password` | `cli.password(prompt: string) -> string` | incomplete | move + incomplete |
| `cli.multi` | `cli.multi` | `cli.multi(prompt: string, options: Vec) -> Vec` | planned | missing facade |

---

<a id="cli.ask"></a>
## `cli.ask`

<!--
id: cli.ask
api: cli.ask
previous: input
-->

```vir
cli.ask(prompt: string) -> string
```

Shows `prompt`, reads one line from stdin, applies the same line-ending strip
rules as `io.readLine`.

### Parameters

#### `prompt: string`

Text shown before waiting. Does **not** auto-append a newline.

### Returns

`string` — user-entered text (no trailing LF / stripped CR as per `io.readLine`).

### Errors

None as `Result` today (same as current `input`).

### Example

```vir
let name = cli.ask("name: ")
io.println(name)
```

### See also

- `io.readLine`
- `cli.password`
- `TextPrompt`

### Notes

**present** as `input` → **move** + rename.

---

<a id="cli.confirm"></a>
## `cli.confirm`

<!--
id: cli.confirm
api: cli.confirm
-->

```vir
cli.confirm(prompt: string) -> bool
```

Yes/no question. Case-insensitive. Leading/trailing whitespace trimmed before
compare. **Empty input → re-ask** (not true/false). Other tokens → re-ask.
No locale-specific yes/no.

### Accepted input

| Result | Tokens (after trim; case-insensitive) |
|---|---|
| `true` | `y`, `yes` |
| `false` | `n`, `no` |

Examples of valid `true`: `y`, `Y`, `yes`, `Yes`, `YES`.  
Examples of valid `false`: `n`, `N`, `no`, `No`, `NO`.

### Parameters

#### `prompt: string`

Question text.

### Returns

`bool`

### Errors

None as `Result` in the basic contract (loops until accepted).

### Example

```vir
if cli.confirm("Continue?") do
    io.println("ok")
end
```

### See also

- `cli.ask`
- `ConfirmPrompt`

### Notes

Facade **missing**; `ConfirmPrompt` **retain**.

---

<a id="cli.choose"></a>
## `cli.choose`

<!--
id: cli.choose
api: cli.choose
-->

```vir
cli.choose(prompt: string, options: Vec) -> int
```

Single-select from a list of **string** options. Returns a **0-based index**
(same indexing as collections) — not the option string — so identity is preserved
without copy/stringify of the selected value.

### Parameters

#### `prompt: string`

Title / question.

#### `options: Vec`

List of `string` choices. Must not be empty (cannot complete with empty list).

### Returns

`int` — selected index (`0 … len-1`).

### Behavior

- Exactly one item active at a time.
- Enter confirms.
- Navigation owned by prompt implementation.
- No implicit cancel in the basic contract.

### Errors

Empty `options`: must not complete (exact signal TBD: panic / `throw` / loop — facade must refuse empty).

### Example

```vir
let colors = ["Red", "Green", "Blue"]
let selected = cli.choose("Color?", colors)
io.println(colors[selected])
```

### See also

- `cli.multi`
- `SelectPrompt`

### Notes

Facade **missing**; `SelectPrompt` **retain**. Return type **`int` index** is closed.

---

<a id="cli.password"></a>
## `cli.password`

<!--
id: cli.password
api: cli.password
previous: read_line_secret
-->

```vir
cli.password(prompt: string) -> string
```

Shows `prompt` and reads a secret from the terminal.

### Required behavior

- Terminal echo **disabled** before read.
- Real input must not appear on the terminal.
- Echo state **always restored** on function exit (success and abnormal).
- Prefer Vir cleanup:

```vir
disable_echo()
ensure restore_echo()
```

- Line ending is not part of the returned string (same strip rules as `io.readLine`).

### Parameters

#### `prompt: string`

Prompt text.

### Returns

`string` — secret text.

### Errors

If there is no TTY, or echo cannot be disabled → **error** (recoverable
`Result` / structured failure when the public signature is migrated). **Never**
fall back to cleartext / echoed input.

### Example

```vir
let secret = cli.password("token: ")
```

### See also

- `cli.ask`
- `PasswordPrompt`

### Notes

**Contract locked:** echo off; restore terminal when the runtime can control it
(success and failure); no unsafe fallback. Today’s `read_line_secret` ==
`readln` is non-conforming. `PasswordPrompt` mask rendering alone is not enough.

---

<a id="cli.multi"></a>
## `cli.multi`

<!--
id: cli.multi
api: cli.multi
-->

```vir
cli.multi(prompt: string, options: Vec) -> Vec
```

Multi-select over string options. Returns a `Vec` of **0-based indices**.

### Parameters

#### `prompt: string`

Title / question.

#### `options: Vec`

List of `string` choices.

### Returns

`Vec` of `int` indices:

- 0-based
- no duplicates
- ordered by appearance in `options` (not by toggle order)

### Behavior

- Zero selections allowed.
- Empty `options` → empty selection (valid).
- Toggle does not end the prompt; explicit confirm finishes.
- No implicit cancel in the basic contract.

### Errors

None as `Result` in the basic contract.

### Example

```vir
let tags = ["Vir", "Compiler", "Runtime"]
let selected = cli.multi("Tags?", tags)
for index in selected
    io.println(tags[index])
end
```

### See also

- `cli.choose`
- `MultiSelectPrompt`

### Notes

Facade **missing**; entity **retain**. Return = index `Vec` is closed.

---

## Prompt entities (advanced)

Kept; not merged away:

```text
TextPrompt
ConfirmPrompt
SelectPrompt
PasswordPrompt
MultiSelectPrompt
```

Document method-level advanced APIs in a later pass if needed. Facades above are
the teaching / common surface.

## Summary

| API | Contract closed | Impl |
|---|---|---|
| `cli.ask` | yes → `string` | move from `input` |
| `cli.confirm` | yes → `bool`; y/yes · n/no; re-ask else | facade missing |
| `cli.choose` | yes → `int` index | facade missing |
| `cli.password` | yes → `string` + echo off/`ensure` | **incomplete** |
| `cli.multi` | yes → `Vec` of indices | facade missing |
| Prompt entities | retain advanced | present |
| `cli.args` / `cli.shlex` | later pass | present under old names |

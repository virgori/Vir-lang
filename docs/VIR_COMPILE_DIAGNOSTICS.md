# Vir Compile Diagnostics — CLI Presentation (Errors & Success)

*Version 0.2 — August 26, 2026*  
*Scope: **stderr/stdout on compile** via `core/build/vir` — errors, warnings, and **success notification**.*

---

## 1. Overview

Vir has **two layers** for compile-time diagnostics:

| Layer | Files | Role |
|-------|-------|------|
| **Diagnostic engine** | `core/src/diagnostic.c`, `core/include/diagnostic.h` | Collect structured issues (codes, spans, analysis, causes, fixes); render terminal / JSON |
| **CLI driver** | `core/src/main.c` | Run lexer → parser → lower → VM; **print messages to stderr** |

**Current state:**

- **Errors:** engine supports **EXECUTION REPORT** / JSON, but `main.c` still **disables** `diag_render_all()` (`if (0)`) → legacy one-line `fprintf`.
- **Success:** no congratulations banner yet; `-v` only prints `[vir] module…` / `result = …`.

---

## 2. CLI behavior today (what actually runs)

Compile failures print **one line** (or a few debug lines) on **stderr**:

| Phase | Message pattern | Example |
|-------|-----------------|---------|
| Lexer | `lexer error: %s` | `lexer error: Unterminated string literal` |
| Parser | `parse error in %s (line %u): %s` | `parse error in foo.vri (line 3): unexpected token` |
| Include | `include error: %s` | `include error: cannot open bar.vri` |
| IR lower | `lower error: %s` | `lower error: [Line 42] unknown identifier` |
| Borrow check | `borrow error: %s` | `borrow error: use after move` |
| WASM build | `wasm codegen error` / `cannot write %s` | (build path) |

**Runtime** (compile OK, VM fails):

```
runtime error: ERR_BAD_JUMP_TARGET
[vir] VM status: ERR_BAD_JUMP_TARGET  (12345 instrs)   # with -v
```

No `.vri` file in message, no stack trace, no `E1001` code.

### Why EXECUTION REPORT does not appear

```c
/* main.c — repeated on parser / include / lower / build paths */
if (0) {
    diag_render_all(&g_parser_diag);
} else {
    fprintf(stderr, "parse error in %s (line %u): %s\n",
            filepath, parser.error_line, parser.error);
}
```

The parser **still writes** structured entries to `g_parser_diag`:

```c
/* parser.c */
diag_error(&g_parser_diag, DCAT_SYNTAX, PHASE_PARSER, E1001, span, msg);
diag_add_cause(...);
diag_add_action(...);
```

Rich data lives in the context; the CLI only prints `parser.error`.

### Related CLI flags

| Flag | Current effect |
|------|----------------|
| `-v` | Verbose: token count, AST size, VM status |
| `--debug` | Sets `VIR_DEBUG_COMPILER=1` |
| `--json` | Sets `g_parser_diag.format = DIAG_FMT_JSON` — **does not change** the `fprintf` error path |
| `--report=E1001` | Sets `report_code` — only effective when `diag_render_all()` is called |
| `VIR_TRACE_STAGE1=1` | Phase timing log to file (not a user-facing banner) |

**On successful compile today:** silent (exit 0), or with `-v`:

```
[vir] module 'main': 42 functions
[vir] result = 0
```

No congratulations line, no total time, no notice count.

---

## 3. Designed format — Terminal

When `diag_render_all()` runs with `DIAG_FMT_TERMINAL` (default in `diag_init`).

### 3.1 Single error — full report

```
═══════════════════════════════════════════════
EXECUTION REPORT
═══════════════════════════════════════════════

Result      : FAILED          # or WARNING / FATAL / INTERNAL ERROR (ICE)
Code        : [E1001] Parser  # prefix E/W/F/I + 4 digits + phase
Subsystem   : Compiler
Stage       : Stage 0 (C Core)

Location
───────────────────────────────────────────────
File        : path/to/file.vri
Line        : 42

Source
───────────────────────────────────────────────
    <source line at line 42>

Related Locations          # optional
───────────────────────────────────────────────
• label (File: other.vri, Line: 10)
  <snippet>

Analysis
───────────────────────────────────────────────
<detailed message or summary>

Possible Causes            # optional, bullet list
───────────────────────────────────────────────
• ...

Action                     # optional: actions + quick fixes
───────────────────────────────────────────────
• ...
• fix message

═══════════════════════════════════════════════
```

**ICE** (`DIAG_ICE`): header `INTERNAL COMPILER ERROR`, Recommendation block (file issue, `--dump-ast`).

### 3.2 Multiple errors

| Error count (error+fatal) | Behavior |
|---------------------------|----------|
| `0` | No error EXECUTION REPORT → see **§ 3.4 COMPILE SUCCESS** |
| `1` | Full EXECUTION REPORT for that error |
| `2–10` | Summary header (`Status: FAILED`, counts) + full block per error |
| `>10` | Summary + **10 compact lines** + `(+N more errors)` |

Compact line (multi-error summary):

```
[E1001] line 42    unexpected token 'foo'
```

Footer:

```
Run:
    vir build --report <ErrorCode>
for detailed diagnostics.
```

*(Help mentions `vir build --report`; the driver accepts the flag on any subcommand that parses options.)*

### 3.3 Plain one-liner (`DIAG_FMT_PLAIN`)

```
[FAIL] E1001 foo.vri:42: unexpected token
[WARN] W2001 foo.vri:10: ...
```

### 3.4 COMPILE SUCCESS — successful compile (target)

Printed when the compile pipeline **finishes** and:

```text
error_count + fatal_count + ice_count == 0
```

(i.e. no `DIAG_ERROR`, `DIAG_FATAL`, or `DIAG_ICE` in `g_parser_diag`).

**When to print:** after the last *compile* phase (borrow check / lower done), **before** VM execution (`vir run`) or writing artifacts (`vir build`). Parse-only commands (`vir tokens`) may use a shortened variant.

#### Terminal (`DIAG_FMT_TERMINAL`)

```
═══════════════════════════════════════════════
COMPILE SUCCESS
═══════════════════════════════════════════════

Congratulations — compiled successfully with 0 errors.

Errors     : 0
Notices    : 3          ← warning_count + note_count (see below)
Time       : 847 ms     ← wall-clock compile (lexer → borrow/lower done)

═══════════════════════════════════════════════
```

**Field definitions:**

| Field | Source | Notes |
|-------|--------|-------|
| **Errors** | `error_count + fatal_count` | Must be `0` to show this banner |
| **Notices** | `warning_count + note_count` | Warnings (`DIAG_WARNING`) + notes (`DIAG_NOTE`, `DIAG_HELP`, `DIAG_SUGGEST` if emitted) |
| **Time** | `trace_now_ms()` | From entry-file compile start through borrow/lower; display ms; ≥1000 ms may show as `1.23 s` |

Terminal colors: title / “Congratulations” **green** (`ANSI_GREEN`); `Errors : 0` green; `Notices : N` yellow if `N > 0`, dim if `N == 0`.

If `Notices > 0`, optional hint:

```
Run: vir run --report=W2001 <file>   # details for a specific notice
```

(or list up to 5 compact lines `[Wxxxx] line …` — implementation choice).

#### Plain (`DIAG_FMT_PLAIN`)

```
[OK] Compile succeeded — 0 errors, 3 notices, 847 ms
```

#### JSON (`DIAG_FMT_JSON`)

Separate object (not inside the error diagnostic array), printed **after** an empty array or after warning entries:

```json
{
  "schema_version": 1,
  "kind": "compile_success",
  "message": "Congratulations — compiled successfully with 0 errors.",
  "errors": 0,
  "notices": 3,
  "warnings": 2,
  "notes": 1,
  "elapsed_ms": 847,
  "entry_file": "foo.vri",
  "functions": 42,
  "instructions_emitted": 12000
}
```

`notices` = `warnings + notes` (aggregate for tooling); `warnings` / `notes` split for filtering.

#### Interaction with `-v`

| Mode | Success output |
|------|----------------|
| Default | § 3.4 banner (short) |
| `-v` | Banner + technical details (`N functions`, `N instrs`, VM result on `run`) |

Success banner **does not replace** runtime errors (`runtime error: ERR_*`) — VM failure after a clean compile still prints separately.

#### Proposed API (C)

```c
void diag_render_compile_success(diag_context_t *ctx,
                                 uint64_t elapsed_ms,
                                 const char *entry_file,
                                 uint32_t function_count,
                                 uint64_t instructions_emitted);
```

Call from `main.c` when `!diag_has_errors(ctx)` after borrow/lower.

---

## 4. Designed format — JSON (errors)

Enable via `diag_init(..., DIAG_FMT_JSON)` or `./core/build/vir ... --json` **and** calling `diag_render_all()`.

Output: **JSON array** of objects (or single object + newline when rendering one entry).

### 4.1 Schema (one diagnostic)

```json
{
  "schema_version": 1,
  "severity": "error",
  "code": 1001,
  "category": 0,
  "phase": "Parser",
  "stage": "Stage 0 (C Core)",
  "summary": "unexpected token",
  "detail": "",
  "analysis": "",
  "causes": ["Unexpected token in current context"],
  "actions": ["Check syntax and spelling"],
  "primary_span": {
    "file": "foo.vri",
    "start_line": 42,
    "start_col": 5,
    "end_line": 42,
    "end_col": 12
  },
  "fixes": [
    { "message": "Insert ';'", "replacement": ";" }
  ],
  "recovery": { "token_index": 0, "sync_token_index": 0, "recovered": 0 },
  "ice": { "file": "parser.c", "line": 100, "func": "parse_expr" }
}
```

`recovery` / `ice` appear only when set on the entry.

### 4.2 Severity values

`fatal` | `error` | `warning` | `note` | `help` | `suggest` | `debug` | `ice`

### 4.3 Error code catalog

See `core/include/diagnostic.h` § Error Code Catalog:

| Prefix | Phase |
|--------|-------|
| `E0xxx` / `W0xxx` | Lexer |
| `E1xxx` / `W1xxx` | Parser |
| `E2xxx` / `W2xxx` | Semantic |
| `E3xxx` | IR lowering |
| `E8xxx` | Borrow checker |
| `E9xxx` | ICE |

Examples: `E0001` invalid character, `E0002` unterminated string, `E1001` parser syntax.

### 4.4 Success object

See § 3.4 — `kind: "compile_success"`, separate from the error diagnostic array.

---

## 5. Compile vs runtime

| | Compile diagnostic | Runtime VM error |
|--|-------------------|------------------|
| Engine | `diagnostic.c` | `vm.c` + `vm_status_str()` |
| Trigger | Lex / parse / lower / borrow | `vm_exec_module` status ≠ OK |
| CLI output | `parse error…` / `lower error…` (today) | `runtime error: ERR_*` |
| File:line | In engine; one-liner has line (parser only) | **No** |
| `--json` | Designed: error array + success object § 4.4 — not wired | No |

---

## 6. Wiring the CLI (target)

### 6.1 Errors — enable EXECUTION REPORT

```c
if (g_diag_initialized && g_parser_diag.count > 0 && diag_has_errors(&g_parser_diag)) {
    diag_render_all(&g_parser_diag);
} else if (parser.error[0] != '\0') {
    fprintf(stderr, "parse error in %s (line %u): %s\n", ...);  /* legacy fallback */
}
```

Lexer: if `g_parser_diag.count > 0` after tokenize → `diag_render_all`; else `lexer error`.

### 6.2 Success — enable COMPILE SUCCESS

After borrow/lower, before VM:

```c
if (g_diag_initialized && !diag_has_errors(&g_parser_diag)) {
    uint64_t elapsed = trace_now_ms() - compile_start_ms;
    diag_render_compile_success(&g_parser_diag, elapsed, filepath,
                                ctx->module.func_count,
                                module_instruction_count(&ctx->module));
}
```

Set `compile_start_ms` at the start of `load_and_parse` / `cmd_run`.

After wiring: `--json` emits `compile_success`; terminal prints congratulations + 0 errors + time + notices.

---

## 7. Related docs

| File | Content |
|------|---------|
| `core/include/diagnostic.h` | API, severity, catalog, JSON schema version |
| `core/src/diagnostic.c` | `render_terminal`, `diag_to_json`, `diag_render_all`; **TODO:** `diag_render_compile_success` |
| `core/src/main.c` | CLI commands, `if (0)` fallback, `--json` / `--report` |
| `core/src/parser.c`, `lexer.c`, `ir_lower.c` | `diag_error()` call sites |
| [`VIR_DEBUGGER_SPEC.md`](VIR_DEBUGGER_SPEC.md) | Runtime debug / DAP — **separate** from this doc |

---

*Reflects `core/` state 2026-08-26. COMPILE SUCCESS banner spec v0.2 — not yet implemented in `diagnostic.c` / `main.c`.*

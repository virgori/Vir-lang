---
module: process
title: Process
summary: Process lifecycle + subprocess — process.*; exit/abort; Command builder.
source:
  - name: process
    path: vir/process/process.vri
  - name: env
    path: vir/env.vri
    notes: exit/abort migrate from env public surface
status: closed
notes: >-
  Design closed P1–P6. Flat process.*; exit/abort here not env. shell deferred.
  Output stdout/stderr = Buffer. Result of (T); Child pipes = Reader/Writer.
  No ProcessError kind. Docs only — pipe lifecycle / platform kill / error map
  need impl audit before full stable.
---

# Process

**Sole** namespace for process lifecycle and subprocesses.

| Namespace | Role |
|---|---|
| **`process`** | This process (`exit`/`abort`) + child processes |
| [`env`](env.md) | Environment **variables** (+ argv / path helpers) |
| [`io`](io.md) | Byte streams / Reader / Writer |
| [`panic`](panic.md) | Non-recoverable abort helpers (logic/dev failure) |

```vir
let cmd = process.command("git")
process.args(cmd, ["status"])
process.stdout(cmd, Stdio.Pipe)
let child = process.spawn(cmd)    # Result of (Child)
# …
let status = process.wait(child)  # Result of (ExitStatus)
```

**Design closed ≠ full API stable** until pipe lifecycle, platform termination,
and OS error mapping are audited against implementation.

## Boundary

| In `process` | Not in `process` |
|---|---|
| `command` builder + spawn/wait/kill/output/status | [`env.get`](env.md) / set / remove |
| `exit` / `abort` (non-returning) | [`panic.fail`](panic.md) for logic bugs |
| Child `Reader`/`Writer` pipes | Public raw file descriptors |
| `Output` with `Buffer` stdout/stderr | Implicit shell / `shell(script)` **deferred** |
| | Nested `process.command.*` namespace |

No implicit shell execution — even if arguments contain `|`, `*`, or `$`.

## Architecture (closed)

```text
Command          # not yet running
   │
   ▼
process.spawn
   │
   ▼
Child
   ├── stdin  : Writer   (if Pipe)
   ├── stdout : Reader
   ├── stderr : Reader
   │
   ▼
process.wait
   │
   ▼
ExitStatus
```

- `spawn` does **not** wait.
- `wait` waits and reaps per OS.
- Pipes owned by `Child`; close via existing I/O contracts — **no** raw fd in core.
- `kill` requests termination; does **not** replace `wait` — caller must still reap.
- Do not re-`spawn` the same `Child`; new process ⇒ new `Command`.

## Types (closed)

```text
Stdio.Inherit | Stdio.Pipe | Stdio.Null

Output
  stdout : Buffer
  stderr : Buffer
  status : ExitStatus

ExitStatus
  code     # optional
  signal   # optional (platforms that support signal termination)
```

Non-zero exit **code** is **not** an API `Err`. `Result.Err` = spawn/wait/I/O/OS
failure. Program outcome lives in `ExitStatus`.

## Errors (closed)

Recoverable ops → `Result of (T)` with default [`Error`](error.md) (same family as `io`/`fs`).
Prefer [`IoError`](error.md) / `ErrorKind` already in registry for OS failures;
`InvalidData` for invalid configuration. **No** `ProcessError` / new `ErrorKind`
in this pass. Keep operation + OS errno in error context when available.

Do **not** use `Err(string)`.

## `exit` / `abort` (closed — P1)

```vir
process.exit(code)   # non-returning
process.abort()      # abnormal; no cleanup/flush guarantee
```

Moved **out** of [`env`](env.md) public surface. Not `Result`. Distinct from
[`panic.*`](panic.md) (invariant/dev failure messaging).

## Public surface (closed)

```text
process
├── command
├── arg
├── args
├── cwd
├── env
├── stdin
├── stdout
├── stderr
│
├── spawn
├── wait
├── kill
├── output
├── status
│
├── exit
└── abort
```

Optional convenience (not a separate primitive):

```text
process.run(program, args)   # thin wrapper over command+output if kept
```

**Deferred / not public core:** `shell(script)`.

## Stdio modes

```text
Stdio.Inherit
Stdio.Pipe
Stdio.Null
```

## `output` / `status` (closed)

`process.output`:

- Capture stdout + stderr as **`Buffer`** (binary-first — P3).
- Must collect both without deadlock when both pipes fill.
- Default: capture both streams; close stdin if no dedicated input.
- **No** UTF-8 decode; **no** trim.

`process.status`: wait for exit without capture. If pipes are configured
explicitly, caller must drain them (or use `spawn` and manage pipes) to avoid
blocking.

## Migration map

| Current | Public | Action |
|---|---|---|
| `command_new` | `process.command` | **rename** |
| `command_arg` / `args` / `cwd` / `env` | `process.arg` / … | **rename** |
| `command_stdin` / `stdout` / `stderr` | `process.stdin` / … | **rename** |
| `command_spawn` | `process.spawn` | **rename** · `Result of (Child)` |
| `child_wait` | `process.wait` | **rename** · `ExitStatus` |
| `child_kill` | `process.kill` | **rename** |
| `command_output` | `process.output` | **rename** · `Buffer` payloads |
| `command_status` | `process.status` | **rename** |
| `run` | `process.run` | optional convenience |
| `shell` | — | **deferred** · not public core |
| `env.exit` / free `exit` | `process.exit` | **move** |
| `env.abort` / free `abort` | `process.abort` | **move** |
| Child raw `*_fd` | `Reader` / `Writer` | **hide** fd · typed I/O |
| `Output` as `string` | `Buffer` | **change** |
| `Err(string)` | `Err(Error)` | **change** |

Flat names only — **no** `process.command.arg` nesting (P6).

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `process.Stdio` | `Stdio` | enum | proposed |
| `process.Command` | `Command` | type | proposed |
| `process.Child` | `Child` | type | proposed |
| `process.Output` | `Output` | type · Buffer streams | proposed |
| `process.ExitStatus` | `ExitStatus` | type | proposed |
| `process.command` | `process.command` | `process.command(program: string) -> Command` | proposed |
| `process.arg` | `process.arg` | `process.arg(cmd, value: string)` | proposed |
| `process.args` | `process.args` | `process.args(cmd, values: Vec)` | proposed |
| `process.cwd` | `process.cwd` | `process.cwd(cmd, path: string)` | proposed |
| `process.env` | `process.env` | `process.env(cmd, key, value: string)` | proposed |
| `process.stdin` | `process.stdin` | `process.stdin(cmd, mode: Stdio)` | proposed |
| `process.stdout` | `process.stdout` | `process.stdout(cmd, mode: Stdio)` | proposed |
| `process.stderr` | `process.stderr` | `process.stderr(cmd, mode: Stdio)` | proposed |
| `process.spawn` | `process.spawn` | `process.spawn(cmd) -> Result of (Child)` | proposed |
| `process.wait` | `process.wait` | `process.wait(child) -> Result of (ExitStatus)` | proposed |
| `process.kill` | `process.kill` | `process.kill(child) -> Result` · void success · bare `Result` (A) | proposed |
| `process.output` | `process.output` | `process.output(cmd) -> Result of (Output)` | proposed |
| `process.status` | `process.status` | `process.status(cmd) -> Result of (ExitStatus)` | proposed |
| `process.exit` | `process.exit` | `process.exit(code: int)` | proposed |
| `process.abort` | `process.abort` | `process.abort()` | proposed |

---

<a id="process.command"></a>
## Builder

```vir
process.command(program: string) -> Command
process.arg(cmd, value: string)
process.args(cmd, values: Vec)
process.cwd(cmd, path: string)
process.env(cmd, key: string, value: string)
process.stdin(cmd, mode: Stdio)
process.stdout(cmd, mode: Stdio)
process.stderr(cmd, mode: Stdio)
```

### Status

`proposed` — **present** as `command_*`.

---

<a id="process.spawn"></a>
## `process.spawn` / `wait` / `kill`

```vir
process.spawn(cmd) -> Result of (Child)
process.wait(child) -> Result of (ExitStatus)
process.kill(child) -> Result  # void success · bare Result (decision A)
```

### Status

`proposed` — fd→Reader/Writer and `ExitStatus` shape are design targets.

---

<a id="process.output"></a>
## `process.output` / `process.status`

```vir
process.output(cmd) -> Result of (Output)
process.status(cmd) -> Result of (ExitStatus)
```

### Status

`proposed` — deadlock-safe dual-pipe capture required for conforming `output`.

---

<a id="process.exit"></a>
## `process.exit` / `process.abort`

```vir
process.exit(code: int)
process.abort()
```

### Status

`proposed` — migrate from `env`.

### See also

- [`panic`](panic.md)
- [`env`](env.md) — variables only

---

## Implementation readiness

1. Flat `process.*`; move `exit`/`abort` from env public API.
2. `Buffer` output; typed Child pipes; `Result of (T)` (default `Error`).
3. Drop public `shell`; keep migration aliases briefly.
4. Audit pipe close, wait/kill, and errno→Error mapping before “stable”.

**Next:** core registry (option…json) design-closed. Open **csv** wave. No `.vri` / no PR.

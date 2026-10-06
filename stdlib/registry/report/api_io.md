# `io` (console) — danh sách tên hàm

Source console: `stdlib/vir/io/stdio.vri`  
Gọi registry-style: `include stdio` → global **`io`** (`IoNamespace`)  
Module name `io` trong `stdlib.vri` vẫn trỏ `rt/io.vri` (low-level / compiler) — remount blocked.

## Canonical (trên `io`)

| Tên | Chữ ký (rút gọn) | Ghi chú |
|---|---|---|
| `io.print` | `(s) -> void` | |
| `io.println` | `(s) -> void` | |
| `io.eprint` | `(s) -> void` | |
| `io.eprintln` | `(s) -> void` | |
| `io.readln` | `() -> string` | **không** dùng `readLine` |

## Free-function cùng hành vi (`stdio`)

| Tên | Tag |
|---|---|
| `print` / `println` | canonical free |
| `eprint` / `eprintln` | canonical free |
| `readln` | canonical free |
| `stdin_at_eof` | true after `readln` hit EOF with no bytes (Ctrl+D) |
| `print_str` / `print_ln` | alias |
| `eprint_str` / `eprint_ln` | alias |
| `readLine` / `read_line` | alias (sai hướng camelCase — chỉ migration) |
| `flush` / `flush_stdout` / `flush_stderr` | incomplete stub |
| `input` | migration → `cli.ask` |
| `read_line_secret` | migration → `cli.password` (echo-off incomplete) |
| `str_ptr` | internal/FFI: `string` → address via **`as ptr`** (spec §4.1) |
| `cstr_to_str` | ABI boundary: NUL C-string → soft `string` handle |
| `stdio_cstr` / `stdio_len` / `stdio_byte` | byte accessors for soft handles |
| `stdio_len_p` / `stdio_byte_p` | same on raw C address |

## Cast policy (spec)

- `string` → pointer: **`as ptr`** only (not `as i64`).
- Soft handle retype at ABI boundary: `cstr_to_str` (`p as string`) — temporary until literals are fat-boxed.
- Do **not** probe fat `{data,byte_len,char_len}` fields on arbitrary soft literals (SEGV).


## Planned (registry `io.md`, chưa có)

| Tên | Ghi chú |
|---|---|
| `io.stdin` / `io.stdout` / `io.stderr` | → Reader / Writer |
| `Reader.read` / `exact` / `atLeast` / `all` / `limit` / `until` / `line` / `byte` | traits |
| `Writer.write` / `flush` / `writeAll` | traits |
| `io.copy` / `chain` / `tee` | utilities |

## Low-level `rt/io` (không phải console public)

Module registry name hiện tại: `io` → `rt/io.vri`  
Ví dụ: `print_str`, `print_int`, `print_ln`, `read_line`, `file_open_*`, … — compiler / runtime, không liệt kê là API console.

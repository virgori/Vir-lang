# `cli` — danh sách tên hàm

Source: `stdlib/vir/cli.vri`  
Namespace: global `cli` (`CliNamespace`) · `include cli`  
(`cli.args` / `cli.shlex` vẫn là module riêng — chưa gộp wave này.)

## Canonical (trên `cli`)

| Tên | Chữ ký (rút gọn) | Ghi chú |
|---|---|---|
| `cli.ask` | `(prompt) -> string` | |
| `cli.confirm` | `(prompt) -> bool` | y/yes · n/no; re-ask |
| `cli.choose` | `(prompt, options) -> int` | index 0-based |
| `cli.password` | `(prompt) -> string` | echo-off via Darwin `TIOCGETA`/`TIOCSETA`; no-op if not a tty |
| `cli.multi` | `(prompt, options) -> Vec` | indices |

## Free exports (cùng tên)

| Tên |
|---|
| `ask` |
| `confirm` |
| `choose` |
| `password` |
| `multi` |

## Later / module khác

| Tên | Module |
|---|---|
| ArgParser / `cli.args` | `cli/args.vri` |
| `cli.shlex` | `cli/shlex.vri` |
| `TextPrompt` / `ConfirmPrompt` / … | `term/prompt.vri` (render) |

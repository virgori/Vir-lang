# `env` — danh sách tên hàm

Source: `stdlib/vir/env.vri`  
Namespace: global `env` (`EnvNamespace`) · `include env`

## Canonical (trên `env`)

| Tên | Chữ ký (rút gọn) | Ghi chú |
|---|---|---|
| `env.get` | `(key) -> Option(string)` | |
| `env.unwrapOr` | `(key, fallback) -> string` | SPEC ghi `env.or` — `or` là keyword Vir |
| `env.has` | `(key) -> bool` | |
| `env.set` | `(key, val) -> Result` | |
| `env.remove` | `(key) -> Result` | |
| `env.int` | `(key) -> Option(int)` | thiếu / parse fail → `None` |
| `env.bool` | `(key) -> Option(bool)` | thiếu / parse fail → `None` |
| `env.require` | `(key) -> Result(string)` | |
| `env.args` | `() -> …` | argv |
| `env.name` | `() -> string` | argv[0] |
| `env.cwd` | `() -> string` | |
| `env.home` | `() -> string` | |
| `env.temp` | `() -> string` | |

## Alias / surface rộng (vẫn trên `env`)

| Tên | Ghi chú |
|---|---|
| `env.get_or` | alias → `unwrapOr` |
| `env.str` / `env.string` | `(key, default) -> string` · chưa đóng trong registry surface |
| `env.keys` / `env.values` / `env.vars` / `env.count` / `env.clear` | inventory · không thuộc surface đóng |

## Free-function migration (export, ngoài `env.`)

| Tên | Ghi chú |
|---|---|
| `get` / `get_or` / `has` / `set` / `remove` | |
| `int` / `str` / `bool` | `(key, default)` — default-arg cũ |
| `require` / `args` / `cwd` | |
| `program_name` | → canonical `env.name` |
| `home_dir` | → canonical `env.home` |
| `temp_dir` | → canonical `env.temp` |
| `keys` / `values` / `count` / `clear` | |
| `exit` / `abort` / `panic` | registry: chuyển `process` |
| `current_os` / `current_arch` / `os_name` / `arch_name` | |
| `on_signal` / `ignore_signal` / `default_signal` | stub |
| `env_int` | helper internal/migration |

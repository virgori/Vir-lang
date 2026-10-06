# Report — `env`

Source: `stdlib/vir/env.vri` (sync `env/env.vri`)  
Registry: [`../env.md`](../env.md)

| API | Status | Notes |
|---|---|---|
| `env.get` | done | |
| `env.unwrapOr` | done | SPEC wrote `env.or` — illegal (`or` keyword); same shape as `option.unwrapOr` |
| `env.has` | done | |
| `env.set` | done | bare `Result` |
| `env.remove` | done | bare `Result` |
| `env.int` | done | → `Option of (int)`; free `int(key, default)` migration only |
| `env.bool` | done | → `Option of (bool)`; free `bool(key, default)` migration only |
| `env.require` | done | |
| `env.args` | done | method on `env` |
| `env.name` | done | previous: `program_name` free |
| `env.cwd` | done | |
| `env.home` | done | previous: `home_dir` |
| `env.temp` | done | previous: `temp_dir` |
| `env.exit` / `abort` | skip | stay on free/`process` (registry move) |
| free `get`/`set`/… | alias | keep for callers; not closed surface |

**Tests touched:** `tests/test_env_extensions.vri`, `tests/test_backend_sample.vri`

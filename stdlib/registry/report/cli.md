# Report — `cli`

Source: `stdlib/vir/cli.vri` (new) · registered `cli = cli.vri`  
Registry: [`../cli.md`](../cli.md)

| API | Status | Notes |
|---|---|---|
| `cli.ask` | done | wraps `print` + `readln` |
| `cli.confirm` | done | y/yes · n/no; re-ask else |
| `cli.choose` | done | numbered list → index |
| `cli.password` | **partial** | no echo-off / termios yet |
| `cli.multi` | done | comma-separated indices → `Vec` |
| `cli.args` / `cli.shlex` | skip | later pass (`cli.args` / `cli.shlex` modules) |
| Prompt entities | skip | remain in `term.prompt` |

**Usage:**

```vir
include cli
# cli.ask("Name: ")
```

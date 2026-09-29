# Report — `io`

Sources: `stdlib/vir/io/stdio.vri` (console) · `stdlib/vir/rt/io.vri` (low-level)  
Registry: [`../io.md`](../io.md)

| API | Status | Notes |
|---|---|---|
| Console `io.print` / `println` / `eprint` / `eprintln` / `readln` | done | via `include stdio` → global `io` (`IoNamespace`) |
| Free `print` / `readln` on `stdio` | alias | same impl |
| `io.stdin` / `stdout` / `stderr` → Reader/Writer | planned | |
| Reader.`exact` / `atLeast` / `until` / `line` | planned | traits |
| Writer.`writeAll` rename | planned | |
| Module remount `io` ← stdio | **blocked** | `stdlib.vri` `io` = `rt/io.vri` (compiler) |

**Call form (until remount):**

```vir
include stdio
io.println("ok")
io.readln()
```

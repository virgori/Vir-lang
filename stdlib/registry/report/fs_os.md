# Report — FS / path / process

**Registry:** [`../fs.md`](../fs.md) · [`../path.md`](../path.md) · [`../process.md`](../process.md)  
**Status:** design **closed**; compile **partial**

## Scope

| Module | Source | Notes |
|---|---|---|
| `fs` | `fs.vri` (+ `fs/fs.vri` dup) | Dedup debt |
| `path` | `path/path.vri` | Lexical + FS queries mixed |
| `process` | `process/process.vri` | Command/Child/Output |
| `os.*` | `os/mmap` `pipe` `signal` | **No** registry |

## Compile smoke

| Module | Result |
|---|---|
| `fs` | **OK** |
| `path` | FAIL E1001 |
| `process` | FAIL E1001 |

## Naming

```text
fs.read / fs.write / path.join / process.run
```

## Verdict

`fs` include works; path/process need parser cleanup before API remount. Deduplicate `fs.vri` vs `fs/fs.vri`. OS helpers deserve a later `os` / `process` adjacent registry wave.

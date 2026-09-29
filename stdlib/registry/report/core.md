# Report — Core (`option` / `result` / `error` / `panic` / `types`)

**Registry:** [`../option.md`](../option.md) · [`../result.md`](../result.md) · [`../error.md`](../error.md) · [`../panic.md`](../panic.md)  
**Status:** design **closed** (panic docs-only); `types` has **no** registry file

## Scope

| Module | Source | Notes |
|---|---|---|
| `option` | `core/option.vri` | |
| `result` | `core/result.vri` | Bare `Result` for void success (Decision A) |
| `error` | `error/error.vri` | Also hosts some panic helpers |
| `panic` | docs-only registry | Helpers live in `error` / `types` today |
| `types` | `core/types.vri` | No `registry/types.md`; `parse_int` debt → `parse` |
| `ops` / `bits` | `core/ops.vri` / `bits.vri` | No registry |

## Compile smoke

| Module | Result |
|---|---|
| `option` | **OK** |
| `result` | **OK** |
| `error` | FAIL — fat-string field access via `string` |
| `panic` | FAIL — E2102 unresolved include |

## Verdict

`option`/`result` are the healthiest core includes. Close `panic` remount + `error` string ABI before claiming usable diagnostics APIs. Add `types` registry when `parse.*` map lands.

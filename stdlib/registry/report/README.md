# Stdlib registry — implementation progress

Track how far `stdlib/vir/` matches `stdlib/registry/*.md` contracts.

## How to use

| File | Role |
|---|---|
| [`API.md`](API.md) | Index danh sách tên hàm (env / json / io / cli) |
| [`api_env.md`](api_env.md) | API `env` |
| [`api_json.md`](api_json.md) | API `json` |
| [`api_io.md`](api_io.md) | API `io` (console) |
| [`api_cli.md`](api_cli.md) | API `cli` |
| [`STATUS.md`](STATUS.md) | Wave rollup — done / blocked |
| [`env.md`](env.md) / [`json.md`](json.md) / [`io.md`](io.md) / [`cli.md`](cli.md) | Checklist trạng thái implement |

Status values (checklist):

| Tag | Meaning |
|---|---|
| `done` | Public name + contract shape in source |
| `alias` | New name present; old name kept for callers |
| `partial` | Present but incomplete (e.g. password echo still on) |
| `planned` | Registry-only; not in source yet |
| `blocked` | Needs remount / ABI / gate before finish |
| `skip` | Explicitly out of this wave |

Update the matching report file in the same change as the `.vri` edit.
Do not mark `stable` here — that stays a registry readiness claim.

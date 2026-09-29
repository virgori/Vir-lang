# Stdlib registry — implementation progress

Track how far `stdlib/vir/` matches `stdlib/registry/*.md` contracts.

## How to use

| File | Role |
|---|---|
| [`AUDIT.md`](AUDIT.md) | **Rollup audit** — remaining libraries + compile smoke |
| [`INVENTORY.md`](INVENTORY.md) | Dirs without registry SSOT |
| [`API.md`](API.md) | Index tên hàm wave env/json/io/cli |
| [`api_env.md`](api_env.md) / [`api_json.md`](api_json.md) / [`api_io.md`](api_io.md) / [`api_cli.md`](api_cli.md) | API lists |
| [`STATUS.md`](STATUS.md) | Wave rollup — done / blocked |
| [`env.md`](env.md) / [`json.md`](json.md) / [`io.md`](io.md) / [`cli.md`](cli.md) / [`crypto.md`](crypto.md) | Wave checklists |
| [`collections.md`](collections.md) · [`core.md`](core.md) · [`string_cluster.md`](string_cluster.md) · [`fs_os.md`](fs_os.md) · [`format_cluster.md`](format_cluster.md) · [`data.md`](data.md) · [`net.md`](net.md) · [`concurrency.md`](concurrency.md) · [`misc.md`](misc.md) | Cluster audits |

Status values (checklist):

| Tag | Meaning |
|---|---|
| `done` | Public name + contract shape in source |
| `alias` | New name present; old name kept for callers |
| `partial` | Present but incomplete |
| `planned` | Registry-only; not in source yet |
| `blocked` | Needs remount / ABI / gate before finish |
| `skip` | Explicitly out of this wave |

Update the matching report file in the same change as the `.vri` edit.
Do not mark `stable` here — that stays a registry readiness claim.

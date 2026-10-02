# Danh sách tên hàm — wave `env` / `json` / `io` / `cli`

Bảng tên **public** theo source hiện tại. Chi tiết từng module:

| Module | File |
|---|---|
| env | [`api_env.md`](api_env.md) |
| json | [`api_json.md`](api_json.md) |
| io (console / `stdio`) | [`api_io.md`](api_io.md) |
| cli | [`api_cli.md`](api_cli.md) |

Tiến độ implement: [`STATUS.md`](STATUS.md) · checklist: [`env.md`](env.md) / [`json.md`](json.md) / [`io.md`](io.md) / [`cli.md`](cli.md).

**Chú thích cột**

| Tag | Nghĩa |
|---|---|
| canonical | Tên public đúng contract / SPEC |
| alias | Tên cũ / tương thích, giữ tạm |
| migration | Free-function hoặc helper ngoài surface đóng |
| internal | Không phải API user-facing |
| incomplete | Có tên nhưng hành vi chưa đủ contract |

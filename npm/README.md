# vir-lang

**Vir** — Ngôn ngữ lập trình cú pháp tiếng Việt, JIT compilation, SIMD-accelerated native core.

## Cài đặt / Install

```bash
# npm
npm install -g vir-lang

# pnpm
pnpm add -g vir-lang

# yarn
yarn global add vir-lang
```

## Sử dụng / Usage

```bash
# Chạy file .vir
vir hello.vir

# REPL tương tác
vir --interactive

# Xem IR trung gian
vir --dump-ir hello.vir

# Khởi động server
viron --serve
```

## Ví dụ / Example

```vir
hàm chính() {
    in("Xin chào thế giới!")

    cho i = 1 đến 10 {
        nếu i % 2 == 0 {
            in(i, "là số chẵn")
        }
    }
}
```

## Yêu cầu hệ thống / Requirements

- **Node.js** >= 16 (for npm wrapper)
- **Python** >= 3.11 (for full runtime — fallback if native binary unavailable)

The npm package automatically downloads the correct native binary for your platform during install. If the binary is not available, it falls back to the Python-based CLI.

## Nền tảng hỗ trợ / Supported Platforms

| Platform        | Architecture | Status |
| --------------- | ------------ | ------ |
| macOS           | ARM64 (M1+)  | ✅      |
| macOS           | x86_64       | ✅      |
| Linux           | x86_64       | ✅      |
| Linux           | ARM64        | ✅      |
| Windows         | x86_64       | ✅      |
| Windows         | ARM64        | ✅      |

## Giấy phép / License

MIT

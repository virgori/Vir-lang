# vir-lang

**Vir** — Ngôn ngữ lập trình đa cú pháp (Multilingual Syntax Programming Language). Viết code bằng tiếng Việt, Trung, Nhật, Hàn, Anh — cùng biên dịch sang Q-IR và mã máy giống nhau. Tích hợp JIT, self-patching binary, SIMD-accelerated native core.

## Kiến trúc / Architecture

```
Layer 1: Multilingual Frontend  (N-Gram Tokenizer → Parser → AST)
Layer 2: Virtual Machine        (Q-IR with SSA form)
Layer 3: Self-Patching Backend  (x86_64/ARM64 codegen, Jump Table)
Layer 4: Runtime & Security     (JIT Engine, Binary Patcher, HMAC-SHA256)
```

## Cài đặt / Install

```bash
# npm
npm install -g vir-lang

# pnpm
pnpm add -g vir-lang

# yarn
yarn global add vir-lang

# pip (Python package)
pip install vir-lang
```

## Sử dụng / Usage

```bash
# Chạy file .vir
vir hello.vir

# REPL tương tác
vir --interactive

# Xem IR trung gian
vir --dump-ir hello.vir

# Xem mã máy
vir --dump-asm hello.vir

# Xuất binary .sri
vir --emit-sri output.sri hello.vir

# Khởi động server
viron --serve
```

## Cú pháp v1.2 / Syntax v1.2

```vir
# Hàm (function)
func add:
    in(a:int; b:int; result:int)
    result = a + b;
    out result;
end

# Cấu trúc dữ liệu (entity)
entity User:
    name:string;
    age:int;
end

method User.greet:
    print "Hello " + name;
end

# Điều kiện (conditions)
if x > 10:
    print x;
eif x > 5:
    print "medium";
else
    print "small";
end

# Vòng lặp (loop)
when x > 0 loop
    x = x - 1;
end

# Async task
async func fetchData:
    in(url:string)
    out data;
end
task result wait fetchData("https://api.example.com");

# Xử lý lỗi (error handling)
out divide(a, b) try 0 error DivisionError end
```

### Đa cú pháp / Multilingual — cùng 1 chương trình, 5 ngôn ngữ:

```
🇻🇳  Nếu máy rảnh, tính tổng A và B bằng thanh ghi.
🇨🇳  如果 机器空闲 加 A 和 B 用 寄存器
🇯🇵  もし CPU空き 足す A と B レジスタで
🇰🇷  만약 CPU여유 더하기 A 와 B 레지스터로
🇬🇧  if cpu_idle add A and B register
```

Tất cả biên dịch ra **cùng Q-IR và mã máy**.

## Virgex — Pattern Matching Engine

**Virgex** (Vir + Regex) thay thế regex truyền thống bằng **Vir Pattern Syntax (VPS)** — chỉ **8 ký hiệu cốt lõi**, dễ đọc hơn regex.

| Ký hiệu | Ý nghĩa | Ví dụ | Regex tương đương |
| -------- | -------- | ----- | ----------------- |
| `@` | Atom (lớp ký tự) | `@Az` | `[A-Za-z]` |
| `!` | Lặp (postfix) | `@0!3` | `[0-9]{3}` |
| `~` | Phạm vi lặp | `@Az!2~5` | `[A-Za-z]{2,5}` |
| `?` | Tuỳ chọn (prefix) | `?@Az` | `[A-Za-z]?` |
| `:(` `:)` | Nhóm | `:(A \| B:)` | `(?:A\|B)` |
| `\|` | Anchor hoặc OR | `\| @0!3 \|` | `^[0-9]{3}$` |
| `$` | Escape | `$-` | literal `-` |
| `-` | Khoảng trắng | `@Az - @0` | `[A-Za-z] [0-9]` |

```python
import virgex

# Số điện thoại VN: 09x hoặc 03x, 10 chữ số
virgex.fullmatch("| :( 09 | 03 :) @0!8 |", "0912345678")  # ✅

# Username 3–12 ký tự
virgex.fullmatch("| @Az0!3~12 |", "user123")  # ✅

# Chuyển sang regex truyền thống
virgex.to_regex("@Az0!3~12")  # → ^[A-Za-z0-9]{3,12}$
```

## Thống kê / Stats

- **C/ASM native core**: ~9,900 LOC (27 sources + 27 headers)
- **Python compiler pipeline**: 26,840 LOC (152 modules)
- **Standard Library**: **233 modules** · 72,724 LOC `.vri` · 71 categories
- **Virgex engine**: ~1,400 LOC (Python) + 708 LOC (.vri)
- **GPU**: CUDA PTX + Apple Metal (10 kernel templates)
- **Tests**: **700/700 pass** ✅
- **Domains**: Server · IoT · AI · Kernel/OS · Network · Crypto

## Yêu cầu / Requirements

- **Node.js** >= 16 (for npm wrapper)
- **Python** >= 3.11 (for full runtime — fallback if native binary unavailable)

Gói npm tự động tải native binary đúng nền tảng khi cài đặt.

## Nền tảng hỗ trợ / Supported Platforms

| Platform | Architecture | Status |
| -------- | ------------ | ------ |
| macOS | ARM64 (M1+) | ✅ |
| macOS | x86_64 | ✅ |
| Linux | x86_64 | ✅ |
| Linux | ARM64 | ✅ |
| Windows | x86_64 | ✅ |
| Windows | ARM64 | ✅ |

## Giấy phép / License

MIT

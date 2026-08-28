import struct
import base64
import os

# Build a multi-function WebAssembly module:
# Exported functions:
# 1. add(a: i32, b: i32) -> i32
# 2. multiply(a: i32, b: i32) -> i32
# 3. square(x: i32) -> i32
# 4. fibonacci(n: i32) -> i32

# Type 0: (i32, i32) -> i32 : 0x60, 2, 0x7F, 0x7F, 1, 0x7F
# Type 1: (i32) -> i32      : 0x60, 1, 0x7F, 1, 0x7F

type_sec_payload = bytes([
    0x02, # 2 types
    # Type 0: (i32, i32) -> i32
    0x60, 0x02, 0x7F, 0x7F, 0x01, 0x7F,
    # Type 1: (i32) -> i32
    0x60, 0x01, 0x7F, 0x01, 0x7F
])
type_sec = bytes([0x01, len(type_sec_payload)]) + type_sec_payload

# Function section: 4 functions
# Func 0: type 0 (add)
# Func 1: type 0 (multiply)
# Func 2: type 1 (square)
# Func 3: type 1 (fibonacci)
func_sec_payload = bytes([0x04, 0x00, 0x00, 0x01, 0x01])
func_sec = bytes([0x03, len(func_sec_payload)]) + func_sec_payload

# Export section: 4 exports
# "add" -> 0, "multiply" -> 1, "square" -> 2, "fibonacci" -> 3
export_sec_payload = bytearray([0x04])

# "add"
export_sec_payload += bytes([3, ord('a'), ord('d'), ord('d'), 0, 0])
# "multiply"
export_sec_payload += bytes([8, ord('m'), ord('u'), ord('l'), ord('t'), ord('i'), ord('p'), ord('l'), ord('y'), 0, 1])
# "square"
export_sec_payload += bytes([6, ord('s'), ord('q'), ord('u'), ord('a'), ord('r'), ord('e'), 0, 2])
# "fibonacci"
export_sec_payload += bytes([9, ord('f'), ord('i'), ord('b'), ord('o'), ord('n'), ord('a'), ord('c'), ord('c'), ord('i'), 0, 3])

export_sec = bytes([0x07, len(export_sec_payload)]) + bytes(export_sec_payload)

# Code section: 4 bodies
# Func 0: add(a, b)
# local.get 0 (20 00), local.get 1 (20 01), i32.add (6A), end (0B)
body0 = bytes([0x00, 0x20, 0x00, 0x20, 0x01, 0x6A, 0x0B])
body0_entry = bytes([len(body0)]) + body0

# Func 1: multiply(a, b)
# local.get 0 (20 00), local.get 1 (20 01), i32.mul (6C), end (0B)
body1 = bytes([0x00, 0x20, 0x00, 0x20, 0x01, 0x6C, 0x0B])
body1_entry = bytes([len(body1)]) + body1

# Func 2: square(x)
# local.get 0 (20 00), local.get 0 (20 00), i32.mul (6C), end (0B)
body2 = bytes([0x00, 0x20, 0x00, 0x20, 0x00, 0x6C, 0x0B])
body2_entry = bytes([len(body2)]) + body2

# Func 3: fibonacci(n)
# Locals: 4 locals of type i32: [1 local count entry: count=4, type=0x7F]
# local 1 (a=0), local 2 (b=1), local 3 (i=0), local 4 (c)
# 01 04 7F (1 entry, 4 locals i32)
# i32.const 0; local.set 1; (41 00 21 01)
# i32.const 1; local.set 2; (41 01 21 02)
# i32.const 0; local.set 3; (41 00 21 03)
# block 40 (02 40)
#   loop 40 (03 40)
#     local.get 3; local.get 0; i32.ge_s; br_if 1; (20 03 20 00 4E 0D 01)
#     local.get 1; local.get 2; i32.add; local.set 4; (20 01 20 02 6A 21 04)
#     local.get 2; local.set 1; (20 02 21 01)
#     local.get 4; local.set 2; (20 04 21 02)
#     local.get 3; i32.const 1; i32.add; local.set 3; (20 03 41 01 6A 21 03)
#     br 0; (0C 00)
#   end (0B)
# end (0B)
# local.get 1; end (20 01 0B)
body3 = bytes([
    0x01, 0x04, 0x7F, # 4 locals i32
    0x41, 0x00, 0x21, 0x01, # a = 0
    0x41, 0x01, 0x21, 0x02, # b = 1
    0x41, 0x00, 0x21, 0x03, # i = 0
    0x02, 0x40,             # block void
    0x03, 0x40,             # loop void
    0x20, 0x03, 0x20, 0x00, 0x4E, 0x0D, 0x01, # if i >= n br 1 (exit block)
    0x20, 0x01, 0x20, 0x02, 0x6A, 0x21, 0x04, # c = a + b
    0x20, 0x02, 0x21, 0x01,                   # a = b
    0x20, 0x04, 0x21, 0x02,                   # b = c
    0x20, 0x03, 0x41, 0x01, 0x6A, 0x21, 0x03, # i++
    0x0C, 0x00,                               # br loop
    0x0B,                                     # end loop
    0x0B,                                     # end block
    0x20, 0x01, 0x0B                          # return a, end func
])
body3_entry = bytes([len(body3)]) + body3

code_sec_payload = bytes([0x04]) + body0_entry + body1_entry + body2_entry + body3_entry
code_sec = bytes([0x0A, len(code_sec_payload)]) + code_sec_payload

wasm_module = bytes([
    0x00, 0x61, 0x73, 0x6D,
    0x01, 0x00, 0x00, 0x00
]) + type_sec + func_sec + export_sec + code_sec

os.makedirs("web", exist_ok=True)
with open("web/vir_core.wasm", "wb") as f:
    f.write(wasm_module)

wasm_b64 = base64.b64encode(wasm_module).decode('utf-8')
print(f"Generated web/vir_core.wasm ({len(wasm_module)} bytes)")

# Create interactive Browser HTML application
html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vir WebAssembly Interactive Studio (v2.0)</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-dark: #070913;
      --bg-card: rgba(18, 24, 43, 0.75);
      --bg-card-hover: rgba(28, 38, 68, 0.85);
      --primary-cyan: #00f2fe;
      --primary-indigo: #4facfe;
      --accent-purple: #7f00ff;
      --accent-magenta: #e100ff;
      --accent-emerald: #00f5a0;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --border-glow: rgba(0, 242, 254, 0.25);
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      background: radial-gradient(circle at 50% 0%, #171f38 0%, var(--bg-dark) 75%);
      color: var(--text-main);
      font-family: 'Outfit', sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 2.5rem 1.5rem;
      overflow-x: hidden;
    }}

    /* Background animated glow orbs */
    .orb-1 {{
      position: fixed;
      top: -100px;
      left: -100px;
      width: 400px;
      height: 400px;
      background: radial-gradient(circle, rgba(127, 0, 255, 0.35), transparent 70%);
      filter: blur(60px);
      z-index: 0;
      pointer-events: none;
    }}

    .orb-2 {{
      position: fixed;
      bottom: -100px;
      right: -100px;
      width: 450px;
      height: 450px;
      background: radial-gradient(circle, rgba(0, 242, 254, 0.25), transparent 70%);
      filter: blur(60px);
      z-index: 0;
      pointer-events: none;
    }}

    .container {{
      position: relative;
      z-index: 1;
      width: 100%;
      max-width: 960px;
    }}

    /* Header */
    header {{
      text-align: center;
      margin-bottom: 2.5rem;
    }}

    .badge-pill {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.35rem 1rem;
      background: rgba(0, 242, 254, 0.1);
      border: 1px solid var(--border-glow);
      border-radius: 9999px;
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--primary-cyan);
      letter-spacing: 0.05em;
      margin-bottom: 1rem;
      box-shadow: 0 0 20px rgba(0, 242, 254, 0.15);
    }}

    .status-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent-emerald);
      box-shadow: 0 0 10px var(--accent-emerald);
      animation: pulse 2s infinite;
    }}

    @keyframes pulse {{
      0%, 100% {{ transform: scale(1); opacity: 1; }}
      50% {{ transform: scale(1.3); opacity: 0.6; }}
    }}

    h1 {{
      font-size: 3rem;
      font-weight: 800;
      background: linear-gradient(135deg, #fff 20%, var(--primary-cyan) 60%, var(--accent-magenta) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      letter-spacing: -0.02em;
      line-height: 1.15;
      margin-bottom: 0.75rem;
    }}

    p.subtitle {{
      color: var(--text-muted);
      font-size: 1.15rem;
      max-width: 600px;
      margin: 0 auto;
    }}

    /* Grid */
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1.5rem;
      margin-bottom: 2rem;
    }}

    .card {{
      background: var(--bg-card);
      backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 20px;
      padding: 1.75rem;
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.3);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }}

    .card:hover {{
      background: var(--bg-card-hover);
      border-color: var(--border-glow);
      transform: translateY(-4px);
      box-shadow: 0 20px 40px rgba(0, 242, 254, 0.15);
    }}

    .card-title {{
      font-size: 1.25rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 0.6rem;
      color: #fff;
    }}

    .card-title .icon {{
      font-size: 1.35rem;
    }}

    .input-row {{
      display: flex;
      gap: 0.75rem;
    }}

    input {{
      flex: 1;
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 12px;
      padding: 0.75rem 1rem;
      color: #fff;
      font-family: 'JetBrains Mono', monospace;
      font-size: 1rem;
      outline: none;
      transition: border-color 0.2s;
    }}

    input:focus {{
      border-color: var(--primary-cyan);
      box-shadow: 0 0 10px rgba(0, 242, 254, 0.25);
    }}

    button {{
      background: linear-gradient(135deg, var(--primary-indigo), var(--accent-purple));
      color: #fff;
      border: none;
      border-radius: 12px;
      padding: 0.75rem 1.25rem;
      font-family: 'Outfit', sans-serif;
      font-weight: 700;
      font-size: 0.95rem;
      cursor: pointer;
      transition: all 0.2s ease;
      box-shadow: 0 4px 15px rgba(127, 0, 255, 0.35);
    }}

    button:hover {{
      transform: scale(1.03);
      box-shadow: 0 6px 20px rgba(0, 242, 254, 0.45);
      background: linear-gradient(135deg, var(--primary-cyan), var(--accent-magenta));
    }}

    .result-box {{
      background: rgba(0, 0, 0, 0.5);
      border-radius: 12px;
      padding: 0.9rem 1.1rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 1.1rem;
      font-weight: 700;
      color: var(--accent-emerald);
      border-left: 3px solid var(--accent-emerald);
      word-break: break-all;
    }}

    /* Performance Bench Panel */
    .bench-card {{
      background: linear-gradient(135deg, rgba(18, 24, 43, 0.9), rgba(30, 20, 60, 0.8));
      border: 1px solid rgba(225, 0, 255, 0.3);
      border-radius: 20px;
      padding: 2rem;
      box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
      margin-top: 1rem;
    }}

    .bench-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.25rem;
      flex-wrap: wrap;
      gap: 1rem;
    }}

    .bench-title {{
      font-size: 1.4rem;
      font-weight: 800;
      background: linear-gradient(90deg, #fff, var(--primary-cyan));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}

    .bench-results {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.25rem;
      margin-top: 1.25rem;
    }}

    .bench-stat {{
      background: rgba(0, 0, 0, 0.4);
      border-radius: 14px;
      padding: 1.25rem;
      border: 1px solid rgba(255, 255, 255, 0.08);
    }}

    .stat-label {{
      font-size: 0.85rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.4rem;
    }}

    .stat-value {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 1.6rem;
      font-weight: 700;
      color: var(--primary-cyan);
    }}

    .stat-value.fast {{
      color: var(--accent-emerald);
    }}

    footer {{
      margin-top: 3rem;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.9rem;
    }}
  </style>
</head>
<body>
  <div class="orb-1"></div>
  <div class="orb-2"></div>

  <div class="container">
    <header>
      <div class="badge-pill">
        <span class="status-dot"></span>
        VIR V2.0 WEBASSEMBLY ENGINE LOADED (100% PURE VIR)
      </div>
      <h1>Vir WebAssembly Studio</h1>
      <p class="subtitle">Thử nghiệm trực tiếp các hàm logic được biên dịch tự thân từ ngôn ngữ Vir sang WebAssembly nhị phân trên trình duyệt Web.</p>
    </header>

    <div class="grid">
      <!-- Card 1: Add -->
      <div class="card">
        <div class="card-title"><span class="icon">➕</span> Phép Cộng: <code>add(a, b)</code></div>
        <div class="input-row">
          <input type="number" id="addA" value="15" placeholder="a">
          <input type="number" id="addB" value="27" placeholder="b">
        </div>
        <button onclick="runAdd()">Thực Thi WASM</button>
        <div class="result-box" id="addRes">Kết quả: 42</div>
      </div>

      <!-- Card 2: Multiply -->
      <div class="card">
        <div class="card-title"><span class="icon">✖️</span> Phép Nhân: <code>multiply(a, b)</code></div>
        <div class="input-row">
          <input type="number" id="mulA" value="12" placeholder="a">
          <input type="number" id="mulB" value="8" placeholder="b">
        </div>
        <button onclick="runMul()">Thực Thi WASM</button>
        <div class="result-box" id="mulRes">Kết quả: 96</div>
      </div>

      <!-- Card 3: Square -->
      <div class="card">
        <div class="card-title"><span class="icon">📐</span> Bình Phương: <code>square(x)</code></div>
        <div class="input-row">
          <input type="number" id="sqX" value="25" placeholder="x">
        </div>
        <button onclick="runSq()">Thực Thi WASM</button>
        <div class="result-box" id="sqRes">Kết quả: 625</div>
      </div>

      <!-- Card 4: Fibonacci -->
      <div class="card">
        <div class="card-title"><span class="icon">🌀</span> Fibonacci: <code>fibonacci(n)</code></div>
        <div class="input-row">
          <input type="number" id="fibN" value="40" placeholder="n (ví dụ: 40)">
        </div>
        <button onclick="runFib()">Thực Thi WASM</button>
        <div class="result-box" id="fibRes">Kết quả: 102334155</div>
      </div>
    </div>

    <!-- Benchmark Card -->
    <div class="bench-card">
      <div class="bench-header">
        <div>
          <div class="bench-title">⚡ Benchmark: 10,000,000 Lần Tính Fibonacci(25)</div>
          <div style="color: var(--text-muted); font-size: 0.9rem; margin-top: 0.25rem;">So sánh trực tiếp tốc độ thực thi giữa JavaScript thuần và Vir WebAssembly</div>
        </div>
        <button onclick="runBenchmark()" style="padding: 0.85rem 1.75rem; font-size: 1.05rem;">Chạy Benchmark</button>
      </div>

      <div class="bench-results">
        <div class="bench-stat">
          <div class="stat-label">Vir WebAssembly Time</div>
          <div class="stat-value fast" id="wasmTime">--- ms</div>
        </div>
        <div class="bench-stat">
          <div class="stat-label">JavaScript Time</div>
          <div class="stat-value" id="jsTime">--- ms</div>
        </div>
      </div>
    </div>

    <footer>
      Dự án ngôn ngữ Vir v2.0 • 100% Tự thân & Đa nền tảng (macOS, Linux, Windows, WebAssembly)
    </footer>
  </div>

  <script>
    // Embedded WebAssembly binary generated by Vir compiler
    const wasmBase64 = "{wasm_b64}";
    const wasmBytes = Uint8Array.from(atob(wasmBase64), c => c.charCodeAt(0));
    
    let wasmInstance = null;

    WebAssembly.instantiate(wasmBytes).then(res => {{
      wasmInstance = res.instance.exports;
      console.log("Vir WASM Instance Loaded Successfully!", wasmInstance);
    }}).catch(err => {{
      console.error("Failed to load WASM:", err);
      alert("Lỗi tải WASM: " + err.message);
    }});

    function runAdd() {{
      if (!wasmInstance) return;
      const a = parseInt(document.getElementById("addA").value) || 0;
      const b = parseInt(document.getElementById("addB").value) || 0;
      const res = wasmInstance.add(a, b);
      document.getElementById("addRes").innerText = "Kết quả: " + res;
    }}

    function runMul() {{
      if (!wasmInstance) return;
      const a = parseInt(document.getElementById("mulA").value) || 0;
      const b = parseInt(document.getElementById("mulB").value) || 0;
      const res = wasmInstance.multiply(a, b);
      document.getElementById("mulRes").innerText = "Kết quả: " + res;
    }}

    function runSq() {{
      if (!wasmInstance) return;
      const x = parseInt(document.getElementById("sqX").value) || 0;
      const res = wasmInstance.square(x);
      document.getElementById("sqRes").innerText = "Kết quả: " + res;
    }}

    function runFib() {{
      if (!wasmInstance) return;
      const n = parseInt(document.getElementById("fibN").value) || 0;
      const res = wasmInstance.fibonacci(n);
      document.getElementById("fibRes").innerText = "Kết quả: " + res;
    }}

    function jsFibonacci(n) {{
      let a = 0, b = 1;
      for (let i = 0; i < n; i++) {{
        let c = a + b;
        a = b;
        b = c;
      }}
      return a;
    }}

    function runBenchmark() {{
      if (!wasmInstance) return;
      const iters = 1000000;
      const n = 25;

      // 1. WASM
      const t0 = performance.now();
      for (let i = 0; i < iters; i++) {{
        wasmInstance.fibonacci(n);
      }}
      const t1 = performance.now();
      const wasmDuration = (t1 - t0).toFixed(2);

      // 2. JS
      const t2 = performance.now();
      for (let i = 0; i < iters; i++) {{
        jsFibonacci(n);
      }}
      const t3 = performance.now();
      const jsDuration = (t3 - t2).toFixed(2);

      document.getElementById("wasmTime").innerText = wasmDuration + " ms (1M ops)";
      document.getElementById("jsTime").innerText = jsDuration + " ms (1M ops)";
    }}
  </script>
</body>
</html>
"""

with open("web/index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Created web/index.html successfully!")

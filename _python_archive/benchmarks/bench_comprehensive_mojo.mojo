# bench_comprehensive_mojo.mojo — Vir Cross-Language Benchmark (Mojo)
# Run: mojo bench_comprehensive_mojo.mojo
from time import now
from math import exp, sqrt, abs
from memory import memset_zero, UnsafePointer
from sys import num_physical_cores

alias F64 = Float64
alias TILE = 64

# ═══════════════════════════════════════════════════════
# 1. COMPUTATIONAL THROUGHPUT
# ═══════════════════════════════════════════════════════

fn gemm_tiled(a: UnsafePointer[F64], b: UnsafePointer[F64], c: UnsafePointer[F64], n: Int):
    for i in range(n * n):
        c[i] = 0.0
    for i0 in range(0, n, TILE):
        for k0 in range(0, n, TILE):
            for j0 in range(0, n, TILE):
                var ie = min(i0 + TILE, n)
                var ke = min(k0 + TILE, n)
                var je = min(j0 + TILE, n)
                for i in range(i0, ie):
                    for k in range(k0, ke):
                        var a_ik = a[i * n + k]
                        for j in range(j0, je):
                            c[i * n + j] += a_ik * b[k * n + j]

fn winograd_f2x3(tile: UnsafePointer[F64], filt: UnsafePointer[F64], out: UnsafePointer[F64]):
    var r00 = tile[0]-tile[8]; var r01 = tile[1]-tile[9]; var r02 = tile[2]-tile[10]; var r03 = tile[3]-tile[11]
    var r10 = tile[4]+tile[8]; var r11 = tile[5]+tile[9]; var r12 = tile[6]+tile[10]; var r13 = tile[7]+tile[11]
    var r20 = tile[8]-tile[4]; var r21 = tile[9]-tile[5]; var r22 = tile[10]-tile[6]; var r23 = tile[11]-tile[7]
    var r30 = tile[4]-tile[12]; var r31 = tile[5]-tile[13]; var r32 = tile[6]-tile[14]; var r33 = tile[7]-tile[15]

    var d = UnsafePointer[F64].alloc(16)
    d[0]=r00-r02; d[1]=r01+r02; d[2]=r02-r01; d[3]=r01-r03
    d[4]=r10-r12; d[5]=r11+r12; d[6]=r12-r11; d[7]=r11-r13
    d[8]=r20-r22; d[9]=r21+r22; d[10]=r22-r21; d[11]=r21-r23
    d[12]=r30-r32; d[13]=r31+r32; d[14]=r32-r31; d[15]=r31-r33

    var v = UnsafePointer[F64].alloc(16)
    for i in range(16):
        v[i] = d[i] * filt[i]

    var s00 = v[0]+v[4]+v[8]; var s01 = v[1]+v[5]+v[9]; var s02 = v[2]+v[6]+v[10]; var s03 = v[3]+v[7]+v[11]
    var s10 = v[4]-v[8]-v[12]; var s11 = v[5]-v[9]-v[13]; var s12 = v[6]-v[10]-v[14]; var s13 = v[7]-v[11]-v[15]

    out[0] = s00+s01+s02; out[1] = s01-s02-s03; out[2] = s10+s11+s12; out[3] = s11-s12-s13
    d.free()
    v.free()

fn kahan_dot(a: UnsafePointer[F64], b: UnsafePointer[F64], n: Int) -> F64:
    var s: F64 = 0.0
    var c: F64 = 0.0
    for i in range(n):
        var y = a[i] * b[i] - c
        var t = s + y
        c = (t - s) - y
        s = t
    return s

fn softmax_online(x: UnsafePointer[F64], out: UnsafePointer[F64], n: Int):
    var run_max: F64 = -1e308
    var run_sum: F64 = 0.0
    for i in range(n):
        if x[i] > run_max:
            run_sum = run_sum * exp(run_max - x[i])
            run_max = x[i]
        run_sum += exp(x[i] - run_max)
    for i in range(n):
        out[i] = exp(x[i] - run_max) / run_sum

fn fused_ew(x: UnsafePointer[F64], y: UnsafePointer[F64], n: Int, a: F64, b: F64):
    for i in range(n):
        var v = a * x[i] + b
        y[i] = v if v > 0.0 else 0.0

fn unfused_ew(x: UnsafePointer[F64], y: UnsafePointer[F64], n: Int, a: F64, b: F64):
    var t1 = UnsafePointer[F64].alloc(n)
    var t2 = UnsafePointer[F64].alloc(n)
    for i in range(n):
        t1[i] = a * x[i]
    for i in range(n):
        t2[i] = t1[i] + b
    for i in range(n):
        y[i] = t2[i] if t2[i] > 0.0 else 0.0
    t1.free()
    t2.free()

fn welford_kahan(x: UnsafePointer[F64], n: Int) -> (F64, F64):
    var mean: F64 = 0.0
    var m2: F64 = 0.0
    var comp: F64 = 0.0
    for i in range(n):
        var delta = x[i] - mean
        mean += delta / F64(i + 1)
        var delta2 = x[i] - mean
        var y = delta * delta2 - comp
        var s = m2 + y
        comp = (s - m2) - y
        m2 = s
    return (mean, m2 / F64(n))

# ═══════════════════════════════════════════════════════
# 2. MEMORY
# ═══════════════════════════════════════════════════════

fn bench_alloc_latency(n_allocs: Int, size: Int) -> F64:
    var start = now()
    for _ in range(n_allocs):
        var p = UnsafePointer[UInt8].alloc(size)
        p[0] = 0
        p.free()
    var elapsed = now() - start
    return F64(elapsed) / F64(n_allocs)

# ═══════════════════════════════════════════════════════
# NUMERICAL STABILITY
# ═══════════════════════════════════════════════════════

fn sum_naive(x: UnsafePointer[F64], n: Int) -> F64:
    var s: F64 = 0.0
    for i in range(n):
        s += x[i]
    return s

fn sum_kahan(x: UnsafePointer[F64], n: Int) -> F64:
    var s: F64 = 0.0
    var c: F64 = 0.0
    for i in range(n):
        var y = x[i] - c
        var t = s + y
        c = (t - s) - y
        s = t
    return s

# ═══════════════════════════════════════════════════════
# BENCHMARK HELPER
# ═══════════════════════════════════════════════════════

fn bench_fn(label: String, iters: Int, body: fn() -> None) -> F64:
    body()  # warmup
    var start = now()
    for _ in range(iters):
        body()
    var elapsed = now() - start
    var us = F64(elapsed) / 1000.0 / F64(iters)
    print(label, "  ", us, " µs")
    return us

# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

fn main():
    print("═══════════════════════════════════════════")
    print("  Mojo Comprehensive Benchmark")
    print("═══════════════════════════════════════════")
    print()

    # ── 1. THROUGHPUT ─────────────────────────────
    print("▓ 1. COMPUTATIONAL THROUGHPUT")
    print("───────────────────────────────────────────")

    # GEMM 512
    var n512 = 512
    var a512 = UnsafePointer[F64].alloc(n512 * n512)
    var b512 = UnsafePointer[F64].alloc(n512 * n512)
    var c512 = UnsafePointer[F64].alloc(n512 * n512)
    for i in range(n512 * n512):
        a512[i] = F64(i % 97) * 0.01
        b512[i] = F64(i % 89) * 0.01

    var start = now()
    for _ in range(5):
        gemm_tiled(a512, b512, c512, n512)
    var elapsed = now() - start
    print("GEMM 512×512 tiled               ", F64(elapsed) / 1000.0 / 5.0, " µs")
    a512.free(); b512.free(); c512.free()

    # GEMM 1024
    var n1k = 1024
    var a1k = UnsafePointer[F64].alloc(n1k * n1k)
    var b1k = UnsafePointer[F64].alloc(n1k * n1k)
    var c1k = UnsafePointer[F64].alloc(n1k * n1k)
    for i in range(n1k * n1k):
        a1k[i] = F64(i % 97) * 0.01
        b1k[i] = F64(i % 89) * 0.01

    start = now()
    for _ in range(3):
        gemm_tiled(a1k, b1k, c1k, n1k)
    elapsed = now() - start
    print("GEMM 1024×1024 tiled             ", F64(elapsed) / 1000.0 / 3.0, " µs")
    a1k.free(); b1k.free(); c1k.free()

    # Winograd 100K tiles
    var tile = UnsafePointer[F64].alloc(16)
    var filt = UnsafePointer[F64].alloc(16)
    var wout = UnsafePointer[F64].alloc(4)
    for i in range(16):
        tile[i] = F64(i) * 0.1
        filt[i] = F64(15 - i) * 0.1

    start = now()
    for _ in range(10):
        for t in range(100000):
            tile[0] = F64(t) * 0.00001
            winograd_f2x3(tile, filt, wout)
    elapsed = now() - start
    print("Winograd F(2,3) 100K tiles       ", F64(elapsed) / 1000.0 / 10.0, " µs")
    tile.free(); filt.free(); wout.free()

    # Softmax
    var ns = 100000
    var sx = UnsafePointer[F64].alloc(ns)
    var sy = UnsafePointer[F64].alloc(ns)
    for i in range(ns):
        sx[i] = F64(i % 1000) * 0.001 - 0.5

    start = now()
    for _ in range(200):
        softmax_online(sx, sy, ns)
    elapsed = now() - start
    print("Softmax (2-pass online) 100K     ", F64(elapsed) / 1000.0 / 200.0, " µs")
    sx.free(); sy.free()

    # Fused EW
    var ne = 1000000
    var ex = UnsafePointer[F64].alloc(ne)
    var ey = UnsafePointer[F64].alloc(ne)
    for i in range(ne):
        ex[i] = F64(i) * 1e-6

    start = now()
    for _ in range(200):
        fused_ew(ex, ey, ne, 2.0, -0.5)
    elapsed = now() - start
    print("EW fused (mul+add+relu) 1M       ", F64(elapsed) / 1000.0 / 200.0, " µs")

    start = now()
    for _ in range(200):
        unfused_ew(ex, ey, ne, 2.0, -0.5)
    elapsed = now() - start
    print("EW unfused 3-pass 1M             ", F64(elapsed) / 1000.0 / 200.0, " µs")
    ex.free(); ey.free()

    # Welford
    var nw = 1000000
    var wx = UnsafePointer[F64].alloc(nw)
    for i in range(nw):
        wx[i] = F64(i % 10000) * 0.0001

    start = now()
    for _ in range(50):
        _ = welford_kahan(wx, nw)
    elapsed = now() - start
    print("Welford-Kahan variance 1M        ", F64(elapsed) / 1000.0 / 50.0, " µs")
    wx.free()

    # Kahan dot
    var nd = 10000000
    var da = UnsafePointer[F64].alloc(nd)
    var db = UnsafePointer[F64].alloc(nd)
    for i in range(nd):
        da[i] = 1.0 + 1e-8 * F64(i)
        db[i] = 1.0 - 1e-8 * F64(i)

    start = now()
    for _ in range(10):
        _ = kahan_dot(da, db, nd)
    elapsed = now() - start
    print("Kahan dot product 10M            ", F64(elapsed) / 1000.0 / 10.0, " µs")
    da.free(); db.free()

    # ── 2. MEMORY ─────────────────────────────────
    print()
    print("▓ 2. MEMORY DISCIPLINE")
    print("───────────────────────────────────────────")

    print("alloc/free 64B                    ", bench_alloc_latency(1000000, 64), " ns/op")
    print("alloc/free 4KB                    ", bench_alloc_latency(1000000, 4096), " ns/op")
    print("alloc/free 1MB                    ", bench_alloc_latency(100000, 1048576), " ns/op")

    # ── NUMERICAL STABILITY ──────────────────────
    print()
    print("▓ NUMERICAL STABILITY")
    print("───────────────────────────────────────────")

    var nn = 10000000
    var nx = UnsafePointer[F64].alloc(nn)
    for i in range(nn):
        nx[i] = 1.0 + 1e-12 * F64(i - nn // 2)

    var naive = sum_naive(nx, nn)
    var kahan = sum_kahan(nx, nn)
    var true_sum = F64(nn)
    print("  True sum (analytic): ", true_sum)
    print("  Naive summation:     ", naive, "  (err=", abs(naive - true_sum), ")")
    print("  Kahan summation:     ", kahan, "  (err=", abs(kahan - true_sum), ")")
    nx.free()

    print()
    print("═══════════════════════════════════════════")

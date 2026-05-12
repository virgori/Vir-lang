"""
Tests for NEON kernels — Backend equivalence against scalar oracle.
====================================================================
Per design plan §7: "scalar va vector backend cho ket qua dung trong tolerance"
"""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.virmatrix.registry import get_global_registry
from src.virplat.capability_profile import VectorBackend
import src.virmatrix.kernels.scalar.ops  # noqa: F401
import src.virmatrix.kernels.neon.ops  # noqa: F401

R = get_global_registry()
SCALAR = VectorBackend.SCALAR
NEON = VectorBackend.NEON
TOL = 1e-5


def _get(op, backend):
    fn = R.get(op, backend)
    assert fn is not None, f"No kernel for ({op}, {backend.name})"
    return fn


def _approx(a, b, tol=TOL):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < tol
    return len(a) == len(b) and all(abs(x - y) < tol for x, y in zip(a, b))


# =============================================================================
#  Elementwise binary — NEON vs SCALAR
# =============================================================================

def _test_binary(op: str, a: list[float], b: list[float]):
    ref = _get(op, SCALAR)(a, b)
    got = _get(op, NEON)(a, b)
    assert _approx(ref, got), f"{op}: ref={ref} got={got}"


def test_add_neon():
    _test_binary("add", [1.0, 2.0, 3.0, 4.0, 5.0], [10.0, 20.0, 30.0, 40.0, 50.0])

def test_sub_neon():
    _test_binary("sub", [5.0, 3.0, 1.0, 0.0], [1.0, 2.0, 3.0, 4.0])

def test_mul_neon():
    _test_binary("mul", [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
                        [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])

def test_div_neon():
    _test_binary("div", [10.0, 20.0, 30.0, 40.0], [2.0, 4.0, 5.0, 8.0])

def test_div_zero_neon():
    ref = _get("div", SCALAR)([1.0], [0.0])
    got = _get("div", NEON)([1.0], [0.0])
    assert ref == got


# =============================================================================
#  Elementwise unary — NEON vs SCALAR
# =============================================================================

def _test_unary(op: str, a: list[float]):
    ref = _get(op, SCALAR)(a)
    got = _get(op, NEON)(a)
    assert _approx(ref, got), f"{op}: ref={ref} got={got}"


def test_neg_neon():
    _test_unary("neg", [1.0, -2.0, 0.0, 3.0, -7.0])

def test_abs_neon():
    _test_unary("abs", [-3.0, 2.0, -1.0, 0.0, 5.0])

def test_sqrt_neon():
    _test_unary("sqrt", [4.0, 9.0, 16.0, 25.0, 0.0])

def test_rsqrt_neon():
    _test_unary("rsqrt", [4.0, 9.0, 16.0, 25.0])

def test_exp_neon():
    _test_unary("exp", [0.0, 1.0, -1.0, 2.0, -2.0])

def test_log_neon():
    _test_unary("log", [1.0, 2.718281828, 10.0, 0.5, 100.0])


# =============================================================================
#  Activations — NEON vs SCALAR
# =============================================================================

def test_relu_neon():
    _test_unary("relu", [-1.0, 0.0, 2.0, -0.5, 3.0, -100.0, 50.0, 0.1])

def test_sigmoid_neon():
    _test_unary("sigmoid", [0.0, 1.0, -1.0, 5.0, -5.0])

def test_tanh_neon():
    _test_unary("tanh", [0.0, 1.0, -1.0, 2.0, -2.0])

def test_gelu_neon():
    _test_unary("gelu", [0.0, 1.0, -1.0, 2.0, -0.5, 3.0, -3.0, 0.5])

def test_silu_neon():
    _test_unary("silu", [0.0, 1.0, -1.0, 2.0, -2.0])


# =============================================================================
#  Reductions — NEON vs SCALAR
# =============================================================================

def test_reduce_sum_neon():
    a = [float(i) for i in range(1, 17)]  # 16 elements to test NEON path
    ref = _get("reduce_sum", SCALAR)(a)
    got = _get("reduce_sum", NEON)(a)
    assert abs(ref - got) < TOL

def test_reduce_mean_neon():
    a = [2.0, 4.0, 6.0, 8.0, 10.0]
    ref = _get("reduce_mean", SCALAR)(a)
    got = _get("reduce_mean", NEON)(a)
    assert abs(ref - got) < TOL

def test_reduce_max_neon():
    a = [1.0, 5.0, 3.0, 7.0, 2.0, 6.0, 4.0, 8.0]
    ref = _get("reduce_max", SCALAR)(a)
    got = _get("reduce_max", NEON)(a)
    assert abs(ref - got) < TOL


# =============================================================================
#  GEMM — NEON vs SCALAR
# =============================================================================

def test_matmul_neon_identity():
    rk = _get("matmul", NEON)
    a = [1.0, 0.0, 0.0, 1.0]
    b = [5.0, 6.0, 7.0, 8.0]
    ref = _get("matmul", SCALAR)(a, b, 2, 2, 2)
    got = rk(a, b, 2, 2, 2)
    assert _approx(ref, got)

def test_matmul_neon_3x3():
    a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
    b = [9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
    ref = _get("matmul", SCALAR)(a, b, 3, 3, 3)
    got = _get("matmul", NEON)(a, b, 3, 3, 3)
    assert _approx(ref, got)

def test_matmul_neon_8x8():
    """8x8 matmul exercises the tiled NEON path fully."""
    import random
    random.seed(42)
    n = 8
    a = [random.uniform(-1, 1) for _ in range(n * n)]
    b = [random.uniform(-1, 1) for _ in range(n * n)]
    ref = _get("matmul", SCALAR)(a, b, n, n, n)
    got = _get("matmul", NEON)(a, b, n, n, n)
    assert _approx(ref, got, tol=1e-4)

def test_matmul_neon_rect():
    """Non-square: (2x3) @ (3x5) = (2x5)."""
    import random
    random.seed(7)
    m, k, n = 2, 3, 5
    a = [random.uniform(-1, 1) for _ in range(m * k)]
    b = [random.uniform(-1, 1) for _ in range(k * n)]
    ref = _get("matmul", SCALAR)(a, b, m, k, n)
    got = _get("matmul", NEON)(a, b, m, k, n)
    assert _approx(ref, got, tol=1e-4)


# =============================================================================
#  Normalization — NEON vs SCALAR
# =============================================================================

def test_softmax_neon():
    a = [1.0, 2.0, 3.0, 4.0]
    ref = _get("softmax", SCALAR)(a)
    got = _get("softmax", NEON)(a)
    assert _approx(ref, got)

def test_layer_norm_neon():
    x = [1.0, 2.0, 3.0, 4.0]
    g = [1.0, 1.0, 1.0, 1.0]
    b = [0.0, 0.0, 0.0, 0.0]
    ref = _get("layer_norm", SCALAR)(x, g, b)
    got = _get("layer_norm", NEON)(x, g, b)
    assert _approx(ref, got)

def test_rms_norm_neon():
    x = [1.0, 2.0, 3.0, 4.0]
    g = [1.0, 1.0, 1.0, 1.0]
    ref = _get("rms_norm", SCALAR)(x, g)
    got = _get("rms_norm", NEON)(x, g)
    assert _approx(ref, got)


# =============================================================================
#  Scale / Fill / AXPY — NEON vs SCALAR
# =============================================================================

def test_scale_neon():
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    ref = _get("scale", SCALAR)(a, 2.5)
    got = _get("scale", NEON)(a, 2.5)
    assert _approx(ref, got)

def test_fill_neon():
    ref = _get("fill", SCALAR)(8, 3.14)
    got = _get("fill", NEON)(8, 3.14)
    assert ref == got

def test_axpy_neon():
    alpha = [2.0]
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [10.0, 20.0, 30.0, 40.0, 50.0]
    ref = _get("axpy", SCALAR)(alpha, x, y)
    got = _get("axpy", NEON)(alpha, x, y)
    assert _approx(ref, got)


# =============================================================================
#  Registry — NEON kernels are actually registered
# =============================================================================

def test_neon_registered():
    """All NEON kernels must be in the registry."""
    ops = ["add", "sub", "mul", "div", "neg", "abs", "sqrt", "rsqrt",
           "exp", "log", "relu", "sigmoid", "tanh", "gelu", "silu",
           "reduce_sum", "reduce_mean", "reduce_max", "softmax",
           "layer_norm", "rms_norm", "matmul", "fill", "scale", "axpy"]
    for op in ops:
        assert R._kernels.get((op, NEON)) is not None, \
            f"NEON kernel for '{op}' not registered"

"""Tests for VirMatrix scalar kernels."""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.virmatrix.registry import get_global_registry
from src.virplat.capability_profile import VectorBackend
import src.virmatrix.kernels.scalar.ops  # noqa: F401

B = VectorBackend.SCALAR
R = get_global_registry()


def _get(op):
    return R.get(op, B)


def _approx(a, b, tol=1e-5):
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) < tol
    return len(a) == len(b) and all(abs(x - y) < tol for x, y in zip(a, b))


def test_add():
    assert _get("add")([1.0, 2.0, 3.0], [4.0, 5.0, 6.0]) == [5.0, 7.0, 9.0]

def test_sub():
    assert _get("sub")([5.0, 3.0], [1.0, 2.0]) == [4.0, 1.0]

def test_mul():
    assert _get("mul")([2.0, 3.0], [4.0, 5.0]) == [8.0, 15.0]

def test_div():
    assert _approx(_get("div")([6.0, 9.0], [2.0, 3.0]), [3.0, 3.0])

def test_neg():
    assert _get("neg")([1.0, -2.0, 0.0]) == [-1.0, 2.0, 0.0]

def test_abs():
    assert _get("abs")([-3.0, 2.0, -1.0]) == [3.0, 2.0, 1.0]

def test_relu():
    assert _get("relu")([-1.0, 0.0, 2.0, -0.5]) == [0.0, 0.0, 2.0, 0.0]

def test_sigmoid():
    assert abs(_get("sigmoid")([0.0])[0] - 0.5) < 1e-6

def test_tanh():
    assert abs(_get("tanh")([0.0])[0]) < 1e-6

def test_gelu():
    r = _get("gelu")([0.0, 1.0, -1.0])
    assert abs(r[0]) < 1e-5
    assert abs(r[1] - 0.8413) < 0.01

def test_silu():
    assert abs(_get("silu")([0.0])[0]) < 1e-6

def test_sqrt():
    assert _approx(_get("sqrt")([4.0, 9.0, 16.0]), [2.0, 3.0, 4.0])

def test_exp():
    r = _get("exp")([0.0, 1.0])
    assert abs(r[0] - 1.0) < 1e-6
    assert abs(r[1] - math.e) < 1e-5

def test_log():
    r = _get("log")([1.0, math.e])
    assert abs(r[0]) < 1e-6
    assert abs(r[1] - 1.0) < 1e-5

def test_matmul_identity():
    k = _get("matmul")
    assert _approx(k([1.0, 0.0, 0.0, 1.0], [5.0, 6.0, 7.0, 8.0], 2, 2, 2),
                   [5.0, 6.0, 7.0, 8.0])

def test_matmul_basic():
    k = _get("matmul")
    # (1x3) @ (3x2) = (1x2): [1*4+2*6+3*8, 1*5+2*7+3*9] = [40, 46]
    assert _approx(k([1.0, 2.0, 3.0], [4.0, 5.0, 6.0, 7.0, 8.0, 9.0], 1, 3, 2),
                   [40.0, 46.0])

# reduce/softmax/layer_norm take flat lists (vector-level ops)
def test_reduce_sum():
    assert abs(_get("reduce_sum")([1.0, 2.0, 3.0]) - 6.0) < 1e-6

def test_reduce_mean():
    assert abs(_get("reduce_mean")([2.0, 4.0, 6.0]) - 4.0) < 1e-6

def test_reduce_max():
    assert abs(_get("reduce_max")([1.0, 5.0, 3.0]) - 5.0) < 1e-6

def test_softmax():
    r = _get("softmax")([1.0, 2.0, 3.0])
    assert abs(sum(r) - 1.0) < 1e-5
    assert r[0] < r[1] < r[2]

def test_layer_norm():
    x = [1.0, 2.0, 3.0]
    g = [1.0, 1.0, 1.0]
    b = [0.0, 0.0, 0.0]
    r = _get("layer_norm")(x, g, b, 1e-5)
    assert abs(sum(r) / 3) < 1e-4

def test_fill_and_scale():
    assert _get("fill")(4, 3.0) == [3.0, 3.0, 3.0, 3.0]
    assert _get("scale")([1.0, 2.0, 3.0], 2.0) == [2.0, 4.0, 6.0]

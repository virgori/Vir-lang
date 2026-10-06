"""
Tests for additional gradient rules — gelu, silu, softmax, layer_norm, etc.
=============================================================================
Uses numerical gradient checking for correctness.
"""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.virgrad.grad_rules import GradRules


EPS = 1e-5
TOL = 1e-3  # numerical gradient tolerance


def _numerical_grad_unary(fn, x, eps=EPS):
    """Compute numerical gradient for a scalar function applied elementwise."""
    grad = []
    for i in range(len(x)):
        x_plus = x[:]
        x_minus = x[:]
        x_plus[i] += eps
        x_minus[i] -= eps
        grad.append((fn(x_plus[i]) - fn(x_minus[i])) / (2 * eps))
    return grad


def _check_grad(op, inputs, expected_count=None):
    """Verify that gradient rule exists and returns correct number of grads."""
    assert GradRules.has(op), f"No gradient rule for '{op}'"
    fn = GradRules.get(op)
    assert fn is not None
    grad_out = [1.0] * len(inputs[0]) if isinstance(inputs[0], list) else [1.0]
    result = fn(grad_out, *inputs)
    assert isinstance(result, tuple)
    if expected_count is not None:
        assert len(result) == expected_count


# =============================================================================
#  Test existence of all gradient rules
# =============================================================================

def test_grad_rules_registered():
    """All required gradient rules should be registered."""
    required = [
        "add", "sub", "mul", "div", "relu", "sigmoid", "tanh",
        "exp", "log", "neg", "matmul", "reduce_mean", "reduce_sum",
        # New rules
        "abs", "sqrt", "rsqrt", "gelu", "silu", "softmax",
        "layer_norm", "rms_norm", "reduce_max",
    ]
    for op in required:
        assert GradRules.has(op), f"Missing gradient rule: {op}"


# =============================================================================
#  Numerical gradient checks for new rules
# =============================================================================

def test_grad_abs():
    x = [2.0, -3.0, 0.5]
    grad_out = [1.0, 1.0, 1.0]
    grads = GradRules.get("abs")(grad_out, x)
    assert len(grads) == 1
    # d|x|/dx = sign(x)
    assert grads[0] == [1.0, -1.0, 1.0]


def test_grad_sqrt():
    x = [4.0, 9.0, 16.0]
    grad_out = [1.0, 1.0, 1.0]
    grads = GradRules.get("sqrt")(grad_out, x)
    expected = [1.0 / (2.0 * math.sqrt(xi)) for xi in x]
    for g, e in zip(grads[0], expected):
        assert abs(g - e) < TOL


def test_grad_rsqrt():
    x = [4.0, 9.0]
    grad_out = [1.0, 1.0]
    grads = GradRules.get("rsqrt")(grad_out, x)
    # d(x^-0.5)/dx = -0.5 * x^-1.5
    expected = [-0.5 / (xi * math.sqrt(xi)) for xi in x]
    for g, e in zip(grads[0], expected):
        assert abs(g - e) < TOL


def test_grad_gelu_numerical():
    """GELU gradient vs numerical."""
    c = math.sqrt(2.0 / math.pi)

    def gelu(xi):
        return xi * 0.5 * (1.0 + math.tanh(c * (xi + 0.044715 * xi ** 3)))

    x = [0.5, 1.0, -0.5, 2.0]
    grad_out = [1.0] * len(x)
    grads = GradRules.get("gelu")(grad_out, x)

    # Numerical
    for i, xi in enumerate(x):
        num = (gelu(xi + EPS) - gelu(xi - EPS)) / (2 * EPS)
        assert abs(grads[0][i] - num) < TOL, f"gelu grad at x={xi}: {grads[0][i]} vs num={num}"


def test_grad_silu_numerical():
    """SiLU/Swish gradient vs numerical."""
    def sig(v):
        if v >= 0:
            return 1.0 / (1.0 + math.exp(-v))
        ex = math.exp(v)
        return ex / (1.0 + ex)

    def silu(xi):
        return xi * sig(xi)

    x = [0.0, 1.0, -1.0, 2.0]
    grad_out = [1.0] * len(x)
    grads = GradRules.get("silu")(grad_out, x)

    for i, xi in enumerate(x):
        num = (silu(xi + EPS) - silu(xi - EPS)) / (2 * EPS)
        assert abs(grads[0][i] - num) < TOL, f"silu grad at x={xi}"


def test_grad_softmax():
    """Softmax backward: sum of input grads should equal 0 when grad_out is uniform."""
    x = [1.0, 2.0, 3.0]
    # When grad_out is uniform and already normalized, dx should sum to ~0
    grad_out = [1.0, 1.0, 1.0]
    grads = GradRules.get("softmax")(grad_out, x)
    assert len(grads) == 1
    assert len(grads[0]) == 3
    # Sum of softmax jacobian with uniform upstream should be ~0
    assert abs(sum(grads[0])) < TOL


def test_grad_softmax_specific():
    """Softmax backward with specific upstream."""
    x = [1.0, 2.0, 3.0]
    # s = softmax(x)
    mx = max(x)
    exps = [math.exp(xi - mx) for xi in x]
    total = sum(exps)
    s = [e / total for e in exps]

    # Use softmax values as upstream gradient (Jacobian check)
    grad_out = [0.0, 1.0, 0.0]  # select 2nd element
    grads = GradRules.get("softmax")(grad_out, x)
    # dx_i = s_i * (dy_i - sum(dy_j * s_j))
    dot = sum(g * si for g, si in zip(grad_out, s))
    expected = [si * (g - dot) for si, g in zip(s, grad_out)]
    for g, e in zip(grads[0], expected):
        assert abs(g - e) < TOL


def test_grad_layer_norm():
    """Layer norm backward returns 3 gradients: dx, dgamma, dbeta."""
    x = [1.0, 2.0, 3.0, 4.0]
    gamma = [1.0, 1.0, 1.0, 1.0]
    beta = [0.0, 0.0, 0.0, 0.0]
    grad_out = [1.0, 0.0, 0.0, 0.0]
    grads = GradRules.get("layer_norm")(grad_out, x, gamma, beta)
    assert len(grads) == 3  # dx, dgamma, dbeta
    dx, dgamma, dbeta = grads
    assert len(dx) == 4
    assert len(dgamma) == 4
    assert len(dbeta) == 4
    # dbeta should equal grad_out
    assert dbeta == grad_out


def test_grad_rms_norm():
    """RMS norm backward returns 2 gradients: dx, dgamma."""
    x = [1.0, 2.0, 3.0]
    gamma = [1.0, 1.0, 1.0]
    grad_out = [1.0, 1.0, 1.0]
    grads = GradRules.get("rms_norm")(grad_out, x, gamma)
    assert len(grads) == 2  # dx, dgamma
    dx, dgamma = grads
    assert len(dx) == 3
    assert len(dgamma) == 3


def test_grad_reduce_max():
    """Gradient flows only to the max element."""
    x = [1.0, 5.0, 3.0]
    grad_out = [1.0]
    grads = GradRules.get("reduce_max")(grad_out, x)
    assert grads[0] == [0.0, 1.0, 0.0]

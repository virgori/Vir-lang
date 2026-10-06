"""Tests for VirNN — tensor, module, layers, and end-to-end MLP."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Ensure scalar kernels are registered
import src.virmatrix.kernels.scalar.ops as _scalar_ops  # noqa: F401

from src.virnn.tensor import Tensor
from src.virnn.parameter import Parameter
from src.virnn.module import Module
from src.virnn.layers.linear import Linear
from src.virnn.layers.activations import ReLU, GELU, SiLU
from src.virnn.layers.normalization import LayerNorm, RMSNorm
from src.virnn.layers.embedding import Embedding
from src.virnn.layers.containers import Sequential, MLP


# ── Tensor tests ────────────────────────────────────────────


def test_tensor_zeros():
    t = Tensor.zeros((3, 4))
    assert t.shape == (3, 4)
    assert t.numel == 12
    assert all(v == 0.0 for v in t.data)


def test_tensor_ones():
    t = Tensor.ones((2, 3))
    assert all(v == 1.0 for v in t.data)


def test_tensor_randn():
    t = Tensor.randn((100,), seed=42)
    assert t.numel == 100
    mean = sum(t.data) / len(t.data)
    # Should be roughly zero-centered
    assert abs(mean) < 0.5


def test_tensor_item():
    t = Tensor(data=[3.14], shape=(1,))
    assert abs(t.item() - 3.14) < 1e-6


def test_tensor_indexing():
    t = Tensor(data=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0], shape=(2, 3))
    assert t[(0, 0)] == 1.0
    assert t[(0, 2)] == 3.0
    assert t[(1, 0)] == 4.0
    t[(1, 1)] = 99.0
    assert t[(1, 1)] == 99.0


def test_tensor_clone():
    t = Tensor(data=[1.0, 2.0], shape=(2,))
    c = t.clone()
    c.data[0] = 99.0
    assert t.data[0] == 1.0  # Original unchanged


def test_tensor_grad():
    t = Tensor.zeros((4,), requires_grad=True)
    assert t.grad is None
    t.accumulate_grad([1.0, 2.0, 3.0, 4.0])
    assert t.grad == [1.0, 2.0, 3.0, 4.0]
    t.accumulate_grad([1.0, 1.0, 1.0, 1.0])
    assert t.grad == [2.0, 3.0, 4.0, 5.0]
    t.zero_grad()
    assert all(v == 0.0 for v in t.grad)


# ── Parameter tests ─────────────────────────────────────────


def test_parameter():
    p = Parameter(data=[1.0, 2.0], shape=(2,), name="w")
    assert p.requires_grad is True
    assert p.name == "w"


def test_parameter_from_tensor():
    t = Tensor(data=[3.0, 4.0], shape=(2,))
    p = Parameter.from_tensor(t, name="bias")
    assert p.data == [3.0, 4.0]
    assert p.requires_grad is True


# ── Module tests ────────────────────────────────────────────


def test_module_parameters():
    lin = Linear(4, 3)
    params = lin.parameters()
    # Should have weight + bias
    assert len(params) == 2


def test_module_named_parameters():
    lin = Linear(4, 3)
    named = lin.named_parameters()
    names = [n for n, _ in named]
    assert "weight" in names
    assert "bias_param" in names


def test_module_zero_grad():
    lin = Linear(4, 3)
    for p in lin.parameters():
        p.accumulate_grad([1.0] * p.numel)
    lin.zero_grad()
    for p in lin.parameters():
        if p.grad is not None:
            assert all(v == 0.0 for v in p.grad)


def test_module_train_eval():
    lin = Linear(4, 3)
    assert lin.training is True
    lin.eval()
    assert lin.training is False
    lin.train()
    assert lin.training is True


# ── Layer tests ─────────────────────────────────────────────


def test_linear_forward():
    lin = Linear(4, 3, bias=True)
    x = Tensor.randn((2, 4), seed=1)
    out = lin(x)
    assert out.shape == (2, 3)
    assert len(out.data) == 6


def test_relu_forward():
    relu = ReLU()
    x = Tensor(data=[-1.0, 0.0, 1.0, -0.5], shape=(4,))
    out = relu(x)
    assert out.data[0] == 0.0
    assert out.data[2] == 1.0


def test_gelu_forward():
    gelu = GELU()
    x = Tensor(data=[0.0, 1.0], shape=(2,))
    out = gelu(x)
    assert abs(out.data[0]) < 1e-5


def test_layer_norm_forward():
    ln = LayerNorm(4)
    x = Tensor(data=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0], shape=(2, 4))
    out = ln(x)
    assert out.shape == (2, 4)
    # Each row should have ~zero mean
    row_mean = sum(out.data[:4]) / 4
    assert abs(row_mean) < 1e-4


def test_rms_norm_forward():
    rn = RMSNorm(3)
    x = Tensor(data=[1.0, 2.0, 3.0], shape=(1, 3))
    out = rn(x)
    assert out.shape == (1, 3)


def test_embedding_forward():
    emb = Embedding(10, 8)
    indices = Tensor(data=[0.0, 3.0, 7.0], shape=(3,))
    out = emb(indices)
    assert out.shape == (3, 8)


# ── Container tests ─────────────────────────────────────────


def test_sequential():
    seq = Sequential(Linear(4, 8), ReLU(), Linear(8, 2))
    x = Tensor.randn((1, 4), seed=42)
    out = seq(x)
    assert out.shape == (1, 2)


def test_mlp():
    mlp = MLP(dims=[4, 8, 2], activation="relu")
    x = Tensor.randn((1, 4), seed=42)
    out = mlp(x)
    assert out.shape == (1, 2)
    # Check parameter count
    params = mlp.parameters()
    assert len(params) > 0


def test_mlp_parameters():
    mlp = MLP(dims=[4, 8, 3])
    params = mlp.parameters()
    # Linear(4,8): weight(8,4)=32 + bias(8)=8 → 2 params
    # Linear(8,3): weight(3,8)=24 + bias(3)=3 → 2 params
    assert len(params) == 4


# ── End-to-end MLP training step ────────────────────────────


def test_mlp_forward_backward_step():
    """Smoke test: MLP forward pass + manual SGD-like step."""
    import random
    random.seed(42)

    mlp = MLP(dims=[4, 8, 2])
    x = Tensor.randn((2, 4), seed=1)
    target = Tensor(data=[1.0, 0.0, 0.0, 1.0], shape=(2, 2))

    # Forward
    pred = mlp(x)
    assert pred.shape == (2, 2)

    # Compute MSE loss manually
    loss = 0.0
    for i in range(pred.numel):
        diff = pred.data[i] - target.data[i]
        loss += diff * diff
    loss /= pred.numel
    assert isinstance(loss, float)
    assert loss >= 0.0

    # Simulate gradient step (just verify parameters can be updated)
    lr = 0.01
    for p in mlp.parameters():
        for i in range(p.numel):
            p.data[i] -= lr * 0.01  # Tiny pseudo-gradient
    # Verify forward still works after update
    pred2 = mlp(x)
    assert pred2.shape == (2, 2)

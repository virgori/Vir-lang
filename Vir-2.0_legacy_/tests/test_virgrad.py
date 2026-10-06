"""Tests for VirGrad — backward rules and tape-based autograd."""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.virgrad.grad_rules import GradRules
from src.virgrad.backward_builder import BackwardBuilder
from src.virgrad.tape_runtime import GradTape


def _approx(a, b, tol=1e-4):
    return len(a) == len(b) and all(abs(x - y) < tol for x, y in zip(a, b))


# ── Gradient rules ──────────────────────────────────────────

def test_grad_add():
    fn = GradRules.get("add")
    # fn(grad_out, a, b) -> (da, db)
    da, db = fn([1.0, 1.0], [1.0, 2.0], [3.0, 4.0])
    assert da == [1.0, 1.0]
    assert db == [1.0, 1.0]

def test_grad_mul():
    fn = GradRules.get("mul")
    # d(a*b)/da = b*go, d(a*b)/db = a*go
    da, db = fn([1.0, 1.0], [2.0, 3.0], [4.0, 5.0])
    assert da == [4.0, 5.0]
    assert db == [2.0, 3.0]

def test_grad_relu():
    fn = GradRules.get("relu")
    (da,) = fn([1.0, 1.0, 1.0, 1.0], [-1.0, 0.5, 0.0, 2.0])
    assert da == [0.0, 1.0, 0.0, 1.0]

def test_grad_exp():
    fn = GradRules.get("exp")
    (da,) = fn([1.0, 1.0], [0.0, 1.0])
    assert abs(da[0] - math.exp(0.0)) < 1e-5
    assert abs(da[1] - math.exp(1.0)) < 1e-5

def test_grad_neg():
    fn = GradRules.get("neg")
    (da,) = fn([1.0, 1.0], [1.0, -2.0])
    assert da == [-1.0, -1.0]


# ── BackwardBuilder ─────────────────────────────────────────

def test_backward_builder_simple():
    bb = BackwardBuilder()
    a_data = [2.0, 3.0]
    b_data = [4.0, 5.0]
    # Record: output_id=10, inputs=(1, 2)
    bb.record("add", output_id=10, input_ids=(1, 2),
              saved={"a": a_data, "b": b_data})
    grads = bb.backward({10: [1.0, 1.0]})
    assert 1 in grads
    assert 2 in grads
    assert grads[1] == [1.0, 1.0]


# ── GradTape ────────────────────────────────────────────────

def test_tape_basic():
    tape = GradTape()
    tape.watch(1)  # tensor_id=1

    # Record: relu(input_id=1) -> output_id=2
    tape.record_op("relu", output_id=2, input_ids=(1,),
                   saved={"x": [2.0, 3.0]})

    grads = tape.gradient(loss_id=2, loss_grad=[1.0, 1.0])
    assert 1 in grads
    assert grads[1] == [1.0, 1.0]  # Both values > 0 → grad passes through


def test_tape_chain():
    tape = GradTape()
    tape.watch(1)

    # neg(1) -> 2
    tape.record_op("neg", output_id=2, input_ids=(1,),
                   saved={"x": [1.0, -1.0]})
    # relu(2) -> 3, where data of 2 = [-1.0, 1.0]
    tape.record_op("relu", output_id=3, input_ids=(2,),
                   saved={"x": [-1.0, 1.0]})

    grads = tape.gradient(loss_id=3, loss_grad=[1.0, 1.0])
    # relu'([-1, 1]) = [0, 1], neg'() = -1
    # chain: [0*-1, 1*-1] = [0, -1]
    assert _approx(grads[1], [0.0, -1.0])


def test_tape_pause_resume():
    tape = GradTape()
    tape.watch(1)

    tape.pause()
    tape.record_op("relu", output_id=99, input_ids=(1,),
                   saved={"x": [1.0]})

    tape.resume()
    tape.record_op("relu", output_id=2, input_ids=(1,),
                   saved={"x": [1.0]})

    grads = tape.gradient(loss_id=2, loss_grad=[1.0])
    assert 1 in grads

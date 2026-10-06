"""Tests for VirOptim — SGD and Adam optimizers."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.viroptim.sgd import SGD
from src.viroptim.adam import Adam


def test_sgd_basic():
    params = {0: [1.0, 2.0, 3.0]}
    grads = {0: [0.1, 0.2, 0.3]}
    opt = SGD(lr=1.0)
    opt.step(params, grads)
    assert abs(params[0][0] - 0.9) < 1e-6
    assert abs(params[0][1] - 1.8) < 1e-6
    assert abs(params[0][2] - 2.7) < 1e-6

def test_sgd_weight_decay():
    params = {0: [1.0, 2.0]}
    grads = {0: [0.0, 0.0]}
    opt = SGD(lr=0.1, weight_decay=0.1)
    opt.step(params, grads)
    # effective_grad = [0 + 0.1*1, 0 + 0.1*2] = [0.1, 0.2]
    # param = [1 - 0.1*0.1, 2 - 0.1*0.2] = [0.99, 1.98]
    assert abs(params[0][0] - 0.99) < 1e-6
    assert abs(params[0][1] - 1.98) < 1e-6

def test_sgd_momentum():
    params = {0: [1.0]}
    grads = {0: [1.0]}
    opt = SGD(lr=0.1, momentum=0.9)
    opt.step(params, grads)
    assert abs(params[0][0] - 0.9) < 1e-6
    # Step 2
    grads = {0: [1.0]}
    opt.step(params, grads)
    assert abs(params[0][0] - 0.71) < 1e-6

def test_adam_basic():
    params = {0: [1.0, 2.0]}
    grads = {0: [0.1, 0.2]}
    opt = Adam(lr=0.001)
    opt.step(params, grads)
    assert params[0][0] < 1.0
    assert params[0][1] < 2.0

def test_adam_multiple_steps():
    params = {0: [5.0]}
    opt = Adam(lr=0.1)
    for _ in range(10):
        grads = {0: [1.0]}
        opt.step(params, grads)
    assert params[0][0] < 5.0

def test_adam_weight_decay():
    params = {0: [1.0]}
    grads = {0: [0.0]}
    opt = Adam(lr=0.01, weight_decay=0.1)
    opt.step(params, grads)
    assert params[0][0] < 1.0

"""Tests for VirPass — pass manager and builtin passes."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.qir.schema import DType
from src.qir.builder.graph_builder import QIRBuilder
from src.virpass.pass_manager import PassManager
from src.virpass.passes.builtin import ShapeTypeInferPass, VerifyPass, ElementwiseFusionPass


def test_pass_manager_infer_then_verify():
    b = QIRBuilder()
    x = b.input("x", DType.FLOAT32, (4, 8))
    y = b.relu(x)
    g = b.build()

    pm = PassManager()
    pm.add(ShapeTypeInferPass()).add(VerifyPass(allow_composite=True))
    pm.run(g)

    assert len(pm.results) == 2
    # Infer pass should have changed something
    assert pm.results[0][1].changed is True
    # Verify pass should report no errors
    assert len(pm.results[1][1].errors) == 0


def test_elementwise_fusion():
    b = QIRBuilder()
    x = b.input("x", DType.FLOAT32, (4,))
    bias = b.parameter("b", DType.FLOAT32, (4,))
    added = b.add(x, bias)
    y = b.relu(added)
    g = b.build()

    pm = PassManager()
    pm.add(ShapeTypeInferPass())
    pm.add(ElementwiseFusionPass())
    pm.run(g)

    # Fusion pass should have tried to fuse add+relu
    _, fusion_result = pm.results[1]
    assert fusion_result is not None


def test_pass_summary():
    b = QIRBuilder()
    x = b.input("x", DType.FLOAT32, (4,))
    y = b.relu(x)
    g = b.build()

    pm = PassManager()
    pm.add(ShapeTypeInferPass())
    pm.run(g)

    summary = pm.summary()
    assert "shape_type_infer" in summary

"""
Built-in passes: Shape/Type inference, Verification, Fusion.
=============================================================
"""

from __future__ import annotations

from src.virpass.base_pass import BasePass, PassResult, PassAction
from src.qir.module import QIRGraph
from src.qir.infer.shape_type_infer import ShapeTypeInfer
from src.qir.verify.verifiers import QIRVerifier
from src.qir.opcodes import QIRHOp, QIRMOp
from src.qir.schema import QIRMNode


class ShapeTypeInferPass(BasePass):
    """Run shape and type inference on QIR-H graph."""
    name = "shape_type_infer"
    action = PassAction.ANNOTATE

    def run(self, graph: QIRGraph) -> PassResult:
        infer = ShapeTypeInfer(graph)
        ok = infer.run()
        return PassResult(
            changed=True,
            errors=infer.errors if not ok else [],
            stats={"nodes_inferred": len(infer._resolved)},
        )


class VerifyPass(BasePass):
    """Run all QIR verifiers."""
    name = "verify"
    action = PassAction.INSPECT

    def __init__(self, allow_composite: bool = True) -> None:
        self._allow_composite = allow_composite

    def run(self, graph: QIRGraph) -> PassResult:
        verifier = QIRVerifier()
        result = verifier.verify_all(graph, allow_composite=self._allow_composite)
        return PassResult(
            changed=False,
            errors=[f"[{e.category}] node {e.node_id}: {e.message}" for e in result.errors],
            stats={"errors": len(result.errors)},
        )


class ElementwiseFusionPass(BasePass):
    """Fuse consecutive elementwise ops in QIR-M (e.g., mul+add -> fma)."""
    name = "elementwise_fusion"
    action = PassAction.FUSE

    # Fuseable patterns: (op1, op2) -> fused_op
    _PATTERNS: list[tuple[QIRMOp, QIRMOp, QIRMOp]] = [
        (QIRMOp.MUL, QIRMOp.ADD, QIRMOp.FUSED_MUL_ADD),
        (QIRMOp.ADD, QIRMOp.RELU, QIRMOp.FUSED_BIAS_RELU),
        (QIRMOp.ADD, QIRMOp.GELU, QIRMOp.FUSED_BIAS_GELU),
    ]

    def run(self, graph: QIRGraph) -> PassResult:
        if not graph.m_nodes:
            return PassResult(changed=False)

        fused = 0
        # Build reverse map: which M-node consumes each M-node
        consumers: dict[int, list[int]] = {}
        for nid, node in graph.m_nodes.items():
            for inp in node.input_ids:
                consumers.setdefault(inp, []).append(nid)

        to_remove: set[int] = set()
        for nid, node in list(graph.m_nodes.items()):
            if nid in to_remove:
                continue
            for op1, op2, fused_op in self._PATTERNS:
                if node.op != op1:
                    continue
                succs = consumers.get(nid, [])
                if len(succs) != 1:
                    continue
                succ_node = graph.m_nodes.get(succs[0])
                if succ_node is None or succ_node.op != op2:
                    continue
                # Fuse: replace succ with fused op taking all inputs
                all_inputs = node.input_ids + tuple(
                    i for i in succ_node.input_ids if i != nid
                )
                graph.m_nodes[succs[0]] = QIRMNode(
                    node_id=succs[0], op=fused_op,
                    input_ids=all_inputs,
                    tensor_type=succ_node.tensor_type,
                    shape_inferred=True, type_inferred=True,
                )
                to_remove.add(nid)
                fused += 1
                break

        for nid in to_remove:
            del graph.m_nodes[nid]

        return PassResult(changed=fused > 0, stats={"fused_ops": fused})

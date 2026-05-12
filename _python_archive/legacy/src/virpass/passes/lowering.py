"""
Additional fusion and lowering passes for Phase 4 completion.
===============================================================
Includes:
  - MatmulEpilogueFusionPass: fuses matmul + bias + activation
  - HToMLoweringPass: wraps h_to_m as a pass
  - MToLLoweringPass: wraps m_to_l as a pass
"""

from __future__ import annotations

from src.virpass.base_pass import BasePass, PassResult, PassAction
from src.qir.module import QIRGraph
from src.qir.opcodes import QIRMOp
from src.qir.schema import QIRMNode


class MatmulEpilogueFusionPass(BasePass):
    """Fuse matmul + bias + activation into fused patterns.

    Patterns detected:
      - MATMUL → ADD (bias) → RELU  →  matmul_bias_relu
      - MATMUL → ADD (bias) → GELU  →  matmul_bias_gelu
      - MATMUL → ADD (bias)         →  matmul_bias

    This reduces memory traffic by avoiding intermediate materializations.
    """
    name = "matmul_epilogue_fusion"
    action = PassAction.FUSE

    def run(self, graph: QIRGraph) -> PassResult:
        if not graph.m_nodes:
            return PassResult(changed=False)

        # Build consumer map
        consumers: dict[int, list[int]] = {}
        for nid, node in graph.m_nodes.items():
            for inp in node.input_ids:
                consumers.setdefault(inp, []).append(nid)

        fused = 0
        to_remove: set[int] = set()

        for nid, node in list(graph.m_nodes.items()):
            if nid in to_remove:
                continue
            if node.op != QIRMOp.MATMUL:
                continue

            succs = consumers.get(nid, [])
            if len(succs) != 1:
                continue

            bias_node = graph.m_nodes.get(succs[0])
            if bias_node is None or bias_node.op != QIRMOp.ADD:
                continue

            # MATMUL + ADD (bias) found — check for activation
            bias_succs = consumers.get(succs[0], [])

            if len(bias_succs) == 1:
                act_node = graph.m_nodes.get(bias_succs[0])
                if act_node and act_node.op in (QIRMOp.RELU, QIRMOp.GELU, QIRMOp.SILU):
                    # Fuse: matmul + bias + activation
                    fused_op = {
                        QIRMOp.RELU: QIRMOp.FUSED_BIAS_RELU,
                        QIRMOp.GELU: QIRMOp.FUSED_BIAS_GELU,
                    }.get(act_node.op)

                    if fused_op:
                        # Get bias input (the non-matmul input to ADD)
                        bias_input = [i for i in bias_node.input_ids if i != nid]
                        all_inputs = node.input_ids + tuple(bias_input)

                        graph.m_nodes[bias_succs[0]] = QIRMNode(
                            node_id=bias_succs[0],
                            op=fused_op,
                            input_ids=all_inputs,
                            tensor_type=act_node.tensor_type,
                            shape_inferred=True,
                            type_inferred=True,
                            attrs={**dict(node.attrs), "fused_matmul_epilogue": True},
                        )
                        to_remove.add(nid)
                        to_remove.add(succs[0])
                        fused += 1
                        continue

            # Just matmul + bias (no activation to fuse)
            bias_input = [i for i in bias_node.input_ids if i != nid]
            all_inputs = node.input_ids + tuple(bias_input)

            graph.m_nodes[succs[0]] = QIRMNode(
                node_id=succs[0],
                op=QIRMOp.FUSED_MUL_ADD,
                input_ids=all_inputs,
                tensor_type=bias_node.tensor_type,
                shape_inferred=True,
                type_inferred=True,
                attrs={**dict(node.attrs), "fused_matmul_bias": True},
            )
            to_remove.add(nid)
            fused += 1

        for nid in to_remove:
            del graph.m_nodes[nid]

        return PassResult(changed=fused > 0, stats={"fused_matmul_epilogues": fused})


class HToMLoweringPass(BasePass):
    """Wrap H→M lowering as a compiler pass."""
    name = "h_to_m_lower"
    action = PassAction.LOWER

    def run(self, graph: QIRGraph) -> PassResult:
        from src.qir.lower.h_to_m import lower_h_to_m
        had_m = len(graph.m_nodes)
        lower_h_to_m(graph)
        new_m = len(graph.m_nodes)
        return PassResult(
            changed=new_m > had_m,
            stats={"m_nodes_created": new_m - had_m},
        )


class MToLLoweringPass(BasePass):
    """Wrap M→L lowering as a compiler pass."""
    name = "m_to_l_lower"
    action = PassAction.LOWER

    def __init__(self, profile=None):
        self._profile = profile

    def run(self, graph: QIRGraph) -> PassResult:
        from src.qir.lower.m_to_l import lower_m_to_l
        had_l = len(graph.l_nodes)
        lower_m_to_l(graph, profile=self._profile)
        new_l = len(graph.l_nodes)
        return PassResult(
            changed=new_l > had_l,
            stats={"l_nodes_created": new_l - had_l},
        )

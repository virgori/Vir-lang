"""
QIR Lowering — H -> M -> L progressive IR lowering.
=====================================================
"""

from __future__ import annotations

from src.qir.module import QIRGraph
from src.qir.schema import QIRHNode, QIRMNode, TensorType
from src.qir.opcodes import QIRHOp, QIRMOp


# H-op -> M-op mapping for direct 1:1 lowerable ops
_H_TO_M: dict[QIRHOp, QIRMOp] = {
    QIRHOp.ADD: QIRMOp.ADD,
    QIRHOp.SUB: QIRMOp.SUB,
    QIRHOp.MUL: QIRMOp.MUL,
    QIRHOp.DIV: QIRMOp.DIV,
    QIRHOp.NEG: QIRMOp.NEG,
    QIRHOp.ABS: QIRMOp.ABS,
    QIRHOp.SQRT: QIRMOp.SQRT,
    QIRHOp.RSQRT: QIRMOp.RSQRT,
    QIRHOp.EXP: QIRMOp.EXP,
    QIRHOp.LOG: QIRMOp.LOG,
    QIRHOp.TANH: QIRMOp.TANH,
    QIRHOp.SIGMOID: QIRMOp.SIGMOID,
    QIRHOp.RELU: QIRMOp.RELU,
    QIRHOp.GELU: QIRMOp.GELU,
    QIRHOp.SILU: QIRMOp.SILU,
    QIRHOp.POW: QIRMOp.POW,
    QIRHOp.MAXIMUM: QIRMOp.MAXIMUM,
    QIRHOp.MINIMUM: QIRMOp.MINIMUM,
    QIRHOp.REDUCE_SUM: QIRMOp.REDUCE_SUM,
    QIRHOp.REDUCE_MEAN: QIRMOp.REDUCE_MEAN,
    QIRHOp.REDUCE_MAX: QIRMOp.REDUCE_MAX,
    QIRHOp.MATMUL: QIRMOp.MATMUL,
    QIRHOp.TRANSPOSE: QIRMOp.TRANSPOSE,
    QIRHOp.RESHAPE: QIRMOp.RESHAPE,
    QIRHOp.BROADCAST: QIRMOp.BROADCAST,
    QIRHOp.GATHER: QIRMOp.GATHER,
    QIRHOp.SCATTER: QIRMOp.SCATTER,
    QIRHOp.SLICE: QIRMOp.SLICE,
    QIRHOp.CONCAT: QIRMOp.CONCAT,
    QIRHOp.CAST: QIRMOp.CAST,
    QIRHOp.SOFTMAX: QIRMOp.REDUCE_MAX,  # placeholder: decomposed by pass
}


def lower_h_to_m(graph: QIRGraph) -> QIRGraph:
    """Lower QIR-H nodes to QIR-M canonical form.

    Composite ops (LINEAR, EMBEDDING, etc.) are decomposed.
    Direct ops are mapped 1:1 via _H_TO_M.
    """
    mid_id_counter = 1

    def alloc_mid() -> int:
        nonlocal mid_id_counter
        nid = mid_id_counter
        mid_id_counter += 1
        return nid

    # Map from H-node-id to M-node-id(s)
    h_to_m_map: dict[int, int] = {}

    for h_nid in graph.topo_order_h():
        h_node = graph.h_nodes.get(h_nid)
        if h_node is None:
            continue

        # Map input H-ids to M-ids
        m_inputs = tuple(h_to_m_map.get(inp, inp) for inp in h_node.input_ids)

        # PARAMETER / INPUT / CONSTANT: pass through
        if h_node.op in (QIRHOp.PARAMETER, QIRHOp.INPUT, QIRHOp.CONSTANT):
            m_nid = alloc_mid()
            graph.m_nodes[m_nid] = QIRMNode(
                node_id=m_nid, op=QIRMOp.COPY,
                input_ids=(), tensor_type=h_node.tensor_type,
                shape_inferred=True, type_inferred=True,
                alias_group=h_node.alias_group,
                inplace_safe=h_node.inplace_safe,
                lifetime_region=h_node.lifetime_region,
            )
            h_to_m_map[h_nid] = m_nid
            continue

        # LINEAR decomposition: x @ W^T + bias
        if h_node.op == QIRHOp.LINEAR:
            # Transpose weight
            w_mid = h_to_m_map.get(h_node.input_ids[1], h_node.input_ids[1])
            wt_nid = alloc_mid()
            w_node = graph.h_nodes.get(h_node.input_ids[1])
            wt_type = None
            if w_node and w_node.tensor_type and w_node.tensor_type.rank == 2:
                wt_type = w_node.tensor_type.with_shape(
                    (w_node.tensor_type.shape[1], w_node.tensor_type.shape[0]))
            graph.m_nodes[wt_nid] = QIRMNode(
                node_id=wt_nid, op=QIRMOp.TRANSPOSE,
                input_ids=(w_mid,), tensor_type=wt_type,
                shape_inferred=True, type_inferred=True,
            )
            # Matmul
            mm_nid = alloc_mid()
            graph.m_nodes[mm_nid] = QIRMNode(
                node_id=mm_nid, op=QIRMOp.MATMUL,
                input_ids=(m_inputs[0], wt_nid),
                tensor_type=h_node.tensor_type,
                shape_inferred=True, type_inferred=True,
            )
            # Add bias if present
            if len(h_node.input_ids) >= 3:
                bias_mid = h_to_m_map.get(h_node.input_ids[2], h_node.input_ids[2])
                add_nid = alloc_mid()
                graph.m_nodes[add_nid] = QIRMNode(
                    node_id=add_nid, op=QIRMOp.ADD,
                    input_ids=(mm_nid, bias_mid),
                    tensor_type=h_node.tensor_type,
                    shape_inferred=True, type_inferred=True,
                )
                h_to_m_map[h_nid] = add_nid
            else:
                h_to_m_map[h_nid] = mm_nid
            continue

        # Grad markers: skip (transparent)
        if h_node.op in (QIRHOp.GRAD_STOP, QIRHOp.SAVE_FOR_BACKWARD,
                         QIRHOp.ALIAS_BARRIER, QIRHOp.BUFFER_HINT):
            if m_inputs:
                h_to_m_map[h_nid] = m_inputs[0]
            continue

        # Direct mapping
        m_op = _H_TO_M.get(h_node.op)
        if m_op is not None:
            m_nid = alloc_mid()
            graph.m_nodes[m_nid] = QIRMNode(
                node_id=m_nid, op=m_op,
                input_ids=m_inputs,
                tensor_type=h_node.tensor_type,
                shape_inferred=True, type_inferred=True,
                alias_group=h_node.alias_group,
                inplace_safe=h_node.inplace_safe,
                lifetime_region=h_node.lifetime_region,
                attrs=h_node.attrs,
            )
            h_to_m_map[h_nid] = m_nid

    return graph

"""
QIR Lowering — M -> L (Mid-level to Low-level tiled/scheduled IR).
===================================================================
Converts canonical tensor ops into tiled, vectorized, schedulable form.
Uses CapabilityProfile to determine tile sizes and vector widths.
"""

from __future__ import annotations

from src.qir.module import QIRGraph
from src.qir.schema import QIRMNode, QIRLNode, TensorType
from src.qir.opcodes import QIRMOp, QIRLOp
from src.virplat.capability_profile import CapabilityProfile, VectorBackend


# M-op categories for dispatch
_UNARY_OPS = frozenset({
    QIRMOp.NEG, QIRMOp.ABS, QIRMOp.SQRT, QIRMOp.RSQRT,
    QIRMOp.EXP, QIRMOp.LOG, QIRMOp.TANH, QIRMOp.SIGMOID,
    QIRMOp.RELU, QIRMOp.GELU, QIRMOp.SILU,
})

_BINARY_OPS = frozenset({
    QIRMOp.ADD, QIRMOp.SUB, QIRMOp.MUL, QIRMOp.DIV,
    QIRMOp.POW, QIRMOp.MAXIMUM, QIRMOp.MINIMUM,
})

_REDUCE_OPS = frozenset({
    QIRMOp.REDUCE_SUM, QIRMOp.REDUCE_MEAN, QIRMOp.REDUCE_MAX,
})

_FUSED_EW_OPS = frozenset({
    QIRMOp.FUSED_MUL_ADD, QIRMOp.FUSED_BIAS_RELU, QIRMOp.FUSED_BIAS_GELU,
})


def lower_m_to_l(
    graph: QIRGraph,
    profile: CapabilityProfile | None = None,
) -> QIRGraph:
    """Lower QIR-M nodes to QIR-L tiled/scheduled form.

    Produces QIRLNode entries with tile sizes, vector widths,
    kernel family references, and scheduling metadata.

    Args:
        graph: QIRGraph with populated m_nodes.
        profile: Platform capability profile. Auto-detected if None.

    Returns:
        Same graph with l_nodes populated.
    """
    if profile is None:
        profile = CapabilityProfile.detect()

    tile_m = profile.tile_m
    tile_n = profile.tile_n
    tile_k = profile.tile_k
    vw = profile.vector_width_f32
    backend = profile.preferred_backend

    lid_counter = 1

    def alloc_lid() -> int:
        nonlocal lid_counter
        nid = lid_counter
        lid_counter += 1
        return nid

    # Map from M-node-id to primary L-node-id
    m_to_l_map: dict[int, int] = {}

    for mid in _topo_sort_m(graph):
        m_node = graph.m_nodes.get(mid)
        if m_node is None:
            continue

        # Map input M-ids to L-ids
        l_inputs = tuple(m_to_l_map.get(inp, inp) for inp in m_node.input_ids)

        # COPY: passthrough
        if m_node.op == QIRMOp.COPY:
            lid = alloc_lid()
            graph.l_nodes[lid] = QIRLNode(
                node_id=lid,
                op=QIRLOp.SCALAR_OP,
                input_ids=l_inputs,
                source_mid_id=mid,
                kernel_family="copy",
                attrs={"pass_through": True},
            )
            m_to_l_map[mid] = lid
            continue

        # ── MATMUL / BATCH_MATMUL → TILE_LOOP + MICRO_GEMM ─────────
        if m_node.op in (QIRMOp.MATMUL, QIRMOp.BATCH_MATMUL):
            m_dim = m_node.attrs.get("M", 1)
            k_dim = m_node.attrs.get("K", 1)
            n_dim = m_node.attrs.get("N", 1)

            # Infer from tensor_type if attrs not set
            if m_node.tensor_type and m_node.tensor_type.rank >= 2:
                if m_dim == 1 and n_dim == 1:
                    n_dim = m_node.tensor_type.shape[-1]
                    m_dim = m_node.tensor_type.shape[-2] if m_node.tensor_type.rank >= 2 else 1

            # Outer tile loop
            tile_lid = alloc_lid()
            graph.l_nodes[tile_lid] = QIRLNode(
                node_id=tile_lid,
                op=QIRLOp.TILE_LOOP,
                input_ids=l_inputs,
                tile_sizes=(tile_m, tile_n, tile_k),
                parallel_dim=0,  # parallel over M dimension
                source_mid_id=mid,
                attrs={"M": m_dim, "K": k_dim, "N": n_dim},
            )

            # Micro-GEMM kernel
            gemm_lid = alloc_lid()
            kernel_fam = _gemm_kernel_family(backend, tile_m, tile_n)
            graph.l_nodes[gemm_lid] = QIRLNode(
                node_id=gemm_lid,
                op=QIRLOp.MICRO_GEMM,
                input_ids=(tile_lid,),
                tile_sizes=(tile_m, tile_n, tile_k),
                vector_width=vw,
                kernel_family=kernel_fam,
                kernel_variant=f"m{tile_m}_n{tile_n}_k{tile_k}",
                source_mid_id=mid,
                attrs={"M": m_dim, "K": k_dim, "N": n_dim},
            )

            # Optional prefetch for large K
            if isinstance(k_dim, int) and k_dim > tile_k * 4:
                pf_lid = alloc_lid()
                graph.l_nodes[pf_lid] = QIRLNode(
                    node_id=pf_lid,
                    op=QIRLOp.PREFETCH,
                    input_ids=(gemm_lid,),
                    prefetch_distance=2,
                    source_mid_id=mid,
                )

            m_to_l_map[mid] = gemm_lid
            continue

        # ── Elementwise (unary/binary) → VECTOR_LOOP + MICRO_EW ────
        if m_node.op in _UNARY_OPS or m_node.op in _BINARY_OPS:
            numel = _infer_numel(m_node)

            # Vector loop wrapper
            vloop_lid = alloc_lid()
            graph.l_nodes[vloop_lid] = QIRLNode(
                node_id=vloop_lid,
                op=QIRLOp.VECTOR_LOOP,
                input_ids=l_inputs,
                vector_width=vw,
                source_mid_id=mid,
                attrs={"numel": numel, "m_op": m_node.op.name},
            )

            # Micro elementwise kernel
            ew_lid = alloc_lid()
            graph.l_nodes[ew_lid] = QIRLNode(
                node_id=ew_lid,
                op=QIRLOp.MICRO_EW,
                input_ids=(vloop_lid,),
                vector_width=vw,
                kernel_family=m_node.op.name.lower(),
                source_mid_id=mid,
                attrs={"numel": numel},
            )
            m_to_l_map[mid] = ew_lid
            continue

        # ── Fused elementwise → MICRO_EW with fused kernel ─────────
        if m_node.op in _FUSED_EW_OPS:
            numel = _infer_numel(m_node)
            ew_lid = alloc_lid()
            graph.l_nodes[ew_lid] = QIRLNode(
                node_id=ew_lid,
                op=QIRLOp.MICRO_EW,
                input_ids=l_inputs,
                vector_width=vw,
                kernel_family=m_node.op.name.lower(),
                source_mid_id=mid,
                attrs={"numel": numel, "fused": True},
            )
            m_to_l_map[mid] = ew_lid
            continue

        # ── Reduction → TILE + MICRO_REDUCE ─────────────────────────
        if m_node.op in _REDUCE_OPS:
            numel = _infer_input_numel(m_node, graph)

            # Parallel reduction over tiles
            tile_lid = alloc_lid()
            graph.l_nodes[tile_lid] = QIRLNode(
                node_id=tile_lid,
                op=QIRLOp.TILE_LOOP,
                input_ids=l_inputs,
                tile_sizes=(min(numel, tile_m * vw),),
                source_mid_id=mid,
                attrs={"numel": numel, "reduce_op": m_node.op.name},
            )

            red_lid = alloc_lid()
            graph.l_nodes[red_lid] = QIRLNode(
                node_id=red_lid,
                op=QIRLOp.MICRO_REDUCE,
                input_ids=(tile_lid,),
                vector_width=vw,
                kernel_family=m_node.op.name.lower(),
                source_mid_id=mid,
                attrs={"numel": numel},
            )
            m_to_l_map[mid] = red_lid
            continue

        # ── Memory ops → KERNEL_CALL ────────────────────────────────
        if m_node.op in (QIRMOp.ALLOC_BUFFER, QIRMOp.FREE_BUFFER):
            lid = alloc_lid()
            graph.l_nodes[lid] = QIRLNode(
                node_id=lid,
                op=QIRLOp.KERNEL_CALL,
                input_ids=l_inputs,
                kernel_family=m_node.op.name.lower(),
                source_mid_id=mid,
            )
            m_to_l_map[mid] = lid
            continue

        # ── Bounds check → BOUNDS_CHECK or eliminate ────────────────
        if m_node.op == QIRMOp.BOUNDS_CHECK:
            # If the node has a "bce_safe" annotation, skip emission entirely
            if m_node.attrs.get("bce_safe", False):
                # BCE proved this is safe — emit NOP/passthrough
                lid = alloc_lid()
                graph.l_nodes[lid] = QIRLNode(
                    node_id=lid,
                    op=QIRLOp.SCALAR_OP,
                    input_ids=l_inputs,
                    source_mid_id=mid,
                    kernel_family="nop",
                    attrs={"bce_eliminated": True},
                )
                m_to_l_map[mid] = lid
            else:
                # Emit actual bounds check at L-level
                lid = alloc_lid()
                graph.l_nodes[lid] = QIRLNode(
                    node_id=lid,
                    op=QIRLOp.BOUNDS_CHECK,
                    input_ids=l_inputs,
                    source_mid_id=mid,
                    kernel_family="bounds_check",
                    attrs=dict(m_node.attrs) if m_node.attrs else {},
                )
                m_to_l_map[mid] = lid
            continue

        # ── Data movement (reshape/transpose/etc.) → KERNEL_CALL ───
        # Vectorize gather/scatter when element count is high enough
        if m_node.op in (QIRMOp.GATHER, QIRMOp.SCATTER):
            numel = _infer_numel(m_node)
            if numel >= vw * 4:
                # Vectorized gather/scatter via VECTOR_LOOP + MICRO_EW
                vloop_lid = alloc_lid()
                graph.l_nodes[vloop_lid] = QIRLNode(
                    node_id=vloop_lid,
                    op=QIRLOp.VECTOR_LOOP,
                    input_ids=l_inputs,
                    vector_width=vw,
                    source_mid_id=mid,
                    attrs={"numel": numel, "m_op": m_node.op.name},
                )
                ew_lid = alloc_lid()
                graph.l_nodes[ew_lid] = QIRLNode(
                    node_id=ew_lid,
                    op=QIRLOp.MICRO_EW,
                    input_ids=(vloop_lid,),
                    vector_width=vw,
                    kernel_family=f"vec_{m_node.op.name.lower()}",
                    source_mid_id=mid,
                    attrs={"numel": numel, "vectorized": True},
                )
                m_to_l_map[mid] = ew_lid
                continue

        if m_node.op in (QIRMOp.TRANSPOSE, QIRMOp.RESHAPE, QIRMOp.BROADCAST,
                         QIRMOp.GATHER, QIRMOp.SCATTER, QIRMOp.SLICE,
                         QIRMOp.CONCAT, QIRMOp.CAST):
            lid = alloc_lid()
            graph.l_nodes[lid] = QIRLNode(
                node_id=lid,
                op=QIRLOp.KERNEL_CALL,
                input_ids=l_inputs,
                kernel_family=m_node.op.name.lower(),
                source_mid_id=mid,
                attrs=dict(m_node.attrs) if m_node.attrs else {},
            )
            m_to_l_map[mid] = lid
            continue

        # ── Fallback: SCALAR_OP ─────────────────────────────────────
        lid = alloc_lid()
        graph.l_nodes[lid] = QIRLNode(
            node_id=lid,
            op=QIRLOp.SCALAR_OP,
            input_ids=l_inputs,
            kernel_family=m_node.op.name.lower(),
            source_mid_id=mid,
            attrs=dict(m_node.attrs) if m_node.attrs else {},
        )
        m_to_l_map[mid] = lid

    return graph


# =============================================================================
#  Helpers
# =============================================================================

def _gemm_kernel_family(backend: VectorBackend, tile_m: int, tile_n: int) -> str:
    """Determine GEMM kernel family name based on backend."""
    backend_name = backend.name.lower()
    return f"gemm_{backend_name}_{tile_m}x{tile_n}"


def _infer_numel(node: QIRMNode) -> int:
    """Infer output element count from tensor_type."""
    if node.tensor_type:
        return node.tensor_type.numel
    return node.attrs.get("numel", 1)


def _infer_input_numel(node: QIRMNode, graph: QIRGraph) -> int:
    """Infer input element count for reductions."""
    if node.input_ids:
        inp_node = graph.m_nodes.get(node.input_ids[0])
        if inp_node and inp_node.tensor_type:
            return inp_node.tensor_type.numel
    return _infer_numel(node)


def _topo_sort_m(graph: QIRGraph) -> list[int]:
    """Kahn's algorithm on m_nodes."""
    in_degree: dict[int, int] = {}
    dependents: dict[int, list[int]] = {}

    for nid, node in graph.m_nodes.items():
        in_degree.setdefault(nid, 0)
        for dep in node.input_ids:
            if dep in graph.m_nodes:
                dependents.setdefault(dep, []).append(nid)
                in_degree[nid] = in_degree.get(nid, 0) + 1

    queue: list[int] = [n for n, d in in_degree.items() if d == 0]
    order: list[int] = []

    while queue:
        nid = queue.pop(0)
        order.append(nid)
        for dep in dependents.get(nid, []):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    return order

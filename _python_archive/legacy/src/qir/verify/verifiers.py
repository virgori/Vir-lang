"""
QIR Verifiers — Mandatory correctness checks before lowering.
================================================================
Per design plan §4.1.A.4:
  - Shape verifier
  - Type verifier
  - Alias verifier
  - Inplace legality verifier
  - Gradient legality verifier
  - Backend legality verifier
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.qir.module import QIRGraph
from src.qir.schema import QIRHNode, TensorType, DType
from src.qir.opcodes import QIRHOp


@dataclass
class VerifyError:
    node_id: int
    category: str
    message: str


@dataclass
class VerifyResult:
    passed: bool
    errors: list[VerifyError] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


# =============================================================================
#  Shape Verifier
# =============================================================================

class ShapeVerifier:
    """Verifies all nodes have resolved shapes and shapes are consistent."""

    def verify(self, graph: QIRGraph) -> VerifyResult:
        errors: list[VerifyError] = []

        for nid, node in graph.h_nodes.items():
            # PARAMETER, INPUT, CONSTANT must have tensor_type
            if node.op in (QIRHOp.PARAMETER, QIRHOp.INPUT, QIRHOp.CONSTANT):
                if node.tensor_type is None:
                    errors.append(VerifyError(nid, "shape",
                                              f"{node.op.name} node '{node.name}' missing tensor_type"))
                elif not node.tensor_type.shape:
                    errors.append(VerifyError(nid, "shape",
                                              f"{node.op.name} node '{node.name}' has empty shape"))
                continue

            # Compute ops should have been inferred
            if node.tensor_type is None:
                errors.append(VerifyError(nid, "shape",
                                          f"Node {nid} ({node.op.name}) has no inferred shape"))
                continue

            # Shape dimensions must be positive
            for i, d in enumerate(node.tensor_type.shape):
                if d <= 0:
                    errors.append(VerifyError(nid, "shape",
                                              f"Node {nid}: dim[{i}] = {d} (must be positive)"))

            # Matmul K-dimension check
            if node.op == QIRHOp.MATMUL and len(node.input_ids) >= 2:
                ta = self._get_type(graph, node.input_ids[0])
                tb = self._get_type(graph, node.input_ids[1])
                if ta and tb and ta.rank >= 2 and tb.rank >= 2:
                    if ta.shape[-1] != tb.shape[-2]:
                        errors.append(VerifyError(
                            nid, "shape",
                            f"MATMUL K-dim mismatch: {ta.shape}[-1]={ta.shape[-1]} "
                            f"vs {tb.shape}[-2]={tb.shape[-2]}"))

        return VerifyResult(passed=len(errors) == 0, errors=errors)

    @staticmethod
    def _get_type(graph: QIRGraph, nid: int) -> TensorType | None:
        node = graph.h_nodes.get(nid)
        return node.tensor_type if node else None


# =============================================================================
#  Type Verifier
# =============================================================================

class TypeVerifier:
    """Verifies dtype consistency across ops."""

    def verify(self, graph: QIRGraph) -> VerifyResult:
        errors: list[VerifyError] = []

        for nid, node in graph.h_nodes.items():
            if node.op == QIRHOp.CAST:
                continue  # Cast is the only op that changes dtype

            if len(node.input_ids) < 2:
                continue

            # For binary ops, dtypes should match
            types = [self._get_dtype(graph, inp) for inp in node.input_ids[:2]]
            if all(t is not None for t in types) and types[0] != types[1]:
                errors.append(VerifyError(nid, "type",
                                          f"Node {nid} ({node.op.name}): "
                                          f"dtype mismatch {types[0]} vs {types[1]}"))

        return VerifyResult(passed=len(errors) == 0, errors=errors)

    @staticmethod
    def _get_dtype(graph: QIRGraph, nid: int) -> DType | None:
        node = graph.h_nodes.get(nid)
        return node.tensor_type.dtype if node and node.tensor_type else None


# =============================================================================
#  Alias Verifier
# =============================================================================

class AliasVerifier:
    """Verifies alias group annotations are consistent (no conflicting writes)."""

    def verify(self, graph: QIRGraph) -> VerifyResult:
        errors: list[VerifyError] = []
        # Collect alias groups
        groups: dict[int, list[int]] = {}
        for nid, node in graph.h_nodes.items():
            if node.alias_group > 0:
                groups.setdefault(node.alias_group, []).append(nid)

        # Check: at most one mutable writer per alias group
        for gid, members in groups.items():
            mutable_count = sum(
                1 for nid in members
                if graph.h_nodes[nid].mutable
            )
            if mutable_count > 1:
                errors.append(VerifyError(
                    members[0], "alias",
                    f"Alias group {gid}: {mutable_count} mutable writers (max 1)"))

        return VerifyResult(passed=len(errors) == 0, errors=errors)


# =============================================================================
#  Inplace Legality Verifier
# =============================================================================

class InplaceLegalityVerifier:
    """Verifies inplace_safe annotations are actually safe."""

    def verify(self, graph: QIRGraph) -> VerifyResult:
        errors: list[VerifyError] = []

        # Build use-count per node
        use_count: dict[int, int] = {}
        for node in graph.h_nodes.values():
            for inp in node.input_ids:
                use_count[inp] = use_count.get(inp, 0) + 1

        for nid, node in graph.h_nodes.items():
            if not node.inplace_safe:
                continue
            # inplace_safe requires: input has exactly 1 consumer (this op)
            if node.input_ids:
                inp_id = node.input_ids[0]
                if use_count.get(inp_id, 0) > 1:
                    errors.append(VerifyError(
                        nid, "inplace",
                        f"Node {nid}: inplace_safe but input {inp_id} "
                        f"has {use_count[inp_id]} consumers"))
                # inplace_safe requires same shape
                inp_node = graph.h_nodes.get(inp_id)
                if inp_node and inp_node.tensor_type and node.tensor_type:
                    if inp_node.tensor_type.shape != node.tensor_type.shape:
                        errors.append(VerifyError(
                            nid, "inplace",
                            f"Node {nid}: inplace_safe but shape mismatch "
                            f"{inp_node.tensor_type.shape} vs {node.tensor_type.shape}"))

        return VerifyResult(passed=len(errors) == 0, errors=errors)


# =============================================================================
#  Gradient Legality Verifier
# =============================================================================

class GradientLegalityVerifier:
    """Verifies gradient annotations form a valid training graph."""

    def verify(self, graph: QIRGraph) -> VerifyResult:
        errors: list[VerifyError] = []

        for nid, node in graph.h_nodes.items():
            # requires_grad on non-float is suspicious
            if node.requires_grad and node.tensor_type:
                if not node.tensor_type.dtype.is_float:
                    errors.append(VerifyError(
                        nid, "grad",
                        f"Node {nid}: requires_grad on non-float dtype "
                        f"{node.tensor_type.dtype.name}"))

            # stop_gradient + requires_grad is contradictory
            if node.stop_gradient and node.requires_grad:
                errors.append(VerifyError(
                    nid, "grad",
                    f"Node {nid}: both stop_gradient and requires_grad set"))

        return VerifyResult(passed=len(errors) == 0, errors=errors)


# =============================================================================
#  Backend Legality Verifier
# =============================================================================

class BackendLegalityVerifier:
    """Verifies IR is legal for lowering to backend (no unsupported combos)."""

    # Ops that cannot be lowered directly (need decomposition)
    _COMPOSITE_OPS = frozenset({
        QIRHOp.LINEAR, QIRHOp.EMBEDDING, QIRHOp.ATTENTION, QIRHOp.MLP_BLOCK,
    })

    def verify(self, graph: QIRGraph, allow_composite: bool = True) -> VerifyResult:
        errors: list[VerifyError] = []

        for nid, node in graph.h_nodes.items():
            if not allow_composite and node.op in self._COMPOSITE_OPS:
                errors.append(VerifyError(
                    nid, "backend",
                    f"Node {nid}: composite op {node.op.name} must be lowered first"))

            # All inputs must exist
            for inp in node.input_ids:
                if inp not in graph.h_nodes:
                    errors.append(VerifyError(
                        nid, "backend",
                        f"Node {nid}: input {inp} not found in graph"))

        return VerifyResult(passed=len(errors) == 0, errors=errors)


# =============================================================================
#  Combined Verifier
# =============================================================================

class QIRVerifier:
    """Run all mandatory verifiers in sequence."""

    def __init__(self) -> None:
        self.shape = ShapeVerifier()
        self.type = TypeVerifier()
        self.alias = AliasVerifier()
        self.inplace = InplaceLegalityVerifier()
        self.gradient = GradientLegalityVerifier()
        self.backend = BackendLegalityVerifier()

    def verify_all(self, graph: QIRGraph, allow_composite: bool = True) -> VerifyResult:
        all_errors: list[VerifyError] = []
        for result in [
            self.shape.verify(graph),
            self.type.verify(graph),
            self.alias.verify(graph),
            self.inplace.verify(graph),
            self.gradient.verify(graph),
            self.backend.verify(graph, allow_composite),
        ]:
            all_errors.extend(result.errors)
        return VerifyResult(passed=len(all_errors) == 0, errors=all_errors)

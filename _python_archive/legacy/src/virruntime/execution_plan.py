"""
ExecutionPlan — Walk a QIR-M graph and execute node-by-node.
=============================================================
Simple interpreter-style execution: topological order,
dispatch each op through the Dispatcher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.qir.schema import QIRMNode, QIRMOp
from src.qir.module import QIRGraph
from src.virruntime.dispatcher import Dispatcher


@dataclass
class ExecutionPlan:
    """A concrete execution plan for a QIR-M graph."""

    graph: QIRGraph
    dispatcher: Dispatcher
    # node_id → result data
    values: dict[int, Any] = field(default_factory=dict)

    def bind_input(self, node_id: int, data: Any) -> None:
        self.values[node_id] = data

    def bind_inputs(self, inputs: dict[int, Any]) -> None:
        self.values.update(inputs)


def execute_plan(plan: ExecutionPlan) -> dict[int, Any]:
    """Execute all M-nodes in topological order.

    Returns mapping of node_id → computed value for output nodes.
    """
    graph = plan.graph
    disp = plan.dispatcher
    vals = plan.values

    # Simple topo sort on m_nodes via input dependencies
    executed: set[int] = set(vals.keys())
    m_sorted = _topo_sort_m(graph)

    _M_OP_MAP: dict[QIRMOp, str] = {
        QIRMOp.ADD: "add",
        QIRMOp.SUB: "sub",
        QIRMOp.MUL: "mul",
        QIRMOp.DIV: "div",
        QIRMOp.NEG: "neg",
        QIRMOp.ABS: "abs",
        QIRMOp.SQRT: "sqrt",
        QIRMOp.RSQRT: "rsqrt",
        QIRMOp.EXP: "exp",
        QIRMOp.LOG: "log",
        QIRMOp.RELU: "relu",
        QIRMOp.SIGMOID: "sigmoid",
        QIRMOp.TANH: "tanh",
        QIRMOp.GELU: "gelu",
        QIRMOp.SILU: "silu",
        QIRMOp.MATMUL: "matmul",
        QIRMOp.REDUCE_SUM: "reduce_sum",
        QIRMOp.REDUCE_MEAN: "reduce_mean",
        QIRMOp.REDUCE_MAX: "reduce_max",
        QIRMOp.SOFTMAX: "softmax",
        QIRMOp.LAYER_NORM: "layer_norm",
        QIRMOp.RMS_NORM: "rms_norm",
    }

    for nid in m_sorted:
        if nid in executed:
            continue
        node = graph.m_nodes[nid]

        if node.op == QIRMOp.COPY:
            # Pass-through (parameters, inputs, constants)
            if node.input_ids:
                vals[nid] = vals[node.input_ids[0]]
            continue

        op_name = _M_OP_MAP.get(node.op)
        if op_name is None:
            raise RuntimeError(f"No runtime mapping for QIRMOp.{node.op.name}")

        inp = [vals[i] for i in node.input_ids]

        if node.op == QIRMOp.MATMUL:
            # matmul expects (a_data, b_data, M, K, N)
            a, b = inp[0], inp[1]
            M = node.attrs.get("M", 1)
            K = node.attrs.get("K", 1)
            N = node.attrs.get("N", 1)
            vals[nid] = disp.dispatch(op_name, a, b, M, K, N)
        elif node.op in (QIRMOp.LAYER_NORM, QIRMOp.RMS_NORM):
            vals[nid] = disp.dispatch(op_name, *inp)
        elif len(inp) == 1:
            vals[nid] = disp.dispatch(op_name, inp[0])
        elif len(inp) == 2:
            vals[nid] = disp.dispatch(op_name, inp[0], inp[1])
        else:
            vals[nid] = disp.dispatch(op_name, *inp)

        executed.add(nid)

    return vals


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

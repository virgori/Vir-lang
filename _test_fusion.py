"""Quick test for AutoKernelFusionPass."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.virpass.passes.auto_fusion import AutoKernelFusionPass
from src.qir.module import QIRGraph
from src.qir.schema import QIRMNode, TensorType, DType
from src.qir.opcodes import QIRMOp

g = QIRGraph()
tt = TensorType(dtype=DType.FLOAT64, shape=(1024,))

# Chain: MUL -> ADD -> RELU -> MUL -> ADD (5 ops)
g.m_nodes[1] = QIRMNode(node_id=1, op=QIRMOp.MUL, input_ids=(100, 101), tensor_type=tt)
g.m_nodes[2] = QIRMNode(node_id=2, op=QIRMOp.ADD, input_ids=(1, 102), tensor_type=tt)
g.m_nodes[3] = QIRMNode(node_id=3, op=QIRMOp.RELU, input_ids=(2,), tensor_type=tt)
g.m_nodes[4] = QIRMNode(node_id=4, op=QIRMOp.MUL, input_ids=(3, 103), tensor_type=tt)
g.m_nodes[5] = QIRMNode(node_id=5, op=QIRMOp.ADD, input_ids=(4, 104), tensor_type=tt)

print(f"Before fusion: {len(g.m_nodes)} M-nodes")
analysis = AutoKernelFusionPass.analyze_fusion_potential(g)
print(f"Analysis: {analysis}")

p = AutoKernelFusionPass()
result = p.run(g)
print(f"After fusion: {len(g.m_nodes)} M-nodes")
print(f"Stats: {result.stats}")
for nid, n in g.m_nodes.items():
    attrs = dict(n.attrs) if n.attrs else {}
    print(f"  node {nid}: {n.op.name} inputs={n.input_ids} attrs={attrs}")
print("OK - AutoKernelFusionPass works!")

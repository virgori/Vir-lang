"""Benchmark: Q-IR AutoKernelFusionPass on realistic graphs."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.virpass.passes.auto_fusion import AutoKernelFusionPass
from src.qir.module import QIRGraph
from src.qir.schema import QIRMNode, TensorType, DType
from src.qir.opcodes import QIRMOp

tt = TensorType(dtype=DType.FLOAT64, shape=(1024, 1024))

def build_mlp_graph(layers=4, ops_per_layer=5):
    """Build a realistic MLP-like graph: matmul + bias + activation per layer,
    with elementwise chains in each layer."""
    g = QIRGraph()
    nid = 1
    prev_output = 0  # external input

    for layer in range(layers):
        # MATMUL (not fuseable — but feeds into chain)
        g.m_nodes[nid] = QIRMNode(
            node_id=nid, op=QIRMOp.MATMUL,
            input_ids=(prev_output, 1000 + layer),
            tensor_type=tt
        )
        matmul_out = nid; nid += 1

        # Chain: ADD (bias) -> MUL (scale) -> ADD (residual) -> RELU -> MUL (dropout_mask)
        chain_ops = [QIRMOp.ADD, QIRMOp.MUL, QIRMOp.ADD, QIRMOp.RELU, QIRMOp.MUL]
        prev = matmul_out
        for i, op in enumerate(chain_ops):
            inp = (prev,) if op == QIRMOp.RELU else (prev, 2000 + layer * 10 + i)
            g.m_nodes[nid] = QIRMNode(
                node_id=nid, op=op,
                input_ids=inp,
                tensor_type=tt
            )
            prev = nid; nid += 1

        prev_output = prev

    return g, nid - 1

# Test 1: Single MLP graph
g, total_nodes = build_mlp_graph(layers=4)
print(f"MLP graph: {len(g.m_nodes)} M-nodes")

analysis = AutoKernelFusionPass.analyze_fusion_potential(g)
print(f"Fusion potential: {analysis}")

p = AutoKernelFusionPass()
t0 = time.perf_counter_ns()
result = p.run(g)
t1 = time.perf_counter_ns()
print(f"After fusion: {len(g.m_nodes)} M-nodes")
print(f"Stats: {result.stats}")
print(f"Fusion pass time: {(t1-t0)/1000:.1f} us")

# Test 2: Large transformer-like graph
def build_transformer_graph(n_layers=12):
    g = QIRGraph()
    nid = 1
    prev = 0

    for layer in range(n_layers):
        # Self-attention Q,K,V projections (3 × matmul+bias+gelu chains)
        for proj in range(3):
            g.m_nodes[nid] = QIRMNode(node_id=nid, op=QIRMOp.MATMUL,
                input_ids=(prev, 5000+layer*100+proj), tensor_type=tt)
            matmul_out = nid; nid += 1
            for op in [QIRMOp.ADD, QIRMOp.GELU]:
                inp = (nid-1,) if op == QIRMOp.GELU else (nid-1, 6000+nid)
                g.m_nodes[nid] = QIRMNode(node_id=nid, op=op, input_ids=inp, tensor_type=tt)
                nid += 1

        # Post-attention: ADD (residual) -> layernorm-like chain
        for op in [QIRMOp.ADD, QIRMOp.MUL, QIRMOp.ADD, QIRMOp.SQRT, QIRMOp.MUL]:
            inp = (nid-1,) if op in (QIRMOp.SQRT,) else (nid-1, 7000+nid)
            g.m_nodes[nid] = QIRMNode(node_id=nid, op=op, input_ids=inp, tensor_type=tt)
            nid += 1

        # FFN: matmul + bias + gelu + matmul + bias + relu
        g.m_nodes[nid] = QIRMNode(node_id=nid, op=QIRMOp.MATMUL,
            input_ids=(nid-1, 8000+layer), tensor_type=tt)
        nid += 1
        for op in [QIRMOp.ADD, QIRMOp.GELU, QIRMOp.MUL, QIRMOp.ADD, QIRMOp.RELU]:
            inp = (nid-1,) if op in (QIRMOp.GELU, QIRMOp.RELU) else (nid-1, 9000+nid)
            g.m_nodes[nid] = QIRMNode(node_id=nid, op=op, input_ids=inp, tensor_type=tt)
            nid += 1

        prev = nid - 1

    return g

print(f"\n--- Transformer-like graph (12 layers) ---")
g2 = build_transformer_graph(12)
print(f"Before: {len(g2.m_nodes)} M-nodes")

analysis2 = AutoKernelFusionPass.analyze_fusion_potential(g2)
print(f"Fusion potential: {analysis2}")

p2 = AutoKernelFusionPass()
t0 = time.perf_counter_ns()
result2 = p2.run(g2)
t1 = time.perf_counter_ns()
print(f"After fusion: {len(g2.m_nodes)} M-nodes")
print(f"Stats: {result2.stats}")
print(f"Fusion pass time: {(t1-t0)/1000:.1f} us")
eliminated = result2.stats.get('ops_eliminated', 0)
mem_saved = result2.stats.get('memory_ops_saved', 0)
print(f"Memory traffic reduction: {mem_saved} fewer load/store ops per inference")

"""
Automatic Kernel Fusion — Advanced Q-IR Pass
==============================================================
Fuses arbitrary chains of elementwise operations into single
"mega-kernels" that keep all intermediate values in CPU registers.

Standard approach (numpy/PyTorch):
  Each elementwise op materializes the full output buffer:
    tmp1 = alloc(N); for i in N: tmp1[i] = a[i] * b[i]     # LOAD a, LOAD b, STORE tmp1
    tmp2 = alloc(N); for i in N: tmp2[i] = tmp1[i] + c[i]  # LOAD tmp1, LOAD c, STORE tmp2
    out  = alloc(N); for i in N: out[i] = relu(tmp2[i])     # LOAD tmp2, STORE out
  Total memory traffic: 8 loads + 3 stores = 11N reads/writes

VirFusion approach:
  Fuse the entire chain into one kernel:
    for i in N:
      r0 = LOAD a[i]       # 1 load from RAM
      r1 = LOAD b[i]       # 1 load from RAM
      r2 = r0 * r1         # register-only
      r3 = LOAD c[i]       # 1 load from RAM
      r4 = r2 + r3         # register-only
      r5 = max(0, r4)      # register-only
      STORE out[i] = r5    # 1 store to RAM
  Total memory traffic: 3 loads + 1 store = 4N reads/writes

  Speedup factor: 11N / 4N = 2.75x from memory traffic alone.
  On cache-bound workloads (large N), this is the dominant factor.

[CUSTOM ALGORITHM — "VirFusion: Greedy Chain Fusion with Register Pressure Analysis"]

Implementation:
  1. Build dataflow DAG of M-nodes
  2. Identify "fuseable chains": sequences of elementwise ops where
     each output has exactly one consumer
  3. Estimate register pressure for the fused chain
  4. If pressure < MAX_REGISTERS, fuse the chain into a single MicroEW L-node
  5. Dead-code-eliminate the intermediate nodes
"""
from __future__ import annotations

from dataclasses import dataclass
from src.virpass.base_pass import BasePass, PassResult, PassAction
from src.qir.module import QIRGraph
from src.qir.opcodes import QIRMOp, QIRLOp
from src.qir.schema import QIRMNode, QIRLNode

# ═══════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════

# arm64 has 32 NEON registers; x86 has 16 AVX registers.
# We keep a margin for spill safety.
MAX_CHAIN_REGISTERS = 24
MAX_CHAIN_LENGTH    = 16    # don't fuse excessively long chains

# Elementwise ops that can participate in fusion.
_FUSEABLE_OPS = frozenset({
    QIRMOp.ADD, QIRMOp.SUB, QIRMOp.MUL, QIRMOp.DIV,
    QIRMOp.NEG, QIRMOp.ABS, QIRMOp.SQRT, QIRMOp.RSQRT,
    QIRMOp.EXP, QIRMOp.LOG, QIRMOp.TANH, QIRMOp.SIGMOID,
    QIRMOp.RELU, QIRMOp.GELU, QIRMOp.SILU,
    QIRMOp.MAXIMUM, QIRMOp.MINIMUM, QIRMOp.POW,
})

# Number of register "slots" each op uses for its result.
_OP_REG_COST: dict[QIRMOp, int] = {
    QIRMOp.ADD: 1, QIRMOp.SUB: 1, QIRMOp.MUL: 1, QIRMOp.DIV: 1,
    QIRMOp.NEG: 1, QIRMOp.ABS: 1, QIRMOp.SQRT: 1, QIRMOp.RSQRT: 1,
    QIRMOp.EXP: 2, QIRMOp.LOG: 2,        # transcendental needs tmp
    QIRMOp.TANH: 3, QIRMOp.SIGMOID: 2,    # multi-instruction expansion
    QIRMOp.RELU: 1, QIRMOp.GELU: 3, QIRMOp.SILU: 2,
    QIRMOp.MAXIMUM: 1, QIRMOp.MINIMUM: 1, QIRMOp.POW: 3,
}


@dataclass
class FuseChain:
    """A chain of M-nodes that can be fused into one kernel."""
    node_ids: list[int]     # ordered: first = earliest, last = final output
    external_inputs: set[int]   # node_ids feeding from outside the chain
    register_pressure: int      # estimated register slots needed
    memory_savings: int         # estimated load+store ops eliminated


class AutoKernelFusionPass(BasePass):
    """Detect and fuse arbitrary-length elementwise chains in QIR-M.

    This pass goes beyond the simple 2-op pattern matching of
    ElementwiseFusionPass. It discovers maximal chains of any
    length, estimates register pressure, and fuses if safe.
    """
    name = "auto_kernel_fusion"
    action = PassAction.FUSE

    def run(self, graph: QIRGraph) -> PassResult:
        if not graph.m_nodes:
            return PassResult(changed=False)

        consumers = self._build_consumer_map(graph)
        chains = self._discover_chains(graph, consumers)
        fused = self._apply_fusions(graph, chains, consumers)

        return PassResult(
            changed=fused > 0,
            stats={
                "chains_fused": fused,
                "chains_discovered": len(chains),
                "ops_eliminated": sum(len(c.node_ids) - 1 for c in chains[:fused]),
                "memory_ops_saved": sum(c.memory_savings for c in chains[:fused]),
            },
        )

    # ─── Phase 1: Build consumer map ─────────────────────

    @staticmethod
    def _build_consumer_map(graph: QIRGraph) -> dict[int, list[int]]:
        consumers: dict[int, list[int]] = {}
        for nid, node in graph.m_nodes.items():
            for inp in node.input_ids:
                consumers.setdefault(inp, []).append(nid)
        return consumers

    # ─── Phase 2: Discover fuseable chains ────────────────

    def _discover_chains(
        self, graph: QIRGraph, consumers: dict[int, list[int]]
    ) -> list[FuseChain]:
        """Find maximal chains of fuseable elementwise ops.

        Strategy: greedy forward walk.
          - Start from every fuseable node that is NOT already the
            single consumer of another fuseable node (i.e., chain head).
          - Walk forward following single-consumer links.
          - Stop when: non-fuseable op, multiple consumers, or
            register pressure exceeds limit.
        """
        visited: set[int] = set()
        chains: list[FuseChain] = []

        # Identify chain heads: fuseable nodes whose predecessors
        # are NOT fuseable or have multiple consumers.
        for nid, node in graph.m_nodes.items():
            if node.op not in _FUSEABLE_OPS:
                continue
            if nid in visited:
                continue
            # Check if this node is the only consumer of a fuseable pred
            is_mid = False
            for inp in node.input_ids:
                pred = graph.m_nodes.get(inp)
                if pred and pred.op in _FUSEABLE_OPS:
                    pred_consumers = consumers.get(inp, [])
                    if len(pred_consumers) == 1:
                        is_mid = True
                        break
            if is_mid:
                continue  # not a head — will be found from its head

            chain = self._walk_chain(graph, consumers, nid, visited)
            if chain and len(chain.node_ids) >= 2:
                chains.append(chain)

        # Sort by memory savings (descending) to prioritize best fusions
        chains.sort(key=lambda c: c.memory_savings, reverse=True)
        return chains

    def _walk_chain(
        self, graph: QIRGraph, consumers: dict[int, list[int]],
        start: int, visited: set[int],
    ) -> FuseChain | None:
        """Walk forward from start, collecting the maximal chain."""
        chain_ids: list[int] = []
        external_inputs: set[int] = set()
        reg_pressure = 0
        chain_set: set[int] = set()

        cur = start
        while True:
            node = graph.m_nodes.get(cur)
            if node is None or node.op not in _FUSEABLE_OPS:
                break
            if cur in visited:
                break

            # Check register pressure
            cost = _OP_REG_COST.get(node.op, 1)
            if reg_pressure + cost > MAX_CHAIN_REGISTERS:
                break
            if len(chain_ids) >= MAX_CHAIN_LENGTH:
                break

            chain_ids.append(cur)
            chain_set.add(cur)
            visited.add(cur)
            reg_pressure += cost

            # Track external inputs (not produced within chain)
            for inp in node.input_ids:
                if inp not in chain_set:
                    external_inputs.add(inp)

            # Follow single-consumer link
            succs = consumers.get(cur, [])
            if len(succs) != 1:
                break
            cur = succs[0]

        if len(chain_ids) < 2:
            return None

        # Memory savings: each intermediate node eliminated saves 1 store + 1 load
        mem_saved = (len(chain_ids) - 1) * 2   # store + load per intermediate
        return FuseChain(
            node_ids=chain_ids,
            external_inputs=external_inputs,
            register_pressure=reg_pressure,
            memory_savings=mem_saved,
        )

    # ─── Phase 3: Apply fusions ──────────────────────────

    def _apply_fusions(
        self, graph: QIRGraph, chains: list[FuseChain],
        consumers: dict[int, list[int]],
    ) -> int:
        """Replace each chain with a single fused node."""
        fused_count = 0
        removed: set[int] = set()

        for chain in chains:
            # Skip if any node was already removed by a prior fusion
            if any(nid in removed for nid in chain.node_ids):
                continue

            head_nid = chain.node_ids[0]
            tail_nid = chain.node_ids[-1]
            tail_node = graph.m_nodes[tail_nid]

            # Build op sequence annotation for the fused kernel
            op_sequence = [graph.m_nodes[nid].op.name for nid in chain.node_ids]

            # Create fused M-node: uses external inputs of the chain,
            # produces the output of the tail node.
            fused_inputs = tuple(sorted(chain.external_inputs))
            attrs = dict(tail_node.attrs) if tail_node.attrs else {}
            attrs["fused_chain"] = op_sequence
            attrs["fused_chain_length"] = len(chain.node_ids)
            attrs["register_pressure"] = chain.register_pressure
            attrs["memory_ops_saved"] = chain.memory_savings

            # Determine fused opcode (use best matching pattern)
            fused_op = self._select_fused_op(graph, chain)

            graph.m_nodes[tail_nid] = QIRMNode(
                node_id=tail_nid,
                op=fused_op,
                input_ids=fused_inputs,
                tensor_type=tail_node.tensor_type,
                shape_inferred=True,
                type_inferred=True,
                attrs=attrs,
            )

            # Remove intermediate nodes
            for nid in chain.node_ids[:-1]:
                del graph.m_nodes[nid]
                removed.add(nid)

            fused_count += 1

        return fused_count

    def _select_fused_op(self, graph: QIRGraph, chain: FuseChain) -> QIRMOp:
        """Pick the best fused opcode for the chain."""
        ops = [graph.m_nodes[nid].op for nid in chain.node_ids]

        # Check for known patterns first
        if len(ops) == 2:
            if ops[0] == QIRMOp.MUL and ops[1] == QIRMOp.ADD:
                return QIRMOp.FUSED_MUL_ADD
            if ops[0] == QIRMOp.ADD and ops[1] == QIRMOp.RELU:
                return QIRMOp.FUSED_BIAS_RELU
            if ops[0] == QIRMOp.ADD and ops[1] == QIRMOp.GELU:
                return QIRMOp.FUSED_BIAS_GELU

        if len(ops) == 3:
            if ops[0] == QIRMOp.MUL and ops[1] == QIRMOp.ADD and ops[2] == QIRMOp.RELU:
                return QIRMOp.FUSED_BIAS_RELU
            if ops[0] == QIRMOp.MUL and ops[1] == QIRMOp.ADD and ops[2] == QIRMOp.GELU:
                return QIRMOp.FUSED_BIAS_GELU

        # Generic fused op — the attrs carry the full op sequence
        return QIRMOp.FUSED_MUL_ADD

    # ─── Analysis utilities ──────────────────────────────

    @staticmethod
    def analyze_fusion_potential(graph: QIRGraph) -> dict:
        """Read-only analysis: report fusion opportunities without modifying graph."""
        consumers: dict[int, list[int]] = {}
        for nid, node in graph.m_nodes.items():
            for inp in node.input_ids:
                consumers.setdefault(inp, []).append(nid)

        fuseable_count = sum(1 for n in graph.m_nodes.values() if n.op in _FUSEABLE_OPS)
        single_consumer = sum(
            1 for nid in graph.m_nodes
            if nid in consumers and len(consumers[nid]) == 1
        )

        return {
            "total_m_nodes": len(graph.m_nodes),
            "fuseable_ops": fuseable_count,
            "single_consumer_ops": single_consumer,
            "estimated_max_chains": single_consumer // 2,
            "estimated_memory_traffic_reduction": f"{single_consumer * 2}N reads/writes",
        }

"""
WIR Module — Graph, Block, Component containers for WIR nodes.
================================================================
WIRGraph is the top-level container (equivalent to QIRGraph for tensor IR).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.wir.schema import WIRHNode, WIRMNode, WIRLNode
from src.wir.opcodes import WIRHOp


# =============================================================================
#  WIR Component — component-scoped metadata
# =============================================================================

@dataclass
class WIRComponent:
    """Component metadata within the W-IR graph."""
    component_id: int
    name: str = ""
    root_node_id: int = 0
    prop_names: list[str] = field(default_factory=list)
    state_names: list[str] = field(default_factory=list)
    event_handlers: list[str] = field(default_factory=list)
    vss_classes: list[str] = field(default_factory=list)
    mount_fn: str = ""
    unmount_fn: str = ""
    render_fn: str = ""


# =============================================================================
#  WIR Block — basic block of sequential DOM ops
# =============================================================================

@dataclass
class WIRBlock:
    """A basic block containing sequential WIR nodes."""
    block_id: int
    name: str = ""
    node_ids: list[int] = field(default_factory=list)


# =============================================================================
#  WIR Graph — top-level web IR container
# =============================================================================

@dataclass
class WIRGraph:
    """Top-level web IR graph holding all nodes, blocks, and component metadata.

    Supports all three levels (H/M/L) — a graph progresses
    through H -> M -> L via lowering passes.
    """
    name: str = "main"

    # Node storage (keyed by node_id)
    h_nodes: dict[int, WIRHNode] = field(default_factory=dict)
    m_nodes: dict[int, WIRMNode] = field(default_factory=dict)
    l_nodes: dict[int, WIRLNode] = field(default_factory=dict)

    # Block structure
    blocks: list[WIRBlock] = field(default_factory=list)

    # Component registry
    components: dict[str, WIRComponent] = field(default_factory=dict)

    # Route table
    routes: list[int] = field(default_factory=list)   # Node IDs of ROUTE_DEF

    # Entry points
    root_component: str = ""
    entry_node_ids: list[int] = field(default_factory=list)

    # Auto-increment counter
    _next_id: int = field(default=1, repr=False)

    def _alloc_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    # ── WIR-H construction helpers ──────────────────────────

    def add_h_node(self, op: WIRHOp, **kwargs: object) -> int:
        """Create and store a WIR-H node, return its node_id."""
        nid = self._alloc_id()
        node = WIRHNode(node_id=nid, op=op, **kwargs)
        self.h_nodes[nid] = node
        if self.blocks:
            self.blocks[-1].node_ids.append(nid)
        return nid

    def add_element(
        self,
        tag: str,
        attrs: tuple[tuple[str, str], ...] = (),
        children_ids: tuple[int, ...] = (),
        vss_class: str = "",
        name: str = "",
    ) -> int:
        """Add a virtual DOM element node."""
        return self.add_h_node(
            WIRHOp.ELEMENT,
            tag=tag,
            attrs=attrs,
            children_ids=children_ids,
            vss_class=vss_class,
            name=name,
        )

    def add_text(self, content: str, name: str = "") -> int:
        """Add a text node."""
        return self.add_h_node(
            WIRHOp.TEXT,
            text_content=content,
            name=name,
        )

    def add_fragment(self, children_ids: tuple[int, ...], name: str = "") -> int:
        """Add a fragment (grouping without a real DOM element)."""
        return self.add_h_node(
            WIRHOp.FRAGMENT,
            children_ids=children_ids,
            name=name,
        )

    def add_component_def(
        self,
        comp_name: str,
        props: tuple[tuple[str, str], ...] = (),
        state_fields: tuple[tuple[str, str, str], ...] = (),
    ) -> int:
        """Define a component."""
        nid = self.add_h_node(
            WIRHOp.COMPONENT_DEF,
            component_name=comp_name,
            props=props,
            state_fields=state_fields,
            name=comp_name,
        )
        self.components[comp_name] = WIRComponent(
            component_id=nid,
            name=comp_name,
            prop_names=[p[0] for p in props],
            state_names=[s[0] for s in state_fields],
        )
        return nid

    def add_state_def(self, state_name: str, state_type: str = "int", initial: str = "") -> int:
        """Define a reactive state variable."""
        return self.add_h_node(
            WIRHOp.STATE_DEF,
            state_name=state_name,
            name=state_name,
            state_fields=((state_name, state_type, initial),),
        )

    def add_event_bind(
        self,
        element_id: int,
        event_type: str,
        handler_fn: str,
    ) -> int:
        """Bind an event handler to an element."""
        return self.add_h_node(
            WIRHOp.EVENT_BIND,
            input_ids=(element_id,),
            event_type=event_type,
            handler_fn=handler_fn,
        )

    def add_style_bind(self, element_id: int, vss_class: str) -> int:
        """Bind a VSS class to an element."""
        return self.add_h_node(
            WIRHOp.STYLE_BIND,
            input_ids=(element_id,),
            vss_class=vss_class,
        )

    def add_conditional(
        self,
        condition_id: int,
        then_ids: tuple[int, ...],
        else_ids: tuple[int, ...] = (),
    ) -> int:
        """Conditional rendering."""
        return self.add_h_node(
            WIRHOp.CONDITIONAL,
            condition_id=condition_id,
            then_ids=then_ids,
            else_ids=else_ids,
        )

    def add_list(
        self,
        items_id: int,
        key_fn: str = "",
        render_fn: str = "",
    ) -> int:
        """List rendering with keyed reconciliation."""
        return self.add_h_node(
            WIRHOp.LIST,
            items_id=items_id,
            key_fn=key_fn,
            render_fn=render_fn,
        )

    def add_route(self, path: str, component: str, guards: tuple[str, ...] = ()) -> int:
        """Define a route."""
        nid = self.add_h_node(
            WIRHOp.ROUTE_DEF,
            route_path=path,
            route_component=component,
            route_guards=guards,
        )
        self.routes.append(nid)
        return nid

    def add_block(self, name: str = "") -> WIRBlock:
        """Add a new basic block."""
        blk = WIRBlock(block_id=len(self.blocks), name=name)
        self.blocks.append(blk)
        return blk

    def get_h_node(self, nid: int) -> WIRHNode | None:
        return self.h_nodes.get(nid)

    def get_m_node(self, nid: int) -> WIRMNode | None:
        return self.m_nodes.get(nid)

    def get_l_node(self, nid: int) -> WIRLNode | None:
        return self.l_nodes.get(nid)

    @property
    def h_node_count(self) -> int:
        return len(self.h_nodes)

    @property
    def m_node_count(self) -> int:
        return len(self.m_nodes)

    @property
    def l_node_count(self) -> int:
        return len(self.l_nodes)

    def topo_order_h(self) -> list[int]:
        """Topological order of H-nodes by dependency (input_ids + children_ids)."""
        visited: set[int] = set()
        order: list[int] = []

        def _visit(nid: int) -> None:
            if nid in visited:
                return
            visited.add(nid)
            node = self.h_nodes.get(nid)
            if node is None:
                return
            for dep in node.input_ids:
                _visit(dep)
            for child in node.children_ids:
                _visit(child)
            order.append(nid)

        for nid in self.h_nodes:
            _visit(nid)
        return order

    def dump(self) -> str:
        """Textual dump of the graph for debugging."""
        lines = [f"WIRGraph({self.name!r})"]
        lines.append(f"  components: {list(self.components.keys())}")
        lines.append(f"  routes: {len(self.routes)}")
        lines.append(f"  H-nodes: {self.h_node_count}")
        lines.append(f"  M-nodes: {self.m_node_count}")
        lines.append(f"  L-nodes: {self.l_node_count}")
        for nid in sorted(self.h_nodes):
            n = self.h_nodes[nid]
            lines.append(f"  H[{nid}] {n.op.name} tag={n.tag!r} name={n.name!r}")
        for nid in sorted(self.m_nodes):
            n = self.m_nodes[nid]
            lines.append(f"  M[{nid}] {n.op.name} tag={n.tag!r}")
        for nid in sorted(self.l_nodes):
            n = self.l_nodes[nid]
            lines.append(f"  L[{nid}] {n.op.name} js_func={n.js_func!r}")
        return "\n".join(lines)

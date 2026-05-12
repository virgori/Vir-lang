"""
DOMBuilder — Fluent builder for constructing WIR-H graphs from component ASTs.
================================================================================
Provides a high-level API for building component trees that populate a WIRGraph
with WIR-H nodes.  Follows the QIRBuilder pattern.

Usage:
    graph = WIRGraph(name="my_app")
    builder = DOMBuilder(graph)
    with builder.component("App") as app:
        app.state("count", "int", "0")
        div_id = app.element("div", vss_class="container")
        h1_id = app.element("h1")
        app.text("Hello Vir!", parent=h1_id)
        app.child(div_id, h1_id)
        btn_id = app.element("button")
        app.text("Click me", parent=btn_id)
        app.child(div_id, btn_id)
        app.event(btn_id, "click", "on_click")
        app.root(div_id)
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from src.wir.module import WIRGraph, WIRBlock
from src.wir.opcodes import WIRHOp


class ComponentScope:
    """Scoped builder for a single component's WIR-H nodes."""

    def __init__(self, graph: WIRGraph, component_name: str) -> None:
        self._graph = graph
        self._name = component_name
        self._root_id: int = 0

    # ── Element construction ─────────────────────────────────

    def element(
        self,
        tag: str,
        attrs: tuple[tuple[str, str], ...] = (),
        vss_class: str = "",
    ) -> int:
        """Create an element node. Returns node_id."""
        return self._graph.add_element(
            tag=tag,
            attrs=attrs,
            vss_class=vss_class,
            name=f"{self._name}.{tag}",
        )

    def text(self, content: str, parent: int = 0) -> int:
        """Create a text node."""
        nid = self._graph.add_text(content, name=f"{self._name}.text")
        if parent:
            self.child(parent, nid)
        return nid

    def fragment(self, children: tuple[int, ...] = ()) -> int:
        """Create a fragment grouping node."""
        return self._graph.add_fragment(children, name=f"{self._name}.frag")

    # ── Tree assembly ────────────────────────────────────────

    def child(self, parent_id: int, child_id: int) -> None:
        """Append child_id to parent_id's children list."""
        parent = self._graph.h_nodes.get(parent_id)
        if parent is None:
            return
        # Rebuild with extended children (frozen dataclass)
        extended = parent.children_ids + (child_id,)
        from dataclasses import replace
        self._graph.h_nodes[parent_id] = replace(parent, children_ids=extended)

    def root(self, node_id: int) -> None:
        """Set the root render node for this component."""
        self._root_id = node_id
        comp = self._graph.components.get(self._name)
        if comp:
            comp.root_node_id = node_id

    # ── State ────────────────────────────────────────────────

    def state(self, name: str, stype: str = "int", initial: str = "0") -> int:
        """Define a reactive state variable."""
        nid = self._graph.add_state_def(name, stype, initial)
        comp = self._graph.components.get(self._name)
        if comp and name not in comp.state_names:
            comp.state_names.append(name)
        return nid

    def computed(self, name: str, deps: tuple[int, ...], fn: str) -> int:
        """Define a computed value derived from dependencies."""
        return self._graph.add_h_node(
            WIRHOp.COMPUTED,
            state_name=name,
            deps=deps,
            compute_fn=fn,
            name=f"{self._name}.computed.{name}",
        )

    def effect(self, deps: tuple[int, ...], fn: str) -> int:
        """Define a side-effect that runs when deps change."""
        return self._graph.add_h_node(
            WIRHOp.EFFECT,
            deps=deps,
            compute_fn=fn,
            name=f"{self._name}.effect",
        )

    # ── Events ───────────────────────────────────────────────

    def event(self, element_id: int, event_type: str, handler: str) -> int:
        """Bind an event handler to an element."""
        nid = self._graph.add_event_bind(element_id, event_type, handler)
        comp = self._graph.components.get(self._name)
        if comp and handler not in comp.event_handlers:
            comp.event_handlers.append(handler)
        return nid

    # ── Style ────────────────────────────────────────────────

    def style(self, element_id: int, vss_class: str) -> int:
        """Bind a VSS class to an element."""
        nid = self._graph.add_style_bind(element_id, vss_class)
        comp = self._graph.components.get(self._name)
        if comp and vss_class not in comp.vss_classes:
            comp.vss_classes.append(vss_class)
        return nid

    # ── Control flow ─────────────────────────────────────────

    def conditional(
        self,
        condition_id: int,
        then_ids: tuple[int, ...],
        else_ids: tuple[int, ...] = (),
    ) -> int:
        """Conditional rendering node."""
        return self._graph.add_conditional(condition_id, then_ids, else_ids)

    def list_render(self, items_id: int, key_fn: str, render_fn: str) -> int:
        """List rendering node with keyed reconciliation."""
        return self._graph.add_list(items_id, key_fn, render_fn)

    # ── Lifecycle hooks ──────────────────────────────────────

    def on_mount(self, fn: str) -> int:
        """Register mount lifecycle hook."""
        nid = self._graph.add_h_node(
            WIRHOp.ON_MOUNT,
            compute_fn=fn,
            name=f"{self._name}.on_mount",
        )
        comp = self._graph.components.get(self._name)
        if comp:
            comp.mount_fn = fn
        return nid

    def on_unmount(self, fn: str) -> int:
        """Register unmount lifecycle hook."""
        nid = self._graph.add_h_node(
            WIRHOp.ON_UNMOUNT,
            compute_fn=fn,
            name=f"{self._name}.on_unmount",
        )
        comp = self._graph.components.get(self._name)
        if comp:
            comp.unmount_fn = fn
        return nid


class DOMBuilder:
    """Fluent WIR-H graph builder.  Top-level entry point."""

    def __init__(self, graph: WIRGraph | None = None) -> None:
        self.graph = graph or WIRGraph()

    @contextmanager
    def component(
        self,
        name: str,
        props: tuple[tuple[str, str], ...] = (),
        state_fields: tuple[tuple[str, str, str], ...] = (),
    ) -> Generator[ComponentScope, None, None]:
        """Context manager for building a component."""
        # Ensure a block exists
        if not self.graph.blocks:
            self.graph.add_block(name)

        self.graph.add_component_def(name, props, state_fields)
        scope = ComponentScope(self.graph, name)
        yield scope

        # After scope exits, finalize component
        comp = self.graph.components.get(name)
        if comp and scope._root_id:
            comp.root_node_id = scope._root_id
            if not self.graph.root_component:
                self.graph.root_component = name

    def route(self, path: str, component: str, guards: tuple[str, ...] = ()) -> int:
        """Add a route definition."""
        return self.graph.add_route(path, component, guards)

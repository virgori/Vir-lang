"""
Pass Manager — Orchestrates pass ordering and execution.
=========================================================
"""

from __future__ import annotations

from src.virpass.base_pass import BasePass, PassResult
from src.qir.module import QIRGraph


class PassManager:
    """Manages and executes a pipeline of compiler passes."""

    def __init__(self) -> None:
        self._passes: list[BasePass] = []
        self._results: list[tuple[str, PassResult]] = []

    def add(self, p: BasePass) -> "PassManager":
        """Add a pass to the pipeline. Returns self for chaining."""
        self._passes.append(p)
        return self

    def run(self, graph: QIRGraph) -> bool:
        """Run all passes in order. Returns True if no errors."""
        self._results.clear()
        for p in self._passes:
            result = p.run(graph)
            self._results.append((p.name, result))
            if not result.ok:
                return False
        return True

    @property
    def results(self) -> list[tuple[str, PassResult]]:
        return self._results

    @property
    def total_changes(self) -> int:
        return sum(1 for _, r in self._results if r.changed)

    def summary(self) -> str:
        lines = [f"PassManager: {len(self._passes)} passes"]
        for name, result in self._results:
            status = "OK" if result.ok else "FAIL"
            changed = " [changed]" if result.changed else ""
            lines.append(f"  {name}: {status}{changed}")
            for err in result.errors:
                lines.append(f"    ERROR: {err}")
            for k, v in result.stats.items():
                lines.append(f"    {k}: {v}")
        return "\n".join(lines)

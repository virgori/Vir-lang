"""
Base Pass — Abstract pass interface for QIR transformations.
=============================================================
Pass hooks per design plan §4.1.A.5:
  inspect / rewrite / annotate / replace / fuse / lower
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto

from src.qir.module import QIRGraph


class PassAction(Enum):
    """What kind of mutation a pass performs."""
    INSPECT = auto()    # read-only analysis
    REWRITE = auto()    # modify existing nodes
    ANNOTATE = auto()   # add metadata to nodes
    REPLACE = auto()    # replace nodes with different nodes
    FUSE = auto()       # merge multiple nodes into one
    LOWER = auto()      # lower to next IR level


@dataclass
class PassResult:
    """Result of running a pass."""
    changed: bool = False
    errors: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


class BasePass(ABC):
    """Abstract base for all QIR compiler passes."""

    name: str = "unnamed_pass"
    action: PassAction = PassAction.INSPECT

    @abstractmethod
    def run(self, graph: QIRGraph) -> PassResult:
        """Execute pass on the graph. Return PassResult."""
        ...

    def __repr__(self) -> str:
        return f"<Pass:{self.name}>"

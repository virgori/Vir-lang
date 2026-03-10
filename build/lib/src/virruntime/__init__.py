"""VirRuntime — CPU-first dispatch and execution engine."""

from src.virruntime.dispatcher import Dispatcher
from src.virruntime.execution_plan import ExecutionPlan, execute_plan

__all__ = ["Dispatcher", "ExecutionPlan", "execute_plan"]

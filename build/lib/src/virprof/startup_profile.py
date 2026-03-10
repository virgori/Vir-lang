"""
StartupProfile — Break down initialization costs.
====================================================
Profiles the startup sequence: CPU probe, capability detection,
kernel registry loading, and module imports.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from src.virprof.timer import Timer


@dataclass
class PhaseRecord:
    """One startup phase measurement."""
    name: str
    elapsed_ms: float
    details: dict[str, Any] = field(default_factory=dict)


class StartupProfile:
    """Profiles Vir runtime startup sequence.

    Usage:
        sp = StartupProfile()
        sp.begin()

        sp.phase_start("cpu_probe")
        profile = CapabilityProfile.detect()
        sp.phase_end(details={"backend": profile.preferred_backend.name})

        sp.phase_start("kernel_load")
        import src.virmatrix.kernels.scalar.ops
        sp.phase_end()

        sp.finish()
        print(sp.report())
    """

    def __init__(self) -> None:
        self.phases: list[PhaseRecord] = []
        self._start_ns: int = 0
        self._total_ns: int = 0
        self._phase_name: str = ""
        self._phase_start_ns: int = 0

    def begin(self) -> None:
        """Mark beginning of startup sequence."""
        self._start_ns = time.perf_counter_ns()

    def phase_start(self, name: str) -> None:
        """Begin timing a named phase."""
        self._phase_name = name
        self._phase_start_ns = time.perf_counter_ns()

    def phase_end(self, details: dict[str, Any] | None = None) -> None:
        """End timing current phase and record it."""
        end_ns = time.perf_counter_ns()
        elapsed_ms = (end_ns - self._phase_start_ns) / 1_000_000
        self.phases.append(PhaseRecord(
            name=self._phase_name,
            elapsed_ms=elapsed_ms,
            details=details or {},
        ))

    def finish(self) -> None:
        """Mark end of startup sequence."""
        self._total_ns = time.perf_counter_ns() - self._start_ns

    @property
    def total_ms(self) -> float:
        return self._total_ns / 1_000_000

    def report(self) -> str:
        """Generate human-readable startup profile report."""
        lines = [
            "=== Vir Startup Profile ===",
            f"Total: {self.total_ms:.2f}ms",
            "",
        ]
        for phase in self.phases:
            pct = (phase.elapsed_ms / self.total_ms * 100) if self.total_ms > 0 else 0
            line = f"  {phase.name:20s} {phase.elapsed_ms:8.2f}ms  ({pct:5.1f}%)"
            if phase.details:
                detail_str = ", ".join(f"{k}={v}" for k, v in phase.details.items())
                line += f"  [{detail_str}]"
            lines.append(line)

        accounted = sum(p.elapsed_ms for p in self.phases)
        overhead = self.total_ms - accounted
        if overhead > 0.01:
            pct = (overhead / self.total_ms * 100) if self.total_ms > 0 else 0
            lines.append(f"  {'(overhead)':20s} {overhead:8.2f}ms  ({pct:5.1f}%)")

        return "\n".join(lines)

    def profile_full_startup(self) -> "StartupProfile":
        """Run the complete standard startup sequence and profile it."""
        self.begin()

        # Phase 1: CPU probe
        self.phase_start("cpu_probe")
        from src.virplat.capability_profile import CapabilityProfile
        profile = CapabilityProfile.detect()
        self.phase_end(details={
            "backend": profile.preferred_backend.name,
            "vector_width": profile.vector_width_f32,
        })

        # Phase 2: Scalar kernels
        self.phase_start("scalar_kernels")
        import src.virmatrix.kernels.scalar.ops  # noqa: F401
        self.phase_end()

        # Phase 3: NEON kernels (if applicable)
        self.phase_start("neon_kernels")
        try:
            import src.virmatrix.kernels.neon.ops  # noqa: F401
            self.phase_end(details={"loaded": True})
        except ImportError:
            self.phase_end(details={"loaded": False})

        # Phase 4: Registry summary
        self.phase_start("registry_summary")
        from src.virmatrix.registry import get_global_registry
        reg = get_global_registry()
        self.phase_end(details={"ops": len(reg.list_ops())})

        self.finish()
        return self

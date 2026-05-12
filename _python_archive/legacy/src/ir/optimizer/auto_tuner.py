"""
auto_tuner.py – ML-Based Self-Optimization for Vir Compiler
=============================================================
Auto-tuning engine that optimizes compiler heuristic parameters
by measuring actual performance and using Bayesian-inspired search.

Tunable parameters:
  - vectorization_threshold: min iterations before vectorizing
  - unroll_factor: loop unroll depth
  - prefetch_distance: software prefetch distance (cache lines)
  - strength_reduce_threshold: latency cutoff for strength reduction
  - simd_min_trip_count: minimum trip count for SIMD conversion
  - alignment_pad: data alignment padding (bytes)

The auto-tuner works in phases:
  1. Profile: measure baseline performance
  2. Explore: try paramater variations
  3. Exploit: converge on best configuration
  4. Export: save optimal config

Usage:
    from src.ir.optimizer.auto_tuner import AutoTuner
    tuner = AutoTuner(arch="arm64")
    best = tuner.tune(benchmark_fn, max_trials=50)
"""

from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Optional


@dataclass
class TuningConfig:
    """Set of tunable compiler parameters."""
    vectorization_threshold: int = 8       # min elements to vectorize
    unroll_factor: int = 4                  # loop unroll depth
    prefetch_distance: int = 8              # SW prefetch (cache lines)
    strength_reduce_threshold: int = 3      # latency cutoff
    simd_min_trip_count: int = 16           # min loop iters for SIMD
    alignment_pad: int = 64                 # data alignment (bytes)
    inline_threshold: int = 50              # max instructions to inline


@dataclass
class TrialResult:
    """Result of a single tuning trial."""
    config: TuningConfig
    score: float          # lower is better (execution time in µs)
    variance: float = 0.0
    trial_id: int = 0


@dataclass
class TuningState:
    """Persistent state for the auto-tuner."""
    arch: str
    best_config: TuningConfig = field(default_factory=TuningConfig)
    best_score: float = float('inf')
    trials: list[TrialResult] = field(default_factory=list)
    total_trials: int = 0
    converged: bool = False


class AutoTuner:
    """ML-inspired auto-tuning engine for compiler optimization parameters.

    Uses a combination of:
    - Random search for initial exploration
    - Thompson sampling for exploitation
    - Gaussian perturbation for local refinement
    """

    # Parameter ranges for exploration
    _PARAM_RANGES = {
        "vectorization_threshold": (2, 64),
        "unroll_factor": (1, 16),
        "prefetch_distance": (0, 32),
        "strength_reduce_threshold": (2, 10),
        "simd_min_trip_count": (4, 128),
        "alignment_pad": (16, 256),
        "inline_threshold": (10, 200),
    }

    def __init__(self, arch: str = "arm64",
                 state_path: Optional[str] = None) -> None:
        self.arch = arch
        self.state = TuningState(arch=arch)
        self._rng = random.Random(42)

        if state_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            self._state_path = project_root / "data" / "tuning" / f"{arch}_tuning.json"
        else:
            self._state_path = Path(state_path)

        self._load_state()

    def _load_state(self) -> None:
        """Load previous tuning state if available."""
        if self._state_path.exists():
            with open(self._state_path) as f:
                data = json.load(f)
            self.state.best_score = data.get("best_score", float('inf'))
            bc = data.get("best_config", {})
            if bc:
                self.state.best_config = TuningConfig(**{
                    k: v for k, v in bc.items()
                    if k in TuningConfig.__dataclass_fields__
                })
            self.state.total_trials = data.get("total_trials", 0)
            self.state.converged = data.get("converged", False)

    def save_state(self) -> None:
        """Save tuning state to disk."""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "arch": self.arch,
            "best_config": asdict(self.state.best_config),
            "best_score": self.state.best_score,
            "total_trials": self.state.total_trials,
            "converged": self.state.converged,
            "history": [
                {"score": t.score, "trial_id": t.trial_id,
                 "config": asdict(t.config)}
                for t in self.state.trials[-100:]  # keep last 100
            ],
        }
        with open(self._state_path, "w") as f:
            json.dump(data, f, indent=2)

    def tune(
        self, benchmark_fn: Callable[[TuningConfig], float],
        max_trials: int = 50,
        patience: int = 10,
    ) -> TuningConfig:
        """Run the auto-tuning loop.

        Args:
            benchmark_fn: Function that takes TuningConfig and returns
                          execution time (lower is better).
            max_trials: Maximum number of tuning trials.
            patience: Stop early if no improvement for this many trials.

        Returns:
            Best TuningConfig found.
        """
        no_improve = 0
        baseline_score = benchmark_fn(self.state.best_config)
        self.state.best_score = baseline_score

        for trial_id in range(max_trials):
            self.state.total_trials += 1

            # Phase selection based on trial count
            if trial_id < max_trials // 3:
                config = self._random_config()      # Explore
            elif trial_id < 2 * max_trials // 3:
                config = self._perturb_best()        # Local search
            else:
                config = self._thompson_sample()     # Exploit

            # Measure
            score = benchmark_fn(config)
            result = TrialResult(
                config=config, score=score,
                trial_id=self.state.total_trials,
            )
            self.state.trials.append(result)

            # Update best
            if score < self.state.best_score:
                self.state.best_score = score
                self.state.best_config = config
                no_improve = 0
            else:
                no_improve += 1

            # Patience-based early stopping
            if no_improve >= patience:
                self.state.converged = True
                break

        self.save_state()
        return self.state.best_config

    def _random_config(self) -> TuningConfig:
        """Generate a uniformly random configuration."""
        params = {}
        for name, (lo, hi) in self._PARAM_RANGES.items():
            params[name] = self._rng.randint(lo, hi)
        # Ensure alignment_pad is power of 2
        params["alignment_pad"] = 1 << self._rng.randint(4, 8)
        return TuningConfig(**params)

    def _perturb_best(self) -> TuningConfig:
        """Perturb the current best config with Gaussian noise."""
        best = self.state.best_config
        params = asdict(best)
        # Pick 1-3 random parameters to perturb
        keys = list(self._PARAM_RANGES.keys())
        n_perturb = self._rng.randint(1, 3)
        to_perturb = self._rng.sample(keys, min(n_perturb, len(keys)))

        for key in to_perturb:
            lo, hi = self._PARAM_RANGES[key]
            current = params[key]
            sigma = max(1, (hi - lo) // 6)
            new_val = int(current + self._rng.gauss(0, sigma))
            params[key] = max(lo, min(hi, new_val))

        if "alignment_pad" in to_perturb:
            # Snap to power of 2
            raw = params["alignment_pad"]
            exp = max(4, min(8, int(math.log2(max(1, raw)))))
            params["alignment_pad"] = 1 << exp

        return TuningConfig(**params)

    def _thompson_sample(self) -> TuningConfig:
        """Thompson sampling: sample from posterior of good configs.

        Uses the top 20% of trials, samples a config from them
        with Gaussian perturbation.
        """
        if len(self.state.trials) < 5:
            return self._random_config()

        # Sort by score (lower is better), take top 20%
        sorted_trials = sorted(self.state.trials, key=lambda t: t.score)
        n_elite = max(2, len(sorted_trials) // 5)
        elite = sorted_trials[:n_elite]

        # Sample from elite
        chosen = self._rng.choice(elite)
        params = asdict(chosen.config)

        # Light perturbation
        keys = list(self._PARAM_RANGES.keys())
        key = self._rng.choice(keys)
        lo, hi = self._PARAM_RANGES[key]
        sigma = max(1, (hi - lo) // 10)
        params[key] = max(lo, min(hi, int(params[key] + self._rng.gauss(0, sigma))))

        if key == "alignment_pad":
            exp = max(4, min(8, int(math.log2(max(1, params[key])))))
            params["alignment_pad"] = 1 << exp

        return TuningConfig(**params)

    def get_best(self) -> TuningConfig:
        """Return the current best configuration."""
        return self.state.best_config

    def summary(self) -> str:
        """Human-readable summary of tuning state."""
        lines = [
            f"AutoTuner: {self.arch}",
            f"  Total trials: {self.state.total_trials}",
            f"  Best score: {self.state.best_score:.2f}",
            f"  Converged: {self.state.converged}",
            "",
            "  Best config:",
        ]
        for k, v in asdict(self.state.best_config).items():
            lines.append(f"    {k}: {v}")
        return "\n".join(lines)

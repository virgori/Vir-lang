"""
VSS Scoper — Scoped class name mangling.
==========================================
Generates unique, scoped CSS class names to prevent global style collisions.
Each style block gets a deterministic hash suffix based on component + name.

Example: style "card" in component "App" → ".card_a7f2"
"""

from __future__ import annotations

import hashlib

from src.vss.ast import (
    VSSStylesheet, VSSStyleBlock, VSSKeyframes,
)


class VSSScoper:
    """Generates scoped CSS class names for VSS style blocks."""

    def __init__(self, scope_prefix: str = "") -> None:
        self._prefix = scope_prefix  # e.g., component name or file name
        self._map: dict[str, str] = {}   # original_name → scoped_name

    def scope_stylesheet(self, stylesheet: VSSStylesheet) -> dict[str, str]:
        """Generate scoped names for all style blocks. Returns name mapping."""
        for style in stylesheet.styles:
            scoped = self._generate_scoped_name(style.name)
            self._map[style.name] = scoped

        for kf in stylesheet.keyframes:
            scoped = self._generate_scoped_name(kf.name)
            self._map[kf.name] = scoped

        return dict(self._map)

    def get_scoped_name(self, original: str) -> str:
        """Get the scoped name for an original style name."""
        return self._map.get(original, original)

    def _generate_scoped_name(self, name: str) -> str:
        """Generate a deterministic scoped name: name_XXXX."""
        seed = f"{self._prefix}:{name}"
        h = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:4]
        return f"{name}_{h}"

"""
lockfile.py — vir.lock reader/writer.
======================================
Format:
    # vir.lock — auto-generated, do not edit
    [[package]]
    name = "http"
    version = "1.2.3"
    deps = ["net", "tls"]

    [[package]]
    name = "net"
    version = "0.8.1"
    deps = []
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .manifest import SemVer, parse_semver


@dataclass(frozen=True)
class LockEntry:
    """One locked package."""
    name: str
    version: SemVer
    checksum: str = ""
    deps: tuple[str, ...] = ()


@dataclass
class LockFile:
    """All locked packages."""
    entries: list[LockEntry] = field(default_factory=list)

    def get(self, name: str) -> LockEntry | None:
        for e in self.entries:
            if e.name == name:
                return e
        return None


def parse_lockfile(text: str) -> LockFile:
    """Parse vir.lock content."""
    lockfile = LockFile()
    current: dict[str, str] = {}

    def _flush() -> None:
        if "name" in current and "version" in current:
            deps_str = current.get("deps", "[]")
            deps = _parse_deps_array(deps_str)
            lockfile.entries.append(LockEntry(
                name=current["name"],
                version=parse_semver(current["version"]),
                checksum=current.get("checksum", ""),
                deps=tuple(deps),
            ))

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[[package]]":
            _flush()
            current = {}
            continue
        m = re.match(r'^(\w+)\s*=\s*(.+)$', line)
        if m:
            key = m.group(1)
            val = m.group(2).strip().strip('"').strip("'")
            current[key] = val

    _flush()
    return lockfile


def _parse_deps_array(s: str) -> list[str]:
    s = s.strip()
    if s.startswith("["):
        s = s[1:]
    if s.endswith("]"):
        s = s[:-1]
    items = []
    for part in s.split(","):
        part = part.strip().strip('"').strip("'")
        if part:
            items.append(part)
    return items


def write_lockfile(lockfile: LockFile, path: Path | None = None) -> None:
    """Write vir.lock."""
    if path is None:
        path = Path.cwd() / "vir.lock"

    lines = ["# vir.lock — auto-generated, do not edit manually"]

    for entry in sorted(lockfile.entries, key=lambda e: e.name):
        lines.append("")
        lines.append("[[package]]")
        lines.append(f'name = "{entry.name}"')
        lines.append(f'version = "{entry.version}"')
        if entry.checksum:
            lines.append(f'checksum = "{entry.checksum}"')
        deps_str = ", ".join(f'"{d}"' for d in entry.deps)
        lines.append(f"deps = [{deps_str}]")

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def load_lockfile(path: Path | None = None) -> LockFile | None:
    """Load vir.lock from given path or cwd. Returns None if not found."""
    if path is None:
        path = Path.cwd() / "vir.lock"
    if not path.exists():
        return None
    return parse_lockfile(path.read_text(encoding="utf-8"))

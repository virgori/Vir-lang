"""
manifest.py — Vir package manifest (vir.toml) parser & writer.
================================================================
[package]
name = "my-app"
version = "1.0.0"
authors = ["dev"]
license = "MIT"
description = "A Vir project"

[dependencies]
http = "^1.2.0"
json = ">=0.5.0"

[dev-dependencies]
test = "^2.0.0"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SemVer:
    """Semantic version: MAJOR.MINOR.PATCH"""
    major: int = 0
    minor: int = 0
    patch: int = 0

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __lt__(self, other: SemVer) -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: SemVer) -> bool:
        return self == other or self < other

    def __gt__(self, other: SemVer) -> bool:
        return not self <= other

    def __ge__(self, other: SemVer) -> bool:
        return not self < other

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch))


def parse_semver(s: str) -> SemVer:
    """Parse '1.2.3' into SemVer."""
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", s.strip())
    if not m:
        raise ValueError(f"Invalid semver: {s!r}")
    return SemVer(int(m.group(1)), int(m.group(2)), int(m.group(3)))


@dataclass
class VersionReq:
    """Version requirement: ^1.2.0, >=0.5.0, =1.0.0, ~1.2.0"""
    op: str       # "^", "~", ">=", "<=", ">", "<", "="
    version: SemVer

    def matches(self, v: SemVer) -> bool:
        """Check if version v satisfies this requirement."""
        ref = self.version
        if self.op == "=":
            return v == ref
        if self.op == ">=":
            return v >= ref
        if self.op == "<=":
            return v <= ref
        if self.op == ">":
            return v > ref
        if self.op == "<":
            return v < ref
        if self.op == "^":
            # Caret: compatible with same major (>=1.0.0 means >=1.2.0, <2.0.0)
            if ref.major == 0:
                if ref.minor == 0:
                    return v == ref
                return v.major == 0 and v.minor == ref.minor and v.patch >= ref.patch
            return v.major == ref.major and v >= ref
        if self.op == "~":
            # Tilde: same major.minor
            return v.major == ref.major and v.minor == ref.minor and v.patch >= ref.patch
        return False

    def __str__(self) -> str:
        return f"{self.op}{self.version}"


def parse_version_req(s: str) -> VersionReq:
    """Parse '^1.2.0', '>=0.5.0', '=1.0.0', '~1.2.0', '1.2.3' -> VersionReq."""
    s = s.strip().strip('"').strip("'")
    m = re.match(r"^(\^|~|>=|<=|>|<|=)?(\d+\.\d+\.\d+)$", s)
    if not m:
        raise ValueError(f"Invalid version requirement: {s!r}")
    op = m.group(1) or "^"
    return VersionReq(op=op, version=parse_semver(m.group(2)))


@dataclass
class Dependency:
    """A package dependency."""
    name: str
    version_req: VersionReq
    dev: bool = False

    def __str__(self) -> str:
        return f'{self.name} = "{self.version_req}"'


@dataclass
class Manifest:
    """Parsed vir.toml manifest."""
    name: str = "untitled"
    version: SemVer = field(default_factory=lambda: SemVer(0, 1, 0))
    authors: list[str] = field(default_factory=list)
    license: str = "MIT"
    description: str = ""
    dependencies: list[Dependency] = field(default_factory=list)
    dev_dependencies: list[Dependency] = field(default_factory=list)


def _parse_toml_simple(text: str) -> dict[str, dict[str, str]]:
    """
    Minimal TOML parser for vir.toml.
    Supports [section] headers and key = "value" pairs.
    """
    sections: dict[str, dict[str, str]] = {}
    current_section = "_root"
    sections[current_section] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # Section header
        m = re.match(r"^\[(.+)\]$", line)
        if m:
            current_section = m.group(1).strip()
            if current_section not in sections:
                sections[current_section] = {}
            continue
        # Key = value
        m = re.match(r'^(\S+)\s*=\s*(.+)$', line)
        if m:
            key = m.group(1).strip()
            value = m.group(2).strip()
            # Strip quotes
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            # Array
            elif value.startswith("[") and value.endswith("]"):
                value = value  # keep as-is, parsed later
            sections[current_section][key] = value

    return sections


def _parse_array(s: str) -> list[str]:
    """Parse a TOML-like inline array: ['a', 'b'] → ['a', 'b']"""
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


def parse_manifest(text: str) -> Manifest:
    """Parse vir.toml content into Manifest."""
    sections = _parse_toml_simple(text)

    pkg = sections.get("package", {})
    manifest = Manifest(
        name=pkg.get("name", "untitled"),
        version=parse_semver(pkg.get("version", "0.1.0")),
        authors=_parse_array(pkg.get("authors", "[]")),
        license=pkg.get("license", "MIT"),
        description=pkg.get("description", ""),
    )

    # Dependencies
    for dep_name, ver_str in sections.get("dependencies", {}).items():
        manifest.dependencies.append(Dependency(
            name=dep_name,
            version_req=parse_version_req(ver_str),
        ))

    # Dev-dependencies
    for dep_name, ver_str in sections.get("dev-dependencies", {}).items():
        manifest.dev_dependencies.append(Dependency(
            name=dep_name,
            version_req=parse_version_req(ver_str),
            dev=True,
        ))

    return manifest


def load_manifest(path: Path | None = None) -> Manifest:
    """Load vir.toml from given path or current directory."""
    if path is None:
        path = Path.cwd() / "vir.toml"
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    return parse_manifest(path.read_text(encoding="utf-8"))


def write_manifest(manifest: Manifest, path: Path | None = None) -> None:
    """Write Manifest to vir.toml."""
    if path is None:
        path = Path.cwd() / "vir.toml"

    lines = [
        "[package]",
        f'name = "{manifest.name}"',
        f'version = "{manifest.version}"',
        f'authors = [{", ".join(f"{a!r}" for a in manifest.authors)}]',
        f'license = "{manifest.license}"',
        f'description = "{manifest.description}"',
    ]

    if manifest.dependencies:
        lines.append("")
        lines.append("[dependencies]")
        for dep in manifest.dependencies:
            lines.append(f'{dep.name} = "{dep.version_req}"')

    if manifest.dev_dependencies:
        lines.append("")
        lines.append("[dev-dependencies]")
        for dep in manifest.dev_dependencies:
            lines.append(f'{dep.name} = "{dep.version_req}"')

    lines.append("")  # trailing newline
    path.write_text("\n".join(lines), encoding="utf-8")


def init_manifest(project_dir: Path, name: Optional[str] = None) -> Manifest:
    """Create a new vir.toml in project_dir."""
    if name is None:
        name = project_dir.name
    manifest = Manifest(
        name=name,
        version=SemVer(0, 1, 0),
        description=f"A Vir project: {name}",
    )
    write_manifest(manifest, project_dir / "vir.toml")
    # Create src/ directory
    (project_dir / "src").mkdir(exist_ok=True)
    # Create main.vri
    main_vri = project_dir / "src" / "main.vri"
    if not main_vri.exists():
        main_vri.write_text('include io;\n\nfunc main: in()\n    print("Xin chào từ Vir!");\nend\n',
                           encoding="utf-8")
    return manifest

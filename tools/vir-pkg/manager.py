"""
vir-pkg — Vir Package Manager
===============================
Phase 3 Task F3: Local dependency resolution and package management.

Usage:
    python -m tools.vir-pkg.manager init          # Create vir.toml manifest
    python -m tools.vir-pkg.manager install        # Install dependencies
    python -m tools.vir-pkg.manager build          # Build package
    python -m tools.vir-pkg.manager list           # List installed packages

Manifest: vir.toml
Lockfile: vir.lock
Package cache: ~/.vir/packages/
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PackageDep:
    """A single dependency entry."""
    name: str
    version: str = "*"
    path: str | None = None     # Local path dependency
    source: str = "local"       # "local" | "registry" (registry TBD)


@dataclass
class PackageManifest:
    """Contents of vir.toml."""
    name: str = "my-package"
    version: str = "0.1.0"
    authors: list[str] = field(default_factory=list)
    description: str = ""
    lang: str = "vi"           # Default language (vi/en/zh)
    entry: str = "src/main.vri"
    dependencies: list[PackageDep] = field(default_factory=list)
    dev_dependencies: list[PackageDep] = field(default_factory=list)


@dataclass
class LockEntry:
    """One entry in vir.lock."""
    name: str
    version: str
    checksum: str
    resolved_path: str


class ManifestParser:
    """Parse minimal TOML-like vir.toml files."""

    @staticmethod
    def parse(text: str) -> PackageManifest:
        m = PackageManifest()
        section = "package"
        deps: list[PackageDep] = []

        for raw_line in text.split("\n"):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            # Section headers
            if line.startswith("["):
                section = line.strip("[] ").lower()
                continue

            if "=" not in line:
                continue

            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")

            if section == "package":
                if key == "name":
                    m.name = val
                elif key == "version":
                    m.version = val
                elif key == "description":
                    m.description = val
                elif key == "entry":
                    m.entry = val
                elif key == "lang":
                    m.lang = val
            elif section in ("dependencies", "dev-dependencies"):
                dep = PackageDep(name=key, version=val)
                if section == "dependencies":
                    deps.append(dep)
                else:
                    m.dev_dependencies.append(dep)

        m.dependencies = deps
        return m

    @staticmethod
    def generate(m: PackageManifest) -> str:
        lines = [
            "[package]",
            f'name = "{m.name}"',
            f'version = "{m.version}"',
            f'description = "{m.description}"',
            f'entry = "{m.entry}"',
            f'lang = "{m.lang}"',
            "",
            "[dependencies]",
        ]
        for d in m.dependencies:
            if d.path:
                lines.append(f'{d.name} = {{ path = "{d.path}" }}')
            else:
                lines.append(f'{d.name} = "{d.version}"')
        lines.append("")
        lines.append("[dev-dependencies]")
        for d in m.dev_dependencies:
            lines.append(f'{d.name} = "{d.version}"')
        lines.append("")
        return "\n".join(lines)


class VirPackageManager:
    """Package manager core logic."""

    CACHE_DIR = Path.home() / ".vir" / "packages"

    def __init__(self, project_dir: Path | None = None):
        self.project_dir = project_dir or Path.cwd()
        self.manifest_path = self.project_dir / "vir.toml"
        self.lock_path = self.project_dir / "vir.lock"

    def init(self) -> None:
        """Create a new vir.toml manifest."""
        if self.manifest_path.exists():
            print(f"vir.toml already exists in {self.project_dir}")
            return
        m = PackageManifest(name=self.project_dir.name)
        self.manifest_path.write_text(ManifestParser.generate(m), encoding="utf-8")
        print(f"Created {self.manifest_path}")

    def load_manifest(self) -> PackageManifest:
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"No vir.toml found in {self.project_dir}")
        return ManifestParser.parse(self.manifest_path.read_text(encoding="utf-8"))

    def install(self) -> list[LockEntry]:
        """Resolve and install dependencies."""
        manifest = self.load_manifest()
        entries: list[LockEntry] = []

        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        for dep in manifest.dependencies:
            entry = self._resolve_dep(dep)
            if entry:
                entries.append(entry)
                print(f"  Installed: {dep.name} @ {entry.version}")

        # Write lockfile
        self._write_lock(entries)
        print(f"Wrote {self.lock_path} ({len(entries)} packages)")
        return entries

    def _resolve_dep(self, dep: PackageDep) -> LockEntry | None:
        """Resolve a single dependency."""
        if dep.path:
            # Local path dependency
            dep_path = self.project_dir / dep.path
            if not dep_path.exists():
                print(f"  Warning: local dep path {dep_path} not found")
                return None
            checksum = self._checksum_dir(dep_path)
            return LockEntry(
                name=dep.name,
                version=dep.version,
                checksum=checksum,
                resolved_path=str(dep_path.resolve()),
            )
        # For now, only local deps supported
        print(f"  Warning: remote registry not yet implemented for '{dep.name}'")
        return None

    def _checksum_dir(self, path: Path) -> str:
        """Compute SHA-256 checksum of all .vri files in directory."""
        h = hashlib.sha256()
        for f in sorted(path.rglob("*.vri")):
            h.update(f.read_bytes())
        return h.hexdigest()[:16]

    def _write_lock(self, entries: list[LockEntry]) -> None:
        data = {
            "version": 1,
            "packages": [
                {
                    "name": e.name,
                    "version": e.version,
                    "checksum": e.checksum,
                    "resolved_path": e.resolved_path,
                }
                for e in entries
            ],
        }
        self.lock_path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                  encoding="utf-8")

    def build(self) -> bool:
        """Build the current package (compile entry point)."""
        manifest = self.load_manifest()
        entry = self.project_dir / manifest.entry
        if not entry.exists():
            print(f"Entry point {entry} not found")
            return False
        print(f"Building {manifest.name} v{manifest.version}...")
        # Delegate to compiler
        build_dir = self.project_dir / "build"
        build_dir.mkdir(exist_ok=True)
        print(f"  Entry: {entry}")
        print(f"  Output: {build_dir}/")
        print("  (Compiler integration pending)")
        return True

    def list_packages(self) -> None:
        """List installed packages from lockfile."""
        if not self.lock_path.exists():
            print("No lockfile found. Run 'vir-pkg install' first.")
            return
        data = json.loads(self.lock_path.read_text(encoding="utf-8"))
        for pkg in data.get("packages", []):
            print(f"  {pkg['name']} @ {pkg['version']}  [{pkg['checksum']}]")


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: vir-pkg <init|install|build|list>")
        sys.exit(1)

    mgr = VirPackageManager()
    cmd = args[0]

    if cmd == "init":
        mgr.init()
    elif cmd == "install":
        mgr.install()
    elif cmd == "build":
        mgr.build()
    elif cmd == "list":
        mgr.list_packages()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()

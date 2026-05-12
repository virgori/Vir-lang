"""
registry.py — Vir package registry client.
============================================
Default registry: ~/.vir/registry/ (local file-based).
Future: HTTP registry at registry.vir-lang.dev
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .manifest import Dependency, SemVer, VersionReq, parse_semver, parse_version_req
from .resolver import PackageIndex


VIR_HOME = Path.home() / ".vir"
REGISTRY_DIR = VIR_HOME / "registry"
CACHE_DIR = VIR_HOME / "cache"


@dataclass
class PackageInfo:
    """Metadata for a published package."""
    name: str
    version: SemVer
    description: str = ""
    authors: list[str] = field(default_factory=list)
    license: str = "MIT"
    checksum: str = ""
    dependencies: list[Dependency] = field(default_factory=list)


def _ensure_dirs() -> None:
    """Ensure ~/.vir/registry/ and ~/.vir/cache/ exist."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def publish_local(pkg_dir: Path, info: PackageInfo) -> None:
    """Publish a package to local registry."""
    _ensure_dirs()

    pkg_reg_dir = REGISTRY_DIR / info.name
    pkg_reg_dir.mkdir(exist_ok=True)

    # Write version metadata
    ver_file = pkg_reg_dir / f"{info.version}.json"
    meta = {
        "name": info.name,
        "version": str(info.version),
        "description": info.description,
        "authors": info.authors,
        "license": info.license,
        "checksum": info.checksum,
        "dependencies": {d.name: str(d.version_req) for d in info.dependencies},
    }
    ver_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # Copy source files to cache
    cache_pkg = CACHE_DIR / info.name / str(info.version)
    cache_pkg.mkdir(parents=True, exist_ok=True)

    for src_file in pkg_dir.rglob("*.vri"):
        relative = src_file.relative_to(pkg_dir)
        dest = cache_pkg / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src_file.read_bytes())


def search_local(query: str) -> list[PackageInfo]:
    """Search local registry by name substring."""
    _ensure_dirs()
    results = []
    if not REGISTRY_DIR.exists():
        return results

    for pkg_dir in REGISTRY_DIR.iterdir():
        if not pkg_dir.is_dir():
            continue
        if query.lower() not in pkg_dir.name.lower():
            continue
        # Get latest version
        versions: list[tuple[SemVer, Path]] = []
        for ver_file in pkg_dir.glob("*.json"):
            try:
                v = parse_semver(ver_file.stem)
                versions.append((v, ver_file))
            except ValueError:
                continue
        if versions:
            versions.sort(key=lambda x: x[0], reverse=True)
            latest_ver, latest_path = versions[0]
            meta = json.loads(latest_path.read_text(encoding="utf-8"))
            results.append(PackageInfo(
                name=meta["name"],
                version=latest_ver,
                description=meta.get("description", ""),
                authors=meta.get("authors", []),
            ))
    return results


def build_index_local() -> PackageIndex:
    """Build a PackageIndex from local registry."""
    _ensure_dirs()
    index = PackageIndex()

    if not REGISTRY_DIR.exists():
        return index

    for pkg_dir in REGISTRY_DIR.iterdir():
        if not pkg_dir.is_dir():
            continue
        for ver_file in pkg_dir.glob("*.json"):
            try:
                ver = parse_semver(ver_file.stem)
            except ValueError:
                continue
            meta = json.loads(ver_file.read_text(encoding="utf-8"))
            deps = []
            for dep_name, dep_ver in meta.get("dependencies", {}).items():
                deps.append(Dependency(name=dep_name, version_req=parse_version_req(dep_ver)))
            index.add(pkg_dir.name, ver, deps)

    return index


def fetch_package(name: str, version: SemVer) -> Optional[Path]:
    """Get cached source path for a package version. Returns None if not found."""
    cache_path = CACHE_DIR / name / str(version)
    if cache_path.exists():
        return cache_path
    return None


def list_installed(project_dir: Path) -> list[tuple[str, SemVer]]:
    """List packages installed in project_dir/vir_modules/."""
    modules_dir = project_dir / "vir_modules"
    if not modules_dir.exists():
        return []
    result = []
    for pkg_dir in modules_dir.iterdir():
        if not pkg_dir.is_dir():
            continue
        ver_file = pkg_dir / ".version"
        if ver_file.exists():
            try:
                ver = parse_semver(ver_file.read_text(encoding="utf-8").strip())
                result.append((pkg_dir.name, ver))
            except ValueError:
                pass
    return sorted(result, key=lambda x: x[0])

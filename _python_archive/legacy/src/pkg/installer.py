"""
installer.py — Download & install resolved packages into vir_modules/.
========================================================================
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .lockfile import LockEntry, LockFile, write_lockfile
from .manifest import Manifest, SemVer, load_manifest
from .registry import CACHE_DIR, build_index_local, fetch_package
from .resolver import ResolvedPackage, resolve


def install_all(project_dir: Path, include_dev: bool = False) -> list[ResolvedPackage]:
    """
    Resolve and install all dependencies from vir.toml.
    Returns list of installed packages.
    """
    manifest = load_manifest(project_dir / "vir.toml")
    index = build_index_local()
    resolved = resolve(manifest, index, include_dev=include_dev)

    modules_dir = project_dir / "vir_modules"
    modules_dir.mkdir(exist_ok=True)

    for pkg in resolved:
        _install_one(pkg, modules_dir)

    # Write lockfile
    lockfile = LockFile(entries=[
        LockEntry(
            name=pkg.name,
            version=pkg.version,
            deps=pkg.dependencies,
        )
        for pkg in resolved
    ])
    write_lockfile(lockfile, project_dir / "vir.lock")

    return resolved


def _install_one(pkg: ResolvedPackage, modules_dir: Path) -> bool:
    """Install a single resolved package to vir_modules/."""
    target = modules_dir / pkg.name
    if target.exists():
        # Check version
        ver_file = target / ".version"
        if ver_file.exists():
            current = ver_file.read_text(encoding="utf-8").strip()
            if current == str(pkg.version):
                return False  # Already installed

    # Fetch from cache
    source = fetch_package(pkg.name, pkg.version)
    if source is None:
        print(f"  ⚠ Package {pkg.name}@{pkg.version} not found in cache")
        return False

    # Copy to vir_modules
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)

    # Write version marker
    (target / ".version").write_text(str(pkg.version), encoding="utf-8")
    return True


def add_dependency(project_dir: Path, name: str, version_req_str: str = "^0.1.0") -> None:
    """Add a dependency to vir.toml."""
    from .manifest import Dependency, parse_version_req, write_manifest

    manifest = load_manifest(project_dir / "vir.toml")

    # Check if already exists
    for dep in manifest.dependencies:
        if dep.name == name:
            dep.version_req = parse_version_req(version_req_str)
            write_manifest(manifest, project_dir / "vir.toml")
            return

    manifest.dependencies.append(Dependency(
        name=name,
        version_req=parse_version_req(version_req_str),
    ))
    write_manifest(manifest, project_dir / "vir.toml")


def remove_dependency(project_dir: Path, name: str) -> bool:
    """Remove a dependency from vir.toml. Returns True if found."""
    from .manifest import write_manifest

    manifest = load_manifest(project_dir / "vir.toml")

    original_len = len(manifest.dependencies)
    manifest.dependencies = [d for d in manifest.dependencies if d.name != name]

    if len(manifest.dependencies) < original_len:
        write_manifest(manifest, project_dir / "vir.toml")
        # Remove from vir_modules
        target = project_dir / "vir_modules" / name
        if target.exists():
            shutil.rmtree(target)
        return True
    return False

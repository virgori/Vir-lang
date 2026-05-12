"""
resolver.py — Dependency Resolver for Vir packages.
=====================================================
Topological sort + version constraint satisfaction.
Greedy resolver: pick highest compatible version for each dep.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .manifest import Dependency, Manifest, SemVer, VersionReq


@dataclass(frozen=True)
class ResolvedPackage:
    """A resolved dependency with exact version."""
    name: str
    version: SemVer
    dependencies: tuple[str, ...] = ()

    def __str__(self) -> str:
        return f"{self.name}@{self.version}"


@dataclass
class PackageIndex:
    """
    Available package versions from registry.
    Maps package_name → list of (version, dependencies).
    """
    packages: dict[str, list[tuple[SemVer, list[Dependency]]]] = field(default_factory=dict)

    def add(self, name: str, version: SemVer, deps: list[Dependency] | None = None) -> None:
        if name not in self.packages:
            self.packages[name] = []
        self.packages[name].append((version, deps or []))
        # Keep sorted descending so we pick highest first
        self.packages[name].sort(key=lambda x: x[0], reverse=True)

    def get_versions(self, name: str) -> list[tuple[SemVer, list[Dependency]]]:
        return self.packages.get(name, [])


class ResolveError(Exception):
    """Lỗi giải quyết phụ thuộc."""
    pass


def resolve(
    manifest: Manifest,
    index: PackageIndex,
    include_dev: bool = False,
) -> list[ResolvedPackage]:
    """
    Resolve all dependencies to exact versions.

    Algorithm: Greedy topological resolution.
    For each dependency, pick the highest version that satisfies
    all constraints, then recursively resolve its transitive deps.
    """
    # Collect all top-level requirements
    requirements: list[Dependency] = list(manifest.dependencies)
    if include_dev:
        requirements.extend(manifest.dev_dependencies)

    # Constraints: package_name → list of VersionReq
    constraints: dict[str, list[VersionReq]] = {}
    for dep in requirements:
        constraints.setdefault(dep.name, []).append(dep.version_req)

    resolved: dict[str, ResolvedPackage] = {}
    _resolve_recursive(constraints, index, resolved, set())

    return list(resolved.values())


def _resolve_recursive(
    constraints: dict[str, list[VersionReq]],
    index: PackageIndex,
    resolved: dict[str, ResolvedPackage],
    visited: set[str],
) -> None:
    """Recursively resolve deps with cycle detection."""
    for name, reqs in list(constraints.items()):
        if name in resolved:
            # Verify existing resolution satisfies new constraints
            existing = resolved[name]
            for req in reqs:
                if not req.matches(existing.version):
                    raise ResolveError(
                        f"Conflict: {name}@{existing.version} does not satisfy {req}"
                    )
            continue

        if name in visited:
            raise ResolveError(f"Circular dependency detected: {name}")

        visited.add(name)

        # Find highest compatible version
        versions = index.get_versions(name)
        if not versions:
            raise ResolveError(f"Package not found in index: {name}")

        selected = None
        selected_deps: list[Dependency] = []
        for ver, deps in versions:
            if all(req.matches(ver) for req in reqs):
                selected = ver
                selected_deps = deps
                break

        if selected is None:
            req_str = ", ".join(str(r) for r in reqs)
            raise ResolveError(f"No compatible version for {name} (requires: {req_str})")

        # Record resolved package
        resolved[name] = ResolvedPackage(
            name=name,
            version=selected,
            dependencies=tuple(d.name for d in selected_deps),
        )

        # Resolve transitive deps
        if selected_deps:
            trans_constraints: dict[str, list[VersionReq]] = {}
            for dep in selected_deps:
                trans_constraints.setdefault(dep.name, []).append(dep.version_req)
            _resolve_recursive(trans_constraints, index, resolved, visited)

        visited.discard(name)

#!/usr/bin/env python3
"""
tools/module_graph.py — Canonical module resolution, dependency DAG, and registry engine.

Implements the Vir Spec v2.0 module resolution contract (VIR-SPC-0014, VIRC-PLN-0003):
- Parses stdlib registry (stdlib.vri) and project registry (module.list)
- Resolves canonical Module IDs and physical file paths
- Directory alias support (e.g. `virc = src` -> `virc.a.b` -> `src/a/b.vri`)
- Prefix collision and duplicate entry rejection
- Strict failure for missing registered targets (no search fallback)
- Cycle detection with clear cycle chain output
- Include/import convergence on single Module ID
- Deterministic topological ordering of module dependencies
- CWD-independent resolution
"""

from __future__ import annotations
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

class ModuleRegistryError(Exception):
    def __init__(self, code: int, message: str, location: Optional[str] = None):
        super().__init__(f"[E{code}] {message}" + (f" at {location}" if location else ""))
        self.code = code
        self.message = message
        self.location = location

class ModuleEntry:
    def __init__(self, name: str, rel_path: str, phys_path: Path, is_dir: bool, source_registry: str, line_no: int):
        self.name = name
        self.rel_path = rel_path
        self.phys_path = phys_path.resolve()
        self.is_dir = is_dir
        self.source_registry = source_registry
        self.line_no = line_no

class ModuleResolver:
    def __init__(self, repo_root: Path, project_root: Optional[Path] = None, stdlib_root: Optional[Path] = None):
        self.repo_root = repo_root.resolve()
        self.project_root = (project_root or repo_root).resolve()
        self.stdlib_root = (stdlib_root or (self.repo_root / "stdlib")).resolve()
        
        self.entries: Dict[str, ModuleEntry] = {}
        self.dir_aliases: Dict[str, ModuleEntry] = {}
        self.realpath_to_id: Dict[str, str] = {}
        
        self.load_registries()

    def _parse_registry_file(self, reg_path: Path, base_dir: Path, reg_name: str) -> None:
        if not reg_path.is_file():
            return

        lines = reg_path.read_text(encoding="utf-8").splitlines()
        root_dir = base_dir
        
        for idx, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            
            if "=" not in line:
                raise ModuleRegistryError(2120, f"Malformed registry entry: '{raw_line}'", f"{reg_path}:{idx}")
            
            key, val = [p.strip() for p in line.split("=", 1)]
            # Strip quotes if present
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1].strip()
            
            if key == "root":
                root_dir = (base_dir / val).resolve()
                continue
            
            # Reject duplicate entries
            if key in self.entries:
                prev = self.entries[key]
                raise ModuleRegistryError(
                    2121,
                    f"Duplicate module registration for '{key}' (previously defined at {prev.source_registry}:{prev.line_no})",
                    f"{reg_path}:{idx}"
                )

            # Check for prefix collision against existing directory aliases
            for dir_key in self.dir_aliases:
                if key.startswith(dir_key + "."):
                    raise ModuleRegistryError(
                        2122,
                        f"Prefix collision: module key '{key}' shadows existing directory alias '{dir_key}'",
                        f"{reg_path}:{idx}"
                    )
            
            target_phys = (root_dir / val).resolve()
            is_dir = target_phys.is_dir() or (not target_phys.exists() and not val.endswith(".vri"))
            
            if is_dir:
                # Check for prefix collision with existing entries
                for existing_key in self.entries:
                    if existing_key.startswith(key + "."):
                        raise ModuleRegistryError(
                            2122,
                            f"Prefix collision between directory alias '{key}' and registered entry '{existing_key}'",
                            f"{reg_path}:{idx}"
                        )
                
            entry = ModuleEntry(
                name=key,
                rel_path=val,
                phys_path=target_phys,
                is_dir=is_dir,
                source_registry=str(reg_path),
                line_no=idx
            )
            
            if is_dir:
                self.dir_aliases[key] = entry
            
            self.entries[key] = entry

    def load_registries(self) -> None:
        # 1. Load stdlib registry if present
        stdlib_vri = self.stdlib_root / "stdlib.vri"
        if stdlib_vri.is_file():
            self._parse_registry_file(stdlib_vri, self.stdlib_root / "vir", "stdlib.vri")

        # 2. Load nearest project module.list if present
        cur = self.project_root
        mod_list = None
        while cur != cur.parent:
            candidate = cur / "module.list"
            if candidate.is_file():
                mod_list = candidate
                break
            if cur == self.repo_root:
                break
            cur = cur.parent

        if mod_list is None and (self.repo_root / "compiler/module.list").is_file():
            mod_list = self.repo_root / "compiler/module.list"

        if mod_list and mod_list.is_file():
            self._parse_registry_file(mod_list, mod_list.parent, "module.list")

    def resolve(self, module_spec: str) -> Tuple[str, Path]:
        """
        Resolves a module name or include path (e.g. 'virc.semantic.passTypecheck' or 'compiler.lexer')
        Returns (canonical_module_id, physical_path).
        """
        spec = module_spec.strip()
        # Direct registered exact match
        if spec in self.entries and not self.entries[spec].is_dir:
            entry = self.entries[spec]
            if not entry.phys_path.is_file():
                raise ModuleRegistryError(2125, f"Registered target for '{spec}' does not exist: {entry.phys_path}", entry.source_registry)
            canonical_id = f"mod::{spec}"
            self.realpath_to_id[str(entry.phys_path.resolve())] = canonical_id
            return canonical_id, entry.phys_path

        # Dotted tail lookup under directory alias
        if "." in spec:
            parts = spec.split(".")
            prefix = parts[0]
            if prefix in self.dir_aliases:
                dir_entry = self.dir_aliases[prefix]
                tail = Path(*parts[1:])
                target = (dir_entry.phys_path / tail).with_suffix(".vri")
                if not target.is_file():
                    raise ModuleRegistryError(2125, f"Module '{spec}' resolves to missing target: {target}")
                canonical_id = f"mod::{spec}"
                self.realpath_to_id[str(target.resolve())] = canonical_id
                return canonical_id, target

        # Direct file path relative to repo or project root
        file_candidate = (self.project_root / spec).resolve()
        if not file_candidate.is_file() and not spec.endswith(".vri"):
            file_candidate = (self.project_root / f"{spec}.vri").resolve()
            
        if file_candidate.is_file():
            canon_str = str(file_candidate.resolve())
            if canon_str in self.realpath_to_id:
                return self.realpath_to_id[canon_str], file_candidate
            canonical_id = f"file::{file_candidate.relative_to(self.repo_root).as_posix()}"
            self.realpath_to_id[canon_str] = canonical_id
            return canonical_id, file_candidate

        raise ModuleRegistryError(2120, f"Module '{spec}' could not be resolved in registry or filesystem")

class DependencyGraph:
    def __init__(self, resolver: ModuleResolver):
        self.resolver = resolver
        self.adj: Dict[str, Set[str]] = {}
        self.id_to_path: Dict[str, Path] = {}

    def extract_dependencies(self, file_path: Path) -> List[str]:
        deps = []
        if not file_path.is_file():
            return deps
            
        content = file_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m_inc = re.match(r"^include\s+([a-zA-Z0-9_.\"'/]+)", line)
            if m_inc:
                raw = m_inc.group(1).strip("\"'")
                deps.append(raw)
                continue
            m_imp = re.match(r"^import\s+.*\s+from\s+([a-zA-Z0-9_.\"'/]+)", line)
            if m_imp:
                raw = m_imp.group(1).strip("\"'")
                deps.append(raw)
        return deps

    def build_graph(self, root_specs: List[str]) -> None:
        visited = set()
        queue = list(root_specs)
        
        while queue:
            cur_spec = queue.pop(0)
            canon_id, phys_path = self.resolver.resolve(cur_spec)
            self.id_to_path[canon_id] = phys_path
            
            if canon_id not in self.adj:
                self.adj[canon_id] = set()
                
            if canon_id in visited:
                continue
            visited.add(canon_id)
            
            deps = self.extract_dependencies(phys_path)
            for dep in deps:
                dep_id, dep_path = self.resolver.resolve(dep)
                self.adj[canon_id].add(dep_id)
                self.id_to_path[dep_id] = dep_path
                if dep_id not in visited:
                    queue.append(dep)

    def topological_sort(self) -> List[str]:
        visited: Dict[str, int] = {} # 0=unvisited, 1=visiting, 2=visited
        order: List[str] = []

        def dfs(node: str, path: List[str]):
            visited[node] = 1
            path.append(node)
            for neighbor in sorted(self.adj.get(node, set())):
                state = visited.get(neighbor, 0)
                if state == 1:
                    cycle_idx = path.index(neighbor)
                    cycle_nodes = path[cycle_idx:] + [neighbor]
                    raise ModuleRegistryError(2126, f"Include cycle detected: {' -> '.join(cycle_nodes)}")
                elif state == 0:
                    dfs(neighbor, path)
            path.pop()
            visited[node] = 2
            order.append(node)

        for node in sorted(self.adj.keys()):
            if visited.get(node, 0) == 0:
                dfs(node, [])

        return order

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Vir module resolver and graph generator")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--resolve", help="Resolve a single module spec")
    parser.add_argument("--entry", help="Build dependency graph from entrypoint")
    args = parser.parse_args()

    resolver = ModuleResolver(args.root)
    if args.resolve:
        canon_id, phys = resolver.resolve(args.resolve)
        print(f"Resolved: {args.resolve} -> {canon_id} ({phys})")
    elif args.entry:
        graph = DependencyGraph(resolver)
        graph.build_graph([args.entry])
        order = graph.topological_sort()
        print(f"Topological order ({len(order)} modules):")
        for m in order:
            print(f"  {m} ({graph.id_to_path[m]})")

if __name__ == "__main__":
    main()

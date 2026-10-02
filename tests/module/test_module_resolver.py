#!/usr/bin/env python3
"""
Unit and integration test suite for Vir Spec v2.0 module resolution and dependency graph.
Tests all requirements of Phase 3 gate:
1. Automatic stdlib and project registry loading
2. Duplicate, missing, and malformed entry rejection
3. Directory alias and prefix collision rejection
4. Repeated and diamond dependency deduplication
5. Include cycle detection with explicit cycle chain
6. Include/import convergence on one canonical Module ID
7. Same realpath through compatible spellings loads once
8. Distinct same-basename files remain distinct
9. Registered-target failure has no search fallback
10. CWD independence (repo root, subdirectory, and unrelated CWD)
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

# Add tools directory to sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from module_graph import ModuleResolver, DependencyGraph, ModuleRegistryError

class TestModuleResolver(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        
        # Structure:
        # root/
        #   stdlib/
        #     stdlib.vri
        #     vir/
        #       core/
        #         types.vri
        #   project/
        #     module.list
        #     src/
        #       main.vri
        #       foo/
        #         bar.vri
        #         baz.vri
        #       dup/
        #         types.vri
        self.stdlib_dir = self.root / "stdlib"
        self.stdlib_vir = self.stdlib_dir / "vir"
        self.stdlib_vir.mkdir(parents=True)
        (self.stdlib_vir / "core").mkdir()
        (self.stdlib_vir / "core/types.vri").write_text("export func int_size: out 8 end.\n")
        (self.stdlib_dir / "stdlib.vri").write_text('core.types = "core/types.vri"\n')
        
        self.proj_dir = self.root / "project"
        self.src_dir = self.proj_dir / "src"
        (self.src_dir / "foo").mkdir(parents=True)
        (self.src_dir / "dup").mkdir(parents=True)
        
        (self.src_dir / "foo/bar.vri").write_text('include virc.foo.baz\nexport func bar_fn: out 1 end.\n')
        (self.src_dir / "foo/baz.vri").write_text('import int_size from core.types\nexport func baz_fn: out 2 end.\n')
        (self.src_dir / "dup/types.vri").write_text('export func custom_types: out 99 end.\n')
        (self.src_dir / "main.vri").write_text('include virc.foo.bar\nimport baz_fn from virc.foo.baz\n')
        
        (self.proj_dir / "module.list").write_text('root = .\nvirc = src\n')

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_automatic_registry_loading_and_resolution(self):
        """Test 1: Automatic stdlib and project registry loading and directory alias resolution."""
        resolver = ModuleResolver(repo_root=self.root, project_root=self.proj_dir, stdlib_root=self.stdlib_dir)
        
        # Test stdlib module resolution
        cid_std, path_std = resolver.resolve("core.types")
        self.assertEqual(cid_std, "mod::core.types")
        self.assertEqual(path_std, (self.stdlib_vir / "core/types.vri").resolve())
        
        # Test project module resolution via directory alias
        cid_proj, path_proj = resolver.resolve("virc.foo.bar")
        self.assertEqual(cid_proj, "mod::virc.foo.bar")
        self.assertEqual(path_proj, (self.src_dir / "foo/bar.vri").resolve())

    def test_duplicate_registration_rejection(self):
        """Test 2: Duplicate registry entry rejection."""
        bad_mod_list = self.proj_dir / "bad_dup.list"
        bad_mod_list.write_text("virc = src\nvirc = other\n")
        
        resolver = ModuleResolver(repo_root=self.root, project_root=self.proj_dir, stdlib_root=self.stdlib_dir)
        with self.assertRaises(ModuleRegistryError) as ctx:
            resolver._parse_registry_file(bad_mod_list, self.proj_dir, "bad_dup.list")
        self.assertEqual(ctx.exception.code, 2121)

    def test_malformed_entry_rejection(self):
        """Test 2b: Malformed registry entry rejection."""
        bad_mod_list = self.proj_dir / "bad_syntax.list"
        bad_mod_list.write_text("this_line_has_no_equals_sign\n")
        
        resolver = ModuleResolver(repo_root=self.root, project_root=self.proj_dir, stdlib_root=self.stdlib_dir)
        with self.assertRaises(ModuleRegistryError) as ctx:
            resolver._parse_registry_file(bad_mod_list, self.proj_dir, "bad_syntax.list")
        self.assertEqual(ctx.exception.code, 2120)

    def test_prefix_collision_rejection(self):
        """Test 3: Prefix collision between directory alias and existing entries."""
        custom_proj = self.root / "custom_proj"
        custom_proj.mkdir()
        (custom_proj / "module.list").write_text("root = .\nmyalias = src\nmyalias.sub = other\n")
        
        with self.assertRaises(ModuleRegistryError) as ctx:
            ModuleResolver(repo_root=self.root, project_root=custom_proj, stdlib_root=self.stdlib_dir)
        self.assertEqual(ctx.exception.code, 2122)

    def test_missing_registered_target_rejection(self):
        """Test 9: Registered target missing fails strictly with no fallback search."""
        resolver = ModuleResolver(repo_root=self.root, project_root=self.proj_dir, stdlib_root=self.stdlib_dir)
        with self.assertRaises(ModuleRegistryError) as ctx:
            resolver.resolve("virc.foo.nonexistent")
        self.assertEqual(ctx.exception.code, 2125)

    def test_diamond_dependency_deduplication(self):
        """Test 4: Repeated / diamond dependency deduplication in graph."""
        resolver = ModuleResolver(repo_root=self.root, project_root=self.proj_dir, stdlib_root=self.stdlib_dir)
        graph = DependencyGraph(resolver)
        graph.build_graph(["virc.main"])
        
        order = graph.topological_sort()
        # Verify each module appears exactly once
        self.assertEqual(len(order), len(set(order)))
        # Order should be core.types -> virc.foo.baz -> virc.foo.bar -> virc.main
        self.assertIn("mod::core.types", order)
        self.assertIn("mod::virc.foo.baz", order)
        self.assertIn("mod::virc.foo.bar", order)
        self.assertIn("mod::virc.main", order)
        
        idx_types = order.index("mod::core.types")
        idx_baz = order.index("mod::virc.foo.baz")
        idx_bar = order.index("mod::virc.foo.bar")
        self.assertLess(idx_types, idx_baz)
        self.assertLess(idx_baz, idx_bar)

    def test_include_cycle_chain_reporting(self):
        """Test 5: Include cycle detected with helpful chain."""
        (self.src_dir / "foo/cycle_a.vri").write_text("include virc.foo.cycle_b\n")
        (self.src_dir / "foo/cycle_b.vri").write_text("include virc.foo.cycle_a\n")
        
        resolver = ModuleResolver(repo_root=self.root, project_root=self.proj_dir, stdlib_root=self.stdlib_dir)
        graph = DependencyGraph(resolver)
        graph.build_graph(["virc.foo.cycle_a"])
        
        with self.assertRaises(ModuleRegistryError) as ctx:
            graph.topological_sort()
        self.assertEqual(ctx.exception.code, 2126)
        self.assertIn("cycle_a -> mod::virc.foo.cycle_b -> mod::virc.foo.cycle_a", str(ctx.exception))

    def test_same_basename_distinct_identities(self):
        """Test 8: Distinct same-basename files remain distinct."""
        resolver = ModuleResolver(repo_root=self.root, project_root=self.proj_dir, stdlib_root=self.stdlib_dir)
        cid_std, path_std = resolver.resolve("core.types")
        cid_proj, path_proj = resolver.resolve("virc.dup.types")
        
        self.assertNotEqual(cid_std, cid_proj)
        self.assertNotEqual(path_std, path_proj)

    def test_same_realpath_convergence(self):
        """Test 7: Same physical unit reached through compatible spellings converges on one Module ID."""
        resolver = ModuleResolver(repo_root=self.root, project_root=self.proj_dir, stdlib_root=self.stdlib_dir)
        # Resolved via registry
        cid_reg, p_reg = resolver.resolve("virc.foo.baz")
        # Resolved via direct file path
        cid_file, p_file = resolver.resolve("src/foo/baz.vri")
        
        self.assertEqual(p_reg.resolve(), p_file.resolve())
        self.assertEqual(cid_reg, cid_file)

    def test_cwd_independence(self):
        """Test 10: Execution from repo root, subdirectory, and unrelated CWD yields identical results."""
        unrelated_cwd = Path(tempfile.mkdtemp()).resolve()
        sub_dir = self.src_dir / "foo"
        
        try:
            # 1. From root
            os.chdir(self.root)
            r1 = ModuleResolver(repo_root=self.root, project_root=self.proj_dir, stdlib_root=self.stdlib_dir)
            c1, p1 = r1.resolve("virc.foo.bar")
            
            # 2. From subdir
            os.chdir(sub_dir)
            r2 = ModuleResolver(repo_root=self.root, project_root=self.proj_dir, stdlib_root=self.stdlib_dir)
            c2, p2 = r2.resolve("virc.foo.bar")
            
            # 3. From unrelated CWD
            os.chdir(unrelated_cwd)
            r3 = ModuleResolver(repo_root=self.root, project_root=self.proj_dir, stdlib_root=self.stdlib_dir)
            c3, p3 = r3.resolve("virc.foo.bar")
            
            self.assertEqual(c1, c2)
            self.assertEqual(c2, c3)
            self.assertEqual(p1, p2)
            self.assertEqual(p2, p3)
        finally:
            shutil.rmtree(unrelated_cwd)

if __name__ == "__main__":
    unittest.main()

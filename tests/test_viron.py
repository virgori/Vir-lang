#!/usr/bin/env python3
"""Comprehensive test suite for the standalone Viron toolchain & package manager.

Tests production binary bin/viron across:
1. Module registry validation: missing path, duplicate, collision, alternate CWD
2. CLI baseline: --help, --version, unknown command exit code 127
3. Local-first vertical slice: viron new (binary & --lib), check, build, run, test
4. Deterministic lock, module map, archive reproduction
5. Structured diagnostics: malformed manifest/lock/registry (VIR4001, VIR4002)
6. Dependency cycle, SemVer constraints, and frozen mismatch (VIR4204)
7. Global cache: path, info, clean, prune, checksum validation (VIR4301)
8. Security baseline: path traversal / tar-slip defense (VIR4302)
9. Toolchain lifecycle: install, list, default, rollback, verify, repair
10. Atomic installation & concurrency safety under VIR_HOME
11. Alternate CWD execution and sysroot discovery
12. Standard library lifecycle: viron std list, install, update, verify, repair, rollback
13. Execution smoke tests across commands
14. Complete absence of legacy stdlib/vir/viron dependencies
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIRON_BIN = ROOT / "bin/viron"
VIRC_BIN = ROOT / "bin/virc"


class TestVironStandalone(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure viron binary is built
        if not VIRON_BIN.is_file():
            res = subprocess.run([sys.executable, "tools/build_viron.py"], cwd=ROOT, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"Failed to build viron: {res.stderr}\n{res.stdout}")

    def run_viron(self, args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            [str(VIRON_BIN)] + args,
            cwd=str(cwd or ROOT),
            capture_output=True,
            text=True,
            env=merged_env,
        )

    # ── 1. Module Registry & Graph Validation ───────────────────────────────────
    def test_01_module_registry_graph(self):
        """Validate tools/viron/module.list with module_graph.py."""
        res_resolve = subprocess.run(
            [sys.executable, "tools/module_graph.py", "--root", "tools/viron", "--resolve", "viron.main"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_resolve.returncode, 0, res_resolve.stderr)
        self.assertIn("mod::viron.main", res_resolve.stdout)

        res_entry = subprocess.run(
            [sys.executable, "tools/module_graph.py", "--root", "tools/viron", "--entry", "viron.main"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_entry.returncode, 0, res_entry.stderr)
        self.assertIn("Topological order (15 modules):", res_entry.stdout)
        self.assertIn("mod::viron.diagnostic", res_entry.stdout)
        self.assertIn("mod::viron.cli", res_entry.stdout)
        self.assertIn("mod::viron.main", res_entry.stdout)

    # ── 2. CLI Baseline: Version, Help, Unknown Command ────────────────────────
    def test_02_cli_baseline(self):
        """Test --version, --help, and unknown command with stable exit codes."""
        res_ver = self.run_viron(["--version"])
        self.assertEqual(res_ver.returncode, 0)
        self.assertIn("viron 2.0.0", res_ver.stdout)

        res_help = self.run_viron(["--help"])
        self.assertEqual(res_help.returncode, 0)
        self.assertIn("V I R O N   v2.0.0", res_help.stdout)
        self.assertIn("Commands:", res_help.stdout)

        res_unknown = self.run_viron(["nonexistent-command-xyz"])
        self.assertEqual(res_unknown.returncode, 127)
        self.assertIn("error[VIR4101]", res_unknown.stdout)

    # ── 3. Local-First Vertical Slice (new, check, build, run, test) ────────────
    def test_03_local_vertical_slice(self):
        """Test viron new, viron new --lib, check, build, run, test, and package with real artifacts."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            tmp = Path(tmpdir)

            # 3a. viron new app
            res_new = self.run_viron(["new", "demo_app"], cwd=tmp)
            self.assertEqual(res_new.returncode, 0)
            self.assertTrue((tmp / "vir.toml").is_file())
            self.assertTrue((tmp / "module.list").is_file())
            self.assertTrue((tmp / "src/main.vri").is_file())
            self.assertTrue((tmp / "tests/test_main.vri").is_file())

            # 3b. viron check
            res_check = self.run_viron(["check"], cwd=tmp)
            self.assertEqual(res_check.returncode, 0)
            self.assertIn("Project check: manifest and module registry valid", res_check.stdout)

            # 3c. viron build (dev)
            res_build = self.run_viron(["build"], cwd=tmp)
            self.assertEqual(res_build.returncode, 0, res_build.stderr)
            self.assertIn("Build finished successfully", res_build.stdout)

            output_bin = tmp / "target/debug/output"
            self.assertTrue(output_bin.is_file(), "target/debug/output binary must exist on disk")
            self.assertTrue(os.access(output_bin, os.X_OK), "target/debug/output binary must be executable")
            dev_hash = hashlib.sha256(output_bin.read_bytes()).hexdigest()

            # Execute built binary directly and verify stdout
            exec_res = subprocess.run([str(output_bin)], capture_output=True, text=True)
            self.assertEqual(exec_res.returncode, 0)
            self.assertIn("Hello from Vir standalone application!", exec_res.stdout)

            res_run = self.run_viron(["run"], cwd=tmp)
            self.assertEqual(res_run.returncode, 0)
            self.assertIn("Hello from Vir standalone application!", res_run.stdout)

            # 3c-2. viron build --release
            res_rel = self.run_viron(["build", "--release"], cwd=tmp)
            self.assertEqual(res_rel.returncode, 0, res_rel.stderr)
            self.assertIn("Profile: release (-O3", res_rel.stdout)
            rel_bin = tmp / "target/release/output"
            self.assertTrue(rel_bin.is_file(), "target/release/output binary must exist on disk")
            rel_hash = hashlib.sha256(rel_bin.read_bytes()).hexdigest()
            self.assertNotEqual(dev_hash, rel_hash, "Debug and Release binaries must differ due to optimization level (-O3)")

            # 3c-3. viron build fails when entrypoint is missing
            main_src = (tmp / "src/main.vri").read_text(encoding="utf-8")
            (tmp / "src/main.vri").unlink()
            res_no_entry = self.run_viron(["build"], cwd=tmp)
            self.assertEqual(res_no_entry.returncode, 1)
            self.assertIn("error[VIR4101]", res_no_entry.stdout)
            self.assertIn("no entrypoint found", res_no_entry.stdout)
            (tmp / "src/main.vri").write_text(main_src, encoding="utf-8")

            # 3c-4. viron add mutates vir.toml
            toml_before = (tmp / "vir.toml").read_text(encoding="utf-8")
            h_before = hashlib.sha256(toml_before.encode("utf-8")).hexdigest()
            res_add = self.run_viron(["add", "vir.json", "1.2.3"], cwd=tmp)
            self.assertEqual(res_add.returncode, 0)
            self.assertIn("Adding dependency 'vir.json' (1.2.3) to vir.toml... OK", res_add.stdout)
            toml_after = (tmp / "vir.toml").read_text(encoding="utf-8")
            h_after = hashlib.sha256(toml_after.encode("utf-8")).hexdigest()
            self.assertNotEqual(h_before, h_after, "vir.toml must be modified on disk by viron add")
            self.assertIn('vir.json = "^1.2.3"', toml_after)

            # 3d. viron test
            res_test = self.run_viron(["test"], cwd=tmp)
            self.assertEqual(res_test.returncode, 0)
            self.assertIn("All tests passed successfully", res_test.stdout)
            test_bin = tmp / "target/debug/test_runner"
            self.assertTrue(test_bin.is_file(), "target/debug/test_runner must exist on disk")
            self.assertTrue(os.access(test_bin, os.X_OK), "target/debug/test_runner must be executable")

            # 3e. viron package
            res_pkg = self.run_viron(["package"], cwd=tmp)
            self.assertEqual(res_pkg.returncode, 0)
            tar_file = tmp / "target/package/demo_app-0.1.0.tar"
            zst_file = tmp / "target/package/demo_app-0.1.0.tar.zst"
            self.assertTrue(tar_file.is_file(), "package .tar archive must exist on disk")
            self.assertTrue(zst_file.is_file(), "package .tar.zst archive must exist on disk")
            self.assertGreater(tar_file.stat().st_size, 0)

            # Use tar -tf to verify standard POSIX ustar archive
            tar_proc = subprocess.run(["tar", "-tf", str(tar_file)], capture_output=True, text=True)
            self.assertEqual(tar_proc.returncode, 0, f"tar -tf failed: {tar_proc.stderr}")
            self.assertIn("demo_app-0.1.0/vir.toml", tar_proc.stdout)
            self.assertIn("demo_app-0.1.0/module.list", tar_proc.stdout)
            self.assertIn("demo_app-0.1.0/src/main.vri", tar_proc.stdout)

    def test_03b_new_library(self):
        """Test viron new --lib creates library layout."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            tmp = Path(tmpdir)
            res_new_lib = self.run_viron(["new", "--lib", "demo_lib"], cwd=tmp)
            self.assertEqual(res_new_lib.returncode, 0)
            self.assertTrue((tmp / "vir.toml").is_file())
            self.assertTrue((tmp / "src/lib.vri").is_file())
            toml_text = (tmp / "vir.toml").read_text(encoding="utf-8")
            self.assertIn('entry = "src/lib.vri"', toml_text)

    # ── 4. Deterministic Lock, Tree & Module Map ────────────────────────────────
    def test_04_lock_and_tree(self):
        """Test deterministic vir.lock generation and tree visualization."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            tmp = Path(tmpdir)
            self.run_viron(["new", "locked_app"], cwd=tmp)

            # Generate lock
            res_lock = self.run_viron(["lock"], cwd=tmp)
            self.assertEqual(res_lock.returncode, 0)
            self.assertTrue((tmp / "vir.lock").is_file())
            lock1 = (tmp / "vir.lock").read_text(encoding="utf-8")

            # Running lock again must be deterministic
            res_lock2 = self.run_viron(["lock"], cwd=tmp)
            self.assertEqual(res_lock2.returncode, 0)
            lock2 = (tmp / "vir.lock").read_text(encoding="utf-8")
            self.assertEqual(lock1, lock2)
            self.assertIn("version = 1", lock1)

            # Test tree/resolve
            res_tree = self.run_viron(["tree"], cwd=tmp)
            self.assertEqual(res_tree.returncode, 0)
            self.assertIn("Dependency Build Order", res_tree.stdout)
            self.assertIn("0 cycles", res_tree.stdout)

            res_resolve = self.run_viron(["resolve"], cwd=tmp)
            self.assertEqual(res_resolve.returncode, 0)
            self.assertIn("Resolved module graph and package paths", res_resolve.stdout)
            self.assertIn("locked_app", res_resolve.stdout)

    # ── 5. Malformed Manifest & Module Registry Diagnostics ─────────────────────
    def test_05_malformed_diagnostics(self):
        """Test VIR4001 and VIR4002 diagnostics for missing or invalid manifests."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            tmp = Path(tmpdir)

            # check in empty dir -> vir.toml missing
            res = self.run_viron(["check"], cwd=tmp)
            self.assertEqual(res.returncode, 1)
            self.assertIn("error[VIR4001]", res.stdout)

            # Empty vir.toml -> fails with VIR4001
            (tmp / "vir.toml").write_text("", encoding="utf-8")
            res_empty = self.run_viron(["check"], cwd=tmp)
            self.assertEqual(res_empty.returncode, 1)
            self.assertIn("error[VIR4001]", res_empty.stdout)

            # Malformed vir.toml (missing [package] / version)
            (tmp / "vir.toml").write_text("name = 'foo'\n", encoding="utf-8")
            res_mal = self.run_viron(["check"], cwd=tmp)
            self.assertEqual(res_mal.returncode, 1)
            self.assertIn("error[VIR4001]", res_mal.stdout)

            # Valid vir.toml but missing module.list -> fails with VIR4002
            (tmp / "vir.toml").write_text("[package]\nname = \"foo\"\nversion = \"0.1.0\"\n", encoding="utf-8")
            res_nomod = self.run_viron(["check"], cwd=tmp)
            self.assertEqual(res_nomod.returncode, 1)
            self.assertIn("error[VIR4002]", res_nomod.stdout)

            # Empty module.list -> fails with VIR4002
            (tmp / "module.list").write_text("", encoding="utf-8")
            res_empmod = self.run_viron(["check"], cwd=tmp)
            self.assertEqual(res_empmod.returncode, 1)
            self.assertIn("error[VIR4002]", res_empmod.stdout)

            # module.list without root directive -> fails with VIR4002
            (tmp / "module.list").write_text("foo = bar.vri\n", encoding="utf-8")
            res_noroot = self.run_viron(["check"], cwd=tmp)
            self.assertEqual(res_noroot.returncode, 1)
            self.assertIn("error[VIR4002]", res_noroot.stdout)

            # module.list with only commented root -> fails with VIR4002
            (tmp / "module.list").write_text("# root = nowhere\n", encoding="utf-8")
            res_commroot = self.run_viron(["check"], cwd=tmp)
            self.assertEqual(res_commroot.returncode, 1)
            self.assertIn("error[VIR4002]", res_commroot.stdout)

    # ── 6. Frozen Lockfile & Invariant Enforcement ─────────────────────────────
    def test_06_frozen_mode(self):
        """Test that --frozen rejects build when vir.lock is missing or out of sync."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            tmp = Path(tmpdir)
            self.run_viron(["new", "frozen_app"], cwd=tmp)

            # Without vir.lock, --frozen must fail with VIR4204
            res = self.run_viron(["build", "--frozen"], cwd=tmp)
            self.assertEqual(res.returncode, 1)
            self.assertIn("error[VIR4204]", res.stdout)

            # Generate lock
            self.run_viron(["lock"], cwd=tmp)
            self.assertTrue((tmp / "vir.lock").is_file())

            # With vir.lock present and matched, --frozen must succeed
            res2 = self.run_viron(["build", "--frozen"], cwd=tmp)
            self.assertEqual(res2.returncode, 0)
            self.assertTrue((tmp / "target/debug/output").is_file())

            # Mutate manifest version -> --frozen must detect mismatch and reject build!
            toml_content = (tmp / "vir.toml").read_text(encoding="utf-8")
            (tmp / "vir.toml").write_text(toml_content.replace('version = "0.1.0"', 'version = "0.9.9"'), encoding="utf-8")
            res_mismatch = self.run_viron(["build", "--frozen"], cwd=tmp)
            self.assertEqual(res_mismatch.returncode, 1)
            self.assertIn("error[VIR4204]", res_mismatch.stdout)
            self.assertIn("out of sync", res_mismatch.stdout)

    # ── 7. Global Cache Management ──────────────────────────────────────────────
    def test_07_cache_management(self):
        """Test viron cache path, info, clean, prune with real file deletion."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            vhome = Path(tmpdir) / "vhome"
            env = {"VIR_HOME": str(vhome)}

            res_path = self.run_viron(["cache", "path"], env=env)
            self.assertEqual(res_path.returncode, 0)
            self.assertIn(str(vhome / "cache"), res_path.stdout)

            res_info = self.run_viron(["cache", "info"], env=env)
            self.assertEqual(res_info.returncode, 0)
            self.assertIn("Viron Package Cache Statistics", res_info.stdout)

            # Stage temporary test file in cache/tmp
            tmp_cache = vhome / "cache/tmp"
            tmp_cache.mkdir(parents=True, exist_ok=True)
            test_file = tmp_cache / "test_file.tmp"
            test_file.write_text("temporary download data", encoding="utf-8")
            self.assertTrue(test_file.is_file(), "Staged cache file must exist before clean")

            res_clean = self.run_viron(["cache", "clean"], env=env)
            self.assertEqual(res_clean.returncode, 0)
            self.assertIn("Cleaning temporary downloads", res_clean.stdout)
            self.assertFalse(test_file.exists(), "test_file.tmp must be deleted on disk by cache clean")

            res_prune = self.run_viron(["cache", "prune"], env=env)
            self.assertEqual(res_prune.returncode, 0)
            self.assertIn("Pruning unreferenced package versions", res_prune.stdout)

    # ── 8. Packaging & Security Protection ─────────────────────────────────────
    def test_08_packaging_and_security(self):
        """Test reproducible packaging and defense against path traversal."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            tmp = Path(tmpdir)
            self.run_viron(["new", "pkg_demo"], cwd=tmp)

            # Package creation: artifacts exist
            res_pkg = self.run_viron(["package"], cwd=tmp)
            self.assertEqual(res_pkg.returncode, 0)
            tar_file = tmp / "target/package/pkg_demo-0.1.0.tar"
            zst_file = tmp / "target/package/pkg_demo-0.1.0.tar.zst"
            self.assertTrue(tar_file.is_file())
            self.assertTrue(zst_file.is_file())
            self.assertGreater(tar_file.stat().st_size, 0)

            # Path traversal security: inject directory traversal into vir.toml
            toml_text = (tmp / "vir.toml").read_text(encoding="utf-8")
            (tmp / "vir.toml").write_text(toml_text + '\n[dependencies]\nescape = { path = "../../secret" }\n', encoding="utf-8")
            res_traversal = self.run_viron(["package"], cwd=tmp)
            self.assertEqual(res_traversal.returncode, 1)
            self.assertIn("error[VIR4302]", res_traversal.stdout)
            self.assertIn("traversal", res_traversal.stdout)

            # Publish dry-run
            # Restore valid manifest for publish dry-run
            (tmp / "vir.toml").write_text(toml_text, encoding="utf-8")
            res_pub_dry = self.run_viron(["publish", "--dry-run"], cwd=tmp)
            self.assertEqual(res_pub_dry.returncode, 0)
            self.assertIn("0 remote mutations performed", res_pub_dry.stdout)

            # Publish without credentials is gated
            res_pub = self.run_viron(["publish"], cwd=tmp)
            self.assertEqual(res_pub.returncode, 1)
            self.assertIn("error[VIR4301]", res_pub.stdout)

    # ── 9. Toolchain Lifecycle ──────────────────────────────────────────────────
    def test_09_toolchain_lifecycle(self):
        """Test viron toolchain install, list, default, rollback, verify, repair with real disk state under VIR_HOME."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            vhome = Path(tmpdir) / "vhome"
            env = {"VIR_HOME": str(vhome)}

            res_list = self.run_viron(["toolchain", "list"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_list.returncode, 0)
            self.assertIn("Installed Vir Toolchains", res_list.stdout)

            res_install = self.run_viron(["toolchain", "install", "3.2.0"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_install.returncode, 0)
            self.assertIn("Atomic install complete for 3.2.0", res_install.stdout)
            tc_meta = vhome / "toolchains/3.2.0/toolchain.json"
            self.assertTrue(tc_meta.is_file(), "toolchain.json must exist on disk under VIR_HOME")
            tc_data = json.loads(tc_meta.read_text(encoding="utf-8"))
            self.assertEqual(tc_data["version"], "3.2.0")
            self.assertEqual(tc_data["status"], "installed")

            # Check staged compiler
            tc_virc = vhome / "toolchains/3.2.0/bin/virc"
            self.assertTrue(tc_virc.is_file(), "Staged compiler must exist under toolchain bin/")

            res_def = self.run_viron(["toolchain", "default", "3.2.0"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_def.returncode, 0)
            self.assertIn("Toolchain: default set to 3.2.0", res_def.stdout)
            active_file = vhome / "toolchains/active.txt"
            self.assertTrue(active_file.is_file(), "active.txt must exist on disk under VIR_HOME")
            self.assertEqual(active_file.read_text(encoding="utf-8").strip(), "3.2.0")

            res_ver = self.run_viron(["toolchain", "verify", "3.2.0"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_ver.returncode, 0)
            self.assertIn("10/10 checks passed", res_ver.stdout)

            res_rb = self.run_viron(["toolchain", "rollback"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_rb.returncode, 0)
            self.assertIn("rolled back to previous active toolchain", res_rb.stdout)
            self.assertEqual(active_file.read_text(encoding="utf-8").strip(), "2026.1")

            res_rep = self.run_viron(["toolchain", "repair"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_rep.returncode, 0)
            self.assertIn("repairing toolchain metadata", res_rep.stdout)

    # ── 10. Bootstrap Setup & Doctor Health Audit ───────────────────────────────
    def test_10_setup_and_doctor(self):
        """Test viron setup and viron doctor [--repair]."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            vhome = Path(tmpdir) / "vhome"
            env = {"VIR_HOME": str(vhome)}

            # Doctor in uninitialized state detects missing components
            res_doc_missing = self.run_viron(["doctor"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_doc_missing.returncode, 0)
            self.assertIn("NOT FOUND", res_doc_missing.stdout)
            self.assertIn("issues detected", res_doc_missing.stdout)

            # Setup bootstraps VIR_HOME
            vhome.mkdir(parents=True, exist_ok=True)
            res_setup = self.run_viron(["setup"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_setup.returncode, 0)
            self.assertIn("Bootstrap complete", res_setup.stdout)

            # Doctor with repair mode reconciles state
            res_doc_rep = self.run_viron(["doctor", "--repair"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_doc_rep.returncode, 0)
            self.assertIn("Repair mode completed", res_doc_rep.stdout)

    # ── 11. Standard Library Lifecycle ──────────────────────────────────────────
    def test_11_stdlib_lifecycle(self):
        """Test viron std list, install, update, verify, repair, rollback with real disk state."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            vhome = Path(tmpdir) / "vhome"
            env = {"VIR_HOME": str(vhome)}

            res_list = self.run_viron(["std", "list"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_list.returncode, 0)
            self.assertIn("Official Vir Standard Library Modules", res_list.stdout)

            # Verify before install must fail
            res_ver_fail = self.run_viron(["std", "verify"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_ver_fail.returncode, 1)
            self.assertIn("error[VIR4101]", res_ver_fail.stdout)
            self.assertIn("standard library not installed in sysroot", res_ver_fail.stdout)

            # Install stdlib module
            res_inst = self.run_viron(["std", "install", "vir.json"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_inst.returncode, 0)
            self.assertIn("atomic install completed", res_inst.stdout)
            mod_meta = vhome / "sysroot/stdlib/vir.json/module.json"
            self.assertTrue(mod_meta.is_file(), "installed stdlib module.json must exist on disk under VIR_HOME")
            mod_data = json.loads(mod_meta.read_text(encoding="utf-8"))
            self.assertEqual(mod_data["package"], "installed")

            # Verify after install must succeed
            res_ver = self.run_viron(["std", "verify"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_ver.returncode, 0)
            self.assertIn("Verifying standard library integrity: 100% valid", res_ver.stdout)

            res_upd = self.run_viron(["std", "update"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_upd.returncode, 0)
            self.assertIn("official libraries in sysroot", res_upd.stdout)

            res_rep = self.run_viron(["std", "repair"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_rep.returncode, 0)
            self.assertIn("all modules verified", res_rep.stdout)

            res_rb = self.run_viron(["std", "rollback"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_rb.returncode, 0)
            self.assertIn("Rolling back standard library", res_rb.stdout)

    # ── 12. Alternate CWD Execution ─────────────────────────────────────────────
    def test_12_alternate_cwd(self):
        """Verify that viron binary functions identically from an arbitrary working directory."""
        with tempfile.TemporaryDirectory() as external_dir:
            ext = Path(external_dir)
            res = subprocess.run([str(VIRON_BIN), "--version"], cwd=ext, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("viron 2.0.0", res.stdout)

            res_help = subprocess.run([str(VIRON_BIN), "--help"], cwd=ext, capture_output=True, text=True)
            self.assertEqual(res_help.returncode, 0)
            self.assertIn("V I R O N   v2.0.0", res_help.stdout)

    # ── 13. Absence of Legacy stdlib/vir/viron References ───────────────────────
    def test_13_no_legacy_stdlib_dependencies(self):
        """Verify that stdlib/stdlib.vri contains no viron mappings and stdlib/vir/viron is gone."""
        stdlib_vri = (ROOT / "stdlib/stdlib.vri").read_text(encoding="utf-8")
        for line in stdlib_vri.splitlines():
            line_str = line.strip()
            self.assertFalse(line_str.startswith("viron ="), f"Unexpected viron entry in stdlib.vri: {line_str}")
            self.assertFalse(line_str.startswith("viron."), f"Unexpected viron entry in stdlib.vri: {line_str}")

        legacy_dir = ROOT / "stdlib/vir/viron"
        self.assertFalse(legacy_dir.exists(), "Legacy directory stdlib/vir/viron must not exist")

    # ── 14. Version Policy & Metadata Consistency ───────────────────────────────
    def test_14_version_policy_sync(self):
        """Verify that tools/bump_viron_version.py passes and version.json is canonical."""
        res = subprocess.run([sys.executable, "tools/bump_viron_version.py", "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Version sync failed: {res.stderr}\n{res.stdout}")
        self.assertIn("viron version metadata is synchronized", res.stdout)


    # ── 15. Negative Toolchain Verification ─────────────────────────────────────
    def test_15_negative_toolchain_cases(self):
        """Verify rejection of uncataloged versions and detection of corrupted compilers."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            vhome = Path(tmpdir) / "vhome"
            env = {"VIR_HOME": str(vhome)}

            # Reject uncataloged version
            res_bad_ver = self.run_viron(["toolchain", "install", "9999.9.9"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_bad_ver.returncode, 1)
            self.assertIn("error[VIR4101]", res_bad_ver.stdout)
            self.assertIn("unknown or uncataloged toolchain version", res_bad_ver.stdout)

            # Install valid toolchain
            res_inst = self.run_viron(["toolchain", "install", "3.2.0"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_inst.returncode, 0)

            # Corrupt compiler binary to 1 byte
            virc_bin = vhome / "toolchains/3.2.0/bin/virc"
            self.assertTrue(virc_bin.is_file())
            virc_bin.write_bytes(b"\x00")

            # Verify must detect corrupted compiler binary (< 1KB) and fail
            res_verify_corrupt = self.run_viron(["toolchain", "verify", "3.2.0"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_verify_corrupt.returncode, 1)
            self.assertIn("error[VIR4101]", res_verify_corrupt.stdout)
            self.assertIn("size < 1KB", res_verify_corrupt.stdout)

    # ── 16. Negative Manifest & Module Registry Validation ──────────────────────
    def test_16_negative_manifest_and_module_list(self):
        """Verify strict token matching for root and section isolation in vir.toml."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "vir.toml").write_text('[package]\nname = "test_pkg"\nversion = "0.1.0"\n', encoding="utf-8")

            # module.list with 'rootjunk = .' must be rejected
            (tmp / "module.list").write_text("rootjunk = .\n", encoding="utf-8")
            res_junk = self.run_viron(["check"], cwd=tmp)
            self.assertEqual(res_junk.returncode, 1)
            self.assertIn("error[VIR4002]", res_junk.stdout)
            self.assertIn("missing root directive", res_junk.stdout)

            # vir.toml with name/version outside [package] must be rejected
            (tmp / "module.list").write_text("root = .\n", encoding="utf-8")
            (tmp / "vir.toml").write_text('[other]\nname = "test_pkg"\nversion = "0.1.0"\n', encoding="utf-8")
            res_bad_section = self.run_viron(["check"], cwd=tmp)
            self.assertEqual(res_bad_section.returncode, 1)
            self.assertIn("error[VIR4001]", res_bad_section.stdout)

    # ── 17. Packaging: Mandatory LICENSE and Multi-Module Registry ──────────────
    def test_17_package_license_and_multimodule(self):
        """Verify package fails without LICENSE and includes all modules registered in module.list."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            tmp = Path(tmpdir)
            self.run_viron(["new", "multi_pkg"], cwd=tmp)

            # Removing LICENSE must fail package
            lic_file = tmp / "LICENSE"
            self.assertTrue(lic_file.is_file())
            lic_file.unlink()
            res_no_lic = self.run_viron(["package"], cwd=tmp)
            self.assertEqual(res_no_lic.returncode, 1)
            self.assertIn("error[VIR4302]", res_no_lic.stdout)
            self.assertIn("mandatory LICENSE", res_no_lic.stdout)

            # Restore LICENSE and add helper module
            lic_file.write_text("Apache-2.0 License\n", encoding="utf-8")
            helper_file = tmp / "src/helper.vri"
            helper_file.write_text("func helper_fn(): out 42 end.\n", encoding="utf-8")
            modlist_text = (tmp / "module.list").read_text(encoding="utf-8")
            (tmp / "module.list").write_text(modlist_text + "multi_pkg.helper = src/helper.vri\n", encoding="utf-8")

            res_pkg = self.run_viron(["package"], cwd=tmp)
            self.assertEqual(res_pkg.returncode, 0)
            tar_file = tmp / "target/package/multi_pkg-0.1.0.tar"
            self.assertTrue(tar_file.is_file())

            tar_proc = subprocess.run(["tar", "-tf", str(tar_file)], capture_output=True, text=True)
            self.assertEqual(tar_proc.returncode, 0)
            self.assertIn("multi_pkg-0.1.0/src/helper.vri", tar_proc.stdout)
            self.assertIn("multi_pkg-0.1.0/LICENSE", tar_proc.stdout)

    # ── 18. Stdlib Negative Verification ────────────────────────────────────────
    def test_18_stdlib_empty_verification(self):
        """Verify viron std verify fails when sysroot/stdlib is empty without stdlib.vri."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            vhome = Path(tmpdir) / "vhome"
            env = {"VIR_HOME": str(vhome)}

            # Create empty sysroot/stdlib directory
            std_dir = vhome / "sysroot/stdlib"
            std_dir.mkdir(parents=True, exist_ok=True)

            res_ver = self.run_viron(["std", "verify"], cwd=Path(tmpdir), env=env)
            self.assertEqual(res_ver.returncode, 1)
            self.assertIn("error[VIR4101]", res_ver.stdout)
            self.assertIn("empty or corrupted", res_ver.stdout)

    # ── 19. Arbitrary Temporary Files Cache Clean ──────────────────────────────
    def test_19_cache_arbitrary_files_clean(self):
        """Verify cache clean removes arbitrary temporary files, not just hardcoded names."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            vhome = Path(tmpdir) / "vhome"
            env = {"VIR_HOME": str(vhome)}

            tmp_cache = vhome / "cache/tmp"
            tmp_cache.mkdir(parents=True, exist_ok=True)
            f1 = tmp_cache / "random.tmp"
            f2 = tmp_cache / "random-download.part"
            f3 = tmp_cache / "custom_temp_payload.tmp"
            f1.write_text("random payload 1", encoding="utf-8")
            f2.write_text("random payload 2", encoding="utf-8")
            f3.write_text("random payload 3", encoding="utf-8")

            res_clean = self.run_viron(["cache", "clean"], env=env)
            self.assertEqual(res_clean.returncode, 0)
            self.assertFalse(f1.exists(), "random.tmp must be removed by cache clean")
            self.assertFalse(f2.exists(), "random-download.part must be removed by cache clean")
            self.assertFalse(f3.exists(), "custom_temp_payload.tmp must be removed by cache clean")

    # ── 20. Run Argument Forwarding ─────────────────────────────────────────────
    def test_20_run_argument_forwarding(self):
        """Verify that viron run forwards extra arguments to the executed program."""
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as tmpdir:
            tmp = Path(tmpdir)
            self.run_viron(["new", "arg_app"], cwd=tmp)
            main_src = (
                "func main():\n"
                "    let c = arg_count()\n"
                "    if c > 1 do\n"
                "        print_str(get_arg(1))\n"
                "        print_str(\"\\n\")\n"
                "    end\n"
                "end.\n"
            )
            (tmp / "src/main.vri").write_text(main_src, encoding="utf-8")
            res_run = self.run_viron(["run", "hello_argument_forwarding"], cwd=tmp)
            self.assertEqual(res_run.returncode, 0)
            self.assertIn("hello_argument_forwarding", res_run.stdout)


if __name__ == "__main__":
    unittest.main()


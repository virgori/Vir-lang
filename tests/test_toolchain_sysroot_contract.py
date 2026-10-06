#!/usr/bin/env python3
"""
tests/test_toolchain_sysroot_contract.py — Regression contract for VIRC-ISS-0043 / VIRC-PLN-0028.

Verifies:
1. virc --print-sysroot and --print-stdlib in text and JSON modes.
2. Explicit CLI override (--sysroot <path>) and fail-closed validation.
3. Environment override (VIR_SYSROOT=<path>) and fail-closed validation.
4. Relative path canonicalization (--sysroot . and VIR_SYSROOT=.).
5. Malformed registry rejection (schema validation & compatibility checks).
6. Missing prelude rejection (core/types.vri and rt/alloc.vri verification).
7. Standalone binary isolation (no ancestor or project tree stdlib stealing).
8. Side-by-side toolchains with distinct sysroots.
9. Precedence: CLI --sysroot takes precedence over VIR_SYSROOT.
10. CWD independence: external projects compile from foreign directories without vendoring stdlib.
11. Symlink invocation resolution to canonical installed sysroot.
12. vir-lsp parity: help documentation, sysroot argument support, fail-closed validation.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIRC = ROOT / "bin" / "virc"
VIR_LSP = ROOT / "bin" / "vir-lsp"


def sign_if_darwin(path):
    if sys.platform == "darwin":
        subprocess.run(["codesign", "-s", "-", "-f", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def run_cmd(args, cwd=None, env=None):
    base_env = os.environ.copy()
    if env:
        base_env.update(env)
    return subprocess.run(
        args,
        cwd=cwd or str(ROOT),
        env=base_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_print_sysroot_text():
    res = run_cmd([str(VIRC), "--print-sysroot", "--color=never"])
    assert res.returncode == 0, f"Expected 0, got {res.returncode}: {res.stderr}"
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    assert len(lines) == 1, f"Expected 1 line output, got: {res.stdout}"
    assert lines[0] == str(ROOT), f"Expected {ROOT}, got {lines[0]}"


def test_print_stdlib_text():
    res = run_cmd([str(VIRC), "--print-stdlib", "--color=never"])
    assert res.returncode == 0, f"Expected 0, got {res.returncode}: {res.stderr}"
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    assert len(lines) == 1, f"Expected 1 line output, got: {res.stdout}"
    assert lines[0] == str(ROOT / "stdlib"), f"Expected {ROOT / 'stdlib'}, got {lines[0]}"


def test_print_sysroot_json():
    res = run_cmd([str(VIRC), "--print-sysroot", "--json"])
    assert res.returncode == 0, f"Expected 0, got {res.returncode}: {res.stderr}"
    data = json.loads(res.stdout.strip())
    assert data.get("status") == "ok", f"Expected ok, got {data}"
    assert data.get("sysroot") == str(ROOT), f"Expected {ROOT}, got {data.get('sysroot')}"


def test_print_stdlib_json():
    res = run_cmd([str(VIRC), "--print-stdlib", "--json"])
    assert res.returncode == 0, f"Expected 0, got {res.returncode}: {res.stderr}"
    data = json.loads(res.stdout.strip())
    assert data.get("status") == "ok", f"Expected ok, got {data}"
    assert data.get("stdlib") == str(ROOT / "stdlib"), f"Expected stdlib, got {data.get('stdlib')}"
    assert data.get("registry") == str(ROOT / "stdlib" / "stdlib.vri")


def test_sysroot_override_valid():
    res = run_cmd([str(VIRC), "--sysroot", str(ROOT), "--print-sysroot"])
    assert res.returncode == 0
    assert res.stdout.strip() == str(ROOT)


def test_sysroot_override_invalid_fail_closed():
    res = run_cmd([str(VIRC), "--sysroot", "/nonexistent/vir/path", "--print-sysroot"])
    assert res.returncode == 1
    assert "invalid --sysroot" in res.stdout or "invalid --sysroot" in res.stderr
    assert "E2120" in res.stdout or "E2120" in res.stderr

    res_json = run_cmd([str(VIRC), "--sysroot", "/nonexistent/vir/path", "--print-sysroot", "--json"])
    assert res_json.returncode == 1
    data = json.loads(res_json.stdout.strip())
    assert data.get("error_kind") == "sysroot" or data.get("status") == "error"


def test_sysroot_canonicalization_cli():
    # --sysroot . must canonicalize to absolute path of ROOT, not "."
    res = run_cmd([str(VIRC), "--sysroot", ".", "--print-sysroot"], cwd=str(ROOT))
    assert res.returncode == 0
    assert res.stdout.strip() == str(ROOT)


def test_sysroot_canonicalization_env():
    # VIR_SYSROOT=. must canonicalize to absolute path of ROOT, not "."
    res = run_cmd([str(VIRC), "--print-sysroot"], cwd=str(ROOT), env={"VIR_SYSROOT": "."})
    assert res.returncode == 0
    assert res.stdout.strip() == str(ROOT)


def test_vir_sysroot_env_valid():
    res = run_cmd([str(VIRC), "--print-sysroot"], env={"VIR_SYSROOT": str(ROOT)})
    assert res.returncode == 0
    assert res.stdout.strip() == str(ROOT)


def test_vir_sysroot_env_invalid_fail_closed():
    res = run_cmd([str(VIRC), "--print-sysroot"], env={"VIR_SYSROOT": "/invalid/env/sysroot"})
    assert res.returncode == 1
    assert "invalid VIR_SYSROOT" in res.stdout or "invalid VIR_SYSROOT" in res.stderr
    assert "E2120" in res.stdout or "E2120" in res.stderr


def test_malformed_registry_fail_closed():
    scratch_dir = ROOT / "scratch" / "malformed_reg_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text("not a registry\n", encoding="utf-8")

    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 1
    assert "E2120" in res.stdout or "E2120" in res.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_missing_prelude_fail_closed():
    scratch_dir = ROOT / "scratch" / "missing_prelude_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    # Specifies root = vir, but vir/core/types.vri is missing
    (scratch_dir / "stdlib" / "stdlib.vri").write_text("root = vir\n", encoding="utf-8")

    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 1
    assert "E2120" in res.stdout or "E2120" in res.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_standalone_binary_no_ancestor_leak():
    scratch_bin = ROOT / "scratch" / "isolated_bin"
    shutil.rmtree(scratch_bin, ignore_errors=True)
    scratch_bin.mkdir(parents=True, exist_ok=True)
    foreign_virc = scratch_bin / "virc"
    shutil.copy2(VIRC, foreign_virc)
    sign_if_darwin(foreign_virc)

    # 1. Foreign virc --print-sysroot must fail E2120
    p1 = run_cmd([str(foreign_virc), "--print-sysroot"])
    assert p1.returncode == 1
    assert "E2120" in p1.stdout or "E2120" in p1.stderr

    # 2. Compiling a source file in repo without --sysroot must fail E2120 (no ancestor fallback leak)
    target_src = ROOT / "tests" / "strict_v2" / "decl_group_positive_e2e.vri"
    dummy_out = scratch_bin / "dummy.out"
    p2 = run_cmd([str(foreign_virc), str(target_src), "-o", str(dummy_out)])
    assert p2.returncode == 1
    assert "E2120" in p2.stdout or "E2120" in p2.stderr

    # 3. Supplying explicit --sysroot restores compilation
    p3 = run_cmd([str(foreign_virc), "--sysroot", str(ROOT), str(target_src), "-o", str(dummy_out)])
    assert p3.returncode == 0
    assert dummy_out.exists()

    shutil.rmtree(scratch_bin, ignore_errors=True)


def test_side_by_side_toolchains():
    scratch_tc = ROOT / "scratch" / "alt_toolchain"
    shutil.rmtree(scratch_tc, ignore_errors=True)
    (scratch_tc / "stdlib").mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "stdlib" / "vir", scratch_tc / "stdlib" / "vir")
    shutil.copy2(ROOT / "stdlib" / "stdlib.vri", scratch_tc / "stdlib" / "stdlib.vri")

    # Both sysroots are valid and resolve independently
    res1 = run_cmd([str(VIRC), "--sysroot", str(ROOT), "--print-sysroot"])
    assert res1.returncode == 0
    assert res1.stdout.strip() == str(ROOT)

    res2 = run_cmd([str(VIRC), "--sysroot", str(scratch_tc), "--print-sysroot"])
    assert res2.returncode == 0
    assert res2.stdout.strip() == str(scratch_tc)

    shutil.rmtree(scratch_tc, ignore_errors=True)


def test_precedence_cli_over_env():
    # CLI valid overrides invalid ENV
    res = run_cmd(
        [str(VIRC), "--sysroot", str(ROOT), "--print-sysroot"],
        env={"VIR_SYSROOT": "/invalid/env/sysroot"},
    )
    assert res.returncode == 0
    assert res.stdout.strip() == str(ROOT)

    # CLI invalid fails even if ENV is valid
    res_fail = run_cmd(
        [str(VIRC), "--sysroot", "/invalid/cli/sysroot", "--print-sysroot"],
        env={"VIR_SYSROOT": str(ROOT)},
    )
    assert res_fail.returncode == 1
    assert "invalid --sysroot" in res_fail.stdout or "invalid --sysroot" in res_fail.stderr


def test_foreign_cwd_compilation():
    scratch_dir = ROOT / "scratch" / "sysroot_contract_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    src_file = scratch_dir / "app.vri"
    out_file = scratch_dir / "app.out"

    src_file.write_text(
        "include math\n\nfunc main:\n    out abs(0 - 77)\nend.\n",
        encoding="utf-8",
    )

    # Compile from inside scratch_dir (foreign CWD with no stdlib in tree)
    res = run_cmd(
        [str(VIRC), str(src_file), "-o", str(out_file), "-q", "--color=never"],
        cwd=str(scratch_dir),
    )
    assert res.returncode == 0, f"Compilation failed: {res.stdout}\n{res.stderr}"
    assert out_file.exists()

    sign_if_darwin(out_file)
    run_res = subprocess.run([str(out_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert run_res.returncode == 77

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_symlink_invocation():
    scratch_dir = ROOT / "scratch" / "symlink_test_dir"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    symlink_virc = scratch_dir / "virc_symlink"
    symlink_virc.symlink_to(VIRC)

    res = run_cmd([str(symlink_virc), "--print-sysroot", "--color=never"], cwd=str(scratch_dir))
    assert res.returncode == 0, f"Failed symlink invocation: {res.stderr}"
    assert res.stdout.strip() == str(ROOT)

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_help_documents_sysroot():
    res = run_cmd([str(VIRC), "--help"])
    assert res.returncode == 0
    assert "--sysroot" in res.stdout
    assert "--print-sysroot" in res.stdout
    assert "--print-stdlib" in res.stdout


def test_fake_empty_preludes_fail_closed():
    scratch_dir = ROOT / "scratch" / "fake_empty_preludes_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    # Empty 0-byte fake files must fail validation
    (scratch_dir / "stdlib" / "vir" / "core" / "types.vri").write_text("", encoding="utf-8")
    (scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri").write_text("", encoding="utf-8")

    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 1
    assert "E2120" in res.stdout or "E2120" in res.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_version_mismatch_fail_closed():
    scratch_dir = ROOT / "scratch" / "version_mismatch_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "stdlib" / "vir" / "core" / "types.vri", scratch_dir / "stdlib" / "vir" / "core" / "types.vri")
    shutil.copy2(ROOT / "stdlib" / "vir" / "rt" / "alloc.vri", scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri")

    # 1. abi_version mismatch (abi_version = 99)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 99\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    res_abi = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res_abi.returncode == 1
    assert "E2120" in res_abi.stdout or "E2120" in res_abi.stderr

    # 2. compiler_min mismatch (compiler_min = 99.0.0)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 99.0.0\n",
        encoding="utf-8",
    )
    res_min = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res_min.returncode == 1
    assert "E2120" in res_min.stdout or "E2120" in res_min.stderr

    # 3. major version mismatch (version = 3.0.0)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 3.0.0\nabi_version = 2\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    res_ver = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res_ver.returncode == 1
    assert "E2120" in res_ver.stdout or "E2120" in res_ver.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_path_invocation():
    # When virc is invoked through PATH without path separators
    env = os.environ.copy()
    env["PATH"] = f"{ROOT / 'bin'}:{env.get('PATH', '')}"
    res = run_cmd(["virc", "--print-sysroot"], env=env)
    assert res.returncode == 0, f"PATH invocation failed: {res.stderr}"
    assert res.stdout.strip() == str(ROOT)


def test_sysroot_containment_escape_fail_closed():
    scratch_dir = ROOT / "scratch" / "containment_escape_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    # Attempt to escape sysroot stdlib directory via ".." directory traversal
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        f"root = ../../../../{ROOT.relative_to(ROOT.anchor)}/stdlib/vir\n"
        "schema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 1
    assert "E2120" in res.stdout or "E2120" in res.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_compatibility_missing_compiler_min_fail_closed():
    scratch_dir = ROOT / "scratch" / "missing_comp_min_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "stdlib" / "vir" / "core" / "types.vri", scratch_dir / "stdlib" / "vir" / "core" / "types.vri")
    shutil.copy2(ROOT / "stdlib" / "vir" / "rt" / "alloc.vri", scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri")

    # compiler_min is completely missing
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 2\n",
        encoding="utf-8",
    )
    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 1
    assert "E2120" in res.stdout or "E2120" in res.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_compatibility_malformed_semver_fail_closed():
    scratch_dir = ROOT / "scratch" / "malformed_semver_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "stdlib" / "vir" / "core" / "types.vri", scratch_dir / "stdlib" / "vir" / "core" / "types.vri")
    shutil.copy2(ROOT / "stdlib" / "vir" / "rt" / "alloc.vri", scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri")

    # version has trailing invalid non-semver characters
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2not-semver\nabi_version = 2\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 1
    assert "E2120" in res.stdout or "E2120" in res.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_compatibility_higher_compiler_min_fail_closed():
    scratch_dir = ROOT / "scratch" / "higher_comp_min_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "stdlib" / "vir" / "core" / "types.vri", scratch_dir / "stdlib" / "vir" / "core" / "types.vri")
    shutil.copy2(ROOT / "stdlib" / "vir" / "rt" / "alloc.vri", scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri")

    # compiler_min patch is higher than actual compiler (e.g. 4.2.999 > 4.2.1)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.999\n",
        encoding="utf-8",
    )
    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 1
    assert "E2120" in res.stdout or "E2120" in res.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_prelude_comment_padding_fail_closed():
    scratch_dir = ROOT / "scratch" / "prelude_padding_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    # File size >= 50 bytes, but contains only comments padding and no structural type declarations
    padding = "# " + ("comment_padding_token " * 10) + "\n"
    (scratch_dir / "stdlib" / "vir" / "core" / "types.vri").write_text(padding, encoding="utf-8")
    (scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri").write_text(padding, encoding="utf-8")

    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 1
    assert "E2120" in res.stdout or "E2120" in res.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_compatibility_abi_prefix_leak_fail_closed():
    scratch_dir = ROOT / "scratch" / "abi_prefix_leak_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "stdlib" / "vir" / "core" / "types.vri", scratch_dir / "stdlib" / "vir" / "core" / "types.vri")
    shutil.copy2(ROOT / "stdlib" / "vir" / "rt" / "alloc.vri", scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri")

    # Incomplete ABI key match: "abi_vxxxxxx = 2" has length 11 and starts with "abi_v", but is invalid
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_vxxxxxx = 2\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 1
    assert "E2120" in res.stdout or "E2120" in res.stderr

    # Also test truncated "abi_v = 2"
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_v = 2\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    res2 = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res2.returncode == 1
    assert "E2120" in res2.stdout or "E2120" in res2.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_prelude_magic_strings_in_comments_fail_closed():
    scratch_dir = ROOT / "scratch" / "prelude_magic_comments_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    # Magic declaration strings placed ONLY inside comments (both line comments and block doc comments)
    types_stub = (
        "# type i64\n"
        "# type bool\n"
        "##\n"
        "type i64\n"
        "type bool\n"
        "##\n"
    )
    alloc_stub = (
        "# module vir.rt.alloc\n"
        "# func vir_alloc\n"
        "##\n"
        "vir.rt.alloc\n"
        "vir_alloc\n"
        "##\n"
    )
    (scratch_dir / "stdlib" / "vir" / "core" / "types.vri").write_text(types_stub, encoding="utf-8")
    (scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri").write_text(alloc_stub, encoding="utf-8")

    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 1
    assert "E2120" in res.stdout or "E2120" in res.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_prelude_canonical_block_comment_fail_closed():
    scratch_dir = ROOT / "scratch" / "prelude_canonical_block_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    # Magic declaration strings placed solely inside canonical Vir block comments #*# ... #*#
    types_stub = (
        "#*#\n"
        "type i64\n"
        "type bool\n"
        "#*#\n"
    )
    alloc_stub = (
        "#*#\n"
        "vir.rt.alloc\n"
        "vir_alloc\n"
        "#*#\n"
    )
    (scratch_dir / "stdlib" / "vir" / "core" / "types.vri").write_text(types_stub, encoding="utf-8")
    (scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri").write_text(alloc_stub, encoding="utf-8")

    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 1
    assert "E2120" in res.stdout or "E2120" in res.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_prelude_string_literal_only_fail_closed():
    scratch_dir = ROOT / "scratch" / "prelude_string_lit_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    # Magic declaration strings placed solely inside string literals, not real code statements
    types_stub = 'let dummy = "type i64 type bool"\n'
    alloc_stub = 'let dummy = "vir.rt.alloc vir_alloc"\n'
    (scratch_dir / "stdlib" / "vir" / "core" / "types.vri").write_text(types_stub, encoding="utf-8")
    (scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri").write_text(alloc_stub, encoding="utf-8")

    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 1
    assert "E2120" in res.stdout or "E2120" in res.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_registry_duplicate_metadata_fail_closed():
    scratch_dir = ROOT / "scratch" / "reg_duplicate_metadata_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "stdlib" / "vir" / "core" / "types.vri", scratch_dir / "stdlib" / "vir" / "core" / "types.vri")
    shutil.copy2(ROOT / "stdlib" / "vir" / "rt" / "alloc.vri", scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri")

    base = "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.0\n"
    for dup in ["schema = 1\n", "version = 2.0.0\n", "abi_version = 2\n", "compiler_min = 4.2.0\n", "root = vir\n"]:
        (scratch_dir / "stdlib" / "stdlib.vri").write_text(base + dup, encoding="utf-8")
        res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
        assert res.returncode == 1, f"Failed for duplicate directive: {dup}"
        assert "E2120" in res.stdout or "E2120" in res.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_semver_overflow_fail_closed():
    scratch_dir = ROOT / "scratch" / "semver_overflow_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "stdlib" / "vir" / "core" / "types.vri", scratch_dir / "stdlib" / "vir" / "core" / "types.vri")
    shutil.copy2(ROOT / "stdlib" / "vir" / "rt" / "alloc.vri", scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri")

    # 1. version component overflows 2^64 (e.g. 18446744073709551618 wraps to 2)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 18446744073709551618.0.0\nabi_version = 2\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 1
    assert "E2120" in res.stdout or "E2120" in res.stderr

    # 2. compiler_min component overflows 2^64 (e.g. 18446744073709551616 wraps to 0)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 18446744073709551616.0.0\n",
        encoding="utf-8",
    )
    res2 = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res2.returncode == 1
    assert "E2120" in res2.stdout or "E2120" in res2.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_prelude_decoy_aliases_fail_closed():
    scratch_dir = ROOT / "scratch" / "prelude_decoy_aliases_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)

    # 1. Decoy type aliases: type i64_alias, type bool_alias
    (scratch_dir / "stdlib" / "vir" / "core" / "types.vri").write_text(
        "type i64_alias;\ntype bool_alias;\n", encoding="utf-8"
    )
    shutil.copy2(ROOT / "stdlib" / "vir" / "rt" / "alloc.vri", scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri")
    res1 = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res1.returncode == 1
    assert "E2120" in res1.stdout or "E2120" in res1.stderr

    # 2. Decoy allocator: include vir.rt.alloc.fake and fake_vir_alloc
    shutil.copy2(ROOT / "stdlib" / "vir" / "core" / "types.vri", scratch_dir / "stdlib" / "vir" / "core" / "types.vri")
    (scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri").write_text(
        "include vir.rt.alloc.fake\nfunc fake_vir_alloc(sz: int) -> int: out 0 end.\n", encoding="utf-8"
    )
    res2 = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res2.returncode == 1
    assert "E2120" in res2.stdout or "E2120" in res2.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_prelude_whitespace_and_comments_preserved():
    scratch_dir = ROOT / "scratch" / "prelude_ws_comments_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "stdlib" / "vir" / "rt" / "alloc.vri", scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri")

    # Legal extra whitespace and inline comments between 'type' and identifier
    types_content = (
        "type    i64;\n"
        "type # inline comment\n"
        "  bool;\n"
    )
    (scratch_dir / "stdlib" / "vir" / "core" / "types.vri").write_text(types_content, encoding="utf-8")
    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 0
    assert str(scratch_dir) in res.stdout

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_registry_malformed_and_empty_directives_fail_closed():
    scratch_dir = ROOT / "scratch" / "reg_malformed_lines_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "stdlib" / "vir" / "core" / "types.vri", scratch_dir / "stdlib" / "vir" / "core" / "types.vri")
    shutil.copy2(ROOT / "stdlib" / "vir" / "rt" / "alloc.vri", scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri")

    base = "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.0\n"
    malformed_cases = [
        "schema =",
        "root =",
        "compiler_min =",
        "garbage",
        "schema",
        "= value",
    ]
    for case in malformed_cases:
        (scratch_dir / "stdlib" / "stdlib.vri").write_text(base + case + "\n", encoding="utf-8")
        res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
        assert res.returncode == 1, f"Expected fail-closed for malformed line: {case}"
        assert "E2120" in res.stdout or "E2120" in res.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_distinct_toolchain_versions():
    # Two distinct installed toolchains with independent binaries resolve to their own sysroot
    tc_a = ROOT / "scratch" / "tc_inst_a"
    tc_b = ROOT / "scratch" / "tc_inst_b"
    shutil.rmtree(tc_a, ignore_errors=True)
    shutil.rmtree(tc_b, ignore_errors=True)

    for tc, ver in ((tc_a, "2.0.0"), (tc_b, "2.1.0")):
        (tc / "bin").mkdir(parents=True, exist_ok=True)
        (tc / "stdlib").mkdir(parents=True, exist_ok=True)
        shutil.copy2(VIRC, tc / "bin" / "virc")
        sign_if_darwin(tc / "bin" / "virc")
        shutil.copytree(ROOT / "stdlib" / "vir", tc / "stdlib" / "vir")
        (tc / "stdlib" / "stdlib.vri").write_text(
            f"root = vir\nschema = 1\nversion = {ver}\nabi_version = 2\ncompiler_min = 4.2.0\n",
            encoding="utf-8",
        )

    # 1. Executable-derived sysroot resolution for each distinct installed toolchain
    res_a = run_cmd([str(tc_a / "bin" / "virc"), "--print-sysroot"])
    assert res_a.returncode == 0
    assert res_a.stdout.strip() == str(tc_a)

    res_b = run_cmd([str(tc_b / "bin" / "virc"), "--print-sysroot"])
    assert res_b.returncode == 0
    assert res_b.stdout.strip() == str(tc_b)

    # 2. Independent compilation using each distinct toolchain
    app_src = ROOT / "scratch" / "distinct_tc_app.vri"
    app_src.write_text("func main:\n    out 77\nend.\n", encoding="utf-8")

    out_a = tc_a / "app_a.out"
    p_a = run_cmd([str(tc_a / "bin" / "virc"), str(app_src), "-o", str(out_a), "-q"])
    assert p_a.returncode == 0
    sign_if_darwin(out_a)
    assert subprocess.run([str(out_a)], stdout=subprocess.PIPE).returncode == 77

    out_b = tc_b / "app_b.out"
    p_b = run_cmd([str(tc_b / "bin" / "virc"), str(app_src), "-o", str(out_b), "-q"])
    assert p_b.returncode == 0
    sign_if_darwin(out_b)
    assert subprocess.run([str(out_b)], stdout=subprocess.PIPE).returncode == 77

    app_src.unlink(missing_ok=True)
    shutil.rmtree(tc_a, ignore_errors=True)
    shutil.rmtree(tc_b, ignore_errors=True)


def test_vir_lsp_parity():
    # 1. Help documents --sysroot and --stdlib-registry
    res_help = run_cmd([str(VIR_LSP), "--help"])
    assert res_help.returncode == 0
    assert "--sysroot PATH" in res_help.stdout
    assert "--stdlib-registry PATH" in res_help.stdout

    # 2. Invalid --sysroot fails closed with code 1 and E2120
    res_inv = run_cmd([str(VIR_LSP), "--sysroot", "/nonexistent/sysroot"])
    assert res_inv.returncode == 1
    assert "E2120" in res_inv.stdout or "E2120" in res_inv.stderr

    # 3. Invalid VIR_SYSROOT fails closed with code 1 and E2120
    res_inv_env = run_cmd([str(VIR_LSP), "--stdio"], env={"VIR_SYSROOT": "/invalid/lsp/sysroot"})
    assert res_inv_env.returncode == 1
    assert "E2120" in res_inv_env.stdout or "E2120" in res_inv_env.stderr

    # 4. Invalid explicit --stdlib-registry fails closed with code 1 and E2120
    scratch_bad = ROOT / "scratch" / "bad_reg_lsp.vri"
    scratch_bad.parent.mkdir(parents=True, exist_ok=True)
    scratch_bad.write_text("not a registry\n", encoding="utf-8")
    res_bad_reg = run_cmd([str(VIR_LSP), "--stdlib-registry", str(scratch_bad), "--stdio"])
    assert res_bad_reg.returncode == 1
    assert "E2120" in res_bad_reg.stdout or "E2120" in res_bad_reg.stderr
    scratch_bad.unlink(missing_ok=True)

    # 5. Standalone vir-lsp binary copied outside toolchain without sysroot fails closed with code 1 and E2120
    scratch_lsp = ROOT / "scratch" / "isolated_lsp"
    shutil.rmtree(scratch_lsp, ignore_errors=True)
    scratch_lsp.mkdir(parents=True, exist_ok=True)
    foreign_lsp = scratch_lsp / "vir-lsp"
    shutil.copy2(VIR_LSP, foreign_lsp)
    sign_if_darwin(foreign_lsp)
    res_foreign = run_cmd([str(foreign_lsp), "--stdio"])
    assert res_foreign.returncode == 1
    assert "E2120" in res_foreign.stdout or "E2120" in res_foreign.stderr
    shutil.rmtree(scratch_lsp, ignore_errors=True)

    # 6. Valid --sysroot accepted and completes full LSP initialize/shutdown handshake
    proc = subprocess.Popen(
        [str(VIR_LSP), "--sysroot", str(ROOT), "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    def send(payload):
        body = json.dumps(payload).encode("utf-8")
        hdr = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        proc.stdin.write(hdr + body)
        proc.stdin.flush()

    def read_msg():
        header = b""
        while b"\r\n\r\n" not in header:
            ch = proc.stdout.read(1)
            if not ch:
                raise EOFError("vir-lsp closed stdout")
            header += ch
        clen = int(header.split(b"\r\n")[0].split(b":")[1].strip())
        return json.loads(proc.stdout.read(clen).decode("utf-8"))

    send({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"processId": os.getpid(), "rootUri": f"file://{ROOT}", "capabilities": {}},
    })
    init_resp = read_msg()
    assert init_resp.get("result", {}).get("serverInfo", {}).get("name") == "vir-lsp"

    send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
    send({"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}})
    shut_resp = read_msg()
    assert shut_resp.get("id") == 2
    assert shut_resp.get("result") is None

    send({"jsonrpc": "2.0", "method": "exit"})
    proc.wait(timeout=5)
def test_module_mapping_escape_fail_closed():
    scratch_dir = ROOT / "scratch" / "mod_map_escape_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "stdlib" / "vir" / "core" / "types.vri", scratch_dir / "stdlib" / "vir" / "core" / "types.vri")
    shutil.copy2(ROOT / "stdlib" / "vir" / "rt" / "alloc.vri", scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri")

    outside_file = ROOT / "scratch" / "outside_target.vri"
    outside_file.write_text("func outside_fn -> int: out 73 end.\n", encoding="utf-8")

    reg_content = (
        "root = vir\n"
        "schema = 1\n"
        "version = 2.0.0\n"
        "abi_version = 2\n"
        "compiler_min = 4.2.0\n"
        "types = core/types.vri\n"
        "alloc = rt/alloc.vri\n"
        "escape = ../../../scratch/outside_target.vri\n"
    )
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(reg_content, encoding="utf-8")

    res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res.returncode == 1, "Expected --print-sysroot to reject escaping module mapping"
    assert "E2120" in res.stdout or "E2120" in res.stderr

    app_src = ROOT / "scratch" / "import_escape_app.vri"
    app_src.write_text("import outside_fn from escape\nfunc main: out outside_fn() end.\n", encoding="utf-8")
    app_out = ROOT / "scratch" / "import_escape_app.out"
    p = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), str(app_src), "-o", str(app_out), "-q"])
    assert p.returncode == 1, "Expected compilation to fail closed when module mapping escapes root"

    outside_file.unlink(missing_ok=True)
    app_src.unlink(missing_ok=True)
    app_out.unlink(missing_ok=True)
    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_identifier_boundary_utf8_and_delimiters_fail_closed():
    scratch_dir = ROOT / "scratch" / "ident_boundary_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        "root = vir\nschema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.0\n",
        encoding="utf-8",
    )
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)

    # 1. UTF-8 continuation byte decoy: type i64é, type boolé
    (scratch_dir / "stdlib" / "vir" / "core" / "types.vri").write_text("type i64é;\ntype boolé;\n", encoding="utf-8")
    shutil.copy2(ROOT / "stdlib" / "vir" / "rt" / "alloc.vri", scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri")
    res1 = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res1.returncode == 1, "Expected fail-closed for type i64é UTF-8 decoy"
    assert "E2120" in res1.stdout or "E2120" in res1.stderr

    # 2. UTF-8 continuation byte decoy for allocator: vir.rt.allocé, func vir_allocé
    shutil.copy2(ROOT / "stdlib" / "vir" / "core" / "types.vri", scratch_dir / "stdlib" / "vir" / "core" / "types.vri")
    (scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri").write_text(
        "module vir.rt.allocé\nfunc vir_allocé(sz: int) -> int: out 0 end.\n", encoding="utf-8"
    )
    res2 = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res2.returncode == 1, "Expected fail-closed for vir_allocé UTF-8 decoy"
    assert "E2120" in res2.stdout or "E2120" in res2.stderr

    # 3. Dot delimiter decoy: type i64.fake, func vir_alloc.fake
    (scratch_dir / "stdlib" / "vir" / "core" / "types.vri").write_text("type i64.fake;\ntype bool.fake;\n", encoding="utf-8")
    res3 = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res3.returncode == 1, "Expected fail-closed for dot-delimited type decoy"
    assert "E2120" in res3.stdout or "E2120" in res3.stderr

    (scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri").write_text(
        "func vir_alloc.fake(sz: int) -> int: out 0 end.\n", encoding="utf-8"
    )
    res4 = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res4.returncode == 1, "Expected fail-closed for dot-delimited func decoy"
    assert "E2120" in res4.stdout or "E2120" in res4.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


def test_registry_trailing_tokens_and_module_validity_fail_closed():
    scratch_dir = ROOT / "scratch" / "trailing_tokens_test"
    shutil.rmtree(scratch_dir, ignore_errors=True)
    (scratch_dir / "stdlib").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "core").mkdir(parents=True, exist_ok=True)
    (scratch_dir / "stdlib" / "vir" / "rt").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "stdlib" / "vir" / "core" / "types.vri", scratch_dir / "stdlib" / "vir" / "core" / "types.vri")
    shutil.copy2(ROOT / "stdlib" / "vir" / "rt" / "alloc.vri", scratch_dir / "stdlib" / "vir" / "rt" / "alloc.vri")

    # 1. Trailing junk on metadata lines
    trailing_cases = [
        "schema = 1 trailing\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.0\nroot = vir\n",
        "schema = 1\nversion = 2.0.0 trailing\nabi_version = 2\ncompiler_min = 4.2.0\nroot = vir\n",
        "schema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.0\nroot = vir trailing\n",
    ]
    for case in trailing_cases:
        (scratch_dir / "stdlib" / "stdlib.vri").write_text(case, encoding="utf-8")
        res = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
        assert res.returncode == 1, f"Expected fail-closed for trailing token: {case}"
        assert "E2120" in res.stdout or "E2120" in res.stderr

    # 2. Missing module target
    base = "schema = 1\nversion = 2.0.0\nabi_version = 2\ncompiler_min = 4.2.0\nroot = vir\n"
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(base + "ghost = does/not/exist.vri\n", encoding="utf-8")
    res_ghost = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res_ghost.returncode == 1, "Expected fail-closed for missing module target"
    assert "E2120" in res_ghost.stdout or "E2120" in res_ghost.stderr

    # 3. Duplicate module key
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(
        base + "dup = core/types.vri\ndup = core/types.vri\n", encoding="utf-8"
    )
    res_dup = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res_dup.returncode == 1, "Expected fail-closed for duplicate module key"
    assert "E2120" in res_dup.stdout or "E2120" in res_dup.stderr

    # 4. Invalid module ID
    (scratch_dir / "stdlib" / "stdlib.vri").write_text(base + "bad..id = core/types.vri\n", encoding="utf-8")
    res_bad = run_cmd([str(VIRC), "--sysroot", str(scratch_dir), "--print-sysroot"])
    assert res_bad.returncode == 1, "Expected fail-closed for invalid module ID"
    assert "E2120" in res_bad.stdout or "E2120" in res_bad.stderr

    shutil.rmtree(scratch_dir, ignore_errors=True)


if __name__ == "__main__":
    test_print_sysroot_text()
    print("PASS: test_print_sysroot_text")
    test_print_stdlib_text()
    print("PASS: test_print_stdlib_text")
    test_print_sysroot_json()
    print("PASS: test_print_sysroot_json")
    test_print_stdlib_json()
    print("PASS: test_print_stdlib_json")
    test_sysroot_override_valid()
    print("PASS: test_sysroot_override_valid")
    test_sysroot_override_invalid_fail_closed()
    print("PASS: test_sysroot_override_invalid_fail_closed")
    test_sysroot_canonicalization_cli()
    print("PASS: test_sysroot_canonicalization_cli")
    test_sysroot_canonicalization_env()
    print("PASS: test_sysroot_canonicalization_env")
    test_vir_sysroot_env_valid()
    print("PASS: test_vir_sysroot_env_valid")
    test_vir_sysroot_env_invalid_fail_closed()
    print("PASS: test_vir_sysroot_env_invalid_fail_closed")
    test_malformed_registry_fail_closed()
    print("PASS: test_malformed_registry_fail_closed")
    test_missing_prelude_fail_closed()
    print("PASS: test_missing_prelude_fail_closed")
    test_fake_empty_preludes_fail_closed()
    print("PASS: test_fake_empty_preludes_fail_closed")
    test_version_mismatch_fail_closed()
    print("PASS: test_version_mismatch_fail_closed")
    test_standalone_binary_no_ancestor_leak()
    print("PASS: test_standalone_binary_no_ancestor_leak")
    test_side_by_side_toolchains()
    print("PASS: test_side_by_side_toolchains")
    test_distinct_toolchain_versions()
    print("PASS: test_distinct_toolchain_versions")
    test_path_invocation()
    print("PASS: test_path_invocation")
    test_precedence_cli_over_env()
    print("PASS: test_precedence_cli_over_env")
    test_foreign_cwd_compilation()
    print("PASS: test_foreign_cwd_compilation")
    test_symlink_invocation()
    print("PASS: test_symlink_invocation")
    test_help_documents_sysroot()
    print("PASS: test_help_documents_sysroot")
    test_vir_lsp_parity()
    print("PASS: test_vir_lsp_parity")
    test_sysroot_containment_escape_fail_closed()
    print("PASS: test_sysroot_containment_escape_fail_closed")
    test_compatibility_missing_compiler_min_fail_closed()
    print("PASS: test_compatibility_missing_compiler_min_fail_closed")
    test_compatibility_malformed_semver_fail_closed()
    print("PASS: test_compatibility_malformed_semver_fail_closed")
    test_compatibility_higher_compiler_min_fail_closed()
    print("PASS: test_compatibility_higher_compiler_min_fail_closed")
    test_prelude_comment_padding_fail_closed()
    print("PASS: test_prelude_comment_padding_fail_closed")
    test_compatibility_abi_prefix_leak_fail_closed()
    print("PASS: test_compatibility_abi_prefix_leak_fail_closed")
    test_prelude_magic_strings_in_comments_fail_closed()
    print("PASS: test_prelude_magic_strings_in_comments_fail_closed")
    test_prelude_canonical_block_comment_fail_closed()
    print("PASS: test_prelude_canonical_block_comment_fail_closed")
    test_prelude_string_literal_only_fail_closed()
    print("PASS: test_prelude_string_literal_only_fail_closed")
    test_registry_duplicate_metadata_fail_closed()
    print("PASS: test_registry_duplicate_metadata_fail_closed")
    test_semver_overflow_fail_closed()
    print("PASS: test_semver_overflow_fail_closed")
    test_prelude_decoy_aliases_fail_closed()
    print("PASS: test_prelude_decoy_aliases_fail_closed")
    test_prelude_whitespace_and_comments_preserved()
    print("PASS: test_prelude_whitespace_and_comments_preserved")
    test_registry_malformed_and_empty_directives_fail_closed()
    print("PASS: test_registry_malformed_and_empty_directives_fail_closed")
    test_module_mapping_escape_fail_closed()
    print("PASS: test_module_mapping_escape_fail_closed")
    test_identifier_boundary_utf8_and_delimiters_fail_closed()
    print("PASS: test_identifier_boundary_utf8_and_delimiters_fail_closed")
    test_registry_trailing_tokens_and_module_validity_fail_closed()
    print("PASS: test_registry_trailing_tokens_and_module_validity_fail_closed")
    print("\nALL 40 SYSROOT CONTRACT TESTS PASSED!")

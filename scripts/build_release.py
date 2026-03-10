#!/usr/bin/env python3
"""
scripts/build_release.py — Cross-Platform Binary Packaging
============================================================
Orchestrates the full build pipeline:
  1. Build libvir_core (shared + static) via Make
  2. Compile stdlib (.vri → .sri → .vsib)
  3. Bundle native libs into src/native/lib/
  4. Build platform-specific Python wheel

Usage:
    python scripts/build_release.py                # full build
    python scripts/build_release.py --native-only  # just native library
    python scripts/build_release.py --wheel-only   # just wheel (assumes native already built)
    python scripts/build_release.py --arch arm64   # force architecture
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

VIR_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = VIR_ROOT / "core"
LIB_DIR = CORE_DIR / "lib"
NATIVE_LIB_DEST = VIR_ROOT / "src" / "native" / "lib"
DIST_DIR = VIR_ROOT / "dist"


def detect_platform() -> tuple[str, str]:
    """Return (os_name, arch) for current machine."""
    system = platform.system()
    machine = platform.machine().lower()

    if system == "Darwin":
        os_name = "macos"
    elif system == "Linux":
        os_name = "linux"
    elif system == "Windows":
        os_name = "windows"
    else:
        os_name = system.lower()

    if machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("arm64", "aarch64"):
        arch = "arm64"
    else:
        arch = machine

    return os_name, arch


def lib_filename(os_name: str) -> str:
    """Return the shared library filename for the platform."""
    if os_name == "macos":
        return "libvir_core.dylib"
    elif os_name == "windows":
        return "vir_core.dll"
    return "libvir_core.so"


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    """Run a command, raising on failure."""
    merged_env = {**os.environ, **(env or {})}
    print(f"  → {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, env=merged_env, check=True)


def build_native(arch: str | None = None) -> None:
    """Build libvir_core via make."""
    print("\n═══ Building native library (libvir_core) ═══")
    env = {}
    if arch:
        env["UNAME_M"] = "aarch64" if arch == "arm64" else arch
    run(["make", "clean"], cwd=CORE_DIR, env=env)
    run(["make", "all"], cwd=CORE_DIR, env=env)
    print(f"  ✓ Native library built in {LIB_DIR}/")


def inject_native_lib(os_name: str) -> None:
    """Copy the native library into the Python package tree."""
    print("\n═══ Injecting native lib into package ═══")
    NATIVE_LIB_DEST.mkdir(parents=True, exist_ok=True)

    fname = lib_filename(os_name)
    src = LIB_DIR / fname
    if not src.exists():
        print(f"  ✗ {src} not found — run build_native first")
        sys.exit(1)

    dst = NATIVE_LIB_DEST / fname
    shutil.copy2(src, dst)
    print(f"  ✓ Copied {src.name} → {dst}")

    # Also copy static lib
    static_src = LIB_DIR / "libvir_core.a"
    if static_src.exists():
        shutil.copy2(static_src, NATIVE_LIB_DEST / "libvir_core.a")
        print(f"  ✓ Copied libvir_core.a → {NATIVE_LIB_DEST}")


def build_stdlib(arch: str) -> None:
    """Compile the standard library for the given architecture."""
    print(f"\n═══ Building stdlib ({arch}) ═══")
    build_stdlib_script = VIR_ROOT / "scripts" / "build_stdlib.py"
    if not build_stdlib_script.exists():
        print("  ⚠ scripts/build_stdlib.py not found, skipping stdlib")
        return
    run([sys.executable, "-m", "scripts.build_stdlib", "--arch", arch], cwd=VIR_ROOT)
    print(f"  ✓ Stdlib compiled for {arch}")


def build_wheel() -> None:
    """Build a Python wheel using the build module."""
    print("\n═══ Building Python wheel ═══")
    run([sys.executable, "-m", "pip", "install", "build", "setuptools", "wheel", "-q"])
    run([sys.executable, "-m", "build", "--wheel", "--outdir", str(DIST_DIR)], cwd=VIR_ROOT)
    wheels = list(DIST_DIR.glob("*.whl"))
    if wheels:
        print(f"  ✓ Wheel: {wheels[-1].name}")
    else:
        print("  ✗ No wheel produced!")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Vir cross-platform release builder")
    parser.add_argument("--native-only", action="store_true", help="Only build native library")
    parser.add_argument("--wheel-only", action="store_true", help="Only build wheel (skip native)")
    parser.add_argument("--arch", type=str, help="Force architecture (arm64, x86_64)")
    parser.add_argument("--skip-stdlib", action="store_true", help="Skip stdlib compilation")
    args = parser.parse_args()

    os_name, detected_arch = detect_platform()
    arch = args.arch or detected_arch

    print(f"Platform: {os_name}/{arch}")
    print(f"Root:     {VIR_ROOT}")

    if not args.wheel_only:
        build_native(args.arch)
        inject_native_lib(os_name)
        if not args.skip_stdlib:
            build_stdlib(arch)

    if args.native_only:
        print("\n✓ Native build complete")
        return

    build_wheel()
    print(f"\n✓ Release build complete → {DIST_DIR}/")


if __name__ == "__main__":
    main()

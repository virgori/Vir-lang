#!/usr/bin/env python3
"""
packaging/build_packages.py — Master Packaging Orchestrator
=============================================================
Builds distribution packages for all supported targets:

  Linux x86_64:  .deb (Debian/Ubuntu) + .rpm (Fedora/RHEL) + Docker image
  Linux ARM64:   .deb (arm64) + .rpm (aarch64) + Docker image
  Windows x64:   .msi installer (via WiX)

Usage:
    python packaging/build_packages.py                     # all targets
    python packaging/build_packages.py --target linux-x86_64
    python packaging/build_packages.py --target linux-arm64
    python packaging/build_packages.py --target windows-x64
    python packaging/build_packages.py --target docker
    python packaging/build_packages.py --list              # show available targets
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
PACKAGING_DIR = VIR_ROOT / "packaging"
DIST_DIR = VIR_ROOT / "dist"
VERSION = "0.3.0"

TARGETS = {
    "linux-x86_64": {
        "name": "Linux x86_64",
        "formats": ["deb", "rpm"],
        "arch_deb": "amd64",
        "arch_rpm": "x86_64",
    },
    "linux-arm64": {
        "name": "Linux ARM64",
        "formats": ["deb", "rpm"],
        "arch_deb": "arm64",
        "arch_rpm": "aarch64",
    },
    "windows-x64": {
        "name": "Windows Server x64",
        "formats": ["msi"],
    },
    "docker": {
        "name": "Docker (multi-arch)",
        "formats": ["docker"],
    },
}


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> int:
    """Run a command and return exit code."""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if check and result.returncode != 0:
        print(f"  ✗ Command failed with exit code {result.returncode}")
        return result.returncode
    return result.returncode


def check_tool(name: str) -> bool:
    """Check if a command-line tool is available."""
    return shutil.which(name) is not None


def build_deb(arch: str) -> bool:
    """Build .deb package."""
    script = PACKAGING_DIR / "linux" / "build_deb.sh"
    if not check_tool("dpkg-deb"):
        print("  ⚠ dpkg-deb not found. Install: sudo apt install dpkg-dev")
        print("  ⚠ Skipping .deb build")
        return False
    return run(["bash", str(script), "--arch", arch, "--version", VERSION]) == 0


def build_rpm(arch: str) -> bool:
    """Build .rpm package."""
    script = PACKAGING_DIR / "linux" / "build_rpm.sh"
    if not check_tool("rpmbuild"):
        print("  ⚠ rpmbuild not found. Install: sudo apt install rpm")
        print("  ⚠ Skipping .rpm build")
        return False
    return run(["bash", str(script), "--arch", arch, "--version", VERSION]) == 0


def build_msi() -> bool:
    """Build Windows MSI installer."""
    script = PACKAGING_DIR / "windows" / "build_msi.ps1"
    if platform.system() != "Windows":
        print("  ⚠ MSI build requires Windows with WiX Toolset")
        print("  ⚠ Run on Windows: powershell -File packaging\\windows\\build_msi.ps1")
        return False
    return run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)]) == 0


def build_docker() -> bool:
    """Build multi-arch Docker image."""
    if not check_tool("docker"):
        print("  ⚠ docker not found")
        return False

    print("  Building Docker image (current arch)...")
    rc = run([
        "docker", "build",
        "-t", f"vir-lang:{VERSION}",
        "-t", "vir-lang:latest",
        "-f", str(VIR_ROOT / "Dockerfile"),
        str(VIR_ROOT),
    ])

    if rc == 0:
        print(f"  ✓ Docker image: vir-lang:{VERSION}")
        # Export as tarball
        tarball = DIST_DIR / f"vir-lang-{VERSION}-docker.tar.gz"
        run(["docker", "save", f"vir-lang:{VERSION}", "-o", str(tarball)], check=False)
        if tarball.exists():
            print(f"  ✓ Exported: {tarball}")

    return rc == 0


def build_docker_multiarch() -> bool:
    """Build multi-architecture Docker images using buildx."""
    if not check_tool("docker"):
        print("  ⚠ docker not found")
        return False

    print("  Building multi-arch Docker images (linux/amd64 + linux/arm64)...")
    rc = run([
        "docker", "buildx", "build",
        "--platform", "linux/amd64,linux/arm64",
        "-t", f"vir-lang:{VERSION}",
        "-t", "vir-lang:latest",
        "-f", str(VIR_ROOT / "Dockerfile"),
        str(VIR_ROOT),
    ])
    return rc == 0


def build_target(target: str) -> None:
    """Build all package formats for a given target."""
    info = TARGETS[target]
    print(f"\n{'═' * 60}")
    print(f"  Target: {info['name']}")
    print(f"{'═' * 60}")

    DIST_DIR.mkdir(parents=True, exist_ok=True)

    for fmt in info["formats"]:
        print(f"\n─── Format: {fmt} ───")
        if fmt == "deb":
            build_deb(info["arch_deb"])
        elif fmt == "rpm":
            build_rpm(info["arch_rpm"])
        elif fmt == "msi":
            build_msi()
        elif fmt == "docker":
            build_docker()


def main():
    parser = argparse.ArgumentParser(description="Vir — Master Packaging Orchestrator")
    parser.add_argument("--target", type=str, help="Target platform (linux-x86_64, linux-arm64, windows-x64, docker)")
    parser.add_argument("--list", action="store_true", help="List available targets")
    parser.add_argument("--version", type=str, default=VERSION, help="Package version")
    parser.add_argument("--docker-multiarch", action="store_true", help="Build multi-arch Docker images")
    args = parser.parse_args()

    global VERSION
    VERSION = args.version

    if args.list:
        print("Available packaging targets:")
        for key, info in TARGETS.items():
            fmts = ", ".join(info["formats"])
            print(f"  {key:20s} — {info['name']:25s} [{fmts}]")
        return

    if args.docker_multiarch:
        build_docker_multiarch()
        return

    if args.target:
        if args.target not in TARGETS:
            print(f"Unknown target: {args.target}")
            print(f"Available: {', '.join(TARGETS.keys())}")
            sys.exit(1)
        build_target(args.target)
    else:
        # Build all targets applicable to current platform
        current_os = platform.system()
        current_arch = platform.machine().lower()

        for target, info in TARGETS.items():
            if target == "docker":
                build_target(target)
            elif target.startswith("linux") and current_os == "Linux":
                build_target(target)
            elif target.startswith("windows") and current_os == "Windows":
                build_target(target)
            elif target.startswith("linux") and current_os == "Darwin":
                print(f"\n  ⚠ {info['name']}: use Docker to cross-build Linux packages on macOS")
                print(f"    docker run --rm -v $(pwd):/build debian:bookworm bash /build/packaging/linux/build_deb.sh")

    print(f"\n{'═' * 60}")
    print(f"  Packaging complete. Output: {DIST_DIR}/")
    if DIST_DIR.exists():
        for f in sorted(DIST_DIR.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"    {f.name:50s} ({size_mb:.1f} MB)")
    print(f"{'═' * 60}")


if __name__ == "__main__":
    main()

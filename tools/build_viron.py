#!/usr/bin/env python3
"""Build native viron executable on the Vir self-hosting compiler.

Computes source and compiler hashes, validates version synchronization,
compiles tools/viron/src/main.vri into bin/viron, and records build provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(ROOT / "bin/virc"), help="Path to virc compiler")
    parser.add_argument("--optimization", choices=["0", "1", "2", "3"], default="1", help="Optimization level")
    parser.add_argument(
        "--target",
        choices=[
            "macos-arm64",
            "macos-arm64-libsystem",
            "linux-arm64",
            "windows-arm64",
            "linux-x86_64",
            "windows-x86_64",
            "linux-riscv64",
            "wasm32-wasi-p1",
        ],
        help="Target architecture/platform",
    )
    parser.add_argument("--output", default=str(ROOT / "bin/viron"), help="Output binary path")
    options = parser.parse_args()

    # 1. Version gate check (pre-build: check source metadata)
    subprocess.run([sys.executable, "tools/bump_viron_version.py", "--check", "--skip-binary"], cwd=ROOT, check=True)

    compiler_path = Path(options.compiler).resolve()
    if not compiler_path.is_file():
        print(f"Error: compiler not found at {compiler_path}", file=sys.stderr)
        return 1

    compiler_hash = sha256(compiler_path)

    # 2. Canonical sources hash map
    viron_src_dir = ROOT / "tools/viron/src"
    canonical_sources: dict[str, str] = {}
    for src_file in sorted(viron_src_dir.rglob("*.vri")):
        rel = src_file.relative_to(ROOT).as_posix()
        canonical_sources[rel] = sha256(src_file)

    module_list_path = ROOT / "tools/viron/module.list"
    if module_list_path.is_file():
        canonical_sources[module_list_path.relative_to(ROOT).as_posix()] = sha256(module_list_path)

    vir_toml_path = ROOT / "tools/viron/vir.toml"
    if vir_toml_path.is_file():
        canonical_sources[vir_toml_path.relative_to(ROOT).as_posix()] = sha256(vir_toml_path)

    # 3. Invoke compiler
    main_vri = viron_src_dir / "main.vri"
    output_path = Path(options.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(compiler_path),
        "--ui=classic",
        "-q",
        f"-O{options.optimization}",
        str(main_vri),
        "-o",
        str(output_path),
    ]
    if options.target:
        cmd.extend(["--target", options.target])

    result = subprocess.run(cmd, cwd=ROOT)

    # Ad-hoc code signing on macOS
    if sys.platform == "darwin" and output_path.is_file():
        subprocess.run(["codesign", "-s", "-", "-f", str(output_path)], capture_output=True)

    if output_path.is_file():
        output_path.chmod(0o755)

    output_hash = sha256(output_path) if output_path.is_file() else None

    # 4. Record provenance manifest
    manifest = {
        "schemaVersion": 1,
        "tool": "viron",
        "compiler": str(compiler_path),
        "compilerSha256": compiler_hash,
        "target": options.target or "host",
        "optimizationLevel": int(options.optimization),
        "command": cmd,
        "workingDirectory": str(ROOT),
        "exitCode": result.returncode,
        "outputBinary": str(output_path),
        "outputBinarySha256": output_hash,
        "canonicalSources": canonical_sources,
    }

    manifest_path = output_path.parent / f"{output_path.name}.build.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if result.returncode != 0:
        print(f"viron build failed with exit code {result.returncode}", file=sys.stderr)
        return result.returncode

    print(f"Built viron executable: {output_path} (sha256: {output_hash})")
    # 5. Post-build version gate check (verify binary and build manifest)
    subprocess.run([sys.executable, "tools/bump_viron_version.py", "--check"], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

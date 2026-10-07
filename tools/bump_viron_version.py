#!/usr/bin/env python3
"""Manage the independent Semantic Version of the native viron tool."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
ISSUE_RE = re.compile(r"^VIRON-ISS-[0-9]{4}$")


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int

    @property
    def public(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def load_record(root: Path) -> dict[str, object]:
    path = root / "tools/viron/version.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    required = {
        "schema",
        "major",
        "minor",
        "patch",
        "public_version",
        "last_completed_issue",
    }
    if set(record) != required or record["schema"] != 1:
        raise ValueError("tools/viron/version.json does not match schema 1")
    return record


def version_from_record(record: dict[str, object]) -> Version:
    version = Version(
        int(record["major"]),
        int(record["minor"]),
        int(record["patch"]),
    )
    if version.major < 1 or version.minor < 0 or version.patch < 0:
        raise ValueError("invalid viron Semantic Version")
    return version


def expected_record(version: Version, issue: str) -> dict[str, object]:
    return {
        "schema": 1,
        "major": version.major,
        "minor": version.minor,
        "patch": version.patch,
        "public_version": version.public,
        "last_completed_issue": issue,
    }


def check(root: Path, check_binary: bool = True) -> None:
    record = load_record(root)
    version = version_from_record(record)
    issue = str(record["last_completed_issue"])
    if not ISSUE_RE.fullmatch(issue):
        raise ValueError("last_completed_issue must be a VIRON-ISS ID")
    if record != expected_record(version, issue):
        raise ValueError("derived fields in viron version metadata are inconsistent")

    main_vri = root / "tools/viron/src/main.vri"
    if main_vri.is_file():
        source = main_vri.read_text(encoding="utf-8")
        expected_literal = f"viron {version.public}"
        if expected_literal not in source:
            raise ValueError(f"tools/viron/src/main.vri is not synchronized with version {version.public}")

    vir_toml = root / "tools/viron/vir.toml"
    if vir_toml.is_file():
        toml_content = vir_toml.read_text(encoding="utf-8")
        expected_ver_str = f'version = "{version.public}"'
        if expected_ver_str not in toml_content:
            raise ValueError(f"tools/viron/vir.toml is not synchronized with version {version.public}")

    cli_vri = root / "tools/viron/src/cli/cli.vri"
    if cli_vri.is_file():
        cli_content = cli_vri.read_text(encoding="utf-8")
        expected_banner = f"V I R O N   v{version.public}"
        expected_cli_ver = f"viron {version.public}"
        if expected_banner not in cli_content or expected_cli_ver not in cli_content:
            raise ValueError(f"tools/viron/src/cli/cli.vri is not synchronized with version {version.public}")

    if check_binary:
        viron_bin = root / "bin/viron"
        if viron_bin.is_file():
            import subprocess
            res = subprocess.run([str(viron_bin), "--version"], capture_output=True, text=True)
            if res.returncode != 0 or f"viron {version.public}" not in res.stdout:
                raise ValueError(
                    f"bin/viron binary version does not match public version {version.public} (got: {res.stdout.strip()})"
                )

        build_json = root / "bin/viron.build.json"
        if build_json.is_file():
            try:
                bdata = json.loads(build_json.read_text(encoding="utf-8"))
                if bdata.get("schemaVersion") != 1 or bdata.get("tool") != "viron":
                    raise ValueError("bin/viron.build.json schemaVersion or tool mismatch")
                if viron_bin.is_file():
                    import hashlib
                    actual_bin_hash = hashlib.sha256(viron_bin.read_bytes()).hexdigest()
                    recorded_bin_hash = bdata.get("outputBinarySha256")
                    if recorded_bin_hash and recorded_bin_hash != actual_bin_hash:
                        raise ValueError(
                            f"bin/viron hash mismatch with build manifest (expected {recorded_bin_hash}, got {actual_bin_hash})"
                        )
                canonical_sources = bdata.get("canonicalSources", {})
                for rel_path, expected_hash in canonical_sources.items():
                    src_file = root / rel_path
                    if src_file.is_file():
                        import hashlib
                        actual_src_hash = hashlib.sha256(src_file.read_bytes()).hexdigest()
                        if actual_src_hash != expected_hash:
                            raise ValueError(
                                f"canonical source {rel_path} hash mismatch with build manifest"
                            )
            except Exception as e:
                raise ValueError(f"bin/viron.build.json verification failed: {e}")



def write_version(root: Path, version: Version, issue: str) -> None:
    if not ISSUE_RE.fullmatch(issue):
        raise ValueError("issue must be a VIRON-ISS ID")
    record_path = root / "tools/viron/version.json"
    main_path = root / "tools/viron/src/main.vri"
    toml_path = root / "tools/viron/vir.toml"
    cli_path = root / "tools/viron/src/cli/cli.vri"

    current = version_from_record(load_record(root)).public

    if main_path.is_file():
        source = main_path.read_text(encoding="utf-8")
        source = source.replace(f"viron {current}", f"viron {version.public}")
        source = source.replace(f"VIRON v{current}", f"VIRON v{version.public}")
        main_path.write_text(source, encoding="utf-8")

    if toml_path.is_file():
        toml_text = toml_path.read_text(encoding="utf-8")
        toml_text = toml_text.replace(f'version = "{current}"', f'version = "{version.public}"')
        toml_path.write_text(toml_text, encoding="utf-8")

    if cli_path.is_file():
        cli_text = cli_path.read_text(encoding="utf-8")
        cli_text = cli_text.replace(f"V I R O N   v{current}", f"V I R O N   v{version.public}")
        cli_text = cli_text.replace(f"viron {current}", f"viron {version.public}")
        cli_text = cli_text.replace(f"v{current}", f"v{version.public}")
        cli_path.write_text(cli_text, encoding="utf-8")

    record_path.write_text(
        json.dumps(expected_record(version, issue), indent=2) + "\n",
        encoding="utf-8",
    )
    check(root, check_binary=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--patch", metavar="ISSUE")
    mode.add_argument("--minor", metavar="ISSUE")
    mode.add_argument("--major", metavar="ISSUE")
    parser.add_argument("--skip-binary", action="store_true", help="Skip binary verification (for build bootstrap)")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.root.resolve()

    try:
        if args.check:
            check(root, check_binary=not args.skip_binary)
            print("viron version metadata is synchronized.")
            return 0

        record = load_record(root)
        current = version_from_record(record)
        issue = args.patch or args.minor or args.major
        if record["last_completed_issue"] == issue:
            check(root)
            print(f"{issue} already owns viron version {current.public}; no bump needed.")
            return 0
        if args.patch:
            next_version = Version(current.major, current.minor, current.patch + 1)
        elif args.minor:
            next_version = Version(current.major, current.minor + 1, 0)
        else:
            next_version = Version(current.major + 1, 0, 0)
        write_version(root, next_version, issue)
        print(f"viron version is now {next_version.public}.")
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Manage Vir compiler calendar versions from compiler/version.json."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
ISSUE_RE = re.compile(r"^(?:VIR|VIRC)-ISS-[0-9]{4}$")
OFFICIAL_RE = re.compile(r"^([0-9]{4})\.([1-9][0-9]*)$")


@dataclass(frozen=True)
class Version:
    year: int
    release: int
    internal_patch: int

    @property
    def public(self) -> str:
        base = f"{self.year}.{self.release}"
        if self.internal_patch == 0:
            return base
        return f"{base}.{self.internal_patch}"

    @property
    def channel(self) -> str:
        return "official" if self.internal_patch == 0 else "internal"


def load_record(root: Path) -> dict[str, object]:
    path = root / "compiler/version.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    required = {
        "schema",
        "year",
        "release",
        "internal_patch",
        "channel",
        "public_version",
        "last_completed_issue",
    }
    if set(record) != required or record["schema"] != 1:
        raise ValueError("compiler/version.json does not match schema 1")
    return record


def version_from_record(record: dict[str, object]) -> Version:
    version = Version(
        year=int(record["year"]),
        release=int(record["release"]),
        internal_patch=int(record["internal_patch"]),
    )
    if version.year < 2026 or version.release < 1 or version.internal_patch < 0:
        raise ValueError("invalid calendar compiler version")
    return version


def expected_record(version: Version, issue: str) -> dict[str, object]:
    return {
        "schema": 1,
        "year": version.year,
        "release": version.release,
        "internal_patch": version.internal_patch,
        "channel": version.channel,
        "public_version": version.public,
        "last_completed_issue": issue,
    }


def expected_config(version: Version) -> tuple[str, str, str, str]:
    return (
        f'out "{version.public}"',
        f"out {version.year}",
        f"out {version.release}",
        f"out {version.internal_patch}",
    )


def check(root: Path) -> None:
    record = load_record(root)
    version = version_from_record(record)
    issue = str(record["last_completed_issue"])
    if not ISSUE_RE.fullmatch(issue):
        raise ValueError("last_completed_issue must be a VIR-ISS or VIRC-ISS ID")
    if record != expected_record(version, issue):
        raise ValueError("derived fields in compiler/version.json are inconsistent")

    config = (root / "compiler/src/main/driver/config.vri").read_text(encoding="utf-8")
    function_names = (
        "vircVersionNumber",
        "vircVersionMajor",
        "vircVersionMinor",
        "vircVersionPatch",
    )
    for name, expected in zip(function_names, expected_config(version), strict=True):
        pattern = rf"func {name}[^:]*:\s*\n\s*{re.escape(expected)}\s*\nend\."
        if re.search(pattern, config) is None:
            raise ValueError(f"{name} is not synchronized with compiler/version.json")

    sync = subprocess.run(
        [sys.executable, "tools/sync_virc.py", "--check"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if sync.returncode != 0:
        raise ValueError(sync.stdout.strip() or sync.stderr.strip())


def replace_function_value(text: str, name: str, value: str) -> str:
    pattern = rf"(func {name}[^:]*:\s*\n\s*)out (?:\"[^\"]*\"|[0-9]+)(\s*\nend\.)"
    updated, count = re.subn(pattern, rf"\g<1>out {value}\g<2>", text, count=1)
    if count != 1:
        raise ValueError(f"cannot update {name}")
    return updated


def write_version(root: Path, version: Version, issue: str) -> None:
    if not ISSUE_RE.fullmatch(issue):
        raise ValueError("issue must be a VIR-ISS or VIRC-ISS ID")
    record_path = root / "compiler/version.json"
    config_path = root / "compiler/src/main/driver/config.vri"
    config = config_path.read_text(encoding="utf-8")
    config = replace_function_value(config, "vircVersionNumber", json.dumps(version.public))
    config = replace_function_value(config, "vircVersionMajor", str(version.year))
    config = replace_function_value(config, "vircVersionMinor", str(version.release))
    config = replace_function_value(config, "vircVersionPatch", str(version.internal_patch))

    record_path.write_text(
        json.dumps(expected_record(version, issue), indent=2) + "\n",
        encoding="utf-8",
    )
    config_path.write_text(config, encoding="utf-8")
    subprocess.run([sys.executable, "tools/sync_virc.py"], cwd=root, check=True)
    check(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--bump-internal", metavar="ISSUE")
    mode.add_argument("--set-official", metavar="YYYY_RELEASE")
    parser.add_argument("--issue", help="issue ID for --set-official")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.root.resolve()

    try:
        if args.check:
            if args.issue:
                parser.error("--issue is only valid with --set-official")
            check(root)
            print("Vir compiler version metadata is synchronized.")
            return 0

        record = load_record(root)
        current = version_from_record(record)
        if args.bump_internal:
            issue = args.bump_internal
            if args.issue:
                parser.error("--issue is only valid with --set-official")
            if record["last_completed_issue"] == issue:
                check(root)
                print(f"{issue} already owns compiler version {current.public}; no bump needed.")
                return 0
            next_version = Version(current.year, current.release, current.internal_patch + 1)
        else:
            if not args.issue:
                parser.error("--set-official requires --issue")
            match = OFFICIAL_RE.fullmatch(args.set_official)
            if match is None:
                parser.error("official version must use YYYY.R with R >= 1")
            issue = args.issue
            next_version = Version(int(match.group(1)), int(match.group(2)), 0)
            if (next_version.year, next_version.release) <= (current.year, current.release):
                parser.error("official version must advance the year/release tuple")

        write_version(root, next_version, issue)
        print(f"Vir compiler version is now {next_version.public} ({next_version.channel}).")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Manage the independent Semantic Version of the native vir-lsp server."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
ISSUE_RE = re.compile(r"^VLSP-ISS-[0-9]{4}$")


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int

    @property
    def public(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def load_record(root: Path) -> dict[str, object]:
    path = root / "tools/vir-lsp/version.json"
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
        raise ValueError("tools/vir-lsp/version.json does not match schema 1")
    return record


def version_from_record(record: dict[str, object]) -> Version:
    version = Version(
        int(record["major"]),
        int(record["minor"]),
        int(record["patch"]),
    )
    if version.major < 1 or version.minor < 0 or version.patch < 0:
        raise ValueError("invalid vir-lsp Semantic Version")
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


def check(root: Path) -> None:
    record = load_record(root)
    version = version_from_record(record)
    issue = str(record["last_completed_issue"])
    if not ISSUE_RE.fullmatch(issue):
        raise ValueError("last_completed_issue must be a VLSP-ISS ID")
    if record != expected_record(version, issue):
        raise ValueError("derived fields in vir-lsp version metadata are inconsistent")

    source = (root / "tools/vir-lsp/src/main.vri").read_text(encoding="utf-8")
    expected_literals = (
        f"Version: {version.public} (Pure Vir Native Binary)",
        f"V I R - L S P   {version.public} (Native)",
        f"vir-lsp {version.public} (Language Server Protocol daemon - standalone pure vir)",
        f'\\"version\\":\\"{version.public}\\"',
    )
    for literal in expected_literals:
        if source.count(literal) != 1:
            raise ValueError(f"vir-lsp source is not synchronized: {literal}")


def write_version(root: Path, version: Version, issue: str) -> None:
    if not ISSUE_RE.fullmatch(issue):
        raise ValueError("issue must be a VLSP-ISS ID")
    record_path = root / "tools/vir-lsp/version.json"
    source_path = root / "tools/vir-lsp/src/main.vri"
    current = version_from_record(load_record(root)).public
    source = source_path.read_text(encoding="utf-8")
    source, count = re.subn(rf"(?<![0-9]){re.escape(current)}(?![0-9])", version.public, source)
    if count != 4:
        raise ValueError(f"expected four vir-lsp version literals, found {count}")
    source = source.replace(f"V I R - L S P   v{version.public}", f"V I R - L S P   {version.public}")
    source_path.write_text(source, encoding="utf-8")
    record_path.write_text(
        json.dumps(expected_record(version, issue), indent=2) + "\n",
        encoding="utf-8",
    )
    check(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--patch", metavar="ISSUE")
    mode.add_argument("--minor", metavar="ISSUE")
    mode.add_argument("--major", metavar="ISSUE")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.root.resolve()

    try:
        if args.check:
            check(root)
            print("vir-lsp version metadata is synchronized.")
            return 0

        record = load_record(root)
        current = version_from_record(record)
        issue = args.patch or args.minor or args.major
        if record["last_completed_issue"] == issue:
            check(root)
            print(f"{issue} already owns vir-lsp version {current.public}; no bump needed.")
            return 0
        if args.patch:
            next_version = Version(current.major, current.minor, current.patch + 1)
        elif args.minor:
            next_version = Version(current.major, current.minor + 1, 0)
        else:
            next_version = Version(current.major + 1, 0, 0)
        write_version(root, next_version, issue)
        print(f"vir-lsp version is now {next_version.public}.")
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

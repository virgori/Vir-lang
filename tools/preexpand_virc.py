#!/usr/bin/env python3
"""Pre-expand virc.vri includes (offline) for native compile bootstrap."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = [
    "stdlib/vir/compiler",
    "stdlib/vir/rt",
    "stdlib/vir/collections",
    "stdlib/vir/mem",
    "stdlib/vir/str",
    "stdlib/vir/io",
    "stdlib/vir",
]

# Mirrors read_include_source soft preludes in main.vri
PRELUDE_MAP = {
    "types": "stdlib/vir/compiler/types_prelude.vri",
    "option": "stdlib/vir/compiler/option_prelude.vri",
    "result": "stdlib/vir/compiler/result_prelude.vri",
    "alloc": "stdlib/vir/rt/alloc.vri",
    "syscall": "stdlib/vir/compiler/syscall_prelude.vri",
    "syscall": "stdlib/vir/rt/syscall.vri",
    "vec": "stdlib/vir/compiler/vec_prelude.vri",
    "string_rt": "stdlib/vir/compiler/string_rt_prelude.vri",
    "string_rt": "stdlib/vir/rt/string_rt.vri",
    "error": "stdlib/vir/error/error.vri",
}


def normalize_include(name: str) -> str:
    return name.strip().strip('"').rstrip(";")


def resolve(name: str, parent: Path | None = None) -> Path | None:
    raw = normalize_include(name)

    if raw in PRELUDE_MAP:
        p = ROOT / PRELUDE_MAP[raw]
        if p.is_file():
            return p

    if raw.endswith(".vri"):
        rel = raw
    elif "." in raw and "/" not in raw:
        rel = raw.replace(".", "/") + ".vri"
    else:
        rel = f"{raw}.vri"

    if rel.startswith("vir/"):
        p = ROOT / "stdlib" / rel
        if p.is_file():
            return p

    if parent is not None:
        p = parent.parent / rel
        if p.is_file():
            return p

    for pref in PREFIXES:
        p = ROOT / pref / rel
        if p.is_file():
            return p
        # compiler-local bare includes: parser, mir, lir, etc.
        base = Path(rel).name
        p2 = ROOT / pref / base
        if p2.is_file():
            return p2

    p = ROOT / rel
    return p if p.is_file() else None


def expand_file(path: Path, seen_names: set[str], seen_paths: set[Path]) -> str:
    if path in seen_paths:
        return ""
    canon = path.resolve()
    if canon in seen_paths:
        return ""
    seen_paths.add(path)
    seen_paths.add(canon)

    display_path = path.relative_to(ROOT).as_posix()
    out: list[str] = [f"# @vir_source {display_path} 1"]
    for line_no, line in enumerate(path.read_text().splitlines(), start=1):
        m = re.match(r"^include\s+(\S+)", line)
        if m:
            iname = normalize_include(m.group(1))
            if iname in seen_names:
                continue
            inc = resolve(m.group(1), path)
            if inc is None:
                out.append(f"/* MISSING INCLUDE {m.group(1)} */")
            else:
                seen_names.add(iname)
                out.append(expand_file(inc, seen_names, seen_paths))
                # Restore the parent mapping after returning from an include.
                out.append(f"# @vir_source {display_path} {line_no + 1}")
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def main() -> int:
    src = ROOT / "stdlib/vir/compiler/virc.vri"
    out = ROOT / "dist/virc-expanded.vri"
    if len(sys.argv) > 1:
        out = Path(sys.argv[1])
    text = expand_file(src, set(), set())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    funcs = len(re.findall(r"^func ", text, re.M))
    missing = text.count("MISSING INCLUDE")
    byte_len = len(text.encode())
    print(f"Wrote {out} ({byte_len} bytes, {funcs} funcs, {missing} missing)")
    return 0 if missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

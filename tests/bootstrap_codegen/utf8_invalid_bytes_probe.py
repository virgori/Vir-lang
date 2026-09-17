#!/usr/bin/env python3
"""Check that native virc rejects malformed UTF-8 source with stable diagnostics.

Fixtures are generated at runtime because malformed UTF-8 is not safely stored
in a text .vri file. Usage: python3 utf8_invalid_bytes_probe.py /path/to/virc
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path


PREFIX = b"func main:\n    print_str(\"Ti\xe1\xba\xbfng Vi\xe1\xbb\x87t "
SUFFIX = b"\")\n    out 0\nend.\n"
CASES = {
    "stray_continuation_in_string": PREFIX + b"\x80" + SUFFIX,
    "invalid_lead_in_string": PREFIX + b"\xff" + SUFFIX,
    "truncated_sequence_in_string": PREFIX + b"\xe2" + SUFFIX,
    "overlong_sequence_in_string": PREFIX + b"\xc0\xaf" + SUFFIX,
    "surrogate_sequence_in_string": PREFIX + b"\xed\xa0\x80" + SUFFIX,
    "out_of_range_sequence_in_string": PREFIX + b"\xf4\x90\x80\x80" + SUFFIX,
    "invalid_identifier": b"func main:\n    var x\xff = 1\n    out 0\nend.\n",
    "invalid_comment": b"# Ti\xe1\xba\xbfng Vi\xe1\xbb\x87t \xff\nfunc main:\n    out 0\nend.\n",
}
INCLUDE_CASES = {
    "invalid_included_string": b"func utf8_child_test():\n    print_str(\"Vi\xe1\xbb\x87t \xff\")\nend.\n",
    "invalid_included_comment": b"# Ti\xe1\xba\xbfng Vi\xe1\xbb\x87t \xff\nfunc utf8_child_test():\n    print_str(\"ok\")\nend.\n",
}
IMPORT_CASES = {
    "invalid_imported_string": b"export utf8_child_test;\nfunc utf8_child_test():\n    print_str(\"Vi\xe1\xbb\x87t \xff\")\nend.\n",
    "invalid_imported_comment": b"# Ti\xe1\xba\xbfng Vi\xe1\xbb\x87t \xff\nexport utf8_child_test;\nfunc utf8_child_test():\n    print_str(\"ok\")\nend.\n",
}


def invoke(compiler: Path, source: Path, output: Path):
    result = subprocess.run(
        [str(compiler), str(source), "-o", str(output)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=20,
        check=False,
    )
    codes = re.findall(rb"\[E\d{4}\]", result.stdout)
    return result.returncode, tuple(codes), output.exists(), result.stdout


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    compiler = Path(sys.argv[1]).resolve()
    if not compiler.is_file():
        print(f"Compiler does not exist: {compiler}", file=sys.stderr)
        return 2

    failures = 0
    with tempfile.TemporaryDirectory(prefix="vir_utf8_invalid_", dir="/private/tmp") as temp:
        root = Path(temp)
        sources = dict(CASES)
        for name, child_body in INCLUDE_CASES.items():
            child_name = f"{name}_child.vri"
            (root / child_name).write_bytes(child_body)
            sources[name] = f'include "{child_name}"\nfunc main:\n    utf8_child_test()\n    out 0\nend.\n'.encode("ascii")
        for name, module_body in IMPORT_CASES.items():
            module_name = f"{name}_mod"
            (root / f"{module_name}.vri").write_bytes(module_body)
            sources[name] = f'import utf8_child_test from {module_name};\nfunc main:\n    utf8_child_test()\n    out 0\nend.\n'.encode("ascii")
        for name, body in sources.items():
            source = root / f"{name}.vri"
            source.write_bytes(body)
            first = invoke(compiler, source, root / f"{name}_first")
            second = invoke(compiler, source, root / f"{name}_second")
            ok = (
                first == second
                and first[0] > 0
                and len(first[1]) > 0
                and not first[2]
            )
            print(f"{'PASS' if ok else 'FAIL'} {name}: exit={first[0]} codes={first[1]} binary={first[2]}")
            if not ok:
                print(f"  diagnostic={first[3][-400:]!r}")
                failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

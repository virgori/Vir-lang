#!/usr/bin/env python3
"""alignment_audit.py — Static struct alignment checker for RISC-V compatibility.

Scans C header files for struct definitions and reports fields that would
cause unaligned memory access (SIGBUS/trap) on strict-alignment architectures
like RISC-V.

Usage:
    python scripts/alignment_audit.py [--fix] [header_dir]

Default header_dir: core/include/
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Natural alignment for C types (LP64 model)
TYPE_ALIGNMENT: dict[str, int] = {
    "uint8_t": 1, "int8_t": 1, "char": 1, "bool": 1, "_Bool": 1,
    "uint16_t": 2, "int16_t": 2, "short": 2,
    "uint32_t": 4, "int32_t": 4, "int": 4, "float": 4,
    "uint64_t": 8, "int64_t": 8, "long": 8, "double": 8, "size_t": 8,
    "uintptr_t": 8, "intptr_t": 8, "ptrdiff_t": 8,
}

TYPE_SIZE: dict[str, int] = {
    "uint8_t": 1, "int8_t": 1, "char": 1, "bool": 1, "_Bool": 1,
    "uint16_t": 2, "int16_t": 2, "short": 2,
    "uint32_t": 4, "int32_t": 4, "int": 4, "float": 4,
    "uint64_t": 8, "int64_t": 8, "long": 8, "double": 8, "size_t": 8,
    "uintptr_t": 8, "intptr_t": 8, "ptrdiff_t": 8,
}

# Pointer types: any type ending with * is 8 bytes aligned to 8
POINTER_SIZE = 8
POINTER_ALIGN = 8


@dataclass
class Field:
    name: str
    type_name: str
    is_pointer: bool
    is_array: bool
    array_count: int
    line_no: int

    @property
    def size(self) -> int:
        if self.is_pointer:
            return POINTER_SIZE
        base = TYPE_SIZE.get(self.type_name, 0)
        if self.is_array and base > 0:
            return base * self.array_count
        return base

    @property
    def alignment(self) -> int:
        if self.is_pointer:
            return POINTER_ALIGN
        return TYPE_ALIGNMENT.get(self.type_name, 0)


@dataclass
class StructDef:
    name: str
    fields: list[Field]
    file_path: str
    line_no: int


@dataclass
class AlignmentIssue:
    struct_name: str
    field_name: str
    offset: int
    required_align: int
    file_path: str
    line_no: int
    severity: str  # "error" or "warning"


# Regex patterns for struct parsing
STRUCT_START = re.compile(
    r"typedef\s+struct\s*\{|struct\s+(\w+)\s*\{", re.MULTILINE
)
STRUCT_TYPEDEF_END = re.compile(r"\}\s*(\w+)\s*;")
FIELD_PATTERN = re.compile(
    r"^\s+"
    r"(?:const\s+|volatile\s+|unsigned\s+|signed\s+)*"
    r"(\w+)"               # type
    r"\s*(\*?)\s*"          # optional pointer
    r"(\w+)"               # field name
    r"(?:\[(\d+)\])?"      # optional array
    r"\s*;",
    re.MULTILINE,
)


def parse_structs(path: Path) -> list[StructDef]:
    """Extract struct definitions from a C header file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    structs: list[StructDef] = []

    # Simple brace-matching parser
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = STRUCT_START.search(line)
        if m:
            struct_start_line = i + 1
            # Collect until closing brace
            depth = line.count("{") - line.count("}")
            body_lines = [line]
            j = i + 1
            while j < len(lines) and depth > 0:
                body_lines.append(lines[j])
                depth += lines[j].count("{") - lines[j].count("}")
                j += 1
            body = "\n".join(body_lines)

            # Get struct name
            name = m.group(1) or ""
            end_m = STRUCT_TYPEDEF_END.search(body_lines[-1] if body_lines else "")
            if end_m:
                name = end_m.group(1)
            if not name:
                i = j
                continue

            # Parse fields
            fields: list[Field] = []
            for fi, fline in enumerate(body_lines[1:], start=struct_start_line + 1):
                fm = FIELD_PATTERN.match(fline)
                if fm:
                    type_name = fm.group(1)
                    is_ptr = bool(fm.group(2))
                    field_name = fm.group(3)
                    arr_count = int(fm.group(4)) if fm.group(4) else 0
                    fields.append(Field(
                        name=field_name,
                        type_name=type_name,
                        is_pointer=is_ptr,
                        is_array=arr_count > 0,
                        array_count=arr_count,
                        line_no=fi,
                    ))

            if fields:
                structs.append(StructDef(
                    name=name,
                    fields=fields,
                    file_path=str(path),
                    line_no=struct_start_line,
                ))
            i = j
        else:
            i += 1

    return structs


def check_alignment(s: StructDef) -> list[AlignmentIssue]:
    """Check a struct for alignment issues."""
    issues: list[AlignmentIssue] = []
    offset = 0
    max_align = 1

    for field in s.fields:
        align = field.alignment
        size = field.size

        if align == 0 or size == 0:
            # Unknown type (nested struct, enum, etc.) — skip
            continue

        max_align = max(max_align, align)

        # Check if current offset satisfies alignment
        misalign = offset % align
        if misalign != 0:
            issues.append(AlignmentIssue(
                struct_name=s.name,
                field_name=field.name,
                offset=offset,
                required_align=align,
                file_path=s.file_path,
                line_no=field.line_no,
                severity="error",
            ))
            # Add padding for continued analysis
            offset += align - misalign

        offset += size

    # Check total struct size alignment
    if max_align > 1 and offset % max_align != 0:
        issues.append(AlignmentIssue(
            struct_name=s.name,
            field_name="<struct_total_size>",
            offset=offset,
            required_align=max_align,
            file_path=s.file_path,
            line_no=s.line_no,
            severity="warning",
        ))

    return issues


def audit_directory(header_dir: Path) -> list[AlignmentIssue]:
    """Audit all .h files in a directory."""
    all_issues: list[AlignmentIssue] = []
    headers = sorted(header_dir.glob("*.h"))

    for hdr in headers:
        structs = parse_structs(hdr)
        for s in structs:
            issues = check_alignment(s)
            all_issues.extend(issues)

    return all_issues


def main() -> int:
    header_dir = Path("core/include")

    if len(sys.argv) > 1 and sys.argv[-1] != "--fix":
        header_dir = Path(sys.argv[-1])

    if not header_dir.is_dir():
        print(f"Error: {header_dir} is not a directory", file=sys.stderr)
        return 1

    print(f"Scanning {header_dir}/ for alignment issues...\n")

    issues = audit_directory(header_dir)

    if not issues:
        print("✅ No alignment issues found — RISC-V safe!")
        return 0

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    for issue in issues:
        icon = "❌" if issue.severity == "error" else "⚠️"
        if issue.field_name == "<struct_total_size>":
            print(
                f"  {icon} {issue.struct_name}: total size {issue.offset} "
                f"not a multiple of {issue.required_align} "
                f"({issue.file_path}:{issue.line_no})"
            )
        else:
            print(
                f"  {icon} {issue.struct_name}.{issue.field_name}: "
                f"offset {issue.offset} misaligned for {issue.required_align}-byte type "
                f"({issue.file_path}:{issue.line_no})"
            )

    print(f"\nSummary: {len(errors)} errors, {len(warnings)} warnings")

    if errors:
        print("\nTo fix: reorder fields from largest to smallest alignment,")
        print("or add VIR_ALIGNED(n) from vir_platform.h.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

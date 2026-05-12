#!/usr/bin/env python3
"""Phase 3: Fix remaining Vietnamese keywords in .vri files.
   - 'in khi' -> 'while' (compound keyword)
   - 'không' -> 'not' (negation, code-only)
   - 'dài(' -> 'len(' (length function)
"""
import os
import re

changes = 0
total_replacements = 0

for root, dirs, files in os.walk("stdlib"):
    for f in files:
        if not f.endswith(".vri"):
            continue
        path = os.path.join(root, f)
        with open(path, "r") as fh:
            content = fh.read()
        original = content

        # 'in khi' -> 'while'
        content = re.sub(r"\bin khi\b", "while", content)

        # 'không' -> 'not' in code lines only (skip comments and strings)
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("#") or stripped.startswith("*") or stripped.startswith("//"):
                new_lines.append(line)
                continue
            if "không" in line:
                parts = re.split(r'("[^"]*")', line)
                new_parts = []
                for part in parts:
                    if part.startswith('"'):
                        new_parts.append(part)
                    else:
                        new_parts.append(re.sub(r"\bkhông\b", "not", part))
                line = "".join(new_parts)
            new_lines.append(line)
        content = "\n".join(new_lines)

        # 'dài(' -> 'len('
        content = re.sub(r"\bdài\(", "len(", content)

        if content != original:
            with open(path, "w") as fh:
                fh.write(content)
            count = original.count("in khi") + original.count("không") + original.count("dài(") - content.count("in khi") - content.count("không") - content.count("dài(")
            print(f"  {path} ({count} replacements)")
            changes += 1
            total_replacements += count

print(f"\nPhase 3: {changes} files updated, {total_replacements} replacements")

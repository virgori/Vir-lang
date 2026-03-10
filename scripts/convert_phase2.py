#!/usr/bin/env python3
"""Phase 2 conversion: remaining Vietnamese keywords the first pass missed."""

import os, re, sys

STDLIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stdlib', 'vir')

# Ordered: multi-word first, then single-word
REPLACEMENTS = [
    # Multi-word keywords
    (r'\bho\u1eb7c_n\u1ebfu\b', 'eif'),
    (r'\btr\u01b0\u1eddng_h\u1ee3p\b', 'case'),
    (r'\bv\u1edbi_m\u1ed7i\b', 'for'),
    # 'thi' at end of line (block opener) - remove
    (r'\s+th\u00ec\s*$', ''),
    # 'thi' inline (case X thi Y) - just remove
    (r'\bth\u00ec\b\s*', ''),
    # Single-word
    (r'\bl\u1eb7p\b', 'loop'),
    (r'\bti\u1ebfp\b', 'skip'),
    (r'\bnh\u1eadn\b', 'input'),
    (r'\btrong\b', 'in'),
]

def convert_file(filepath, dry_run=False):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    changes = 0

    for pattern, replacement in REPLACEMENTS:
        c = len(re.findall(pattern, content, flags=re.MULTILINE))
        changes += c
        if c > 0:
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    if changes > 0 and not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    return changes

def main():
    dry_run = '--dry-run' in sys.argv
    total_changes = 0
    total_files = 0

    for root, dirs, files in os.walk(STDLIB_DIR):
        for f in sorted(files):
            if f.endswith('.vri'):
                path = os.path.join(root, f)
                changes = convert_file(path, dry_run)
                if changes > 0:
                    total_files += 1
                    total_changes += changes
                    rel = os.path.relpath(path, STDLIB_DIR)
                    tag = '[DRY] ' if dry_run else ''
                    print(f"  {tag}v {rel}: {changes} changes")

    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\n[{mode}] {total_files} files, {total_changes} total changes")

if __name__ == '__main__':
    main()

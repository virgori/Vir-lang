#!/usr/bin/env python3
"""
Update test .vri files to use new v1.2 block syntax:
  - if/eif conditions get 'do' at end of line
  - func/entity/enum/record blocks close with 'end.' instead of 'end'
  - loop/while/when/for/case/if blocks keep plain 'end'
  - else block does NOT get 'do'
"""
import re, glob, sys

# Block openers that use 'end.' (definition blocks)
DEF_OPENERS = re.compile(r'^\s*(func|entity|enum|record|struct|method|class|trait|impl)\b')
# Block openers that use plain 'end' (control flow) — only ones that have their own 'end'
# eif/elif/else do NOT push, they are part of the if block
CTRL_OPENERS = re.compile(r'^\s*(if|loop|while|when|for|case)\b')
# if/eif line pattern: captures leading whitespace, keyword, and condition
IF_LINE = re.compile(r'^(\s*)(if|eif|elif)\s+(.+)$')
# end line
END_LINE = re.compile(r'^(\s*)end\s*$')

def transform_file(path):
    with open(path, 'r') as f:
        lines = f.readlines()

    # First pass: track block stack to know what each 'end' closes
    block_stack = []  # list of 'def' or 'ctrl'
    changes = []  # (line_idx, change_type)

    for i, line in enumerate(lines):
        stripped = line.rstrip('\n')

        # Check if this line opens a definition block
        if DEF_OPENERS.match(stripped):
            block_stack.append('def')
            continue

        # Check if this line opens a control flow block
        if CTRL_OPENERS.match(stripped):
            block_stack.append('ctrl')
            continue

        # Check if this is an 'end' line
        if END_LINE.match(stripped):
            if block_stack:
                block_type = block_stack.pop()
                if block_type == 'def':
                    changes.append((i, 'end_dot'))
            continue

    # Second pass: apply changes
    new_lines = list(lines)

    # Add 'do' to if/eif lines
    for i, line in enumerate(new_lines):
        m = IF_LINE.match(line.rstrip('\n'))
        if m:
            indent, kw, cond = m.groups()
            cond = cond.rstrip()
            # Don't add if already has 'do' at end
            if not cond.endswith(' do') and cond != 'do':
                new_lines[i] = f"{indent}{kw} {cond} do\n"

    # Change 'end' to 'end.' for definition blocks
    for line_idx, change_type in changes:
        if change_type == 'end_dot':
            m = END_LINE.match(new_lines[line_idx].rstrip('\n'))
            if m:
                indent = m.group(1)
                new_lines[line_idx] = f"{indent}end.\n"

    if new_lines != lines:
        with open(path, 'w') as f:
            f.writelines(new_lines)
        return True
    return False

def main():
    files = sorted(glob.glob('/Users/gengyang/Desktop/AI/Vir/test_*.vri'))
    # Also include demo files
    files += sorted(glob.glob('/Users/gengyang/Desktop/AI/Vir/demo_*.vri'))

    changed = 0
    for path in files:
        if transform_file(path):
            changed += 1
            print(f"  updated: {path.split('/')[-1]}")
    print(f"\nTotal: {changed}/{len(files)} files updated")

if __name__ == '__main__':
    main()

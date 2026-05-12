#!/usr/bin/env python3
"""
Revert test .vri files back to old syntax, then apply new syntax correctly.
Step 1: Remove 'do' from if/eif lines, change 'end.' back to 'end'
Step 2: Re-apply with correct block tracking (eif/else don't push stack)
"""
import re, glob

IF_DO_LINE = re.compile(r'^(\s*)(if|eif|elif)\s+(.*?)\s+do\s*$')
END_DOT_LINE = re.compile(r'^(\s*)end\.\s*$')

def revert_file(path):
    with open(path, 'r') as f:
        lines = f.readlines()
    new_lines = []
    for line in lines:
        # Remove trailing 'do' from if/eif lines
        m = IF_DO_LINE.match(line.rstrip('\n'))
        if m:
            indent, kw, cond = m.groups()
            new_lines.append(f"{indent}{kw} {cond}\n")
            continue
        # Change 'end.' back to 'end'
        m = END_DOT_LINE.match(line.rstrip('\n'))
        if m:
            indent = m.group(1)
            new_lines.append(f"{indent}end\n")
            continue
        new_lines.append(line)
    with open(path, 'w') as f:
        f.writelines(new_lines)

# Block openers that use 'end.' (definition blocks)
DEF_OPENERS = re.compile(r'^\s*(func|entity|enum|record|struct|method|class|trait|impl)\b')
# Block openers that use plain 'end' (control flow)
# eif/elif/else do NOT push — they are part of the if block
CTRL_OPENERS = re.compile(r'^\s*(if|loop|while|when|for|case)\b')
IF_LINE = re.compile(r'^(\s*)(if|eif|elif)\s+(.+)$')
END_LINE = re.compile(r'^(\s*)end\s*$')

def transform_file(path):
    with open(path, 'r') as f:
        lines = f.readlines()

    # Track block stack
    block_stack = []  # 'def' or 'ctrl'
    end_dot_lines = set()

    for i, line in enumerate(lines):
        stripped = line.rstrip('\n')
        # Skip comments and blank lines
        stripped_no_ws = stripped.lstrip()
        if stripped_no_ws.startswith('#') or stripped_no_ws == '':
            continue

        if DEF_OPENERS.match(stripped):
            block_stack.append('def')
            continue

        if CTRL_OPENERS.match(stripped):
            block_stack.append('ctrl')
            continue

        if END_LINE.match(stripped):
            if block_stack:
                block_type = block_stack.pop()
                if block_type == 'def':
                    end_dot_lines.add(i)
            continue

    # Apply changes
    new_lines = list(lines)

    # Add 'do' to if/eif lines
    for i, line in enumerate(new_lines):
        m = IF_LINE.match(line.rstrip('\n'))
        if m:
            indent, kw, cond = m.groups()
            cond = cond.rstrip()
            if not cond.endswith(' do') and cond != 'do':
                new_lines[i] = f"{indent}{kw} {cond} do\n"

    # Change 'end' to 'end.' for definition blocks
    for line_idx in end_dot_lines:
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
    files += sorted(glob.glob('/Users/gengyang/Desktop/AI/Vir/demo_*.vri'))

    print("Step 1: Reverting to original syntax...")
    for path in files:
        revert_file(path)

    print("Step 2: Applying new syntax (fixed block tracking)...")
    changed = 0
    for path in files:
        if transform_file(path):
            changed += 1
    print(f"\nTotal: {changed}/{len(files)} files updated")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Convert vir_parser.vri from legacy syntax to v1.2 syntax."""
import re
import sys

infile = sys.argv[1] if len(sys.argv) > 1 else 'core/bootstrap/vir_parser_legacy.vri'
outfile = sys.argv[2] if len(sys.argv) > 2 else 'core/bootstrap/vir_parser.vri'

with open(infile, 'r') as f:
    lines = f.readlines()

out = []
for line in lines:
    s = line.rstrip('\n')

    # func name() then → func name:
    m = re.match(r'^(func\s+\w+)\(\)\s+then\s*$', s)
    if m:
        out.append(m.group(1) + ':')
        continue

    # func name(params) then → func name:\n    in(params)
    m = re.match(r'^(func\s+\w+)\(([^)]+)\)\s+then\s*$', s)
    if m:
        out.append(m.group(1) + ':')
        out.append('    in(' + m.group(2) + ')')
        continue

    # while COND then → when COND loop  (any indentation)
    m = re.match(r'^(\s*)while\s+(.+?)\s+then\s*$', s)
    if m:
        out.append(m.group(1) + 'when ' + m.group(2) + ' loop')
        continue

    # return EXPR → out EXPR;  (any indentation)
    m = re.match(r'^(\s*)return\s+(.+)$', s)
    if m:
        out.append(m.group(1) + 'out ' + m.group(2) + ';')
        continue

    # return (bare) → out 0;
    m = re.match(r'^(\s*)return\s*$', s)
    if m:
        out.append(m.group(1) + 'out 0;')
        continue

    # if COND then → if COND:  (any indentation)
    m = re.match(r'^(\s*)if\s+(.+?)\s+then\s*$', s)
    if m:
        out.append(m.group(1) + 'if ' + m.group(2) + ':')
        continue

    # elif COND then → eif COND:  (any indentation)
    m = re.match(r'^(\s*)elif\s+(.+?)\s+then\s*$', s)
    if m:
        out.append(m.group(1) + 'eif ' + m.group(2) + ':')
        continue

    # No match — keep as is
    out.append(s)

with open(outfile, 'w') as f:
    f.write('\n'.join(out) + '\n')

print(f'Converted {len(lines)} lines → {len(out)} lines written to {outfile}')

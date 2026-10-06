#!/usr/bin/env python3
"""Run the native LSP regression suite with bounded subprocess lifetimes."""
import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--lsp', type=Path, default=root / 'bin/vir-lsp')
options = parser.parse_args()
binary = options.lsp.resolve()
if not binary.is_file() or not os.access(binary, os.X_OK):
    parser.error(f'LSP binary is not executable: {binary}')
environment = dict(os.environ, VIR_LSP=str(binary))
print(f'LSP: {binary} sha256={hashlib.sha256(binary.read_bytes()).hexdigest()}', flush=True)
for name in (
    'test_lsp_document_isolation.py',
    'test_lsp_registry_cwd.py',
    'test_lsp_cancellation.py',
    'test_lsp_partial_input.py',
    'test_lsp_timeout.py',
    'test_lsp_cross_file.py',
    'test_lsp_import_alias.py',
    'test_lsp_focus.py',
    'test_lsp_checker_equivalence.py',
    'test_lsp_diagnostic_mapping.py',
    'test_lsp_member_graph.py',
    'test_lsp_type_graph.py',
    'test_lsp_unicode_roundtrip.py',
    'test_lsp_compiler_facts.py',
    'test_lsp_session_resources.py',
    'test_lsp_repro_turn3.py',
    'test_lsp_repro_p1_p2.py',
    'test_lsp_in_ref_out.py',
    'test_lsp_features.py',
    'test_lsp_initialize.py',
    'test_lsp_completion_rename_contract.py',
):
    subprocess.run([sys.executable, str(root / 'tests' / name)], cwd=root,
                   check=True, timeout=60 if name == 'test_lsp_session_resources.py' else (45 if name == 'test_lsp_timeout.py' else 30),
                   env=environment)
if os.environ.get('VIR_LSP_SKIP_NODE_CLIENT') == '1':
    print('SKIP: Node client contract delegated to an external host')
else:
    subprocess.run(['node', 'vscode-tool/test/lsp_contract.js'], cwd=root,
                   check=True, timeout=30, env=environment)
print('PASS: native LSP regression suite')

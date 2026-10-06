#!/usr/bin/env python3
"""Build native LSP on the synchronized self-host compiler runtime.

The compiler bundle supplies its verified runtime ABI and semantic passes.
The entrypoint and session adapter are derived from canonical source files;
this script does not rewrite language syntax or compiler semantics.
"""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def adapter(path):
    lines = path.read_text().splitlines()
    result = []
    skipping = False
    exporting = False
    for line in lines:
        if exporting:
            exporting = line.rstrip().endswith(",")
            result.append("")
            continue
        if re.match(r'^(include|module)\s', line):
            result.append('')
            continue
        if re.match(r'^import\s', line):
            skipping = ' from ' not in line
            result.append('')
            continue
        if skipping:
            if ' from ' in line:
                skipping = False
            result.append('')
            continue
        if re.match(r'^export\s', line):
            exporting = line.rstrip().endswith(",")
            result.append('')
            continue
        result.append(line)
    return '\n'.join(result)

args = argparse.ArgumentParser()
args.add_argument('--compiler', default=str(ROOT / 'bin/virc'))
args.add_argument('--optimization', choices=['0', '1', '2', '3'], default='1')
args.add_argument('--target', choices=['macos-arm64', 'macos-arm64-libsystem',
                  'linux-arm64', 'windows-arm64', 'linux-x86_64',
                  'windows-x86_64', 'linux-riscv64', 'wasm32-wasi-p1'])
args.add_argument('--output', default=str(ROOT / 'bin/vir-lsp'))
options = args.parse_args()

subprocess.run(['python3', 'tools/sync_virc.py', '--check'], cwd=ROOT, check=True)
subprocess.run(['python3', 'tools/bump_vir_lsp_version.py', '--check'], cwd=ROOT, check=True)

virc_bundle_path = ROOT / 'compiler/generated/virc.vri'
if not virc_bundle_path.is_file():
    virc_bundle_path = ROOT / 'stdlib/vir/compiler/virc.vri'

ide_session_path = ROOT / 'compiler/src/ide/ide_session.vri'
if not ide_session_path.is_file():
    ide_session_path = ROOT / 'stdlib/vir/compiler/ide_session.vri'

lsp_main_path = ROOT / 'tools/vir-lsp/src/main.vri'
if not lsp_main_path.is_file():
    lsp_main_path = ROOT / 'vir-lsp/src/main.vri'

canonicalHashes = {
    str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in (virc_bundle_path, ide_session_path, lsp_main_path)
}
compiler = Path(options.compiler).resolve()
compilerHash = hashlib.sha256(compiler.read_bytes()).hexdigest()

bundle = virc_bundle_path.read_text()
bundle, count = re.subn(r'^func main(?=[:(])', 'func compilerMain', bundle, flags=re.M)
if count != 1:
    raise RuntimeError(f'Expected one compiler entrypoint, found {count}')

(ROOT / 'scratch').mkdir(exist_ok=True)
with tempfile.NamedTemporaryFile(prefix='vir-lsp-build-', suffix='.vri', dir=ROOT / 'scratch', delete=False) as temporary:
    source = Path(temporary.name)

source.write_text(
    bundle +
    f'\n# @vir_source {ide_session_path.relative_to(ROOT).as_posix()} 1\n' + adapter(ide_session_path) +
    f'\n# @vir_source {lsp_main_path.relative_to(ROOT).as_posix()} 1\n' + adapter(lsp_main_path) +
    '\n'
)

command = [options.compiler, '--ui=classic', '-q', '-O' + options.optimization,
           str(source), '-o', options.output]
if options.target:
    command.extend(['--target', options.target])

completed = subprocess.run(command, cwd=ROOT)
output = Path(options.output).resolve()
compiler = Path(options.compiler).resolve()

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

manifest = {
    'schemaVersion': 1,
    'compiler': str(compiler), 'compilerSha256': compilerHash,
    'target': options.target or 'host', 'optimizationLevel': int(options.optimization),
    'command': command, 'workingDirectory': str(ROOT), 'exitCode': completed.returncode,
    'generatedSource': str(source), 'generatedSourceSha256': sha256(source),
    'outputBinary': str(output), 'outputBinarySha256': sha256(output),
    'canonicalSources': canonicalHashes,
}
manifestPath = ROOT / 'bin/vir-lsp.build.json'
manifestPath.write_text(json.dumps(manifest, indent=2) + '\n')

if completed.returncode != 0:
    print(f'vir-lsp build failed with exit code {completed.returncode}')
    raise SystemExit(completed.returncode)

print(f'Built vir-lsp executable: {output} (sha256: {sha256(output)})')

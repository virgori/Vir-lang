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
            exporting = line.rstrip().endswith(',')
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
canonicalHashes = {
    str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in (ROOT / 'stdlib/vir/compiler/virc.vri',
                 ROOT / 'stdlib/vir/compiler/ide_session.vri',
                 ROOT / 'tools/vir-lsp/src/main.vri')
}
compiler = Path(options.compiler).resolve()
compilerHash = hashlib.sha256(compiler.read_bytes()).hexdigest()
bundle = (ROOT / 'stdlib/vir/compiler/virc.vri').read_text()
bundle, count = re.subn(r'^func main(?=[:(])', 'func compilerMain', bundle, flags=re.M)
if count != 1:
    raise RuntimeError(f'Expected one compiler entrypoint, found {count}')
with tempfile.NamedTemporaryFile(prefix='vir-lsp-build-', suffix='.vri', dir=ROOT / 'scratch', delete=False) as temporary:
    source = Path(temporary.name)
source.write_text(bundle + '\n# @vir_source stdlib/vir/compiler/ide_session.vri 1\n' + adapter(ROOT / 'stdlib/vir/compiler/ide_session.vri') + '\n# @vir_source tools/vir-lsp/src/main.vri 1\n' + adapter(ROOT / 'tools/vir-lsp/src/main.vri') + '\n')
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
    'canonicalSourceSha256': canonicalHashes,
    'output': str(output),
    'outputSha256': sha256(output) if completed.returncode == 0 else None,
}
output.with_name(output.name + '.build.json').write_text(json.dumps(manifest, indent=2) + '\n')
if completed.returncode:
    raise subprocess.CalledProcessError(completed.returncode, command)

# macOS: re-sign the binary after replacing it in-place, otherwise the OS
# invalidates the existing code signature and kills it with SIGKILL on launch.
import platform
if platform.system() == 'Darwin' and output.exists():
    subprocess.run(['codesign', '-f', '-s', '-', str(output)], check=False)

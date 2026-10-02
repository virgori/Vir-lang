"""Unsaved snapshots preserve checker results for branch, loop and loan fixtures."""
import os
import re
import subprocess
import tempfile
from pathlib import Path
from test_lsp_in_ref_out import ROOT, VIR_LSP, send_message, read_response

compiler = Path(os.environ.get('VIRC', ROOT / 'bin/virc'))
p = subprocess.Popen([str(VIR_LSP), '--stdio'], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
notifications = []
ident = 0

def request(method, params):
    global ident
    ident += 1
    send_message(p, {'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params})
    return read_response(p, ident, notifications)

def snapshot(uri, source):
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {
        'textDocument': {'uri': uri, 'version': 1, 'text': source}}})
    result = request('vir/semanticSnapshot', {'textDocument': {'uri': uri}})['result']
    diagnostics = [n['params']['diagnostics'] for n in notifications
                   if n.get('method') == 'textDocument/publishDiagnostics'
                   and n['params']['uri'] == uri][-1]
    return result, diagnostics

try:
    request('initialize', {'capabilities': {}})
    fixtures = ['double_mut_borrow_negative', 'mutate_shared_borrow_negative',
                'loop_if_move_negative', 'loop_borrow_last_use_positive',
                'loop_shadow_binding_positive']
    with tempfile.TemporaryDirectory(prefix='vir-checker-equivalence-') as directory:
        for name in fixtures:
            fixture = ROOT / 'tests/memory_contract' / (name + '.vri')
            source = fixture.read_text()
            native = subprocess.run([str(compiler), str(fixture), '-O1', '-o',
                                     str(Path(directory) / name)], capture_output=True,
                                    text=True, timeout=60)
            native_codes = set(re.findall(r'\bE5\d{3}\b', native.stdout + native.stderr))
            result, diagnostics = snapshot('file:///tmp/unsaved-' + name + '.vri', source)
            ide_codes = {d['code'] for d in diagnostics if str(d['code']).startswith('E5')}
            assert native_codes == ide_codes, (name, native_codes, ide_codes, diagnostics)
            assert (native.returncode == 0) == (not ide_codes), (name, native.returncode, diagnostics)
            if native_codes:
                assert any('virMoved' in o['states'] or 'virBorrowed' in o['states']
                           or 'virInvalid' in o['states'] for o in result['occurrences']), result
    for mode, address in [('shared', '&value'), ('mutable', '&mut value')]:
        source = 'func main:\n    var value = 10\n    let holder = ' + address + '\n    print holder\nend.\n'
        result, diagnostics = snapshot('file:///tmp/loan-mode-' + mode + '.vri', source)
        assert not diagnostics, diagnostics
        holder = next(s for s in result['symbols'] if s['name'] == 'holder')
        use = next(o for o in result['occurrences'] if o['symbolId'] == holder['symbolId']
                   and o['range']['start']['line'] == 3)
        assert use['borrowKind'] == mode and 'virBorrowed' in use['states'], use
        assert use['lifetimeEnd'] == {'uri': 'file:///tmp/loan-mode-' + mode + '.vri',
                                      'position': {'line': 3, 'character': 4}}, use
        binding = next(f for f in result['checkerFacts'] if f['symbolId'] == holder['symbolId']
                       and f['range']['start']['line'] == 3)
        assert binding['bindingId'] != binding['ownerBindingId'], binding
        assert binding['borrowOrigin'] == {'uri': 'file:///tmp/loan-mode-' + mode + '.vri', 'line': 2}, binding
        assert binding['stateBefore'] == 2 and binding['stateAfter'] == 2, binding
    branch_uri = 'file:///tmp/loan-branch-boundary.vri'
    branch_source = ('func main:\n    var value = 10\n    let holder = &value\n'
                     '    if true do\n        print holder\n    else\n        print holder\n    end\n'
                     '    value = 11\n    print value\nend.\n')
    branch, branch_diagnostics = snapshot(branch_uri, branch_source)
    assert not branch_diagnostics and branch['complete'], (branch_diagnostics, branch)
    branch_holder = next(s for s in branch['symbols'] if s['name'] == 'holder')
    branch_uses = [o for o in branch['occurrences'] if o['symbolId'] == branch_holder['symbolId']
                   and o['role'] != 'declaration']
    assert all('virLastUse' not in o['states'] for o in branch_uses), branch_uses
    conservative = [f for f in branch['checkerFacts'] if f['symbolId'] == branch_holder['symbolId']
                    and f['lastUseMode'] == 'conservative']
    assert conservative, branch
    assert any('conservative' in o['lifetimeEndReason'] and o['lifetimeEnd'] == {
        'uri': branch_uri, 'position': {'line': 3, 'character': 4}} for o in branch_uses), branch_uses
    request('shutdown', {})
    send_message(p, {'jsonrpc': '2.0', 'method': 'exit'})
    assert p.wait(timeout=5) == 0
    print('PASS: CLI/checker diagnostic equivalence and actual shared/mutable loan facts')
finally:
    if p.poll() is None:
        p.kill()
        p.wait(timeout=5)

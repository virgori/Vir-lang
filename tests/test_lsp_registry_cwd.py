"""Explicit IDE sysroot is independent of client working directory."""
import subprocess
from test_lsp_in_ref_out import ROOT, VIR_LSP, send_message, read_response
for directory, registry, expected in [('/', ROOT / 'stdlib/stdlib.vri', True), ('/tmp', ROOT / 'stdlib/stdlib.vri', True), ('/', ROOT / 'scratch/missing-registry.vri', False)]:
    p = subprocess.Popen([str(VIR_LSP), '--stdio', '--stdlib-registry', str(registry)], cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    notifications = []
    try:
        send_message(p, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'capabilities': {}}})
        read_response(p, 1, notifications)
        uri = 'file:///tmp/vir-foreign-cwd.vri'
        send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {'textDocument': {'uri': uri, 'version': 3, 'text': 'func main:\n    var value = 1\n    print value\nend.\n'}}})
        send_message(p, {'jsonrpc': '2.0', 'id': 2, 'method': 'vir/semanticSnapshot', 'params': {'textDocument': {'uri': uri}}})
        result = read_response(p, 2, notifications)['result']
        assert result['complete'] == expected, result
        if expected:
            assert any(s['name'] == 'value' and s['type'] == 'int' for s in result['symbols']), result
        else:
            assert result['unavailableReason']
        send_message(p, {'jsonrpc': '2.0', 'id': 3, 'method': 'shutdown', 'params': {}})
        read_response(p, 3, notifications)
        send_message(p, {'jsonrpc': '2.0', 'method': 'exit'})
        assert p.wait(timeout=5) == 0
    finally:
        if p.poll() is None:
            p.kill(); p.wait(timeout=5)
print('PASS: explicit registry works from foreign CWD; missing configured sysroot fails without fallback')

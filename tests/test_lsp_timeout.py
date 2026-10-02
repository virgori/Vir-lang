"""Bound pathological compiler work and keep the supervisor usable afterwards."""
import subprocess
import time
from test_lsp_in_ref_out import VIR_LSP, send_message, read_response
p = subprocess.Popen([str(VIR_LSP), '--stdio'], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
try:
    send_message(p, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'capabilities': {}}})
    read_response(p, 1)
    uri = 'file:///tmp/compiler-worker-timeout.vri'
    source = 'func main:\n' + ''.join(f'    var value{i} = {i}\n' for i in range(120000)) + 'end.\n'
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {
        'textDocument': {'uri': uri, 'version': 1, 'text': source}}})
    started = time.monotonic()
    send_message(p, {'jsonrpc': '2.0', 'id': 2, 'method': 'vir/semanticSnapshot',
                     'params': {'textDocument': {'uri': uri}}})
    result = read_response(p, 2)
    elapsed = time.monotonic() - started
    assert result.get('error', {}).get('code') == -32800, result
    assert 'timed out' in result['error']['message'], result
    assert 8 <= elapsed < 35, elapsed
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didChange', 'params': {
        'textDocument': {'uri': uri, 'version': 2},
        'contentChanges': [{'text': 'func main:\n    print 1\nend.\n'}]}})
    send_message(p, {'jsonrpc': '2.0', 'id': 3, 'method': 'vir/semanticSnapshot',
                     'params': {'textDocument': {'uri': uri}}})
    assert read_response(p, 3)['result']['documentVersion'] == 2
    send_message(p, {'jsonrpc': '2.0', 'id': 4, 'method': 'shutdown'})
    read_response(p, 4)
    send_message(p, {'jsonrpc': '2.0', 'method': 'exit'})
    assert p.wait(timeout=5) == 0
    print(f'PASS: compiler timeout, worker reap and recovery ({elapsed:.2f}s)')
finally:
    if p.poll() is None:
        p.kill()
        p.wait(timeout=5)

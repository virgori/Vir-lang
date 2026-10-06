"""Cancellation and stale-work isolation over the real native transport."""
import json
import subprocess
import time
from test_lsp_in_ref_out import VIR_LSP, send_message, read_response

p = subprocess.Popen([str(VIR_LSP), '--stdio'], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
notifications = []
def send(method, params, ident=None):
    msg = {'jsonrpc': '2.0', 'method': method, 'params': params}
    if ident is not None:
        msg['id'] = ident
    send_message(p, msg)
def query(ident, uri):
    send('vir/semanticSnapshot', {'textDocument': {'uri': uri}}, ident)
try:
    send('initialize', {'capabilities': {}}, 1)
    assert 'result' in read_response(p, 1, notifications)
    uri = 'file:///tmp/lsp-cancel-unsaved.vri'
    source = 'func main:\n' + ''.join(f'    var value{i} = {i}\n' for i in range(400)) + 'end.\n'
    send('textDocument/didOpen', {'textDocument': {'uri': uri, 'version': 1, 'text': source}})
    query(2, uri)
    send('$/cancelRequest', {'id': 2})
    cancelled = read_response(p, 2, notifications)
    assert cancelled.get('error', {}).get('code') == -32800, cancelled
    query(3, uri)
    send('textDocument/didChange', {'textDocument': {'uri': uri, 'version': 2},
                                  'contentChanges': [{'text': 'func main:\n    var fresh = 1\nend.\n'}]})
    stale = read_response(p, 3, notifications)
    assert stale.get('error', {}).get('code') == -32801, stale
    query(4, uri)
    current = read_response(p, 4, notifications)['result']
    assert current['documentVersion'] == 2, current
    assert any(s['name'] == 'fresh' for s in current['symbols']), current
    assert not any(s['name'] == 'value0' for s in current['symbols']), current
    send('shutdown', {}, 5)
    assert read_response(p, 5, notifications)['result'] is None
    send('exit', {})
    assert p.wait(timeout=5) == 0
    print('PASS: cancellation, stale requests, recovery and shutdown')
finally:
    if p.poll() is None:
        p.kill()
        p.wait(timeout=5)

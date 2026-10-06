"""Focus uses versioned compiler IDs and never combines same-name bindings."""
import subprocess
from test_lsp_in_ref_out import VIR_LSP, send_message, read_response
p = subprocess.Popen([str(VIR_LSP), '--stdio'], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
ident = 0
notifications = []
def request(method, params):
    global ident
    ident += 1
    send_message(p, {'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params})
    return read_response(p, ident, notifications)
try:
    request('initialize', {'capabilities': {}})
    uri = 'file:///tmp/compiler-focus-shadowing.vri'
    source = ('func alpha:\n    var value = 1\n    print value\nend.\n'
              'func beta:\n    var value = 2\n    print value\nend.\n')
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {
        'textDocument': {'uri': uri, 'version': 1, 'text': source}}})
    params = {'uri': uri, 'textDocument': {'uri': uri}, 'version': 1}
    full = request('vir/semanticSnapshot', {**params, 'mode': 'full'})['result']
    assert full['complete'] is True and 'focus' not in full, full
    symbols = sorted([s for s in full['symbols'] if s['name'] == 'value'],
                     key=lambda s: s['range']['start']['line'])
    assert len(symbols) == 2 and symbols[0]['symbolId'] != symbols[1]['symbolId'], symbols
    for symbol, lines in zip(symbols, [{1, 2}, {5, 6}]):
        focus = request('vir/semanticSnapshot', {**params, 'mode': 'focus',
                                                'focusSymbolId': symbol['symbolId']})['result']
        assert focus['focus']['symbolId'] == symbol['symbolId'], focus
        assert {o['range']['start']['line'] for o in focus['focus']['path']} == lines, focus
        assert all(o['symbolId'] == symbol['symbolId'] for o in focus['focus']['path']), focus
    cached = request('vir/semanticSnapshot', params)['result']
    assert 'focus' not in cached and cached['complete'] is True, cached
    stale = request('vir/semanticSnapshot', {**params, 'version': 0})
    assert stale['error']['code'] == -32801, stale
    invalid = request('vir/semanticSnapshot', {**params, 'mode': 'focus', 'focusSymbolId': '0'})
    assert invalid['error']['code'] == -32602, invalid
    request('shutdown', {})
    send_message(p, {'jsonrpc': '2.0', 'method': 'exit'})
    assert p.wait(timeout=5) == 0
    print('PASS: compiler ID focus, shadowing, cache isolation and stale version rejection')
finally:
    if p.poll() is None:
        p.kill()
        p.wait(timeout=5)

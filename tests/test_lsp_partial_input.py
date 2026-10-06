"""A partial next frame must not prevent publishing an active analysis result."""
import json
import select
import subprocess
from test_lsp_in_ref_out import VIR_LSP, send_message, read_response
p = subprocess.Popen([str(VIR_LSP), '--stdio'], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
def frame(message):
    body = json.dumps(message).encode()
    return f'Content-Length: {len(body)}\r\n\r\n'.encode() + body
try:
    send_message(p, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'capabilities': {}}})
    read_response(p, 1)
    uri = 'file:///tmp/partial-frame-unsaved.vri'
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {
        'textDocument': {'uri': uri, 'version': 1, 'text': 'func main:\n    print 1\nend.\n'}}})
    for query_id, split in [(2, 5), (4, -5)]:
        query = frame({'jsonrpc': '2.0', 'id': query_id, 'method': 'vir/semanticSnapshot',
                       'params': {'textDocument': {'uri': uri}}})
        following = frame({'jsonrpc': '2.0', 'id': query_id + 1, 'method': 'textDocument/hover',
                           'params': {'textDocument': {'uri': uri}, 'position': {'line': 1, 'character': 10}}})
        p.stdin.write(query + following[:split])
        p.stdin.flush()
        assert select.select([p.stdout], [], [], 5)[0], 'Analysis stalled on partial incoming frame'
        assert read_response(p, query_id)['result']['documentVersion'] == 1
        p.stdin.write(following[split:])
        p.stdin.flush()
        assert 'result' in read_response(p, query_id + 1)
    send_message(p, {'jsonrpc': '2.0', 'id': 6, 'method': 'shutdown'})
    read_response(p, 6)
    send_message(p, {'jsonrpc': '2.0', 'method': 'exit'})
    assert p.wait(timeout=5) == 0
    print('PASS: active analysis publishes during partial header and partial body')
finally:
    if p.poll() is None:
        p.kill()
        p.wait(timeout=5)

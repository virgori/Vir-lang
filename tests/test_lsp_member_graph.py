"""Member occurrences are bound to the receiver's resolved entity declaration."""
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
def at(uri, line, col):
    return {'textDocument': {'uri': uri}, 'position': {'line': line, 'character': col}}
try:
    request('initialize', {'capabilities': {'workspace': {'workspaceEdit': {'documentChanges': True}}}})
    uri = 'file:///tmp/member-graph-unsaved.vri'
    source = ('entity Box:\n    value: int\nend.\n'
              'entity Other:\n    value: int\nend.\n'
              'func main:\n    var box = Box(value: 1)\n'
              '    var other = Other(value: 2)\n    print box.value\n'
              '    print other.value\n    box.value = 3\nend.\n')
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {
        'textDocument': {'uri': uri, 'version': 4, 'text': source}}})
    for line, col, declaration in [(9, 15, 1), (10, 17, 4), (11, 9, 1), (7, 19, 1), (8, 23, 4)]:
        definition = request('textDocument/definition', at(uri, line, col))['result']
        assert definition['range']['start'] == {'line': declaration, 'character': 4}, definition
    refs = request('textDocument/references', {**at(uri, 1, 6), 'context': {'includeDeclaration': True}})['result']
    assert {r['range']['start']['line'] for r in refs} == {1, 7, 9, 11}, refs
    edits = request('textDocument/rename', {**at(uri, 9, 15), 'newName': 'renamedValue'})['result']['documentChanges'][0]['edits']
    assert {e['range']['start']['line'] for e in edits} == {1, 7, 9, 11}, edits
    assert all(e['newText'] == 'renamedValue' for e in edits)
    snapshot = request('vir/semanticSnapshot', {'textDocument': {'uri': uri}})['result']
    fields = [s for s in snapshot['symbols'] if s['name'] == 'value']
    assert len(fields) == 2 and fields[0]['symbolId'] != fields[1]['symbolId'], fields
    assert all(s['type'] == 'int' for s in fields), fields
    method_uri = 'file:///tmp/method-local-graph.vri'
    method_source = ('entity Counter:\n    value: int\n'
                     '    func add(delta: int) -> int:\n'
                     '        let total = this.value + delta\n'
                     '        out total\n    end.\nend.\n'
                     'func main:\n    var item = Counter(value: 2)\n'
                     '    print item.add(3)\nend.\n')
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {
        'textDocument': {'uri': method_uri, 'version': 5, 'text': method_source}}})
    method_def = request('textDocument/definition', at(method_uri, 9, 16))['result']
    assert method_def['range']['start'] == {'line': 2, 'character': 9}, method_def
    delta_def = request('textDocument/definition', at(method_uri, 3, 35))['result']
    assert delta_def['range']['start'] == {'line': 2, 'character': 13}, delta_def
    total_def = request('textDocument/definition', at(method_uri, 4, 13))['result']
    assert total_def['range']['start'] == {'line': 3, 'character': 12}, total_def
    local_edits = request('textDocument/rename', {**at(method_uri, 4, 13), 'newName': 'sum'})['result']['documentChanges'][0]['edits']
    assert {e['range']['start']['line'] for e in local_edits} == {3, 4}, local_edits
    request('shutdown', {})
    send_message(p, {'jsonrpc': '2.0', 'method': 'exit'})
    assert p.wait(timeout=5) == 0
    print('PASS: receiver-specific field definition, initializer/write references and atomic rename')
finally:
    if p.poll() is None:
        p.kill()
        p.wait(timeout=5)

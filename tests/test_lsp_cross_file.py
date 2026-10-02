"""Compiler module resolver sees unsaved dependency buffers and source origins."""
import subprocess
from test_lsp_in_ref_out import VIR_LSP, send_message, read_response
p = subprocess.Popen([str(VIR_LSP), '--stdio'], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
notifications = []
ident = 0
def request(method, params):
    global ident
    ident += 1
    send_message(p, {'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params})
    return read_response(p, ident, notifications)
def open_doc(uri, text, version):
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen',
                    'params': {'textDocument': {'uri': uri, 'text': text, 'version': version}}})
def at(uri, line, column):
    return {'textDocument': {'uri': uri}, 'position': {'line': line, 'character': column}}
try:
    request('initialize', {'capabilities': {'workspace': {'workspaceEdit': {'documentChanges': True}}}})
    dependency = 'file:///tmp/vir-lsp-unsaved-workspace/helper.vri'
    root = 'file:///tmp/vir-lsp-unsaved-workspace/main.vri'
    open_doc(dependency, 'func helper(value: int) -> int:\n    out value + 1\nend.\n', 7)
    line = '    var label = "😀"; print helper(4)'
    open_doc(root, 'include helper\nfunc main:\n' + line + '\nend.\n', 3)
    column = len(line[:line.index('helper')].encode('utf-16-le')) // 2
    definition = request('textDocument/definition', at(root, 2, column))
    assert definition.get('result', {}).get('uri') == dependency, definition
    assert definition['result']['range']['start'] == {'line': 0, 'character': 5}, definition
    references = request('textDocument/references', {**at(root, 2, column), 'context': {'includeDeclaration': True}})['result']
    assert {r['uri'] for r in references} == {root, dependency}, references
    assert any(r['uri'] == root and r['range']['start']['character'] == column for r in references), references
    snapshot = request('vir/semanticSnapshot', {'textDocument': {'uri': root}})['result']
    helper = next(s for s in snapshot['symbols'] if s['name'] == 'helper')
    assert helper['uri'] == dependency, helper
    occurrences = [o for o in snapshot['occurrences'] if o['symbolId'] == helper['symbolId']]
    assert {o['uri'] for o in occurrences} == {root, dependency}, occurrences
    rename = request('textDocument/rename', {**at(root, 2, column), 'newName': 'renamedHelper'})['result']
    documents = {d['textDocument']['uri']: d for d in rename['documentChanges']}
    assert set(documents) == {root, dependency}, rename
    assert documents[root]['textDocument']['version'] == 3
    assert documents[dependency]['textDocument']['version'] == 7
    assert sum(len(d['edits']) for d in documents.values()) == 2
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didChange', 'params': {
        'textDocument': {'uri': dependency, 'version': 8},
        'contentChanges': [{'text': '\nfunc helper(value: int) -> int:\n    out value + 2\nend.\n'}]}})
    changed = request('textDocument/definition', at(root, 2, column))['result']
    assert changed['range']['start']['line'] == 1, changed
    next_snapshot = request('vir/semanticSnapshot', {'textDocument': {'uri': root}})['result']
    assert next_snapshot['analysisId'] != snapshot['analysisId']
    request('shutdown', {})
    send_message(p, {'jsonrpc': '2.0', 'method': 'exit'})
    assert p.wait(timeout=5) == 0
    print('PASS: unsaved cross-file definition, references, rename, Unicode and dependency invalidation')
finally:
    if p.poll() is None:
        p.kill()
        p.wait(timeout=5)

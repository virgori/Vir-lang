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
    open_doc(dependency, 'func helper(value: int) -> int:\n    out value + 1\nend.\nexport helper\n', 7)
    import_line = 'import helper from helper as aliasedHelper'
    open_doc(root, import_line + '\nfunc main:\n    print aliasedHelper(4)\nend.\n', 3)
    alias_column = import_line.index('aliasedHelper')
    definition = request('textDocument/definition', at(root, 2, 13))['result']
    assert definition['uri'] == root and definition['range']['start'] == {'line': 0, 'character': alias_column}, definition
    references = request('textDocument/references', {**at(root, 2, 13), 'context': {'includeDeclaration': True}})['result']
    assert len(references) == 2 and all(r['uri'] == root for r in references), references
    renamed = request('textDocument/rename', {**at(root, 2, 13), 'newName': 'newAlias'})['result']['documentChanges']
    assert len(renamed) == 1 and renamed[0]['textDocument'] == {'uri': root, 'version': 3}, renamed
    assert {e['range']['start']['line'] for e in renamed[0]['edits']} == {0, 2}, renamed
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didChange', 'params': {
        'textDocument': {'uri': root, 'version': 4},
        'contentChanges': [{'text': 'import helper from helper\nfunc main:\n    print helper(4)\nend.\n'}]}})
    definition = request('textDocument/definition', at(root, 2, 10))['result']
    assert definition['uri'] == dependency and definition['range']['start'] == {'line': 0, 'character': 5}, definition
    references = request('textDocument/references', {**at(root, 2, 10), 'context': {'includeDeclaration': True}})['result']
    assert {r['uri'] for r in references} == {root, dependency}, references
    snapshot = request('vir/semanticSnapshot', {'textDocument': {'uri': root}})['result']
    assert snapshot['complete'] is True, snapshot
    normal_rename = request('textDocument/rename', {**at(root, 2, 10), 'newName': 'renamedHelper'})['result']['documentChanges']
    documents = {change['textDocument']['uri']: change for change in normal_rename}
    assert set(documents) == {root, dependency}, normal_rename
    assert documents[root]['textDocument']['version'] == 4 and documents[dependency]['textDocument']['version'] == 7, normal_rename
    assert sum(len(change['edits']) for change in documents.values()) == 3, normal_rename
    request('shutdown', {})
    send_message(p, {'jsonrpc': '2.0', 'method': 'exit'})
    assert p.wait(timeout=5) == 0
    print('PASS: compiler import aliases and direct imports have complete definition, references, snapshot and atomic rename coverage')
finally:
    if p.poll() is None:
        p.kill()
        p.wait(timeout=5)

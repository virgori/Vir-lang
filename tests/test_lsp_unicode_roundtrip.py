"""Physical URI/UTF-16 ranges and versioned rename edits survive re-analysis."""
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

def at(uri, line, character):
    return {'textDocument': {'uri': uri}, 'position': {'line': line, 'character': character}}

def utf16(text):
    return len(text.encode('utf-16-le')) // 2

def apply_edit(source, edit):
    # LSP positions count UTF-16 code units; retain CRLF and tab bytes exactly.
    lines = source.splitlines(keepends=True)
    start, end = edit['range']['start'], edit['range']['end']
    assert start['line'] == end['line']
    line = lines[start['line']]
    encoded = line.encode('utf-16-le')
    lines[start['line']] = (encoded[:start['character'] * 2].decode('utf-16-le')
                           + edit['newText']
                           + encoded[end['character'] * 2:].decode('utf-16-le'))
    return ''.join(lines)

try:
    request('initialize', {'capabilities': {'workspace': {'workspaceEdit': {'documentChanges': True}}}})
    uri = 'file:///tmp/vir%20roundtrip-e%CC%81-%F0%9F%98%80.vri'
    line = '\tvar label = "e\u0301😀"; var value = 1; print value'
    source = 'func main:\r\n' + line + '\r\nend.\r\n'
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {
        'textDocument': {'uri': uri, 'version': 7, 'text': source}}})
    declaration = utf16(line[:line.index('value')])
    use = utf16(line[:line.rindex('value')])
    before = request('vir/semanticSnapshot', {'textDocument': {'uri': uri}})['result']
    assert before['complete'], before
    definition = request('textDocument/definition', at(uri, 1, use))['result']
    assert definition == {'uri': uri, 'range': {'start': {'line': 1, 'character': declaration},
                                               'end': {'line': 1, 'character': declaration + 5}}}, definition
    renamed = request('textDocument/rename', {**at(uri, 1, use), 'newName': 'renamedValue'})['result']['documentChanges']
    assert len(renamed) == 1 and renamed[0]['textDocument'] == {'uri': uri, 'version': 7}, renamed
    assert len(renamed[0]['edits']) == 2, renamed
    for edit in sorted(renamed[0]['edits'], key=lambda e: (e['range']['start']['line'], e['range']['start']['character']), reverse=True):
        source = apply_edit(source, edit)
    assert 'var value' not in source and 'print value' not in source
    assert '\r\n' in source and '\t' in source and 'e\u0301😀' in source
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didChange', 'params': {
        'textDocument': {'uri': uri, 'version': 8}, 'contentChanges': [{'text': source}]}})
    after = request('vir/semanticSnapshot', {'textDocument': {'uri': uri}})['result']
    assert after['complete'] and after['documentVersion'] == 8 and after['analysisId'] != before['analysisId'], after
    symbols = {s['name']: s for s in after['symbols']}
    assert 'renamedValue' in symbols and 'value' not in symbols and 'label' in symbols, symbols
    assert symbols['label']['type'] == 'string' and symbols['renamedValue']['type'] == 'int', symbols
    binding_id = symbols['renamedValue']['symbolId']
    uses = [o for o in after['occurrences'] if o['symbolId'] == binding_id]
    assert len(uses) == 2 and all(o['uri'] == uri for o in uses), uses
    assert all(d['documentVersion'] == 8 for d in after['dependencies'] if d['uri'] == uri), after
    request('shutdown', {})
    send_message(p, {'jsonrpc': '2.0', 'method': 'exit'})
    assert p.wait(timeout=5) == 0
    print('PASS: combining/non-BMP Unicode, encoded path, CRLF/tab UTF-16 ranges, atomic rename round trip and versions')
finally:
    if p.poll() is None:
        p.kill(); p.wait(timeout=5)

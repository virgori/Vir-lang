#!/usr/bin/env python3
"""Regression coverage for open-buffer identity and compiler type facts."""
import subprocess
from test_lsp_in_ref_out import VIR_LSP, send_message, read_response

p = subprocess.Popen([str(VIR_LSP), '--stdio'], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
request_id = 0

def request(method, params):
    global request_id
    request_id += 1
    send_message(p, {'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
    return read_response(p, request_id)

def notify(method, params):
    send_message(p, {'jsonrpc': '2.0', 'method': method, 'params': params})

def open_document(uri, text):
    notify('textDocument/didOpen', {'textDocument': {'uri': uri, 'languageId': 'vir', 'version': 1, 'text': text}})

def position(uri, line, character):
    return {'textDocument': {'uri': uri}, 'position': {'line': line, 'character': character}}

try:
    request('initialize', {'capabilities': {'workspace': {'workspaceEdit': {'documentChanges': True}}}})
    a, b = 'file:///tmp/vir-review-a.vri', 'file:///tmp/vir-review-b.vri'
    open_document(a, 'func alpha:\n    var valueA = 10\n    out valueA\nend.\n')
    open_document(b, 'func beta:\n    var valueB = "hello"\n    valueB.\nend.\n')
    for uri, name, expected_type in [(a, 'valueA', 'int'), (b, 'valueB', 'string'), (a, 'valueA', 'int')]:
        hover = request('textDocument/hover', position(uri, 1, 9))['result']['contents']['value']
        assert name in hover and f'`{expected_type}`' in hover, hover
    rename = request('textDocument/rename', {**position(a, 1, 9), 'newName': 'renamedA'})['result']['documentChanges']
    assert len(rename) == 1 and rename[0]['textDocument'] == {'uri': a, 'version': 1}, rename
    completion = request('textDocument/completion', position(b, 2, 11))['result']
    assert completion['items'] == [] and completion['isIncomplete'] is True, completion
    snapshot = request('vir/semanticSnapshot', {'textDocument': {'uri': a}})['result']
    assert snapshot['uri'] == a and snapshot['documentVersion'] == 1
    assert snapshot['complete'] is True and 'unavailableReason' not in snapshot
    for occurrence in snapshot['occurrences']:
        assert not {'virMoved', 'virLastUse'} & set(occurrence['states']), occurrence
    notify('textDocument/didChange', {'textDocument': {'uri': a, 'version': 2}, 'contentChanges': [{'text': 'func alpha:\n    var changedA = 20\n    out changedA\nend.\n'}]})
    assert 'changedA' in request('textDocument/hover', position(a, 1, 9))['result']['contents']['value']
    notify('textDocument/didChange', {'textDocument': {'uri': a, 'version': 1}, 'contentChanges': [{'text': 'func stale:\nend.\n'}]})
    assert request('vir/semanticSnapshot', {'textDocument': {'uri': a}})['result']['documentVersion'] == 2
    notify('textDocument/didClose', {'textDocument': {'uri': a}})
    assert 'error' in request('textDocument/hover', position(a, 1, 9))
    assert 'valueB' in request('textDocument/hover', position(b, 1, 9))['result']['contents']['value']
    empty_uri = 'file:///tmp/vir-review-empty.vri'
    open_document(empty_uri, '')
    empty = request('vir/semanticSnapshot', {'textDocument': {'uri': empty_uri}})['result']
    assert empty['uri'] == empty_uri and empty['occurrences'] == [], empty
    assert request('textDocument/hover', position(empty_uri, 1, 17))['result'] is None
    request('shutdown', {})
    notify('exit', {})
    p.wait(timeout=5)
    assert p.returncode == 0
    print('PASS: document isolation, changes, stale versions, close, empty buffers and compiler type facts')
finally:
    if p.poll() is None:
        p.kill()
        p.wait()

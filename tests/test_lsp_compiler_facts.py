#!/usr/bin/env python3
"""Exercise actual compiler resolver, inference and borrow facts over unsaved buffers."""
import subprocess
from test_lsp_in_ref_out import VIR_LSP, send_message, read_response

p = subprocess.Popen([str(VIR_LSP), '--stdio'], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
request_id = 0
notifications = []

def request(method, params):
    global request_id
    request_id += 1
    send_message(p, {'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
    return read_response(p, request_id, notifications)

def open_buffer(uri, text):
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen',
                    'params': {'textDocument': {'uri': uri, 'version': 1,
                                               'languageId': 'vir', 'text': text}}})

def position(uri, line, character):
    return {'textDocument': {'uri': uri}, 'position': {'line': line, 'character': character}}

try:
    request('initialize', {'capabilities': {'workspace': {'workspaceEdit': {'documentChanges': True}}}})
    uri = 'file:///tmp/compiler-facts-unsaved.vri'
    open_buffer(uri, 'func main:\n    var text = "hello"\n    var ratio = 1.25\n    var flag = true\n    print text\nend.\n')
    for line, name, kind in [(1, 'text', 'string'), (2, 'ratio', 'float'), (3, 'flag', 'bool')]:
        hover = request('textDocument/hover', position(uri, line, 9))['result']['contents']['value']
        assert name in hover and f'`{kind}`' in hover, hover
        assert 'Compiler resolver/type snapshot' in hover
    for line, character, kind in [(1, 17, 'string'), (2, 17, 'float'), (3, 15, 'bool')]:
        literal = request('textDocument/hover', position(uri, line, character))['result']['contents']['value']
        assert literal == f'Compiler expression type: `{kind}`', literal
    snap = request('vir/semanticSnapshot', {'textDocument': {'uri': uri}})['result']
    assert snap['analysisId'].startswith('compiler-buffer-')
    assert snap['complete'] is True, snap
    assert all(o['role'] in {'declaration', 'read', 'write', 'call', 'type-use'} for o in snap['occurrences'])
    assert {'string', 'float', 'bool'} <= {e['displayType'] for e in snap['expressions']}, snap['expressions']
    assert all(e['uri'] == uri and isinstance(e['expressionId'], str)
               and isinstance(e['typeId'], str) for e in snap['expressions'])
    symbol = next(s for s in snap['symbols'] if s['name'] == 'text')
    occurrences = [o for o in snap['occurrences'] if o['symbolId'] == symbol['symbolId']]
    assert [o['range']['start']['line'] for o in occurrences] == [1, 4], occurrences
    assert all('virLastUse' not in o['states'] for o in occurrences)
    invalid_name = request('textDocument/rename', {**position(uri, 1, 9), 'newName': 'bad-name'})
    assert invalid_name.get('error', {}).get('code') == -32602, invalid_name

    expression_uri = 'file:///tmp/compiler-nested-expression-unsaved.vri'
    expression_line = '    var answer = 1 + 2 * 3 == 7'
    open_buffer(expression_uri, 'func main:\n' + expression_line + '\n    print answer\nend.\n')
    expression_snapshot = request('vir/semanticSnapshot', {'textDocument': {'uri': expression_uri}})['result']
    assert expression_snapshot['complete'], expression_snapshot
    for operator, display_type in [('+', 'int'), ('*', 'int'), ('==', 'bool')]:
        response = request('textDocument/hover', position(expression_uri, 1, expression_line.index(operator)))
        assert response['result']['contents']['value'] == f'Compiler expression type: `{display_type}`', response
    actual_ranges = {(e['range']['start']['character'], e['range']['end']['character'], e['displayType'])
                     for e in expression_snapshot['expressions'] if e['range']['start']['line'] == 1}
    # Pratt parses multiplication first, then addition, then comparison.
    assert {(21, 26, 'int'), (17, 26, 'int'), (17, 31, 'bool')} <= actual_ranges, actual_ranges

    member_uri = 'file:///tmp/compiler-members-unsaved.vri'
    open_buffer(member_uri, 'entity Box:\n    value: int\nend.\nentity Other:\n    unrelated: int\nend.\nfunc main:\n    var item: Box = Box(value: 1)\n    item.\nend.\n')
    completion = request('textDocument/completion', position(member_uri, 8, 9))['result']
    assert {i['label'] for i in completion['items']} == {'value'}, completion
    assert completion['isIncomplete'] is True
    incomplete_uri = 'file:///tmp/compiler-incomplete-unsaved.vri'
    open_buffer(incomplete_uri, 'func main:\n    var value = 1\n    missing(value)\nend.\n')
    rejected = request('textDocument/rename', {**position(incomplete_uri, 1, 9), 'newName': 'renamed'})
    assert 'incomplete' in rejected.get('error', {}).get('message', ''), rejected

    move_uri = 'file:///tmp/compiler-move-unsaved.vri'
    open_buffer(move_uri, 'func consume(values: [int]):\n    print values[0]\nend.\nfunc main:\n    var values = [8, 13]\n    consume(values)\n    print values[0]\nend.\n')
    moved = request('vir/semanticSnapshot', {'textDocument': {'uri': move_uri}})['result']
    uses = [o for o in moved['occurrences'] if o['range']['start']['line'] == 6]
    assert any('virMoved' in o['states'] for o in uses), uses
    diagnostics = [n for n in notifications if n.get('method') == 'textDocument/publishDiagnostics'
                   and n.get('params', {}).get('uri') == move_uri]
    assert diagnostics and any(d['code'] == 'E5001' for d in diagnostics[-1]['params']['diagnostics']), diagnostics
    assert moved['complete'] is False
    moved_facts = [f for f in moved['checkerFacts'] if f['range']['start']['line'] == 6]
    assert any(f['stateBefore'] == 4 and f['stateAfter'] == 4
               and f['moveOrigin'] == {'uri': move_uri, 'line': 5} for f in moved_facts), moved_facts
    transitions = [f for f in moved['checkerFacts'] if f['range']['start']['line'] == 5]
    assert any(f['stateBefore'] == 2 and f['stateAfter'] == 4 for f in transitions), transitions
    # The checker releases holder's named borrow after inspect(holder).
    # This is positive evidence of NLL, not a last-textual-occurrence rule.
    nll_uri = 'file:///tmp/compiler-nll-unsaved.vri'
    open_buffer(nll_uri, 'entity Box:\n    val: int\nend.\nfunc consume(b: Box): print b.val end.\nfunc inspect(b: &Box): print b.val end.\nfunc main:\n    var owner = Box(val: 1)\n    var holder = &owner\n    inspect(holder)\n    consume(owner)\nend.\n')
    nll = request('vir/semanticSnapshot', {'textDocument': {'uri': nll_uri}})['result']
    holder = next(s for s in nll['symbols'] if s['name'] == 'holder')
    holder_uses = [o for o in nll['occurrences'] if o['symbolId'] == holder['symbolId']]
    assert any(o['range']['start']['line'] == 8 and 'virLastUse' in o['states']
               and 'virBorrowed' in o['states'] for o in holder_uses), holder_uses
    assert all('virLastUse' not in o['states'] for o in nll['occurrences']
               if o['symbolId'] != holder['symbolId']), nll['occurrences']

    invalid_uri = 'file:///tmp/compiler-out-parens-invalid.vri'
    open_buffer(invalid_uri, 'func invalid(out destination: int):\n    destination = 1\nend.\n')
    request('vir/semanticSnapshot', {'textDocument': {'uri': invalid_uri}})
    invalid_diagnostics = [n for n in notifications if n.get('method') == 'textDocument/publishDiagnostics'
                           and n.get('params', {}).get('uri') == invalid_uri]
    assert any(d['code'] == 'E3045' for d in invalid_diagnostics[-1]['params']['diagnostics']), invalid_diagnostics

    unicode_uri = 'file:///tmp/compiler-unicode-unsaved.vri'
    unicode_line = '    var message = "😀"; var value = 1; print value'
    open_buffer(unicode_uri, 'func main:\n' + unicode_line + '\nend.\n')
    declaration_col = len(unicode_line[:unicode_line.index('value')].encode('utf-16-le')) // 2
    reference_col = len(unicode_line[:unicode_line.rindex('value')].encode('utf-16-le')) // 2
    definition = request('textDocument/definition', position(unicode_uri, 1, reference_col))['result']
    assert definition['uri'] == unicode_uri and definition['range']['start'] == {'line': 1, 'character': declaration_col}, definition
    edits = request('textDocument/rename', {**position(unicode_uri, 1, reference_col), 'newName': 'renamedValue'})['result']['documentChanges'][0]['edits']
    assert [e['range']['start']['character'] for e in edits] == [declaration_col, reference_col], edits

    many_uri = 'file:///tmp/compiler-many-references.vri'
    open_buffer(many_uri, 'func main:\n    var counter = 0\n' + '    print counter\n' * 100 + 'end.\n')
    many_references = request('textDocument/references', {**position(many_uri, 1, 9), 'context': {'includeDeclaration': True}})['result']
    assert len(many_references) == 101, len(many_references)
    many_edits = request('textDocument/rename', {**position(many_uri, 1, 9), 'newName': 'renamedCounter'})['result']['documentChanges'][0]['edits']
    assert len(many_edits) == 101, len(many_edits)

    large_uri = 'file:///tmp/compiler-many-completions.vri'
    names = ['value_' + str(i) + '_' + 'x' * 180 for i in range(50)]
    open_buffer(large_uri, 'func main:\n' + ''.join(f'    var {name} = {i}\n' for i, name in enumerate(names)) + '    print 1\nend.\n')
    large_completion = request('textDocument/completion', position(large_uri, 51, 4))['result']
    labels = {item['label'] for item in large_completion['items']}
    assert set(names) <= labels, set(names) - labels

    oversized_uri = 'file:///tmp/compiler-oversized-graph.vri'
    open_buffer(oversized_uri, 'func main:\n' + ''.join(f'    var value{i} = {i}\n' for i in range(510)) + 'end.\n')
    oversized = request('vir/semanticSnapshot', {'textDocument': {'uri': oversized_uri}})['result']
    assert oversized['complete'] is False
    rejected_large = request('textDocument/rename', {**position(oversized_uri, 1, 9), 'newName': 'renamed'})
    assert 'incomplete' in rejected_large.get('error', {}).get('message', ''), rejected_large

    ufcs_uri = 'file:///tmp/compiler-ufcs-rename-coverage.vri'
    open_buffer(ufcs_uri, 'entity Box:\n    value: int\nend.\nfunc inspect(this: Box):\n    print this.value\nend.\nfunc main:\n    var item = Box(value: 1)\n    item.inspect()\nend.\n')
    ufcs_definition = request('textDocument/definition', position(ufcs_uri, 8, 11))['result']
    assert ufcs_definition['range']['start'] == {'line': 3, 'character': 5}, ufcs_definition
    ufcs_references = request('textDocument/references', {**position(ufcs_uri, 3, 7),
                              'context': {'includeDeclaration': True}})['result']
    assert {r['range']['start']['line'] for r in ufcs_references} == {3, 8}, ufcs_references
    prepared = request('textDocument/prepareRename', position(ufcs_uri, 8, 11))
    assert 'result' in prepared and prepared['result'] is not None, prepared
    renamed = request('textDocument/rename', {**position(ufcs_uri, 3, 7),
                                            'newName': 'renamedInspect'})
    assert len(renamed['result']['documentChanges'][0]['edits']) == 2, renamed

    # Analysis generations must change across edits and close/reopen, even
    # when the URI and document version are reused by the editor.
    identity_uri = 'file:///tmp/compiler-analysis-generation.vri'
    identity_source = 'func main:\n    var value = 1\n    print value\nend.\n'
    open_buffer(identity_uri, identity_source)
    first = request('vir/semanticSnapshot', {'textDocument': {'uri': identity_uri}})['result']
    repeated = request('vir/semanticSnapshot', {'textDocument': {'uri': identity_uri}})['result']
    assert first['analysisId'] == repeated['analysisId']
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didChange',
                    'params': {'textDocument': {'uri': identity_uri, 'version': 2},
                               'contentChanges': [{'text': identity_source.replace('1', '2')}]}})
    changed = request('vir/semanticSnapshot', {'textDocument': {'uri': identity_uri}})['result']
    assert changed['analysisId'] != first['analysisId']
    assert changed['documentVersion'] == 2
    versioned = request('textDocument/rename', {**position(identity_uri, 1, 9),
                                              'newName': 'updatedValue'})['result']
    assert 'changes' not in versioned
    assert versioned['documentChanges'][0]['textDocument'] == {'uri': identity_uri, 'version': 2}
    assert len(versioned['documentChanges'][0]['edits']) == 2
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didClose',
                    'params': {'textDocument': {'uri': identity_uri}}})
    open_buffer(identity_uri, identity_source)
    reopened = request('vir/semanticSnapshot', {'textDocument': {'uri': identity_uri}})['result']
    assert reopened['analysisId'] not in {first['analysisId'], changed['analysisId']}

    for index, (line, marker, message) in enumerate([
        ('    print `', '`', 'unexpected character'),
        ('    var text = "😀"; print Foo::Bar', '::', "invalid token '::'"),
        ('    var text = "unfinished', None, 'unterminated string literal'),
        ('    var text = "$(value', None, 'unterminated expression'),
    ]):
        lex_uri = f'file:///tmp/compiler-lexer-error-{index}.vri'
        source = 'func main:\n' + line
        open_buffer(lex_uri, source)
        snapshot = request('vir/semanticSnapshot', {'textDocument': {'uri': lex_uri}})['result']
        published = [n['params']['diagnostics'] for n in notifications
                     if n.get('method') == 'textDocument/publishDiagnostics'
                     and n['params']['uri'] == lex_uri][-1]
        matching = [d for d in published if message in d['message']]
        assert matching, (source, published)
        diagnostic = matching[0]
        offset = line.index(marker) if marker else len(line)
        expected_column = len(line[:offset].encode('utf-16-le')) // 2
        assert diagnostic['range']['start'] == {'line': 1, 'character': expected_column}, diagnostic
        assert snapshot['complete'] is False
        assert snapshot['analysisId'].startswith('fallback-buffer-')

    request('shutdown', {})
    send_message(p, {'jsonrpc': '2.0', 'method': 'exit', 'params': {}})
    p.wait(timeout=5)
    assert p.returncode == 0
    p = subprocess.Popen([str(VIR_LSP), '--stdio'], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    request('initialize', {'capabilities': {}})
    open_buffer(identity_uri, identity_source)
    restarted = request('vir/semanticSnapshot', {'textDocument': {'uri': identity_uri}})['result']
    assert restarted['analysisId'] not in {first['analysisId'], changed['analysisId'], reopened['analysisId']}
    unsupported = request('textDocument/rename', {**position(identity_uri, 1, 9), 'newName': 'newValue'})
    assert 'versioned documentChanges' in unsupported.get('error', {}).get('message', ''), unsupported
    request('shutdown', {})
    send_message(p, {'jsonrpc': '2.0', 'method': 'exit', 'params': {}})
    p.wait(timeout=5)
    assert p.returncode == 0
    print('PASS: compiler identity, string/float/bool inference, entity members, rename validation actual move diagnostics and checker-proven NLL')
finally:
    if p.poll() is None:
        p.kill()
        p.wait()

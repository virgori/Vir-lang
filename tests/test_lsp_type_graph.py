"""Named type identity and complete annotation/constructor/export occurrences."""
import subprocess
from test_lsp_in_ref_out import VIR_LSP, send_message, read_response
p = subprocess.Popen([str(VIR_LSP), '--stdio'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
notifications = []
ident = 0
def request(method, params):
    global ident
    ident += 1
    send_message(p, {'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params})
    return read_response(p, ident, notifications)
def at(uri, line, column):
    return {'textDocument': {'uri': uri}, 'position': {'line': line, 'character': column}}
try:
    request('initialize', {'capabilities': {'workspace': {'workspaceEdit': {'documentChanges': True}}}})
    uri = 'file:///tmp/named-type-graph.vri'
    source = ('entity Box:\n    value: int\nend.\n'
              'entity Other:\n    value: int\nend.\n'
              'func use(item: Box) -> int:\n    out item.value\nend.\n'
              'func main:\n    var box: Box = Box(value: 1)\n'
              '    var other = Other(value: 2)\n    print use(box)\nend.\n'
              'export use\n')
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {'textDocument': {'uri': uri, 'text': source, 'version': 4}}})
    snapshot = request('vir/semanticSnapshot', {'textDocument': {'uri': uri}})['result']
    assert snapshot['complete'], snapshot
    symbols = {s['name']: s for s in snapshot['symbols'] if s['name'] != 'value'}
    box_id = symbols['Box']['symbolId']
    assert symbols['box']['typeId'] == symbols['item']['typeId'] == 'symbol:' + box_id, symbols
    assert symbols['other']['typeId'] == 'symbol:' + symbols['Other']['symbolId']
    assert symbols['other']['typeId'] != symbols['box']['typeId']
    uses = [o for o in snapshot['occurrences'] if o['symbolId'] == box_id]
    assert {(o['range']['start']['line'], o['range']['start']['character']) for o in uses} == {(0, 7), (6, 15), (10, 13), (10, 19)}, uses
    assert all(o['role'] == 'type-use' for o in uses if o['range']['start']['line'] != 0)
    edits = request('textDocument/rename', {**at(uri, 0, 8), 'newName': 'Crate'})['result']['documentChanges'][0]['edits']
    assert len(edits) == 4, edits
    assert request('textDocument/definition', at(uri, 6, 15))['result']['range']['start'] == {'line': 0, 'character': 7}
    refs = request('textDocument/references', {**at(uri, 6, 6), 'context': {'includeDeclaration': True}})['result']
    assert {r['range']['start']['line'] for r in refs} == {6, 12, 14}, refs
    fields = [s for s in snapshot['symbols'] if s['name'] == 'value']
    assert {s['containerId'] for s in fields} == {box_id, symbols['Other']['symbolId']}
    enum_uri = 'file:///tmp/enum-graph-safety.vri'
    enum_source = 'enum Shade:\n    Blue\nend.\nfunc main:\n    let shade = Shade.Blue()\n    print shade\nend.\n'
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {
        'textDocument': {'uri': enum_uri, 'text': enum_source, 'version': 1}}})
    enum_snapshot = request('vir/semanticSnapshot', {'textDocument': {'uri': enum_uri}})['result']
    assert enum_snapshot['complete'], enum_snapshot
    enum_symbols = {s['name']: s for s in enum_snapshot['symbols']}
    enum_id = enum_symbols['Shade']['symbolId']
    variant_id = enum_symbols['Blue']['symbolId']
    assert enum_symbols['Blue']['containerId'] == enum_id, enum_symbols
    assert enum_symbols['shade']['typeId'] == 'symbol:' + enum_id, enum_symbols
    assert len([o for o in enum_snapshot['occurrences'] if o['symbolId'] == enum_id]) == 2, enum_snapshot
    enum_edits = request('textDocument/rename', {**at(enum_uri, 0, 6), 'newName': 'Color'})['result']['documentChanges'][0]['edits']
    assert len(enum_edits) == 2, enum_edits
    variant_edits = request('textDocument/rename', {**at(enum_uri, 1, 5), 'newName': 'Azure'})['result']['documentChanges'][0]['edits']
    assert len(variant_edits) == 2, variant_edits
    assert request('textDocument/definition', at(enum_uri, 4, 23))['result']['range']['start'] == {'line': 1, 'character': 4}
    unqualified_uri = 'file:///tmp/enum-unqualified-type-graph.vri'
    unqualified_source = 'enum Tone:\n    Quiet\nend.\nfunc main:\n    let tone = Quiet()\n    print tone\nend.\n'
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {
        'textDocument': {'uri': unqualified_uri, 'text': unqualified_source, 'version': 1}}})
    unqualified = request('vir/semanticSnapshot', {'textDocument': {'uri': unqualified_uri}})['result']
    assert unqualified['complete'], unqualified
    tone_symbol = next(s for s in unqualified['symbols'] if s['name'] == 'Tone')
    constructor_expression = next(e for e in unqualified['expressions']
                                  if e['range']['start'] == {'line': 4, 'character': 15})
    assert constructor_expression['typeId'] == 'symbol:' + tone_symbol['symbolId'], constructor_expression
    assert constructor_expression['displayType'] == 'Tone', constructor_expression
    collision_uri = 'file:///tmp/enum-qualified-collision-graph.vri'
    collision_source = ('enum First:\n    Value(x: int)\nend.\n'
                        'enum Second:\n    Value(x: int)\nend.\n'
                        'func main:\n    let v1 = First.Value(10)\n    let v2 = Second.Value(20)\n'
                        '    case v1\n        First.Value(x): print(x)\n    end\n'
                        '    case v2\n        Second.Value(y): print(y)\n    end\nend.\n')
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {
        'textDocument': {'uri': collision_uri, 'text': collision_source, 'version': 2}}})
    collision = request('vir/semanticSnapshot', {'textDocument': {'uri': collision_uri}})['result']
    assert collision['complete'], collision
    variants = [s for s in collision['symbols'] if s['name'] == 'Value']
    assert len(variants) == 2 and variants[0]['symbolId'] != variants[1]['symbolId'], variants
    assert variants[0]['containerId'] != variants[1]['containerId'], variants
    for declaration_line, expected_lines in ((1, {1, 7, 10}), (4, {4, 8, 13})):
        changed = request('textDocument/rename', {**at(collision_uri, declaration_line, 5), 'newName': 'Item'})['result']['documentChanges'][0]['edits']
        assert {e['range']['start']['line'] for e in changed} == expected_lines, changed
    for form, declaration, type_name in (
        ('packed', 'packed entity Packet:\n    value: u8\nend.\n', 'Packet'),
        ('register', 'register Flags: u16\n    LOW: 0..2\nend.\n', 'Flags'),
    ):
        structured_uri = 'file:///tmp/' + form + '-type-graph.vri'
        body = ('func main:\n    var item: Packet = Packet(value: 1)\n    print item.value\nend.\n'
                if form == 'packed' else
                'func main:\n    var item: Flags = 0\n    item.LOW = 7\n    print item.LOW\nend.\n')
        send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {
            'textDocument': {'uri': structured_uri, 'text': declaration + body, 'version': 3}}})
        structured = request('vir/semanticSnapshot', {'textDocument': {'uri': structured_uri}})['result']
        assert structured['complete'], structured
        structured_symbols = {s['name']: s for s in structured['symbols']}
        assert structured_symbols['item']['typeId'] == 'symbol:' + structured_symbols[type_name]['symbolId'], structured_symbols
        type_column = declaration.splitlines()[0].index(type_name)
        structured_edits = request('textDocument/rename', {**at(structured_uri, 0, type_column), 'newName': 'RenamedType'})['result']['documentChanges'][0]['edits']
        assert len(structured_edits) == (3 if form == 'packed' else 2), structured_edits

    legacy_uri = 'file:///tmp/class-alias-type-graph.vri'
    legacy_source = ('type Count = int\n'
                     'class Node:\n    value: int\nend.\n'
                     'func main:\n    var count: Count = 1\n'
                     '    var node: Node = Node(value: 2)\n'
                     '    print count\nend.\n')
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {
        'textDocument': {'uri': legacy_uri, 'text': legacy_source, 'version': 5}}})
    legacy = request('vir/semanticSnapshot', {'textDocument': {'uri': legacy_uri}})['result']
    assert legacy['complete'], legacy
    legacy_symbols = {symbol['name']: symbol for symbol in legacy['symbols']}
    assert legacy_symbols['count']['typeId'] == 'symbol:' + legacy_symbols['Count']['symbolId'], legacy_symbols
    assert legacy_symbols['node']['typeId'] == 'symbol:' + legacy_symbols['Node']['symbolId'], legacy_symbols
    alias_edits = request('textDocument/rename', {**at(legacy_uri, 0, 5), 'newName': 'Total'})['result']['documentChanges'][0]['edits']
    assert len(alias_edits) == 2, alias_edits
    class_edits = request('textDocument/rename', {**at(legacy_uri, 1, 6), 'newName': 'Cell'})['result']['documentChanges'][0]['edits']
    assert len(class_edits) == 3, class_edits

    request('shutdown', {})
    send_message(p, {'jsonrpc': '2.0', 'method': 'exit'})
    assert p.wait(timeout=5) == 0
    print('PASS: named type identity, annotation/constructor/export graph and complete atomic rename')
finally:
    if p.poll() is None:
        p.kill(); p.wait(timeout=5)

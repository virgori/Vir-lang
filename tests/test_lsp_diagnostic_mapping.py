"""CLI and LSP keep every diagnostic and agree on physical source/code/severity."""
import collections
import json
import os
from pathlib import Path
import subprocess
import tempfile
from test_lsp_in_ref_out import ROOT, VIR_LSP, send_message, read_response
compiler = Path(os.environ.get('VIRC', ROOT / 'bin/virc'))
p = subprocess.Popen([str(VIR_LSP), '--stdio'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
notifications = []
ident = 0
def request(method, params):
    global ident
    ident += 1
    send_message(p, {'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params})
    return read_response(p, ident, notifications)
def open_doc(path, source, version):
    send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {'textDocument': {'uri': path.as_uri(), 'version': version, 'text': source}}})
def compiler_diags(path):
    run = subprocess.run([str(compiler), '--json', str(path), '-o', str(path.with_suffix('.bin'))], capture_output=True, text=True, timeout=60)
    assert run.returncode != 0, run.stdout
    return json.loads(run.stdout)['diagnostics']
def latest(uri):
    values = [n['params'] for n in notifications if n.get('method') == 'textDocument/publishDiagnostics' and n['params']['uri'] == uri]
    assert values, (uri, notifications)
    return values[-1]
def utf16_column(path, line, column):
    text = Path(path).read_text().splitlines()[line - 1]
    prefix = text.encode('utf-8')[:column - 1].decode('utf-8')
    return len(prefix.encode('utf-16-le')) // 2

def compare(records, publication):
    severity = {'error': 1, 'warning': 2, 'info': 3}
    expected = collections.Counter((d['code'], d['primary_span']['start_line'] - 1, severity[d['severity']]) for d in records)
    actual = collections.Counter((d['code'], d['range']['start']['line'], d['severity']) for d in publication['diagnostics'])
    assert expected == actual, (expected, actual)
    expected_messages = collections.Counter((d['code'], d['message']) for d in records)
    actual_messages = collections.Counter((d['code'], d['message']) for d in publication['diagnostics'])
    assert expected_messages == actual_messages, (expected_messages, actual_messages)
    for record, diagnostic in zip(records, publication['diagnostics']):
        span = record['primary_span']
        expected_range = {
            'start': {'line': span['start_line'] - 1,
                      'character': utf16_column(span['file'], span['start_line'], span['start_column'])},
            'end': {'line': span['end_line'] - 1,
                    'character': utf16_column(span['file'], span['end_line'], span['end_column'])},
        }
        assert diagnostic['range'] == expected_range, (record, diagnostic)
        related = record.get('related_locations', [])
        actual_related = diagnostic.get('relatedInformation', [])
        assert len(related) == len(actual_related), (record, diagnostic)
        for location, actual_location in zip(related, actual_related):
            assert actual_location['location']['uri'] == Path(location['file']).absolute().as_uri(), (location, actual_location)
            assert actual_location['location']['range']['start'] == {
                'line': location['line'] - 1,
                'character': utf16_column(location['file'], location['line'], location['column']),
            }, (location, actual_location)
            assert actual_location['message'] == location['message'], (location, actual_location)
try:
    request('initialize', {'capabilities': {}})
    with tempfile.TemporaryDirectory(prefix='vir-diagnostic-map-') as directory:
        base = Path(directory)
        many = base / 'many.vri'
        text = 'func main:\n' + ''.join(f'    print missing{n}\n' for n in range(140)) + 'end.\n'
        many.write_text(text)
        records = compiler_diags(many)
        assert len(records) > 100, len(records)
        open_doc(many, text, 7)
        request('vir/semanticSnapshot', {'textDocument': {'uri': many.as_uri()}})
        publication = latest(many.as_uri())
        assert publication['version'] == 7
        compare(records, publication)
        dependency = base / 'helper.vri'
        root = base / 'root.vri'
        helper = 'func helper:\n    print missingHelper\nend.\n'
        main = 'include helper\nfunc main:\n    print missingMain\nend.\n'
        dependency.write_text(helper); root.write_text(main)
        records = compiler_diags(root)
        open_doc(dependency, helper, 8)
        open_doc(root, main, 9)
        request('vir/semanticSnapshot', {'textDocument': {'uri': root.as_uri()}})
        for path, version in [(dependency, 8), (root, 9)]:
            selected = [d for d in records if Path(d['primary_span']['file']).resolve() == path.resolve()]
            assert selected, (path, records)
            publication = latest(path.as_uri())
            assert publication['version'] == version
            compare(selected, publication)
        for name, text in [('syntax', 'func bad(out value: int):\nend.\n'), ('lexer', 'func main:\n    print `\nend.\n'),
                           ('unicode-lexer', 'func main:\n    print "😀"; print `\nend.\n')]:
            fixture = base / (name + '.vri'); fixture.write_text(text)
            records = compiler_diags(fixture)
            open_doc(fixture, text, 10)
            request('vir/semanticSnapshot', {'textDocument': {'uri': fixture.as_uri()}})
            compare(records, latest(fixture.as_uri()))
        repeated = base / 'repeated-syntax.vri'
        repeated_text = ''.join(f'func bad{n}(out value: int):\nend.\n' for n in range(3))
        repeated.write_text(repeated_text)
        records = compiler_diags(repeated)
        assert len(records) == 3, records
        assert {d['primary_span']['start_line'] for d in records} == {1, 3, 5}, records
        open_doc(repeated, repeated_text, 11)
        request('vir/semanticSnapshot', {'textDocument': {'uri': repeated.as_uri()}})
        compare(records, latest(repeated.as_uri()))
        borrow = base / 'borrow space.vri'
        borrow_text = (ROOT / 'tests/memory_contract/double_mut_borrow_negative.vri').read_text()
        borrow.write_text(borrow_text)
        records = compiler_diags(borrow)
        assert records[0]['related_locations'], records
        open_doc(borrow, borrow_text, 11)
        request('vir/semanticSnapshot', {'textDocument': {'uri': borrow.as_uri()}})
        compare(records, latest(borrow.as_uri()))
        stored = request('vir/diagnosticSnapshot', {'uri': borrow.as_uri()})['result']
        cli_stored = subprocess.run([str(compiler), 'show', str(borrow), '--json'],
                                    capture_output=True, text=True, timeout=10)
        assert cli_stored.returncode == 0, cli_stored.stdout + cli_stored.stderr
        assert stored == json.loads(cli_stored.stdout), (stored, cli_stored.stdout)
        for uri in ['https://example.org/main.vri', 'file://host/tmp/main.vri',
                    'file:///tmp/invalid%00.vri', 'file:///tmp/invalid%zz.vri',
                    'file:///tmp/invalid%.vri', 'file:///tmp/main.vri?other']:
            error = request('vir/diagnosticSnapshot', {'uri': uri})
            assert error.get('error', {}).get('code') == -32602, error
        send_message(p, {'jsonrpc': '2.0', 'method': 'textDocument/didChange', 'params': {
            'textDocument': {'uri': dependency.as_uri(), 'version': 12},
            'contentChanges': [{'text': 'func helper:\n    print 1\nend.\n'}]}})
        request('vir/semanticSnapshot', {'textDocument': {'uri': root.as_uri()}})
        assert latest(dependency.as_uri())['version'] == 12
        assert latest(dependency.as_uri())['diagnostics'] == []
        assert latest(root.as_uri())['diagnostics'], latest(root.as_uri())
    request('shutdown', {})
    send_message(p, {'jsonrpc': '2.0', 'method': 'exit'})
    assert p.wait(timeout=5) == 0
    print('PASS: all diagnostics above 100, repeated parser errors, cross-file primary/related ranges, UTF-16, exact code/message/severity, URI validation and stored snapshot equivalence')
finally:
    if p.poll() is None:
        p.kill(); p.wait(timeout=5)

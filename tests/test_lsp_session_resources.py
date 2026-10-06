#!/usr/bin/env python3
"""Check repeated compiler analyses reclaim memory and keep snapshot identity stable."""
import json
import subprocess
import sys

from test_lsp_in_ref_out import VIR_LSP, read_response, send_message


def measure(iterations):
    import resource
    process = subprocess.Popen([str(VIR_LSP), '--stdio'], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    sequence = 0
    notifications = []

    def request(method, params):
        nonlocal sequence
        sequence += 1
        send_message(process, {'jsonrpc': '2.0', 'id': sequence,
                               'method': method, 'params': params})
        response = read_response(process, sequence, notifications)
        assert 'error' not in response, response
        return response.get('result')

    uri = 'file:///tmp/compiler-session-resources.vri'
    declarations = ''.join(f'    var value{i} = {i}\n' for i in range(128))
    source = 'func main:\n' + declarations + '    out value0\nend.\n'
    try:
        request('initialize', {'capabilities': {}})
        send_message(process, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen',
                               'params': {'textDocument': {'uri': uri, 'languageId': 'vir',
                                                          'version': 1, 'text': source}}})
        previous_id = None
        for version in range(2, iterations + 2):
            send_message(process, {'jsonrpc': '2.0', 'method': 'textDocument/didChange',
                                   'params': {'textDocument': {'uri': uri, 'version': version},
                                              'contentChanges': [{'text': source}]}})
            snapshot = request('vir/semanticSnapshot', {'textDocument': {'uri': uri}})
            assert snapshot['documentVersion'] == version, snapshot
            dependencies = snapshot['dependencies']
            assert len({d['uri'] for d in dependencies}) == len(dependencies), (version, dependencies)
            root_dependency = next(d for d in dependencies if d['uri'] == uri)
            assert root_dependency['documentVersion'] == version, (version, dependencies)
            assert snapshot['complete'], (version, snapshot.get('unavailableReason'))
            assert snapshot['analysisId'] != previous_id
            assert len(snapshot['symbols']) == 129, (
                version, len(snapshot['symbols']), snapshot['analysisId'],
                snapshot.get('unavailableReason'),
                sorted({'main', *(f'value{i}' for i in range(128))}
                       - {symbol['name'] for symbol in snapshot['symbols']}))
            repeated = request('vir/semanticSnapshot', {'textDocument': {'uri': uri}})
            assert repeated['analysisId'] == snapshot['analysisId'], (version, snapshot['analysisId'], repeated['analysisId'], snapshot.get('unavailableReason'), repeated.get('unavailableReason'), snapshot.get('dependencies'), repeated.get('dependencies'), [n for n in notifications[-3:] if n.get('method') == 'textDocument/publishDiagnostics'])
            previous_id = snapshot['analysisId']
        request('shutdown', {})
        send_message(process, {'jsonrpc': '2.0', 'method': 'exit', 'params': {}})
        process.wait(timeout=5)
        assert process.returncode == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    usage = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return usage if sys.platform == 'darwin' else usage * 1024


def main():
    if sys.platform == 'win32':
        print('SKIP: POSIX worker RSS contract is unavailable on Windows')
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--measure':
        print(json.dumps({'peakBytes': measure(int(sys.argv[2]))}))
        return
    peaks = []
    for iterations in (3, 80):
        result = subprocess.run([sys.executable, __file__, '--measure', str(iterations)],
                                capture_output=True, text=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        peaks.append(json.loads(result.stdout)['peakBytes'])
    growth = peaks[1] - peaks[0]
    assert growth < 32 * 1024 * 1024, (peaks, growth)
    print(f'PASS: repeated compiler analyses have bounded peak RSS ({peaks}, growth={growth})')


if __name__ == '__main__':
    main()

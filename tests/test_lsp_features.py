#!/usr/bin/env python3
"""
Test LSP language features (didOpen, didChange, hover, definition, references,
completion, prepareRename, rename, semanticTokens, semanticSnapshot,
diagnosticSnapshot, publishDiagnostics, shutdown, exit)
against native vir-lsp daemon.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIR_LSP = Path(os.environ.get("VIR_LSP", ROOT / "bin/vir-lsp"))


def send_message(proc, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    proc.stdin.write(header + body)
    proc.stdin.flush()


def read_message(proc) -> dict:
    header = b""
    while b"\r\n\r\n" not in header:
        ch = proc.stdout.read(1)
        if not ch:
            raise EOFError("vir-lsp closed stdout unexpectedly")
        header += ch

    content_length = None
    for line in header.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            content_length = int(line.split(b":")[1].strip())
            break

    if content_length is None:
        raise ValueError(f"Missing Content-Length header: {header}")

    body = proc.stdout.read(content_length)
    if len(body) != content_length:
        raise EOFError(f"Expected {content_length} bytes, got {len(body)}")

    return json.loads(body.decode("utf-8"))


def read_response(proc, req_id: int, notifications_sink: list = None) -> dict:
    while True:
        msg = read_message(proc)
        if msg.get("id") == req_id:
            return msg
        if "method" in msg:
            if notifications_sink is not None:
                notifications_sink.append(msg)
            continue
        raise ValueError(f"Unexpected message without expected id {req_id}: {msg}")


def test_lsp_features():
    proc = subprocess.Popen(
        [str(VIR_LSP), "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    notifications = []

    try:
        # 1. initialize
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "processId": os.getpid(),
                    "rootUri": f"file://{ROOT}",
                    "capabilities": {"workspace": {"workspaceEdit": {"documentChanges": True}}},
                },
            },
        )
        resp = read_response(proc, 1, notifications)
        assert resp.get("id") == 1
        caps = resp["result"]["capabilities"]
        assert caps.get("positionEncoding") == "utf-16"
        assert caps.get("hoverProvider") is True
        assert caps.get("definitionProvider") is True
        assert caps.get("referencesProvider") is True
        assert "semanticTokensProvider" in caps
        assert "experimental" in caps and "vir" in caps["experimental"]
        vir_cap = caps["experimental"]["vir"]
        assert vir_cap["schemaVersion"] == 1
        assert vir_cap["semanticSnapshot"] is True
        assert "virAlive" in vir_cap["semanticTokenModifiers"]
        assert "virMoved" in vir_cap["semanticTokenModifiers"]
        assert "virLastUse" in vir_cap["semanticTokenModifiers"]
        print("PASS: initialize (full capabilities negotiated)")

        # 2. initialized
        send_message(proc, {"jsonrpc": "2.0", "method": "initialized", "params": {}})

        # 3. didOpen
        doc_uri = f"file://{ROOT}/tests/sample.vri"
        doc_text = (
            "func add(a: int, b: int) -> int:\n"
            "    out a + b\n"
            "end.\n"
            "\n"
            "func main():\n"
            "    let x = add(1, 2)\n"
            "end.\n"
        )
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": doc_uri,
                        "languageId": "vir",
                        "version": 1,
                        "text": doc_text,
                    }
                },
            },
        )
        print("PASS: textDocument/didOpen sent")

        # 4. hover
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 0, "character": 6},
                },
            },
        )
        hover_resp = read_response(proc, 2, notifications)
        assert hover_resp.get("id") == 2
        assert "result" in hover_resp
        assert "contents" in hover_resp["result"]
        contents_val = hover_resp["result"]["contents"]["value"]
        assert "add" in contents_val
        assert "function" in contents_val
        print(f"PASS: textDocument/hover -> {contents_val[:40]}...")

        # Check that publishDiagnostics was emitted for didOpen
        assert any(n.get("method") == "textDocument/publishDiagnostics" for n in notifications)
        print("PASS: textDocument/publishDiagnostics received")

        # 5. definition
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "textDocument/definition",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 5, "character": 13},
                },
            },
        )
        def_resp = read_response(proc, 3, notifications)
        assert def_resp.get("id") == 3
        assert "result" in def_resp
        target = def_resp["result"]
        assert target["range"]["start"]["line"] == 0
        assert target["range"]["start"]["character"] == 5
        print(f"PASS: textDocument/definition -> line {target['range']['start']['line']}, col {target['range']['start']['character']}")

        # 6. references
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "textDocument/references",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 0, "character": 6},
                },
            },
        )
        ref_resp = read_response(proc, 4, notifications)
        assert ref_resp.get("id") == 4
        refs = ref_resp["result"]
        assert isinstance(refs, list) and len(refs) >= 2  # declaration + call
        print(f"PASS: textDocument/references -> {len(refs)} reference occurrences found")

        # 7. completion
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "textDocument/completion",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 6, "character": 0},
                },
            },
        )
        comp_resp = read_response(proc, 5, notifications)
        assert comp_resp.get("id") == 5
        items = comp_resp["result"]["items"]
        labels = [it["label"] for it in items]
        assert "func" in labels
        assert "let" in labels
        assert "add" in labels
        print(f"PASS: textDocument/completion -> {len(items)} items including 'add', 'func', 'let'")

        # 8. prepareRename
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "textDocument/prepareRename",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 0, "character": 6},
                },
            },
        )
        prep_resp = read_response(proc, 6, notifications)
        assert prep_resp.get("id") == 6
        assert prep_resp["result"]["placeholder"] == "add"
        print("PASS: textDocument/prepareRename on 'add'")

        # 9. rename
        # 9a. Collision test: rename to keyword 'func' should fail
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "textDocument/rename",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 0, "character": 6},
                    "newName": "func",
                },
            },
        )
        ren_err_resp = read_response(proc, 7, notifications)
        assert "error" in ren_err_resp
        assert ren_err_resp["error"]["code"] == -32602
        print("PASS: textDocument/rename negative (collision with keyword rejected)")

        # 9b. Valid rename: rename 'add' to 'sum_values'
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "textDocument/rename",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 0, "character": 6},
                    "newName": "sum_values",
                },
            },
        )
        ren_resp = read_response(proc, 8, notifications)
        assert ren_resp.get("id") == 8
        edits = ren_resp["result"]["documentChanges"][0]["edits"]
        assert len(edits) >= 2
        assert all(e["newText"] == "sum_values" for e in edits)
        print(f"PASS: textDocument/rename positive -> {len(edits)} edits replacing 'add' with 'sum_values'")

        # 10. semanticTokens/full
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "textDocument/semanticTokens/full",
                "params": {
                    "textDocument": {"uri": doc_uri},
                },
            },
        )
        tok_resp = read_response(proc, 9, notifications)
        assert tok_resp.get("id") == 9
        tok_data = tok_resp["result"]["data"]
        assert len(tok_data) > 0
        assert len(tok_data) % 5 == 0
        print(f"PASS: textDocument/semanticTokens/full -> {len(tok_data) // 5} semantic tokens delta-encoded")

        # 11. vir/semanticSnapshot
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "vir/semanticSnapshot",
                "params": {"textDocument": {"uri": doc_uri}},
            },
        )
        snap_resp = read_response(proc, 10, notifications)
        assert snap_resp.get("id") == 10
        snap = snap_resp["result"]
        assert snap["schemaVersion"] == 1
        assert snap["complete"] is True
        assert len(snap["occurrences"]) >= 2
        assert len(snap["functions"]) >= 2
        print(f"PASS: vir/semanticSnapshot -> {len(snap['occurrences'])} occurrences, {len(snap['functions'])} functions")

        # 12. vir/diagnosticSnapshot
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "vir/diagnosticSnapshot",
                "params": {"textDocument": {"uri": doc_uri}},
            },
        )
        dsnap_resp = read_response(proc, 11, notifications)
        assert dsnap_resp.get("id") == 11
        assert dsnap_resp["result"]["schemaVersion"] == 1
        print("PASS: vir/diagnosticSnapshot")

        # 13. didChange uses the compiler parser diagnostic, with no lexical fake code
        bad_text = "func compute():\n    let m = Matrix<1, 2, 3>\nend.\n"
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didChange",
                "params": {
                    "textDocument": {"uri": doc_uri, "version": 2},
                    "contentChanges": [{"text": bad_text}],
                },
            },
        )
        # Flush notifications to find error
        diag_notif = None
        for _ in range(5):
            msg = read_message(proc)
            if msg.get("method") == "textDocument/publishDiagnostics":
                diag_notif = msg
                break
        assert diag_notif is not None
        diags = diag_notif["params"]["diagnostics"]
        assert len(diags) > 0
        assert any(d["code"] == "E1004" for d in diags), diags
        assert all(d["code"] != "E3010" for d in diags), diags
        print(f"PASS: textDocument/didChange -> compiler parser error E1004 emitted: '{diags[0]['message']}'")

        # 14. shutdown
        send_message(proc, {"jsonrpc": "2.0", "id": 12, "method": "shutdown", "params": {}})
        shut_resp = read_response(proc, 12)
        assert shut_resp.get("id") == 12
        assert shut_resp.get("result") is None
        print("PASS: shutdown")

        # 15. exit
        send_message(proc, {"jsonrpc": "2.0", "method": "exit", "params": {}})
        proc.wait(timeout=5)
        assert proc.returncode == 0
        print("PASS: clean exit (code 0)")

    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    test_lsp_features()
    print("\nALL LSP PASS 2 INTEGRATION TESTS PASSED (15/15)!")

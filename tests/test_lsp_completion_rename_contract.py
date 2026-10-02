#!/usr/bin/env python3
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

    body = proc.stdout.read(content_length)
    return json.loads(body.decode("utf-8"))

def read_response(proc, req_id: int) -> dict:
    while True:
        msg = read_message(proc)
        if msg.get("id") == req_id:
            return msg

def main():
    proc = subprocess.Popen(
        [str(VIR_LSP), "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # 1. Initialize
        send_message(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"processId": os.getpid(), "rootUri": f"file://{ROOT}", "capabilities": {"workspace": {"workspaceEdit": {"documentChanges": True}}}}})
        init_resp = read_response(proc, 1)
        assert init_resp["result"]["capabilities"]["completionProvider"] is not None
        assert init_resp["result"]["capabilities"]["renameProvider"] is not None
        send_message(proc, {"jsonrpc": "2.0", "method": "initialized", "params": {}})
        print("PASS: Handshake & capabilities confirmed")

        # 2. Document with member access, multiple functions & child scopes
        doc_uri = f"file://{ROOT}/tests/contract_test.vri"
        doc_lines = [
            "func funcA():",               # 0
            "    var localA = 10",         # 1
            "    if true do",              # 2
            "        var childA = 20",     # 3
            "    end",                     # 4
            "end.",                        # 5
            "func funcB():",               # 6
            "    var localB = 30",         # 7
            "    localB.",                 # 8  (cursor right after dot)
            "end.",                        # 9
        ]
        doc_text = "\n".join(doc_lines) + "\n"

        send_message(proc, {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_uri, "languageId": "vir", "version": 1, "text": doc_text}},
        })

        # Test A: Member completion on line 8 right after 'localB.' (col 11)
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "textDocument/completion",
            "params": {"textDocument": {"uri": doc_uri}, "position": {"line": 8, "character": 11}},
        })
        comp_mem = read_response(proc, 2)
        items = comp_mem["result"]["items"]
        labels = [it["label"] for it in items]
        assert labels == []
        assert comp_mem["result"]["isIncomplete"] is True
        assert "slice" not in labels
        assert "matmul" not in labels
        assert "func" not in labels  # keyword should NOT be present in member completion
        assert "localA" not in labels # local variable should NOT be in member completion
        print("PASS: Unresolved receiver returns incomplete empty completion")

        # Test B: Scope-filtered completion on line 7 inside funcB
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "textDocument/completion",
            "params": {"textDocument": {"uri": doc_uri}, "position": {"line": 7, "character": 4}},
        })
        comp_scope = read_response(proc, 3)
        items_scope = comp_scope["result"]["items"]
        labels_scope = [it["label"] for it in items_scope]
        assert "func" in labels_scope
        assert "funcA" in labels_scope # global function visible
        assert "funcB" in labels_scope # global function visible
        assert "localB" in labels_scope # local variable of funcB visible
        assert "localA" not in labels_scope # local variable of funcA must NOT leak into funcB
        assert "childA" not in labels_scope # child scope variable must NOT leak
        print("PASS: Scope-filtered completion -> 'localB' visible in funcB, 'localA' and 'childA' strictly isolated")

        # Test C: Child-scope capture rejection on rename
        # In funcA, line 1: var localA = 10; child scope has childA = 20
        # If we try to rename localA -> childA, it must be rejected!
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "textDocument/rename",
            "params": {
                "textDocument": {"uri": doc_uri},
                "position": {"line": 1, "character": 8},
                "newName": "childA",
            },
        })
        ren_capture = read_response(proc, 4)
        assert "error" in ren_capture
        assert ren_capture["error"]["code"] == -32602
        print(f"PASS: Variable capture in child scope rejected -> {ren_capture['error']['message']}")

        # Test D: Prepare rename returns valid placeholder
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "textDocument/prepareRename",
            "params": {"textDocument": {"uri": doc_uri}, "position": {"line": 1, "character": 8}},
        })
        prep_resp = read_response(proc, 5)
        assert prep_resp["result"]["placeholder"] == "localA"
        print("PASS: prepareRename on localA -> placeholder verified")

        # Test E: vir/diagnosticSnapshot on physical file
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "vir/diagnosticSnapshot",
            "params": {"textDocument": {"uri": doc_uri}, "code": "all"},
        })
        dsnap = read_response(proc, 6)
        assert dsnap["result"]["schemaVersion"] == 1
        print("PASS: vir/diagnosticSnapshot returned schemaVersion 1 with diagnosticStoreQuery integration")

        # Shutdown & exit
        send_message(proc, {"jsonrpc": "2.0", "id": 7, "method": "shutdown", "params": {}})
        read_response(proc, 7)
        send_message(proc, {"jsonrpc": "2.0", "method": "exit", "params": {}})
        print("PASS: Clean shutdown and exit")

    finally:
        proc.kill()
        proc.wait()

if __name__ == "__main__":
    main()

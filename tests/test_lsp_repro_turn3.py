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
        # initialize
        send_message(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"processId": os.getpid(), "rootUri": f"file://{ROOT}", "capabilities": {"workspace": {"workspaceEdit": {"documentChanges": True}}}}})
        read_response(proc, 1)
        send_message(proc, {"jsonrpc": "2.0", "method": "initialized", "params": {}})

        # ─────────────────────────────────────────────────────────────
        # TEST P1: Block Shadowing
        # ─────────────────────────────────────────────────────────────
        doc_p1_uri = f"file://{ROOT}/tests/p1_shadow_sample.vri"
        doc_p1_lines = [
            "func foo(x: int) -> int:", # 0
            "    if true do",           # 1
            "        var x = 10",       # 2
            "        x = x + 1",        # 3
            "    end",                  # 4
            "    out x",                # 5
            "end.",                     # 6
        ]
        doc_p1_text = "\n".join(doc_p1_lines) + "\n"

        send_message(proc, {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_p1_uri, "languageId": "vir", "version": 1, "text": doc_p1_text}},
        })

        # Check definition of 'x' at line 5 (out x)
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "textDocument/definition",
            "params": {"textDocument": {"uri": doc_p1_uri}, "position": {"line": 5, "character": 8}},
        })
        def_p1_resp = read_response(proc, 2)
        def_p1_line = def_p1_resp.get("result", {}).get("range", {}).get("start", {}).get("line")
        print("P1: Definition of 'x' at line 5 (out x) -> line:", def_p1_line, "(Expected: 0)")

        # Rename 'x' inside if block at line 2 (var x = 10)
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "textDocument/rename",
            "params": {"textDocument": {"uri": doc_p1_uri}, "position": {"line": 2, "character": 12}, "newName": "inner_x"},
        })
        rename_p1_resp = read_response(proc, 3)
        edits = rename_p1_resp.get("result", {}).get("documentChanges", [{}])[0].get("edits", [])
        edit_lines = [e["range"]["start"]["line"] for e in edits]
        print("P1: Rename inner 'x' edit lines:", edit_lines, "(Expected only [2, 3, 3], NOT 5 or 0)")

        # ─────────────────────────────────────────────────────────────
        # TEST P2: Standalone Section Headers (Spec §14.2)
        # ─────────────────────────────────────────────────────────────
        doc_p2_uri = f"file://{ROOT}/tests/p2_standalone_headers.vri"
        doc_p2_lines = [
            "func transfer:",         # 0
            "    in",                 # 1
            "        source: int",    # 2
            "        destination: int", # 3
            "    ref",                # 4
            "        buffer: int",    # 5
            "    out",                # 6
            "        status: int",    # 7
            "    buffer = buffer + source", # 8
            "    status = destination",     # 9
            "end.",                   # 10
        ]
        doc_p2_text = "\n".join(doc_p2_lines) + "\n"

        send_message(proc, {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_p2_uri, "languageId": "vir", "version": 1, "text": doc_p2_text}},
        })

        # Hover on 'source' (line 2, col 9)
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": doc_p2_uri}, "position": {"line": 2, "character": 9}},
        })
        hover_source = read_response(proc, 4).get("result")
        assert hover_source and "source" in hover_source["contents"]["value"], hover_source
        print("P2: Hover on 'source':", hover_source is not None)

        # Hover on 'buffer' (line 5, col 9)
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": doc_p2_uri}, "position": {"line": 5, "character": 9}},
        })
        hover_buffer = read_response(proc, 5).get("result")
        assert hover_buffer and "virBorrowed" in hover_buffer["contents"]["value"], hover_buffer
        print("P2: Hover on 'buffer':", hover_buffer is not None)

        # Hover on 'status' (line 7, col 9)
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": doc_p2_uri}, "position": {"line": 7, "character": 9}},
        })
        hover_status = read_response(proc, 6).get("result")
        assert hover_status and "virOut" in hover_status["contents"]["value"], hover_status
        print("P2: Hover on 'status':", hover_status is not None)

    finally:
        proc.kill()
        proc.wait()

if __name__ == "__main__":
    main()

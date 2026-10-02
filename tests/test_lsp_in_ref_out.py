#!/usr/bin/env python3
"""
Integration test for 'in', 'ref', and 'out' parameter blocks and keyword hover
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


def test_in_ref_out():
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
        print("PASS: initialize")

        send_message(proc, {"jsonrpc": "2.0", "method": "initialized", "params": {}})

        # 2. didOpen with in/ref/out section blocks
        doc_uri = f"file://{ROOT}/tests/param_blocks.vri"
        doc_lines = [
            "func process:",
            "    in input_data: int",
            "    ref buffer: int",
            "    out result: int",
            "    buffer = buffer + input_data",
            "    result = buffer * 2",
            "end.",
        ]
        doc_text = "\n".join(doc_lines) + "\n"

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
        print("PASS: didOpen with in/ref/out block")

        # 3. Hover on keyword 'in' (line 1, col 4)
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 1, "character": 5},
                },
            },
        )
        resp = read_response(proc, 2, notifications)
        assert "result" in resp and resp["result"] is not None
        hover_in = resp["result"]["contents"]["value"]
        assert "`in`" in hover_in and "by-value" in hover_in
        print(f"PASS: Hover on 'in' keyword -> {hover_in[:50]}...")

        # 4. Hover on keyword 'ref' (line 2, col 4)
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 2, "character": 5},
                },
            },
        )
        resp = read_response(proc, 3, notifications)
        assert "result" in resp and resp["result"] is not None
        hover_ref = resp["result"]["contents"]["value"]
        assert "`ref`" in hover_ref and "&mut" in hover_ref
        print(f"PASS: Hover on 'ref' keyword -> {hover_ref[:50]}...")

        # 5. Hover on keyword 'out' (line 3, col 4)
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 3, "character": 5},
                },
            },
        )
        resp = read_response(proc, 4, notifications)
        assert "result" in resp and resp["result"] is not None
        hover_out = resp["result"]["contents"]["value"]
        assert "`out`" in hover_out and "output parameter" in hover_out
        print(f"PASS: Hover on 'out' keyword -> {hover_out[:50]}...")

        # 6. Hover on ref parameter 'buffer' (line 2, col 9)
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 2, "character": 10},
                },
            },
        )
        resp = read_response(proc, 5, notifications)
        assert "result" in resp and resp["result"] is not None
        hover_buf = resp["result"]["contents"]["value"]
        assert "parameter" in hover_buf and "buffer" in hover_buf
        assert "virBorrowed" in hover_buf
        print(f"PASS: Hover on ref parameter 'buffer' -> {hover_buf}")

        # 7. Hover on out parameter 'result' (line 3, col 9)
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 3, "character": 10},
                },
            },
        )
        resp = read_response(proc, 6, notifications)
        assert "result" in resp and resp["result"] is not None
        hover_res = resp["result"]["contents"]["value"]
        assert "parameter" in hover_res and "result" in hover_res
        assert "virOut" in hover_res
        print(f"PASS: Hover on out parameter 'result' -> {hover_res}")

        # 8. Definition on 'buffer' in line 4: `buffer = buffer + input_data` (line 4, col 4)
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "textDocument/definition",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 4, "character": 5},
                },
            },
        )
        resp = read_response(proc, 7, notifications)
        assert "result" in resp and resp["result"] is not None
        def_range = resp["result"]["range"]
        assert def_range["start"]["line"] == 2  # line 2 has `ref buffer: int`
        print(f"PASS: Definition of buffer -> line {def_range['start']['line']}")

        # 9. References of 'buffer'
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "textDocument/references",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 2, "character": 10},
                },
            },
        )
        resp = read_response(proc, 8, notifications)
        assert "result" in resp and isinstance(resp["result"], list)
        refs = resp["result"]
        # declaration (line 2) + write (line 4 col 4) + read (line 4 col 13) + read (line 5 col 13) = 4 occurrences
        assert len(refs) >= 3
        print(f"PASS: References of buffer -> {len(refs)} occurrences found")

        # 10. Rename 'buffer' -> 'state_buf'
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "textDocument/rename",
                "params": {
                    "textDocument": {"uri": doc_uri},
                    "position": {"line": 2, "character": 10},
                    "newName": "state_buf",
                },
            },
        )
        resp = read_response(proc, 9, notifications)
        assert "result" in resp and "documentChanges" in resp["result"]
        edits = resp["result"]["documentChanges"][0]["edits"]
        assert len(edits) >= 3
        assert all(e["newText"] == "state_buf" for e in edits)
        print(f"PASS: Rename 'buffer' -> {len(edits)} occurrences renamed to 'state_buf'")

        # 11. Parenthesized parameter list test
        paren_uri = f"file://{ROOT}/tests/paren_params.vri"
        paren_text = (
            "func transform(a: int, ref b: int, c: int):\n"
            "    b = b + a\n"
            "    c = b\n"
            "end.\n"
        )
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": paren_uri,
                        "languageId": "vir",
                        "version": 1,
                        "text": paren_text,
                    }
                },
            },
        )
        # Hover on 'ref b' in paren signature (line 0, col 28)
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": paren_uri},
                    "position": {"line": 0, "character": paren_text.splitlines()[0].index("b:")},
                },
            },
        )
        resp = read_response(proc, 10, notifications)
        assert "result" in resp and resp["result"] is not None
        hover_pb = resp["result"]["contents"]["value"]
        assert "parameter" in hover_pb and "b" in hover_pb
        assert "virBorrowed" in hover_pb
        print(f"PASS: Parenthesized ref param hover -> {hover_pb}")

        # Parenthesized c is by value; out belongs to section syntax.
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": paren_uri},
                    "position": {"line": 0, "character": paren_text.splitlines()[0].index("c:")},
                },
            },
        )
        resp = read_response(proc, 11, notifications)
        assert "result" in resp and resp["result"] is not None
        hover_pc = resp["result"]["contents"]["value"]
        assert "parameter" in hover_pc and "c" in hover_pc
        assert "virOut" not in hover_pc
        print(f"PASS: Parenthesized by-value param hover -> {hover_pc}")

        # 12. Multi-function scoping & continuation parameter test (§14.2 & P1/P2)
        multi_uri = f"file://{ROOT}/tests/param_multi_scope.vri"
        multi_lines = [
            "func foo:",              # 0
            "    ref buffer: int",     # 1
            "    buffer = buffer + 1", # 2
            "end.",                    # 3
            "",                        # 4
            "func bar:",              # 5
            "    ref buffer: int",     # 6
            "        other: int",      # 7
            "    buffer = buffer + 2", # 8
            "    other = other + 1",   # 9
            "end.",                    # 10
        ]
        multi_text = "\n".join(multi_lines) + "\n"

        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": multi_uri,
                        "languageId": "vir",
                        "version": 1,
                        "text": multi_text,
                    }
                },
            },
        )

        # Hover on continuation parameter 'other' (line 7, col 9)
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 12,
                "method": "textDocument/hover",
                "params": {"textDocument": {"uri": multi_uri}, "position": {"line": 7, "character": 9}},
            },
        )
        resp = read_response(proc, 12, notifications)
        assert resp.get("result") is not None
        h_val = resp["result"]["contents"]["value"]
        assert "other" in h_val and "virBorrowed" in h_val
        print("PASS: Continuation parameter 'other' hover with virBorrowed modifier")

        # Definition of 'buffer' in bar (line 8, col 5) must point to bar's declaration (line 6)
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 13,
                "method": "textDocument/definition",
                "params": {"textDocument": {"uri": multi_uri}, "position": {"line": 8, "character": 5}},
            },
        )
        resp = read_response(proc, 13, notifications)
        def_start = resp.get("result", {}).get("range", {}).get("start", {})
        assert def_start.get("line") == 6, f"Expected definition of 'buffer' in bar at line 6, got {def_start}"
        print("PASS: Definition of 'buffer' in bar correctly points to bar declaration (line 6)")

        # Rename 'buffer' in foo (line 1, col 9) must NOT touch bar
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 14,
                "method": "textDocument/rename",
                "params": {"textDocument": {"uri": multi_uri}, "position": {"line": 1, "character": 9}, "newName": "foo_buf"},
            },
        )
        resp = read_response(proc, 14, notifications)
        edits = resp.get("result", {}).get("documentChanges", [{}])[0].get("edits", [])
        assert len(edits) == 3, f"Expected exactly 3 edits in foo, got {len(edits)}"
        for e in edits:
            assert e["range"]["start"]["line"] in (1, 2), f"Edit outside foo scope: {e}"
        print("PASS: Scoped rename of 'buffer' in foo strictly affects foo only (3 edits)")

        # Rename 'buffer' in bar (line 6, col 9) must NOT touch foo
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 15,
                "method": "textDocument/rename",
                "params": {"textDocument": {"uri": multi_uri}, "position": {"line": 6, "character": 9}, "newName": "bar_buf"},
            },
        )
        resp = read_response(proc, 15, notifications)
        edits = resp.get("result", {}).get("documentChanges", [{}])[0].get("edits", [])
        assert len(edits) == 3, f"Expected exactly 3 edits in bar, got {len(edits)}"
        for e in edits:
            assert e["range"]["start"]["line"] in (6, 8), f"Edit outside bar scope: {e}"
        print("PASS: Scoped rename of 'buffer' in bar strictly affects bar only (3 edits)")

        # vir/semanticSnapshot on multi-scope document
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 16,
                "method": "vir/semanticSnapshot",
                "params": {"textDocument": {"uri": multi_uri}},
            },
        )
        resp = read_response(proc, 16, notifications)
        snap = resp.get("result", {})
        assert snap.get("schemaVersion") == 1
        assert snap.get("complete") is True
        symbols = snap.get("symbols", [])
        assert len(symbols) >= 5
        print(f"PASS: vir/semanticSnapshot verified with {len(symbols)} symbols")

        # 17. Shutdown & Exit
        send_message(proc, {"jsonrpc": "2.0", "id": 17, "method": "shutdown", "params": {}})
        resp = read_response(proc, 17)
        assert resp.get("id") == 17
        send_message(proc, {"jsonrpc": "2.0", "method": "exit", "params": {}})
        proc.wait(timeout=5)
        assert proc.returncode == 0
        print("PASS: Clean shutdown and exit")

    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    test_in_ref_out()
    print("\nALL IN/REF/OUT & MULTI-SCOPE LSP TESTS PASSED (17/17)!")

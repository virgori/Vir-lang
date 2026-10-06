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
        init_resp = read_response(proc, 1)
        assert "capabilities" in init_resp.get("result", {})
        send_message(proc, {"jsonrpc": "2.0", "method": "initialized", "params": {}})

        doc_uri = f"file://{ROOT}/tests/p1_p2_sample.vri"
        doc_lines = [
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
        doc_text = "\n".join(doc_lines) + "\n"

        send_message(proc, {
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
        })

        # Test P2: hover on continuation param 'other' at line 7, col 9
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": doc_uri}, "position": {"line": 7, "character": 9}},
        })
        hover_resp = read_response(proc, 2)
        h_res = hover_resp.get("result")
        assert h_res is not None, "P2: Hover on 'other' must not be None"
        h_val = h_res["contents"]["value"]
        assert "other" in h_val and "virBorrowed" in h_val, f"P2: Expected other and virBorrowed in hover: {h_val}"
        print("PASS: P2 Hover on continuation param 'other':", h_val.split("\n\n")[0])

        # Test P1: definition of 'buffer' in foo (line 2, col 5)
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "textDocument/definition",
            "params": {"textDocument": {"uri": doc_uri}, "position": {"line": 2, "character": 5}},
        })
        def_foo_resp = read_response(proc, 3)
        def_foo_start = def_foo_resp.get("result", {}).get("range", {}).get("start", {})
        assert def_foo_start.get("line") == 1, f"Expected definition of 'buffer' in foo to point to line 1, got {def_foo_start}"
        print("PASS: P1 Definition of 'buffer' in foo correctly points to line 1")

        # Test P1: definition of 'buffer' in bar (line 8, col 5)
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "textDocument/definition",
            "params": {"textDocument": {"uri": doc_uri}, "position": {"line": 8, "character": 5}},
        })
        def_bar_resp = read_response(proc, 4)
        def_bar_start = def_bar_resp.get("result", {}).get("range", {}).get("start", {})
        assert def_bar_start.get("line") == 6, f"Expected definition of 'buffer' in bar to point to line 6, got {def_bar_start}"
        print("PASS: P1 Definition of 'buffer' in bar correctly points to line 6 (inside bar)")

        # Test P1: rename 'buffer' in foo (line 1, col 9)
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "textDocument/rename",
            "params": {"textDocument": {"uri": doc_uri}, "position": {"line": 1, "character": 9}, "newName": "new_buf"},
        })
        rename_foo_resp = read_response(proc, 5)
        foo_edits = rename_foo_resp.get("result", {}).get("documentChanges", [{}])[0].get("edits", [])
        assert len(foo_edits) == 3, f"Expected exactly 3 edits in foo, got {len(foo_edits)}"
        for e in foo_edits:
            assert e["range"]["start"]["line"] in (1, 2), f"Edit out of scope for foo: {e}"
        print(f"PASS: P1 Rename 'buffer' in foo produced exactly {len(foo_edits)} edits, all confined to foo")

        # Test P1: rename 'buffer' in bar (line 6, col 9)
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "textDocument/rename",
            "params": {"textDocument": {"uri": doc_uri}, "position": {"line": 6, "character": 9}, "newName": "bar_buf"},
        })
        rename_bar_resp = read_response(proc, 6)
        bar_edits = rename_bar_resp.get("result", {}).get("documentChanges", [{}])[0].get("edits", [])
        assert len(bar_edits) == 3, f"Expected exactly 3 edits in bar, got {len(bar_edits)}"
        for e in bar_edits:
            assert e["range"]["start"]["line"] in (6, 8), f"Edit out of scope for bar: {e}"
        print(f"PASS: P1 Rename 'buffer' in bar produced exactly {len(bar_edits)} edits, all confined to bar")

        # Test references of 'buffer' in foo vs bar
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "textDocument/references",
            "params": {"textDocument": {"uri": doc_uri}, "position": {"line": 1, "character": 9}},
        })
        ref_foo_resp = read_response(proc, 7)
        foo_refs = ref_foo_resp.get("result", [])
        assert len(foo_refs) == 3, f"Expected 3 references in foo, got {len(foo_refs)}"
        for r in foo_refs:
            assert r["range"]["start"]["line"] in (1, 2)
        print("PASS: References for 'buffer' in foo strictly isolated to foo")

        # Test vir/semanticSnapshot
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "vir/semanticSnapshot",
            "params": {"textDocument": {"uri": doc_uri}},
        })
        snap_resp = read_response(proc, 8)
        snap = snap_resp.get("result", {})
        assert snap.get("schemaVersion") == 1
        assert snap.get("complete") is True
        occurrences = snap.get("occurrences", [])
        symbols = snap.get("symbols", [])
        assert len(occurrences) > 0, "Occurrences must not be empty"
        assert len(symbols) >= 5, f"Expected at least 5 symbols (foo, buffer@foo, bar, buffer@bar, other@bar), got {len(symbols)}"

        # Verify symbol scopes and states
        sym_map = {s["symbolId"]: s for s in symbols}
        buf_foo_sym = next(s for s in symbols if s["name"] == "buffer" and s["range"]["start"]["line"] == 1)
        buf_bar_sym = next(s for s in symbols if s["name"] == "buffer" and s["range"]["start"]["line"] == 6)
        other_sym = next(s for s in symbols if s["name"] == "other" and s["range"]["start"]["line"] == 7)

        assert buf_foo_sym["symbolId"] != buf_bar_sym["symbolId"], "Symbols in different functions must have distinct symbolIds"
        assert buf_foo_sym["scopeId"] != buf_bar_sym["scopeId"], "Symbols in different functions must have distinct scopeIds"
        assert other_sym["scopeId"] == buf_bar_sym["scopeId"], "other and buffer in bar must share the same scopeId"

        # Verify dynamic states in occurrences
        ref_occs = [o for o in occurrences if "virBorrowed" in o.get("states", [])]
        assert len(ref_occs) >= 3, f"Expected at least 3 virBorrowed occurrences (foo.buffer, bar.buffer, bar.other), got {len(ref_occs)}"
        print(f"PASS: vir/semanticSnapshot validated with {len(symbols)} symbols, {len(occurrences)} occurrences and dynamic states")

        print("\nALL SCOPING AND CONTINUATION PARAMETER TESTS PASSED (100%)")

    finally:
        proc.kill()
        proc.wait()

if __name__ == "__main__":
    main()

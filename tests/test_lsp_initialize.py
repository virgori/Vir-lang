#!/usr/bin/env python3
"""
Test LSP JSON-RPC initialize/shutdown/exit handshake for native vir-lsp daemon.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIR_LSP = Path(os.environ.get("VIR_LSP", ROOT / "bin/vir-lsp"))
VIR_LSP_VERSION = json.loads(
    (ROOT / "tools/vir-lsp/version.json").read_text(encoding="utf-8")
)["public_version"]


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


def test_cli_help_and_version():
    res = subprocess.run([str(VIR_LSP), "--version"], capture_output=True, text=True)
    assert res.returncode == 0, f"Expected 0, got {res.returncode}, stderr: {res.stderr}"
    assert f"vir-lsp {VIR_LSP_VERSION}" in res.stdout, f"Unexpected version output: {res.stdout}"
    assert "unknown option" not in res.stderr.lower() and "unknown option" not in res.stdout.lower()

    res = subprocess.run([str(VIR_LSP), "--help"], capture_output=True, text=True)
    assert res.returncode == 0, f"Expected 0, got {res.returncode}, stderr: {res.stderr}"
    assert "vir-lsp" in res.stdout
    assert "unknown option" not in res.stderr.lower() and "unknown option" not in res.stdout.lower()
    print("PASS: test_cli_help_and_version")


def test_lsp_handshake():
    proc = subprocess.Popen(
        [str(VIR_LSP), "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # 1. initialize request
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

        resp = read_message(proc)
        assert resp.get("jsonrpc") == "2.0", f"Bad jsonrpc version: {resp}"
        assert resp.get("id") == 1, f"Bad id: {resp}"
        result = resp.get("result", {})
        caps = result.get("capabilities", {})
        assert caps.get("hoverProvider") is True, f"Missing hoverProvider: {caps}"
        assert caps.get("definitionProvider") is True, f"Missing definitionProvider: {caps}"
        assert "serverInfo" in result, f"Missing serverInfo: {result}"
        assert result["serverInfo"]["name"] == "vir-lsp"
        assert result["serverInfo"]["version"] == VIR_LSP_VERSION
        print("PASS: lsp initialize handshake")

        # 2. initialized notification
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "initialized",
                "params": {},
            },
        )

        # 3. shutdown request
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "shutdown",
                "params": {},
            },
        )
        resp2 = read_message(proc)
        assert resp2.get("id") == 2, f"Bad shutdown id: {resp2}"
        assert resp2.get("result") is None, f"Expected null result for shutdown: {resp2}"
        print("PASS: lsp shutdown")

        # 4. exit notification
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "exit",
                "params": {},
            },
        )
        proc.wait(timeout=5)
        assert proc.returncode == 0, f"Expected returncode 0 on exit, got {proc.returncode}"
        print("PASS: lsp clean exit")

    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    test_cli_help_and_version()
    test_lsp_handshake()
    print("ALL LSP PROTOCOL SMOKE TESTS PASSED!")

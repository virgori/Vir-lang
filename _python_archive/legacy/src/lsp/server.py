"""
Vir LSP Server — Language Server Protocol for Vir language.
=============================================================
Implements LSP 3.17 over stdio with JSON-RPC 2.0 transport.

Features:
  - textDocument/didOpen, didChange, didSave
  - textDocument/completion (keywords + symbols)
  - textDocument/hover (basic type info)
  - textDocument/definition (goto definition)
  - textDocument/publishDiagnostics (parse errors)
  - textDocument/formatting (basic indent)

Launch:  python -m src.lsp
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════
# JSON-RPC 2.0 Transport (Content-Length framing)
# ═══════════════════════════════════════════════════════════

def _read_message(stream=None) -> dict[str, Any] | None:
    """Read a JSON-RPC message from stdin using Content-Length headers."""
    if stream is None:
        stream = sys.stdin.buffer

    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        line_str = line.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line_str:
            break  # Empty line = end of headers
        if ":" in line_str:
            key, _, val = line_str.partition(":")
            headers[key.strip()] = val.strip()

    content_length = int(headers.get("Content-Length", "0"))
    if content_length == 0:
        return None

    body = stream.read(content_length)
    return json.loads(body.decode("utf-8"))


def _write_message(msg: dict[str, Any], stream=None) -> None:
    """Write a JSON-RPC message to stdout with Content-Length headers."""
    if stream is None:
        stream = sys.stdout.buffer

    body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
    stream.write(header)
    stream.write(body)
    stream.flush()


def _response(id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _error(id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


def _notification(method: str, params: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": method, "params": params}


# ═══════════════════════════════════════════════════════════
# Document Manager (open files state)
# ═══════════════════════════════════════════════════════════

@dataclass
class TextDocument:
    uri: str
    version: int = 0
    text: str = ""
    language_id: str = "vir"


class DocumentStore:
    """In-memory store of open documents."""

    def __init__(self) -> None:
        self._docs: dict[str, TextDocument] = {}

    def open(self, uri: str, text: str, version: int = 0, lang: str = "vir") -> None:
        self._docs[uri] = TextDocument(uri=uri, version=version, text=text, language_id=lang)

    def update(self, uri: str, text: str, version: int = 0) -> None:
        if uri in self._docs:
            self._docs[uri].text = text
            self._docs[uri].version = version

    def close(self, uri: str) -> None:
        self._docs.pop(uri, None)

    def get(self, uri: str) -> TextDocument | None:
        return self._docs.get(uri)

    def all_uris(self) -> list[str]:
        return list(self._docs.keys())


# ═══════════════════════════════════════════════════════════
# Diagnostics — Parse source and report errors
# ═══════════════════════════════════════════════════════════

@dataclass
class Diagnostic:
    line: int           # 0-based
    col: int            # 0-based
    end_line: int = 0
    end_col: int = 0
    message: str = ""
    severity: int = 1   # 1=Error, 2=Warning, 3=Info, 4=Hint

    def to_lsp(self) -> dict:
        return {
            "range": {
                "start": {"line": self.line, "character": self.col},
                "end": {"line": self.end_line or self.line, "character": self.end_col or self.col + 1},
            },
            "severity": self.severity,
            "source": "vir",
            "message": self.message,
        }


# Vir keywords for completion
VIR_KEYWORDS = [
    "func", "end", "if", "eif", "else", "when", "loop", "out", "skip",
    "let", "var", "const", "entity", "method", "class", "include", "import",
    "from", "export", "share", "has", "in", "get", "case", "map",
    "print", "input", "async", "task", "wait", "break", "true", "false",
    "enum", "trait", "impl", "for", "match", "extern", "module",
]


def analyze_source(text: str) -> tuple[list[Diagnostic], list[str]]:
    """
    Lightweight analysis of Vir source:
    - Check bracket/block matching (func...end, if...end, etc.)
    - Extract symbol names (func/entity/let definitions)
    Returns (diagnostics, symbols).
    """
    diagnostics: list[Diagnostic] = []
    symbols: list[str] = []
    block_stack: list[tuple[str, int]] = []  # (keyword, line_number)

    block_openers = {"func", "if", "when", "loop", "entity", "method", "class", "case", "map", "enum", "trait", "impl"}

    for lineno, line in enumerate(text.splitlines()):
        stripped = line.strip()

        # Skip comments
        if stripped.startswith("#"):
            continue

        # Extract tokens
        tokens = stripped.split()
        if not tokens:
            continue

        first = tokens[0]

        # Block openers
        if first in block_openers or (first == "async" and len(tokens) > 1 and tokens[1] == "func"):
            block_stack.append((first, lineno))
            # Extract name
            if first in ("func", "entity", "method", "class", "enum", "trait"):
                if len(tokens) > 1:
                    name = tokens[1].rstrip(":")
                    symbols.append(name)
            elif first == "async" and len(tokens) > 2:
                symbols.append(tokens[2].rstrip(":"))

        # Block closers
        elif first == "end":
            if block_stack:
                block_stack.pop()
            else:
                diagnostics.append(Diagnostic(
                    line=lineno, col=0, message="Unexpected 'end' without matching block opener"
                ))

        # let/const definitions
        elif first == "let" and len(tokens) > 1:
            name = tokens[1].rstrip(":").rstrip("=")
            symbols.append(name)
        elif first == "const" and len(tokens) > 1:
            name = tokens[1].rstrip(":")
            symbols.append(name)

    # Unclosed blocks
    for keyword, lineno in block_stack:
        diagnostics.append(Diagnostic(
            line=lineno, col=0,
            message=f"Unclosed '{keyword}' block — missing 'end'",
            severity=1,
        ))

    return diagnostics, symbols


def get_completions(text: str, line: int, col: int) -> list[dict]:
    """Generate completion items at given position."""
    items = []

    # Get word prefix at cursor
    lines = text.splitlines()
    if line < len(lines):
        current_line = lines[line]
        prefix = ""
        for i in range(col - 1, -1, -1):
            if i < len(current_line) and current_line[i].isalnum() or (i < len(current_line) and current_line[i] == "_"):
                prefix = current_line[i] + prefix
            else:
                break
    else:
        prefix = ""

    # Keyword completions
    for kw in VIR_KEYWORDS:
        if kw.startswith(prefix.lower()):
            items.append({
                "label": kw,
                "kind": 14,  # Keyword
                "detail": "Vir keyword",
            })

    # Symbol completions from source
    _, symbols = analyze_source(text)
    for sym in symbols:
        if sym.startswith(prefix):
            items.append({
                "label": sym,
                "kind": 6,  # Variable
                "detail": "Defined symbol",
            })

    return items


def get_hover(text: str, line: int, col: int) -> str | None:
    """Get hover info for word at position."""
    lines = text.splitlines()
    if line >= len(lines):
        return None

    current_line = lines[line]
    # Find word at col
    word_start = col
    while word_start > 0 and (current_line[word_start - 1].isalnum() or current_line[word_start - 1] == "_"):
        word_start -= 1
    word_end = col
    while word_end < len(current_line) and (current_line[word_end].isalnum() or current_line[word_end] == "_"):
        word_end += 1
    word = current_line[word_start:word_end]

    if not word:
        return None

    # Check keywords
    keyword_docs = {
        "func": "**func** — Khai báo hàm.\n```vir\nfunc name: in(params)\n    ...\nend\n```",
        "entity": "**entity** — Khai báo kiểu dữ liệu (struct).\n```vir\nentity Name:\n    field1: Type\n    field2: Type\nend\n```",
        "if": "**if** — Câu lệnh điều kiện.\n```vir\nif condition\n    ...\neif other\n    ...\nelse\n    ...\nend\n```",
        "when": "**when** — Vòng lặp có điều kiện.\n```vir\nwhen condition loop\n    ...\nend\n```",
        "loop": "**loop** — Vòng lặp vô hạn.\n```vir\nloop\n    ...\n    break;\nend\n```",
        "include": "**include** — Import module.\n```vir\ninclude math;\n```",
        "import": "**import** — Import symbols cụ thể.\n```vir\nimport Func1, Func2 from module;\n```",
        "let": "**let** — Khai báo biến.\n```vir\nlet x = 42;\n```",
        "out": "**out** — Trả về giá trị (thay return).\n```vir\nout result;\n```",
        "enum": "**enum** — Kiểu liệt kê.\n```vir\nenum Color:\n    Red\n    Green\n    Blue\nend\n```",
        "trait": "**trait** — Khai báo trait (interface).\n```vir\ntrait Printable:\n    has print;\nend\n```",
    }

    if word in keyword_docs:
        return keyword_docs[word]

    # Search for definition in source
    for i, src_line in enumerate(lines):
        stripped = src_line.strip()
        if stripped.startswith(f"func {word}") or stripped.startswith(f"entity {word}"):
            return f"**{word}** — Defined at line {i + 1}\n```vir\n{stripped}\n```"

    return None


def find_definition(text: str, line: int, col: int) -> tuple[int, int] | None:
    """Find definition of word at position. Returns (def_line, def_col) or None."""
    lines = text.splitlines()
    if line >= len(lines):
        return None

    current_line = lines[line]
    word_start = col
    while word_start > 0 and (current_line[word_start - 1].isalnum() or current_line[word_start - 1] == "_"):
        word_start -= 1
    word_end = col
    while word_end < len(current_line) and (current_line[word_end].isalnum() or current_line[word_end] == "_"):
        word_end += 1
    word = current_line[word_start:word_end]

    if not word:
        return None

    for i, src_line in enumerate(lines):
        stripped = src_line.strip()
        for prefix in ("func ", "entity ", "method ", "class ", "let ", "const ", "enum ", "trait "):
            if stripped.startswith(prefix):
                name = stripped[len(prefix):].split(":")[0].split("=")[0].split("(")[0].strip()
                if name == word:
                    indent = len(src_line) - len(src_line.lstrip())
                    return (i, indent + len(prefix))

    return None


# ═══════════════════════════════════════════════════════════
# LSP Server Loop
# ═══════════════════════════════════════════════════════════

class VirLspServer:
    """Vir Language Server — handles LSP messages."""

    def __init__(self) -> None:
        self.docs = DocumentStore()
        self.running = True
        self.initialized = False

    def handle(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        """Handle a single JSON-RPC message. Returns response or None."""
        method = msg.get("method", "")
        id_ = msg.get("id")
        params = msg.get("params", {})

        # ── Lifecycle ──────────────────────────────────────
        if method == "initialize":
            self.initialized = True
            return _response(id_, {
                "capabilities": {
                    "textDocumentSync": 1,  # Full sync
                    "completionProvider": {"triggerCharacters": [".", ":"]},
                    "hoverProvider": True,
                    "definitionProvider": True,
                },
                "serverInfo": {"name": "vir-lsp", "version": "0.5.0"},
            })

        if method == "initialized":
            return None  # Notification, no response

        if method == "shutdown":
            self.running = False
            return _response(id_, None)

        if method == "exit":
            sys.exit(0)

        # ── Document sync ──────────────────────────────────
        if method == "textDocument/didOpen":
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            text = td.get("text", "")
            version = td.get("version", 0)
            self.docs.open(uri, text, version)
            # Publish diagnostics
            diag_msg = self._publish_diagnostics(uri, text)
            if diag_msg:
                _write_message(diag_msg)
            return None

        if method == "textDocument/didChange":
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            version = td.get("version", 0)
            changes = params.get("contentChanges", [])
            if changes:
                text = changes[-1].get("text", "")
                self.docs.update(uri, text, version)
                diag_msg = self._publish_diagnostics(uri, text)
                if diag_msg:
                    _write_message(diag_msg)
            return None

        if method == "textDocument/didClose":
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            self.docs.close(uri)
            return None

        # ── Completion ─────────────────────────────────────
        if method == "textDocument/completion":
            uri = params.get("textDocument", {}).get("uri", "")
            pos = params.get("position", {})
            line = pos.get("line", 0)
            col = pos.get("character", 0)
            doc = self.docs.get(uri)
            if doc:
                items = get_completions(doc.text, line, col)
                return _response(id_, {"isIncomplete": False, "items": items})
            return _response(id_, {"isIncomplete": False, "items": []})

        # ── Hover ──────────────────────────────────────────
        if method == "textDocument/hover":
            uri = params.get("textDocument", {}).get("uri", "")
            pos = params.get("position", {})
            line = pos.get("line", 0)
            col = pos.get("character", 0)
            doc = self.docs.get(uri)
            if doc:
                hover_text = get_hover(doc.text, line, col)
                if hover_text:
                    return _response(id_, {
                        "contents": {"kind": "markdown", "value": hover_text}
                    })
            return _response(id_, None)

        # ── Go to Definition ───────────────────────────────
        if method == "textDocument/definition":
            uri = params.get("textDocument", {}).get("uri", "")
            pos = params.get("position", {})
            line = pos.get("line", 0)
            col = pos.get("character", 0)
            doc = self.docs.get(uri)
            if doc:
                defn = find_definition(doc.text, line, col)
                if defn:
                    return _response(id_, {
                        "uri": uri,
                        "range": {
                            "start": {"line": defn[0], "character": defn[1]},
                            "end": {"line": defn[0], "character": defn[1]},
                        },
                    })
            return _response(id_, None)

        # ── Unknown method ─────────────────────────────────
        if id_ is not None:
            return _error(id_, -32601, f"Method not found: {method}")
        return None

    def _publish_diagnostics(self, uri: str, text: str) -> dict | None:
        diagnostics, _ = analyze_source(text)
        return _notification("textDocument/publishDiagnostics", {
            "uri": uri,
            "diagnostics": [d.to_lsp() for d in diagnostics],
        })

    def run(self) -> None:
        """Main loop — read messages and dispatch."""
        while self.running:
            msg = _read_message()
            if msg is None:
                break
            response = self.handle(msg)
            if response is not None:
                _write_message(response)


def main() -> None:
    """Entry point for vir-lsp server."""
    server = VirLspServer()
    server.run()

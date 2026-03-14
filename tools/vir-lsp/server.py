"""
Vir LSP Server — Language Server Protocol implementation
=========================================================
Phase 3 Task F1: Real-time IDE support for .vri files.

Features:
  - textDocument/publishDiagnostics — parse error detection
  - textDocument/completion — keyword + symbol completion
  - textDocument/definition — jump to function/entity definition
  - textDocument/hover — type signature + doc comments
  - textDocument/documentSymbol — outline view

Transport: stdio (JSON-RPC 2.0)
"""

from __future__ import annotations

import json
import sys
import os
from dataclasses import dataclass, field
from typing import Any

# Add project root for imports
_VIR_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _VIR_ROOT not in sys.path:
    sys.path.insert(0, _VIR_ROOT)


# ═══════════════════════════════════════════════════════════
# LSP Protocol Types
# ═══════════════════════════════════════════════════════════

@dataclass
class Position:
    line: int = 0
    character: int = 0

    def to_dict(self) -> dict:
        return {"line": self.line, "character": self.character}


@dataclass
class Range:
    start: Position = field(default_factory=Position)
    end: Position = field(default_factory=Position)

    def to_dict(self) -> dict:
        return {"start": self.start.to_dict(), "end": self.end.to_dict()}


@dataclass
class Diagnostic:
    range: Range
    message: str
    severity: int = 1  # 1=Error, 2=Warning, 3=Info, 4=Hint

    def to_dict(self) -> dict:
        return {
            "range": self.range.to_dict(),
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class CompletionItem:
    label: str
    kind: int = 1  # 1=Text, 2=Method, 3=Function, 6=Variable, 8=Keyword
    detail: str = ""

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"label": self.label, "kind": self.kind}
        if self.detail:
            d["detail"] = self.detail
        return d


@dataclass
class SymbolInfo:
    name: str
    kind: int  # 12=Function, 5=Class, 23=Struct, 10=Enum
    range: Range = field(default_factory=Range)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "range": self.range.to_dict(),
            "selectionRange": self.range.to_dict(),
        }


# ═══════════════════════════════════════════════════════════
# Document Analysis
# ═══════════════════════════════════════════════════════════

class DocumentAnalyzer:
    """Analyze .vri files for LSP features."""

    # Core Vir keywords for completion
    VIR_KEYWORDS = [
        "func", "entity", "enum", "trait", "impl", "method", "class",
        "if", "eif", "else", "when", "loop", "case", "end",
        "out", "in", "break", "skip", "try", "error", "fallback",
        "var", "const", "include", "import", "export", "from", "get",
        "async", "task", "wait", "spawn", "await",
        "print", "input", "true", "false", "none",
        "int", "float", "string", "bool", "array", "map",
    ]

    def __init__(self) -> None:
        # uri → source text
        self._documents: dict[str, str] = {}
        # uri → list of extracted symbols
        self._symbols: dict[str, list[SymbolInfo]] = {}

    def open_document(self, uri: str, text: str) -> list[Diagnostic]:
        """Open or update a document, return diagnostics."""
        self._documents[uri] = text
        diagnostics = self._parse_diagnostics(text)
        self._symbols[uri] = self._extract_symbols(text)
        return diagnostics

    def close_document(self, uri: str) -> None:
        self._documents.pop(uri, None)
        self._symbols.pop(uri, None)

    def get_completions(self, uri: str, pos: Position) -> list[CompletionItem]:
        """Get completion items at position."""
        items = []
        # Keywords
        for kw in self.VIR_KEYWORDS:
            items.append(CompletionItem(kw, kind=14, detail="keyword"))
        # Symbols from current document
        for sym in self._symbols.get(uri, []):
            kind_map = {12: 3, 5: 7, 23: 22, 10: 13}  # LSP completion kinds
            items.append(CompletionItem(
                sym.name, kind=kind_map.get(sym.kind, 1), detail="symbol"
            ))
        return items

    def get_definition(self, uri: str, pos: Position) -> Range | None:
        """Find definition of symbol at position."""
        text = self._documents.get(uri, "")
        lines = text.split("\n")
        if pos.line >= len(lines):
            return None
        line = lines[pos.line]
        # Extract word at cursor
        word = self._word_at(line, pos.character)
        if not word:
            return None
        # Search symbols
        for sym in self._symbols.get(uri, []):
            if sym.name == word:
                return sym.range
        return None

    def get_hover(self, uri: str, pos: Position) -> str | None:
        """Get hover info at position."""
        text = self._documents.get(uri, "")
        lines = text.split("\n")
        if pos.line >= len(lines):
            return None
        word = self._word_at(lines[pos.line], pos.character)
        if not word:
            return None
        for sym in self._symbols.get(uri, []):
            if sym.name == word:
                kind_names = {12: "func", 5: "class", 23: "entity", 10: "enum"}
                return f"```vir\n{kind_names.get(sym.kind, 'symbol')} {sym.name}\n```"
        return None

    def get_document_symbols(self, uri: str) -> list[SymbolInfo]:
        """Get all symbols in a document."""
        return self._symbols.get(uri, [])

    def _parse_diagnostics(self, text: str) -> list[Diagnostic]:
        """Parse text and collect error diagnostics."""
        diagnostics = []
        lines = text.split("\n")
        # Track block nesting
        block_stack: list[tuple[str, int]] = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Check for unmatched blocks
            for kw in ("func", "entity", "enum", "trait", "impl",
                       "if", "when", "loop", "case", "class", "method"):
                if stripped.startswith(kw + " ") or stripped.startswith(kw + ":"):
                    block_stack.append((kw, i))
                    break

            if stripped == "end" or stripped == "end;":
                if block_stack:
                    block_stack.pop()
                else:
                    diagnostics.append(Diagnostic(
                        Range(Position(i, 0), Position(i, len(stripped))),
                        "Unexpected 'end' without matching block",
                        severity=1,
                    ))

            # Check for common syntax errors
            if "==" in stripped and stripped.count("=") == 1 and "!=" not in stripped:
                if not stripped.startswith("var ") and not stripped.startswith("const "):
                    pass  # assignment is fine

        # Unclosed blocks
        for kw, line_num in block_stack:
            diagnostics.append(Diagnostic(
                Range(Position(line_num, 0), Position(line_num, len(kw))),
                f"Unclosed '{kw}' block — missing 'end'",
                severity=1,
            ))

        return diagnostics

    def _extract_symbols(self, text: str) -> list[SymbolInfo]:
        """Extract function, entity, enum, trait symbols from source."""
        symbols = []
        lines = text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            # func name: or func name<T>:
            if stripped.startswith("func "):
                name = self._extract_name(stripped[5:])
                if name:
                    symbols.append(SymbolInfo(
                        name, 12, Range(Position(i, 0), Position(i, len(stripped)))
                    ))
            elif stripped.startswith("entity "):
                name = self._extract_name(stripped[7:])
                if name:
                    symbols.append(SymbolInfo(
                        name, 23, Range(Position(i, 0), Position(i, len(stripped)))
                    ))
            elif stripped.startswith("enum "):
                name = self._extract_name(stripped[5:])
                if name:
                    symbols.append(SymbolInfo(
                        name, 10, Range(Position(i, 0), Position(i, len(stripped)))
                    ))
            elif stripped.startswith("trait "):
                name = self._extract_name(stripped[6:])
                if name:
                    symbols.append(SymbolInfo(
                        name, 5, Range(Position(i, 0), Position(i, len(stripped)))
                    ))
            elif stripped.startswith("class "):
                name = self._extract_name(stripped[6:])
                if name:
                    symbols.append(SymbolInfo(
                        name, 5, Range(Position(i, 0), Position(i, len(stripped)))
                    ))
        return symbols

    @staticmethod
    def _extract_name(text: str) -> str:
        """Extract identifier name from text after keyword."""
        name = []
        for ch in text:
            if ch.isalnum() or ch == "_":
                name.append(ch)
            else:
                break
        return "".join(name)

    @staticmethod
    def _word_at(line: str, col: int) -> str:
        """Extract the word at column position."""
        if col >= len(line):
            return ""
        # Expand left
        start = col
        while start > 0 and (line[start - 1].isalnum() or line[start - 1] == "_"):
            start -= 1
        # Expand right
        end = col
        while end < len(line) and (line[end].isalnum() or line[end] == "_"):
            end += 1
        return line[start:end]


# ═══════════════════════════════════════════════════════════
# JSON-RPC Transport
# ═══════════════════════════════════════════════════════════

class JsonRpcTransport:
    """LSP stdio transport — reads/writes JSON-RPC messages."""

    def __init__(self, input_stream=None, output_stream=None):
        self._in = input_stream or sys.stdin.buffer
        self._out = output_stream or sys.stdout.buffer

    def read_message(self) -> dict | None:
        """Read one JSON-RPC message from stdin."""
        headers: dict[str, str] = {}
        while True:
            line = self._in.readline().decode("utf-8")
            if not line:
                return None
            line = line.strip()
            if not line:
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()

        content_length = int(headers.get("Content-Length", "0"))
        if content_length == 0:
            return None

        body = self._in.read(content_length).decode("utf-8")
        return json.loads(body)

    def write_message(self, msg: dict) -> None:
        """Write one JSON-RPC message to stdout."""
        body = json.dumps(msg).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        self._out.write(header)
        self._out.write(body)
        self._out.flush()


# ═══════════════════════════════════════════════════════════
# LSP Server
# ═══════════════════════════════════════════════════════════

class VirLSPServer:
    """
    Vir Language Server — implements LSP protocol over stdio.

    Supported methods:
      - initialize / shutdown / exit
      - textDocument/didOpen, didChange, didClose
      - textDocument/completion
      - textDocument/definition
      - textDocument/hover
      - textDocument/documentSymbol
    """

    def __init__(self) -> None:
        self.transport = JsonRpcTransport()
        self.analyzer = DocumentAnalyzer()
        self._initialized = False
        self._shutdown = False

    def run(self) -> None:
        """Main server loop."""
        while not self._shutdown:
            msg = self.transport.read_message()
            if msg is None:
                break
            self._handle_message(msg)

    def _handle_message(self, msg: dict) -> None:
        """Dispatch a JSON-RPC message."""
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        # Request (has id) → must respond
        if msg_id is not None:
            result = self._handle_request(method, params)
            self.transport.write_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result,
            })
        else:
            # Notification (no id)
            self._handle_notification(method, params)

    def _handle_request(self, method: str, params: dict) -> Any:
        """Handle a request that needs a response."""
        if method == "initialize":
            self._initialized = True
            return {
                "capabilities": {
                    "textDocumentSync": 1,  # Full sync
                    "completionProvider": {"triggerCharacters": [".", "<"]},
                    "definitionProvider": True,
                    "hoverProvider": True,
                    "documentSymbolProvider": True,
                },
                "serverInfo": {"name": "vir-lsp", "version": "0.1.0"},
            }
        elif method == "shutdown":
            self._shutdown = True
            return None
        elif method == "textDocument/completion":
            uri = params.get("textDocument", {}).get("uri", "")
            pos = params.get("position", {})
            items = self.analyzer.get_completions(
                uri, Position(pos.get("line", 0), pos.get("character", 0))
            )
            return {"isIncomplete": False, "items": [i.to_dict() for i in items]}
        elif method == "textDocument/definition":
            uri = params.get("textDocument", {}).get("uri", "")
            pos = params.get("position", {})
            result = self.analyzer.get_definition(
                uri, Position(pos.get("line", 0), pos.get("character", 0))
            )
            if result:
                return {"uri": uri, "range": result.to_dict()}
            return None
        elif method == "textDocument/hover":
            uri = params.get("textDocument", {}).get("uri", "")
            pos = params.get("position", {})
            content = self.analyzer.get_hover(
                uri, Position(pos.get("line", 0), pos.get("character", 0))
            )
            if content:
                return {"contents": {"kind": "markdown", "value": content}}
            return None
        elif method == "textDocument/documentSymbol":
            uri = params.get("textDocument", {}).get("uri", "")
            symbols = self.analyzer.get_document_symbols(uri)
            return [s.to_dict() for s in symbols]
        return None

    def _handle_notification(self, method: str, params: dict) -> None:
        """Handle a notification (no response needed)."""
        if method == "initialized":
            pass
        elif method == "exit":
            self._shutdown = True
        elif method == "textDocument/didOpen":
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            text = td.get("text", "")
            diagnostics = self.analyzer.open_document(uri, text)
            self._publish_diagnostics(uri, diagnostics)
        elif method == "textDocument/didChange":
            uri = params.get("textDocument", {}).get("uri", "")
            changes = params.get("contentChanges", [])
            if changes:
                text = changes[-1].get("text", "")
                diagnostics = self.analyzer.open_document(uri, text)
                self._publish_diagnostics(uri, diagnostics)
        elif method == "textDocument/didClose":
            uri = params.get("textDocument", {}).get("uri", "")
            self.analyzer.close_document(uri)

    def _publish_diagnostics(self, uri: str, diagnostics: list[Diagnostic]) -> None:
        """Push diagnostics to the client."""
        self.transport.write_message({
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": uri,
                "diagnostics": [d.to_dict() for d in diagnostics],
            },
        })


def main():
    """Entry point for the LSP server."""
    server = VirLSPServer()
    server.run()


if __name__ == "__main__":
    main()

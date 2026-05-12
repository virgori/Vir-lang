"""
test_phase5.py — Tests for Phase V features.
==============================================
Package Manager, LSP, WASM Codegen, DAP, REPL.
"""

from __future__ import annotations

import json
import struct
import tempfile
from pathlib import Path

import pytest


# ═══════════════════════════════════════════════════════════
# F1: Package Manager
# ═══════════════════════════════════════════════════════════

class TestSemVer:
    def test_parse(self):
        from src.pkg.manifest import parse_semver, SemVer
        v = parse_semver("1.2.3")
        assert v == SemVer(1, 2, 3)

    def test_compare(self):
        from src.pkg.manifest import SemVer
        assert SemVer(1, 0, 0) < SemVer(2, 0, 0)
        assert SemVer(1, 2, 0) < SemVer(1, 3, 0)
        assert SemVer(1, 2, 3) == SemVer(1, 2, 3)

    def test_str(self):
        from src.pkg.manifest import SemVer
        assert str(SemVer(1, 2, 3)) == "1.2.3"


class TestVersionReq:
    def test_caret(self):
        from src.pkg.manifest import parse_version_req, SemVer
        req = parse_version_req("^1.2.0")
        assert req.matches(SemVer(1, 2, 0))
        assert req.matches(SemVer(1, 9, 0))
        assert not req.matches(SemVer(2, 0, 0))
        assert not req.matches(SemVer(1, 1, 0))

    def test_tilde(self):
        from src.pkg.manifest import parse_version_req, SemVer
        req = parse_version_req("~1.2.0")
        assert req.matches(SemVer(1, 2, 5))
        assert not req.matches(SemVer(1, 3, 0))

    def test_exact(self):
        from src.pkg.manifest import parse_version_req, SemVer
        req = parse_version_req("=1.0.0")
        assert req.matches(SemVer(1, 0, 0))
        assert not req.matches(SemVer(1, 0, 1))

    def test_gte(self):
        from src.pkg.manifest import parse_version_req, SemVer
        req = parse_version_req(">=0.5.0")
        assert req.matches(SemVer(0, 5, 0))
        assert req.matches(SemVer(1, 0, 0))
        assert not req.matches(SemVer(0, 4, 9))


class TestManifest:
    def test_parse_toml(self):
        from src.pkg.manifest import parse_manifest
        toml = '''
[package]
name = "my-app"
version = "1.0.0"
description = "Test project"

[dependencies]
http = "^1.2.0"
json = ">=0.5.0"

[dev-dependencies]
test = "^2.0.0"
'''
        m = parse_manifest(toml)
        assert m.name == "my-app"
        assert str(m.version) == "1.0.0"
        assert len(m.dependencies) == 2
        assert m.dependencies[0].name == "http"
        assert len(m.dev_dependencies) == 1

    def test_write_and_reload(self, tmp_path):
        from src.pkg.manifest import Manifest, SemVer, Dependency, VersionReq, write_manifest, load_manifest

        m = Manifest(
            name="test-pkg",
            version=SemVer(0, 2, 0),
            dependencies=[
                Dependency(name="net", version_req=VersionReq("^", SemVer(1, 0, 0))),
            ],
        )
        write_manifest(m, tmp_path / "vir.toml")
        loaded = load_manifest(tmp_path / "vir.toml")
        assert loaded.name == "test-pkg"
        assert str(loaded.version) == "0.2.0"
        assert len(loaded.dependencies) == 1

    def test_init_manifest(self, tmp_path):
        from src.pkg.manifest import init_manifest
        m = init_manifest(tmp_path, "hello")
        assert m.name == "hello"
        assert (tmp_path / "vir.toml").exists()
        assert (tmp_path / "src" / "main.vri").exists()


class TestResolver:
    def test_basic_resolve(self):
        from src.pkg.manifest import Manifest, SemVer, Dependency, VersionReq
        from src.pkg.resolver import PackageIndex, resolve

        index = PackageIndex()
        index.add("http", SemVer(1, 2, 3), [])
        index.add("http", SemVer(1, 1, 0), [])

        manifest = Manifest(
            name="app",
            dependencies=[
                Dependency(name="http", version_req=VersionReq("^", SemVer(1, 0, 0))),
            ],
        )

        resolved = resolve(manifest, index)
        assert len(resolved) == 1
        assert resolved[0].name == "http"
        assert resolved[0].version == SemVer(1, 2, 3)  # picks highest

    def test_transitive_deps(self):
        from src.pkg.manifest import Manifest, SemVer, Dependency, VersionReq
        from src.pkg.resolver import PackageIndex, resolve

        index = PackageIndex()
        index.add("http", SemVer(1, 0, 0), [
            Dependency(name="net", version_req=VersionReq(">=", SemVer(0, 5, 0))),
        ])
        index.add("net", SemVer(0, 8, 0), [])

        manifest = Manifest(
            name="app",
            dependencies=[
                Dependency(name="http", version_req=VersionReq("^", SemVer(1, 0, 0))),
            ],
        )

        resolved = resolve(manifest, index)
        names = {r.name for r in resolved}
        assert "http" in names
        assert "net" in names

    def test_no_compatible_version(self):
        from src.pkg.manifest import Manifest, SemVer, Dependency, VersionReq
        from src.pkg.resolver import PackageIndex, resolve, ResolveError

        index = PackageIndex()
        index.add("x", SemVer(0, 1, 0), [])

        manifest = Manifest(
            name="app",
            dependencies=[
                Dependency(name="x", version_req=VersionReq("^", SemVer(2, 0, 0))),
            ],
        )

        with pytest.raises(ResolveError):
            resolve(manifest, index)


class TestLockfile:
    def test_round_trip(self, tmp_path):
        from src.pkg.lockfile import LockFile, LockEntry, write_lockfile, load_lockfile
        from src.pkg.manifest import SemVer

        lf = LockFile(entries=[
            LockEntry(name="http", version=SemVer(1, 2, 3), deps=("net",)),
            LockEntry(name="net", version=SemVer(0, 8, 0)),
        ])
        write_lockfile(lf, tmp_path / "vir.lock")
        loaded = load_lockfile(tmp_path / "vir.lock")
        assert loaded is not None
        assert len(loaded.entries) == 2
        assert loaded.get("http") is not None
        assert loaded.get("http").version == SemVer(1, 2, 3)


# ═══════════════════════════════════════════════════════════
# F2: LSP Server
# ═══════════════════════════════════════════════════════════

class TestLspAnalysis:
    def test_analyze_source_basic(self):
        from src.lsp.server import analyze_source
        source = '''func hello:
    print("hi");
end
'''
        diags, symbols = analyze_source(source)
        assert len(diags) == 0
        assert "hello" in symbols

    def test_analyze_unclosed_block(self):
        from src.lsp.server import analyze_source
        source = '''func broken:
    print("no end");
'''
        diags, symbols = analyze_source(source)
        assert len(diags) == 1
        assert "Unclosed" in diags[0].message

    def test_completions(self):
        from src.lsp.server import get_completions
        source = "fu"
        items = get_completions(source, 0, 2)
        labels = [i["label"] for i in items]
        assert "func" in labels

    def test_hover_keyword(self):
        from src.lsp.server import get_hover
        source = "func test:\nend"
        hover = get_hover(source, 0, 0)
        assert hover is not None
        assert "func" in hover

    def test_find_definition(self):
        from src.lsp.server import find_definition
        source = "func hello:\n    print(hello);\nend"
        defn = find_definition(source, 1, 10)
        assert defn is not None
        assert defn[0] == 0  # line 0


class TestLspServer:
    def test_handle_initialize(self):
        from src.lsp.server import VirLspServer
        server = VirLspServer()
        resp = server.handle({
            "jsonrpc": "2.0", "id": 1,
            "method": "initialize",
            "params": {"capabilities": {}},
        })
        assert resp is not None
        assert resp["result"]["capabilities"]["completionProvider"]

    def test_handle_shutdown(self):
        from src.lsp.server import VirLspServer
        server = VirLspServer()
        server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        resp = server.handle({"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}})
        assert resp is not None
        assert server.running is False


# ═══════════════════════════════════════════════════════════
# F3: WASM Codegen
# ═══════════════════════════════════════════════════════════

class TestWasmCodegen:
    def test_empty_module(self):
        from src.backend.codegen.codegen_wasm import compile_to_wasm
        from src.ir.instructions.q_ir import QModule
        module = QModule(name="test")
        wasm = compile_to_wasm(module)
        assert wasm[:4] == b"\x00asm"
        assert wasm[4:8] == b"\x01\x00\x00\x00"

    def test_simple_function(self):
        from src.backend.codegen.codegen_wasm import compile_to_wasm
        from src.ir.instructions.q_ir import QModule, QFunction, QInstruction, Opcode, VReg, Immediate
        module = QModule(name="test")
        func = QFunction(name="add", params=[VReg(0), VReg(1)])
        func.append(QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)))
        func.append(QInstruction(Opcode.Q_RET, src1=VReg(2)))
        module.add_function(func)
        wasm = compile_to_wasm(module)
        assert len(wasm) > 8
        # Valid WASM header
        assert wasm[:4] == b"\x00asm"

    def test_write_wasm(self, tmp_path):
        from src.backend.codegen.codegen_wasm import write_wasm
        from src.ir.instructions.q_ir import QModule
        module = QModule(name="test")
        path = str(tmp_path / "test.wasm")
        write_wasm(module, path)
        assert Path(path).exists()
        data = Path(path).read_bytes()
        assert data[:4] == b"\x00asm"


class TestWasmLeb128:
    def test_uleb128(self):
        from src.backend.codegen.codegen_wasm import _uleb128
        assert _uleb128(0) == b"\x00"
        assert _uleb128(127) == b"\x7f"
        assert _uleb128(128) == b"\x80\x01"

    def test_sleb128(self):
        from src.backend.codegen.codegen_wasm import _sleb128
        assert _sleb128(0) == b"\x00"
        assert _sleb128(-1) == b"\x7f"
        assert _sleb128(64) == b"\xc0\x00"


# ═══════════════════════════════════════════════════════════
# F4: DAP Server
# ═══════════════════════════════════════════════════════════

class TestDapServer:
    def test_initialize(self):
        from src.dap.server import VirDapServer
        server = VirDapServer()
        responses = server.handle({
            "seq": 1, "type": "request", "command": "initialize",
            "arguments": {"clientID": "test"},
        })
        assert len(responses) == 2
        resp = responses[0]
        assert resp["success"] is True
        assert responses[1]["event"] == "initialized"

    def test_launch(self, tmp_path):
        from src.dap.server import VirDapServer
        # Create a test file
        test_file = tmp_path / "test.vri"
        test_file.write_text("func main:\n    print(42);\nend\n")

        server = VirDapServer()
        server.handle({"seq": 1, "type": "request", "command": "initialize", "arguments": {}})
        responses = server.handle({
            "seq": 2, "type": "request", "command": "launch",
            "arguments": {"program": str(test_file)},
        })
        assert any(r.get("event") == "stopped" for r in responses)

    def test_set_breakpoints(self, tmp_path):
        from src.dap.server import VirDapServer
        test_file = tmp_path / "test.vri"
        test_file.write_text("func main:\n    let x = 1;\n    let y = 2;\nend\n")

        server = VirDapServer()
        server.handle({"seq": 1, "type": "request", "command": "initialize", "arguments": {}})
        responses = server.handle({
            "seq": 2, "type": "request", "command": "setBreakpoints",
            "arguments": {
                "source": {"path": str(test_file)},
                "breakpoints": [{"line": 2}],
            },
        })
        resp = responses[0]
        assert resp["success"]
        assert len(resp["body"]["breakpoints"]) == 1

    def test_threads(self):
        from src.dap.server import VirDapServer
        server = VirDapServer()
        server.handle({"seq": 1, "type": "request", "command": "initialize", "arguments": {}})
        responses = server.handle({
            "seq": 2, "type": "request", "command": "threads", "arguments": {},
        })
        assert responses[0]["body"]["threads"][0]["name"] == "main"

    def test_next_step(self, tmp_path):
        from src.dap.server import VirDapServer
        test_file = tmp_path / "test.vri"
        test_file.write_text("line1\nline2\nline3\n")

        server = VirDapServer()
        server.handle({"seq": 1, "type": "request", "command": "initialize", "arguments": {}})
        server.handle({"seq": 2, "type": "request", "command": "launch",
                       "arguments": {"program": str(test_file)}})
        responses = server.handle({"seq": 3, "type": "request", "command": "next", "arguments": {}})
        assert any(r.get("event") == "stopped" for r in responses)


# ═══════════════════════════════════════════════════════════
# F5: TargetArch.WASM in codegen.py
# ═══════════════════════════════════════════════════════════

class TestTargetArchWasm:
    def test_wasm_in_enum(self):
        from src.backend.codegen.codegen import TargetArch
        assert TargetArch.WASM.value == "wasm32"
        assert len(TargetArch) == 3

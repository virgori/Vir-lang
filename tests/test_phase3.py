"""
test_phase3.py – Phase 3 Comprehensive Test Suite
====================================================
Tests for all Phase 3 pillars (E-I):
  E: Type System (Generics, Traits, Enum, Pattern Matching, Error Handling)
  F: Tooling (LSP, Formatter, Package Manager, Debugger)
  G: Stdlib Native (tested via headers/compilation)
  H: Bootstrap (Optimizer, Memory, x86_64 codegen)
  I: Polish (Vietnamese errors, syntax nodes)
"""

import pytest
import sys
import json
from pathlib import Path

# Add tools directories to path for import (dirs use dashes)
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools" / "vir-fmt"))
sys.path.insert(0, str(_ROOT / "tools" / "vir-pkg"))
sys.path.insert(0, str(_ROOT / "tools" / "vir-dbg"))
sys.path.insert(0, str(_ROOT / "tools" / "vir-lsp"))

# ════════════════════════════════════════════════════════════
# Pillar E: Type System
# ════════════════════════════════════════════════════════════

class TestGenericsAST:
    """E1: Generic type system AST nodes."""

    def test_generic_param_creation(self):
        from src.frontend.parser.parser import GenericParam
        gp = GenericParam(name="T", bounds=["Display", "Clone"])
        assert gp.name == "T"
        assert gp.bounds == ["Display", "Clone"]

    def test_generic_type_creation(self):
        from src.frontend.parser.parser import GenericType
        gt = GenericType(base_name="Vec", type_args=["i64"])
        assert gt.base_name == "Vec"
        assert gt.type_args == ["i64"]

    def test_func_with_generics(self):
        from src.frontend.parser.parser import FuncDefNode, GenericParam
        fn = FuncDefNode(
            name="identity",
            generic_params=[GenericParam(name="T")],
            params=["x"],
            body=[],
        )
        assert fn.name == "identity"
        assert len(fn.generic_params) == 1
        assert fn.generic_params[0].name == "T"

    def test_entity_with_generics(self):
        from src.frontend.parser.parser import EntityDefNode, GenericParam
        e = EntityDefNode(
            name="Vec",
            generic_params=[GenericParam(name="T")],
            fields=[("data", "T"), ("len", "int")],
        )
        assert e.name == "Vec"
        assert len(e.generic_params) == 1

    def test_enum_def_node(self):
        from src.frontend.parser.parser import EnumDefNode, GenericParam
        e = EnumDefNode(
            name="Option",
            generic_params=[GenericParam(name="T")],
            variants=[("Some", ["T"]), ("None", [])],
        )
        assert e.name == "Option"
        assert len(e.variants) == 2
        assert e.variants[0] == ("Some", ["T"])
        assert e.variants[1] == ("None", [])


class TestTraits:
    """E2: Trait system."""

    def test_trait_def_node(self):
        from src.frontend.parser.parser import TraitDefNode, FuncDefNode
        t = TraitDefNode(
            name="Display",
            methods=[FuncDefNode(name="to_string", params=["self"])],
        )
        assert t.name == "Display"
        assert len(t.methods) == 1

    def test_impl_node(self):
        from src.frontend.parser.parser import ImplNode, FuncDefNode
        impl = ImplNode(
            trait_name="Display",
            target_type="Vec",
            methods=[FuncDefNode(name="to_string", params=["self"])],
        )
        assert impl.trait_name == "Display"
        assert impl.target_type == "Vec"

    def test_trait_resolver(self):
        from src.ir.trait_resolve import TraitResolver, TraitDef, TraitMethod, ImplDef
        tr = TraitResolver()

        # Register trait
        tr.register_trait(TraitDef(name="Display", methods=[TraitMethod(name="to_string", param_types=["self"], return_type="str")]))
        assert tr.get_trait("Display") is not None

        # Register impl
        tr.register_impl(ImplDef(trait_name="Display", target_type="Vec_i64", methods={
            "to_string": "Vec_i64_to_string",
        }))

        # Resolve
        resolved = tr.resolve("Display", "to_string", "Vec_i64")
        assert resolved == "Vec_i64_to_string"

    def test_trait_resolver_missing(self):
        from src.ir.trait_resolve import TraitResolver, TraitDef, TraitMethod
        tr = TraitResolver()
        tr.register_trait(TraitDef(name="Display", methods=[TraitMethod(name="to_string", param_types=["self"], return_type="str")]))
        resolved = tr.resolve("Display", "to_string", "int")
        assert resolved is None


class TestPatternMatch:
    """E3: Pattern matching AST nodes."""

    def test_match_node(self):
        from src.frontend.parser.parser import MatchNode, NumberLiteral, PrintNode
        m = MatchNode(
            expr=NumberLiteral(value=42),
            arms=[
                (NumberLiteral(value=1), [PrintNode(expr=NumberLiteral(value=1))]),
                (NumberLiteral(value=2), [PrintNode(expr=NumberLiteral(value=2))]),
            ],
            else_body=[PrintNode(expr=NumberLiteral(value=0))],
        )
        assert len(m.arms) == 2
        assert len(m.else_body) == 1

    def test_closure_node(self):
        from src.frontend.parser.parser import ClosureNode
        c = ClosureNode(params=["x", "y"], body=[])
        assert c.params == ["x", "y"]

    def test_propagate_node(self):
        from src.frontend.parser.parser import PropagateNode, IdentifierRef
        p = PropagateNode(expr=IdentifierRef(name="result"))
        assert p.expr.name == "result"


class TestMonomorphization:
    """E1: Monomorphization pass."""

    def test_monomorph_key(self):
        from src.ir.monomorph import MonomorphKey
        k = MonomorphKey(base_name="identity", type_args=("i64",))
        assert k.mangled_name == "identity__i64"

    def test_monomorph_key_multi(self):
        from src.ir.monomorph import MonomorphKey
        k = MonomorphKey(base_name="map_fn", type_args=("str", "i64"))
        assert k.mangled_name == "map_fn__str_i64"


class TestQIROpcodes:
    """E: New Q-IR opcodes for Phase 3."""

    def test_new_opcodes_exist(self):
        from src.ir.instructions.q_ir import Opcode
        assert hasattr(Opcode, "Q_TYPE_META")
        assert hasattr(Opcode, "Q_MONOMORPH")
        assert hasattr(Opcode, "Q_TAG_CHECK")
        assert hasattr(Opcode, "Q_EXTRACT")
        assert hasattr(Opcode, "Q_TAG_NEW")
        assert hasattr(Opcode, "Q_VTABLE_CALL")
        assert hasattr(Opcode, "Q_CLOSURE_NEW")
        assert hasattr(Opcode, "Q_CLOSURE_CALL")
        assert hasattr(Opcode, "Q_CAPTURE")
        assert hasattr(Opcode, "Q_PROPAGATE")

    def test_qfunction_generic_params(self):
        from src.ir.instructions.q_ir import QFunction
        f = QFunction(name="identity", params=["x"],
                      generic_params=["T"],
                      type_constraints={"T": ["Display"]})
        assert f.generic_params == ["T"]
        assert f.type_constraints == {"T": ["Display"]}

    def test_qmodule_registries(self):
        from src.ir.instructions.q_ir import QModule
        m = QModule()
        assert hasattr(m, "traits")
        assert hasattr(m, "impls")
        assert hasattr(m, "enums")


# ════════════════════════════════════════════════════════════
# Pillar F: Tooling
# ════════════════════════════════════════════════════════════

class TestFormatter:
    """F2: Code formatter."""

    def test_basic_format(self):
        from formatter import VirFormatter
        fmt = VirFormatter()
        source = "func   hello:\nprint 42;\nend"
        result = fmt.format(source)
        assert "    print" in result

    def test_indent_block(self):
        from formatter import VirFormatter
        fmt = VirFormatter()
        source = "func test:\nprint 1;\nif true\nprint 2;\nend\nend"
        result = fmt.format(source)
        lines = result.strip().split("\n")
        # func test: should be at indent 0
        assert lines[0] == "func test:"
        # Body should be indented
        assert lines[1].startswith("    ")

    def test_check_mode(self):
        from formatter import VirFormatter
        fmt = VirFormatter()
        formatted = "func test:\n    print 1;\nend\n"
        assert fmt.check(formatted)

    def test_strip_trailing_spaces(self):
        from formatter import VirFormatter
        fmt = VirFormatter()
        source = "func test:   \nprint 1;   \nend   "
        result = fmt.format(source)
        for line in result.split("\n"):
            assert line == line.rstrip()


class TestPackageManager:
    """F3: Package manager."""

    def test_manifest_parse(self):
        from manager import ManifestParser
        toml_text = """
[package]
name = "my-app"
version = "0.2.0"
entry = "src/main.vri"

[dependencies]
math_lib = "1.0.0"
"""
        m = ManifestParser.parse(toml_text)
        assert m.name == "my-app"
        assert m.version == "0.2.0"
        assert m.entry == "src/main.vri"
        assert len(m.dependencies) == 1
        assert m.dependencies[0].name == "math_lib"

    def test_manifest_generate(self):
        from manager import ManifestParser, PackageManifest
        m = PackageManifest(name="test", version="1.0.0")
        text = ManifestParser.generate(m)
        assert 'name = "test"' in text
        assert 'version = "1.0.0"' in text

    def test_manifest_roundtrip(self):
        from manager import ManifestParser, PackageManifest
        m = PackageManifest(name="roundtrip", version="3.1.4")
        text = ManifestParser.generate(m)
        m2 = ManifestParser.parse(text)
        assert m.name == m2.name
        assert m.version == m2.version


class TestDebugger:
    """F4: Debug adapter."""

    def test_breakpoint_management(self):
        from debugger import DebugState
        state = DebugState()
        bp = state.add_breakpoint("test.vri", 10)
        assert bp.id == 1
        assert bp.line == 10
        assert state.check_breakpoint("test.vri", 10) is not None
        assert state.check_breakpoint("test.vri", 20) is None

    def test_stack_frame(self):
        from debugger import DebugState
        state = DebugState()
        f1 = state.push_frame("main", "test.vri", 1)
        f2 = state.push_frame("helper", "test.vri", 20)
        assert len(state.frames) == 2
        popped = state.pop_frame()
        assert popped.name == "helper"
        assert len(state.frames) == 1

    def test_dap_initialize(self):
        from debugger import VirDebugAdapter
        adapter = VirDebugAdapter()
        resp = adapter.handle_request({
            "seq": 1,
            "type": "request",
            "command": "initialize",
            "arguments": {},
        })
        assert resp["success"]
        assert resp["body"]["supportsConfigurationDoneRequest"]

    def test_dap_launch(self):
        from debugger import VirDebugAdapter
        adapter = VirDebugAdapter()
        adapter.handle_request({"seq": 1, "command": "initialize", "arguments": {}})
        resp = adapter.handle_request({
            "seq": 2,
            "command": "launch",
            "arguments": {"program": "test.vri"},
        })
        assert resp["success"]
        assert adapter.state.stopped

    def test_dap_set_breakpoints(self):
        from debugger import VirDebugAdapter
        adapter = VirDebugAdapter()
        adapter.handle_request({"seq": 1, "command": "initialize", "arguments": {}})
        resp = adapter.handle_request({
            "seq": 2,
            "command": "setBreakpoints",
            "arguments": {
                "source": {"path": "test.vri"},
                "breakpoints": [{"line": 5}, {"line": 10}],
            },
        })
        assert resp["success"]
        assert len(resp["body"]["breakpoints"]) == 2


class TestLSPServer:
    """F1: LSP server."""

    def test_lsp_import_and_classes(self):
        from server import VirLSPServer, DocumentAnalyzer
        # Just verify the classes can be imported
        assert VirLSPServer is not None
        assert DocumentAnalyzer is not None

    def test_document_analyzer_symbols(self):
        from server import DocumentAnalyzer
        analyzer = DocumentAnalyzer()
        source = "func hello:\n    print 42;\nend\nentity Point:\n    x:int;\n    y:int;\nend"
        diags = analyzer.open_document("test.vri", source)
        symbols = analyzer.get_document_symbols("test.vri")
        names = [s.name for s in symbols]
        assert "hello" in names
        assert "Point" in names


# ════════════════════════════════════════════════════════════
# Pillar H: Bootstrap
# ════════════════════════════════════════════════════════════

class TestOptimizer:
    """H1: Q-IR optimizer."""

    def test_constant_folding(self):
        from src.ir.opt_passes import Optimizer
        from src.ir.instructions.q_ir import (
            Opcode, QInstruction, QFunction, QModule, VReg, Immediate,
        )
        mod = QModule()
        func = QFunction(name="test", params=[])
        # x = 3; y = 4; z = x + y → z should be folded to 7
        func.body = [
            QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(3)),
            QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(4)),
            QInstruction(opcode=Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
        ]
        mod.functions.append(func)
        opt = Optimizer()
        opt.optimize(mod)
        assert opt.stats.constants_folded >= 1

    def test_dead_code_elimination(self):
        from src.ir.opt_passes import Optimizer
        from src.ir.instructions.q_ir import (
            Opcode, QInstruction, QFunction, QModule, VReg, Immediate,
        )
        mod = QModule()
        func = QFunction(name="test", params=[])
        func.body = [
            QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(1)),
            QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(2)),
            QInstruction(opcode=Opcode.Q_PRINT, dest=VReg(0)),
        ]
        mod.functions.append(func)
        opt = Optimizer()
        opt.optimize(mod)
        assert opt.stats.dead_code_removed >= 1

    def test_strength_reduction_mul_power2(self):
        from src.ir.opt_passes import Optimizer
        from src.ir.instructions.q_ir import (
            Opcode, QInstruction, QFunction, QModule, VReg, Immediate,
        )
        mod = QModule()
        func = QFunction(name="test", params=[VReg(0)])
        # VReg(0) is a param (unknown value), so MUL can't be constant-folded
        func.body = [
            QInstruction(opcode=Opcode.Q_MUL, dest=VReg(1), src1=VReg(0), src2=Immediate(8)),
            QInstruction(opcode=Opcode.Q_PRINT, dest=VReg(1)),
        ]
        mod.functions.append(func)
        opt = Optimizer()
        opt.optimize(mod)
        assert opt.stats.strength_reduced >= 1


class TestX86Codegen:
    """H3: x86_64 code generation."""

    def test_basic_generation(self):
        from src.backend.codegen.codegen_x86 import X86_64Codegen
        from src.ir.instructions.q_ir import (
            Opcode, QInstruction, QFunction, QModule, VReg, Immediate, Label,
        )
        mod = QModule()
        func = QFunction(name="main", params=[])
        func.body = [
            QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(42)),
            QInstruction(opcode=Opcode.Q_PRINT, dest=VReg(0)),
            QInstruction(opcode=Opcode.Q_RET),
        ]
        mod.functions.append(func)

        cg = X86_64Codegen()
        asm = cg.generate(mod)
        assert "_vir_main:" in asm
        assert "movq $42" in asm or "$42.0" in asm
        assert "callq _printf" in asm
        assert "retq" in asm

    def test_arithmetic_ops(self):
        from src.backend.codegen.codegen_x86 import X86_64Codegen
        from src.ir.instructions.q_ir import (
            Opcode, QInstruction, QFunction, QModule, VReg, Immediate,
        )
        mod = QModule()
        func = QFunction(name="arith", params=[])
        func.body = [
            QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(10)),
            QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(3)),
            QInstruction(opcode=Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(opcode=Opcode.Q_SUB, dest=VReg(3), src1=VReg(0), src2=VReg(1)),
            QInstruction(opcode=Opcode.Q_MUL, dest=VReg(4), src1=VReg(0), src2=VReg(1)),
        ]
        mod.functions.append(func)

        cg = X86_64Codegen()
        asm = cg.generate(mod)
        assert "addq" in asm
        assert "subq" in asm
        assert "imulq" in asm

    def test_stats(self):
        from src.backend.codegen.codegen_x86 import X86_64Codegen
        from src.ir.instructions.q_ir import (
            Opcode, QInstruction, QFunction, QModule, VReg, Immediate,
        )
        mod = QModule()
        func = QFunction(name="main", params=[])
        func.body = [
            QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(1)),
            QInstruction(opcode=Opcode.Q_RET, dest=VReg(0)),
        ]
        mod.functions.append(func)

        cg = X86_64Codegen()
        cg.generate(mod)
        assert cg.stats.functions_emitted >= 1
        assert cg.stats.instructions_emitted > 0


# ════════════════════════════════════════════════════════════
# Pillar I: Polish
# ════════════════════════════════════════════════════════════

class TestVietnameseErrors:
    """I4: Vietnamese error messages."""

    def test_error_creation(self):
        from src.frontend.vi_errors import (
            VirError, ErrorCode, ErrorSeverity, SourceLocation,
        )
        err = VirError(
            code=ErrorCode.T001_TYPE_MISMATCH,
            params={"expected": "int", "actual": "str"},
            location=SourceLocation(file="test.vri", line=5, column=10),
        )
        msg_vi = err.message("vi")
        assert "int" in msg_vi
        assert "str" in msg_vi
        assert "mong đợi" in msg_vi

        msg_en = err.message("en")
        assert "expected" in msg_en

    def test_error_display(self):
        from src.frontend.vi_errors import (
            VirError, ErrorCode, SourceLocation,
        )
        err = VirError(
            code=ErrorCode.N001_UNDEFINED_VAR,
            params={"name": "x"},
            location=SourceLocation(file="test.vri", line=3, column=5),
            source_line="print x;",
        )
        display = err.display("vi")
        assert "x" in display
        assert "test.vri:3:5" in display
        assert "print x;" in display

    def test_error_collector(self):
        from src.frontend.vi_errors import ErrorCollector, ErrorCode
        ec = ErrorCollector(lang="vi")
        ec.add(ErrorCode.P001_UNEXPECTED_TOKEN, token="+")
        ec.add(ErrorCode.T001_TYPE_MISMATCH, expected="int", actual="str")
        assert ec.count == 2
        assert ec.has_errors()
        summary = ec.summary()
        assert "2 lỗi" in summary

    def test_english_fallback(self):
        from src.frontend.vi_errors import ErrorCollector, ErrorCode
        ec = ErrorCollector(lang="en")
        ec.add(ErrorCode.R001_DIVISION_BY_ZERO)
        display = ec.display_all()
        assert "Division by zero" in display


class TestTokenKinds:
    """I1: Syntax reconciliation — verify new token types."""

    def test_phase3_token_kinds(self):
        from src.lib.keywords import TokenKind
        assert hasattr(TokenKind, "ENUM_DEF")
        assert hasattr(TokenKind, "TRAIT_DEF")
        assert hasattr(TokenKind, "IMPL_BLOCK")
        assert hasattr(TokenKind, "WHERE")
        assert hasattr(TokenKind, "PIPE")
        assert hasattr(TokenKind, "DOUBLE_ARROW")
        assert hasattr(TokenKind, "FALLBACK")


# ════════════════════════════════════════════════════════════
# Integration: Full pipeline round-trips
# ════════════════════════════════════════════════════════════

class TestIntegration:
    """End-to-end integration tests."""

    def test_optimizer_then_codegen(self):
        """Optimize Q-IR then generate x86_64 assembly."""
        from src.ir.opt_passes import Optimizer
        from src.backend.codegen.codegen_x86 import X86_64Codegen
        from src.ir.instructions.q_ir import (
            Opcode, QInstruction, QFunction, QModule, VReg, Immediate,
        )
        mod = QModule()
        func = QFunction(name="main", params=[])
        func.body = [
            QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(5)),
            QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(10)),
            QInstruction(opcode=Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(opcode=Opcode.Q_PRINT, dest=VReg(2)),
            QInstruction(opcode=Opcode.Q_RET),
        ]
        mod.functions.append(func)

        opt = Optimizer()
        opt.optimize(mod)

        cg = X86_64Codegen()
        asm = cg.generate(mod)
        assert "_vir_main:" in asm
        assert "retq" in asm

    def test_monomorph_with_trait(self):
        """Test monomorphization + trait resolution together."""
        from src.ir.monomorph import MonomorphPass
        from src.ir.trait_resolve import TraitResolver, TraitDef, TraitMethod, ImplDef
        from src.ir.instructions.q_ir import (
            Opcode, QInstruction, QFunction, QModule, VReg, Immediate, Label,
        )

        # Setup
        tr = TraitResolver()
        tr.register_trait(TraitDef(name="Printable", methods=[TraitMethod(name="print", param_types=["self"], return_type="void")]))
        tr.register_impl(ImplDef(trait_name="Printable", target_type="i64", methods={"print": "i64_print"}))
        tr.register_impl(ImplDef(trait_name="Printable", target_type="str", methods={"print": "str_print"}))

        # Verify resolution
        assert tr.resolve("Printable", "print", "i64") == "i64_print"
        assert tr.resolve("Printable", "print", "str") == "str_print"

        # Monomorphization
        mod = QModule()
        generic = QFunction(name="show", params=[VReg(0)],
                            generic_params=["T"],
                            type_constraints={"T": ["Printable"]})
        generic.body = [
            QInstruction(opcode=Opcode.Q_VTABLE_CALL, dest=Label("Printable.print"), src1=VReg(0)),
        ]
        mod.functions.append(generic)

        # Create a non-generic caller
        caller = QFunction(name="main", params=[])
        caller.body = [
            QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(42)),
            QInstruction(opcode=Opcode.Q_MONOMORPH, dest=Label("show"), src1=VReg(0)),
        ]
        mod.functions.append(caller)

        mp = MonomorphPass()
        stats = mp.run(mod)
        assert stats.generic_funcs >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

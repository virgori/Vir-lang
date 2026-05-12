"""
parser.py – Vir v1.2 Parser (lib/sublib aware)
==================================================
Takes Token list (with canonical TokenKind) from NGramTokenizer
and produces an AST per the Vir Core Syntax Specification v1.2.

Key v1.2 grammar rules:
  - `func <name>:` ... `end`  (with `in()` / `out`)
  - `if` / `eif` / `else` ... `end`
  - `when <cond> loop` ... `end`
  - `loop` ... `end`
  - `entity <name>:` ... `end`
  - `method Entity.method:` ... `end`
  - `class <name>` ... `end`
  - `case <expr>` ... `end`
  - `map` ... `end`
  - `out <expr>;` replaces return
  - `skip;` replaces continue
  - `eif` replaces elif
  - `has <name>` forward declaration
  - `export func1, func2`
  - `share state1, state2`
  - `import ... get ... from <module>`
  - named arguments: `func(param=value; param=value)`
  - `task <name> wait <func>`
  - `async func <name>:` ... `end`
  - `var` block (module state, Pascal style)
  - `const <name>: <value>;`
  - `include <module>`
  - `# comment`, `## block comment ##`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.lib.keywords import TokenKind
from src.frontend.tokenizer.ngram_tokenizer import Token


# ═══════════════════════════════════════════════════════════
# AST Node Definitions (v1.2)
# ═══════════════════════════════════════════════════════════

@dataclass
class ASTNode:
    """Base AST node."""
    token: Optional[Token] = None


@dataclass
class ProgramNode(ASTNode):
    """Root of program — list of top-level statements."""
    statements: list[ASTNode] = field(default_factory=list)


# ── Module structure ───────────────────────────────────────

@dataclass
class IncludeNode(ASTNode):
    """include <module>"""
    module_name: str = ""


@dataclass
class ConstDeclNode(ASTNode):
    """const <name>: <value>;"""
    name: str = ""
    value: Optional[ASTNode] = None


@dataclass
class ModuleStateNode(ASTNode):
    """var block (module state, Pascal style).
    var
        counter:int;
        mode:string;
    """
    fields: list[tuple[str, str]] = field(default_factory=list)  # (name, type)


@dataclass
class ExportNode(ASTNode):
    """export func1, func2"""
    names: list[str] = field(default_factory=list)


@dataclass
class ShareNode(ASTNode):
    """share state1, state2"""
    names: list[str] = field(default_factory=list)


@dataclass
class ImportNode(ASTNode):
    """import func1, func2, get state1, state2 from module"""
    funcs: list[str] = field(default_factory=list)
    shared: list[str] = field(default_factory=list)   # after "get"
    module_name: str = ""


@dataclass
class HasDeclNode(ASTNode):
    """has <funcName> — forward declaration."""
    name: str = ""


# ── Function definitions ──────────────────────────────────

@dataclass
class FuncDefNode(ASTNode):
    """func <name><T>: in(<params>) ... out <expr>; end"""
    name: str = ""
    params: list[str] = field(default_factory=list)
    body: list[ASTNode] = field(default_factory=list)
    param_types: list[Optional[str]] = field(default_factory=list)
    return_type: Optional[str] = None
    is_async: bool = False
    generic_params: list = field(default_factory=list)  # list[GenericParam]


@dataclass
class InParamsNode(ASTNode):
    """in(a:int; b:int; result:int)"""
    params: list[tuple[str, Optional[str]]] = field(default_factory=list)


@dataclass
class OutNode(ASTNode):
    """out <expr>;"""
    expr: Optional[ASTNode] = None


# ── Entity / Method / Class ───────────────────────────────

@dataclass
class EntityDefNode(ASTNode):
    """entity <name><T>: field:type; ... end"""
    name: str = ""
    fields: list[tuple[str, str]] = field(default_factory=list)
    generic_params: list = field(default_factory=list)

@dataclass
class EntityNode(ASTNode):
    type_name: str = ""
    fields: list[tuple[str, ASTNode]] = field(default_factory=list)


@dataclass
class MethodDefNode(ASTNode):
    """method Entity.method: ... end"""
    entity_name: str = ""
    method_name: str = ""
    body: list[ASTNode] = field(default_factory=list)


@dataclass
class ClassDefNode(ASTNode):
    """class <name> entity method end"""
    name: str = ""
    entities: list[EntityDefNode] = field(default_factory=list)
    methods: list[MethodDefNode] = field(default_factory=list)


# ── Task / async ──────────────────────────────────────────

@dataclass
class TaskNode(ASTNode):
    """task <name> wait <asyncFunc>"""
    name: str = ""
    wait_func: str = ""


# ── Control flow ──────────────────────────────────────────

@dataclass
class IfNode(ASTNode):
    """if condition: ... eif condition: ... else ... end"""
    condition: Optional[ASTNode] = None
    then_body: list[ASTNode] = field(default_factory=list)
    eif_clauses: list[tuple[ASTNode, list[ASTNode]]] = field(default_factory=list)
    else_body: list[ASTNode] = field(default_factory=list)


@dataclass
class LoopNode(ASTNode):
    """loop ... end (infinite loop)"""
    body: list[ASTNode] = field(default_factory=list)


@dataclass
class WhenLoopNode(ASTNode):
    """when <condition> loop ... end"""
    condition: Optional[ASTNode] = None
    body: list[ASTNode] = field(default_factory=list)


@dataclass
class BreakNode(ASTNode):
    """break;"""
    pass


@dataclass
class SkipNode(ASTNode):
    """skip; (replaces continue)"""
    pass


@dataclass
class CaseNode(ASTNode):
    """case expression value: action; ... else fallback; end"""
    expr: Optional[ASTNode] = None
    branches: list[tuple[ASTNode, ASTNode]] = field(default_factory=list)
    else_body: list[ASTNode] = field(default_factory=list)


# ── Error handling ────────────────────────────────────────

@dataclass
class TryErrorNode(ASTNode):
    """try ... fallback ... error <ErrorName> ... end"""
    try_body: list[ASTNode] = field(default_factory=list)
    fallback_body: list[ASTNode] = field(default_factory=list)
    error_handlers: list[tuple[str, list[ASTNode]]] = field(default_factory=list)
    expr: Optional[ASTNode] = None
    fallback: Optional[ASTNode] = None
    error_name: str = ""


# ── Phase 3: Generics / Traits / Enum / Closures ─────────

@dataclass
class GenericParam(ASTNode):
    """Type parameter: T, T: Display, T: Display + Clone"""
    name: str = ""
    bounds: list[str] = field(default_factory=list)


@dataclass
class GenericType(ASTNode):
    """Generic type reference: Vec<i64>, Map<str, i64>"""
    base_name: str = ""
    type_args: list[str] = field(default_factory=list)


@dataclass
class EnumDefNode(ASTNode):
    """enum Option<T>: Some(T); None; end"""
    name: str = ""
    generic_params: list[GenericParam] = field(default_factory=list)
    variants: list[tuple[str, list[str]]] = field(default_factory=list)


@dataclass
class TraitDefNode(ASTNode):
    """trait Display: func to_string(self) -> str; end"""
    name: str = ""
    generic_params: list[GenericParam] = field(default_factory=list)
    methods: list[FuncDefNode] = field(default_factory=list)


@dataclass
class ImplNode(ASTNode):
    """impl Display for Vec<i64>: ... end"""
    trait_name: str = ""
    target_type: str = ""
    generic_params: list[GenericParam] = field(default_factory=list)
    methods: list[FuncDefNode] = field(default_factory=list)


@dataclass
class MatchNode(ASTNode):
    """match expr: pattern => body; ... end"""
    expr: Optional[ASTNode] = None
    arms: list[tuple[ASTNode, list[ASTNode]]] = field(default_factory=list)
    else_body: list[ASTNode] = field(default_factory=list)


@dataclass
class ClosureNode(ASTNode):
    """|params| body"""
    params: list[str] = field(default_factory=list)
    body: list[ASTNode] = field(default_factory=list)


@dataclass
class PropagateNode(ASTNode):
    """expr? — unwrap Result/Option or early return"""
    expr: Optional[ASTNode] = None


# ── Data structures ───────────────────────────────────────

@dataclass
class MapNode(ASTNode):
    """map key: value; ... end"""
    entries: list[tuple[ASTNode, ASTNode]] = field(default_factory=list)


# ── Expressions ───────────────────────────────────────────

@dataclass
class VarDeclNode(ASTNode):
    """Legacy variable declaration for backward compat."""
    name: str = ""
    value: Optional[ASTNode] = None
    type_ann: Optional[str] = None


@dataclass
class BinOpNode(ASTNode):
    """Binary operation: a + b"""
    op: str = ""          # "ADD", "SUB", "MUL", "DIV", "POW", "MOD", "PERCENT"
    left: Optional[ASTNode] = None
    right: Optional[ASTNode] = None


@dataclass
class CompareNode(ASTNode):
    """Comparison: a == b"""
    op: str = ""          # "EQ", "NE", "GT", "LT", "GE", "LE", "SAFE_EQ", "SAFE_NE"
    left: Optional[ASTNode] = None
    right: Optional[ASTNode] = None


@dataclass
class LogicOpNode(ASTNode):
    """Logical operation: & || !"""
    op: str = ""          # "AND", "OR", "NOT"
    left: Optional[ASTNode] = None
    right: Optional[ASTNode] = None


@dataclass
class AssignNode(ASTNode):
    """Assignment: name = expr;"""
    name: str = ""
    value: Optional[ASTNode] = None


@dataclass
class CallNode(ASTNode):
    """Function call with named arguments: func(param=value; param=value)"""
    name: str = ""
    args: list[ASTNode] = field(default_factory=list)
    named_args: list[tuple[str, ASTNode]] = field(default_factory=list)


@dataclass
class NumberLiteral(ASTNode):
    """Numeric literal."""
    value: float = 0.0


@dataclass
class StringLiteral(ASTNode):
    """String literal."""
    value: str = ""


@dataclass
class IdentifierRef(ASTNode):
    """Variable / function reference."""
    name: str = ""


@dataclass
class PrintNode(ASTNode):
    """print <expr>"""
    expr: Optional[ASTNode] = None


@dataclass
class InputNode(ASTNode):
    """input <varname>"""
    var_name: str = ""


@dataclass
class PatternMatchNode(ASTNode):
    """Pattern match: expr :~ pattern"""
    expr: Optional[ASTNode] = None
    pattern: Optional[ASTNode] = None


@dataclass
class SafeAccessNode(ASTNode):
    """Safe access: expr?.field"""
    expr: Optional[ASTNode] = None
    field_name: str = ""


@dataclass
class CastNode(ASTNode):
    """Type cast: expr >> Type"""
    expr: Optional[ASTNode] = None
    target_type: str = ""


@dataclass
class ExistCheckNode(ASTNode):
    """Existence check: expr?"""
    expr: Optional[ASTNode] = None


@dataclass
class AccessNode(ASTNode):
    """Member access: expr.field"""
    expr: Optional[ASTNode] = None
    field_name: str = ""


# ── Legacy compatibility nodes ─────────────────────────────

@dataclass
class ReturnNode(ASTNode):
    """Legacy return (maps to OutNode internally)."""
    expr: Optional[ASTNode] = None


@dataclass
class WhileNode(ASTNode):
    """Legacy while loop (maps to WhenLoopNode)."""
    condition: Optional[ASTNode] = None
    body: list[ASTNode] = field(default_factory=list)


@dataclass
class ForNode(ASTNode):
    """Legacy for loop."""
    var_name: str = ""
    start: Optional[ASTNode] = None
    end: Optional[ASTNode] = None
    step: Optional[ASTNode] = None
    body: list[ASTNode] = field(default_factory=list)


@dataclass
class ContinueNode(ASTNode):
    """Legacy continue (maps to SkipNode)."""
    pass


@dataclass
class PatchPointNode(ASTNode):
    """Patch point for binary self-patching."""
    patch_id: str = ""
    target_hint: str = ""


@dataclass
class CheckCPUNode(ASTNode):
    """Check CPU idle."""
    then_body: list[ASTNode] = field(default_factory=list)
    else_body: list[ASTNode] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════
# Token → IR mapping helpers
# ═══════════════════════════════════════════════════════════

_OP_MAP = {
    TokenKind.OP_ADD: "ADD",
    TokenKind.OP_SUB: "SUB",
    TokenKind.OP_MUL: "MUL",
    TokenKind.OP_DIV: "DIV",
    TokenKind.OP_MOD: "MOD",
    TokenKind.OP_POW: "POW",
    TokenKind.OP_PERCENT: "PERCENT",
}

_CMP_MAP = {
    TokenKind.CMP_EQ: "EQ",
    TokenKind.CMP_NE: "NE",
    TokenKind.CMP_GT: "GT",
    TokenKind.CMP_LT: "LT",
    TokenKind.CMP_GE: "GE",
    TokenKind.CMP_LE: "LE",
    TokenKind.CMP_SAFE_EQ: "SAFE_EQ",
    TokenKind.CMP_SAFE_NE: "SAFE_NE",
}

_LOGIC_MAP = {
    TokenKind.LOGIC_AND: "AND",
    TokenKind.LOGIC_OR: "OR",
    TokenKind.LOGIC_NOT: "NOT",
}

# Tokens that signal end of a block body (v1.2: always END)
_BLOCK_ENDERS = {
    TokenKind.END, TokenKind.ELSE, TokenKind.EIF, TokenKind.ELIF,
}

# v1.2 Operator precedence (high → low)
# () → ?. . → ! - → ^ → * / → % mod → + - → >> shl shr
# → :~ → > < >= <= → == != ?= ?=/= → & → xor → || → =
_PREC: dict[TokenKind, int] = {
    TokenKind.LOGIC_OR:      2,
    TokenKind.BIT_XOR:       2,
    TokenKind.LOGIC_AND:     3,
    TokenKind.CMP_EQ: 5, TokenKind.CMP_NE: 5,
    TokenKind.CMP_SAFE_EQ: 5, TokenKind.CMP_SAFE_NE: 5,
    TokenKind.CMP_GT: 6, TokenKind.CMP_LT: 6,
    TokenKind.CMP_GE: 6, TokenKind.CMP_LE: 6,
    TokenKind.OP_PATTERN:    8,
    TokenKind.OP_CAST: 12, TokenKind.BIT_SHL: 12, TokenKind.BIT_SHR: 12,
    TokenKind.OP_ADD: 10, TokenKind.OP_SUB: 10,
    TokenKind.OP_PERCENT: 18, TokenKind.OP_MOD: 18,
    TokenKind.OP_MUL: 20, TokenKind.OP_DIV: 20,
    TokenKind.OP_POW: 30,
    TokenKind.OP_ACCESS: 40, TokenKind.OP_SAFE_ACCESS: 40,
}


# ═══════════════════════════════════════════════════════════
# Parser (v1.2)
# ═══════════════════════════════════════════════════════════

class ParseError(Exception):
    pass


class Parser:
    """
    Recursive-descent parser for Vir v1.2.

    Blocks always close with `end`.
    `:` opens a block.
    `;` terminates statements.
    """

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # ── Utility ────────────────────────────────────────────
    def _peek(self) -> Optional[Token]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, kind: TokenKind) -> Token:
        tok = self._peek()
        if tok is None or tok.kind != kind:
            raise ParseError(f"Expected {kind}, got {tok}")
        return self._advance()

    def _at_end(self) -> bool:
        return self.pos >= len(self.tokens)

    def _skip_semi(self) -> None:
        """Consume optional semicolons."""
        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.SEMICOLON:
                self._advance()
            else:
                break

    def _skip_end(self) -> None:
        """Consume 'end' if present."""
        p = self._peek()
        if p and p.kind == TokenKind.END:
            self._advance()

    def _skip_colon(self) -> None:
        """Consume ':' if present (block opener)."""
        p = self._peek()
        if p and p.kind == TokenKind.COLON:
            self._advance()

    # ── Entry point ────────────────────────────────────────
    def parse(self) -> ProgramNode:
        program = ProgramNode()
        while not self._at_end():
            saved_pos = self.pos
            stmt = self._parse_statement()
            if stmt is not None:
                program.statements.append(stmt)
            elif self.pos == saved_pos:
                self._advance()  # skip unrecognised token to avoid hang
        return program

    # ── Statement dispatcher ───────────────────────────────
    def _parse_statement(self) -> Optional[ASTNode]:
        tok = self._peek()
        if tok is None:
            return None

        match tok.kind:
            # ── v1.2 module structure ──────────────────────
            case TokenKind.INCLUDE:
                return self._parse_include()
            case TokenKind.CONST_DECL:
                return self._parse_const()
            case TokenKind.VAR_DECL:
                return self._parse_var_block()
            case TokenKind.ENTITY_DEF:
                return self._parse_entity()
            case TokenKind.METHOD_DEF:
                return self._parse_method()
            case TokenKind.CLASS_DEF:
                return self._parse_class()
            case TokenKind.EXPORT:
                return self._parse_export()
            case TokenKind.SHARE:
                return self._parse_share()
            case TokenKind.IMPORT:
                return self._parse_import()
            case TokenKind.HAS:
                return self._parse_has()
            case TokenKind.ASYNC:
                return self._parse_async_func()
            case TokenKind.FUNC_DEF:
                return self._parse_func_def()
            case TokenKind.TASK:
                return self._parse_task()

            # ── v1.2 control flow ──────────────────────────
            case TokenKind.IF:
                return self._parse_if()
            case TokenKind.EIF | TokenKind.ELIF:
                return None  # handled inside _parse_if
            case TokenKind.WHEN:
                return self._parse_when_loop()
            case TokenKind.LOOP:
                return self._parse_loop()
            case TokenKind.CASE:
                return self._parse_case()
            case TokenKind.MAP:
                return self._parse_map()
            case TokenKind.BREAK:
                return self._parse_break()
            case TokenKind.SKIP:
                return self._parse_skip()
            case TokenKind.CONTINUE:
                return self._parse_skip()   # legacy compat
            case TokenKind.OUT:
                return self._parse_out()
            case TokenKind.RETURN:
                return self._parse_out()    # legacy compat

            # ── Phase 3: generics / traits / enum / match ──
            case TokenKind.ENUM_DEF:
                return self._parse_enum()
            case TokenKind.TRAIT_DEF:
                return self._parse_trait()
            case TokenKind.IMPL_BLOCK:
                return self._parse_impl()

            # ── error handling ─────────────────────────────
            case TokenKind.TRY:
                return self._parse_try_error()

            # ── I/O ────────────────────────────────────────
            case TokenKind.PRINT:
                return self._parse_print()
            case TokenKind.INPUT:
                return self._parse_input()

            # ── system ─────────────────────────────────────
            case TokenKind.CHECK_CPU:
                return self._parse_check_cpu()
            case TokenKind.PATCH:
                return self._parse_patch()
            case TokenKind.EXECUTE:
                self._advance()
                return self._parse_statement()

            # ── block enders ───────────────────────────────
            case TokenKind.END:
                return None  # consumed by block parser
            case TokenKind.ELSE:
                return None  # consumed by if parser
            case TokenKind.SEMICOLON:
                self._advance()
                return None

            # ── legacy compat ──────────────────────────────
            case TokenKind.WHILE:
                return self._parse_while_legacy()
            case TokenKind.FOR:
                return self._parse_for_legacy()

            # ── expressions / assignments ──────────────────
            case tok_kind if tok_kind in _OP_MAP:
                return self._parse_binop()
            case tok_kind if tok_kind in _CMP_MAP:
                return self._parse_compare()
            case tok_kind if tok_kind in _LOGIC_MAP:
                return self._parse_logic()
            case _:
                return self._parse_expr_or_assign()

    # ══════════════════════════════════════════════════════
    # v1.2 Module Structure
    # ══════════════════════════════════════════════════════

    def _parse_include(self) -> IncludeNode:
        tok = self._advance()  # INCLUDE
        node = IncludeNode(token=tok)
        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            node.module_name = p.raw_text
        self._skip_semi()
        return node

    def _parse_const(self) -> ConstDeclNode:
        tok = self._advance()  # CONST
        node = ConstDeclNode(token=tok)
        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            node.name = p.raw_text
        self._skip_colon()
        node.value = self._parse_expr()
        self._skip_semi()
        return node

    def _parse_var_block(self) -> ModuleStateNode:
        """Parse var block (Pascal style module state)."""
        tok = self._advance()  # VAR
        node = ModuleStateNode(token=tok)
        # Parse fields: name:type; separated by ;
        while not self._at_end():
            p = self._peek()
            if p is None:
                break
            # Stop at any non-identifier (next keyword starts)
            if p.kind != TokenKind.IDENTIFIER:
                break
            self._advance()
            var_name = p.raw_text
            var_type = ""
            # Check for :type
            p2 = self._peek()
            if p2 and p2.kind == TokenKind.COLON:
                self._advance()  # :
                p3 = self._peek()
                if p3 and p3.kind == TokenKind.IDENTIFIER:
                    self._advance()
                    var_type = p3.raw_text
                elif p3 and p3.kind in (TokenKind.TYPE_INT, TokenKind.TYPE_FLOAT,
                                         TokenKind.TYPE_STRING, TokenKind.TYPE_BOOL):
                    self._advance()
                    var_type = p3.raw_text
            node.fields.append((var_name, var_type))
            self._skip_semi()
        return node

    def _parse_export(self) -> ExportNode:
        tok = self._advance()  # EXPORT
        node = ExportNode(token=tok)
        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.IDENTIFIER:
                self._advance()
                node.names.append(p.raw_text)
            elif p and p.kind == TokenKind.COMMA:
                self._advance()
            else:
                break
        self._skip_semi()
        return node

    def _parse_share(self) -> ShareNode:
        tok = self._advance()  # SHARE
        node = ShareNode(token=tok)
        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.IDENTIFIER:
                self._advance()
                node.names.append(p.raw_text)
            elif p and p.kind == TokenKind.COMMA:
                self._advance()
            else:
                break
        self._skip_semi()
        return node

    def _parse_import(self) -> ImportNode:
        """import func1, func2, get state1, state2 from module"""
        tok = self._advance()  # IMPORT
        node = ImportNode(token=tok)
        collecting_shared = False
        while not self._at_end():
            p = self._peek()
            if p is None:
                break
            if p.kind == TokenKind.GET:
                self._advance()
                collecting_shared = True
                continue
            if p.kind == TokenKind.FROM:
                self._advance()
                pm = self._peek()
                if pm and pm.kind == TokenKind.IDENTIFIER:
                    self._advance()
                    node.module_name = pm.raw_text
                break
            if p.kind == TokenKind.IDENTIFIER:
                self._advance()
                if collecting_shared:
                    node.shared.append(p.raw_text)
                else:
                    node.funcs.append(p.raw_text)
            elif p.kind == TokenKind.COMMA:
                self._advance()
            else:
                break
        self._skip_semi()
        return node

    def _parse_has(self) -> HasDeclNode:
        tok = self._advance()  # HAS
        node = HasDeclNode(token=tok)
        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            node.name = p.raw_text
        self._skip_semi()
        return node

    # ══════════════════════════════════════════════════════
    # Function / Method / Entity / Class
    # ══════════════════════════════════════════════════════

    def _parse_func_def(self) -> FuncDefNode:
        """func <name>: in(<params>) ... out <expr>; end"""
        tok = self._advance()  # FUNC_DEF
        node = FuncDefNode(token=tok)

        # Function name
        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            node.name = p.raw_text

        self._skip_colon()

        # Body until END
        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.END:
                self._advance()
                break
            # parse in() as parameter declaration inside body
            if p and p.kind == TokenKind.IN:
                in_node = self._parse_in_params()
                if in_node:
                    node.params = [name for name, _ in in_node.params]
                    node.param_types = [t for _, t in in_node.params]
                    node.body.append(in_node)
                continue
            saved_pos = self.pos
            stmt = self._parse_statement()
            if stmt:
                node.body.append(stmt)
            elif self.pos == saved_pos:
                self._advance()  # skip unrecognised token to avoid hang

        return node

    def _parse_async_func(self) -> FuncDefNode:
        """async func <name>: ... end"""
        self._advance()  # ASYNC
        node = self._parse_func_def()
        node.is_async = True
        return node

    def _parse_in_params(self) -> Optional[InParamsNode]:
        """in(a:int; b:int; result:int)"""
        tok = self._advance()  # IN
        node = InParamsNode(token=tok)

        # Expect OPEN_PAREN
        p = self._peek()
        if p and p.kind == TokenKind.OPEN_PAREN:
            self._advance()
        else:
            return node  # bare 'in' without parens

        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.CLOSE_PAREN:
                self._advance()
                break
            if p and p.kind == TokenKind.SEMICOLON:
                self._advance()
                continue
            if p and p.kind == TokenKind.IDENTIFIER:
                self._advance()
                param_name = p.raw_text
                param_type: Optional[str] = None
                # Check for :type
                p2 = self._peek()
                if p2 and p2.kind == TokenKind.COLON:
                    self._advance()
                    p3 = self._peek()
                    if p3 and p3.kind == TokenKind.IDENTIFIER:
                        self._advance()
                        param_type = p3.raw_text
                    elif p3 and p3.kind in (TokenKind.TYPE_INT, TokenKind.TYPE_FLOAT,
                                             TokenKind.TYPE_STRING, TokenKind.TYPE_BOOL):
                        self._advance()
                        param_type = p3.raw_text
                node.params.append((param_name, param_type))
            else:
                self._advance()  # skip unexpected
        return node

    def _parse_entity(self) -> EntityDefNode:
        """entity <name>: field:type; ... end"""
        tok = self._advance()  # ENTITY_DEF
        node = EntityDefNode(token=tok)

        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            node.name = p.raw_text

        self._skip_colon()

        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.END:
                self._advance()
                break
            if p and p.kind == TokenKind.IDENTIFIER:
                self._advance()
                field_name = p.raw_text
                field_type = ""
                p2 = self._peek()
                if p2 and p2.kind == TokenKind.COLON:
                    self._advance()
                    p3 = self._peek()
                    if p3 and p3.kind == TokenKind.IDENTIFIER:
                        self._advance()
                        field_type = p3.raw_text
                node.fields.append((field_name, field_type))
                self._skip_semi()
            else:
                self._advance()
        return node

    def _parse_method(self) -> MethodDefNode:
        """method Entity.method: ... end"""
        tok = self._advance()  # METHOD_DEF
        node = MethodDefNode(token=tok)

        # Expect Entity.method pattern
        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            full_name = p.raw_text
            # Check for .method
            p2 = self._peek()
            if p2 and (p2.kind == TokenKind.DOT or p2.kind == TokenKind.OP_ACCESS):
                self._advance()
                p3 = self._peek()
                if p3 and p3.kind == TokenKind.IDENTIFIER:
                    self._advance()
                    node.entity_name = full_name
                    node.method_name = p3.raw_text
                else:
                    node.method_name = full_name
            else:
                node.method_name = full_name

        self._skip_colon()

        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.END:
                self._advance()
                break
            saved_pos = self.pos
            stmt = self._parse_statement()
            if stmt:
                node.body.append(stmt)
            elif self.pos == saved_pos:
                self._advance()

        return node

    def _parse_class(self) -> ClassDefNode:
        """class <name> entity method end"""
        tok = self._advance()  # CLASS_DEF
        node = ClassDefNode(token=tok)

        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            node.name = p.raw_text

        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.END:
                self._advance()
                break
            if p and p.kind == TokenKind.ENTITY_DEF:
                entity = self._parse_entity()
                node.entities.append(entity)
            elif p and p.kind == TokenKind.METHOD_DEF:
                method = self._parse_method()
                node.methods.append(method)
            else:
                self._advance()  # skip unexpected inside class

        return node

    def _parse_task(self) -> TaskNode:
        """task <name> wait <asyncFunc>"""
        tok = self._advance()  # TASK
        node = TaskNode(token=tok)
        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            node.name = p.raw_text
        p2 = self._peek()
        if p2 and p2.kind == TokenKind.WAIT:
            self._advance()
            p3 = self._peek()
            if p3 and p3.kind == TokenKind.IDENTIFIER:
                self._advance()
                node.wait_func = p3.raw_text
        self._skip_semi()
        return node

    # ══════════════════════════════════════════════════════
    # Control flow (v1.2)
    # ══════════════════════════════════════════════════════

    def _parse_if(self) -> IfNode:
        """if condition: ... eif condition: ... else ... end"""
        tok = self._advance()  # IF (or EIF for recursion)
        node = IfNode(token=tok)
        node.condition = self._parse_expr()
        self._skip_colon()

        # Then body
        while not self._at_end():
            p = self._peek()
            if p and p.kind in (TokenKind.EIF, TokenKind.ELIF,
                                 TokenKind.ELSE, TokenKind.END):
                break
            saved_pos = self.pos
            stmt = self._parse_statement()
            if stmt:
                node.then_body.append(stmt)
            elif self.pos == saved_pos:
                self._advance()

        # EIF chain
        while not self._at_end():
            p = self._peek()
            if p and p.kind in (TokenKind.EIF, TokenKind.ELIF):
                self._advance()  # consume eif/elif
                eif_cond = self._parse_expr()
                self._skip_colon()
                eif_body: list[ASTNode] = []
                while not self._at_end():
                    p2 = self._peek()
                    if p2 and p2.kind in (TokenKind.EIF, TokenKind.ELIF,
                                           TokenKind.ELSE, TokenKind.END):
                        break
                    s = self._parse_statement()
                    if s:
                        eif_body.append(s)
                    else:
                        break
                if eif_cond:
                    node.eif_clauses.append((eif_cond, eif_body))
            else:
                break

        # ELSE
        p = self._peek()
        if p and p.kind == TokenKind.ELSE:
            self._advance()
            while not self._at_end():
                p2 = self._peek()
                if p2 and p2.kind == TokenKind.END:
                    break
                s = self._parse_statement()
                if s:
                    node.else_body.append(s)
                else:
                    break

        self._skip_end()
        return node

    def _parse_when_loop(self) -> WhenLoopNode:
        """when <condition> loop ... end"""
        tok = self._advance()  # WHEN
        node = WhenLoopNode(token=tok)
        node.condition = self._parse_expr()

        # Expect LOOP keyword
        p = self._peek()
        if p and p.kind == TokenKind.LOOP:
            self._advance()

        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.END:
                self._advance()
                break
            stmt = self._parse_statement()
            if stmt:
                node.body.append(stmt)
            else:
                break
        return node

    def _parse_loop(self) -> LoopNode:
        """loop ... end (infinite loop)"""
        tok = self._advance()  # LOOP
        node = LoopNode(token=tok)

        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.END:
                self._advance()
                break
            stmt = self._parse_statement()
            if stmt:
                node.body.append(stmt)
            else:
                break
        return node

    def _parse_case(self) -> CaseNode:
        """case expression value: action; ... else fallback; end"""
        tok = self._advance()  # CASE
        node = CaseNode(token=tok)
        node.expr = self._parse_expr()

        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.END:
                self._advance()
                break
            if p and p.kind == TokenKind.ELSE:
                self._advance()
                while not self._at_end():
                    p2 = self._peek()
                    if p2 and p2.kind == TokenKind.END:
                        break
                    s = self._parse_statement()
                    if s:
                        node.else_body.append(s)
                    else:
                        break
                self._skip_end()
                break
            # value: action;
            val = self._parse_expr()
            self._skip_colon()
            action = self._parse_statement()
            self._skip_semi()
            if val and action:
                node.branches.append((val, action))
        return node

    def _parse_map(self) -> MapNode:
        """map key: value; ... end"""
        tok = self._advance()  # MAP
        node = MapNode(token=tok)

        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.END:
                self._advance()
                break
            key = self._parse_expr()
            self._skip_colon()
            value = self._parse_expr()
            self._skip_semi()
            if key and value:
                node.entries.append((key, value))
        return node

    def _parse_break(self) -> BreakNode:
        tok = self._advance()
        self._skip_semi()
        return BreakNode(token=tok)

    def _parse_skip(self) -> SkipNode:
        tok = self._advance()  # SKIP or CONTINUE
        self._skip_semi()
        return SkipNode(token=tok)

    def _parse_entity_inst(self, type_tok: Token) -> EntityNode:
        """Name: field: value; ... end"""
        # We already advanced past Name, now skip COLON
        self._advance() 
        node = EntityNode(token=type_tok, type_name=type_tok.raw_text)
        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.END:
                self._advance()
                break
            if p and p.kind == TokenKind.IDENTIFIER:
                self._advance()
                field_name = p.raw_text
                self._skip_colon()
                field_val = self._parse_expr()
                self._skip_semi()
                if field_val:
                    node.fields.append((field_name, field_val))
            else:
                self._advance()
        return node

    def _parse_out(self) -> OutNode:
        """out <expr>;"""
        tok = self._advance()  # OUT or RETURN
        node = OutNode(token=tok)
        node.expr = self._parse_expr()
        self._skip_semi()
        return node

    def _parse_try_error(self) -> TryErrorNode:
        """out <expr> try <fallback> error <ErrorName> end"""
        tok = self._advance()  # TRY
        node = TryErrorNode(token=tok)
        node.fallback = self._parse_expr()
        p = self._peek()
        if p and p.kind == TokenKind.ERROR:
            self._advance()
            pe = self._peek()
            if pe and pe.kind == TokenKind.IDENTIFIER:
                self._advance()
                node.error_name = pe.raw_text
        self._skip_end()
        return node

    # ══════════════════════════════════════════════════════
    # Expressions
    # ══════════════════════════════════════════════════════

    def _parse_expr(self) -> Optional[ASTNode]:
        tok = self._peek()
        if tok is None:
            return None

        if tok.kind == TokenKind.NUMBER:
            self._advance()
            from src.frontend.tokenizer.ngram_tokenizer import NumberToken
            val = tok.value if isinstance(tok, NumberToken) else 0.0
            return NumberLiteral(token=tok, value=val)

        if tok.kind == TokenKind.STRING:
            self._advance()
            from src.frontend.tokenizer.ngram_tokenizer import StringToken
            val = tok.string_value if isinstance(tok, StringToken) else tok.raw_text
            return StringLiteral(token=tok, value=val)

        if tok.kind == TokenKind.IDENTIFIER:
            self._advance()
            p = self._peek()
            if p and p.kind == TokenKind.COLON:
                return self._parse_entity_inst(tok)
            if p and p.kind == TokenKind.OPEN_PAREN:
                return self._parse_call(tok)
            if p and p.kind == TokenKind.DOT:
                return self._parse_access(IdentifierRef(token=tok, name=tok.raw_text))
            return IdentifierRef(token=tok, name=tok.raw_text)

        if tok.kind in _OP_MAP:
            return self._parse_binop()

        if tok.kind in _CMP_MAP:
            return self._parse_compare()

        if tok.kind in _LOGIC_MAP:
            return self._parse_logic()

        if tok.kind == TokenKind.OPEN_PAREN:
            self._advance()
            inner = self._parse_expr()
            p = self._peek()
            if p and p.kind == TokenKind.CLOSE_PAREN:
                self._advance()
            return inner

        # Fallback: consume and skip
        self._advance()
        return None

    def _parse_expr_or_assign(self) -> Optional[ASTNode]:
        """Parse expression, detecting assignment (name = expr)."""
        tok = self._peek()
        if tok is None:
            return None

        if tok.kind == TokenKind.IDENTIFIER:
            self._advance()
            name = tok.raw_text
            p = self._peek()
            # Check for assignment: name = expr
            if p and p.kind == TokenKind.ASSIGN:
                self._advance()
                value = self._parse_expr()
                self._skip_semi()
                return AssignNode(token=tok, name=name, value=value)
            # Check for call: name(...)
            if p and p.kind == TokenKind.OPEN_PAREN:
                call = self._parse_call(tok)
                self._skip_semi()
                return call
            return IdentifierRef(token=tok, name=name)

        return self._parse_expr()

    # ── Function call with named arguments ─────────────────
    def _parse_call(self, name_tok: Token) -> CallNode:
        """Parse func(param=value; param=value) with named arguments."""
        self._advance()  # consume OPEN_PAREN
        node = CallNode(token=name_tok, name=name_tok.raw_text)

        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.CLOSE_PAREN:
                self._advance()
                break
            if p and p.kind in (TokenKind.COMMA, TokenKind.SEMICOLON):
                self._advance()
                continue

            # Check for named arg: name=value
            if p and p.kind == TokenKind.IDENTIFIER:
                saved_pos = self.pos
                self._advance()
                p2 = self._peek()
                if p2 and p2.kind == TokenKind.ASSIGN:
                    self._advance()  # consume =
                    val = self._parse_expr()
                    if val:
                        node.named_args.append((p.raw_text, val))
                    continue
                else:
                    # Not a named arg, backtrack and parse as positional
                    self.pos = saved_pos

            arg = self._parse_expr()
            if arg:
                node.args.append(arg)
            else:
                break
        return node

    # ── Binary/Compare/Logic ───────────────────────────────
    def _parse_binop(self) -> BinOpNode:
        tok = self._advance()
        op = _OP_MAP.get(tok.kind, "ADD")
        node = BinOpNode(token=tok, op=op)
        node.left = self._parse_expr()
        node.right = self._parse_expr()
        return node

    def _parse_compare(self) -> CompareNode:
        tok = self._advance()
        op = _CMP_MAP.get(tok.kind, "EQ")
        node = CompareNode(token=tok, op=op)
        node.left = self._parse_expr()
        node.right = self._parse_expr()
        return node

    def _parse_logic(self) -> LogicOpNode:
        tok = self._advance()
        op = _LOGIC_MAP.get(tok.kind, "AND")
        node = LogicOpNode(token=tok, op=op)
        node.left = self._parse_expr()
        if op != "NOT":
            node.right = self._parse_expr()
        return node

    # ── I/O ────────────────────────────────────────────────
    def _parse_print(self) -> PrintNode:
        tok = self._advance()
        node = PrintNode(token=tok)
        node.expr = self._parse_expr()
        self._skip_semi()
        return node

    def _parse_input(self) -> InputNode:
        tok = self._advance()
        node = InputNode(token=tok)
        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            node.var_name = p.raw_text
        self._skip_semi()
        return node

    # ── System ─────────────────────────────────────────────
    def _parse_check_cpu(self) -> CheckCPUNode:
        tok = self._advance()
        node = CheckCPUNode(token=tok)
        while not self._at_end():
            p = self._peek()
            if p and p.kind in _BLOCK_ENDERS:
                break
            stmt = self._parse_statement()
            if stmt:
                node.then_body.append(stmt)
            else:
                break
        return node

    def _parse_patch(self) -> PatchPointNode:
        tok = self._advance()
        node = PatchPointNode(token=tok, patch_id=f"PATCH_{self.pos}")
        p = self._peek()
        if p and p.kind == TokenKind.TARGET_REGISTER:
            self._advance()
            node.target_hint = "register"
        return node

    # ── Infix expression with precedence climbing ──────────
    def _parse_infix(self, min_prec: int = 0) -> Optional[ASTNode]:
        """Precedence-climbing expression parser."""
        left = self._parse_expr()
        while not self._at_end():
            tok = self._peek()
            if tok is None:
                break
            prec = _PREC.get(tok.kind)
            if prec is None or prec < min_prec:
                break
            if tok.kind in _OP_MAP:
                op_tok = self._advance()
                right = self._parse_infix(prec + 1)
                left = BinOpNode(token=op_tok, op=_OP_MAP[tok.kind],
                                 left=left, right=right)
            elif tok.kind in _CMP_MAP:
                op_tok = self._advance()
                right = self._parse_infix(prec + 1)
                left = CompareNode(token=op_tok, op=_CMP_MAP[tok.kind],
                                   left=left, right=right)
            elif tok.kind in _LOGIC_MAP:
                op_tok = self._advance()
                right = self._parse_infix(prec + 1)
                left = LogicOpNode(token=op_tok, op=_LOGIC_MAP[tok.kind],
                                   left=left, right=right)
            elif tok.kind == TokenKind.OP_PATTERN:
                op_tok = self._advance()
                right = self._parse_infix(prec + 1)
                left = PatternMatchNode(token=op_tok, expr=left, pattern=right)
            elif tok.kind == TokenKind.OP_CAST:
                op_tok = self._advance()
                right = self._parse_infix(prec + 1)
                target = right.name if isinstance(right, IdentifierRef) else ""
                left = CastNode(token=op_tok, expr=left, target_type=target)
            else:
                break
        return left

    # ── Legacy backward-compat parsers ─────────────────────

    def _parse_while_legacy(self) -> WhenLoopNode:
        """Legacy: parse while as when...loop."""
        tok = self._advance()  # WHILE
        node = WhenLoopNode(token=tok)
        node.condition = self._parse_expr()
        while not self._at_end():
            p = self._peek()
            if p and p.kind in (_BLOCK_ENDERS | {TokenKind.FUNC_DEF}):
                if p.kind == TokenKind.END:
                    self._advance()
                break
            stmt = self._parse_statement()
            if stmt:
                node.body.append(stmt)
            else:
                break
        return node

    def _parse_for_legacy(self) -> ForNode:
        """Legacy: parse for loop."""
        tok = self._advance()  # FOR
        node = ForNode(token=tok)
        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            node.var_name = p.raw_text
        node.start = self._parse_expr()
        node.end = self._parse_expr()
        p = self._peek()
        if p and p.kind == TokenKind.NUMBER:
            node.step = self._parse_expr()
        while not self._at_end():
            p = self._peek()
            if p and p.kind in (_BLOCK_ENDERS | {TokenKind.FUNC_DEF}):
                if p.kind == TokenKind.END:
                    self._advance()
                break
            stmt = self._parse_statement()
            if stmt:
                node.body.append(stmt)
            else:
                break
        return node

    def _parse_assign(self) -> AssignNode:
        """Legacy: parse ASSIGN token."""
        tok = self._advance()
        node = AssignNode(token=tok)
        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            node.name = p.raw_text
        node.value = self._parse_expr()
        self._skip_semi()
        return node

    # ══════════════════════════════════════════════════════
    # Phase 3: Generics, Traits, Enum, Match, Closures
    # ══════════════════════════════════════════════════════

    def _parse_generic_params(self) -> list[GenericParam]:
        """Parse <T, U: Display + Clone> if present."""
        p = self._peek()
        if not (p and p.kind == TokenKind.CMP_LT):
            return []
        self._advance()  # <
        params: list[GenericParam] = []
        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.CMP_GT:
                self._advance()  # >
                break
            if p and p.kind == TokenKind.COMMA:
                self._advance()
                continue
            if p and p.kind == TokenKind.IDENTIFIER:
                self._advance()
                gp = GenericParam(name=p.raw_text)
                # Check for bounds: T: Display + Clone
                p2 = self._peek()
                if p2 and p2.kind == TokenKind.COLON:
                    self._advance()
                    while not self._at_end():
                        pb = self._peek()
                        if pb and pb.kind == TokenKind.IDENTIFIER:
                            self._advance()
                            gp.bounds.append(pb.raw_text)
                        else:
                            break
                        # + for additional bounds
                        pplus = self._peek()
                        if pplus and pplus.kind == TokenKind.OP_ADD:
                            self._advance()
                        else:
                            break
                params.append(gp)
            else:
                self._advance()
        return params

    def _parse_enum(self) -> EnumDefNode:
        """enum <Name><T>: Variant1(Type); Variant2; end"""
        tok = self._advance()  # ENUM_DEF
        node = EnumDefNode(token=tok)
        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            node.name = p.raw_text
        node.generic_params = self._parse_generic_params()
        self._skip_colon()

        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.END:
                self._advance()
                break
            if p and p.kind == TokenKind.IDENTIFIER:
                self._advance()
                variant_name = p.raw_text
                variant_types: list[str] = []
                # Check for (Type1, Type2)
                p2 = self._peek()
                if p2 and p2.kind == TokenKind.OPEN_PAREN:
                    self._advance()
                    while not self._at_end():
                        pt = self._peek()
                        if pt and pt.kind == TokenKind.CLOSE_PAREN:
                            self._advance()
                            break
                        if pt and pt.kind == TokenKind.COMMA:
                            self._advance()
                            continue
                        if pt and pt.kind == TokenKind.IDENTIFIER:
                            self._advance()
                            variant_types.append(pt.raw_text)
                        else:
                            self._advance()
                node.variants.append((variant_name, variant_types))
                self._skip_semi()
            else:
                self._advance()
        return node

    def _parse_trait(self) -> TraitDefNode:
        """trait <Name><T>: method_signature; ... end"""
        tok = self._advance()  # TRAIT_DEF
        node = TraitDefNode(token=tok)
        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            node.name = p.raw_text
        node.generic_params = self._parse_generic_params()
        self._skip_colon()

        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.END:
                self._advance()
                break
            if p and p.kind == TokenKind.FUNC_DEF:
                func = self._parse_func_def()
                node.methods.append(func)
            else:
                self._advance()
        return node

    def _parse_impl(self) -> ImplNode:
        """impl <Trait> for <Type><T>: ... end"""
        tok = self._advance()  # IMPL_BLOCK
        node = ImplNode(token=tok)

        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            node.trait_name = p.raw_text

        # Expect 'for' (identifier with raw_text "for")
        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER and p.raw_text == "for":
            self._advance()

        p = self._peek()
        if p and p.kind == TokenKind.IDENTIFIER:
            self._advance()
            node.target_type = p.raw_text

        node.generic_params = self._parse_generic_params()
        self._skip_colon()

        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.END:
                self._advance()
                break
            if p and p.kind == TokenKind.FUNC_DEF:
                func = self._parse_func_def()
                node.methods.append(func)
            else:
                self._advance()
        return node

    def _parse_match(self) -> MatchNode:
        """match <expr>: pattern => body; ... else ... end"""
        tok = self._advance()  # MATCH (or via case dispatch)
        node = MatchNode(token=tok)
        node.expr = self._parse_expr()
        self._skip_colon()

        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.END:
                self._advance()
                break
            if p and p.kind == TokenKind.ELSE:
                self._advance()
                while not self._at_end():
                    p2 = self._peek()
                    if p2 and p2.kind == TokenKind.END:
                        break
                    s = self._parse_statement()
                    if s:
                        node.else_body.append(s)
                    else:
                        break
                self._skip_end()
                break
            # pattern => body;
            pattern = self._parse_expr()
            p2 = self._peek()
            if p2 and p2.kind == TokenKind.DOUBLE_ARROW:
                self._advance()
            arm_body: list[ASTNode] = []
            while not self._at_end():
                p3 = self._peek()
                if p3 and p3.kind == TokenKind.SEMICOLON:
                    self._advance()
                    break
                if p3 and p3.kind in (TokenKind.END, TokenKind.ELSE):
                    break
                s = self._parse_statement()
                if s:
                    arm_body.append(s)
                else:
                    break
            if pattern:
                node.arms.append((pattern, arm_body))
        return node

    def _parse_closure(self) -> ClosureNode:
        """Parse |param1, param2| body expression."""
        tok = self._advance()  # PIPE |
        node = ClosureNode(token=tok)
        # Params until next |
        while not self._at_end():
            p = self._peek()
            if p and p.kind == TokenKind.PIPE:
                self._advance()
                break
            if p and p.kind == TokenKind.COMMA:
                self._advance()
                continue
            if p and p.kind == TokenKind.IDENTIFIER:
                self._advance()
                node.params.append(p.raw_text)
            else:
                break
        # Body: single expression or block
        stmt = self._parse_statement()
        if stmt:
            node.body.append(stmt)
        return node

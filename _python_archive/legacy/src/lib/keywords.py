"""
keywords.py – Vir Standard Keyword Registry (Core v1.2)
========================================================
The SINGLE SOURCE OF TRUTH for all language primitives.

Every keyword, operator, and built-in is defined here in standard English.
sublib adapters translate native-language phrases into these canonical tokens.

Design principles:
  1. All TokenKind values are English, stable, and versioned.
  2. Parser / IR / Codegen ONLY reference TokenKind – never raw strings.
  3. sublib maps native phrases → TokenKind (many-to-one).
  4. lib also stores grammar rules (arity, precedence, category).

Vir v1.2 syntax changes:
  - `out` replaces `return`
  - `eif` replaces `elif`
  - `skip` replaces `continue`
  - `when <cond> loop` replaces `while`
  - `end` closes all blocks (no `then`)
  - `entity` replaces `record`/`struct`
  - `has` = forward declaration
  - `share` = export module state
  - `in()` = parameter block inside func
  - named arguments: func(param=value; param=value)
  - `^` = power, `%` = percent, `mod` = remainder
  - `&` = AND, `||` = OR, `!` = NOT
  - `?=` safe equal, `?=/=` safe not equal
  - `?.` safe access, `?` existence check
  - `:~` pattern match, `>>` cast
  - `xor`, `shl`, `shr` keywords
  - `#` comment, `## ... ##` block comment
  - `async func` for async functions
  - `task <name> wait <func>` for task definitions
  - `get` used in import syntax
  - `map` data structure keyword
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════
# TokenKind – Canonical Token Types (v1.2)
# ═══════════════════════════════════════════════════════════

class TokenKind(enum.Enum):
    """
    All language-level token types for Vir v1.2.

    Naming: <CATEGORY>_<NAME>
    These are the ONLY values the parser / IR see.
    """

    # ── Definitions ────────────────────────────────────────
    FUNC_DEF        = "func_def"
    ASYNC           = "async"
    VAR_DECL        = "var_decl"
    CONST_DECL      = "const_decl"
    CLASS_DEF       = "class_def"
    ENTITY_DEF      = "entity_def"
    METHOD_DEF      = "method_def"
    IMPORT          = "import"
    EXPORT          = "export"
    SHARE           = "share"
    INCLUDE         = "include"
    HAS             = "has"           # forward declaration
    FROM            = "from"
    GET             = "get"           # selective import

    # ── Control flow ───────────────────────────────────────
    IF              = "if"
    ELSE            = "else"
    EIF             = "eif"           # v1.2: replaces elif
    LOOP            = "loop"
    WHEN            = "when"          # v1.2: conditional loop prefix
    BREAK           = "break"
    SKIP            = "skip"          # v1.2: replaces continue
    OUT             = "out"           # v1.2: replaces return
    CASE            = "case"
    END             = "end"           # v1.2: block closer
    IN              = "in"            # param block / iteration

    # ── Task / async ───────────────────────────────────────
    TASK            = "task"
    WAIT            = "wait"

    # ── Arithmetic operators ───────────────────────────────
    OP_ADD          = "op_add"        # +
    OP_SUB          = "op_sub"        # -
    OP_MUL          = "op_mul"        # *
    OP_DIV          = "op_div"        # /
    OP_POW          = "op_pow"        # ^ (power)
    OP_PERCENT      = "op_percent"    # % (percentage)
    OP_MOD          = "op_mod"        # mod (remainder)

    # ── Comparison operators ───────────────────────────────
    CMP_EQ          = "cmp_eq"        # ==
    CMP_NE          = "cmp_ne"        # !=
    CMP_GT          = "cmp_gt"        # >
    CMP_LT          = "cmp_lt"        # <
    CMP_GE          = "cmp_ge"        # >=
    CMP_LE          = "cmp_le"        # <=
    CMP_SAFE_EQ     = "cmp_safe_eq"   # ?=
    CMP_SAFE_NE     = "cmp_safe_ne"   # ?=/=

    # ── Logical operators ──────────────────────────────────
    LOGIC_AND       = "logic_and"     # &
    LOGIC_OR        = "logic_or"      # ||
    LOGIC_NOT       = "logic_not"     # !

    # ── Bitwise / keyword operators ────────────────────────
    BIT_XOR         = "bit_xor"       # xor
    BIT_SHL         = "bit_shl"       # shl
    BIT_SHR         = "bit_shr"       # shr

    # ── Access / Transform ─────────────────────────────────
    OP_ACCESS       = "op_access"     # .
    OP_SAFE_ACCESS  = "op_safe_access" # ?.
    OP_EXIST        = "op_exist"      # ? (existence check)
    OP_CAST         = "op_cast"       # >>
    OP_PATTERN      = "op_pattern"    # :~

    # ── Assignment ─────────────────────────────────────────
    ASSIGN          = "assign"        # =

    # ── I/O ────────────────────────────────────────────────
    PRINT           = "print"
    INPUT           = "input"
    READ_FILE       = "read_file"
    WRITE_FILE      = "write_file"

    # ── Type system ────────────────────────────────────────
    TYPE_INT        = "type_int"
    TYPE_FLOAT      = "type_float"
    TYPE_STRING     = "type_string"
    TYPE_BOOL       = "type_bool"
    TYPE_ARRAY      = "type_array"
    TYPE_MAP        = "type_map"
    TYPE_VOID       = "type_void"

    # ── Data structures ────────────────────────────────────
    MAP             = "map"           # map ... end

    # ── Boolean literals ───────────────────────────────────
    TRUE            = "true"
    FALSE           = "false"
    NONE            = "none"

    # ── Error handling ─────────────────────────────────────
    TRY             = "try"
    ERROR           = "error"
    FALLBACK        = "fallback"

    # ── Phase 3: Type system ───────────────────────────────
    ENUM_DEF        = "enum_def"      # enum
    TRAIT_DEF       = "trait_def"     # trait
    IMPL_BLOCK      = "impl_block"    # impl
    WHERE           = "where"         # where clause
    PIPE            = "pipe"          # | (closure param)
    DOUBLE_ARROW    = "double_arrow"  # => (match arm)
    TYPE_PARAM_OPEN = "type_param_open"   # <  (generic)
    TYPE_PARAM_CLOSE= "type_param_close"  # >  (generic)

    # ── System / runtime ───────────────────────────────────
    CHECK_CPU       = "check_cpu"
    PATCH           = "patch"
    TARGET_REGISTER = "target_register"
    EXECUTE         = "execute"
    SLEEP           = "sleep"
    SPAWN           = "spawn"
    AWAIT           = "await"

    # ── Delimiters & structure ─────────────────────────────
    OPEN_PAREN      = "open_paren"    # (
    CLOSE_PAREN     = "close_paren"   # )
    OPEN_BRACKET    = "open_bracket"  # [
    CLOSE_BRACKET   = "close_bracket" # ]
    OPEN_BRACE      = "open_brace"    # {
    CLOSE_BRACE     = "close_brace"   # }
    COMMA           = "comma"         # ,
    DOT             = "dot"           # .
    COLON           = "colon"         # :
    SEMICOLON       = "semicolon"     # ;
    ARROW           = "arrow"         # ->
    HASH            = "hash"          # # (comment marker)
    BLOCK_COMMENT   = "block_comment" # ## ... ## (block comment)

    # ── Literals (produced by tokenizer, not mapped) ───────
    NUMBER          = "number"
    STRING          = "string"
    IDENTIFIER      = "identifier"
    COMMENT         = "comment"
    EOF             = "eof"

    # ── Legacy compatibility aliases ───────────────────────
    # These are kept for backward compatibility but map to new tokens
    ELIF            = "elif"          # legacy → use EIF
    WHILE           = "while"         # legacy → use WHEN+LOOP
    FOR             = "for"           # legacy
    CONTINUE        = "continue"      # legacy → use SKIP
    RETURN          = "return"        # legacy → use OUT
    MATCH           = "match"         # legacy → use CASE
    BIT_AND         = "bit_and"       # legacy
    BIT_OR          = "bit_or"        # legacy
    ASSIGN_ADD      = "assign_add"    # legacy
    ASSIGN_SUB      = "assign_sub"    # legacy
    STRUCT          = "struct"        # legacy → use ENTITY_DEF
    RECORD          = "record"        # legacy → use ENTITY_DEF


# ═══════════════════════════════════════════════════════════
# Keyword metadata
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Keyword:
    """
    Metadata for a single keyword / operator.

    Attributes:
        kind:        The canonical TokenKind.
        english:     Primary English spelling (used in English-mode source).
        aliases:     Alternative English spellings.
        category:    Grouping for documentation / error messages.
        arity:       Number of operands (0=keyword, 1=unary, 2=binary).
        precedence:  Operator precedence (higher binds tighter). 0 for non-ops.
        description: Human-readable description.
    """

    kind: TokenKind
    english: str
    aliases: tuple[str, ...] = ()
    category: str = ""
    arity: int = 0
    precedence: int = 0
    description: str = ""


# ═══════════════════════════════════════════════════════════
# The Registry
# ═══════════════════════════════════════════════════════════

class KeywordRegistry:
    """
    Master registry of all Vir keywords and operators.

    Usage:
        reg = KeywordRegistry()
        kw  = reg.by_kind(TokenKind.IF)
        kw  = reg.by_english("if")
    """

    def __init__(self) -> None:
        self._by_kind: dict[TokenKind, Keyword] = {}
        self._by_english: dict[str, Keyword] = {}
        self._register_all()

    # ── Lookup ─────────────────────────────────────────────
    def by_kind(self, kind: TokenKind) -> Optional[Keyword]:
        return self._by_kind.get(kind)

    def by_english(self, word: str) -> Optional[Keyword]:
        return self._by_english.get(word.lower().strip())

    def all_keywords(self) -> list[Keyword]:
        return list(self._by_kind.values())

    def categories(self) -> dict[str, list[Keyword]]:
        cats: dict[str, list[Keyword]] = {}
        for kw in self._by_kind.values():
            cats.setdefault(kw.category, []).append(kw)
        return cats

    # ── Internal: register everything ──────────────────────
    def _register(self, kw: Keyword) -> None:
        self._by_kind[kw.kind] = kw
        self._by_english[kw.english.lower()] = kw
        for alias in kw.aliases:
            self._by_english[alias.lower()] = kw

    def _register_all(self) -> None:
        """Register all built-in keywords and operators (v1.2 spec)."""
        defs = [
            # ── Definitions ────────────────────────────────
            Keyword(TokenKind.FUNC_DEF,    "func",       ("function", "def", "fn"),
                    "definition", 0, 0, "Define a function"),
            Keyword(TokenKind.ASYNC,       "async",      (),
                    "definition", 0, 0, "Async function modifier"),
            Keyword(TokenKind.VAR_DECL,    "var",        ("let", "variable"),
                    "definition", 0, 0, "Module state block"),
            Keyword(TokenKind.CONST_DECL,  "const",      ("constant",),
                    "definition", 0, 0, "Declare a constant"),
            Keyword(TokenKind.CLASS_DEF,   "class",      (),
                    "definition", 0, 0, "Define a class"),
            Keyword(TokenKind.ENTITY_DEF,  "entity",     ("struct", "record"),
                    "definition", 0, 0, "Define an entity (struct)"),
            Keyword(TokenKind.METHOD_DEF,  "method",     (),
                    "definition", 0, 0, "Define a method on an entity"),
            Keyword(TokenKind.INCLUDE,     "include",    (),
                    "definition", 0, 0, "Include a file/module"),
            Keyword(TokenKind.IMPORT,      "import",     ("use",),
                    "definition", 0, 0, "Import from a module"),
            Keyword(TokenKind.FROM,        "from",       (),
                    "definition", 0, 0, "Source module for import"),
            Keyword(TokenKind.GET,         "get",        (),
                    "definition", 0, 0, "Selective import of shared state"),
            Keyword(TokenKind.EXPORT,      "export",     ("pub", "public"),
                    "definition", 0, 0, "Export functions"),
            Keyword(TokenKind.SHARE,       "share",      (),
                    "definition", 0, 0, "Share module state"),
            Keyword(TokenKind.HAS,         "has",        (),
                    "definition", 0, 0, "Forward declaration"),

            # ── Control flow (v1.2) ────────────────────────
            Keyword(TokenKind.IF,          "if",         (),
                    "control_flow", 0, 0, "Conditional branch"),
            Keyword(TokenKind.ELSE,        "else",       ("otherwise",),
                    "control_flow", 0, 0, "Else branch"),
            Keyword(TokenKind.EIF,         "eif",        (),
                    "control_flow", 0, 0, "Else-if branch"),
            Keyword(TokenKind.LOOP,        "loop",       ("repeat",),
                    "control_flow", 0, 0, "Loop block"),
            Keyword(TokenKind.WHEN,        "when",       (),
                    "control_flow", 0, 0, "Conditional loop: when <cond> loop"),
            Keyword(TokenKind.BREAK,       "break",      (),
                    "control_flow", 0, 0, "Break out of loop"),
            Keyword(TokenKind.SKIP,        "skip",       (),
                    "control_flow", 0, 0, "Skip to next iteration"),
            Keyword(TokenKind.OUT,         "out",        (),
                    "control_flow", 0, 0, "Return value from function"),
            Keyword(TokenKind.CASE,        "case",       (),
                    "control_flow", 0, 0, "Case expression"),
            Keyword(TokenKind.END,         "end",        (),
                    "control_flow", 0, 0, "Close block"),
            Keyword(TokenKind.IN,          "in",         (),
                    "control_flow", 0, 0, "Parameter block / iteration"),

            # ── Task / async ───────────────────────────────
            Keyword(TokenKind.TASK,        "task",       (),
                    "control_flow", 0, 0, "Define a task"),
            Keyword(TokenKind.WAIT,        "wait",       (),
                    "control_flow", 0, 0, "Wait for async function"),

            # ── Error handling ─────────────────────────────
            Keyword(TokenKind.TRY,         "try",        (),
                    "control_flow", 0, 0, "Try fallback"),
            Keyword(TokenKind.ERROR,       "error",      (),
                    "control_flow", 0, 0, "Error type"),
            Keyword(TokenKind.FALLBACK,    "fallback",   (),
                    "control_flow", 0, 0, "Fallback block in try"),

            # ── Phase 3: Type system ──────────────────────
            Keyword(TokenKind.ENUM_DEF,    "enum",       ("liệt_kê",),
                    "definition", 0, 0, "Define an enum type"),
            Keyword(TokenKind.TRAIT_DEF,   "trait",      ("đặc_tính",),
                    "definition", 0, 0, "Define a trait/interface"),
            Keyword(TokenKind.IMPL_BLOCK,  "impl",       ("triển_khai",),
                    "definition", 0, 0, "Implement a trait for a type"),
            Keyword(TokenKind.WHERE,       "where",      (),
                    "definition", 0, 0, "Generic constraint clause"),
            Keyword(TokenKind.PIPE,        "|",          (),
                    "definition", 0, 0, "Closure parameter delimiter"),
            Keyword(TokenKind.DOUBLE_ARROW,"=>",         ("→",),
                    "control_flow", 0, 0, "Match arm arrow"),

            # ── Arithmetic (v1.2 precedence) ───────────────
            # Precedence (high → low): () → ?. . → ! - → ^
            # → * / → % mod → + - → >> shl shr → :~
            # → > < >= <= → == != ?= ?=/= → & → xor → || → =
            Keyword(TokenKind.OP_ADD,      "+",          ("add", "plus"),
                    "arithmetic", 2, 10, "Addition"),
            Keyword(TokenKind.OP_SUB,      "-",          ("sub", "minus"),
                    "arithmetic", 2, 10, "Subtraction"),
            Keyword(TokenKind.OP_MUL,      "*",          ("mul", "times"),
                    "arithmetic", 2, 20, "Multiplication"),
            Keyword(TokenKind.OP_DIV,      "/",          ("div", "divide"),
                    "arithmetic", 2, 20, "Division"),
            Keyword(TokenKind.OP_POW,      "^",          ("pow", "power"),
                    "arithmetic", 2, 30, "Exponentiation"),
            Keyword(TokenKind.OP_PERCENT,  "%",          ("percent",),
                    "arithmetic", 2, 18, "Percentage (200 * 10% = 20)"),
            Keyword(TokenKind.OP_MOD,      "mod",        ("modulo", "remainder"),
                    "arithmetic", 2, 18, "Remainder: 10 mod 3 = 1"),

            # ── Comparison ─────────────────────────────────
            Keyword(TokenKind.CMP_EQ,      "==",         ("eq", "equals"),
                    "comparison", 2, 5, "Equal"),
            Keyword(TokenKind.CMP_NE,      "!=",         ("ne", "not_equal"),
                    "comparison", 2, 5, "Not equal"),
            Keyword(TokenKind.CMP_GT,      ">",          ("gt", "greater"),
                    "comparison", 2, 6, "Greater than"),
            Keyword(TokenKind.CMP_LT,      "<",          ("lt", "less"),
                    "comparison", 2, 6, "Less than"),
            Keyword(TokenKind.CMP_GE,      ">=",         ("ge", "greater_equal"),
                    "comparison", 2, 6, "Greater or equal"),
            Keyword(TokenKind.CMP_LE,      "<=",         ("le", "less_equal"),
                    "comparison", 2, 6, "Less or equal"),
            Keyword(TokenKind.CMP_SAFE_EQ, "?=",         (),
                    "comparison", 2, 5, "Safe equal (null-safe)"),
            Keyword(TokenKind.CMP_SAFE_NE, "?=/=",       (),
                    "comparison", 2, 5, "Safe not equal (null-safe)"),

            # ── Logical / Bitwise (v1.2) ───────────────────
            Keyword(TokenKind.LOGIC_AND,   "&",          ("and", "&&"),
                    "logical", 2, 3, "Logical/bitwise AND"),
            Keyword(TokenKind.LOGIC_OR,    "||",         ("or",),
                    "logical", 2, 2, "Logical/bitwise OR"),
            Keyword(TokenKind.LOGIC_NOT,   "!",          ("not",),
                    "logical", 1, 28, "Logical NOT"),
            Keyword(TokenKind.BIT_XOR,     "xor",        (),
                    "logical", 2, 2, "Bitwise XOR (between & and ||)"),
            Keyword(TokenKind.BIT_SHL,     "shl",        (),
                    "logical", 2, 12, "Shift left"),
            Keyword(TokenKind.BIT_SHR,     "shr",        (),
                    "logical", 2, 12, "Shift right"),

            # ── Access / Transform ─────────────────────────
            Keyword(TokenKind.OP_ACCESS,     ".",         (),
                    "access", 2, 40, "Member access"),
            Keyword(TokenKind.OP_SAFE_ACCESS,"?.",        (),
                    "access", 2, 40, "Safe member access (null-safe)"),
            Keyword(TokenKind.OP_EXIST,      "?",        (),
                    "access", 1, 35, "Existence check"),
            Keyword(TokenKind.OP_CAST,       ">>",       ("cast",),
                    "access", 2, 12, "Type cast"),
            Keyword(TokenKind.OP_PATTERN,    ":~",       (),
                    "access", 2, 8, "Pattern match operator"),

            # ── I/O ────────────────────────────────────────
            Keyword(TokenKind.PRINT,       "print",      ("echo", "output", "display"),
                    "io", 1, 0, "Print to stdout"),
            Keyword(TokenKind.INPUT,       "input",      ("read", "readline"),
                    "io", 1, 0, "Read from stdin"),

            # ── Types ──────────────────────────────────────
            Keyword(TokenKind.TYPE_INT,    "int",        ("integer",),
                    "type", 0, 0, "Integer type"),
            Keyword(TokenKind.TYPE_FLOAT,  "float",      ("double", "decimal"),
                    "type", 0, 0, "Float type"),
            Keyword(TokenKind.TYPE_STRING, "string",     ("str", "text"),
                    "type", 0, 0, "String type"),
            Keyword(TokenKind.TYPE_BOOL,   "bool",       ("boolean",),
                    "type", 0, 0, "Boolean type"),
            Keyword(TokenKind.TYPE_ARRAY,  "array",      ("list",),
                    "type", 0, 0, "Array type"),
            Keyword(TokenKind.TYPE_MAP,    "map_type",   ("dict", "hashmap"),
                    "type", 0, 0, "Map type"),
            Keyword(TokenKind.MAP,         "map",        (),
                    "data_structure", 0, 0, "Map literal: map ... end"),

            # ── Boolean / null literals ────────────────────
            Keyword(TokenKind.TRUE,        "true",       ("yes",),
                    "literal", 0, 0, "Boolean true"),
            Keyword(TokenKind.FALSE,       "false",      ("no",),
                    "literal", 0, 0, "Boolean false"),
            Keyword(TokenKind.NONE,        "none",       ("null", "nil"),
                    "literal", 0, 0, "None / null"),

            # ── System / runtime ───────────────────────────
            Keyword(TokenKind.CHECK_CPU,   "check_cpu",  ("cpu_idle",),
                    "system", 0, 0, "Check if CPU is idle"),
            Keyword(TokenKind.PATCH,       "patch",      ("hotpatch",),
                    "system", 0, 0, "Patch point for binary self-patching"),
            Keyword(TokenKind.TARGET_REGISTER, "register", ("reg",),
                    "system", 0, 0, "Target register-direct codegen"),
            Keyword(TokenKind.EXECUTE,     "execute",    ("run", "exec"),
                    "system", 0, 0, "Execute / begin"),
            Keyword(TokenKind.SLEEP,       "sleep",      ("delay",),
                    "system", 1, 0, "Sleep for N milliseconds"),
            Keyword(TokenKind.SPAWN,       "spawn",      (),
                    "system", 0, 0, "Spawn async task"),
            Keyword(TokenKind.AWAIT,       "await",      (),
                    "system", 0, 0, "Await async result"),

            # ── Legacy compatibility (map old → new) ──────
            Keyword(TokenKind.ELIF,        "elif",       ("elseif",),
                    "legacy", 0, 0, "Legacy: use eif"),
            Keyword(TokenKind.WHILE,       "while",      (),
                    "legacy", 0, 0, "Legacy: use when...loop"),
            Keyword(TokenKind.FOR,         "for",        ("foreach",),
                    "legacy", 0, 0, "Legacy: for loop"),
            Keyword(TokenKind.CONTINUE,    "continue",   (),
                    "legacy", 0, 0, "Legacy: use skip"),
            Keyword(TokenKind.RETURN,      "return",     (),
                    "legacy", 0, 0, "Legacy: use out"),
            Keyword(TokenKind.MATCH,       "match",      ("switch",),
                    "legacy", 0, 0, "Legacy: use case"),
        ]
        for kw in defs:
            self._register(kw)


# ═══════════════════════════════════════════════════════════
# Legacy Compatibility Map
# ═══════════════════════════════════════════════════════════
# Maps old TOKEN_* ir_token strings to TokenKind (for migration)

LEGACY_TOKEN_MAP: dict[str, TokenKind] = {
    "TOKEN_FUNC_DEF":        TokenKind.FUNC_DEF,
    "TOKEN_VAR_DECL":        TokenKind.VAR_DECL,
    "TOKEN_IF_CONDITION":    TokenKind.IF,
    "TOKEN_ELSE":            TokenKind.ELSE,
    "TOKEN_ELIF":            TokenKind.EIF,      # v1.2: eif
    "TOKEN_LOOP":            TokenKind.LOOP,
    "TOKEN_WHILE_LOOP":      TokenKind.WHEN,     # v1.2: when
    "TOKEN_RETURN":          TokenKind.OUT,       # v1.2: out
    "TOKEN_CONTINUE":        TokenKind.SKIP,      # v1.2: skip
    "TOKEN_BREAK":           TokenKind.BREAK,
    "TOKEN_END":             TokenKind.END,
    "TOKEN_OP_ADD":          TokenKind.OP_ADD,
    "TOKEN_OP_SUB":          TokenKind.OP_SUB,
    "TOKEN_OP_MUL":          TokenKind.OP_MUL,
    "TOKEN_OP_DIV":          TokenKind.OP_DIV,
    "TOKEN_OP_MOD":          TokenKind.OP_MOD,
    "TOKEN_OP_POW":          TokenKind.OP_POW,
    "TOKEN_CMP_EQ":          TokenKind.CMP_EQ,
    "TOKEN_CMP_NE":          TokenKind.CMP_NE,
    "TOKEN_CMP_GT":          TokenKind.CMP_GT,
    "TOKEN_CMP_LT":          TokenKind.CMP_LT,
    "TOKEN_CMP_GE":          TokenKind.CMP_GE,
    "TOKEN_CMP_LE":          TokenKind.CMP_LE,
    "TOKEN_PRINT":           TokenKind.PRINT,
    "TOKEN_INPUT":           TokenKind.INPUT,
    "TOKEN_PATCH":           TokenKind.PATCH,
    "TOKEN_CHECK_CPU":       TokenKind.CHECK_CPU,
    "TOKEN_TARGET_REGISTER": TokenKind.TARGET_REGISTER,
    "TOKEN_EXECUTE":         TokenKind.EXECUTE,
    "TOKEN_NUMBER":          TokenKind.NUMBER,
    "TOKEN_IDENTIFIER":      TokenKind.IDENTIFIER,
    # v1.2 new tokens
    "TOKEN_ENTITY":          TokenKind.ENTITY_DEF,
    "TOKEN_METHOD":          TokenKind.METHOD_DEF,
    "TOKEN_INCLUDE":         TokenKind.INCLUDE,
    "TOKEN_EXPORT":          TokenKind.EXPORT,
    "TOKEN_SHARE":           TokenKind.SHARE,
    "TOKEN_HAS":             TokenKind.HAS,
    "TOKEN_OUT":             TokenKind.OUT,
    "TOKEN_EIF":             TokenKind.EIF,
    "TOKEN_SKIP":            TokenKind.SKIP,
    "TOKEN_WHEN":            TokenKind.WHEN,
    "TOKEN_CASE":            TokenKind.CASE,
    "TOKEN_TASK":            TokenKind.TASK,
    "TOKEN_WAIT":            TokenKind.WAIT,
    "TOKEN_ASYNC":           TokenKind.ASYNC,
    "TOKEN_IN":              TokenKind.IN,
    "TOKEN_FROM":            TokenKind.FROM,
    "TOKEN_GET":             TokenKind.GET,
    "TOKEN_MAP":             TokenKind.MAP,
    "TOKEN_TRY":             TokenKind.TRY,
    "TOKEN_ERROR":           TokenKind.ERROR,
}

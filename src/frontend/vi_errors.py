"""
vi_errors.py – Vietnamese Error Messages
==========================================
Phase 3 – I4: Localized error messages in Vietnamese.

Provides a VirError hierarchy with bilingual error messages
and contextual source location display.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class ErrorSeverity(Enum):
    ERROR = "lỗi"        # Error
    WARNING = "cảnh báo"  # Warning
    HINT = "gợi ý"       # Hint


class ErrorCode(Enum):
    """Standard error codes with Vietnamese descriptions."""
    # Parse errors (P001-P099)
    P001_UNEXPECTED_TOKEN = auto()
    P002_MISSING_END = auto()
    P003_MISSING_COLON = auto()
    P004_MISSING_SEMICOLON = auto()
    P005_INVALID_SYNTAX = auto()
    P006_UNMATCHED_PAREN = auto()
    P007_DUPLICATE_PARAM = auto()

    # Type errors (T001-T099)
    T001_TYPE_MISMATCH = auto()
    T002_UNKNOWN_TYPE = auto()
    T003_INCOMPATIBLE_OPERANDS = auto()
    T004_WRONG_ARG_COUNT = auto()
    T005_WRONG_ARG_TYPE = auto()
    T006_MISSING_RETURN_TYPE = auto()
    T007_GENERIC_MISMATCH = auto()
    T008_TRAIT_NOT_IMPL = auto()

    # Name errors (N001-N099)
    N001_UNDEFINED_VAR = auto()
    N002_UNDEFINED_FUNC = auto()
    N003_DUPLICATE_DEF = auto()
    N004_UNDEFINED_TYPE = auto()
    N005_UNDEFINED_FIELD = auto()

    # Runtime errors (R001-R099)
    R001_DIVISION_BY_ZERO = auto()
    R002_INDEX_OUT_OF_BOUNDS = auto()
    R003_NULL_REFERENCE = auto()
    R004_STACK_OVERFLOW = auto()
    R005_OUT_OF_MEMORY = auto()


# Vietnamese translations
_VI_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.P001_UNEXPECTED_TOKEN:      "Token không mong đợi: {token}",
    ErrorCode.P002_MISSING_END:           "Thiếu 'end' để đóng khối {block}",
    ErrorCode.P003_MISSING_COLON:         "Thiếu ':' sau khai báo {name}",
    ErrorCode.P004_MISSING_SEMICOLON:     "Thiếu ';' sau câu lệnh",
    ErrorCode.P005_INVALID_SYNTAX:        "Cú pháp không hợp lệ: {detail}",
    ErrorCode.P006_UNMATCHED_PAREN:       "Ngoặc không khớp: mong đợi '{expected}'",
    ErrorCode.P007_DUPLICATE_PARAM:       "Tham số trùng lặp: '{name}'",

    ErrorCode.T001_TYPE_MISMATCH:         "Kiểu không khớp: mong đợi {expected}, nhận được {actual}",
    ErrorCode.T002_UNKNOWN_TYPE:          "Kiểu không xác định: '{type_name}'",
    ErrorCode.T003_INCOMPATIBLE_OPERANDS: "Toán hạng không tương thích: {left} {op} {right}",
    ErrorCode.T004_WRONG_ARG_COUNT:       "Hàm '{func}' cần {expected} tham số, nhận được {actual}",
    ErrorCode.T005_WRONG_ARG_TYPE:        "Tham số {index} của '{func}': mong đợi {expected}, nhận được {actual}",
    ErrorCode.T006_MISSING_RETURN_TYPE:   "Thiếu kiểu trả về cho hàm '{func}'",
    ErrorCode.T007_GENERIC_MISMATCH:      "Tham số kiểu không khớp: {detail}",
    ErrorCode.T008_TRAIT_NOT_IMPL:        "Kiểu '{type}' chưa triển khai đặc tính '{trait}'",

    ErrorCode.N001_UNDEFINED_VAR:         "Biến chưa khai báo: '{name}'",
    ErrorCode.N002_UNDEFINED_FUNC:        "Hàm chưa khai báo: '{name}'",
    ErrorCode.N003_DUPLICATE_DEF:         "Khai báo trùng lặp: '{name}'",
    ErrorCode.N004_UNDEFINED_TYPE:        "Kiểu chưa khai báo: '{name}'",
    ErrorCode.N005_UNDEFINED_FIELD:       "Trường không tồn tại: '{name}' trong '{entity}'",

    ErrorCode.R001_DIVISION_BY_ZERO:      "Lỗi chia cho 0",
    ErrorCode.R002_INDEX_OUT_OF_BOUNDS:   "Chỉ mục ngoài phạm vi: {index} (kích thước: {size})",
    ErrorCode.R003_NULL_REFERENCE:        "Tham chiếu null",
    ErrorCode.R004_STACK_OVERFLOW:        "Tràn ngăn xếp (stack overflow)",
    ErrorCode.R005_OUT_OF_MEMORY:         "Hết bộ nhớ",
}

# English translations (fallback)
_EN_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.P001_UNEXPECTED_TOKEN:      "Unexpected token: {token}",
    ErrorCode.P002_MISSING_END:           "Missing 'end' to close {block} block",
    ErrorCode.P003_MISSING_COLON:         "Missing ':' after {name} declaration",
    ErrorCode.P004_MISSING_SEMICOLON:     "Missing ';' after statement",
    ErrorCode.P005_INVALID_SYNTAX:        "Invalid syntax: {detail}",
    ErrorCode.P006_UNMATCHED_PAREN:       "Unmatched parenthesis: expected '{expected}'",
    ErrorCode.P007_DUPLICATE_PARAM:       "Duplicate parameter: '{name}'",

    ErrorCode.T001_TYPE_MISMATCH:         "Type mismatch: expected {expected}, got {actual}",
    ErrorCode.T002_UNKNOWN_TYPE:          "Unknown type: '{type_name}'",
    ErrorCode.T003_INCOMPATIBLE_OPERANDS: "Incompatible operands: {left} {op} {right}",
    ErrorCode.T004_WRONG_ARG_COUNT:       "Function '{func}' expects {expected} args, got {actual}",
    ErrorCode.T005_WRONG_ARG_TYPE:        "Arg {index} of '{func}': expected {expected}, got {actual}",
    ErrorCode.T006_MISSING_RETURN_TYPE:   "Missing return type for function '{func}'",
    ErrorCode.T007_GENERIC_MISMATCH:      "Generic type parameter mismatch: {detail}",
    ErrorCode.T008_TRAIT_NOT_IMPL:        "Type '{type}' does not implement trait '{trait}'",

    ErrorCode.N001_UNDEFINED_VAR:         "Undefined variable: '{name}'",
    ErrorCode.N002_UNDEFINED_FUNC:        "Undefined function: '{name}'",
    ErrorCode.N003_DUPLICATE_DEF:         "Duplicate definition: '{name}'",
    ErrorCode.N004_UNDEFINED_TYPE:        "Undefined type: '{name}'",
    ErrorCode.N005_UNDEFINED_FIELD:       "No such field: '{name}' in '{entity}'",

    ErrorCode.R001_DIVISION_BY_ZERO:      "Division by zero",
    ErrorCode.R002_INDEX_OUT_OF_BOUNDS:   "Index out of bounds: {index} (size: {size})",
    ErrorCode.R003_NULL_REFERENCE:        "Null reference",
    ErrorCode.R004_STACK_OVERFLOW:        "Stack overflow",
    ErrorCode.R005_OUT_OF_MEMORY:         "Out of memory",
}


@dataclass
class SourceLocation:
    """Source code location."""
    file: str = ""
    line: int = 0
    column: int = 0
    length: int = 0


@dataclass
class VirError:
    """A Vir compiler/runtime error with bilingual message."""
    code: ErrorCode
    severity: ErrorSeverity = ErrorSeverity.ERROR
    location: Optional[SourceLocation] = None
    params: dict[str, str] = field(default_factory=dict)
    source_line: str = ""

    def message(self, lang: str = "vi") -> str:
        """Get formatted error message in specified language."""
        templates = _VI_MESSAGES if lang == "vi" else _EN_MESSAGES
        template = templates.get(self.code, f"[{self.code.name}]")
        try:
            return template.format(**self.params)
        except KeyError:
            return template

    def display(self, lang: str = "vi") -> str:
        """Full error display with location and source context."""
        parts: list[str] = []

        # Location
        loc = ""
        if self.location:
            loc = f"{self.location.file}:{self.location.line}:{self.location.column}"

        # Severity + code
        sev = self.severity.value if lang == "vi" else self.severity.name.lower()
        code_str = self.code.name.split("_")[0]  # P001, T001, etc.

        parts.append(f"{sev}[{code_str}]: {self.message(lang)}")
        if loc:
            parts.append(f"  --> {loc}")
        if self.source_line:
            line_num = self.location.line if self.location else 0
            parts.append(f"  {line_num:4d} | {self.source_line}")
            if self.location and self.location.column > 0:
                pointer = " " * (7 + self.location.column) + "^"
                if self.location.length > 1:
                    pointer += "~" * (self.location.length - 1)
                parts.append(pointer)

        return "\n".join(parts)


class ErrorCollector:
    """Collect errors during compilation."""

    def __init__(self, lang: str = "vi"):
        self.errors: list[VirError] = []
        self.lang = lang

    def add(self, code: ErrorCode, location: Optional[SourceLocation] = None,
            source_line: str = "", severity: ErrorSeverity = ErrorSeverity.ERROR,
            **params: str) -> None:
        self.errors.append(VirError(
            code=code,
            severity=severity,
            location=location,
            params=params,
            source_line=source_line,
        ))

    def has_errors(self) -> bool:
        return any(e.severity == ErrorSeverity.ERROR for e in self.errors)

    def display_all(self) -> str:
        return "\n\n".join(e.display(self.lang) for e in self.errors)

    @property
    def count(self) -> int:
        return len(self.errors)

    def summary(self) -> str:
        errors = sum(1 for e in self.errors if e.severity == ErrorSeverity.ERROR)
        warnings = sum(1 for e in self.errors if e.severity == ErrorSeverity.WARNING)
        if self.lang == "vi":
            return f"{errors} lỗi, {warnings} cảnh báo"
        return f"{errors} error(s), {warnings} warning(s)"

"""VPS error types."""


class VPSError(Exception):
    """Base error for all VPS operations."""

    def __init__(self, message: str, pos: int | None = None):
        self.pos = pos
        prefix = f"[pos {pos}] " if pos is not None else ""
        super().__init__(f"{prefix}{message}")


class VPSLexError(VPSError):
    """Tokenization error."""


class VPSParseError(VPSError):
    """Parsing error."""


class VPSCompileError(VPSError):
    """Compilation error (VPS → regex)."""

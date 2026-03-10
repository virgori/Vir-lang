"""
code_validator.py – Bộ xác thực mã trước khi thực thi
=======================================================
Kiểm tra tính toàn vẹn của patched code trước khi cho phép chạy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.security.signer.internal_signer import InternalSigner


@dataclass
class ValidationResult:
    """Kết quả xác thực."""
    patch_id: str
    is_valid: bool
    reason: str = ""


class CodeValidator:
    """
    Xác thực tất cả patched code trước khi cho phép thực thi.
    Nếu bất kỳ patch nào không hợp lệ → ngắt chương trình.
    """

    def __init__(self, signer: InternalSigner) -> None:
        self._signer = signer

    def validate_patch(self, patch_id: str, code_bytes: bytes) -> ValidationResult:
        """Xác thực 1 đoạn patch."""
        if self._signer.verify(patch_id, code_bytes):
            return ValidationResult(patch_id=patch_id, is_valid=True, reason="OK")
        return ValidationResult(
            patch_id=patch_id,
            is_valid=False,
            reason=f"Signature mismatch for {patch_id} – possible tampering detected!",
        )

    def validate_all(
        self, patches: dict[str, bytes]
    ) -> tuple[bool, list[ValidationResult]]:
        """
        Xác thực tất cả patches.
        Trả về (all_valid, results).
        """
        results: list[ValidationResult] = []
        all_valid = True

        for patch_id, code_bytes in patches.items():
            result = self.validate_patch(patch_id, code_bytes)
            results.append(result)
            if not result.is_valid:
                all_valid = False

        return all_valid, results

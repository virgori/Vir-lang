"""
internal_signer.py – Chữ ký số nội bộ (Internal Signer)
=========================================================
Spec §4.2 – Mọi đoạn mã được vá (patched code) phải đi kèm
một mã băm (Hash) được ký bởi Quizz-Core Key.

Nếu Hash không khớp → OS/Runtime sẽ ngắt chương trình.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class CodeSignature:
    """Chữ ký cho một đoạn mã đã vá."""
    patch_id: str
    code_hash: str          # SHA-256 hex digest
    hmac_signature: str     # HMAC-SHA256 hex digest
    nonce: str              # Random nonce (chống replay)


class InternalSigner:
    """
    Bộ ký & xác minh mã nội bộ.

    Sử dụng HMAC-SHA256 với Quizz-Core Key (generated per session).
    Production sẽ dùng key từ HSM / Secure Enclave.
    """

    def __init__(self, key: bytes | None = None) -> None:
        self._key = key or secrets.token_bytes(32)
        self._signatures: dict[str, CodeSignature] = {}

    @property
    def key_fingerprint(self) -> str:
        """Trả về fingerprint (SHA-256 truncated) của key hiện tại."""
        return hashlib.sha256(self._key).hexdigest()[:16]

    # ── Sign ───────────────────────────────────────────────
    def sign(self, patch_id: str, code_bytes: bytes) -> CodeSignature:
        """
        Ký một đoạn mã.
        Trả về CodeSignature chứa hash + HMAC.
        """
        nonce = secrets.token_hex(16)
        code_hash = hashlib.sha256(code_bytes).hexdigest()

        # HMAC = HMAC-SHA256(key, patch_id || code_hash || nonce)
        message = f"{patch_id}:{code_hash}:{nonce}".encode()
        sig = hmac.new(self._key, message, hashlib.sha256).hexdigest()

        signature = CodeSignature(
            patch_id=patch_id,
            code_hash=code_hash,
            hmac_signature=sig,
            nonce=nonce,
        )
        self._signatures[patch_id] = signature
        return signature

    # ── Verify ─────────────────────────────────────────────
    def verify(self, patch_id: str, code_bytes: bytes) -> bool:
        """
        Xác minh: code hiện tại có khớp chữ ký đã lưu không?
        Trả về False nếu không khớp (có thể bị can thiệp / virus).
        """
        stored = self._signatures.get(patch_id)
        if stored is None:
            return False

        # Kiểm tra code hash
        current_hash = hashlib.sha256(code_bytes).hexdigest()
        if current_hash != stored.code_hash:
            return False

        # Kiểm tra HMAC
        message = f"{patch_id}:{stored.code_hash}:{stored.nonce}".encode()
        expected_sig = hmac.new(self._key, message, hashlib.sha256).hexdigest()

        return hmac.compare_digest(expected_sig, stored.hmac_signature)

    # ── Revoke ─────────────────────────────────────────────
    def revoke(self, patch_id: str) -> bool:
        """Thu hồi chữ ký (khi rollback patch)."""
        if patch_id in self._signatures:
            del self._signatures[patch_id]
            return True
        return False

    def list_signed(self) -> list[str]:
        """Trả về danh sách patch_id đã ký."""
        return list(self._signatures.keys())

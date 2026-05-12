"""
test_security.py – Unit tests cho Security (signer, validator)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.security.signer.internal_signer import InternalSigner
from src.security.validator.code_validator import CodeValidator


class TestInternalSigner:
    def test_sign_and_verify(self):
        signer = InternalSigner()
        code = b"\x48\x01\xD8\xC3"  # ADD RAX, RBX; RET
        sig = signer.sign("PATCH_1", code)
        assert sig.patch_id == "PATCH_1"
        assert signer.verify("PATCH_1", code)

    def test_verify_tampered(self):
        signer = InternalSigner()
        code = b"\x48\x01\xD8\xC3"
        signer.sign("PATCH_1", code)
        # Tamper the code
        tampered = b"\x48\x01\xD8\x90"
        assert not signer.verify("PATCH_1", tampered)

    def test_verify_unknown(self):
        signer = InternalSigner()
        assert not signer.verify("UNKNOWN", b"\x00")

    def test_revoke(self):
        signer = InternalSigner()
        signer.sign("PATCH_1", b"\xC3")
        assert signer.revoke("PATCH_1")
        assert not signer.verify("PATCH_1", b"\xC3")

    def test_key_fingerprint(self):
        signer = InternalSigner()
        fp = signer.key_fingerprint
        assert len(fp) == 16


class TestCodeValidator:
    def test_validate_good(self):
        signer = InternalSigner()
        code = b"\x48\x01\xD8"
        signer.sign("P1", code)

        validator = CodeValidator(signer)
        result = validator.validate_patch("P1", code)
        assert result.is_valid

    def test_validate_bad(self):
        signer = InternalSigner()
        code = b"\x48\x01\xD8"
        signer.sign("P1", code)

        validator = CodeValidator(signer)
        result = validator.validate_patch("P1", b"\xFF\xFF")
        assert not result.is_valid

    def test_validate_all(self):
        signer = InternalSigner()
        signer.sign("P1", b"\x01")
        signer.sign("P2", b"\x02")

        validator = CodeValidator(signer)
        all_valid, results = validator.validate_all({
            "P1": b"\x01",
            "P2": b"\x02",
        })
        assert all_valid
        assert len(results) == 2

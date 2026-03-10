"""
test_lifecycle.py – Integration test: End-to-end compilation
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.runtime.lifecycle.lifecycle import VirRuntime


@pytest.fixture
def runtime():
    return VirRuntime(enable_jit=False)


class TestEndToEnd:
    def test_compile_spec_example(self, runtime):
        """Spec §5 ví dụ: 'Nếu máy rảnh, tính tổng A và B bằng thanh ghi.'"""
        result = runtime.compile(
            "Nếu máy rảnh, tính tổng A và B bằng thanh ghi."
        )
        assert len(result.tokens) > 0
        assert result.ir_dump  # Q-IR non-empty
        assert result.compile_time_ms >= 0

    def test_compile_func_def(self, runtime):
        result = runtime.compile("Ta có hàm cộng X Y. Tính tổng X Y. Trả về X.")
        assert len(result.tokens) > 0
        assert "func" in result.ir_dump.lower() or "Q_" in result.ir_dump

    def test_compile_variable(self, runtime):
        result = runtime.compile("Cho biến X 10. Cho biến Y 20. Tính tổng X Y.")
        assert len(result.tokens) > 0

    def test_compile_print(self, runtime):
        result = runtime.compile("Cho biến X 42. In ra X.")
        tokens_ir = [t.ir_token for t in result.tokens]
        assert "print" in tokens_ir

    def test_status(self, runtime):
        status = runtime.status()
        assert "arch" in status
        assert "cpu_load" in status

    def test_dump_tokens(self, runtime):
        result = runtime.compile("Tính tổng 1 2")
        dump = runtime.dump_tokens(result)
        assert "OP_ADD" in dump

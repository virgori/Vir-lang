#!/usr/bin/env python3
"""Regression and mutation checks for source spans after module expansion."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIRC = Path(os.environ.get("VIRC", ROOT / "bin/virc"))


@dataclass(frozen=True)
class ExpectedDiagnostic:
    fixture: str
    code: str
    line: int
    column: int
    end_column: int


CASES = (
    ExpectedDiagnostic(
        "tests/strict_v2/ufcs_unresolved_receiver_rejected.vri",
        "E2001",
        12,
        15,
        25,
    ),
    ExpectedDiagnostic(
        "tests/strict_v2/ufcs_entity_receiver_type_mismatch_rejected.vri",
        "E3001",
        17,
        15,
        18,
    ),
    ExpectedDiagnostic(
        "tests/strict_v2/ufcs_free_arg_type_mismatch_rejected.vri",
        "E3001",
        11,
        23,
        26,
    ),
    ExpectedDiagnostic(
        "tests/test_source_map_include_boundary_rejected.vri",
        "E2001",
        7,
        13,
        25,
    ),
    ExpectedDiagnostic(
        "tests/test_source_map_import_boundary_rejected.vri",
        "E2001",
        7,
        13,
        25,
    ),
)


def diagnostic_span(expected: ExpectedDiagnostic) -> dict[str, object]:
    environment = dict(os.environ, VIRC_UI="classic", NO_COLOR="1")
    result = subprocess.run(
        [str(VIRC), expected.fixture, "--check", "--json"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 0:
        raise AssertionError(f"negative fixture unexpectedly passed: {expected.fixture}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(
            f"compiler did not emit diagnostic JSON for {expected.fixture}: {result.stdout!r}"
        ) from error
    for diagnostic in payload.get("diagnostics", []):
        span = diagnostic.get("primary_span", {})
        if diagnostic.get("code") == expected.code and span.get("file") == expected.fixture:
            return span
    raise AssertionError(
        f"missing {expected.code} for {expected.fixture}: {payload.get('diagnostics', [])!r}"
    )


def assert_expected_span(span: dict[str, object], expected: ExpectedDiagnostic) -> None:
    actual = (
        span.get("file"),
        span.get("start_line"),
        span.get("start_column"),
        span.get("end_line"),
        span.get("end_column"),
    )
    wanted = (
        expected.fixture,
        expected.line,
        expected.column,
        expected.line,
        expected.end_column,
    )
    if actual != wanted:
        raise AssertionError(f"expected span {wanted!r}, got {actual!r}")


class SourceMapSpanTest(unittest.TestCase):
    def test_exact_spans_after_include_and_import_expansion(self) -> None:
        for expected in CASES:
            with self.subTest(fixture=expected.fixture, code=expected.code):
                assert_expected_span(diagnostic_span(expected), expected)

    def test_oracle_rejects_one_line_shift_mutation(self) -> None:
        expected = CASES[3]
        shifted = copy.deepcopy(diagnostic_span(expected))
        shifted["start_line"] = int(shifted["start_line"]) + 1
        shifted["end_line"] = int(shifted["end_line"]) + 1

        with self.assertRaises(AssertionError):
            assert_expected_span(shifted, expected)


if __name__ == "__main__":
    unittest.main()

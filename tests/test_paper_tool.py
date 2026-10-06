#!/usr/bin/env python3

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "paper.py"


class PaperToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        shutil.copytree(REPO_ROOT / "papers", self.root / "papers")
        for domain in ("VIR", "VIRC", "VLSP", "STLB"):
            for paper_type in ("issues", "plans", "reports"):
                for paper in (self.root / "papers" / domain / paper_type).glob("*.md"):
                    paper.unlink()
        (self.root / "papers" / "REGISTRY.yaml").write_text(
            'version: 1\nstandard_version: "1.0.0"\npapers: []\n',
            encoding="utf-8",
        )
        skill_source = REPO_ROOT / ".agents" / "skills" / "vir-paper-management"
        shutil.copytree(skill_source, self.root / ".agents" / "skills" / "vir-paper-management")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_tool(self, *arguments: str, success: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(TOOL), "--root", str(self.root), *arguments],
            text=True,
            capture_output=True,
            check=False,
            env={"PAPER_TODAY": "2026-10-02"},
        )
        if success and result.returncode != 0:
            self.fail(f"paper {' '.join(arguments)} failed:\n{result.stdout}\n{result.stderr}")
        if not success and result.returncode == 0:
            self.fail(f"paper {' '.join(arguments)} unexpectedly passed")
        return result

    def test_repository_fixture_validates(self) -> None:
        result = self.run_tool("validate")
        self.assertIn("3 example paper(s)", result.stdout)

    def test_create_link_list_show_and_validate_chain(self) -> None:
        issue = self.run_tool(
            "new", "issue", "VIRC", "Optimizer loses verifier state",
            "--severity", "S1", "--priority", "P1",
        )
        self.assertIn("VIRC-ISS-0001", issue.stdout)

        missing_source = self.run_tool(
            "new", "plan", "VIRC", "Unlinked plan", success=False,
        )
        self.assertIn("requires at least one --issue", missing_source.stderr)

        plan = self.run_tool(
            "new", "plan", "VIRC", "Preserve verifier state",
            "--issue", "VIRC-ISS-0001",
        )
        self.assertIn("VIRC-PLN-0001", plan.stdout)
        report = self.run_tool(
            "new", "report", "VIRC", "Verifier state implementation",
            "--issue", "VIRC-ISS-0001", "--plan", "VIRC-PLN-0001",
        )
        self.assertIn("VIRC-RPT-0001", report.stdout)

        listing = self.run_tool("list", "--domain", "VIRC")
        self.assertIn("VIRC-ISS-0001", listing.stdout)
        self.assertIn("VIRC-PLN-0001", listing.stdout)
        self.assertIn("VIRC-RPT-0001", listing.stdout)
        shown = self.run_tool("show", "VIRC-RPT-0001")
        self.assertIn("# VIRC-RPT-0001 — Verifier state implementation", shown.stdout)
        self.assertIn("- VIRC-ISS-0001", shown.stdout)
        self.assertIn("- VIRC-PLN-0001", shown.stdout)
        self.run_tool("registry", "--check")
        self.run_tool("validate")

        issue_path = next((self.root / "papers" / "VIRC" / "issues").glob("*.md"))
        issue_text = issue_path.read_text(encoding="utf-8")
        self.assertIn("VIRC-PLN-0001", issue_text)
        self.assertIn("VIRC-RPT-0001", issue_text)

        self.run_tool("new", "issue", "VIRC", "Secondary verifier symptom")
        self.run_tool("link", "VIRC-ISS-0001", "VIRC-ISS-0002")
        linked = self.run_tool("show", "VIRC-ISS-0002")
        self.assertIn("VIRC-ISS-0001", linked.stdout)
        self.run_tool("validate")

    def test_validator_rejects_registry_drift(self) -> None:
        self.run_tool("new", "issue", "VIR", "Example semantic mismatch")
        registry = self.root / "papers" / "REGISTRY.yaml"
        registry.write_text(
            registry.read_text(encoding="utf-8").replace(
                'title: "Example semantic mismatch"', 'title: "Stale title"'
            ),
            encoding="utf-8",
        )
        result = self.run_tool("registry", "--check", success=False)
        self.assertIn("out of sync", result.stderr)
        validation = self.run_tool("validate", success=False)
        self.assertIn("registry entry differs", validation.stderr)
        self.run_tool("registry", "--write")
        self.run_tool("validate")

    def test_schemas_are_json_schema_2020_12(self) -> None:
        for path in sorted((self.root / "papers" / "schemas").glob("*.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
            )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""
tools/test_migrate_generic_of_syntax.py — Unit test suite for the generic migration tool.

Verifies all requirements of docs/plan/STRICT_VIR_OF_GENERIC_SYNTAX_MIGRATION_PROMPT.md §6.1:
- Single and multi-argument generics
- Nested generics Vec<Vec<string>>
- Declarations, type applications, calls, and constructors
- tensor, flux, dict, Vec
- String/comment literals containing <T> preserved
- Comparison (<, >, <=, >=) and operators (><, <-, >>) preserved
- Foreign #include <metal_stdlib> preserved
- Dry-run does not write to disk
- Apply creates manifest, backups, and rewrites atomically
- Rollback restores original state
- Rollback aborts if file was modified after migration
- Idempotence: second apply is a no-op
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from migrate_generic_of_syntax import (
    rewrite_file_content,
    run_dry_run,
    run_apply,
    run_rollback,
    sha256_content,
    sha256_file,
)

class TestGenericMigrationTool(unittest.TestCase):
    def test_single_and_multi_generic_declaration(self):
        code = """entity Box<T>:
    value: T
end.

enum Result<T, E>:
    Ok(value: T)
    Err(error: E)
end.

func identity<T>(value: T) -> T:
    out value
end.
"""
        expected = """entity Box of (T):
    value: T
end.

enum Result of (T, E):
    Ok(value: T)
    Err(error: E)
end.

func identity of (T)(value: T) -> T:
    out value
end.
"""
        res, matches, retained, manual, counts = rewrite_file_content(code)
        self.assertEqual(res, expected)
        self.assertEqual(counts["declaration"], 3)
        self.assertEqual(len(manual), 0)

    def test_type_applications_and_nested_generics(self):
        code = """var box: Box<int>
var result: Result<int, string>
var nested: Vec<Vec<string>>
var table: dict<string, Vec<int>>
var three_levels: Vec<Vec<Vec<int>>>
"""
        expected = """var box: Box of (int)
var result: Result of (int, string)
var nested: Vec of (Vec of (string))
var table: dict of (string, Vec of (int))
var three_levels: Vec of (Vec of (Vec of (int)))
"""
        res, matches, retained, manual, counts = rewrite_file_content(code)
        self.assertEqual(res, expected)
        self.assertEqual(counts["type application"], 2)
        self.assertEqual(counts["dict/Vec"], 7)
        self.assertEqual(len(manual), 0)

    def test_calls_and_constructors(self):
        code = """var value = identity<int>(42)
var pair = Pair<int, string>(first: 42, second: "Vir")
var sz = size_of<int>()
var item = vec_get<Token>(tokens, 0)
"""
        expected = """var value = identity of (int)(42)
var pair = Pair of (int, string)(first: 42, second: "Vir")
var sz = size_of of (int)()
var item = vec_get of (Token)(tokens, 0)
"""
        res, matches, retained, manual, counts = rewrite_file_content(code)
        self.assertEqual(res, expected)
        self.assertEqual(counts["explicit generic call"], 3)
        self.assertEqual(counts["constructor"], 1)
        self.assertEqual(len(manual), 0)

    def test_builtins_tensor_and_flux(self):
        code = """var lanes: flux<f32, 4>
var weights: tensor<f32>[784, 128]
var cube: tensor<i32>[2, 2, 2]
"""
        expected = """var lanes: flux of (f32, 4)
var weights: tensor of (f32)[784, 128]
var cube: tensor of (i32)[2, 2, 2]
"""
        res, matches, retained, manual, counts = rewrite_file_content(code)
        self.assertEqual(res, expected)
        self.assertEqual(counts["flux"], 1)
        self.assertEqual(counts["tensor"], 2)
        self.assertEqual(len(manual), 0)

    def test_strings_and_comments_preserved(self):
        code = """# Comment with Box<T> and Option<int>
#* Block comment with Vec<string> *#
## Doc comment with tensor<f32>[2, 2] ##
print("String with Pair<int, string>")
var ch = '<'
"""
        res, matches, retained, manual, counts = rewrite_file_content(code)
        self.assertEqual(res, code)
        self.assertEqual(len(matches), 0)
        self.assertEqual(len(manual), 0)

    def test_comparisons_and_operators_preserved(self):
        code = """if a < b do
    out 1
end

if a > b do
    out 2
end

if a <= b do
    out 3
end

if a >= b do
    out 4
end

var c = a >< b
send channel <- value
var shifted = bits >> 2
var chained = a < b > c
"""
        res, matches, retained, manual, counts = rewrite_file_content(code)
        self.assertEqual(res, code)
        self.assertEqual(len(matches), 0)
        self.assertEqual(len(manual), 0)

    def test_foreign_include_preserved(self):
        code = """#include <metal_stdlib>
#include <stdio.h>
"""
        res, matches, retained, manual, counts = rewrite_file_content(code)
        self.assertEqual(res, code)
        self.assertEqual(len(matches), 0)

    def test_apply_and_rollback_transaction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            test_root = Path(temp_dir) / "repo"
            test_root.mkdir()
            backup_dir = Path(temp_dir) / "backup"

            src_file = test_root / "sample.vri"
            original_code = """entity Box<T>:
    val: T
end.

func main:
    var b: Box<int>
    var res = identity<int>(10)
end.
"""
            src_file.write_text(original_code, encoding="utf-8")
            orig_sha = sha256_content(original_code)

            # Dry run test: file must NOT change
            ret_dry = run_dry_run(test_root, [src_file])
            self.assertEqual(ret_dry, 0)
            self.assertEqual(src_file.read_text(encoding="utf-8"), original_code)

            # Apply test
            ret_apply = run_apply(test_root, [src_file], backup_dir)
            self.assertEqual(ret_apply, 0)

            migrated_code = src_file.read_text(encoding="utf-8")
            self.assertIn("entity Box of (T):", migrated_code)
            self.assertIn("var b: Box of (int)", migrated_code)
            self.assertIn("var res = identity of (int)(10)", migrated_code)
            self.assertNotEqual(migrated_code, original_code)

            manifest_path = backup_dir / "manifest.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "completed")

            # Second apply (idempotence test)
            ret_apply2 = run_apply(test_root, [src_file], backup_dir / "backup2")
            self.assertEqual(ret_apply2, 0)
            self.assertEqual(src_file.read_text(encoding="utf-8"), migrated_code)

            # Rollback test
            ret_rb = run_rollback(manifest_path)
            self.assertEqual(ret_rb, 0)
            self.assertEqual(src_file.read_text(encoding="utf-8"), original_code)
            self.assertEqual(sha256_file(src_file), orig_sha)

    def test_rollback_conflict_protection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            test_root = Path(temp_dir) / "repo"
            test_root.mkdir()
            backup_dir = Path(temp_dir) / "backup"

            src_file = test_root / "sample.vri"
            original_code = "var x: Box<int>\n"
            src_file.write_text(original_code, encoding="utf-8")

            run_apply(test_root, [src_file], backup_dir)
            manifest_path = backup_dir / "manifest.json"

            # User edits file after migration
            src_file.write_text("var x: Box of (string)\n# user edited\n", encoding="utf-8")

            # Rollback must refuse to overwrite due to conflict!
            ret_rb = run_rollback(manifest_path)
            self.assertEqual(ret_rb, 1)
            self.assertIn("user edited", src_file.read_text(encoding="utf-8"))

    def test_apply_failure_midway_rolls_back(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            test_root = Path(temp_dir) / "repo"
            test_root.mkdir()
            backup_dir = Path(temp_dir) / "backup"

            file1 = test_root / "file1.vri"
            file2 = test_root / "file2.vri"
            code1 = "var a: Box<int>\n"
            code2 = "var b: Box<string>\n"
            file1.write_text(code1, encoding="utf-8")
            file2.write_text(code2, encoding="utf-8")

            # Monkey-patch os.replace to fail on file2
            real_replace = os.replace
            def fail_on_file2(src, dst):
                if "file2" in str(dst):
                    raise PermissionError("Simulated disk error on file2")
                return real_replace(src, dst)

            orig_replace = os.replace
            try:
                os.replace = fail_on_file2
                ret = run_apply(test_root, [file1, file2], backup_dir)
                self.assertEqual(ret, 1)
                # Verify file1 was rolled back to original code
                self.assertEqual(file1.read_text(encoding="utf-8"), code1)
                self.assertEqual(file2.read_text(encoding="utf-8"), code2)
            finally:
                os.replace = orig_replace

if __name__ == "__main__":
    unittest.main()

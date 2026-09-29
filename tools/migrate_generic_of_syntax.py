#!/usr/bin/env python3
"""
tools/migrate_generic_of_syntax.py — Migrate Vir generic syntax from `<T>` to `of (T)`.

Adheres strictly to docs/plan/STRICT_VIR_OF_GENERIC_SYNTAX_MIGRATION_PROMPT.md §6.1:
- Token-aware scanner distinguishing generics from operators (<, >, <=, >=, ><, <-, >>),
  comments (line, block, doc ##...##), strings, and foreign includes (#include <...>).
- Transactional migration with manifest, SHA-256 verification, and atomic apply.
- Safe rollback verifying post-image SHA-256 before restoration.
- Idempotent and dry-run preview by default.

Usage:
    python3 tools/migrate_generic_of_syntax.py --dry-run
    python3 tools/migrate_generic_of_syntax.py --apply --backup-dir ./scratch/migration_backup
    python3 tools/migrate_generic_of_syntax.py --rollback ./scratch/migration_backup/manifest.json
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

DEFAULT_ROOTS = ["stdlib/vir/compiler", "stdlib/vir", "tests"]
DEFAULT_EXCLUDES = [
    ".git",
    "frozen",
    "node_modules",
    "stdlib/vir/compiler/virc.vri",  # Generated bundle synced from modules
    "scratch",
    "dist",
    "bin",
]

FORBIDDEN_KEYWORDS = {
    "if", "when", "loop", "do", "while", "for", "in", "case", "break", "skip",
    "out", "return", "throw", "revert", "ensure", "try", "emit", "task", "await",
    "select", "on", "quiet", "send", "recv", "var", "let", "const", "func",
    "entity", "enum", "mold", "end", "end.", "or", "and", "xor", "shl", "shr", "not"
}

FORBIDDEN_SYMBOLS = {
    "==", "!=", "<=", ">=", "?=", "&&", "||", "+", "-", "*", "/", "%", "**", "^", "><", "<-", "="
}

CATEGORIES = (
    "declaration",
    "type application",
    "explicit generic call",
    "constructor",
    "dict/Vec",
    "flux",
    "tensor",
)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def sha256_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

@dataclass
class Token:
    kind: str
    value: str
    start: int
    end: int
    line: int
    col: int

def tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    n = len(text)
    line = 1
    col = 1

    while i < n:
        start = i
        start_col = col
        start_line = line
        ch = text[i]

        # Foreign preprocessor include, e.g. #include <metal_stdlib>
        if ch == "#" and text[i:i+8] == "#include":
            eol = text.find("\n", i)
            if eol == -1:
                eol = n
            line_str = text[i:eol]
            if "<" in line_str and ">" in line_str:
                tokens.append(Token("FOREIGN_INC", text[i:eol], i, eol, line, col))
                col += eol - i
                i = eol
                continue

        # Comments
        if ch == "#":
            if i + 2 < n and text[i:i+3] == "#*#":
                end = text.find("#*#", i + 3)
                end = n if end == -1 else end + 3
                val = text[i:end]
                tokens.append(Token("COMMENT", val, i, end, line, col))
                line += val.count("\n")
                col = len(val) - val.rfind("\n") if "\n" in val else col + len(val)
                i = end
                continue
            elif i + 1 < n and text[i:i+2] == "#*":
                end = text.find("*#", i + 2)
                end = n if end == -1 else end + 2
                val = text[i:end]
                tokens.append(Token("COMMENT", val, i, end, line, col))
                line += val.count("\n")
                col = len(val) - val.rfind("\n") if "\n" in val else col + len(val)
                i = end
                continue
            elif i + 1 < n and text[i:i+2] == "##":
                end = text.find("##", i + 2)
                end = n if end == -1 else end + 2
                val = text[i:end]
                tokens.append(Token("COMMENT", val, i, end, line, col))
                line += val.count("\n")
                col = len(val) - val.rfind("\n") if "\n" in val else col + len(val)
                i = end
                continue
            else:
                end = text.find("\n", i)
                if end == -1:
                    end = n
                tokens.append(Token("COMMENT", text[i:end], i, end, line, col))
                col += end - i
                i = end
                continue

        # Whitespace
        if ch.isspace():
            while i < n and text[i].isspace():
                if text[i] == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
                i += 1
            tokens.append(Token("WS", text[start:i], start, i, start_line, start_col))
            continue

        # Double-quoted strings
        if ch == '"':
            i += 1
            col += 1
            while i < n and text[i] != '"':
                if text[i] == "\\":
                    i += 1
                    col += 1
                if i < n and text[i] == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
                i += 1
            if i < n:
                i += 1
                col += 1
            tokens.append(Token("STRING", text[start:i], start, i, start_line, start_col))
            continue

        # Single-quoted chars / strings
        if ch == "'":
            i += 1
            col += 1
            while i < n and text[i] != "'":
                if text[i] == "\\":
                    i += 1
                    col += 1
                if i < n and text[i] == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
                i += 1
            if i < n:
                i += 1
                col += 1
            tokens.append(Token("CHAR", text[start:i], start, i, start_line, start_col))
            continue

        # Identifiers
        if ch.isalpha() or ch == "_":
            while i < n and (text[i].isalnum() or text[i] == "_"):
                i += 1
                col += 1
            tokens.append(Token("IDENT", text[start:i], start, i, start_line, start_col))
            continue

        # Numbers
        if ch.isdigit():
            if ch == "0" and i + 1 < n and text[i+1] in "xX":
                i += 2
                col += 2
                while i < n and text[i].isalnum():
                    i += 1
                    col += 1
                tokens.append(Token("INT", text[start:i], start, i, start_line, start_col))
                continue
            is_float = False
            while i < n and (text[i].isdigit() or (text[i] == "." and i + 1 < n and text[i+1].isdigit())):
                if text[i] == ".":
                    is_float = True
                i += 1
                col += 1
            tokens.append(Token("FLOAT" if is_float else "INT", text[start:i], start, i, start_line, start_col))
            continue

        # Multi-char symbols
        four = text[i:i+4]
        if four == "?=/=":
            tokens.append(Token("SYMBOL", four, i, i+4, line, col))
            i += 4; col += 4; continue
        three = text[i:i+3]
        if three in ("><=", "->>"):
            tokens.append(Token("SYMBOL", three, i, i+3, line, col))
            i += 3; col += 3; continue
        two = text[i:i+2]
        if two in ("<-", "><", "<=", ">=", "==", "!=", "?=", "**", "->", "::", "||", "&&"):
            tokens.append(Token("SYMBOL", two, i, i+2, line, col))
            i += 2; col += 2; continue

        tokens.append(Token("SYMBOL", ch, i, i+1, line, col))
        i += 1
        col += 1

    return tokens

@dataclass
class GenericMatch:
    category: str
    base_tok: Token
    lt_tok: Token
    gt_tok: Token
    args_text: str

def find_generics_in_tokens(
    tokens: List[Token], text: str
) -> Tuple[List[GenericMatch], List[Dict[str, Any]], List[Dict[str, Any]]]:
    sig = [t for t in tokens if t.kind not in ("WS", "COMMENT")]
    matches: List[GenericMatch] = []
    retained_hits: List[Dict[str, Any]] = []
    manual_review: List[Dict[str, Any]] = []

    for idx, tok in enumerate(sig):
        if tok.kind == "SYMBOL" and tok.value == "<":
            if idx == 0 or sig[idx-1].kind != "IDENT":
                retained_hits.append({
                    "line": tok.line,
                    "col": tok.col,
                    "text": tok.value,
                    "reason": "comparison or non-identifier opener",
                })
                continue

            base_tok = sig[idx-1]
            base_name = base_tok.value
            depth = 1
            paren_depth = 0
            bracket_depth = 0
            close_idx = -1
            aborted = False

            for j in range(idx + 1, len(sig)):
                t = sig[j]
                if t.kind == "SYMBOL":
                    if t.value == "<":
                        if paren_depth == 0 and bracket_depth == 0:
                            depth += 1
                    elif t.value == ">":
                        if paren_depth == 0 and bracket_depth == 0:
                            depth -= 1
                            if depth == 0:
                                close_idx = j
                                break
                    elif t.value == "(":
                        paren_depth += 1
                    elif t.value == ")":
                        paren_depth -= 1
                        if paren_depth < 0:
                            aborted = True
                            break
                    elif t.value == "[":
                        bracket_depth += 1
                    elif t.value == "]":
                        bracket_depth -= 1
                        if bracket_depth < 0:
                            aborted = True
                            break
                    elif paren_depth == 0 and bracket_depth == 0 and t.value in FORBIDDEN_SYMBOLS:
                        aborted = True
                        break
                    elif paren_depth == 0 and bracket_depth == 0 and t.value in ("&", "|"):
                        if t.value == "&" and j + 1 < len(sig) and (sig[j+1].value == "mut" or sig[j+1].kind == "IDENT"):
                            pass
                        else:
                            aborted = True
                            break
                elif t.kind == "IDENT":
                    if paren_depth == 0 and bracket_depth == 0 and t.value in FORBIDDEN_KEYWORDS:
                        if t.value == "func" and j + 1 < len(sig) and sig[j+1].value == "(":
                            pass
                        else:
                            aborted = True
                            break
                elif t.kind in ("INT", "FLOAT"):
                    if paren_depth == 0 and bracket_depth == 0 and base_name != "flux":
                        aborted = True
                        break

            if aborted or close_idx == -1:
                retained_hits.append({
                    "line": tok.line,
                    "col": tok.col,
                    "text": text[base_tok.start:sig[close_idx].end] if close_idx != -1 else tok.value,
                    "reason": "comparison or operator expression",
                })
                continue

            next_tok = sig[close_idx + 1] if close_idx + 1 < len(sig) else None
            prev2_tok = sig[idx - 2] if idx >= 2 else None
            prev3_tok = sig[idx - 3] if idx >= 3 else None

            # Expression comparison chaining on same line (e.g. `a < b > c` or `a < b > 0`)
            if next_tok and next_tok.kind in ("IDENT", "INT", "FLOAT") and next_tok.line == sig[close_idx].line:
                retained_hits.append({
                    "line": tok.line,
                    "col": tok.col,
                    "text": text[base_tok.start:next_tok.end],
                    "reason": "comparison or operator expression",
                })
                continue

            cat: Optional[str] = None
            if prev2_tok and prev2_tok.value in ("entity", "enum", "func", "method", "mold"):
                cat = "declaration"
            elif prev3_tok and prev3_tok.value in ("packed", "async") and prev2_tok and prev2_tok.value in ("entity", "func"):
                cat = "declaration"
            elif base_name == "tensor" and next_tok and next_tok.value == "[":
                cat = "tensor"
            elif base_name == "flux":
                cat = "flux"
            elif base_name in ("Vec", "dict"):
                cat = "dict/Vec"
            elif next_tok and next_tok.value == "(":
                if base_name[0].isupper():
                    cat = "constructor"
                else:
                    cat = "explicit generic call"
            elif (prev2_tok and prev2_tok.value in (":", "->", "as", "[")) or base_name in ("Map", "map", "Option", "Result", "Pair", "Box"):
                cat = "type application"
            elif next_tok and next_tok.value in (",", ")", "]", "=", ":", "do", "end", "end.", ";", ">"):
                cat = "type application"
            else:
                manual_review.append({
                    "line": base_tok.line,
                    "col": base_tok.col,
                    "base": base_name,
                    "snippet": text[base_tok.start:sig[close_idx].end],
                    "reason": "uncertain syntactic context",
                })
                continue

            args_text = text[tok.end : sig[close_idx].start]
            matches.append(
                GenericMatch(
                    category=cat,
                    base_tok=base_tok,
                    lt_tok=tok,
                    gt_tok=sig[close_idx],
                    args_text=args_text,
                )
            )

    return matches, retained_hits, manual_review

def rewrite_file_content(
    text: str
) -> Tuple[str, List[GenericMatch], List[Dict[str, Any]], List[Dict[str, Any]], Counter]:
    tokens = tokenize(text)
    matches, retained_hits, manual_review = find_generics_in_tokens(tokens, text)
    counts = Counter()

    if not matches:
        return text, matches, retained_hits, manual_review, counts

    for m in matches:
        counts[m.category] += 1

    # Identify top-level matches
    top_level: List[GenericMatch] = []
    for m in matches:
        is_inner = False
        for other in matches:
            if other is not m:
                if other.base_tok.start <= m.base_tok.start and m.gt_tok.end <= other.gt_tok.end:
                    is_inner = True
                    break
        if not is_inner:
            top_level.append(m)

    top_level.sort(key=lambda m: m.base_tok.start, reverse=True)

    def format_match(m: GenericMatch, current_text: str) -> str:
        children = [
            c for c in matches
            if c is not m and m.lt_tok.start <= c.base_tok.start and c.gt_tok.end <= m.gt_tok.end
        ]
        immediate_children = []
        for c in children:
            is_grandchild = False
            for other_c in children:
                if other_c is not c and other_c.base_tok.start <= c.base_tok.start and c.gt_tok.end <= other_c.gt_tok.end:
                    is_grandchild = True
                    break
            if not is_grandchild:
                immediate_children.append(c)

        immediate_children.sort(key=lambda c: c.base_tok.start, reverse=True)

        args_start = m.lt_tok.end
        args_end = m.gt_tok.start
        args_str = current_text[args_start:args_end]

        for c in immediate_children:
            child_formatted = format_match(c, current_text)
            rel_start = c.base_tok.start - args_start
            rel_end = c.gt_tok.end - args_start
            args_str = args_str[:rel_start] + child_formatted + args_str[rel_end:]

        formatted_args = args_str.strip()
        return f"{m.base_tok.value} of ({formatted_args})"

    cur = text
    for m in top_level:
        replacement = format_match(m, cur)
        cur = cur[:m.base_tok.start] + replacement + cur[m.gt_tok.end:]

    return cur, matches, retained_hits, manual_review, counts

def scan_repository(
    repo_root: Path,
    roots: List[str],
    excludes: List[str]
) -> List[Path]:
    target_files: List[Path] = []
    for r in roots:
        root_path = (repo_root / r).resolve()
        if not root_path.exists():
            continue
        if root_path.is_file():
            if root_path.suffix == ".vri":
                target_files.append(root_path)
            continue
        for dirpath, dirnames, filenames in os.walk(root_path):
            dir_rel = os.path.relpath(dirpath, repo_root)
            # Check exclusions
            skip_dir = False
            for excl in excludes:
                if dir_rel == excl or dir_rel.startswith(excl + os.sep) or excl in dir_rel.split(os.sep):
                    skip_dir = True
                    break
            if skip_dir:
                dirnames.clear()
                continue

            for fn in filenames:
                if not fn.endswith(".vri"):
                    continue
                if fn.startswith("legacy_generic_") and fn.endswith("_negative.vri"):
                    continue
                file_path = Path(dirpath) / fn
                rel_file = str(file_path.relative_to(repo_root))
                if rel_file in excludes:
                    continue
                target_files.append(file_path)

    return sorted(set(target_files))

def run_dry_run(
    repo_root: Path,
    target_files: List[Path],
    verbose: bool = False
) -> int:
    total_files = len(target_files)
    modified_files = []
    total_counts = Counter()
    total_retained = 0
    all_manual: List[Tuple[Path, Dict[str, Any]]] = []
    diffs: List[str] = []

    for file_path in target_files:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        new_content, matches, retained, manual, counts = rewrite_file_content(content)
        total_retained += len(retained)
        if manual:
            for item in manual:
                all_manual.append((file_path, item))
        if new_content != content:
            modified_files.append(file_path)
            total_counts.update(counts)
            if verbose or len(diffs) < 10:
                rel = str(file_path.relative_to(repo_root))
                diff = "".join(
                    difflib.unified_diff(
                        content.splitlines(keepends=True),
                        new_content.splitlines(keepends=True),
                        fromfile=f"a/{rel}",
                        tofile=f"b/{rel}",
                        n=2,
                    )
                )
                diffs.append(diff)

    print("════════════════════════════════════════════════════════════════")
    print("  Vir Generic of (...) Syntax Migration — Dry-Run Preview")
    print("════════════════════════════════════════════════════════════════")
    print(f"Total files scanned:    {total_files}")
    print(f"Files to be modified:   {len(modified_files)}")
    print(f"Retained hits (<...>):  {total_retained}")
    print(f"Manual review required: {len(all_manual)}")
    print("\nReplacements by category:")
    for cat in CATEGORIES:
        print(f"  - {cat:22s}: {total_counts[cat]:5d}")

    if all_manual:
        print("\n[WARNING] Uncertain hits requiring manual review:")
        for fp, item in all_manual[:10]:
            rel = fp.relative_to(repo_root)
            print(f"  {rel}:{item['line']} [{item['base']}] -> {item['snippet']!r} ({item['reason']})")
        if len(all_manual) > 10:
            print(f"  ... and {len(all_manual) - 10} more.")

    if diffs:
        print("\nUnified Diff Sample (first 10 files):")
        print("────────────────────────────────────────────────────────────────")
        for d in diffs[:10]:
            print(d)

    return 0 if not all_manual else 1

def run_apply(
    repo_root: Path,
    target_files: List[Path],
    backup_dir: Path
) -> int:
    migration_id = f"migration_{time.strftime('%Y%m%d_%H%M%S')}"
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    backup_dir = backup_dir.resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)

    tool_path = Path(__file__).resolve()
    tool_hash = sha256_file(tool_path)

    # 1. Read all files and prepare modifications
    file_records: Dict[str, Dict[str, Any]] = {}
    modified_contents: Dict[Path, str] = {}
    total_counts = Counter()
    all_retained: List[Dict[str, Any]] = []
    all_manual: List[Dict[str, Any]] = []

    for file_path in target_files:
        rel_str = str(file_path.relative_to(repo_root))
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        pre_sha = sha256_content(content)

        new_content, matches, retained, manual, counts = rewrite_file_content(content)
        for r in retained:
            r["file"] = rel_str
            all_retained.append(r)
        for m in manual:
            m["file"] = rel_str
            all_manual.append(m)

        if new_content != content:
            post_sha = sha256_content(new_content)
            backup_file = backup_dir / rel_str
            file_records[rel_str] = {
                "pre_sha256": pre_sha,
                "post_sha256": post_sha,
                "backup_path": str(backup_file),
            }
            modified_contents[file_path] = new_content
            total_counts.update(counts)

    if all_manual:
        print(f"[ERROR] Migration aborted: {len(all_manual)} uncertain hits require manual review.")
        for item in all_manual[:10]:
            print(f"  {item['file']}:{item['line']} [{item['base']}] -> {item['snippet']!r}")
        return 1

    # 2. Create backups for all modified files
    for file_path in modified_contents:
        rel_str = str(file_path.relative_to(repo_root))
        backup_file = backup_dir / rel_str
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, backup_file)

    manifest_data = {
        "migration_id": migration_id,
        "timestamp": timestamp,
        "repo_root": str(repo_root),
        "tool_hash": tool_hash,
        "files_scanned": len(target_files),
        "files_modified": [str(fp.relative_to(repo_root)) for fp in modified_contents],
        "files_skipped": [str(fp.relative_to(repo_root)) for fp in target_files if fp not in modified_contents],
        "manual_review": all_manual,
        "replacement_counts": {cat: total_counts[cat] for cat in CATEGORIES},
        "retained_hits_count": len(all_retained),
        "file_records": file_records,
        "status": "in_progress",
    }
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    # 3. Apply atomic replacements
    applied_files: List[Path] = []
    try:
        for file_path, new_code in modified_contents.items():
            # Verify pre-SHA256 matches current file on disk
            rel_str = str(file_path.relative_to(repo_root))
            if sha256_file(file_path) != file_records[rel_str]["pre_sha256"]:
                raise IOError(f"Pre-image SHA-256 mismatch for {rel_str}; file changed during migration!")

            # Write atomically using temp file in same directory
            temp_fd, temp_name = tempfile.mkstemp(dir=file_path.parent, prefix=".mig_", suffix=".tmp")
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                f.write(new_code)
            orig_mode = os.stat(file_path).st_mode
            os.chmod(temp_name, orig_mode)
            os.replace(temp_name, file_path)
            applied_files.append(file_path)

        manifest_data["status"] = "completed"
        manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

        print("════════════════════════════════════════════════════════════════")
        print("  Vir Generic of (...) Syntax Migration — Completed Successfully")
        print("════════════════════════════════════════════════════════════════")
        print(f"Migration ID:      {migration_id}")
        print(f"Manifest path:     {manifest_path}")
        print(f"Backup directory:  {backup_dir}")
        print(f"Files modified:    {len(applied_files)}")
        print("\nReplacement summary:")
        for cat in CATEGORIES:
            print(f"  - {cat:22s}: {total_counts[cat]:5d}")
        return 0

    except Exception as exc:
        print(f"[CRITICAL ERROR] Migration apply failed: {exc}")
        print("Rolling back applied files...")
        for file_path in applied_files:
            rel_str = str(file_path.relative_to(repo_root))
            backup_file = Path(file_records[rel_str]["backup_path"])
            if backup_file.exists():
                shutil.copy2(backup_file, file_path)
        manifest_data["status"] = "aborted"
        manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
        return 1

def run_rollback(
    manifest_path: Path
) -> int:
    manifest_path = manifest_path.resolve()
    if not manifest_path.exists():
        print(f"[ERROR] Manifest file not found: {manifest_path}")
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    repo_root = Path(manifest["repo_root"]).resolve()
    migration_id = manifest["migration_id"]
    file_records: Dict[str, Dict[str, Any]] = manifest.get("file_records", {})

    print(f"Initiating rollback for {migration_id} on {repo_root}...")
    conflicts = []
    restored = []

    # 1. Pre-check: verify all files match post_sha256
    for rel_str, record in file_records.items():
        file_path = repo_root / rel_str
        if not file_path.exists():
            conflicts.append((rel_str, "file does not exist on disk"))
            continue
        current_sha = sha256_file(file_path)
        if current_sha != record["post_sha256"]:
            conflicts.append((rel_str, f"SHA mismatch: current={current_sha} != post={record['post_sha256']}"))

    if conflicts:
        print(f"[ERROR] Rollback aborted due to {len(conflicts)} conflict(s):")
        for rel_str, reason in conflicts:
            print(f"  - {rel_str}: {reason}")
        return 1

    # 2. Restore files from backup
    for rel_str, record in file_records.items():
        file_path = repo_root / rel_str
        backup_file = Path(record["backup_path"])
        if not backup_file.exists():
            print(f"[ERROR] Backup missing for {rel_str} at {backup_file}")
            return 1
        shutil.copy2(backup_file, file_path)
        restored_sha = sha256_file(file_path)
        if restored_sha != record["pre_sha256"]:
            print(f"[ERROR] Restored SHA mismatch for {rel_str}!")
            return 1
        restored.append(rel_str)

    print(f"Rollback completed successfully: {len(restored)} files restored to pre-migration state.")
    return 0

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate Vir generic syntax from `<T>` to `of (T)` with rollback and verification."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=False, help="Preview migration without modifying files.")
    group.add_argument("--apply", action="store_true", default=False, help="Atomically apply migration.")
    group.add_argument("--rollback", type=str, metavar="MANIFEST_PATH", help="Roll back migration using manifest.")

    parser.add_argument("--backup-dir", type=str, default="./scratch/migration_backup", help="Directory for backup and manifest.")
    parser.add_argument("--roots", nargs="*", default=DEFAULT_ROOTS, help="Target roots to scan.")
    parser.add_argument("--exclude", nargs="*", default=DEFAULT_EXCLUDES, help="Directory/file patterns to exclude.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose diffs and progress.")

    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]

    if args.rollback:
        return run_rollback(Path(args.rollback))

    target_files = scan_repository(repo_root, args.roots, args.exclude)

    if args.apply:
        return run_apply(repo_root, target_files, Path(args.backup_dir))

    # Default is dry-run
    return run_dry_run(repo_root, target_files, verbose=args.verbose)

if __name__ == "__main__":
    sys.exit(main())

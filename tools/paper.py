#!/usr/bin/env python3
"""Dependency-free command line tooling for VIR Paper Standard v1."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Iterable


DOMAINS = ("VIR", "VIRC", "VLSP", "STLB", "IVIR", "VIRON")
TYPE_INFO = {
    "ISSUE": ("ISS", "issues", "ISSUE.md"),
    "PLAN": ("PLN", "plans", "PLAN.md"),
    "REPORT": ("RPT", "reports", "REPORT.md"),
    "SPEC": ("SPC", "specs", "SPEC.md"),
}
CODE_TO_TYPE = {info[0]: kind for kind, info in TYPE_INFO.items()}
STATUSES = {
    "ISSUE": {
        "DRAFT", "OPEN", "TRIAGED", "PLANNED", "IMPLEMENTING",
        "VERIFYING", "RESOLVED", "CLOSED", "REOPENED", "REJECTED",
    },
    "PLAN": {
        "DRAFT", "REVIEW", "APPROVED", "ACTIVE", "COMPLETED",
        "SUPERSEDED", "CANCELLED",
    },
    "REPORT": {"DRAFT", "REVIEW", "ACCEPTED", "REJECTED", "SUPERSEDED"},
    "SPEC": {"DRAFT", "REVIEW", "ACTIVE", "SUPERSEDED", "RETIRED"},
}
SEVERITIES = {"S0", "S1", "S2", "S3", "S4"}
PRIORITIES = {"P0", "P1", "P2", "P3"}
CONCLUSIONS = {
    "READY_FOR_CLOSE",
    "PARTIALLY_RESOLVED",
    "REQUIRES_FOLLOWUP",
    "FAILED_VERIFICATION",
}
STANDARD_VERSION = "1.1.0"
ID_RE = re.compile(r"^(VIR|VIRC|VLSP|STLB|IVIR|VIRON)-(ISS|PLN|RPT|SPC)-([0-9]{4})$")
FILENAME_RE = re.compile(
    r"^(VIR|VIRC|VLSP|STLB|IVIR|VIRON)-(ISS|PLN|RPT|SPC)-([0-9]{4})_[a-z0-9]+(?:_[a-z0-9]+)*\.md$"
)
COMMON_FIELDS = {
    "id", "type", "domain", "title", "status", "created", "updated",
    "owners", "components", "related", "supersedes", "superseded_by", "tags",
}
REGISTRY_FIELDS = {"id", "type", "domain", "title", "status", "path"}
REQUIRED_SECTIONS = {
    "ISSUE": [
        "Summary", "Context", "Expected Behavior", "Actual Behavior",
        "Reproduction", "Evidence", "Scope", "Impact", "Preliminary Analysis",
        "Acceptance Criteria", "Related Papers", "Revision History",
    ],
    "PLAN": [
        "Objective", "Source Issues", "Scope", "Current Architecture",
        "Proposed Architecture", "Design Decisions", "Implementation Plan",
        "Compatibility", "Migration", "Validation Plan", "Risks",
        "Rollback Strategy", "Exit Criteria", "Related Papers", "Revision History",
    ],
    "REPORT": [
        "Executive Summary", "Source Issues", "Source Plans",
        "Implementation Summary", "Changes by Component", "Deviations from Plan",
        "Verification", "Acceptance Criteria", "Known Limitations",
        "Remaining Work", "Conclusion", "Related Papers", "Revision History",
    ],
    "SPEC": ["Revision History"],
}

SPEC_FIELDS = {"version", "language", "spec_class", "aliases"}
SPEC_CLASSES = {"ARCHITECTURE", "ALGORITHM", "SPECIFICATION", "CONTRACT", "REFERENCE"}
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


class PaperError(Exception):
    pass


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"null", "~"}:
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        if value[0] == '"':
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise PaperError(f"invalid quoted YAML scalar {value!r}: {exc}") from exc
        return value[1:-1].replace("''", "'")
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(item) for item in inner.split(",")]
    if re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    return value


def parse_yaml(text: str, source: str) -> Any:
    """Parse the small, deterministic YAML subset emitted by this tool."""
    lines: list[tuple[int, str, int]] = []
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise PaperError(f"{source}:{number}: tabs are not allowed in indentation")
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw[indent:].rstrip(), number))

    if not lines:
        return {}

    def block(index: int, indent: int) -> tuple[Any, int]:
        if lines[index][0] != indent:
            raise PaperError(f"{source}:{lines[index][2]}: inconsistent indentation")
        if lines[index][1] == "-" or lines[index][1].startswith("- "):
            result: list[Any] = []
            while index < len(lines):
                current_indent, content, number = lines[index]
                if current_indent < indent:
                    break
                if current_indent != indent or not (content == "-" or content.startswith("- ")):
                    raise PaperError(f"{source}:{number}: malformed list item")
                rest = content[1:].strip()
                index += 1
                if not rest:
                    if index >= len(lines) or lines[index][0] <= indent:
                        raise PaperError(f"{source}:{number}: empty list item")
                    item, index = block(index, lines[index][0])
                    result.append(item)
                elif ":" in rest:
                    key, raw_value = rest.split(":", 1)
                    item = {key.strip(): parse_scalar(raw_value)}
                    if index < len(lines) and lines[index][0] > indent:
                        continuation, index = block(index, lines[index][0])
                        if not isinstance(continuation, dict):
                            raise PaperError(f"{source}:{number}: list mapping expected")
                        item.update(continuation)
                    result.append(item)
                else:
                    result.append(parse_scalar(rest))
            return result, index

        result_map: dict[str, Any] = {}
        while index < len(lines):
            current_indent, content, number = lines[index]
            if current_indent < indent:
                break
            if current_indent != indent:
                raise PaperError(f"{source}:{number}: inconsistent indentation")
            if content == "-" or content.startswith("- "):
                break
            if ":" not in content:
                raise PaperError(f"{source}:{number}: expected key: value")
            key, raw_value = content.split(":", 1)
            key = key.strip()
            if not key or key in result_map:
                raise PaperError(f"{source}:{number}: invalid or duplicate key {key!r}")
            index += 1
            if raw_value.strip():
                result_map[key] = parse_scalar(raw_value)
            elif index < len(lines) and lines[index][0] > indent:
                result_map[key], index = block(index, lines[index][0])
            else:
                result_map[key] = {}
        return result_map, index

    value, final = block(0, lines[0][0])
    if final != len(lines):
        raise PaperError(f"{source}:{lines[final][2]}: trailing YAML content")
    return value


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise PaperError(f"cannot serialize YAML scalar {value!r}")


def dump_yaml(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    lines: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, dict):
                if item:
                    lines.append(f"{prefix}{key}:")
                    lines.append(dump_yaml(item, indent + 2))
                else:
                    lines.append(f"{prefix}{key}: {{}}")
            elif isinstance(item, list):
                if item:
                    lines.append(f"{prefix}{key}:")
                    lines.append(dump_yaml(item, indent + 2))
                else:
                    lines.append(f"{prefix}{key}: []")
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(item)}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(dump_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {yaml_scalar(item)}")
    else:
        lines.append(f"{prefix}{yaml_scalar(value)}")
    return "\n".join(lines)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def parse_paper(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n?", text, re.DOTALL)
    if not match:
        raise PaperError(f"{path}: missing YAML front matter")
    metadata = parse_yaml(match.group(1), str(path))
    if not isinstance(metadata, dict):
        raise PaperError(f"{path}: front matter must be a mapping")
    return metadata, text[match.end():]


def write_paper(path: Path, metadata: dict[str, Any], body: str) -> None:
    atomic_write(path, f"---\n{dump_yaml(metadata)}\n---\n\n{body.lstrip()}")


def load_registry(base: Path) -> dict[str, Any]:
    path = base / "REGISTRY.yaml"
    if not path.is_file():
        raise PaperError(f"missing registry: {path}")
    data = parse_yaml(path.read_text(encoding="utf-8"), str(path))
    if not isinstance(data, dict):
        raise PaperError(f"{path}: registry must be a mapping")
    return data


def today() -> str:
    return os.environ.get("PAPER_TODAY", dt.date.today().isoformat())


def validate_date(value: Any) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return False
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def relative_paper_path(base: Path, path: Path) -> str:
    return path.relative_to(base).as_posix()


def discover_papers(base: Path) -> list[Path]:
    paths: list[Path] = []
    for domain in DOMAINS:
        for _, directory, _ in TYPE_INFO.values():
            folder = base / domain / directory
            if folder.is_dir():
                paths.extend(sorted(folder.glob("*.md")))
    return sorted(paths)


def registry_from_files(base: Path) -> dict[str, Any]:
    entries = []
    seen: set[str] = set()
    for path in discover_papers(base):
        metadata, _ = parse_paper(path)
        paper_id = metadata.get("id")
        if not isinstance(paper_id, str):
            raise PaperError(f"{path}: cannot index paper without string id")
        if paper_id in seen:
            raise PaperError(f"duplicate paper ID while indexing: {paper_id}")
        seen.add(paper_id)
        entries.append({
            "id": paper_id,
            "type": metadata.get("type"),
            "domain": metadata.get("domain"),
            "title": metadata.get("title"),
            "status": metadata.get("status"),
            "path": relative_paper_path(base, path),
        })
    entries.sort(key=lambda item: item["id"])
    return {"version": 1, "standard_version": STANDARD_VERSION, "papers": entries}


def registry_entries(base: Path) -> list[dict[str, Any]]:
    registry = load_registry(base)
    entries = registry.get("papers")
    if not isinstance(entries, list):
        raise PaperError(f"{base / 'REGISTRY.yaml'}: papers must be a list")
    if not all(isinstance(entry, dict) for entry in entries):
        raise PaperError(f"{base / 'REGISTRY.yaml'}: every paper entry must be a mapping")
    return entries


def write_registry(base: Path) -> None:
    registry = registry_from_files(base)
    atomic_write(base / "REGISTRY.yaml", dump_yaml(registry) + "\n")


def validate_metadata(
    metadata: dict[str, Any], path: Path, base: Path, production: bool,
) -> list[str]:
    errors: list[str] = []
    label = relative_paper_path(base, path)
    paper_type = metadata.get("type")
    allowed = set(COMMON_FIELDS)
    required = set(COMMON_FIELDS)
    if paper_type == "ISSUE":
        allowed |= {"severity", "priority"}
    elif paper_type == "SPEC":
        allowed |= SPEC_FIELDS
        required |= SPEC_FIELDS
    missing = sorted(required - metadata.keys())
    extra = sorted(metadata.keys() - allowed)
    if missing:
        errors.append(f"{label}: missing metadata fields: {', '.join(missing)}")
    if extra:
        errors.append(f"{label}: unknown metadata fields: {', '.join(extra)}")

    paper_id = metadata.get("id")
    match = ID_RE.fullmatch(paper_id) if isinstance(paper_id, str) else None
    if not match:
        errors.append(f"{label}: invalid paper id {paper_id!r}")
    else:
        id_domain, code, sequence = match.groups()
        if production and sequence == "0000":
            errors.append(f"{label}: production ID must not use reserved sequence 0000")
        if not production and sequence != "0000":
            errors.append(f"{label}: example ID must use reserved sequence 0000")
        if metadata.get("domain") != id_domain:
            errors.append(f"{label}: domain does not match ID")
        if metadata.get("type") != CODE_TO_TYPE[code]:
            errors.append(f"{label}: type does not match ID")

    if paper_type not in TYPE_INFO:
        errors.append(f"{label}: invalid type {paper_type!r}")
    elif metadata.get("status") not in STATUSES[paper_type]:
        errors.append(f"{label}: invalid {paper_type} status {metadata.get('status')!r}")

    if not isinstance(metadata.get("title"), str) or not metadata.get("title", "").strip():
        errors.append(f"{label}: title must be a non-empty string")
    if not validate_date(metadata.get("created")):
        errors.append(f"{label}: created must be an ISO date")
    if not validate_date(metadata.get("updated")):
        errors.append(f"{label}: updated must be an ISO date")
    if validate_date(metadata.get("created")) and validate_date(metadata.get("updated")):
        if metadata["updated"] < metadata["created"]:
            errors.append(f"{label}: updated precedes created")

    for field in ("owners", "components", "tags"):
        value = metadata.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            errors.append(f"{label}: {field} must be a list of non-empty strings")
        elif len(value) != len(set(value)):
            errors.append(f"{label}: {field} contains duplicates")

    related = metadata.get("related")
    if not isinstance(related, dict) or set(related) != {"issues", "plans", "reports"}:
        errors.append(f"{label}: related must contain exactly issues, plans, and reports")
    else:
        for bucket, values in related.items():
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                errors.append(f"{label}: related.{bucket} must be a list of IDs")
            elif len(values) != len(set(values)):
                errors.append(f"{label}: related.{bucket} contains duplicates")
            elif paper_id in values:
                errors.append(f"{label}: self-link in related.{bucket}")

    for field in ("supersedes", "superseded_by"):
        value = metadata.get(field)
        if value is not None and (not isinstance(value, str) or not ID_RE.fullmatch(value)):
            errors.append(f"{label}: {field} must be null or a paper ID")
        if value == paper_id:
            errors.append(f"{label}: {field} must not reference itself")

    if paper_type == "ISSUE":
        if metadata.get("severity") not in SEVERITIES:
            errors.append(f"{label}: invalid or missing severity")
        if metadata.get("priority") not in PRIORITIES:
            errors.append(f"{label}: invalid or missing priority")
    elif "severity" in metadata or "priority" in metadata:
        errors.append(f"{label}: severity and priority are ISSUE-only fields")

    if paper_type == "SPEC":
        if not isinstance(metadata.get("version"), str) or not SEMVER_RE.fullmatch(metadata["version"]):
            errors.append(f"{label}: version must be semantic version text")
        if not isinstance(metadata.get("language"), str) or not metadata["language"]:
            errors.append(f"{label}: language must be a non-empty string")
        if metadata.get("spec_class") not in SPEC_CLASSES:
            errors.append(f"{label}: invalid or missing spec_class")
        aliases = metadata.get("aliases")
        if not isinstance(aliases, list) or not all(isinstance(item, str) and item for item in aliases):
            errors.append(f"{label}: aliases must be a list of non-empty strings")
        elif len(aliases) != len(set(aliases)):
            errors.append(f"{label}: aliases contains duplicates")

    if match and paper_type in TYPE_INFO:
        _, expected_directory, _ = TYPE_INFO[paper_type]
        expected_parent = base / match.group(1) / expected_directory
        if path.parent != expected_parent:
            errors.append(f"{label}: file is not in its domain/type directory")
        if not FILENAME_RE.fullmatch(path.name) or not path.name.startswith(f"{paper_id}_"):
            errors.append(f"{label}: filename must be <ID>_<lowercase_slug>.md")
    return errors


def validate_body(metadata: dict[str, Any], body: str, path: Path, base: Path) -> list[str]:
    errors: list[str] = []
    label = relative_paper_path(base, path)
    paper_id = metadata.get("id")
    title = metadata.get("title")
    if isinstance(paper_id, str) and isinstance(title, str):
        expected = f"# {paper_id} — {title}"
        if expected not in body.splitlines():
            errors.append(f"{label}: missing exact title heading {expected!r}")
    paper_type = metadata.get("type")
    for section in REQUIRED_SECTIONS.get(paper_type, []):
        if not re.search(rf"^## [0-9]+\. {re.escape(section)}\s*$", body, re.MULTILINE):
            errors.append(f"{label}: missing required section {section!r}")
    if paper_type == "REPORT":
        found = sorted(token for token in CONCLUSIONS if re.search(rf"\b{token}\b", body))
        if len(found) != 1:
            errors.append(f"{label}: REPORT must state exactly one conclusion, found {found}")
    return errors


def validate_templates(root: Path) -> list[str]:
    errors: list[str] = []
    for paper_type, (_, _, template_name) in TYPE_INFO.items():
        path = root / "papers" / "templates" / template_name
        if not path.is_file():
            errors.append(f"missing template: {path.relative_to(root)}")
            continue
        try:
            metadata, body = parse_paper(path)
        except (OSError, PaperError) as exc:
            errors.append(str(exc))
            continue
        required_placeholders = {"<ID>", "<TITLE>"}
        text = path.read_text(encoding="utf-8")
        for placeholder in required_placeholders:
            if placeholder not in text:
                errors.append(f"{path.relative_to(root)}: missing placeholder {placeholder}")
        if metadata.get("type") != paper_type:
            errors.append(f"{path.relative_to(root)}: template type mismatch")
        for section in REQUIRED_SECTIONS[paper_type]:
            if not re.search(rf"^## [0-9]+\. {re.escape(section)}\s*$", body, re.MULTILINE):
                errors.append(f"{path.relative_to(root)}: missing section {section!r}")
    return errors


def validate_schema_files(root: Path) -> list[str]:
    errors: list[str] = []
    schema_dir = root / "papers" / "schemas"
    expected = {"paper.schema.json", "issue.schema.json", "plan.schema.json", "report.schema.json", "spec.schema.json"}
    schemas: dict[Path, dict[str, Any]] = {}
    for name in sorted(expected):
        path = schema_dir / name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            errors.append(f"missing schema: {path.relative_to(root)}")
            continue
        except json.JSONDecodeError as exc:
            errors.append(f"{path.relative_to(root)}: invalid JSON: {exc}")
            continue
        if data.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{path.relative_to(root)}: must declare JSON Schema 2020-12")
        if not isinstance(data, dict):
            errors.append(f"{path.relative_to(root)}: schema root must be an object")
        else:
            schemas[path.resolve()] = data

    schema_ids: dict[str, Path] = {}
    for path, schema in schemas.items():
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str) or not schema_id:
            errors.append(f"{path.relative_to(root)}: schema must have a non-empty $id")
        elif schema_id in schema_ids:
            errors.append(f"{path.relative_to(root)}: duplicate schema $id {schema_id}")
        else:
            schema_ids[schema_id] = path

    def references(value: Any) -> Iterable[str]:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "$ref" and isinstance(item, str):
                    yield item
                else:
                    yield from references(item)
        elif isinstance(value, list):
            for item in value:
                yield from references(item)

    for source, schema in schemas.items():
        for reference in references(schema):
            target_name, separator, fragment = reference.partition("#")
            target = source if not target_name else (schema_dir / target_name).resolve()
            target_schema = schemas.get(target)
            if target_schema is None:
                errors.append(f"{source.relative_to(root)}: unresolved schema reference {reference}")
                continue
            if not separator or not fragment:
                continue
            if not fragment.startswith("/"):
                errors.append(f"{source.relative_to(root)}: unsupported schema fragment {reference}")
                continue
            resolved: Any = target_schema
            try:
                for token in fragment[1:].split("/"):
                    token = token.replace("~1", "/").replace("~0", "~")
                    resolved = resolved[token]
            except (KeyError, TypeError):
                errors.append(f"{source.relative_to(root)}: unresolved schema fragment {reference}")
    return errors


def validate_scope(base: Path, production: bool) -> list[str]:
    errors: list[str] = []
    try:
        registry = load_registry(base)
    except (OSError, PaperError) as exc:
        return [str(exc)]
    if set(registry) != {"version", "standard_version", "papers"}:
        errors.append(f"{base / 'REGISTRY.yaml'}: registry has missing or unknown top-level keys")
    if registry.get("version") != 1:
        errors.append(f"{base / 'REGISTRY.yaml'}: registry version must be 1")
    if registry.get("standard_version") != STANDARD_VERSION:
        errors.append(f"{base / 'REGISTRY.yaml'}: standard_version must be {STANDARD_VERSION}")
    entries = registry.get("papers")
    if not isinstance(entries, list):
        return errors + [f"{base / 'REGISTRY.yaml'}: papers must be a list"]

    registry_by_id: dict[str, dict[str, Any]] = {}
    registry_paths: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"{base / 'REGISTRY.yaml'}:papers[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: entry must be a mapping")
            continue
        if set(entry) != REGISTRY_FIELDS:
            errors.append(f"{label}: entry must contain exactly {sorted(REGISTRY_FIELDS)}")
        paper_id = entry.get("id")
        path_value = entry.get("path")
        if not isinstance(paper_id, str):
            errors.append(f"{label}: id must be a string")
        elif paper_id in registry_by_id:
            errors.append(f"{label}: duplicate registry ID {paper_id}")
        else:
            registry_by_id[paper_id] = entry
        if not isinstance(path_value, str) or Path(path_value).is_absolute() or ".." in Path(path_value).parts:
            errors.append(f"{label}: path must be a safe relative path")
        elif path_value in registry_paths:
            errors.append(f"{label}: duplicate registry path {path_value}")
        else:
            registry_paths.add(path_value)

    files = discover_papers(base)
    file_paths = {relative_paper_path(base, path) for path in files}
    for missing in sorted(registry_paths - file_paths):
        errors.append(f"{base / 'REGISTRY.yaml'}: registered path does not exist: {missing}")
    for unregistered in sorted(file_paths - registry_paths):
        errors.append(f"{base / 'REGISTRY.yaml'}: unregistered paper file: {unregistered}")

    papers: dict[str, tuple[dict[str, Any], str, Path]] = {}
    for path in files:
        try:
            metadata, body = parse_paper(path)
        except (OSError, PaperError) as exc:
            errors.append(str(exc))
            continue
        errors.extend(validate_metadata(metadata, path, base, production))
        errors.extend(validate_body(metadata, body, path, base))
        paper_id = metadata.get("id")
        if isinstance(paper_id, str):
            if paper_id in papers:
                errors.append(f"duplicate filesystem paper ID: {paper_id}")
            papers[paper_id] = (metadata, body, path)
            entry = registry_by_id.get(paper_id)
            if entry:
                expected = {
                    "id": paper_id,
                    "type": metadata.get("type"),
                    "domain": metadata.get("domain"),
                    "title": metadata.get("title"),
                    "status": metadata.get("status"),
                    "path": relative_paper_path(base, path),
                }
                if entry != expected:
                    errors.append(f"{paper_id}: registry entry differs from front matter/path")
            elif relative_paper_path(base, path) in registry_paths:
                errors.append(f"{relative_paper_path(base, path)}: registry ID differs from front matter")

    bucket_for_type = {"ISSUE": "issues", "PLAN": "plans", "REPORT": "reports"}
    for paper_id, (metadata, body, path) in papers.items():
        label = relative_paper_path(base, path)
        related = metadata.get("related")
        if not isinstance(related, dict):
            continue
        if metadata.get("type") == "PLAN" and not related.get("issues"):
            errors.append(f"{label}: PLAN must link at least one ISSUE")
        if metadata.get("type") == "REPORT":
            if not related.get("issues"):
                errors.append(f"{label}: REPORT must link at least one ISSUE")
            if not related.get("plans"):
                errors.append(f"{label}: REPORT must link at least one PLAN")
        for bucket, targets in related.items():
            if not isinstance(targets, list):
                continue
            expected_type = {"issues": "ISSUE", "plans": "PLAN", "reports": "REPORT"}.get(bucket)
            for target_id in targets:
                target = papers.get(target_id)
                if target is None:
                    errors.append(f"{label}: unresolved related ID {target_id}")
                    continue
                target_metadata = target[0]
                if target_metadata.get("type") != expected_type:
                    errors.append(f"{label}: {target_id} is in wrong related bucket {bucket}")
                    continue
                source_bucket = bucket_for_type.get(metadata.get("type"))
                target_related = target_metadata.get("related")
                if source_bucket and isinstance(target_related, dict):
                    if paper_id not in target_related.get(source_bucket, []):
                        errors.append(f"{label}: link to {target_id} is not reciprocal")

        supersedes = metadata.get("supersedes")
        superseded_by = metadata.get("superseded_by")
        if isinstance(supersedes, str):
            target = papers.get(supersedes)
            if not target:
                errors.append(f"{label}: unresolved supersedes ID {supersedes}")
            elif target[0].get("superseded_by") != paper_id:
                errors.append(f"{label}: supersedes link to {supersedes} is not reciprocal")
        if isinstance(superseded_by, str):
            target = papers.get(superseded_by)
            if not target:
                errors.append(f"{label}: unresolved superseded_by ID {superseded_by}")
            elif target[0].get("supersedes") != paper_id:
                errors.append(f"{label}: superseded_by link to {superseded_by} is not reciprocal")

        if metadata.get("type") == "ISSUE" and metadata.get("status") == "CLOSED":
            accepted_ready = False
            for report_id in related.get("reports", []):
                report = papers.get(report_id)
                if report and report[0].get("status") == "ACCEPTED" and "READY_FOR_CLOSE" in report[1]:
                    accepted_ready = True
            if not accepted_ready:
                errors.append(f"{label}: CLOSED issue lacks an ACCEPTED READY_FOR_CLOSE report")
    return errors


def command_validate(root: Path) -> int:
    errors = validate_schema_files(root)
    errors.extend(validate_templates(root))
    errors.extend(validate_scope(root / "papers", production=True))
    errors.extend(validate_scope(root / "papers" / "examples", production=False))
    skill = root / ".agents" / "skills" / "vir-paper-management" / "SKILL.md"
    if not skill.is_file():
        errors.append("missing skill: .agents/skills/vir-paper-management/SKILL.md")
    else:
        skill_text = skill.read_text(encoding="utf-8")
        for reference in ("papers/STANDARD.md", "papers/REGISTRY.yaml", "./paper"):
            if reference not in skill_text:
                errors.append(f"skill does not reference {reference}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"VPS validation failed with {len(errors)} error(s).", file=sys.stderr)
        return 1
    production_count = len(discover_papers(root / "papers"))
    example_count = len(discover_papers(root / "papers" / "examples"))
    print(f"VPS validation passed: {production_count} production paper(s), {example_count} example paper(s).")
    return 0


def find_entry(root: Path, paper_id: str, include_examples: bool = True) -> tuple[Path, dict[str, Any], Path]:
    scopes = [root / "papers"]
    if include_examples:
        scopes.append(root / "papers" / "examples")
    for base in scopes:
        for entry in registry_entries(base):
            if entry.get("id") == paper_id:
                path = base / str(entry.get("path"))
                return base, entry, path
    raise PaperError(f"unknown paper ID: {paper_id}")


def command_list(root: Path, args: argparse.Namespace) -> int:
    base = root / "papers" / "examples" if args.examples else root / "papers"
    entries = registry_entries(base)
    for entry in sorted(entries, key=lambda item: str(item.get("id"))):
        if args.domain and entry.get("domain") != args.domain:
            continue
        if args.type and entry.get("type") != args.type:
            continue
        if args.status and entry.get("status") != args.status:
            continue
        print(f"{entry.get('id')}  {entry.get('status')}  {entry.get('title')}")
    return 0


def command_show(root: Path, args: argparse.Namespace) -> int:
    _, _, path = find_entry(root, args.id)
    sys.stdout.write(path.read_text(encoding="utf-8"))
    return 0


def slugify(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_title).strip("_")
    slug = re.sub(r"_+", "_", slug)[:80].rstrip("_")
    return slug or "paper"


def allocate_id(base: Path, domain: str, paper_type: str) -> str:
    code = TYPE_INFO[paper_type][0]
    numbers: set[int] = set()
    for path in discover_papers(base):
        match = ID_RE.fullmatch(path.name.split("_", 1)[0])
        if match and match.group(1) == domain and match.group(2) == code:
            numbers.add(int(match.group(3)))
    for entry in registry_entries(base):
        match = ID_RE.fullmatch(str(entry.get("id")))
        if match and match.group(1) == domain and match.group(2) == code:
            numbers.add(int(match.group(3)))
    number = max(numbers | {0}) + 1
    if number > 9999:
        raise PaperError(f"ID space exhausted for {domain} {paper_type}")
    return f"{domain}-{code}-{number:04d}"


def append_revision(body: str, date: str, change: str) -> str:
    lines = body.rstrip().splitlines()
    heading = next((index for index, line in enumerate(lines) if re.match(r"^## [0-9]+\. Revision History$", line)), None)
    if heading is None:
        raise PaperError("paper has no Revision History section")
    insert_at = heading + 1
    while insert_at < len(lines) and (not lines[insert_at].strip() or lines[insert_at].lstrip().startswith("|")):
        insert_at += 1
    row = f"| {date} | {change} |"
    if row not in lines:
        lines.insert(insert_at, row)
    return "\n".join(lines) + "\n"


def add_reciprocal_link(root: Path, source_id: str, target_id: str, record_source: bool = True) -> None:
    if source_id == target_id:
        raise PaperError("cannot link a paper to itself")
    source_base, _, source_path = find_entry(root, source_id, include_examples=False)
    target_base, _, target_path = find_entry(root, target_id, include_examples=False)
    if source_base != target_base:
        raise PaperError("links must remain in the same registry scope")
    source_metadata, source_body = parse_paper(source_path)
    target_metadata, target_body = parse_paper(target_path)
    bucket_for_type = {"ISSUE": "issues", "PLAN": "plans", "REPORT": "reports"}
    source_bucket = bucket_for_type.get(source_metadata.get("type"))
    target_bucket = bucket_for_type.get(target_metadata.get("type"))
    if not source_bucket or not target_bucket:
        raise PaperError("cannot link a paper with invalid type")
    changed_source = target_id not in source_metadata["related"][target_bucket]
    changed_target = source_id not in target_metadata["related"][source_bucket]
    date = today()
    if changed_source:
        source_metadata["related"][target_bucket].append(target_id)
        source_metadata["related"][target_bucket].sort()
        source_metadata["updated"] = date
        if record_source:
            source_body = append_revision(source_body, date, f"Linked {target_id}")
        write_paper(source_path, source_metadata, source_body)
    if changed_target:
        target_metadata["related"][source_bucket].append(source_id)
        target_metadata["related"][source_bucket].sort()
        target_metadata["updated"] = date
        target_body = append_revision(target_body, date, f"Linked {source_id}")
        write_paper(target_path, target_metadata, target_body)
    if changed_source or changed_target:
        write_registry(source_base)


def render_new_body(template_body: str, paper_id: str, title: str, paper_type: str, links: dict[str, list[str]]) -> str:
    body = template_body.replace("<ID>", paper_id).replace("<Title>", title).replace("<TITLE>", title)
    if paper_type == "PLAN":
        body = body.replace("- <ISSUE-ID>", "\n".join(f"- {item}" for item in links["issues"]))
    elif paper_type == "REPORT":
        body = body.replace(
            "## 2. Source Issues\n\n- ...",
            "## 2. Source Issues\n\n" + "\n".join(f"- {item}" for item in links["issues"]),
        )
        body = body.replace(
            "## 3. Source Plans\n\n- ...",
            "## 3. Source Plans\n\n" + "\n".join(f"- {item}" for item in links["plans"]),
        )
        body = re.sub(
            r"Một trong:\n\n```text\nREADY_FOR_CLOSE\nPARTIALLY_RESOLVED\nREQUIRES_FOLLOWUP\nFAILED_VERIFICATION\n```",
            "REQUIRES_FOLLOWUP",
            body,
        )
    return body


def command_new(root: Path, args: argparse.Namespace) -> int:
    paper_type = args.kind.upper()
    links = {
        "issues": list(dict.fromkeys(args.issue or [])),
        "plans": list(dict.fromkeys(args.plan or [])),
        "reports": [],
    }
    if paper_type == "PLAN" and not links["issues"]:
        raise PaperError("new PLAN requires at least one --issue")
    if paper_type == "REPORT" and (not links["issues"] or not links["plans"]):
        raise PaperError("new REPORT requires at least one --issue and one --plan")
    expected_types = [(item, "ISSUE") for item in links["issues"]] + [(item, "PLAN") for item in links["plans"]]
    for target_id, expected_type in expected_types:
        _, entry, _ = find_entry(root, target_id, include_examples=False)
        if entry.get("type") != expected_type:
            raise PaperError(f"{target_id} is not a {expected_type}")

    base = root / "papers"
    paper_id = allocate_id(base, args.domain, paper_type)
    date = today()
    metadata: dict[str, Any] = {
        "id": paper_id,
        "type": paper_type,
        "domain": args.domain,
        "title": args.title,
        "status": "DRAFT",
    }
    if paper_type == "ISSUE":
        metadata["severity"] = args.severity
        metadata["priority"] = args.priority
    elif paper_type == "SPEC":
        metadata["version"] = args.version
        metadata["language"] = args.language
        metadata["spec_class"] = args.spec_class
        metadata["aliases"] = []
    metadata.update({
        "created": date,
        "updated": date,
        "owners": [],
        "components": [],
        "related": links,
        "supersedes": None,
        "superseded_by": None,
        "tags": [],
    })
    _, directory, template_name = TYPE_INFO[paper_type]
    template_path = base / "templates" / template_name
    _, template_body = parse_paper(template_path)
    body = render_new_body(template_body, paper_id, args.title, paper_type, links)
    path = base / args.domain / directory / f"{paper_id}_{slugify(args.title)}.md"
    if path.exists():
        raise PaperError(f"refusing to overwrite {path}")
    write_paper(path, metadata, body)
    write_registry(base)
    for target_id, _ in expected_types:
        add_reciprocal_link(root, paper_id, target_id, record_source=False)
    print(f"Created {paper_id}: {path.relative_to(root)}")
    return 0


def command_link(root: Path, args: argparse.Namespace) -> int:
    add_reciprocal_link(root, args.source, args.target)
    print(f"Linked {args.source} ↔ {args.target}")
    return 0


def command_registry(root: Path, args: argparse.Namespace) -> int:
    base = root / "papers"
    generated = registry_from_files(base)
    if args.write:
        atomic_write(base / "REGISTRY.yaml", dump_yaml(generated) + "\n")
        print(f"Updated {base / 'REGISTRY.yaml'}")
        return 0
    existing = load_registry(base)
    if existing != generated:
        print("ERROR: papers/REGISTRY.yaml is out of sync; run ./paper registry --write", file=sys.stderr)
        return 1
    print("papers/REGISTRY.yaml is synchronized.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper", description="VIR Paper Standard tooling")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="validate schemas, papers, registries, links, and fixtures")

    list_parser = subparsers.add_parser("list", help="list registered papers")
    list_parser.add_argument("--domain", choices=DOMAINS)
    list_parser.add_argument("--type", choices=tuple(TYPE_INFO))
    list_parser.add_argument("--status")
    list_parser.add_argument("--examples", action="store_true")

    show_parser = subparsers.add_parser("show", help="print a paper by ID")
    show_parser.add_argument("id")

    new_parser = subparsers.add_parser("new", help="create and register a paper")
    new_parser.add_argument("kind", choices=("issue", "plan", "report", "spec"))
    new_parser.add_argument("domain", choices=DOMAINS)
    new_parser.add_argument("title")
    new_parser.add_argument("--issue", action="append", help="source ISSUE ID; repeatable")
    new_parser.add_argument("--plan", action="append", help="source PLAN ID; repeatable")
    new_parser.add_argument("--severity", choices=sorted(SEVERITIES), default="S2")
    new_parser.add_argument("--priority", choices=sorted(PRIORITIES), default="P2")
    new_parser.add_argument("--version", default="1.0.0", help="SPEC semantic version")
    new_parser.add_argument("--language", default="en", help="SPEC language tag")
    new_parser.add_argument("--spec-class", choices=sorted(SPEC_CLASSES), default="SPECIFICATION")

    link_parser = subparsers.add_parser("link", help="add a reciprocal relationship")
    link_parser.add_argument("source")
    link_parser.add_argument("target")

    registry_parser = subparsers.add_parser("registry", help="check or regenerate the production registry")
    registry_mode = registry_parser.add_mutually_exclusive_group(required=True)
    registry_mode.add_argument("--check", action="store_true")
    registry_mode.add_argument("--write", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "validate":
            return command_validate(root)
        if args.command == "list":
            return command_list(root, args)
        if args.command == "show":
            return command_show(root, args)
        if args.command == "new":
            return command_new(root, args)
        if args.command == "link":
            return command_link(root, args)
        if args.command == "registry":
            return command_registry(root, args)
    except (OSError, PaperError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

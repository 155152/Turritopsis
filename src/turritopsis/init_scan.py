from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


MANIFESTS = {
    "pyproject.toml", "package.json", "Cargo.toml", "go.mod", "pom.xml",
    "build.gradle", "build.gradle.kts", "composer.json", "Gemfile",
    "Dockerfile", "compose.yml", "compose.yaml",
}
MATERIAL_NAMES = MANIFESTS | {"AGENTS.md", "CLAUDE.md", "Makefile"}
TEXT_SUFFIXES = {
    ".md", ".rst", ".txt", ".toml", ".json", ".yaml", ".yml",
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go",
    ".java", ".kt", ".rb", ".php", ".sh", ".ps1", ".sql",
}
SKIP_DIRS = {
    ".git", ".turritopsis", "node_modules", ".venv", "venv", "dist", "build",
    "target", "vendor", "__pycache__", ".pytest_cache", ".mypy_cache",
}
SENSITIVE_PARTS = {"secret", "credential", "token", "private", "apikey", "api_key"}
MAX_TREE_FILES = 3000
MAX_MATERIALS = 40
MAX_FILE_CHARS = 12000
MAX_TOTAL_CHARS = 70000


SKELETON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "currents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "blurb": {"type": "string"},
                    "stages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "title": {"type": "string"},
                                "purpose": {"type": "string"},
                                "search_hints": {"type": "string"},
                                "authority": {"type": "string"},
                                "evidence_paths": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["id", "title", "purpose", "search_hints", "authority", "evidence_paths"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["id", "name", "blurb", "stages"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["currents"],
    "additionalProperties": False,
}


def _safe_file(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    lowered = {part.lower() for part in relative.parts}
    if lowered & {item.lower() for item in SKIP_DIRS}:
        return False
    name = path.name.lower()
    if name.startswith(".env") or name.endswith((".lock", ".pem", ".key")):
        return False
    return not any(part in name for part in SENSITIVE_PARTS)


def scan_project(root: Path) -> dict[str, Any]:
    """Collect bounded, reviewable project evidence for LLM classification."""
    root = root.resolve()
    files = []
    for path in sorted(root.rglob("*")):
        if len(files) >= MAX_TREE_FILES:
            break
        if path.is_file() and _safe_file(path, root):
            files.append(path)
    tree = [path.relative_to(root).as_posix() for path in files]
    candidates = sorted(
        files,
        key=lambda path: (
            0 if path.name.lower().startswith("readme") else
            1 if path.name in MATERIAL_NAMES else
            2 if ".github" in path.parts else 3,
            len(path.parts), path.as_posix(),
        ),
    )
    materials: list[dict[str, str]] = []
    used = 0
    for path in candidates:
        if len(materials) >= MAX_MATERIALS or used >= MAX_TOTAL_CHARS:
            break
        if not (path.name in MATERIAL_NAMES or path.name.lower().startswith("readme") or path.suffix.lower() in TEXT_SUFFIXES):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_CHARS]
        except OSError:
            continue
        if not content.strip():
            continue
        remaining = MAX_TOTAL_CHARS - used
        content = content[:remaining]
        materials.append({"path": path.relative_to(root).as_posix(), "content": content})
        used += len(content)
    return {"root_name": root.name, "tree": tree, "materials": materials}


def _valid_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_-]*", value))


def _stage_body(stage: dict[str, Any]) -> str:
    paths = [str(path) for path in stage.get("evidence_paths", [])]
    evidence = "\n".join(f"- `{path}`" for path in paths) or "- [Placeholder: add an evidence path]"
    authority = stage.get("authority", "") or "unassigned"
    return (
        f"# {stage['title']}\n\n"
        f"Purpose: {stage['purpose']}\n"
        f"Search hints: {stage['search_hints']}\n"
        "Summary: [Placeholder: verify and describe this knowledge region.]\n"
        "Verified: not yet verified\n"
        "Status: unresolved\n"
        f"Authority: {authority}\n\n"
        "## Knowledge\n\n"
        "[Placeholder: fill from verified project evidence.]\n\n"
        "## Evidence to review\n\n"
        f"{evidence}\n"
    )


def generate_skeleton(
    root: Path,
    title: str,
    subtitle: str,
    client,
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = scan_project(root)
    prompt = (
        "Classify this long-running software project into 3-8 durable knowledge Currents. "
        "Create addressable Stage skeletons, not a code index. Use only the supplied project tree and materials. "
        "Stage titles, purposes, search hints, authority scopes, and relevant evidence paths are allowed. "
        "Do not assert unverified project facts; canonical bodies will be created locally as placeholders. "
        "Every Stage id must be current_id.topic, lowercase ASCII, and every evidence path must appear in the supplied tree.\n\n"
        f"PROJECT EVIDENCE:\n{json.dumps(evidence, ensure_ascii=False)}"
    )
    result = client.complete_json(
        "You design conservative, evidence-routed project knowledge maps. You never invent canonical truth.",
        prompt, SKELETON_SCHEMA, "turritopsis_project_skeleton",
    )
    currents = result.get("currents", [])
    if not 3 <= len(currents) <= 8:
        raise ValueError("LLM skeleton must contain 3-8 Currents")
    known_paths = set(evidence["tree"])
    seen_currents: set[str] = set()
    seen_stages: set[str] = set()
    canonical_currents = []
    for current in currents:
        current_id = current["id"].strip()
        if not _valid_id(current_id) or current_id in seen_currents:
            raise ValueError(f"Invalid or duplicate Current id from LLM: {current_id}")
        seen_currents.add(current_id)
        canonical_stages = []
        for stage in current["stages"]:
            stage_id = stage["id"].strip()
            if not re.fullmatch(rf"{re.escape(current_id)}\.[a-z][a-z0-9_.-]*", stage_id) or stage_id in seen_stages:
                raise ValueError(f"Invalid or duplicate Stage id from LLM: {stage_id}")
            unknown = sorted(set(stage["evidence_paths"]) - known_paths)
            if unknown:
                raise ValueError(f"LLM Stage {stage_id} cited unknown evidence: {', '.join(unknown)}")
            seen_stages.add(stage_id)
            canonical_stages.append({"id": stage_id, "title": stage["title"].strip(), "body": _stage_body(stage)})
        canonical_currents.append({
            "id": current_id, "name": current["name"].strip(),
            "blurb": current["blurb"].strip(), "stages": canonical_stages,
        })
    return {
        "title": title, "subtitle": subtitle, "version": 1,
        "currents": canonical_currents,
    }, evidence

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from .metadata import parse_metadata
from .revisions import revision
from .store import Store


def _git_revision(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=10,
    )
    if result.returncode:
        raise ValueError("git revision is unavailable")
    return {"git_revision": result.stdout.strip()}


def _file_hash(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    relative = config.get("path")
    if not relative:
        raise ValueError("file_hash generator requires path")
    target = (root / relative).resolve()
    if root.resolve() not in (target, *target.parents):
        raise ValueError("generated path escapes project root")
    return {"path": str(relative), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


def _path_exists(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    relative = config.get("path")
    if not relative:
        raise ValueError("path_exists generator requires path")
    target = (root / relative).resolve()
    if root.resolve() not in (target, *target.parents):
        raise ValueError("generated path escapes project root")
    return {"path": str(relative), "exists": target.exists()}


GENERATORS = {"git_revision": _git_revision, "file_hash": _file_hash, "path_exists": _path_exists}


def refresh_generated(data_path: Path) -> list[dict[str, Any]]:
    """Refresh only explicitly generated Stages through deterministic scanners."""
    store = Store(data_path)
    data = store.load()
    project_root = data_path.parent.parent
    results = []
    for current in data.get("currents", []):
        for stage in current.get("stages", []):
            body = str(stage.get("body") or "")
            meta = parse_metadata(body, stage)
            config = stage.get("generator")
            if meta["status"] != "generated" or not isinstance(config, dict):
                continue
            kind = config.get("type")
            scanner = GENERATORS.get(kind)
            if not scanner:
                results.append({"stage_id": stage.get("id"), "changed": False,
                                "error": f"unknown deterministic generator: {kind}"})
                continue
            try:
                facts = scanner(project_root, config)
                rendered = "\n".join([
                    f"# {stage.get('title', stage.get('id', 'Generated facts'))}", "",
                    "Status: generated",
                    "Purpose: Deterministic mechanical project facts.",
                    "Summary: Automatically refreshed mechanical evidence.",
                    "", "> auto-generated", "> manual edits will be overwritten", "",
                    "```json", __import__("json").dumps(facts, ensure_ascii=False, indent=2), "```", "",
                ])
                update = store.update_stage(stage["id"], rendered, "replace", revision(body), "deterministic-scanner")
                results.append(update)
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                results.append({"stage_id": stage.get("id"), "changed": False, "error": str(error)})
    return results

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from .init_scan import scan_anomalies, scan_project


SCHEMA_VERSION = "2"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scanner_version() -> str:
    try:
        return version("turritopsis")
    except PackageNotFoundError:
        return "source-checkout"


def canonical_json(document: Any) -> bytes:
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_document(document: Any) -> str:
    return hashlib.sha256(canonical_json(document)).hexdigest()


def write_json_atomic(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run_local_scan(
    root: Path,
    *,
    refresh: bool = False,
    agent: str = "installed-agent",
) -> dict[str, Any]:
    """Create the complete local evidence snapshot without a model or network."""
    root = root.expanduser().resolve()
    data_dir = root / ".turritopsis"
    evidence_path = data_dir / "scan-evidence.json"
    anomalies_path = data_dir / "scan-anomalies.json"
    run_path = data_dir / "scan-run.json"

    if evidence_path.is_file() and run_path.is_file() and not refresh:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        run = json.loads(run_path.read_text(encoding="utf-8"))
        return {
            "resumed": True,
            "state": run.get("state", "evidence_ready"),
            "evidence": str(evidence_path),
            "anomalies": str(anomalies_path) if anomalies_path.is_file() else None,
            "scan_run": str(run_path),
            "evidence_sha256": sha256_document(evidence),
            "next": "Have the installed Agent classify scan-evidence.json, then run turritopsis apply-skeleton skeleton.json",
        }

    started = _now()
    write_json_atomic(run_path, {
        "scanner_version": _scanner_version(),
        "schema_version": SCHEMA_VERSION,
        "mode": "installed-agent",
        "agent": agent,
        "started_at": started,
        "state": "scanning",
        "classification_source": "pending-installed-agent",
        "warnings": [],
    })

    evidence = scan_project(root)
    # Evidence is committed first. If the Agent, editor, or network disappears after
    # this point, classification can continue without rescanning the repository.
    write_json_atomic(evidence_path, evidence)
    anomalies = scan_anomalies(root)
    write_json_atomic(anomalies_path, anomalies)

    coverage = {
        "tree_files": len(evidence.get("tree", [])),
        "material_files": len(evidence.get("materials", [])),
        "material_characters": sum(
            len(str(item.get("content", ""))) for item in evidence.get("materials", [])
        ),
        "structure": evidence.get("structure_coverage", {}),
    }
    run = {
        "scanner_version": _scanner_version(),
        "schema_version": SCHEMA_VERSION,
        "mode": "installed-agent",
        "agent": agent,
        "started_at": started,
        "completed_at": _now(),
        "state": "evidence_ready",
        "evidence_sha256": sha256_document(evidence),
        "coverage": coverage,
        "classification_source": "pending-installed-agent",
        "warnings": [],
    }
    write_json_atomic(run_path, run)
    return {
        "resumed": False,
        "state": "evidence_ready",
        "evidence": str(evidence_path),
        "anomalies": str(anomalies_path),
        "scan_run": str(run_path),
        "evidence_sha256": run["evidence_sha256"],
        "next": "Have the installed Agent classify scan-evidence.json, then run turritopsis apply-skeleton skeleton.json",
    }

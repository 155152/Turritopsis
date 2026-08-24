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
TYPICAL_STAGE_COUNT = 14


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


def _capacity_estimate(evidence: dict[str, Any]) -> dict[str, Any]:
    code_files = int(evidence.get("structure_coverage", {}).get("code_files_found", 0))
    raw = code_files / TYPICAL_STAGE_COUNT
    files_per_stage = (
        int(round(raw / 10.0) * 10) if raw >= 100 else max(1, int(round(raw)))
    ) if code_files else 0
    return {
        "code_files_found": code_files,
        "typical_stage_count": TYPICAL_STAGE_COUNT,
        "estimated_files_per_stage": files_per_stage,
        "guidance": "<=5 detail-rich; 10-30 comfortable; >=100 map-only",
    }


def _capacity_hint(estimate: dict[str, Any]) -> str:
    return (
        f"{estimate['code_files_found']} code files · "
        f"预计每个 Stage 需覆盖约 {estimate['estimated_files_per_stage']} 个文件\n"
        "参考：≤5 细节充分 · 10–30 舒适 · ≥100 仅能给出地图"
    )


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
        capacity = run.get("stage_capacity_estimate") or _capacity_estimate(evidence)
        if "stage_capacity_estimate" not in run:
            run["stage_capacity_estimate"] = capacity
            run["warnings"] = list(evidence.get("scan_warnings", run.get("warnings", [])))
            write_json_atomic(run_path, run)
        return {
            "resumed": True,
            "state": run.get("state", "evidence_ready"),
            "evidence": str(evidence_path),
            "anomalies": str(anomalies_path) if anomalies_path.is_file() else None,
            "scan_run": str(run_path),
            "evidence_sha256": sha256_document(evidence),
            "capacity_hint": _capacity_hint(capacity),
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
    capacity = _capacity_estimate(evidence)
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
        "stage_capacity_estimate": capacity,
        "classification_source": "pending-installed-agent",
        "warnings": list(evidence.get("scan_warnings", [])),
    }
    write_json_atomic(run_path, run)
    return {
        "resumed": False,
        "state": "evidence_ready",
        "evidence": str(evidence_path),
        "anomalies": str(anomalies_path),
        "scan_run": str(run_path),
        "evidence_sha256": run["evidence_sha256"],
        "capacity_hint": _capacity_hint(capacity),
        "next": "Have the installed Agent classify scan-evidence.json, then run turritopsis apply-skeleton skeleton.json",
    }

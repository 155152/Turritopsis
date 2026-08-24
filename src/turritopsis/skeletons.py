from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .scan_run import sha256_document, write_json_atomic


STAGE_TYPES = {
    "orientation", "authority", "architecture", "flow", "contract", "domain",
    "data", "boundary", "operations", "verification", "build_release", "handoff",
    "decision", "incident", "history", "generated_inventory",
}
FRESHNESS = {"volatile", "steady", "historical", "generated"}
GARBAGE_IDS = {"misc", "other", "notes", "stuff", "general"}
ID = re.compile(r"^[a-z][a-z0-9_-]*$")


def _required_text(document: dict[str, Any], key: str, where: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}.{key} must be a non-empty string")
    return value.strip()


def _normalise_authority(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().rstrip("."))


def _reject_extra(document: dict[str, Any], allowed: set[str], where: str) -> None:
    extra = sorted(set(document) - allowed)
    if extra:
        raise ValueError(f"{where} contains unsupported fields: {', '.join(extra)}")


def _stage_body(stage: dict[str, Any]) -> str:
    evidence = "\n".join(f"- `{path}`" for path in stage["evidence_paths"])
    return (
        f"# {stage['title']}\n\n"
        f"Type: {stage['type']}\n"
        f"Purpose: {stage['purpose']}\n"
        f"Search hints: {stage['search_hints']}\n"
        "Summary: [Placeholder: give the direct answer after verifying the evidence.]\n"
        "Verified: not yet verified\n"
        "Status: unresolved\n"
        f"Authority: {stage['authority']}\n"
        f"Freshness: {stage['freshness']}\n\n"
        "## Knowledge\n\n[Placeholder: write one complete knowledge region.]\n\n"
        f"## Evidence\n\n{evidence}\n\n"
        "## Unknowns\n\n- [Placeholder: preserve what is not yet confirmed.]\n\n"
        "## Update triggers\n\n"
        + "\n".join(f"- {item}" for item in stage["update_triggers"])
        + "\n"
    )


def validate_skeleton(
    document: dict[str, Any], evidence: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(document, dict):
        raise ValueError("skeleton must be a JSON object")
    _reject_extra(document, {"title", "subtitle", "classification_provenance", "currents"}, "skeleton")
    provenance = document.get("classification_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("classification_provenance must be an object")
    _reject_extra(
        provenance,
        {"source", "agent_self_reported", "created_at", "notes"},
        "classification_provenance",
    )
    source = _required_text(provenance, "source", "classification_provenance")
    agent_self_reported = _required_text(
        provenance, "agent_self_reported", "classification_provenance"
    )
    created_at = _required_text(provenance, "created_at", "classification_provenance")
    currents = document.get("currents")
    if not isinstance(currents, list) or not currents:
        raise ValueError("currents must be a non-empty array")
    if len(currents) > 12:
        raise ValueError("skeleton is over-fragmented: at most 12 Currents are allowed")

    known_paths = set(evidence.get("tree", []))
    known_paths.update(str(item.get("path")) for item in evidence.get("materials", []) if item.get("path"))
    seen_currents: set[str] = set()
    seen_stages: set[str] = set()
    authorities: dict[str, str] = {}
    canonical_currents: list[dict[str, Any]] = []
    warnings: list[str] = []
    stage_count = 0

    for current_index, current in enumerate(currents):
        where = f"currents[{current_index}]"
        if not isinstance(current, dict):
            raise ValueError(f"{where} must be an object")
        _reject_extra(current, {"id", "name", "blurb", "stages"}, where)
        current_id = _required_text(current, "id", where)
        if not ID.fullmatch(current_id) or current_id in seen_currents:
            raise ValueError(f"invalid or duplicate Current id: {current_id}")
        if current_id in GARBAGE_IDS:
            raise ValueError(f"garbage-drawer Current id is not allowed: {current_id}")
        seen_currents.add(current_id)
        name = _required_text(current, "name", where)
        blurb = _required_text(current, "blurb", where)
        stages = current.get("stages")
        if not isinstance(stages, list) or not stages:
            raise ValueError(f"{where}.stages must be a non-empty array")
        if len(stages) > 12:
            raise ValueError(f"{current_id} is over-fragmented: at most 12 Stages per Current")
        canonical_stages: list[dict[str, str]] = []
        for stage_index, stage in enumerate(stages):
            stage_where = f"{where}.stages[{stage_index}]"
            if not isinstance(stage, dict):
                raise ValueError(f"{stage_where} must be an object")
            _reject_extra(stage, {
                "id", "title", "type", "freshness", "purpose", "search_hints",
                "authority", "evidence_paths", "update_triggers",
            }, stage_where)
            stage_id = _required_text(stage, "id", stage_where)
            if not re.fullmatch(rf"{re.escape(current_id)}\.[a-z][a-z0-9_.-]*", stage_id) or stage_id in seen_stages:
                raise ValueError(f"invalid or duplicate Stage id: {stage_id}")
            if stage_id.rsplit(".", 1)[-1] in GARBAGE_IDS:
                raise ValueError(f"garbage-drawer Stage id is not allowed: {stage_id}")
            seen_stages.add(stage_id)
            title = _required_text(stage, "title", stage_where)
            purpose = _required_text(stage, "purpose", stage_where)
            search_hints = _required_text(stage, "search_hints", stage_where)
            authority = _required_text(stage, "authority", stage_where)
            stage_type = _required_text(stage, "type", stage_where)
            freshness = _required_text(stage, "freshness", stage_where)
            if stage_type not in STAGE_TYPES:
                raise ValueError(f"{stage_id}.type must be one of: {', '.join(sorted(STAGE_TYPES))}")
            if freshness not in FRESHNESS:
                raise ValueError(f"{stage_id}.freshness must be one of: {', '.join(sorted(FRESHNESS))}")
            authority_key = _normalise_authority(authority)
            if authority_key in authorities:
                raise ValueError(
                    f"duplicate Authority: {stage_id} and {authorities[authority_key]} both own '{authority}'"
                )
            authorities[authority_key] = stage_id
            paths = stage.get("evidence_paths")
            if not isinstance(paths, list) or not paths or not all(isinstance(path, str) and path.strip() for path in paths):
                raise ValueError(f"{stage_id}.evidence_paths must be a non-empty string array")
            unknown = sorted({path for path in paths if path not in known_paths})
            if unknown:
                raise ValueError(f"{stage_id} cites evidence absent from scan-evidence.json: {', '.join(unknown)}")
            triggers = stage.get("update_triggers")
            if not isinstance(triggers, list) or not triggers or not all(isinstance(item, str) and item.strip() for item in triggers):
                raise ValueError(f"{stage_id}.update_triggers must be a non-empty string array")
            canonical = {
                "id": stage_id,
                "title": title,
                "body": _stage_body({
                    **stage,
                    "title": title,
                    "purpose": purpose,
                    "search_hints": search_hints,
                    "authority": authority,
                    "type": stage_type,
                    "freshness": freshness,
                    "evidence_paths": list(dict.fromkeys(paths)),
                    "update_triggers": list(dict.fromkeys(item.strip() for item in triggers)),
                }),
            }
            canonical_stages.append(canonical)
            stage_count += 1
        canonical_currents.append({"id": current_id, "name": name, "blurb": blurb, "stages": canonical_stages})

    if stage_count > 48:
        raise ValueError("skeleton is over-fragmented: at most 48 Stages are allowed")
    if len(currents) > 8:
        warnings.append("More than 8 Currents: confirm each is a durable knowledge region, not a directory")
    if stage_count > 24:
        warnings.append("More than 24 Stages: confirm the map is not one-file or one-directory per Stage")
    data = {
        "title": str(document.get("title") or evidence.get("root_name") or "Project"),
        "subtitle": str(document.get("subtitle") or "Shared project truth"),
        "version": 1,
        "classification": {
            "source": source,
            "agent_self_reported": agent_self_reported,
            "created_at": created_at,
        },
        "currents": canonical_currents,
    }
    return data, {"currents": len(currents), "stages": stage_count, "warnings": warnings}


def apply_skeleton(root: Path, skeleton_path: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    data_dir = root / ".turritopsis"
    evidence_path = data_dir / "scan-evidence.json"
    if not evidence_path.is_file():
        raise FileNotFoundError(f"Missing scan evidence: {evidence_path}. Run 'turritopsis scan' first.")
    target = data_dir / "stages.json"
    if target.exists():
        raise FileExistsError(
            f"Already exists: {target}; apply-skeleton never overwrites a knowledge base. "
            "Use revision-protected update_stage for later changes."
        )
    document = json.loads(skeleton_path.expanduser().resolve().read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    data, report = validate_skeleton(document, evidence)
    write_json_atomic(target, data)
    (data_dir / "backups").mkdir(exist_ok=True)
    (data_dir / "proposals").mkdir(exist_ok=True)
    run_path = data_dir / "scan-run.json"
    if run_path.is_file():
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run.update({
            "state": "skeleton_applied",
            "classification_source": data["classification"]["source"],
            "classification_agent_self_reported": data["classification"]["agent_self_reported"],
            "skeleton_sha256": sha256_document(document),
        })
        write_json_atomic(run_path, run)
    return {"created": str(target), **report}

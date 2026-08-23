from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .generators import refresh_generated
from .metadata import parse_metadata
from .revisions import revision
from .store import RevisionConflict, Store


ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![\w])(?:[A-Za-z]:\\[^\s`]+|/(?:[^\s`/]+/)+[^\s`]+)")
TOKEN_PATTERN = re.compile(r"[a-z0-9]{3,}", re.I)
COMMON_TERMS = {"current", "project", "stage", "status", "search", "hints", "summary", "manual"}
PATH_SUFFIXES = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java", ".kt",
    ".toml", ".json", ".yaml", ".yml", ".md", ".rst", ".txt", ".sh", ".ps1",
    ".service", ".sql", ".html", ".css", ".svg",
}
MAINTENANCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "stage_id": {"type": "string"},
        "action": {"type": "string", "enum": ["update", "no_change"]},
        "body": {"type": "string"},
        "evidence_paths": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
    "required": ["stage_id", "action", "body", "evidence_paths", "rationale"],
    "additionalProperties": False,
}


def _run_git(root: Path, *args: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=12,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()] if result.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired):
        return []


def _git_changes(root: Path) -> list[str]:
    changes = {
        *_run_git(root, "diff", "--name-only", "HEAD"),
        *_run_git(root, "diff", "--name-only", "--cached"),
        *_run_git(root, "diff", "--name-only", "HEAD~1..HEAD"),
    }
    return sorted(changes)


def _body_paths(body: str) -> list[str]:
    values = [raw.rstrip(".,;:)]}") for raw in ABSOLUTE_PATH_PATTERN.findall(body)]
    for raw in re.findall(r"`([^`\n]+)`", body):
        if "/" in raw or "\\" in raw or Path(raw).suffix.lower() in PATH_SUFFIXES:
            values.append(raw.strip())
    return sorted(set(values))


def _resolved_project_path(root: Path, raw: str) -> Path | None:
    candidate = Path(raw)
    candidate = candidate if candidate.is_absolute() else root / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root.resolve())
        return resolved
    except (OSError, ValueError):
        return None


def _verified_date(value: str) -> date | None:
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", value or "")
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def inspect(data_path: Path, max_age_days: int = 30, now: datetime | None = None) -> dict[str, Any]:
    store = Store(data_path)
    data = store.load()
    project_root = data_path.parent.parent
    changes = _git_changes(project_root)
    today = (now or datetime.now(timezone.utc)).date()
    candidates = []
    for current in data.get("currents", []):
        for stage in current.get("stages", []):
            body = str(stage.get("body") or "")
            meta = parse_metadata(body, stage)
            if meta["status"] == "generated" or stage.get("status") == "generated":
                continue
            reasons: list[dict[str, Any]] = []
            missing = []
            for raw in _body_paths(body):
                candidate = _resolved_project_path(project_root, raw)
                if candidate is not None and not candidate.exists():
                    missing.append(raw)
            if missing:
                reasons.append({"kind": "missing_paths", "evidence": missing[:20]})

            stage_text = " ".join([
                str(stage.get("id", "")), str(stage.get("title", "")), meta["search_hints"],
                meta["purpose"], meta["authority"], *list(_body_paths(body)),
            ]).lower()
            terms = set(TOKEN_PATTERN.findall(stage_text)) - COMMON_TERMS
            related = [path for path in changes if terms & set(TOKEN_PATTERN.findall(path.lower()))]
            if related:
                reasons.append({"kind": "related_git_changes", "evidence": related[:30]})

            verified = _verified_date(meta["verified"])
            if verified is None:
                reasons.append({"kind": "missing_verification", "evidence": [meta["verified"] or "not recorded"]})
            else:
                age = (today - verified).days
                if age > max_age_days:
                    reasons.append({"kind": "verification_age", "evidence": [f"{age} days", verified.isoformat()]})
            if reasons:
                candidates.append({
                    "stage_id": stage.get("id"), "title": stage.get("title"),
                    "current": current.get("id"), "status": meta["status"],
                    "verified": meta["verified"], "revision": revision(body),
                    "body": body, "reasons": reasons,
                })
    return {
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "canonical_modified": False,
        "notice": "Evidence-backed maintenance candidates. No LLM decision has been applied yet.",
        "git_changes": changes, "possible_stale_stages": candidates, "patches": [],
    }


def _read_evidence(root: Path, candidate: dict[str, Any], git_changes: list[str]) -> list[dict[str, str]]:
    identifiers: list[str] = []
    for reason in candidate["reasons"]:
        if reason["kind"] == "related_git_changes":
            identifiers.extend(reason["evidence"])
        elif reason["kind"] == "missing_paths":
            identifiers.extend(f"signal:missing:{path}" for path in reason["evidence"])
        elif reason["kind"] in {"verification_age", "missing_verification"}:
            identifiers.append(f"signal:{reason['kind']}")
    identifiers.extend(_body_paths(candidate["body"]))
    if not any(not item.startswith("signal:") for item in identifiers):
        for name in ("README.md", "README.rst", "pyproject.toml", "package.json", "Cargo.toml"):
            if (root / name).is_file():
                identifiers.append(name)
    evidence = [{"id": f"stage:{candidate['stage_id']}", "content": candidate["body"]}]
    seen = {evidence[0]["id"]}
    for identifier in identifiers:
        if identifier in seen or len(evidence) >= 9:
            continue
        seen.add(identifier)
        if identifier.startswith("signal:"):
            evidence.append({"id": identifier, "content": identifier.replace("signal:", "")})
            continue
        path = _resolved_project_path(root, identifier)
        if path is None or not path.is_file() or path.stat().st_size > 300_000:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")[:10000]
        except OSError:
            continue
        evidence.append({"id": path.relative_to(root).as_posix(), "content": content})
    if git_changes:
        evidence.append({"id": "signal:git-change-list", "content": "\n".join(git_changes[:100])})
    return evidence


def _set_verified(body: str, stamp: str) -> str:
    pattern = re.compile(r"^(Verified|最后核验)\s*[:：].*$", re.I | re.M)
    if pattern.search(body):
        return pattern.sub(f"Verified: {stamp}", body, count=1).rstrip() + "\n"
    heading = re.search(r"^# .+$", body, re.M)
    position = heading.end() if heading else 0
    return (body[:position] + f"\n\nVerified: {stamp}" + body[position:]).strip() + "\n"


def maintain_stages(
    data_path: Path,
    client,
    provider: str,
    model: str,
    max_age_days: int = 30,
    actor: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    generated = refresh_generated(data_path)
    review = inspect(data_path, max_age_days=max_age_days, now=now)
    store = Store(data_path)
    root = data_path.parent.parent
    results = []
    for candidate in review["possible_stale_stages"]:
        evidence = _read_evidence(root, candidate, review["git_changes"])
        allowed = {item["id"] for item in evidence}
        prompt = (
            "Maintain exactly one existing Turritopsis Stage. Decide update or no_change. "
            "Use only the evidence blocks below. Preserve a complete Markdown Stage, its headings, and useful metadata. "
            "Do not invent project facts, versions, states, paths, or decisions. If evidence cannot support a factual update, return no_change. "
            "For update, cite at least one supplied evidence id in evidence_paths.\n\n"
            f"CANDIDATE:\n{json.dumps(candidate, ensure_ascii=False)}\n\n"
            f"EVIDENCE BLOCKS:\n{json.dumps(evidence, ensure_ascii=False)}"
        )
        decision = client.complete_json(
            "You are a conservative project-knowledge maintainer. Evidence outranks inference.",
            prompt, MAINTENANCE_SCHEMA, "turritopsis_stage_maintenance",
        )
        if decision["stage_id"] != candidate["stage_id"]:
            raise ValueError(f"LLM returned the wrong Stage id: {decision['stage_id']}")
        unknown = sorted(set(decision["evidence_paths"]) - allowed)
        if unknown:
            raise ValueError(f"LLM cited unknown evidence for {candidate['stage_id']}: {', '.join(unknown)}")
        if decision["action"] == "no_change":
            results.append({"stage_id": candidate["stage_id"], "changed": False,
                            "rationale": decision["rationale"], "evidence_paths": decision["evidence_paths"]})
            continue
        if not decision["body"].strip() or not decision["evidence_paths"]:
            raise ValueError(f"LLM update for {candidate['stage_id']} lacks body or evidence")
        stamp = f"{now.date().isoformat()} by maintain ({provider}/{model})"
        body = _set_verified(decision["body"], stamp)
        try:
            write = store.update_stage(
                candidate["stage_id"], body, "replace", candidate["revision"],
                actor or f"maintain:{provider}/{model}",
            )
            results.append({**write, "rationale": decision["rationale"],
                            "evidence_paths": decision["evidence_paths"]})
        except RevisionConflict as conflict:
            results.append({"stage_id": candidate["stage_id"], "changed": False,
                            "conflict": True, "current_revision": conflict.current})
    report = {
        "provider": provider, "model": model, "generated_refresh": generated,
        "candidates": len(review["possible_stale_stages"]), "results": results,
        "changed": sum(1 for item in results if item.get("changed")),
    }
    audit = {
        "timestamp": now.isoformat(), "provider": provider, "model": model,
        "candidate_reasons": {
            item["stage_id"]: item["reasons"] for item in review["possible_stale_stages"]
        },
        "results": results,
    }
    log_path = data_path.parent / "maintenance.jsonl"
    with log_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(audit, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return report


def write_proposal(data_path: Path, max_age_days: int = 30) -> Path:
    generated = refresh_generated(data_path)
    proposal = inspect(data_path, max_age_days=max_age_days)
    proposal["generated_refresh"] = generated
    directory = data_path.parent / "proposals"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = directory / f"maintain-{stamp}.json"
    target.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def apply_proposal(data_path: Path, proposal_path: Path, actor: str = "maintain") -> list[dict]:
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    patches = proposal.get("patches", [])
    if not patches:
        raise ValueError("Proposal contains no explicit reviewed patches")
    store = Store(data_path)
    return [store.update_stage(
        patch["stage_id"], patch["body"], patch.get("mode", "replace"),
        patch.get("expected_revision"), actor,
    ) for patch in patches]

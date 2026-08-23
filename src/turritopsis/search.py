from __future__ import annotations

import re
from typing import Any

from .metadata import headings, parse_metadata


WEIGHTS = {
    "stage_id": 80,
    "search_hints": 70,
    "title": 60,
    "authority": 50,
    "summary": 40,
    "purpose": 30,
    "status": 25,
    "verified": 25,
    "current": 20,
    "headings": 8,
    "body": 8,
}


def _terms(query: str) -> list[str]:
    return [item.lower() for item in re.split(r"\s+", query.strip()) if item]


def _contains(term: str, text: str) -> bool:
    if re.fullmatch(r"[a-z0-9_+.-]+", term):
        return re.search(rf"(?<![a-z0-9_+.-]){re.escape(term)}(?![a-z0-9_+.-])", text) is not None
    return term in text


def _snippet(text: str, query: str, size: int = 180) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    lower = flat.lower()
    positions = [lower.find(term) for term in _terms(query) if lower.find(term) >= 0]
    start = max(0, (min(positions) if positions else 0) - 50)
    end = min(len(flat), start + size)
    return ("..." if start else "") + flat[start:end] + ("..." if end < len(flat) else "")


def semantic_search(data: dict[str, Any], query: str, current_id: str = "", limit: int = 8):
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")
    phrase = query.lower()
    terms = _terms(query)
    rows = []
    for current in data.get("currents", []):
        if current_id and current.get("id") != current_id:
            continue
        current_text = " ".join(str(current.get(key) or "") for key in ("id", "name", "blurb"))
        for stage in current.get("stages", []):
            body = str(stage.get("body") or "")
            if not body.strip():
                continue
            meta = parse_metadata(body, stage)
            fields = {
                "stage_id": str(stage.get("id") or ""),
                "title": str(stage.get("title") or ""),
                "current": current_text,
                "search_hints": meta["search_hints"],
                "purpose": meta["purpose"],
                "status": meta["status"],
                "verified": meta["verified"],
                "summary": meta["summary"],
                "authority": meta["authority"],
                "headings": "\n".join(headings(body)),
                "body": body,
            }
            score = 0
            reasons = []
            for field, value in fields.items():
                low = value.lower()
                field_score = WEIGHTS[field] * 2 if phrase and phrase in low else 0
                field_score += sum(WEIGHTS[field] for term in terms if _contains(term, low))
                if field_score:
                    score += field_score
                    reasons.append({"field": field, "score": field_score})
            if score:
                source = "\n".join([fields["stage_id"], fields["title"], meta["search_hints"],
                                     meta["purpose"], meta["summary"], body])
                rows.append({
                    "stage_id": stage.get("id"), "title": stage.get("title"),
                    "current": current.get("id"), "score": score,
                    "status": meta["status"], "authority": meta["authority"],
                    "summary": meta["summary"], "matched": reasons,
                    "snippet": _snippet(source, query),
                })
    rows.sort(key=lambda row: (-row["score"], row["stage_id"]))
    return rows[:max(1, min(int(limit), 20))]


def exact_search(data: dict[str, Any], query: str, current_id: str = "", stage_id: str = "",
                 context: int = 2, limit: int = 12, case_sensitive: bool = False):
    if not query:
        raise ValueError("query must not be empty")
    context = max(0, min(int(context), 5))
    limit = max(1, min(int(limit), 30))
    matches = []
    for current in data.get("currents", []):
        if current_id and current.get("id") != current_id:
            continue
        for stage in current.get("stages", []):
            if stage_id and stage.get("id") != stage_id:
                continue
            body = str(stage.get("body") or "")
            meta = parse_metadata(body, stage)
            lines = body.splitlines()
            for index, line in enumerate(lines):
                found = query in line if case_sensitive else query.lower() in line.lower()
                if not found:
                    continue
                heading = "start"
                for prior in reversed(lines[:index + 1]):
                    if prior.lstrip().startswith("#"):
                        heading = prior.lstrip("# ").strip()
                        break
                start, end = max(0, index - context), min(len(lines), index + context + 1)
                matches.append({
                    "stage_id": stage.get("id"), "title": stage.get("title"),
                    "current": current.get("id"), "status": meta["status"],
                    "authority": meta["authority"], "line": index + 1, "heading": heading,
                    "context": [{"line": number + 1, "text": lines[number], "match": number == index}
                                for number in range(start, end)],
                })
                if len(matches) >= limit:
                    return matches
    return matches


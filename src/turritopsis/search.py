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


CJK = "一-鿿぀-ヿ가-힯"
_HAS_CJK = re.compile(f"[{CJK}]")
_SEGMENT = re.compile(f"[{CJK}]+|[^{CJK}\\s]+")
# Chinese function words. A bigram made of two of these carries no signal.
_CJK_STOP = set("的了是在和与及或吗呢吧啊怎什么样哪里有没做过要会能被把给对从到就都还也很更最这那些个之为以于而且但因所如果不")
_ENGLISH_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "can", "could", "did", "do", "does", "doing", "for", "from", "had", "has",
    "have", "having", "how", "if", "in", "into", "is", "it", "its", "may",
    "might", "must", "no", "nor", "not", "of", "on", "or", "our", "should",
    "so", "than", "that", "the", "their", "then", "there", "these", "they",
    "this", "those", "through", "to", "under", "was", "were", "what", "when",
    "where", "which", "while", "who", "why", "will", "with", "would", "you",
    "your",
}


def _cjk_bigrams(segment: str) -> list[str]:
    """Split a run of CJK characters into overlapping bigrams.

    CJK text has no spaces, so whitespace tokenization leaves a whole question
    as one term and nothing ever matches. Bigrams are the standard fallback
    (same approach as Elasticsearch's CJK analyzer) and need no dictionary.
    """
    if len(segment) <= 2:
        return [segment]
    grams = [
        gram
        for index in range(len(segment) - 1)
        if not ((gram := segment[index:index + 2])[0] in _CJK_STOP and gram[1] in _CJK_STOP)
    ]
    return grams or [segment]


def _terms(query: str) -> list[str]:
    terms: list[str] = []
    for item in re.split(r"\s+", query.strip().lower()):
        if not item:
            continue
        if not _HAS_CJK.search(item):
            if item not in _ENGLISH_STOP:
                terms.append(item)
            continue
        for segment in _SEGMENT.findall(item):
            terms.extend(_cjk_bigrams(segment) if _HAS_CJK.match(segment) else [segment])
    return terms


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
    terms = _terms(query)
    ascii_items = [item for item in re.split(r"\s+", query.lower()) if not _HAS_CJK.search(item)]
    # An exact natural-language phrase must not smuggle stop words back into the
    # score after term filtering. Keep the phrase bonus only for signal-only queries.
    phrase = "" if any(item in _ENGLISH_STOP for item in ascii_items) else query.lower()
    rows = []
    for current in data.get("currents", []):
        if current_id and current.get("id") != current_id:
            continue
        current_text = " ".join(str(current.get(key) or "") for key in ("id", "name", "blurb"))
        current_haystack = current_text.lower()
        for stage in current.get("stages", []):
            body = str(stage.get("body") or "")
            if not body.strip():
                continue
            # Every scored field is drawn from body, the stage id/title, or the
            # current. If none of them contain a term, the score is zero anyway —
            # skip the metadata parse instead of paying for it on every stage.
            haystack = "\n".join((
                body, str(stage.get("id") or ""), str(stage.get("title") or ""), current_haystack,
            )).lower()
            if phrase not in haystack and not any(_contains(term, haystack) for term in terms):
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


from __future__ import annotations

import re
from typing import Any


FIELD_ALIASES = {
    "purpose": ("Purpose", "用途"),
    "search_hints": ("Search hints", "适合检索"),
    "summary": ("Summary", "一句话概括"),
    "verified": ("Verified", "最后核验"),
    "status": ("Status", "当前性"),
    "authority": ("Authority", "权威范围"),
}


# Aliases are constant, so compile once at import instead of per line per stage.
_FIELD_PATTERNS = {
    key: re.compile(rf"^(?:{'|'.join(re.escape(name) for name in names)})\s*[:：]\s*(.*)$", re.I)
    for key, names in FIELD_ALIASES.items()
}
_ANY_FIELD = re.compile(
    rf"^(?:{'|'.join(re.escape(name) for names in FIELD_ALIASES.values() for name in names)})\s*[:：]",
    re.I,
)
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")


def _field(body: str, pattern: re.Pattern[str]) -> str:
    for line in (body or "").splitlines():
        if match := pattern.match(line.strip()):
            return match.group(1).strip()
    return ""


def headings(body: str) -> list[str]:
    return [m.group(1).strip() for line in (body or "").splitlines()
            if (m := _HEADING.match(line.strip()))]


def parse_metadata(body: str, stage: dict[str, Any] | None = None) -> dict[str, str]:
    stage = stage or {}
    result = {key: str(stage.get(key) or _field(body, pattern))
              for key, pattern in _FIELD_PATTERNS.items()}
    if not result["summary"]:
        for line in (body or "").splitlines():
            text = line.strip()
            if text and not text.startswith("#") and not _ANY_FIELD.match(text):
                result["summary"] = text[:240]
                break
    result["status"] = (result["status"] or "current").lower()
    return result


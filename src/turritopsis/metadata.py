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


def _field(body: str, names: tuple[str, ...]) -> str:
    for line in (body or "").splitlines():
        stripped = line.strip()
        for name in names:
            match = re.match(rf"^{re.escape(name)}\s*[:：]\s*(.*)$", stripped, re.I)
            if match:
                return match.group(1).strip()
    return ""


def headings(body: str) -> list[str]:
    return [m.group(1).strip() for line in (body or "").splitlines()
            if (m := re.match(r"^#{1,6}\s+(.+?)\s*$", line.strip()))]


def parse_metadata(body: str, stage: dict[str, Any] | None = None) -> dict[str, str]:
    stage = stage or {}
    result = {key: str(stage.get(key) or _field(body, aliases))
              for key, aliases in FIELD_ALIASES.items()}
    if not result["summary"]:
        for line in (body or "").splitlines():
            text = line.strip()
            if text and not text.startswith("#") and not any(
                re.match(rf"^{re.escape(name)}\s*[:：]", text, re.I)
                for aliases in FIELD_ALIASES.values() for name in aliases
            ):
                result["summary"] = text[:240]
                break
    result["status"] = (result["status"] or "current").lower()
    return result


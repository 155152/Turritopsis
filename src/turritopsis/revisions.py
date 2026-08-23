from __future__ import annotations

import hashlib


def revision(body: str) -> str:
    """Return a stable, stage-local revision for a Markdown body."""
    return hashlib.sha256((body or "").encode("utf-8")).hexdigest()[:16]


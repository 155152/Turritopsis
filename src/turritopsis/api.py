from __future__ import annotations

from typing import Any

from .metadata import parse_metadata
from .revisions import revision
from .search import exact_search, semantic_search
from .store import RevisionConflict, Store


class Turritopsis:
    def __init__(self, data_path):
        self.store = Store(data_path)

    def list_stages(self, current: str = "") -> dict[str, Any]:
        data = self.store.load()
        if not current:
            return {
                "title": data.get("title", "Turritopsis"),
                "subtitle": data.get("subtitle", ""),
                "currents": [{
                    "id": item.get("id"), "name": item.get("name"),
                    "blurb": item.get("blurb", ""), "glyph": item.get("glyph", ""),
                    "stage_count": len(item.get("stages", [])),
                } for item in data.get("currents", [])],
            }
        current_obj = self.store.find_current(data, current)
        if not current_obj:
            raise KeyError(f"Unknown current: {current}")
        stages = []
        for stage in current_obj.get("stages", []):
            body = str(stage.get("body") or "")
            meta = parse_metadata(body, stage)
            stages.append({
                "stage_id": stage.get("id"), "title": stage.get("title"),
                "status": meta["status"], "authority": meta["authority"],
                "summary": meta["summary"], "empty": not bool(body.strip()),
                "revision": revision(body),
            })
        return {"current": {key: current_obj.get(key, "") for key in ("id", "name", "blurb", "glyph")},
                "stages": stages}

    def search_stages(self, query: str, match: str = "semantic", current: str = "",
                      stage_id: str = "", context: int = 2, limit: int = 8,
                      case_sensitive: bool = False) -> dict[str, Any]:
        data = self.store.load()
        if current and not self.store.find_current(data, current):
            raise KeyError(f"Unknown current: {current}")
        match = match.lower().strip()
        if match == "semantic":
            if stage_id:
                raise ValueError("stage_id is only supported for exact search")
            results = semantic_search(data, query, current, limit)
        elif match == "exact":
            results = exact_search(data, query, current, stage_id, context, limit, case_sensitive)
        else:
            raise ValueError("match must be semantic or exact")
        return {"query": query, "match": match, "count": len(results), "results": results}

    def get_stage(self, stage_id: str) -> dict[str, Any]:
        data = self.store.load()
        current, stage = self.store.find_stage(data, stage_id)
        if not stage:
            raise KeyError(f"Unknown stage: {stage_id}")
        body = str(stage.get("body") or "")
        return {
            "current": {"id": current.get("id"), "name": current.get("name")},
            "stage_id": stage.get("id"), "title": stage.get("title"),
            "revision": revision(body), "metadata": parse_metadata(body, stage), "body": body,
        }

    def update_stage(self, stage_id: str, body: str, mode: str = "replace",
                     expected_revision: str = "", actor: str = "agent", reason: str = "",
                     verification: list[str] | None = None, commit: str = "") -> dict[str, Any]:
        try:
            result = self.store.update_stage(
                stage_id, body, mode, expected_revision or None, actor,
                reason=reason, verification=verification, commit=commit,
            )
            return {"ok": True, **result}
        except RevisionConflict as conflict:
            current_stage = self.get_stage(stage_id)
            return {
                "ok": False, "conflict": True,
                "requested_revision": conflict.requested,
                "current_revision": conflict.current,
                "current_stage": current_stage,
            }


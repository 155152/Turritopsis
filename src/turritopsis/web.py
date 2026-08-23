from __future__ import annotations

import hashlib
import json
import os
import tempfile
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from .api import Turritopsis
from .maintain import apply_proposal


ASSETS = files("turritopsis.web_assets")


def _project_revision(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _proposal_path(service: Turritopsis, name: str) -> Path:
    decoded = unquote(name)
    if decoded != Path(decoded).name or not decoded.endswith(".json"):
        raise ValueError("invalid proposal name")
    path = service.store.root / "proposals" / decoded
    if not path.is_file():
        raise FileNotFoundError(f"proposal not found: {decoded}")
    return path


def _read_proposals(service: Turritopsis) -> list[dict[str, Any]]:
    directory = service.store.root / "proposals"
    rows = []
    if not directory.is_dir():
        return rows
    for path in sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        status = document.get("review_status", "pending")
        rows.append({
            "name": path.name, "status": status,
            "generated_at": document.get("generated_at", ""),
            "notice": document.get("notice", ""),
            "stale_count": len(document.get("possible_stale_stages", [])),
            "patch_count": len(document.get("patches", [])),
            "suggestion_count": len(document.get("suggested_stages", [])),
        })
    return rows


def _stale_map(service: Turritopsis) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for proposal in _read_proposals(service):
        if proposal["status"] != "pending":
            continue
        try:
            document = json.loads(_proposal_path(service, proposal["name"]).read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        for candidate in document.get("possible_stale_stages", []):
            result.setdefault(candidate.get("stage_id", ""), []).extend(candidate.get("reasons", []))
    return result


def _history(service: Turritopsis) -> list[dict[str, Any]]:
    path = service.store.root / "changelog.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    rows.reverse()
    for index, row in enumerate(rows):
        row["index"] = index
    return rows


def _last_changes(service: Turritopsis) -> dict[str, dict[str, Any]]:
    result = {}
    for row in _history(service):
        result.setdefault(row.get("stage_id", ""), row)
    return result


async def project_map(request: Request) -> Response:
    service: Turritopsis = request.app.state.service
    overview = service.list_stages()
    stale = _stale_map(service)
    changes = _last_changes(service)
    authority = []
    handoff = None
    currents = []
    for current in overview["currents"]:
        detail = service.list_stages(current["id"])
        for stage in detail["stages"]:
            stage["stale_reasons"] = stale.get(stage["stage_id"], [])
            stage["last_change"] = changes.get(stage["stage_id"])
            if stage["authority"]:
                authority.append({"authority": stage["authority"], "stage_id": stage["stage_id"],
                                  "title": stage["title"], "current": current["id"]})
                if handoff is None and "current work" in stage["authority"].lower():
                    handoff = {"stage_id": stage["stage_id"], "title": stage["title"],
                               "summary": stage["summary"], "current": current["id"]}
        currents.append({**current, "stages": detail["stages"]})
    proposals = _read_proposals(service)
    pending = [item for item in proposals if item["status"] == "pending"]
    return JSONResponse({
        "title": overview["title"], "subtitle": overview["subtitle"],
        "revision": _project_revision(service.store.path),
        "updated_at": service.store.path.stat().st_mtime,
        "counts": {"stale": len(stale), "conflicts": 0, "proposals": len(pending)},
        "currents": currents, "authority": authority, "handoff": handoff,
    })


async def search(request: Request) -> Response:
    params = request.query_params
    result = request.app.state.service.search_stages(
        params.get("q", ""), params.get("match", "semantic"), params.get("current", ""),
        params.get("stage_id", ""), int(params.get("context", "2")), int(params.get("limit", "20")),
        params.get("case_sensitive", "false").lower() == "true",
    )
    return JSONResponse(result)


async def stage_detail(request: Request) -> Response:
    service: Turritopsis = request.app.state.service
    stage_id = unquote(request.path_params["stage_id"])
    result = service.get_stage(stage_id)
    siblings = service.list_stages(result["current"]["id"])["stages"]
    result["siblings"] = siblings
    result["stale_reasons"] = _stale_map(service).get(stage_id, [])
    result["last_change"] = _last_changes(service).get(stage_id)
    return JSONResponse(result)


async def update_stage(request: Request) -> Response:
    service: Turritopsis = request.app.state.service
    stage_id = unquote(request.path_params["stage_id"])
    payload = await request.json()
    result = service.update_stage(
        stage_id, str(payload.get("body", "")), payload.get("mode", "replace"),
        payload.get("expected_revision", ""), payload.get("actor", "human-web-ui"),
    )
    return JSONResponse(result, status_code=409 if result.get("conflict") else 200)


async def history(request: Request) -> Response:
    return JSONResponse({"entries": _history(request.app.state.service)})


async def history_detail(request: Request) -> Response:
    service: Turritopsis = request.app.state.service
    index = int(request.path_params["index"])
    entries = _history(service)
    if index < 0 or index >= len(entries):
        raise KeyError("history entry not found")
    row = entries[index]
    before_body = None
    backup = row.get("backup")
    if backup:
        path = service.store.root / backup
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            _, stage = service.store.find_stage(data, row.get("stage_id", ""))
            before_body = stage.get("body", "") if stage else None
    current = service.get_stage(row["stage_id"])
    after_body = current["body"] if current["revision"] == row.get("after_revision") else None
    return JSONResponse({"entry": row, "before_body": before_body, "after_body": after_body})


async def proposals(request: Request) -> Response:
    return JSONResponse({"proposals": _read_proposals(request.app.state.service)})


async def proposal_detail(request: Request) -> Response:
    service: Turritopsis = request.app.state.service
    path = _proposal_path(service, request.path_params["name"])
    return JSONResponse({"name": path.name, "document": json.loads(path.read_text(encoding="utf-8"))})


def _atomic_json(path: Path, document: dict[str, Any]) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=".proposal-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


async def proposal_action(request: Request) -> Response:
    service: Turritopsis = request.app.state.service
    path = _proposal_path(service, request.path_params["name"])
    payload = await request.json()
    action = payload.get("action")
    document = payload.get("document") or json.loads(path.read_text(encoding="utf-8"))
    if action == "reject":
        document["review_status"] = "rejected"
        document["review_note"] = payload.get("note", "")
        _atomic_json(path, document)
        return JSONResponse({"ok": True, "status": "rejected"})
    if action == "unresolved":
        document["review_status"] = "unresolved"
        document["review_note"] = payload.get("note", "")
        _atomic_json(path, document)
        return JSONResponse({"ok": True, "status": "unresolved"})
    if action == "apply":
        _atomic_json(path, document)
        applied = apply_proposal(service.store.path, path, "human-web-ui")
        document["review_status"] = "applied"
        document["applied_results"] = applied
        _atomic_json(path, document)
        return JSONResponse({"ok": True, "status": "applied", "results": applied})
    raise ValueError("action must be apply, reject, or unresolved")


async def asset(request: Request) -> Response:
    name = request.path_params.get("name") or "index.html"
    if name not in {"index.html", "styles.css", "app.js", "icons.svg"}:
        return Response(status_code=404)
    resource = ASSETS.joinpath(name)
    media = {
        "index.html": "text/html", "styles.css": "text/css",
        "app.js": "text/javascript", "icons.svg": "image/svg+xml",
    }[name]
    return Response(resource.read_bytes(), media_type=media)


async def api_error(request: Request, exc: Exception) -> Response:
    status = 404 if isinstance(exc, (KeyError, FileNotFoundError)) else 400
    return JSONResponse({"error": str(exc).strip("'\"")}, status_code=status)


def web_routes() -> list[Route]:
    return [
        Route("/", asset, methods=["GET"]),
        Route("/assets/{name:str}", asset, methods=["GET"]),
        Route("/api/project", project_map, methods=["GET"]),
        Route("/api/search", search, methods=["GET"]),
        Route("/api/stages/{stage_id:path}", stage_detail, methods=["GET"]),
        Route("/api/stages/{stage_id:path}", update_stage, methods=["PUT"]),
        Route("/api/history", history, methods=["GET"]),
        Route("/api/history/{index:int}", history_detail, methods=["GET"]),
        Route("/api/proposals", proposals, methods=["GET"]),
        Route("/api/proposals/{name:str}", proposal_detail, methods=["GET"]),
        Route("/api/proposals/{name:str}", proposal_action, methods=["POST"]),
    ]


def attach_web(mcp_app: Starlette, service: Turritopsis) -> Starlette:
    mcp_app.state.service = service
    for route in reversed(web_routes()):
        mcp_app.router.routes.insert(0, route)
    mcp_app.add_exception_handler(KeyError, api_error)
    mcp_app.add_exception_handler(ValueError, api_error)
    mcp_app.add_exception_handler(FileNotFoundError, api_error)
    return mcp_app

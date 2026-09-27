from __future__ import annotations

import json
from pathlib import Path

from starlette.testclient import TestClient

from turritopsis.api import Turritopsis
from turritopsis.server import create_http_app
import turritopsis.server as server_module


def test_web_project_map_and_assets_share_canonical_store(data_path):
    app = create_http_app(data_path)
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Project Map" in page.text and "/assets/app.js" in page.text
        styles = client.get("/assets/styles.css")
        assert styles.status_code == 200
        icons = client.get("/assets/icons.svg")
        assert icons.status_code == 200
        assert icons.headers["content-type"].startswith("image/svg+xml")
        assert icons.text.count("<symbol ") == 16
        assert "brand-mark" not in page.text
        assert "brand-mark" not in styles.text
        assert 'href="#zodiac-aquarius"' in page.text
        project = client.get("/api/project").json()
        assert project["title"] == "Long Project"
        assert project["handoff"]["stage_id"] == "project.handoff"
        assert project["authority"][0]["authority"] == "current work, next action"
        assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)


def test_http_app_constructs_one_shared_turritopsis(data_path, monkeypatch):
    constructed = []
    real_service = server_module.Turritopsis

    class CountingTurritopsis(real_service):
        def __init__(self, path):
            constructed.append(path)
            super().__init__(path)

    monkeypatch.setattr(server_module, "Turritopsis", CountingTurritopsis)
    create_http_app(data_path)
    assert constructed == [data_path]


def test_proposal_action_does_not_shadow_browser_document():
    asset = Path(__file__).parents[1] / "src" / "turritopsis" / "web_assets" / "app.js"
    script = asset.read_text(encoding="utf-8")
    assert 'const doc=JSON.parse(document.querySelector("#proposal-json").value)' in script
    assert "const document=JSON.parse(document.querySelector" not in script


def test_public_demo_contains_only_placeholder_project_identity():
    demo = Path(__file__).parents[1] / "examples" / "demo" / ".turritopsis" / "stages.json"
    content = demo.read_text(encoding="utf-8")
    assert '"title": "Your Project"' in content
    assert "simdwell" not in content.lower()


def test_web_search_and_stage_reader_use_same_core(data_path):
    core = Turritopsis(data_path)
    expected = core.search_stages("release frozen")["results"]
    with TestClient(create_http_app(data_path)) as client:
        ranked = client.get("/api/search", params={"q": "release frozen", "match": "semantic"}).json()
        assert [row["stage_id"] for row in ranked["results"]] == [row["stage_id"] for row in expected]
        exact = client.get("/api/search", params={"q": "E_OLD", "match": "exact"}).json()
        assert exact["results"][0]["line"] > 1
        stage = client.get("/api/stages/project.handoff").json()
        assert stage["body"] == core.get_stage("project.handoff")["body"]
        assert len(stage["siblings"]) == 2


def test_web_history_returns_optional_engineering_change_context(data_path):
    core = Turritopsis(data_path)
    current = core.get_stage("project.handoff")
    with TestClient(create_http_app(data_path)) as client:
        response = client.put("/api/stages/project.handoff", json={
            "body": "# Accepted runtime state\n", "expected_revision": current["revision"],
            "actor": "human-web-ui", "reason": "runtime acceptance changed the durable state",
            "verification": ["manual acceptance passed"], "commit": "cafebabe",
        })
        assert response.status_code == 200
        history = client.get("/api/history").json()["entries"]
        assert len(history) == 1
        assert history[0]["reason"] == "runtime acceptance changed the durable state"
        assert history[0]["verification"] == ["manual acceptance passed"]
        assert history[0]["commit"] == "cafebabe"
        detail = client.get("/api/history/0").json()["entry"]
        assert detail["reason"] == history[0]["reason"]


def test_web_editor_returns_revision_conflict_without_overwrite(data_path):
    core = Turritopsis(data_path)
    stale = core.get_stage("project.handoff")["revision"]
    core.update_stage("project.handoff", "Agent changed this.", expected_revision=stale, actor="agent")
    with TestClient(create_http_app(data_path)) as client:
        response = client.put("/api/stages/project.handoff", json={
            "body": "Human draft.", "expected_revision": stale, "actor": "human-web-ui",
        })
        assert response.status_code == 409
        conflict = response.json()
        assert conflict["conflict"] is True
        assert conflict["current_stage"]["body"] == "Agent changed this."
        assert core.get_stage("project.handoff")["body"] == "Agent changed this."


def test_proposal_review_apply_and_reject(data_path):
    core = Turritopsis(data_path)
    proposal_dir = data_path.parent / "proposals"
    proposal_dir.mkdir()
    current = core.get_stage("project.handoff")
    apply_path = proposal_dir / "maintain-apply.json"
    apply_path.write_text(json.dumps({
        "generated_at": "2026-08-24T00:00:00Z", "patches": [{
            "stage_id": "project.handoff", "body": "Reviewed truth.",
            "expected_revision": current["revision"], "mode": "replace",
        }]
    }), encoding="utf-8")
    reject_path = proposal_dir / "scan-reject.json"
    reject_path.write_text(json.dumps({"generated_at": "2026-08-24T00:00:00Z", "patches": []}), encoding="utf-8")

    with TestClient(create_http_app(data_path)) as client:
        listing = client.get("/api/proposals").json()["proposals"]
        assert len(listing) == 2
        applied = client.post("/api/proposals/maintain-apply.json", json={"action": "apply"})
        assert applied.status_code == 200 and applied.json()["status"] == "applied"
        assert core.get_stage("project.handoff")["body"] == "Reviewed truth."
        rejected = client.post("/api/proposals/scan-reject.json", json={"action": "reject", "note": "Not relevant"})
        assert rejected.json()["status"] == "rejected"
        assert json.loads(reject_path.read_text(encoding="utf-8"))["review_status"] == "rejected"

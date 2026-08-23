from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from turritopsis.api import Turritopsis


def test_list_is_map_first_and_exposes_authority(data_path):
    api = Turritopsis(data_path)
    overview = api.list_stages()
    assert overview["currents"][0]["stage_count"] == 2
    assert "body" not in json.dumps(overview)
    stages = api.list_stages("project")["stages"]
    assert stages[0]["authority"] == "current work, next action"
    assert "body" not in stages[0]


def test_semantic_weighting_and_exact_context(data_path):
    api = Turritopsis(data_path)
    results = api.search_stages("release frozen")["results"]
    assert results[0]["stage_id"] == "project.handoff"
    assert results[0]["matched"][0]["field"] in {"search_hints", "summary", "body"}
    exact = api.search_stages("E_OLD", match="exact", context=1)["results"][0]
    assert exact["stage_id"] == "project.timeline"
    assert exact["line"] > 1 and exact["heading"] == "2025"


def test_get_is_complete_and_update_logs_backup(data_path):
    api = Turritopsis(data_path)
    before = api.get_stage("project.handoff")
    assert "Run the hardware regression" in before["body"]
    result = api.update_stage("project.handoff", "Added evidence.", "append", before["revision"], "codex")
    assert result["ok"] and result["changed"]
    assert "Added evidence." in api.get_stage("project.handoff")["body"]
    assert list((data_path.parent / "backups").glob("stages-*.json"))
    assert json.loads(data_path.read_text(encoding="utf-8"))["version"] == 2
    log = json.loads((data_path.parent / "changelog.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert log["actor"] == "codex" and log["stage_id"] == "project.handoff"


def test_same_stage_conflict_different_stage_updates_succeed(data_path):
    api = Turritopsis(data_path)
    stale = api.get_stage("project.handoff")["revision"]
    assert api.update_stage("project.handoff", "first", expected_revision=stale)["ok"]
    conflict = api.update_stage("project.handoff", "second", expected_revision=stale)
    assert conflict["conflict"] and conflict["current_stage"]["body"] == "first"

    revisions = {sid: api.get_stage(sid)["revision"] for sid in ("project.handoff", "project.timeline")}
    def update(sid):
        return api.update_stage(sid, f"updated {sid}", expected_revision=revisions[sid])

    with ThreadPoolExecutor(max_workers=len(revisions)) as executor:
        results = list(executor.map(update, revisions))
    assert len(results) == 2 and all(item["ok"] for item in results)


def test_many_concurrent_writes_are_serialized_without_lock_errors(data_path):
    api = Turritopsis(data_path)
    stage_ids = ["project.handoff", "project.timeline"]

    def update(index):
        stage_id = stage_ids[index % len(stage_ids)]
        return api.update_stage(
            stage_id, f"concurrent write {index}", mode="append", actor="concurrency-test",
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(update, range(20)))
    assert len(results) == 20 and all(item["ok"] for item in results)
    combined = "\n".join(api.get_stage(stage_id)["body"] for stage_id in stage_ids)
    assert all(f"concurrent write {index}" in combined for index in range(20))

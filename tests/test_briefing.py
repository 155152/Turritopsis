from __future__ import annotations

import json
from pathlib import Path

import pytest

from turritopsis.briefing import build_briefing, read_handoff


def _skeleton_stage(current_id: str) -> dict:
    return {
        "id": f"{current_id}.overview", "title": f"{current_id} overview",
        "body": (f"# {current_id}\n\nPurpose: route.\nSearch hints: x\n"
                 "Summary: [Placeholder: verify this.]\nVerified: not yet verified\n"
                 "Status: unresolved\nAuthority: a\n"),
    }


@pytest.fixture
def scanned_project() -> dict:
    return {"title": "Svc", "currents": [
        {"id": "storage", "name": "Storage", "blurb": "b", "stages": [_skeleton_stage("storage")]},
        {"id": "gateway", "name": "Gateway", "blurb": "b", "stages": [
            {"id": "gateway.routes", "title": "Routes",
             "body": "# Routes\n\nSummary: Requests enter through app.py.\nVerified: 2026-08-24 by agent\nStatus: current\n"},
        ]},
        {"id": "genesis", "name": "Why", "blurb": "b", "stages": [_skeleton_stage("genesis")]},
        {"id": "bounds", "name": "Bounds", "blurb": "b", "stages": [_skeleton_stage("bounds")]},
    ]}


def test_work_is_split_by_who_can_actually_answer(scanned_project):
    briefing = build_briefing(scanned_project, {"findings": []})
    self_serve = {item["stage_id"] for item in briefing["self_serve"]}
    ask = {item["stage_id"] for item in briefing["ask_a_human"]}
    assert self_serve == {"storage.overview"}
    assert ask == {"genesis.overview", "bounds.overview"}
    # A Stage that is already verified is neither.
    assert "gateway.routes" not in self_serve | ask
    assert briefing["progress"] == {"stages": 4, "filled": 1, "remaining": 3}


def test_questions_carry_the_evidence_that_produced_them(scanned_project):
    anomalies = {"findings": [{
        "kind": "constant_forked",
        "summary": "COLLECTION is defined in 2 modules with 2 divergent values",
        "evidence": {"name": "COLLECTION", "definitions": {
            "reader.py": "'shadows_v4'", "writer.py": "'shadows'"}},
    }]}
    question = build_briefing(scanned_project, anomalies)["questions"][0]
    assert "COLLECTION" in question["question"]
    assert "reader.py ('shadows_v4')" in question["question"]
    assert "authoritative" in question["question"]
    # The human supplies judgement, not lookup: the finding travels with the ask.
    assert question["evidence"]["definitions"]["writer.py"] == "'shadows'"


def test_empty_human_only_currents_generate_their_own_questions(scanned_project):
    questions = build_briefing(scanned_project, {"findings": []})["questions"]
    texts = " ".join(item["question"] for item in questions)
    assert "rejected" in texts          # genesis
    assert "must not be deleted" in texts  # bounds
    assert all(item["source"] == "empty_current" for item in questions)


def test_a_filled_human_current_stops_being_asked_about(scanned_project):
    scanned_project["currents"][2]["stages"][0]["body"] = (
        "# Why\n\nSummary: Chose SQLite over Postgres for single-file backups.\n"
        "Verified: 2026-08-24 by an\nStatus: current\n")
    briefing = build_briefing(scanned_project, {"findings": []})
    assert "genesis.overview" not in {item["stage_id"] for item in briefing["ask_a_human"]}
    assert "rejected" not in " ".join(item["question"] for item in briefing["questions"])


def test_operations_is_self_serve_and_missing_verification_is_not_settled():
    data = {"currents": [{"id": "operations", "stages": [{
        "id": "operations.deploy", "title": "Deploy",
        "body": "# Deploy\n\nSummary: Run deploy.py.\nStatus: current\n",
    }]}]}
    briefing = build_briefing(data, {"findings": []})
    assert briefing["self_serve"] == [{
        "stage_id": "operations.deploy", "title": "Deploy", "state": "unverified"}]
    assert briefing["progress"]["filled"] == 0


def test_handoff_is_authoritative_about_intent_but_not_about_code(scanned_project, tmp_path):
    briefing = build_briefing(scanned_project, {"findings": []}, handoff="We froze the v2 migration.")
    assert briefing["human_handoff"]["text"] == "We froze the v2 migration."
    assert "can still be out of date" in briefing["human_handoff"]["note"]
    assert "drop any question it already answers" in briefing["how_to_use"]


def test_briefing_tells_the_agent_not_to_re_derive_settled_work(scanned_project):
    briefing = build_briefing(scanned_project, {"findings": [{"kind": "import_cycle", "summary": "a -> b -> a"}]})
    settled = briefing["settled_do_not_re_derive"]
    assert "scan-evidence.json" in settled["structure"]
    assert "leads to confirm, never facts" in settled["anomalies"]
    assert "never ask a person a question the code answers" in briefing["how_to_use"]


def test_handoff_is_picked_up_from_the_conventional_locations(tmp_path):
    assert read_handoff(tmp_path) == ""
    (tmp_path / "HANDOFF.md").write_text("Start with the queue worker.\n", encoding="utf-8")
    assert "queue worker" in read_handoff(tmp_path)

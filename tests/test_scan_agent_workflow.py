from __future__ import annotations

import json
from pathlib import Path

import pytest

from turritopsis.scan_run import _capacity_estimate, run_local_scan
from turritopsis.skeletons import apply_skeleton, validate_skeleton


def _project(root: Path) -> None:
    (root / "src").mkdir()
    (root / "README.md").write_text("# Orders\nSubmit orders over HTTP.", encoding="utf-8")
    (root / "src" / "orders.py").write_text("def submit(order):\n    return order\n", encoding="utf-8")


def _skeleton(**stage_changes):
    stage = {
        "id": "orders.submit_flow",
        "title": "How an order reaches a terminal state",
        "type": "flow",
        "freshness": "steady",
        "purpose": "Route questions about order submission.",
        "search_hints": "order submit request retry terminal",
        "authority": "Order submission lifecycle; excludes deployment.",
        "evidence_paths": ["README.md", "src/orders.py"],
        "update_triggers": ["Order states or worker ownership change"],
    }
    stage.update(stage_changes)
    return {
        "classification_provenance": {
            "source": "installed-agent", "agent_self_reported": "codex", "created_at": "2026-08-24T00:00:00Z"
        },
        "currents": [{
            "id": "orders", "name": "Order lifecycle", "blurb": "How orders move",
            "stages": [stage],
        }],
    }


def test_scan_resumes_from_evidence_without_scanning_again(tmp_path, monkeypatch):
    _project(tmp_path)
    first = run_local_scan(tmp_path)
    evidence_path = Path(first["evidence"])
    before = evidence_path.stat().st_mtime_ns

    def forbidden(_root):
        raise AssertionError("repository was scanned twice")

    monkeypatch.setattr("turritopsis.scan_run.scan_project", forbidden)
    second = run_local_scan(tmp_path)
    assert second["resumed"] is True
    assert evidence_path.stat().st_mtime_ns == before


def test_scan_run_records_local_agent_provenance_and_coverage(tmp_path):
    _project(tmp_path)
    result = run_local_scan(tmp_path, agent="codex")
    run = json.loads(Path(result["scan_run"]).read_text(encoding="utf-8"))
    assert run["mode"] == "installed-agent"
    assert run["agent"] == "codex"
    assert run["classification_source"] == "pending-installed-agent"
    assert run["coverage"]["tree_files"] >= 2
    assert len(run["evidence_sha256"]) == 64
    assert run["stage_capacity_estimate"]["typical_stage_count"] == 14
    assert "预计每个 Stage" in result["capacity_hint"]


def test_scan_warns_when_file_tree_is_truncated(tmp_path, monkeypatch):
    for index in range(5):
        (tmp_path / f"file-{index}.py").write_text(
            f"def function_{index}():\n    return {index}\n", encoding="utf-8"
        )
    monkeypatch.setattr("turritopsis.init_scan.MAX_TREE_FILES", 3)
    result = run_local_scan(tmp_path)
    run = json.loads(Path(result["scan_run"]).read_text(encoding="utf-8"))
    assert run["coverage"]["tree_files"] == 3
    assert any(
        "omitted 2 eligible files" in warning
        and "3-file limit" in warning
        and "lexicographic path order" in warning
        for warning in run["warnings"]
    )


def test_scan_warns_for_material_and_structure_budgets(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("R" * 100, encoding="utf-8")
    (tmp_path / "docs" / "design.md").write_text("D" * 100, encoding="utf-8")
    (tmp_path / "service.py").write_text(
        "def start_service(configuration):\n    return configuration\n", encoding="utf-8"
    )
    monkeypatch.setattr("turritopsis.init_scan.MAX_MATERIALS", 1)
    monkeypatch.setattr("turritopsis.init_scan.MAX_FILE_CHARS", 10)
    monkeypatch.setattr("turritopsis.init_scan.MAX_TOTAL_CHARS", 10)
    result = run_local_scan(tmp_path)
    run = json.loads(Path(result["scan_run"]).read_text(encoding="utf-8"))
    assert any("Material evidence truncated" in warning for warning in run["warnings"])
    assert any("Material contents truncated" in warning for warning in run["warnings"])
    assert any("Structure map truncated" in warning for warning in run["warnings"])


def test_large_project_capacity_hint_uses_approximately_150_files_per_stage():
    estimate = _capacity_estimate({"structure_coverage": {"code_files_found": 2122}})
    assert estimate == {
        "code_files_found": 2122,
        "typical_stage_count": 14,
        "estimated_files_per_stage": 150,
        "guidance": "<=5 detail-rich; 10-30 comfortable; >=100 map-only",
    }


@pytest.mark.parametrize("changes, message", [
    ({"evidence_paths": ["invented.py"]}, "absent from scan-evidence"),
    ({"title": ""}, "title must be a non-empty string"),
    ({"type": "directory"}, "type must be one of"),
    ({"freshness": "sometimes"}, "freshness must be one of"),
    ({"update_triggers": []}, "update_triggers must be a non-empty"),
])
def test_apply_skeleton_rejects_untrustworthy_stage_shapes(tmp_path, changes, message):
    _project(tmp_path)
    run_local_scan(tmp_path)
    evidence = json.loads((tmp_path / ".turritopsis" / "scan-evidence.json").read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match=message):
        validate_skeleton(_skeleton(**changes), evidence)


def test_duplicate_authority_is_rejected(tmp_path):
    _project(tmp_path)
    run_local_scan(tmp_path)
    evidence = json.loads((tmp_path / ".turritopsis" / "scan-evidence.json").read_text(encoding="utf-8"))
    document = _skeleton()
    duplicate = dict(document["currents"][0]["stages"][0])
    duplicate.update({"id": "orders.retry_flow", "title": "How retries terminate"})
    document["currents"][0]["stages"].append(duplicate)
    with pytest.raises(ValueError, match="duplicate Authority"):
        validate_skeleton(document, evidence)


def test_apply_updates_scan_run_after_atomic_stage_creation(tmp_path):
    _project(tmp_path)
    run_local_scan(tmp_path)
    skeleton = tmp_path / "skeleton.json"
    skeleton.write_text(json.dumps(_skeleton()), encoding="utf-8")
    result = apply_skeleton(tmp_path, skeleton)
    assert result["stages"] == 1
    run = json.loads((tmp_path / ".turritopsis" / "scan-run.json").read_text(encoding="utf-8"))
    assert run["state"] == "skeleton_applied"
    assert run["classification_source"] == "installed-agent"
    assert run["classification_agent_self_reported"] == "codex"
    with pytest.raises(FileExistsError, match="never overwrites"):
        apply_skeleton(tmp_path, skeleton)


def test_schema_rejects_fields_the_contract_does_not_own(tmp_path):
    _project(tmp_path)
    run_local_scan(tmp_path)
    evidence = json.loads((tmp_path / ".turritopsis" / "scan-evidence.json").read_text(encoding="utf-8"))
    document = _skeleton()
    document["currents"][0]["stages"][0]["body"] = "Agent-authored canonical truth"
    with pytest.raises(ValueError, match="unsupported fields: body"):
        validate_skeleton(document, evidence)

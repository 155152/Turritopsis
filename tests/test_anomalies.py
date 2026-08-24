from __future__ import annotations

import json
from pathlib import Path

import pytest

from turritopsis.cli import main
from turritopsis.anomalies import _cycles
from turritopsis.init_scan import scan_anomalies


def _kinds(report):
    return {item["kind"] for item in report["findings"]}


def _of_kind(report, kind):
    return [item for item in report["findings"] if item["kind"] == kind]


def test_legacy_module_on_the_main_path_is_reported(tmp_path):
    (tmp_path / "old_core.py").write_text(
        '"""Legacy adapter. Do not use in new code."""\n\n\ndef read():\n    return 1\n',
        encoding="utf-8")
    for index in range(6):
        (tmp_path / f"caller{index}.py").write_text("import old_core\n", encoding="utf-8")
    report = scan_anomalies(tmp_path)
    finding = _of_kind(report, "legacy_still_load_bearing")[0]
    assert finding["evidence"]["path"] == "old_core.py"
    assert finding["evidence"]["importers"] >= 5


def test_forked_constant_is_reported_only_when_the_values_share_an_ancestor(tmp_path):
    # One resource that grew a second version: a real fork.
    (tmp_path / "writer.py").write_text("COLLECTION = 'shadows'\n", encoding="utf-8")
    (tmp_path / "reader.py").write_text("COLLECTION = 'shadows_v4_1024'\n", encoding="utf-8")
    # Two modules that each own an unrelated setting: not a fork.
    (tmp_path / "a.py").write_text("MODEL = 'deepseek-chat'\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("MODEL = 'gpt-5'\n", encoding="utf-8")

    report = scan_anomalies(tmp_path)
    forked = _of_kind(report, "constant_forked")
    assert [item["evidence"]["name"] for item in forked] == ["COLLECTION"]
    assert forked[0]["evidence"]["definitions"] == {
        "reader.py": "'shadows_v4_1024'", "writer.py": "'shadows'"}


def test_import_cycle_is_reported(tmp_path):
    (tmp_path / "alpha.py").write_text("import beta\n", encoding="utf-8")
    (tmp_path / "beta.py").write_text("import gamma\n", encoding="utf-8")
    (tmp_path / "gamma.py").write_text("import alpha\n", encoding="utf-8")
    cycles = _of_kind(scan_anomalies(tmp_path), "import_cycle")
    assert cycles
    assert set(cycles[0]["evidence"]["cycle"]) == {"alpha.py", "beta.py", "gamma.py"}


def test_whole_chain_of_generations_is_reported(tmp_path):
    for name in ("router.py", "router_v2.py", "router_v2_runtime.py"):
        (tmp_path / name).write_text("def route():\n    return 1\n", encoding="utf-8")
    report = scan_anomalies(tmp_path)
    covered = {module for item in _of_kind(report, "parallel_generations")
               for module in item["evidence"]["modules"]}
    # A suffix rule only ever sees one generation up; the chain must be covered.
    assert covered == {"router.py", "router_v2.py", "router_v2_runtime.py"}


def test_unowned_hub_needs_no_test_and_no_mention(tmp_path):
    (tmp_path / "hub.py").write_text("def shared():\n    return 1\n", encoding="utf-8")
    (tmp_path / "documented.py").write_text("def other():\n    return 2\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("documented is the entry point.\n", encoding="utf-8")
    (tmp_path / "test_documented.py").write_text("import documented\n", encoding="utf-8")
    for index in range(6):
        (tmp_path / f"user{index}.py").write_text("import hub\nimport documented\n", encoding="utf-8")
    hubs = {item["evidence"]["path"] for item in _of_kind(scan_anomalies(tmp_path), "unowned_hub")}
    assert "hub.py" in hubs
    assert "documented.py" not in hubs


def test_prose_citing_a_live_data_file_is_not_an_anomaly(tmp_path):
    # live_tree must span the whole project; if it only held source files, every
    # citation of a .json or .md would read as missing.
    (tmp_path / "svc.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (tmp_path / "routes.json").write_text('{"a": 1}', encoding="utf-8")
    (tmp_path / "GUIDE.md").write_text(
        "Config lives in `routes.json` and the gone one is `removed_helper.py`.\n", encoding="utf-8")
    cited = {item["evidence"]["cited"] for item in
             _of_kind(scan_anomalies(tmp_path), "prose_cites_missing_path")}
    assert "removed_helper.py" in cited
    assert "routes.json" not in cited


def test_citation_exemptions_do_not_swallow_real_drift(tmp_path):
    (tmp_path / "svc.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (tmp_path / "REVIEW_SPEC.md").write_text(
        "Module B is `conflict_scan.py`.\n"
        "Install to `path/to/target.py`.\n"
        "History lives in `_retired_2026/old_flow.py`.\n",
        encoding="utf-8")
    (tmp_path / "MIGRATION_PLAN.md").write_text("We will add `future_thing.py`.\n", encoding="utf-8")

    cited = {item["evidence"]["cited"] for item in
             _of_kind(scan_anomalies(tmp_path), "prose_cites_missing_path")}
    assert "conflict_scan.py" in cited          # a spec documents what shipped
    assert "path/to/target.py" not in cited     # placeholder
    assert "_retired_2026/old_flow.py" not in cited  # prose discussing history
    assert "future_thing.py" not in cited       # a plan describes what does not exist


def test_declared_dependency_nothing_imports_is_reported(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='svc'\ndependencies = [\n  \"httpx>=0.27\",\n  \"unused-lib>=1\",\n]\n",
        encoding="utf-8")
    (tmp_path / "svc.py").write_text("import httpx\n\n\ndef run():\n    return httpx\n", encoding="utf-8")
    missing = {item["evidence"]["requirement"] for item in
               _of_kind(scan_anomalies(tmp_path), "dependency_never_imported")}
    assert "unused-lib" in missing
    assert "httpx" not in missing


def test_test_importing_a_removed_project_module_is_reported(tmp_path):
    (tmp_path / "test_feature.py").write_text("import removed_feature\n", encoding="utf-8")
    findings = _of_kind(scan_anomalies(tmp_path), "test_targets_missing_module")
    assert findings[0]["evidence"]["missing"] == "removed_feature"


def test_cycle_detection_is_bounded_on_a_dense_acyclic_graph():
    graph = {str(index): {str(target) for target in range(index + 1, 80)} for index in range(80)}
    assert _cycles(graph) == []


def test_anomalies_are_written_beside_the_knowledge_base_never_into_it(tmp_path):
    (tmp_path / "old_core.py").write_text(
        '"""Deprecated core."""\n\n\ndef read():\n    return 1\n', encoding="utf-8")
    for index in range(6):
        (tmp_path / f"caller{index}.py").write_text("import old_core\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Svc\n", encoding="utf-8")
    config_dir = tmp_path / ".turritopsis"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(json.dumps({"llm": {
        "provider": "openai", "model": "m", "api_key_env": "TEST_LLM_KEY"}}), encoding="utf-8")

    assert main(["init", str(tmp_path), "--yes", "--name", "Svc", "--scan"]) == 0

    anomalies = json.loads((config_dir / "scan-anomalies.json").read_text(encoding="utf-8"))
    assert "legacy_still_load_bearing" in {item["kind"] for item in anomalies["findings"]}
    # Scan no longer creates trusted Stages before the installed Agent classifies
    # evidence. Leads remain in their own report and do not contaminate evidence.
    evidence = (config_dir / "scan-evidence.json").read_text(encoding="utf-8")
    assert "legacy_still_load_bearing" not in evidence
    assert not (config_dir / "stages.json").exists()


def test_brief_refreshes_the_persisted_anomaly_report(tmp_path, capsys):
    config = tmp_path / ".turritopsis"
    config.mkdir()
    data_path = config / "stages.json"
    data_path.write_text(json.dumps({
        "title": "Svc", "subtitle": "", "version": 1, "currents": []
    }), encoding="utf-8")
    stale = {"findings": [{
        "kind": "prose_cites_missing_path", "summary": "old finding",
        "evidence": {"document": "OLD.md", "cited": "gone.py"},
    }]}
    (config / "scan-anomalies.json").write_text(json.dumps(stale), encoding="utf-8")

    assert main(["brief", "--data", str(data_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    persisted = json.loads((config / "scan-anomalies.json").read_text(encoding="utf-8"))
    assert output["questions"] == []
    assert persisted["findings"] == []

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from turritopsis.cli import main
from turritopsis.config import LLMConfig, load_llm_config
from turritopsis.exporter import export_project
from turritopsis.generators import refresh_generated
from turritopsis.maintain import maintain_stages


class SkeletonLLM:
    def complete_json(self, system, prompt, schema, schema_name):
        assert "README.md" in prompt and "pyproject.toml" in prompt
        assert "QUEUE = 'jobs'" in prompt
        assert "never invent" in system.lower()
        assert schema_name == "turritopsis_project_skeleton"
        return {"currents": [
            {"id": "product", "name": "Product", "blurb": "Purpose and current direction", "stages": [
                {"id": "product.overview", "title": "Product overview",
                 "purpose": "Route product purpose and scope questions.",
                 "search_hints": "product purpose scope users", "authority": "product scope",
                 "evidence_paths": ["README.md"]},
            ]},
            {"id": "runtime", "name": "Runtime", "blurb": "Executable structure", "stages": [
                {"id": "runtime.components", "title": "Runtime components",
                 "purpose": "Locate the main executable components.",
                 "search_hints": "runtime components package python", "authority": "runtime composition",
                 "evidence_paths": ["pyproject.toml", "src/service.py"]},
            ]},
            {"id": "operations", "name": "Operations", "blurb": "Build and recovery", "stages": [
                {"id": "operations.verify", "title": "Verification",
                 "purpose": "Record the verified test and release path.",
                 "search_hints": "test verify release rollback", "authority": "verification procedure",
                 "evidence_paths": ["README.md"]},
            ]},
        ]}


class MaintenanceLLM:
    def __init__(self):
        self.calls = []

    def complete_json(self, system, prompt, schema, schema_name):
        self.calls.append((system, prompt, schema_name))
        assert "src/service.py" in prompt
        return {
            "stage_id": "runtime.service", "action": "update",
            "body": "# Service\n\nPurpose: Describe the service.\nSearch hints: service queue\nSummary: The service reads jobs from the queue.\nVerified: old\nStatus: current\nAuthority: runtime service\n\n## Current facts\n\nThe service reads jobs from the queue.\n",
            "evidence_paths": ["src/service.py"],
            "rationale": "The referenced service file directly confirms the queue behavior.",
        }


def test_init_with_modules_creates_addressable_empty_knowledge(tmp_path):
    assert main(["init", str(tmp_path), "--yes", "--name", "Demo", "--modules", "API, Worker"]) == 0
    data = json.loads((tmp_path / ".turritopsis" / "stages.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in data["currents"]] == ["api", "worker"]
    assert data["currents"][0]["stages"][0]["id"] == "api.overview"
    assert "Search hints:" in data["currents"][0]["stages"][0]["body"]
    assert "[Placeholder:" in data["currents"][0]["stages"][0]["body"]


def test_init_accepts_non_ascii_module_names(tmp_path):
    assert main(["init", str(tmp_path), "--yes", "--modules", "后端, 前端"]) == 0
    data = json.loads((tmp_path / ".turritopsis" / "stages.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in data["currents"]] == ["module-1", "module-2"]
    assert [item["name"] for item in data["currents"]] == ["后端", "前端"]


def test_init_scan_uses_llm_to_write_canonical_skeleton(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "README.md").write_text("# Sample\nA queued service.", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='sample'", encoding="utf-8")
    (tmp_path / "src" / "service.py").write_text("QUEUE = 'jobs'", encoding="utf-8")
    config_dir = tmp_path / ".turritopsis"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(json.dumps({"llm": {
        "provider": "openai", "model": "small-model", "api_key_env": "TEST_LLM_KEY",
    }}), encoding="utf-8")
    monkeypatch.setattr("turritopsis.cli.LLMClient", lambda config: SkeletonLLM())

    assert main(["init", str(tmp_path), "--yes", "--name", "Sample", "--scan"]) == 0
    data = json.loads((config_dir / "stages.json").read_text(encoding="utf-8"))
    assert [current["id"] for current in data["currents"]] == ["product", "runtime", "operations"]
    stage = data["currents"][1]["stages"][0]
    assert stage["id"] == "runtime.components"
    assert "Purpose: Locate the main executable components." in stage["body"]
    assert "Status: unresolved" in stage["body"]
    assert "[Placeholder: fill from verified project evidence.]" in stage["body"]
    assert (config_dir / "scan-evidence.json").is_file()
    assert not list((config_dir / "proposals").glob("init-scan-*.json"))


def test_maintain_updates_stale_stage_from_traceable_evidence(tmp_path):
    root = tmp_path
    source = root / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def run(job):\n    return queue.read(job)\n", encoding="utf-8")
    data_dir = root / ".turritopsis"
    data_dir.mkdir()
    data_path = data_dir / "stages.json"
    data_path.write_text(json.dumps({
        "title": "Demo", "subtitle": "", "version": 1,
        "currents": [{"id": "runtime", "name": "Runtime", "blurb": "", "stages": [{
            "id": "runtime.service", "title": "Service",
            "body": "# Service\n\nPurpose: Describe the service.\nSearch hints: service queue\nSummary: Old summary.\nVerified: 2025-01-01 by agent\nStatus: current\nAuthority: runtime service\n\n## Evidence\n\nSee `src/service.py`.\n",
        }]}],
    }), encoding="utf-8")
    fake = MaintenanceLLM()
    result = maintain_stages(
        data_path, fake, "openai-compatible", "cheap-model", max_age_days=30,
        now=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )
    assert result["changed"] == 1 and result["model"] == "cheap-model"
    body = json.loads(data_path.read_text(encoding="utf-8"))["currents"][0]["stages"][0]["body"]
    assert "Verified: 2026-08-24 by maintain (openai-compatible/cheap-model)" in body
    assert "reads jobs from the queue" in body
    assert list((data_dir / "backups").glob("stages-*.json"))
    log = (data_dir / "changelog.jsonl").read_text(encoding="utf-8")
    assert "maintain:openai-compatible/cheap-model" in log
    audit = (data_dir / "maintenance.jsonl").read_text(encoding="utf-8")
    assert '"evidence_paths": ["src/service.py"]' in audit


def test_model_override_and_environment_config(tmp_path):
    config_dir = tmp_path / ".turritopsis"
    config_dir.mkdir()
    data_path = config_dir / "stages.json"
    data_path.write_text("{}", encoding="utf-8")
    (config_dir / "config.json").write_text(json.dumps({"llm": {
        "provider": "anthropic", "model": "configured-model", "api_key_env": "CLAUDE_TEST_KEY",
    }}), encoding="utf-8")
    config = load_llm_config(data_path=data_path, model_override="cheap-one-off-model")
    assert config.provider == "anthropic"
    assert config.model == "cheap-one-off-model"
    assert config.api_key_env == "CLAUDE_TEST_KEY"


def test_maintain_cli_model_override_reaches_maintenance(data_path, monkeypatch):
    captured = {}

    def configured(**kwargs):
        captured["override"] = kwargs["model_override"]
        return LLMConfig("openai", kwargs["model_override"], "UNUSED_KEY", "https://api.example.test/v1")

    def maintained(path, client, provider, model, max_age_days, actor):
        captured.update({"path": path, "provider": provider, "model": model})
        return {"changed": 0, "model": model, "results": []}

    monkeypatch.setattr("turritopsis.cli.load_llm_config", configured)
    monkeypatch.setattr("turritopsis.cli.LLMClient", lambda config: object())
    monkeypatch.setattr("turritopsis.cli.maintain_stages", maintained)
    assert main(["maintain", "--data", str(data_path), "--model", "cheap-one-off-model"]) == 0
    assert captured["override"] == "cheap-one-off-model"
    assert captured["model"] == "cheap-one-off-model"


def test_export_markdown_and_json(data_path, capsys):
    markdown = export_project(data_path, "md")
    assert markdown.startswith("# Long Project")
    assert "## Project" in markdown and "<!-- Stage: project.handoff -->" in markdown
    exported = json.loads(export_project(data_path, "json"))
    assert exported["title"] == "Long Project"
    assert main(["export", "--data", str(data_path), "--format", "md"]) == 0
    assert capsys.readouterr().out.startswith("# Long Project")


def test_only_explicit_generated_stage_is_deterministically_refreshed(data_path):
    document = json.loads(data_path.read_text(encoding="utf-8"))
    document["currents"][1]["stages"].append({
        "id": "manual.snapshot", "title": "Path snapshot", "status": "generated",
        "generator": {"type": "path_exists", "path": ".turritopsis/stages.json"}, "body": "",
    })
    data_path.write_text(json.dumps(document), encoding="utf-8")
    results = refresh_generated(data_path)
    assert results[0]["changed"] is True
    refreshed = json.loads(data_path.read_text(encoding="utf-8"))["currents"][1]["stages"][0]["body"]
    assert "auto-generated" in refreshed and '"exists": true' in refreshed

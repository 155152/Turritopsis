from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path

from turritopsis.cli import main
from turritopsis.config import LLMConfig, load_llm_config
from turritopsis.exporter import export_project
from turritopsis.generators import refresh_generated
from turritopsis.maintain import maintain_stages
from turritopsis.revisions import revision


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
    # Named modules are code-shaped, so the human-knowledge Currents are added too:
    # without them there is nowhere to record what was never committed.
    assert [item["id"] for item in data["currents"]] == [
        "api", "worker", "genesis", "bounds", "manual"]
    assert data["currents"][0]["stages"][0]["id"] == "api.overview"
    assert "Search hints:" in data["currents"][0]["stages"][0]["body"]
    assert "[Placeholder:" in data["currents"][0]["stages"][0]["body"]


def test_init_accepts_non_ascii_module_names(tmp_path):
    assert main(["init", str(tmp_path), "--yes", "--modules", "后端, 前端"]) == 0
    data = json.loads((tmp_path / ".turritopsis" / "stages.json").read_text(encoding="utf-8"))
    named = data["currents"][:2]
    assert [item["id"] for item in named] == ["module-1", "module-2"]
    assert [item["name"] for item in named] == ["后端", "前端"]
    assert [item["id"] for item in data["currents"][2:]] == ["genesis", "bounds", "manual"]


def test_init_without_tty_falls_back_to_defaults(tmp_path, monkeypatch):
    # Agents and CI have no tty. Prompting there used to raise EOFError.
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert main(["init", str(tmp_path)]) == 0
    data = json.loads((tmp_path / ".turritopsis" / "stages.json").read_text(encoding="utf-8"))
    assert data["title"] == tmp_path.name
    assert [item["id"] for item in data["currents"]] == ["anatomy", "flow", "bounds", "manual", "genesis"]


def test_init_scan_is_local_and_preserves_evidence_without_api_key(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "README.md").write_text("# Sample\nA queued service.", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='sample'", encoding="utf-8")
    (tmp_path / "src" / "service.py").write_text(
        "QUEUE = 'jobs'\n\n\ndef enqueue(job, priority):\n    return QUEUE\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config_dir = tmp_path / ".turritopsis"
    assert main(["init", str(tmp_path), "--yes", "--name", "Sample", "--scan"]) == 0
    assert (config_dir / "scan-evidence.json").is_file()
    assert (config_dir / "scan-anomalies.json").is_file()
    run = json.loads((config_dir / "scan-run.json").read_text(encoding="utf-8"))
    assert run["state"] == "evidence_ready"
    assert run["classification_source"] == "pending-installed-agent"
    assert not (config_dir / "stages.json").exists()


def test_agent_skeleton_is_validated_and_applied(tmp_path):
    (tmp_path / "README.md").write_text("# Shop\nOrders enter over HTTP.", encoding="utf-8")
    assert main(["scan", str(tmp_path)]) == 0
    skeleton = tmp_path / "skeleton.json"
    skeleton.write_text(json.dumps({
        "title": "Shop",
        "classification_provenance": {
            "source": "installed-agent", "agent_self_reported": "codex", "created_at": "2026-08-24T00:00:00Z"
        },
        "currents": [{
            "id": "orders", "name": "Order lifecycle", "blurb": "How orders move",
            "stages": [{
                "id": "orders.request_flow", "title": "How an order reaches a terminal state",
                "type": "flow", "freshness": "steady",
                "purpose": "Route questions about the order lifecycle.",
                "search_hints": "order request success failure retry terminal",
                "authority": "Order request lifecycle; excludes deployment.",
                "evidence_paths": ["README.md"],
                "update_triggers": ["The order state machine changes"],
            }],
        }],
    }), encoding="utf-8")
    assert main(["apply-skeleton", str(skeleton), str(tmp_path)]) == 0
    data = json.loads((tmp_path / ".turritopsis" / "stages.json").read_text(encoding="utf-8"))
    assert data["classification"]["agent_self_reported"] == "codex"
    assert "agent" not in data["classification"]
    body = data["currents"][0]["stages"][0]["body"]
    assert "Type: flow" in body
    assert "Freshness: steady" in body
    assert "## Update triggers" in body


def test_update_stage_cli_writes_body_and_rejects_stale_revision(data_path, tmp_path, capsys):
    document = json.loads(data_path.read_text(encoding="utf-8"))
    original = document["currents"][0]["stages"][0]["body"]
    original_revision = revision(original)
    body_file = tmp_path / "handoff.md"
    body_file.write_text("# Updated handoff\n\nCurrent work is verified.\n", encoding="utf-8")

    assert main([
        "update-stage", "project.handoff", "--data", str(data_path),
        "--body-file", str(body_file), "--expected-revision", original_revision,
        "--actor", "cold-start-agent",
    ]) == 0
    updated = json.loads(data_path.read_text(encoding="utf-8"))
    assert updated["currents"][0]["stages"][0]["body"] == body_file.read_text(encoding="utf-8")

    body_file.write_text("# Silent overwrite must not happen\n", encoding="utf-8")
    assert main([
        "update-stage", "project.handoff", "--data", str(data_path),
        "--body-file", str(body_file), "--expected-revision", original_revision,
        "--actor", "cold-start-agent",
    ]) == 3
    error = capsys.readouterr().err
    current_body = updated["currents"][0]["stages"][0]["body"]
    assert f"current revision {revision(current_body)}" in error
    after_conflict = json.loads(data_path.read_text(encoding="utf-8"))
    assert after_conflict["currents"][0]["stages"][0]["body"] == current_body


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

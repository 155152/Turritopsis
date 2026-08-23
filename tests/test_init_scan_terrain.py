from __future__ import annotations

import json
from pathlib import Path

import pytest

from turritopsis.init_scan import (
    OUTPUT_CONTRACT,
    _import_counts,
    _import_graph,
    generate_skeleton,
    scan_project,
    survey_terrain,
)
from turritopsis.structure import outline_source


@pytest.fixture
def aged_project(tmp_path: Path) -> Path:
    """A project that has been alive long enough to accumulate sediment."""
    (tmp_path / "README.md").write_text("# Service\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='svc'\n", encoding="utf-8")

    # Live code: store is imported by everything, entry runs as a service.
    (tmp_path / "store.py").write_text(
        "VALUE = 1\n\n\nclass Store:\n    def put(self, key, value):\n        return VALUE\n",
        encoding="utf-8")
    (tmp_path / "entry.py").write_text(
        "import store\n\n\ndef boot():\n    return store.Store()\n\n\n"
        "if __name__ == '__main__':\n    boot()\n", encoding="utf-8")
    (tmp_path / "api.py").write_text(
        "import store\n\n\ndef handle(request):\n    return request\n", encoding="utf-8")
    (tmp_path / "worker.py").write_text(
        "import store\n\n\ndef consume(job):\n    return job\n", encoding="utf-8")
    (tmp_path / "orphan.py").write_text(
        "def unused_helper(value):\n    return value\n", encoding="utf-8")

    # Sediment: dated backups beside the files they shadow.
    (tmp_path / "store.py.bak-20260622-old").write_text("VALUE = 0\n", encoding="utf-8")
    (tmp_path / "api.py.orig").write_text("# old\n", encoding="utf-8")
    backups = tmp_path / "backups-release-20260101"
    backups.mkdir()
    for name in ("store.py", "api.py", "worker.py"):
        (backups / name).write_text("# archived\n", encoding="utf-8")
    retired = tmp_path / "_retired_2026"
    retired.mkdir()
    (retired / "legacy.py").write_text("# gone\n", encoding="utf-8")

    # Runtime output: one filename pattern, many files.
    runs = tmp_path / "runs"
    runs.mkdir()
    for index in range(12):
        (runs / f"run_{index:04d}.json").write_text(json.dumps({"i": index}), encoding="utf-8")
    return tmp_path


def test_backup_and_retired_directories_stay_out_of_the_tree(aged_project):
    tree = scan_project(aged_project)["tree"]
    assert "store.py" in tree
    assert not [path for path in tree if "backups-release" in path]
    assert not [path for path in tree if "_retired_2026" in path]


def test_dated_copies_stay_out_of_the_tree(aged_project):
    tree = scan_project(aged_project)["tree"]
    # A model shown xxx.py.bak-<date> learns the pattern and invents more of them.
    assert "store.py.bak-20260622-old" not in tree
    assert "api.py.orig" not in tree
    assert "api.py" in tree


def test_repeated_filename_pattern_is_collapsed_to_one_sample(aged_project):
    materials = [item["path"] for item in scan_project(aged_project)["materials"]]
    run_samples = [path for path in materials if path.startswith("runs/")]
    assert len(run_samples) <= 1, f"runtime output should not flood materials: {run_samples}"


def test_widely_imported_module_outranks_a_recently_touched_orphan(aged_project):
    outline = scan_project(aged_project)["structure_map"]
    assert "store.py" in outline
    assert outline.index("store.py") < outline.index("orphan.py")


def test_source_reaches_the_model_as_declarations_not_bodies(aged_project):
    (aged_project / "store.py").write_text(
        "SECRET_CONSTANT = 42\n\n\nclass Store:\n"
        "    def put(self, key, value):\n        return SECRET_CONSTANT\n",
        encoding="utf-8")
    evidence = scan_project(aged_project)
    outline = evidence["structure_map"]
    assert "class Store" in outline
    assert "def put(self, key, value)" in outline
    # Global coverage is not the same thing as putting every line in the model.
    assert "SECRET_CONSTANT = 42" not in outline
    assert "return SECRET_CONSTANT" not in outline


def test_prose_is_kept_whole_while_code_is_outlined(aged_project):
    evidence = scan_project(aged_project)
    prose_paths = [item["path"] for item in evidence["materials"]]
    assert "README.md" in prose_paths
    assert not [path for path in prose_paths if path.endswith(".py")]
    assert evidence["structure_coverage"]["files_mapped"] >= 4


def test_structure_coverage_reports_what_the_budget_dropped(aged_project):
    from turritopsis.structure import structure_map
    ranked = [(aged_project / name, name, 0) for name in ("store.py", "api.py", "worker.py")]
    _, coverage = structure_map(ranked, budget=10)
    assert coverage["files_mapped"] == 0
    # A truncated map must not read as complete coverage.
    assert coverage["files_skipped"] == 3


def test_prompt_states_the_output_contract():
    # Only the OpenAI /responses path enforces the schema; the other two providers
    # need the shape spelled out or the model guesses the Stage shape for Currents.
    for key in ("id", "name", "blurb", "stages", "search_hints", "evidence_paths"):
        assert key in OUTPUT_CONTRACT


def test_terrain_survey_separates_sediment_from_live_code(aged_project):
    report = survey_terrain(aged_project)
    assert report["buried_files"] == 4          # 3 in backups-release + 1 in _retired
    assert report["stale_copies"] == 2          # .bak-<date> and .orig
    assert "store.py" in report["shadowed_originals"]
    assert report["generated_clusters"][0][1] == 12
    # entry.py runs standalone and worker/api are imported by nothing but import store;
    # only the genuinely inert module is reported.
    assert "orphan.py" in report["unreferenced_sources"]
    assert "entry.py" not in report["unreferenced_sources"]


class _InventingLLM:
    """Returns one real evidence path and one that never existed."""

    def complete_json(self, system, prompt, schema, schema_name):
        return {"currents": [
            {"id": "core", "name": "Core", "blurb": "Core of the service", "stages": [
                {"id": "core.store", "title": "Store", "purpose": "Route storage questions.",
                 "search_hints": "store value", "authority": "storage",
                 "evidence_paths": ["store.py", "store.py.bak-20260622-old"]},
            ]},
            {"id": "edge", "name": "Edge", "blurb": "Entry points", "stages": [
                {"id": "edge.entry", "title": "Entry", "purpose": "Route startup questions.",
                 "search_hints": "entry main", "authority": "startup",
                 "evidence_paths": ["entry.py"]},
            ]},
            {"id": "ops", "name": "Ops", "blurb": "Operations", "stages": [
                {"id": "ops.api", "title": "API", "purpose": "Route API questions.",
                 "search_hints": "api http", "authority": "api",
                 "evidence_paths": ["api.py"]},
            ]},
        ]}


def test_invented_evidence_is_dropped_not_fatal(aged_project):
    data, evidence = generate_skeleton(aged_project, "Svc", "", _InventingLLM())
    body = data["currents"][0]["stages"][0]["body"]
    assert "store.py" in body
    assert "store.py.bak-20260622-old" not in body
    assert evidence["invented_evidence_paths"] == ["core.store -> store.py.bak-20260622-old"]


class _FullyInventingLLM(_InventingLLM):
    def complete_json(self, system, prompt, schema, schema_name):
        result = super().complete_json(system, prompt, schema, schema_name)
        result["currents"][0]["stages"][0]["evidence_paths"] = ["does/not/exist.py"]
        return result


def test_stage_with_only_invented_evidence_still_fails(aged_project):
    with pytest.raises(ValueError, match="only unknown evidence"):
        generate_skeleton(aged_project, "Svc", "", _FullyInventingLLM())


def test_repository_currents_reserve_room_for_human_knowledge(aged_project):
    class TooMany(_InventingLLM):
        def complete_json(self, system, prompt, schema, schema_name):
            template = super().complete_json(system, prompt, schema, schema_name)["currents"][0]
            return {"currents": [
                {**template, "id": f"c{index}", "stages": [
                    {**template["stages"][0], "id": f"c{index}.overview"}]}
                for index in range(6)
            ]}

    with pytest.raises(ValueError, match="3-5 repository-derived"):
        generate_skeleton(aged_project, "Svc", "", TooMany())


def test_credential_files_never_reach_the_model(tmp_path):
    (tmp_path / "README.md").write_text("# App\n", encoding="utf-8")
    (tmp_path / "svc.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    # Caught by name.
    (tmp_path / "youkies_key.txt").write_text("sk-7HZabcdefghijklmnopqrstuv\n", encoding="utf-8")
    (tmp_path / "auth.json").write_text('{"token": "abc"}\n', encoding="utf-8")
    # Innocent name, credential inside — the name rule alone would miss this.
    (tmp_path / "notes.md").write_text(
        "Deploy steps\n\nexport TOKEN=ghp_abcdefghijklmnopqrst\n", encoding="utf-8")

    evidence = scan_project(tmp_path)
    blob = json.dumps(evidence, ensure_ascii=False)
    assert "sk-7HZabcdefghijklmnopqrstuv" not in blob
    assert "ghp_abcdefghijklmnopqrst" not in blob
    assert "notes.md" not in [item["path"] for item in evidence["materials"]]
    assert "README.md" in [item["path"] for item in evidence["materials"]]


def test_sensitive_name_filter_does_not_hide_normal_source(tmp_path):
    for name in ("auth.py", "authentication.py", "keyboard.py", "monkey.py", "token.py"):
        (tmp_path / name).write_text("def visible():\n    return 1\n", encoding="utf-8")
    (tmp_path / "deploy_secret.txt").write_text("not for the model\n", encoding="utf-8")

    evidence = scan_project(tmp_path)
    assert {"auth.py", "authentication.py", "keyboard.py", "monkey.py", "token.py"} <= set(evidence["tree"])
    assert "deploy_secret.txt" not in evidence["tree"]


def test_package_imports_contribute_to_structure_rank_and_graph(tmp_path):
    package = tmp_path / "src" / "app"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    store = package / "store.py"
    api = package / "api.py"
    store.write_text("class Store:\n    pass\n", encoding="utf-8")
    api.write_text("from app.store import Store\n", encoding="utf-8")
    files = [package / "__init__.py", api, store]

    assert _import_counts(files, tmp_path)[store] == 1
    assert _import_graph(files, tmp_path)[1][api] == {store}


def test_typescript_assigned_functions_reach_the_structure_map():
    source = (
        "export const route = async (request: Request) => request;\n"
        "const Helper: React.FC<Props> = (props) => null;\n"
    )
    assert outline_source(Path("app.tsx"), source) == [
        "const route(request: Request)", "const Helper(props)"]


def test_hardcoded_key_keeps_a_source_file_out_of_the_structure_map(tmp_path):
    (tmp_path / "README.md").write_text("# App\n", encoding="utf-8")
    (tmp_path / "clean.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    (tmp_path / "leaky.py").write_text(
        "API = 'sk-abcdefghijklmnopqrstuvwx'\n\n\ndef call(token=API):\n    return token\n",
        encoding="utf-8")
    outline = scan_project(tmp_path)["structure_map"]
    assert "def ok()" in outline
    assert "leaky.py" not in outline
    assert "sk-abcdefghijklmnopqrstuvwx" not in outline


def test_evidence_roles_answer_different_questions(tmp_path):
    (tmp_path / "README.md").write_text("# Service\nWhat this is.\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='svc'\n", encoding="utf-8")
    (tmp_path / "CONTRIBUTING.md").write_text("Run the tests before pushing.\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("## 1.0\nFirst release.\n", encoding="utf-8")
    (tmp_path / "svc.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    evidence = scan_project(tmp_path)
    roles = {item["path"]: item["role"] for item in evidence["materials"]}
    assert roles["README.md"] == "orientation"
    assert roles["pyproject.toml"] == "manifest"
    assert roles["CONTRIBUTING.md"] == "convention"
    assert roles["CHANGELOG.md"] == "history"
    # The prompt has to say what each role can and cannot settle.
    assert "never treat it as a ruling" in evidence["evidence_roles"]["convention"]
    assert "timeline or genesis" in evidence["evidence_roles"]["history"]


def test_runtime_output_collapses_whether_it_is_many_files_or_many_directories(tmp_path):
    (tmp_path / "README.md").write_text("# App\n", encoding="utf-8")
    flat = tmp_path / "pending"
    flat.mkdir()
    for index in range(9):
        (flat / f"pc_{index:016x}.json").write_text('{"a":1}', encoding="utf-8")
    windows = tmp_path / "by-window"
    windows.mkdir()
    for index in range(9):
        directory = windows / f"1767fd0f-b7c7-480b-b724-{index:012d}"
        directory.mkdir()
        (directory / "summary.md").write_text(f"# window {index}\n", encoding="utf-8")

    paths = [item["path"] for item in scan_project(tmp_path)["materials"]]
    assert len([p for p in paths if p.startswith("pending/")]) <= 1
    assert len([p for p in paths if p.startswith("by-window/")]) <= 1


def test_sediment_is_counted_but_its_contents_stay_out(tmp_path):
    (tmp_path / "README.md").write_text("# App\n", encoding="utf-8")
    (tmp_path / "svc.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (tmp_path / "svc.py.bak-20260101-old").write_text(
        "def run():\n    return 'OBSOLETE_BEHAVIOUR'\n", encoding="utf-8")
    retired = tmp_path / "archive"
    retired.mkdir()
    (retired / "gone.py").write_text("SECRET_OLD_DESIGN = 1\n", encoding="utf-8")

    evidence = scan_project(tmp_path)
    blob = json.dumps(evidence, ensure_ascii=False)
    # History is not thrown away — a genesis Current needs to know it exists.
    assert evidence["sediment"]["total_files"] == 2
    assert evidence["sediment"]["dated_copies"] == 1
    # But it is never quotable as current behaviour.
    assert "OBSOLETE_BEHAVIOUR" not in blob
    assert "SECRET_OLD_DESIGN" not in blob

from __future__ import annotations

import json
from pathlib import Path

from turritopsis.skeletons import FRESHNESS, STAGE_TYPES


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
SCENARIO_SKILLS = {
    "turritopsis-agent-memory": {"authority", "flow", "contract", "boundary", "operations", "verification"},
    "turritopsis-human-facing-pwa": {"flow", "contract", "boundary", "build_release", "verification"},
    "turritopsis-personal-ai-assistant": {"orientation", "authority", "flow", "contract", "boundary", "verification"},
    "turritopsis-persistent-agent-runtime": {"authority", "architecture", "flow", "boundary", "operations", "verification"},
}


def test_scenario_skills_are_installable_and_progressively_disclosed():
    for name in SCENARIO_SKILLS:
        directory = SKILLS / name
        skill = (directory / "SKILL.md").read_text(encoding="utf-8")
        metadata = (directory / "agents" / "openai.yaml").read_text(encoding="utf-8")
        assert skill.startswith(f"---\nname: {name}\n")
        assert "references/stage-suite.md" in skill
        assert "references/fixture.json" in skill
        assert "$turritopsis-onboarding" in skill
        assert "TODO" not in skill
        assert f"${name}" in metadata
        assert "short_description:" in metadata


def test_scenario_fixtures_are_structurally_complete_and_project_specific():
    titles: set[str] = set()
    for name, required_types in SCENARIO_SKILLS.items():
        path = SKILLS / name / "references" / "fixture.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document["classification_provenance"]["source"] == "example"
        assert document["title"] not in titles
        titles.add(document["title"])

        represented: set[str] = set()
        authorities: set[str] = set()
        stage_count = 0
        for current in document["currents"]:
            assert current["id"] not in {"misc", "notes", "other"}
            assert current["name"].strip()
            assert current["stages"]
            for stage in current["stages"]:
                stage_count += 1
                assert stage["type"] in STAGE_TYPES
                assert stage["freshness"] in FRESHNESS
                assert stage["title"].strip()
                assert stage["purpose"].strip()
                assert stage["search_hints"].strip()
                assert stage["authority"].strip()
                assert stage["authority"] not in authorities
                assert stage["evidence_paths"]
                assert stage["update_triggers"]
                authorities.add(stage["authority"])
                represented.add(stage["type"])
        assert 4 <= stage_count <= 8
        assert required_types <= represented


def test_scenario_suites_teach_their_critical_separations():
    expected = {
        "turritopsis-agent-memory": ["Raw evidence is not a belief", "An index is not the source"],
        "turritopsis-human-facing-pwa": ["Stored content and rendered presentation", "UI is not automatically the source of truth"],
        "turritopsis-personal-ai-assistant": ["is not consent", "human-facing reason"],
        "turritopsis-persistent-agent-runtime": ["Process alive", "session reset"],
    }
    for name, phrases in expected.items():
        suite = (SKILLS / name / "references" / "stage-suite.md").read_text(encoding="utf-8")
        for phrase in phrases:
            assert phrase in suite

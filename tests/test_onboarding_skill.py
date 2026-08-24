from __future__ import annotations

import json
from pathlib import Path

from turritopsis.skeletons import FRESHNESS, STAGE_TYPES


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "turritopsis-onboarding"


def test_stage_reference_covers_every_supported_type():
    reference = (SKILL / "references" / "stage-types.md").read_text(encoding="utf-8")
    examples = (SKILL / "references" / "paired-examples.md").read_text(encoding="utf-8")
    for stage_type in STAGE_TYPES:
        assert f"`{stage_type}`" in reference
        assert f"`{stage_type}`" in examples


def test_seven_non_agent_project_fixtures_are_structurally_complete():
    fixtures = sorted((SKILL / "references").glob("fixture-*.json"))
    assert len(fixtures) == 7
    represented: set[str] = set()
    for path in fixtures:
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document["classification_provenance"]["source"] == "example"
        assert document["currents"]
        for current in document["currents"]:
            assert current["id"] not in {"misc", "notes", "other"}
            assert current["stages"]
            for stage in current["stages"]:
                assert stage["type"] in STAGE_TYPES
                assert stage["freshness"] in FRESHNESS
                assert stage["purpose"].strip()
                assert stage["authority"].strip()
                assert stage["evidence_paths"]
                assert stage["update_triggers"]
                represented.add(stage["type"])
    assert {"architecture", "flow", "contract", "domain", "data", "boundary",
            "operations", "verification", "build_release", "authority", "decision"} <= represented


def test_skill_routes_to_local_scan_and_validated_application():
    content = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "turritopsis scan" in content
    assert "turritopsis apply-skeleton skeleton.json" in content
    assert "second model or API key" in content
    assert "one Stage per file" in content

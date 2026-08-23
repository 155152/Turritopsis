from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def data_path(tmp_path: Path) -> Path:
    root = tmp_path / ".turritopsis"
    root.mkdir()
    path = root / "stages.json"
    path.write_text(json.dumps({
        "title": "Long Project", "subtitle": "Shared truth", "version": 1,
        "currents": [
            {"id": "project", "name": "Project", "blurb": "Long-running domain", "stages": [
                {"id": "project.handoff", "title": "Current work and handoff", "body": """# Current work

Purpose: Tell a contributor where work stopped.
Search hints: handoff blocker next step release frozen
Summary: Release is frozen pending hardware regression.
Verified: 2026-08-24 by agent
Status: current
Authority: current work, next action

## Next steps
Run the hardware regression on candidate v2.3.0.
"""},
                {"id": "project.timeline", "title": "Historical timeline", "body": """# Timeline

Search hints: release old path retired
Summary: Historical release decisions.
Status: historical
Authority: historical sequence

## 2025
The /old/entry path was retired after error E_OLD.
"""},
            ]},
            {"id": "manual", "name": "Operations", "blurb": "How to operate", "stages": []},
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


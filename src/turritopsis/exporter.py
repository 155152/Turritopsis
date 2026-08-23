from __future__ import annotations

import json
from pathlib import Path

from .store import Store


def export_project(data_path: Path, format_name: str) -> str:
    data = Store(data_path).load()
    if format_name == "json":
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if format_name != "md":
        raise ValueError("format must be md or json")
    lines = [f"# {data.get('title', 'Untitled project')}"]
    if data.get("subtitle"):
        lines.extend(["", str(data["subtitle"])])
    for current in data.get("currents", []):
        lines.extend(["", f"## {current.get('name') or current.get('id')}"])
        if current.get("blurb"):
            lines.extend(["", str(current["blurb"])])
        for stage in current.get("stages", []):
            lines.extend(["", f"<!-- Stage: {stage.get('id', '')} -->", ""])
            body = str(stage.get("body") or "").strip()
            lines.append(body or f"### {stage.get('title', stage.get('id', 'Untitled Stage'))}\n\n[Empty Stage]")
    return "\n".join(lines).rstrip() + "\n"

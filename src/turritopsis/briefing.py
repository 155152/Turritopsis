"""The handoff packet an arriving agent reads before it writes anything.

A scan produces addresses with empty bodies. Filling them splits cleanly in two.

Some Stages can be filled by reading the repository: what a module contains, how
a request moves, which component calls which. An agent should never spend a
person's attention on those — a question a grep would have answered is a question
that should not have been asked.

The rest cannot be filled from the repository at any depth, because the answer was
never written down anywhere: why this design won and which one lost, what breaks if
you delete the thing that looks unused, what has to be done by hand after a
restore. That knowledge only exists in someone's head, and it maps onto exactly the
Currents a scan leaves empty — genesis, bounds, manual.

So the briefing sorts the work into: settled (do not re-derive), self-serve (go
read), and ask (only a human can answer), and every question in the last group
arrives with the evidence already gathered, so the human supplies judgement rather
than lookup.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PLACEHOLDER = re.compile(r"\[Placeholder:", re.I)
UNVERIFIED = re.compile(r"^Verified:\s*not yet verified\s*$", re.I | re.M)

# Which Currents a repository can and cannot answer for itself. The left column is
# recoverable by reading code; the right column was never written down.
SELF_SERVE_CURRENTS = {"anatomy", "flow", "structure", "components", "runtime", "interface"}
HUMAN_ONLY_CURRENTS = {"genesis", "bounds", "manual", "history", "decisions"}

CURRENT_QUESTIONS = {
    "genesis": [
        "Which designs were tried and rejected here, and what went wrong with them?",
        "Which decisions in this project would you make differently today, and which are load-bearing?",
    ],
    "bounds": [
        "What must never change without your sign-off?",
        "What looks unused or duplicated but must not be deleted, and why?",
    ],
    "manual": [
        "When this breaks in production, what is the first thing you check?",
        "What still has to be done by hand — no script covers it?",
    ],
    "history": [
        "What changed recently enough that the code and the docs may still disagree?",
    ],
}

ANOMALY_QUESTIONS = {
    "constant_forked": "{name} holds different values in {where}. Which one is authoritative, and is the other an unfinished migration?",
    "parallel_generations": "{summary}. Which generation is live, and can the older ones be deleted?",
    "prose_cites_missing_path": "{document} still refers to {cited}, which no longer exists. Was it retired, renamed, or moved — and should the document be corrected?",
    "unowned_hub": "{path} is imported by {importers} modules but has no test and no mention in project prose. Who owns it, and is the lack of tests deliberate?",
    "legacy_still_load_bearing": "{path} is marked '{marker}' yet {importers} modules still import it. Is the label stale, or is a migration unfinished?",
    "import_cycle": "These modules form an import cycle: {summary}. Is that intentional?",
    "dependency_never_imported": "The manifest requires '{requirement}' but nothing imports it. Is it still needed?",
    "test_targets_missing_module": "{path} imports '{missing}', which is not a module here. Is that test still meaningful?",
}


def _stage_state(body: str) -> str:
    if not body.strip():
        return "empty"
    if PLACEHOLDER.search(body) or UNVERIFIED.search(body):
        return "skeleton"
    if re.search(r"^Verified:\s*\S.+$", body, re.I | re.M):
        return "filled"
    return "unverified"


def _question(kind: str, finding: dict[str, Any]) -> str | None:
    template = ANOMALY_QUESTIONS.get(kind)
    if not template:
        return None
    evidence = dict(finding.get("evidence", {}))
    evidence.setdefault("summary", finding.get("summary", ""))
    if kind == "constant_forked":
        definitions = evidence.get("definitions", {})
        evidence["where"] = ", ".join(f"{path} ({value})" for path, value in sorted(definitions.items()))
    try:
        return template.format(**evidence)
    except KeyError:
        return finding.get("summary")


def build_briefing(
    data: dict[str, Any],
    anomalies: dict[str, Any],
    handoff: str = "",
) -> dict[str, Any]:
    """Sort the remaining work into settled, self-serve, and ask-a-human."""
    self_serve: list[dict[str, str]] = []
    ask_current: list[dict[str, str]] = []
    filled = 0
    total = 0

    for current in data.get("currents", []):
        current_id = str(current.get("id", ""))
        root_word = current_id.split(".")[0].lower()
        for stage in current.get("stages", []):
            total += 1
            state = _stage_state(str(stage.get("body") or ""))
            if state == "filled":
                filled += 1
                continue
            entry = {"stage_id": stage.get("id"), "title": stage.get("title"), "state": state}
            if root_word in HUMAN_ONLY_CURRENTS:
                ask_current.append(entry)
            else:
                self_serve.append(entry)

    questions: list[dict[str, Any]] = []
    for finding in anomalies.get("findings", []):
        text = _question(finding.get("kind", ""), finding)
        if text:
            questions.append({
                "question": text,
                "because": finding.get("summary"),
                "evidence": finding.get("evidence"),
                "source": "anomaly",
            })

    asked_currents = {entry["stage_id"].split(".")[0] for entry in ask_current if entry.get("stage_id")}
    for current_id in sorted(asked_currents):
        for text in CURRENT_QUESTIONS.get(current_id.lower(), []):
            questions.append({
                "question": text,
                "because": f"Current '{current_id}' has no verified content and the repository cannot supply it",
                "source": "empty_current",
            })

    briefing: dict[str, Any] = {
        "how_to_use": (
            "Fill self_serve Stages by reading the repository — never ask a person a question "
            "the code answers. Ask the questions below before writing genesis, bounds or manual "
            "content; that knowledge is not in the repository at any depth. Record answers with "
            "update_stage and set 'Verified: <date> by <who>'. Leave anything still unconfirmed "
            "as an explicit placeholder rather than a plausible guess."
        ),
        "progress": {"stages": total, "filled": filled, "remaining": total - filled},
        "settled_do_not_re_derive": {
            "structure": "scan-evidence.json holds the declaration map and inbound import counts",
            "anomalies": f"{len(anomalies.get('findings', []))} cross-layer disagreements already found; "
                         "they are leads to confirm, never facts to copy into a Stage",
        },
        "self_serve": self_serve,
        "ask_a_human": ask_current,
        "questions": questions,
    }
    if handoff.strip():
        briefing["human_handoff"] = {
            "note": "Read this first. It is authoritative about intent and priorities, "
                    "and it can still be out of date about the code — verify claims about "
                    "current behaviour against the repository before recording them.",
            "text": handoff.strip(),
        }
        briefing["how_to_use"] += (
            " A human handoff was supplied: read it before asking anything, and drop any "
            "question it already answers."
        )
    return briefing


def read_handoff(root: Path) -> str:
    """Pick up a hand-written introduction if the engineer left one."""
    for name in ("HANDOFF.md", "ONBOARDING.md", "handoff.md", ".turritopsis/handoff.md"):
        candidate = root / name
        if candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return ""

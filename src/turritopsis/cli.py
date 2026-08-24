from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .briefing import build_briefing, read_handoff
from .config import DATA_RELATIVE, load_llm_config, resolve_data
from .exporter import export_project
from .init_scan import _human_knowledge_currents, scan_anomalies, survey_terrain
from .llm import LLMClient, LLMError
from .maintain import apply_proposal, maintain_stages, write_proposal
from .scheduler import install_schedule, remove_schedule, show_schedule
from .scan_run import run_local_scan
from .server import serve
from .skeletons import apply_skeleton
from .store import RevisionConflict, Store


SKELETON = [
    ("anatomy", "What exists now", "Current components and runtime structure"),
    ("flow", "How it moves", "Data, control, request, and event flows"),
    ("bounds", "What must hold", "Contracts, permissions, invariants, and red lines"),
    ("manual", "How to operate it", "Current deploy, diagnose, restore, and maintenance procedures"),
    ("genesis", "Why it became this", "Decisions, rejected paths, incidents, and history"),
]


def _print(value):
    print(json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _module_currents(raw: str) -> list[dict]:
    names = [item.strip() for item in re.split(r"[,，]", raw) if item.strip()]
    currents = []
    seen = set()
    for name in names:
        current_id = _slug(name) or f"module-{len(currents) + 1}"
        if current_id in seen:
            continue
        seen.add(current_id)
        stage_id = f"{current_id}.overview"
        body = (
            f"# {name} overview\n\n"
            f"Purpose: Describe the current {name} module.\n"
            f"Search hints: {current_id} overview architecture current\n"
            "Summary: [Placeholder: verify and describe this module.]\n"
            "Verified: not yet verified\nStatus: unresolved\n"
            f"Authority: {name} module\n\n"
            "## Knowledge\n\n[Placeholder: fill from verified project evidence.]\n"
        )
        currents.append({"id": current_id, "name": name, "blurb": f"Knowledge about {name}",
                         "stages": [{"id": stage_id, "title": f"{name} overview", "body": body}]})
    return currents


def cmd_init(args) -> int:
    root = Path(args.directory).expanduser().resolve()
    path = root / DATA_RELATIVE
    if path.exists() and not args.force:
        raise FileExistsError(f"Already exists: {path}")
    # Agents and CI run without a tty; prompting there raises EOFError mid-init.
    ask = not args.yes and sys.stdin.isatty()
    title = args.name or ((input(f"Project name [{root.name}]: ").strip() or root.name) if ask else root.name)
    subtitle = args.description or (input("One-line description: ").strip() if ask else "")
    modules = "" if args.scan else (
        args.modules or (input("Main modules (comma-separated; blank for recommended Currents): ").strip() if ask else "")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if args.scan:
        result = run_local_scan(root, refresh=args.force)
        result.update({"title": title, "subtitle": subtitle})
        _print(result)
        return 0
    else:
        if modules:
            # Named modules are code-shaped too, so the same guarantee applies as
            # for --scan: the map needs somewhere to hold what was never committed.
            currents = _module_currents(modules)
            currents.extend(_human_knowledge_currents({item["id"] for item in currents}))
        else:
            currents = []
            for cid, name, blurb in SKELETON:
                stage = _module_currents(name)[0]["stages"][0]
                stage["id"] = f"{cid}.overview"
                stage["body"] = stage["body"].replace(f"Search hints: {_slug(name)}", f"Search hints: {cid}")
                currents.append({"id": cid, "name": name, "blurb": blurb, "stages": [stage]})
        data = {"title": title, "subtitle": subtitle, "version": 1, "currents": currents}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (path.parent / "backups").mkdir(exist_ok=True)
    (path.parent / "proposals").mkdir(exist_ok=True)
    _print({"created": str(path), "currents": [item["id"] for item in data["currents"]],
            "scan_evidence": str(path.parent / "scan-evidence.json") if args.scan else None,
            "scan_anomalies": str(path.parent / "scan-anomalies.json") if args.scan else None})
    return 0


def cmd_add_current(args) -> int:
    store = Store(resolve_data(args.data))
    def mutate(data):
        if store.find_current(data, args.current_id):
            raise ValueError(f"Current already exists: {args.current_id}")
        current = {"id": args.current_id, "name": args.name,
                   "blurb": args.blurb or "", "stages": []}
        if args.glyph:
            current["glyph"] = args.glyph
        data.setdefault("currents", []).append(current)
        return current
    _print(store.mutate_structure(mutate))
    return 0


def cmd_add(args) -> int:
    store = Store(resolve_data(args.data))
    def mutate(data):
        current = store.find_current(data, args.current_id)
        if not current:
            raise KeyError(f"Unknown current: {args.current_id}")
        if store.find_stage(data, args.stage_id)[1]:
            raise ValueError(f"Stage already exists: {args.stage_id}")
        stage = {"id": args.stage_id, "title": args.title, "body": ""}
        current.setdefault("stages", []).append(stage)
        return stage
    _print(store.mutate_structure(mutate))
    return 0


def cmd_maintain(args) -> int:
    data_path = resolve_data(args.data)
    if args.max_age_days <= 0:
        raise ValueError("--max-age-days must be positive")
    selected_modes = sum(bool(item) for item in (
        args.schedule, args.unschedule, args.show_schedule, args.apply, args.proposal_only,
    ))
    if selected_modes > 1:
        raise ValueError("Choose only one of --schedule, --show-schedule, --unschedule, --apply, or --proposal-only")
    if args.schedule:
        _print(install_schedule(data_path, args.schedule, args.model, args.max_age_days))
    elif args.unschedule:
        _print(remove_schedule(data_path))
    elif args.show_schedule:
        _print(show_schedule(data_path))
    elif args.apply:
        _print({"applied": apply_proposal(data_path, Path(args.apply).resolve(), args.actor)})
    elif args.proposal_only:
        _print({"proposal": str(write_proposal(data_path, args.max_age_days))})
    else:
        config = load_llm_config(data_path=data_path, model_override=args.model)
        _print(maintain_stages(
            data_path, LLMClient(config), config.provider, config.model,
            args.max_age_days, args.actor,
        ))
    return 0


def cmd_export(args) -> int:
    content = export_project(resolve_data(args.data), args.format)
    if args.output:
        target = Path(args.output).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        _print({"exported": str(target), "format": args.format})
    else:
        sys.stdout.write(content)
    return 0


def cmd_survey(args) -> int:
    _print(survey_terrain(Path(args.directory).expanduser().resolve()))
    return 0


def cmd_update_stage(args) -> int:
    body_path = Path(args.body_file).expanduser().resolve()
    body = body_path.read_text(encoding="utf-8")
    result = Store(resolve_data(args.data)).update_stage(
        args.stage_id,
        body,
        mode=args.mode,
        expected_revision=args.expected_revision,
        actor=args.actor,
    )
    _print(result)
    return 0


def cmd_scan(args) -> int:
    _print(run_local_scan(
        Path(args.directory), refresh=args.refresh, agent=args.agent or "installed-agent"
    ))
    return 0


def cmd_apply_skeleton(args) -> int:
    _print(apply_skeleton(Path(args.directory), Path(args.skeleton)))
    return 0


def cmd_brief(args) -> int:
    data_path = resolve_data(args.data)
    root = data_path.parent.parent
    data = json.loads(data_path.read_text(encoding="utf-8"))
    anomalies_path = data_path.parent / "scan-anomalies.json"
    anomalies = scan_anomalies(root)
    anomalies_path.write_text(json.dumps(anomalies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print(build_briefing(data, anomalies, read_handoff(root)))
    return 0


def cmd_anomalies(args) -> int:
    root = Path(args.directory).expanduser().resolve()
    report = scan_anomalies(root)
    data_dir = root / ".turritopsis"
    if (data_dir / "stages.json").is_file():
        (data_dir / "scan-anomalies.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print(report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="turritopsis", description="Shared project truth and handoff over MCP")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create the recommended cognitive skeleton")
    init.add_argument("directory", nargs="?", default=".")
    init.add_argument("--name"); init.add_argument("--description"); init.add_argument("--yes", action="store_true")
    init.add_argument("--modules", help="Comma-separated project modules for non-scan initialization")
    init.add_argument("--scan", action="store_true")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)
    scan = sub.add_parser("scan", help="Create a local evidence snapshot without a model or network")
    scan.add_argument("directory", nargs="?", default=".")
    scan.add_argument("--refresh", action="store_true", help="Replace an existing evidence snapshot")
    scan.add_argument("--agent", help="Installed Agent recorded in scan-run.json")
    scan.set_defaults(func=cmd_scan)
    apply_map = sub.add_parser("apply-skeleton", help="Validate an Agent-authored skeleton and create stages.json")
    apply_map.add_argument("skeleton")
    apply_map.add_argument("directory", nargs="?", default=".")
    apply_map.set_defaults(func=cmd_apply_skeleton)
    survey = sub.add_parser("survey", help="Report what would mislead a newcomer to this repository")
    survey.add_argument("directory", nargs="?", default=".")
    survey.set_defaults(func=cmd_survey)
    brief = sub.add_parser("brief", help="Handoff packet for an arriving agent: what is settled, what to read, what to ask")
    brief.add_argument("--data")
    brief.set_defaults(func=cmd_brief)
    anomalies = sub.add_parser("anomalies", help="Report machine-checkable disagreements between project layers")
    anomalies.add_argument("directory", nargs="?", default=".")
    anomalies.set_defaults(func=cmd_anomalies)
    add = sub.add_parser("add", help="Add an empty Stage")
    add.add_argument("current_id"); add.add_argument("stage_id"); add.add_argument("title"); add.add_argument("--data")
    add.set_defaults(func=cmd_add)
    update = sub.add_parser("update-stage", help="Replace or append a Stage body with revision protection")
    update.add_argument("stage_id")
    update.add_argument("--body-file", required=True, help="UTF-8 file containing the Stage body")
    update.add_argument("--expected-revision", required=True, help="Revision returned by get_stage")
    update.add_argument("--actor", required=True)
    update.add_argument("--mode", choices=("replace", "append"), default="replace")
    update.add_argument("--data")
    update.set_defaults(func=cmd_update_stage)
    current = sub.add_parser("add-current", help="Add a Current")
    current.add_argument("current_id"); current.add_argument("name"); current.add_argument("--glyph"); current.add_argument("--blurb"); current.add_argument("--data")
    current.set_defaults(func=cmd_add_current)
    server = sub.add_parser("serve", help="Serve the four MCP tools")
    server.add_argument("--stdio", action="store_true"); server.add_argument("--port", type=int, default=3013)
    server.add_argument("--host", default="127.0.0.1"); server.add_argument("--data")
    server.set_defaults(func=lambda args: serve(args.data, args.host, args.port, args.stdio) or 0)
    ui = sub.add_parser("ui", help="Open the local human Web UI server")
    ui.add_argument("--port", type=int, default=3013); ui.add_argument("--host", default="127.0.0.1"); ui.add_argument("--data")
    ui.set_defaults(func=lambda args: serve(args.data, args.host, args.port, False) or 0)
    maintain = sub.add_parser("maintain", help="Maintain affected Stages from traceable project evidence")
    maintain.add_argument("--data"); maintain.add_argument("--model")
    maintain.add_argument("--max-age-days", type=int, default=30)
    maintain.add_argument("--proposal-only", action="store_true", help="Write a review proposal without LLM maintenance")
    maintain.add_argument("--apply"); maintain.add_argument("--actor")
    scheduling = maintain.add_mutually_exclusive_group()
    scheduling.add_argument("--schedule", metavar="CRON", help="Install or replace this project's user crontab entry")
    scheduling.add_argument("--show-schedule", action="store_true", help="Show this project's managed crontab entry")
    scheduling.add_argument("--unschedule", action="store_true", help="Remove this project's managed crontab entry")
    maintain.set_defaults(func=cmd_maintain)
    export = sub.add_parser("export", help="Export all project knowledge")
    export.add_argument("--format", choices=("md", "json"), default="md")
    export.add_argument("--output"); export.add_argument("--data")
    export.set_defaults(func=cmd_export)
    return parser


def main(argv=None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.func(args) or 0)
    except RevisionConflict as error:
        print(
            f"error: revision conflict: requested {error.requested}, "
            f"current revision {error.current}",
            file=sys.stderr,
        )
        return 3
    except (FileNotFoundError, FileExistsError, KeyError, ValueError, LLMError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

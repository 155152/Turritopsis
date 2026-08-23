from __future__ import annotations

import hashlib
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def _schedule_id(data_path: Path) -> str:
    return hashlib.sha256(str(data_path.resolve()).encode("utf-8")).hexdigest()[:12]


def _markers(data_path: Path) -> tuple[str, str]:
    schedule_id = _schedule_id(data_path)
    return (f"# BEGIN TURRITOPSIS {schedule_id}", f"# END TURRITOPSIS {schedule_id}")


def _validate_cron(expression: str) -> str:
    if "\n" in expression or "\r" in expression:
        raise ValueError("--schedule must be a five-field cron expression, for example '0 3 * * *'")
    expression = " ".join(expression.split())
    if len(expression.split()) != 5:
        raise ValueError("--schedule must be a five-field cron expression, for example '0 3 * * *'")
    return expression


def _command(data_path: Path, model: str | None, max_age_days: int) -> str:
    executable = shutil.which("turritopsis")
    argv = ([executable] if executable else [sys.executable, "-m", "turritopsis.cli"])
    argv += ["maintain", "--data", str(data_path.resolve()),
             "--max-age-days", str(max_age_days), "--actor", "scheduled-maintenance"]
    if model:
        argv += ["--model", model]
    project_root = data_path.resolve().parent.parent
    log_path = data_path.resolve().parent / "maintenance-cron.log"
    return f"cd {shlex.quote(str(project_root))} && {shlex.join(argv)} >> {shlex.quote(str(log_path))} 2>&1"


def _require_cron() -> None:
    if platform.system() == "Windows" or not shutil.which("crontab"):
        raise ValueError("crontab is unavailable on this host; install the schedule on a POSIX project host")


def _read_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return result.stdout
    if "no crontab" in result.stderr.lower():
        return ""
    raise ValueError(f"Unable to read crontab: {result.stderr.strip() or result.returncode}")


def _without_managed_block(content: str, data_path: Path) -> str:
    begin, end = _markers(data_path)
    lines = content.splitlines()
    output: list[str] = []
    inside = False
    found_end = False
    for line in lines:
        if line == begin:
            inside = True
            found_end = False
            continue
        if inside and line == end:
            inside = False
            found_end = True
            continue
        if not inside:
            output.append(line)
    if inside and not found_end:
        raise ValueError(f"Malformed managed crontab block: missing {end}")
    return "\n".join(output).strip()


def _write_crontab(content: str) -> None:
    payload = content.rstrip() + ("\n" if content.strip() else "")
    result = subprocess.run(["crontab", "-"], input=payload, text=True,
                            capture_output=True, check=False)
    if result.returncode != 0:
        raise ValueError(f"Unable to write crontab: {result.stderr.strip() or result.returncode}")


def install_schedule(data_path: Path, expression: str, model: str | None,
                     max_age_days: int) -> dict:
    _require_cron()
    expression = _validate_cron(expression)
    existing = _read_crontab()
    retained = _without_managed_block(existing, data_path)
    begin, end = _markers(data_path)
    block = "\n".join((begin, f"{expression} {_command(data_path, model, max_age_days)}", end))
    _write_crontab("\n\n".join(item for item in (retained, block) if item))
    return {"installed": True, "schedule": expression, "data": str(data_path.resolve()),
            "model": model or "configured default", "marker": begin.removeprefix("# BEGIN ")}


def remove_schedule(data_path: Path) -> dict:
    _require_cron()
    existing = _read_crontab()
    retained = _without_managed_block(existing, data_path)
    removed = retained.strip() != existing.strip()
    if removed:
        _write_crontab(retained)
    return {"removed": removed, "data": str(data_path.resolve())}


def show_schedule(data_path: Path) -> dict:
    _require_cron()
    begin, end = _markers(data_path)
    lines = _read_crontab().splitlines()
    inside = False
    block: list[str] = []
    for line in lines:
        if line == begin:
            inside = True
            continue
        if inside and line == end:
            return {"installed": True, "data": str(data_path.resolve()), "entry": block[0] if block else ""}
        if inside:
            block.append(line)
    return {"installed": False, "data": str(data_path.resolve()), "entry": None}

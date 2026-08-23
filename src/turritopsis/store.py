from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .revisions import revision


_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


class RevisionConflict(RuntimeError):
    def __init__(self, requested: str, current: str, stage: dict[str, Any]):
        super().__init__(f"revision conflict: requested {requested}, current {current}")
        self.requested = requested
        self.current = current
        self.stage = stage


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _thread_lock(path):
        handle = open(lock_path, "a+b")
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(handle.fileno()).st_size == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            acquired = True
            yield
        finally:
            if acquired:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()


class Store:
    def __init__(self, data_path: str | os.PathLike[str]):
        self.path = Path(data_path).resolve()
        self.root = self.path.parent

    def load(self) -> dict[str, Any]:
        with self.path.open(encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def currents(data: dict[str, Any]) -> list[dict[str, Any]]:
        return data.get("currents", [])

    @classmethod
    def find_current(cls, data: dict[str, Any], current_id: str) -> dict[str, Any] | None:
        return next((c for c in cls.currents(data) if c.get("id") == current_id), None)

    @classmethod
    def find_stage(cls, data: dict[str, Any], stage_id: str):
        for current in cls.currents(data):
            for stage in current.get("stages", []):
                if stage.get("id") == stage_id:
                    return current, stage
        return None, None

    def _atomic_write(self, data: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".stages-", suffix=".json.tmp", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            for attempt in range(8):
                try:
                    os.replace(temp_name, self.path)
                    break
                except PermissionError:
                    if attempt == 7:
                        raise
                    time.sleep(0.025 * (attempt + 1))
            if os.name != "nt":
                directory_fd = os.open(self.root, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            if os.path.exists(temp_name):
                for attempt in range(4):
                    try:
                        os.unlink(temp_name)
                        break
                    except PermissionError:
                        if attempt == 3:
                            raise
                        time.sleep(0.025 * (attempt + 1))

    def _backup(self) -> Path:
        directory = self.root / "backups"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        target = directory / f"stages-{stamp}.json"
        shutil.copy2(self.path, target)
        backups = sorted(directory.glob("stages-*.json"), key=lambda p: p.stat().st_mtime)
        for old in backups[:-20]:
            old.unlink(missing_ok=True)
        return target

    def update_stage(self, stage_id: str, body: str, mode: str = "replace",
                     expected_revision: str | None = None, actor: str = "unknown") -> dict[str, Any]:
        mode = mode.lower().strip()
        if mode not in {"replace", "append"}:
            raise ValueError("mode must be replace or append")
        with _locked(self.path):
            data = self.load()
            current, stage = self.find_stage(data, stage_id)
            if not stage:
                raise KeyError(f"Unknown stage: {stage_id}")
            before_body = str(stage.get("body") or "")
            before_revision = revision(before_body)
            if expected_revision and expected_revision != before_revision:
                raise RevisionConflict(expected_revision, before_revision, stage.copy())
            new_body = body or ""
            if mode == "append" and before_body.strip():
                new_body = before_body.rstrip() + "\n\n" + new_body.lstrip()
            after_revision = revision(new_body)
            if new_body == before_body:
                return {"changed": False, "stage_id": stage_id, "revision": before_revision}
            backup = self._backup()
            stage["body"] = new_body
            data["version"] = int(data.get("version", 0)) + 1
            self._atomic_write(data)
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor": actor or "unknown",
                "stage_id": stage_id,
                "mode": mode,
                "before_revision": before_revision,
                "after_revision": after_revision,
                "backup": backup.relative_to(self.root).as_posix(),
            }
            changelog = self.root / "changelog.jsonl"
            with changelog.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return {"changed": True, "current": current.get("id"), **record}

    def mutate_structure(self, mutator, actor: str = "cli") -> Any:
        with _locked(self.path):
            data = self.load()
            result = mutator(data)
            self._backup()
            data["version"] = int(data.get("version", 0)) + 1
            self._atomic_write(data)
            return result

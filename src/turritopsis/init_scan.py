from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .anomalies import detect
from .structure import structure_map


MANIFESTS = {
    "pyproject.toml", "package.json", "Cargo.toml", "go.mod", "pom.xml",
    "build.gradle", "build.gradle.kts", "composer.json", "Gemfile",
    "Dockerfile", "compose.yml", "compose.yaml",
}
MATERIAL_NAMES = MANIFESTS | {"AGENTS.md", "CLAUDE.md", "Makefile"}

# Evidence is not ranked on one axis of importance. A manifest is hard fact about
# runtime and dependencies and says nothing about why the project exists; a
# CONTRIBUTING file is authoritative about how work is done here and is not a
# ruling on what the code currently is. Each role answers a different question, so
# each role gets its own budget and its own line in the prompt.
ORIENTATION_NAMES = {"architecture", "overview", "design", "whitepaper", "roadmap"}
CONVENTION_NAMES = {
    "agents.md", "claude.md", "contributing.md", "code_of_conduct.md",
    "conventions.md", "style.md", "development.md", "hacking.md",
}
HISTORY_NAMES = {"changelog", "changes", "history", "news", "releases", "release-notes"}
HISTORY_DIRS = {"adr", "decisions", "migrations", "changelog.d", "rfcs"}
DOC_DIRS = {"docs", "doc", "documentation", "specs", "spec", "design", "notes"}


def _evidence_role(path: Path, relative: Path) -> str:
    name = path.name.lower()
    stem = path.stem.lower()
    parts = {part.lower() for part in relative.parts[:-1]}
    if _is_archaeology(relative) or STALE_FILE_MARKERS.search(path.name):
        return "sediment"
    if name in CONVENTION_NAMES:
        return "convention"
    if stem in HISTORY_NAMES or parts & HISTORY_DIRS:
        return "history"
    if path.name in MANIFESTS or path.name == "Makefile" or ".github" in relative.parts:
        return "manifest"
    if path.suffix.lower() in CODE_SUFFIXES:
        return "source"
    # Any remaining prose is describing the project to a reader; that is what
    # orientation means. Ordering inside the role still puts README first.
    if name.startswith("readme") or stem in ORIENTATION_NAMES or parts & DOC_DIRS:
        return "orientation"
    return "orientation" if path.suffix.lower() in DOC_SUFFIXES else "other"


# Prose budget split by role. Orientation decides what the project is, so it is
# read first and most; history feeds the genesis/timeline Currents that nothing
# else can supply.
ROLE_BUDGETS = {
    "orientation": 9000,
    "manifest": 5000,
    "convention": 4000,
    "history": 5000,
}
ROLE_GUIDANCE = {
    "orientation": "what the project is, its scope and entry points — the primary source for naming Currents",
    "manifest": "hard evidence about runtime, dependencies, entry points and deployment",
    "convention": "how work is done here: constraints, review habits, red lines. Authoritative about intent, but it can lag the code — never treat it as a ruling on current behaviour",
    "history": "why the project became what it is — the primary source for a timeline or genesis Current",
    "sediment": "superseded copies and retired directories. Never authoritative about current behaviour; useful only as evidence that something changed",
}
CODE_SUFFIXES = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go",
    ".java", ".kt", ".rb", ".php", ".sh", ".ps1", ".sql",
}
DOC_SUFFIXES = {".md", ".rst", ".txt"}
DATA_SUFFIXES = {".toml", ".json", ".yaml", ".yml"}
TEXT_SUFFIXES = CODE_SUFFIXES | DOC_SUFFIXES | DATA_SUFFIXES
# A directory holding this many files that share one filename pattern is holding
# runtime output, not project structure.
COLLAPSE_THRESHOLD = 5
SKIP_DIRS = {
    ".git", ".turritopsis", "node_modules", ".venv", "venv", "dist", "build",
    "target", "vendor", "__pycache__", ".pytest_cache", ".mypy_cache",
}
# Long-running projects accumulate an archaeological layer: dated backups, retired
# code, one-off deploy snapshots. It is real history, but it is not what the project
# *is* now, and it drowns the live tree. Matched case-insensitively against directory
# names, so "backups-closeout-20260719" and ".deploy-recall-v3" are both excluded.
SKIP_DIR_PREFIXES = (
    "backup", "backups", "_backup", ".backup",
    "archive", "_archive", ".archive",
    "_dead", "_retired", "_old", "_deprecated", "_legacy", "_disabled",
    ".tmp-", ".deploy-", ".bak", "_bak",
)
# Same idea at file level: superseded copies of files that still exist for real.
STALE_FILE_MARKERS = re.compile(
    r"(\.orig$|\.rej$|\.bak\b|\.bak-|\.backup\b|~$"
    r"|^_bak|^_old_|^_dead_|^_retired|\bcopy\b"
    r"|\.\d{8}[-.]\d{4,6}\b|-\d{8}-\d{6}\b|\.pre-[a-z0-9-]+$)",
    re.I,
)
SENSITIVE_TOKENS = {
    "secret", "credential", "token", "private", "apikey", "api_key",
    "key", "passwd", "password", "cred", "keystore",
}
SOURCE_ROOT_DIRS = {"src", "lib", "python"}
SENSITIVE_SUFFIXES = (".lock", ".pem", ".key", ".pfx", ".p12", ".jks", ".keystore", ".crt")
# Filename rules are a first line, not the line. A file named youkies_key.txt gets
# caught by the name; one named notes.txt holding the same string does not. Since
# this scanner exists to ship file contents to a third-party model, the contents
# get checked too — one match and the whole file is dropped, never redacted, so a
# near-miss on the pattern cannot leak the rest of the line.
CREDENTIAL_SHAPES = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}"
    r"|gh[pousr]_[A-Za-z0-9]{16,}"
    r"|AKIA[0-9A-Z]{12,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."
    r"|(?i:aws_secret_access_key|client_secret|private_key)\s*[:=]\s*\S{8,})"
)


def looks_like_credential(content: str) -> bool:
    return CREDENTIAL_SHAPES.search(content) is not None
MAX_TREE_FILES = 3000
MAX_MATERIALS = 40
# A source file's opening is its densest region: docstring, imports, top-level
# definitions. Reading 4k from many files maps a project better than 12k from three.
MAX_FILE_CHARS = 4000
MAX_TOTAL_CHARS = 70000
# Prose gets a minority share; the rest maps declarations across the whole codebase.
MAX_PROSE_CHARS = 20000


SKELETON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "currents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "blurb": {"type": "string"},
                    "stages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "title": {"type": "string"},
                                "purpose": {"type": "string"},
                                "search_hints": {"type": "string"},
                                "authority": {"type": "string"},
                                "evidence_paths": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["id", "title", "purpose", "search_hints", "authority", "evidence_paths"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["id", "name", "blurb", "stages"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["currents"],
    "additionalProperties": False,
}


def _is_archaeology(relative: Path) -> bool:
    """True when a path lives under a backup/archive/retired/deploy-snapshot directory."""
    for part in relative.parts[:-1]:
        lowered = part.lower()
        if lowered.startswith(SKIP_DIR_PREFIXES):
            return True
    return False


# Only the OpenAI /responses path sends SKELETON_SCHEMA to the model as an enforced
# json_schema. The anthropic and openai-compatible paths ask for "a JSON object" and
# nothing more, so the shape has to be stated in the prompt or the model has to guess
# it — and it guesses the Stage shape, because that is all the prompt described.
OUTPUT_CONTRACT = """
Return exactly this JSON shape:

{"currents": [
  {"id": "lowercase_ascii", "name": "Human readable name", "blurb": "One line on what this Current covers",
   "stages": [
     {"id": "<current_id>.topic", "title": "...", "purpose": "...",
      "search_hints": "space separated keywords", "authority": "what this Stage is the authority on",
      "evidence_paths": ["path/from/the/supplied/tree"]}
   ]}
]}

Every Current object must have all four keys: id, name, blurb, stages.
Every Stage object must have all six keys: id, title, purpose, search_hints, authority, evidence_paths.
No other keys are allowed anywhere.
"""


def _safe_file(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    lowered = {part.lower() for part in relative.parts}
    if lowered & {item.lower() for item in SKIP_DIRS}:
        return False
    if _is_archaeology(relative) or STALE_FILE_MARKERS.search(path.name):
        return False
    name = path.name.lower()
    if name.startswith(".env") or name.endswith(SENSITIVE_SUFFIXES):
        return False
    # Source reaches the model only as declarations and is content-scanned again
    # before outlining. Do not hide legitimate modules named token.py or password.py.
    if path.suffix.lower() in CODE_SUFFIXES:
        return True
    # Match filename/path components, not arbitrary substrings. Substring matching
    # classified auth.py, authentication.py, keyboard.py and monkey.py as secrets.
    for component in relative.parts:
        tokens = {token for token in re.split(r"[^a-z0-9]+", component.lower()) if token}
        if tokens & SENSITIVE_TOKENS:
            return False
    return True


def _tier(path: Path) -> int:
    if path.name.lower().startswith("readme"):
        return 0
    if path.name in MATERIAL_NAMES:
        return 1
    if ".github" in path.parts:
        return 2
    suffix = path.suffix.lower()
    if suffix in CODE_SUFFIXES:
        return 3
    return 4 if suffix in DOC_SUFFIXES else 5


_IMPORT = re.compile(r"^\s*(?:from|import)\s+([\w.]+)|require\([\"']([\w./]+)", re.M)
# Nothing imports an entry point, but an entry point is where a project starts.
ENTRY_STEMS = {"main", "__main__", "cli", "app", "server", "index", "run", "manage"}
ENTRY_BONUS = 5
IMPORT_SCAN_CHARS = 20000


def _python_modules(files: list[Path], root: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    """Index Python modules by dotted path, with unique-stem fallback for flat repos."""
    modules: dict[str, Path] = {}
    by_stem: dict[str, list[Path]] = {}
    for path in files:
        if path.suffix.lower() not in {".py", ".pyi"}:
            continue
        relative = path.relative_to(root).with_suffix("")
        parts = list(relative.parts)
        if parts and parts[-1] == "__init__":
            parts.pop()
        if parts:
            modules[".".join(parts)] = path
            if parts[0].lower() in SOURCE_ROOT_DIRS and len(parts) > 1:
                modules[".".join(parts[1:])] = path
        by_stem.setdefault(path.stem, []).append(path)
    unique = {stem: paths[0] for stem, paths in by_stem.items() if len(paths) == 1}
    return modules, unique


def _resolve_python_import(
    importer: Path, token: str, root: Path, modules: dict[str, Path], unique: dict[str, Path]
) -> Path | None:
    if token.startswith("."):
        level = len(token) - len(token.lstrip("."))
        package = list(importer.relative_to(root).with_suffix("").parts[:-1])
        package = package[:max(0, len(package) - level + 1)]
        suffix = token.lstrip(".")
        candidate = ".".join(package + ([suffix] if suffix else []))
    else:
        candidate = token
    if candidate in modules:
        return modules[candidate]
    return unique.get(candidate.rsplit(".", 1)[-1]) if "." not in candidate else None


def _import_graph(files: list[Path], root: Path | None = None) -> tuple[dict[Path, str], dict[Path, set[Path]], set[str]]:
    """Read every source file once and return its text, its edges, and manifest deps."""
    sources: dict[Path, str] = {}
    root = (root or (Path(os.path.commonpath([str(path.parent) for path in files])) if files else Path.cwd())).resolve()
    for path in files:
        if path.suffix.lower() not in CODE_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if looks_like_credential(text):
            continue
        sources[path] = text
    modules, unique = _python_modules(list(sources), root)
    edges: dict[Path, set[Path]] = {}
    for path, text in sources.items():
        targets = set()
        for match in _IMPORT.finditer(text[:IMPORT_SCAN_CHARS]):
            token = match.group(1) or match.group(2) or ""
            target = _resolve_python_import(path, token, root, modules, unique)
            if target is not None and target != path:
                targets.add(target)
        edges[path] = targets

    requirements: set[str] = set()
    for path in files:
        if path.name == "pyproject.toml":
            body = path.read_text(encoding="utf-8", errors="replace")
            block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", body, re.S | re.M)
            if block:
                requirements |= {
                    match.group(1) for match in
                    re.finditer(r"[\"']([A-Za-z][\w.-]*)", block.group(1))
                }
        elif path.name == "package.json":
            try:
                document = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except (json.JSONDecodeError, OSError):
                continue
            requirements |= set(document.get("dependencies", {}))
    return sources, edges, requirements


def _import_counts(files: list[Path], root: Path | None = None) -> dict[Path, int]:
    """Rank source files by how often the rest of the project imports them.

    Recency is a biased proxy for importance: a one-off migration script edited
    yesterday looks newer than the module every other file depends on. Inbound
    imports say which files the project is actually built out of.
    """
    code = [path for path in files if path.suffix.lower() in CODE_SUFFIXES]
    if not code:
        return {}
    root = (root or Path(os.path.commonpath([str(path.parent) for path in code]))).resolve()
    modules, unique = _python_modules(code, root)
    counts: dict[Path, int] = {path: ENTRY_BONUS if path.stem in ENTRY_STEMS else 0 for path in code}
    for path in code:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:IMPORT_SCAN_CHARS]
        except OSError:
            continue
        if looks_like_credential(text):
            continue
        for match in _IMPORT.finditer(text):
            token = match.group(1) or match.group(2) or ""
            target = _resolve_python_import(path, token, root, modules, unique)
            if target is not None and target != path:
                counts[target] = counts.get(target, 0) + 1
    return counts


_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def _path_pattern(relative: Path) -> str:
    """Normalise ids out of the whole path, not just the filename.

    Two shapes of runtime output look different but mean the same thing:
    many files in one directory (pending/pc_<hash>.json), and one file each in
    many directories (by-window/<uuid>/compaction.md). Normalising the full path
    collapses both.
    """
    # UUIDs first: their 4-character groups are neither long enough for the hex
    # rule nor purely numeric, so piecewise normalisation leaves them distinct.
    flattened = _UUID.sub("#", relative.as_posix().lower())
    return re.sub(r"[0-9a-f]{8,}|\d+", "#", flattened)


def _collapse_generated(files: list[Path], root: Path) -> tuple[list[Path], list[tuple[str, int]]]:
    """Keep one representative per repeated filename pattern within a directory.

    A directory holding 437 files named pc_<hash>.json is runtime output, not
    structure. Reading three of them teaches the same thing as reading all of
    them, and reading all of them costs the whole character budget.
    """
    groups: dict[str, list[Path]] = {}
    for path in files:
        groups.setdefault(_path_pattern(path.relative_to(root)), []).append(path)
    kept: list[Path] = []
    collapsed: list[tuple[str, int]] = []
    for pattern, group in groups.items():
        if len(group) >= COLLAPSE_THRESHOLD:
            group.sort(key=lambda p: -p.stat().st_mtime)
            kept.append(group[0])
            collapsed.append((pattern, len(group)))
        else:
            kept.extend(group)
    collapsed.sort(key=lambda item: -item[1])
    return kept, collapsed


def _rank_materials(files: list[Path], root: Path) -> tuple[list[Path], dict[Path, int]]:
    """Order files so the sample describes the live project, not its biggest folder.

    Manifests and docs come first, then source files interleaved round-robin across
    top-level areas so one crowded package cannot spend the whole character budget
    while sibling subsystems go unseen. Docs and data files queue behind all source
    code. Within an area, recently touched files win — live code keeps getting
    edited, sediment does not.
    """
    live = [path for path in files if not STALE_FILE_MARKERS.search(path.name)]
    live, _ = _collapse_generated(live, root)
    imports = _import_counts(live, root)
    front = sorted((p for p in live if _tier(p) < 3),
                   key=lambda p: (_tier(p), len(p.parts), p.as_posix()))

    areas: dict[str, list[Path]] = {}
    for path in live:
        if _tier(path) < 3:
            continue
        relative = path.relative_to(root)
        area = relative.parts[0] if len(relative.parts) > 1 else ""
        areas.setdefault(area, []).append(path)

    for group in areas.values():
        group.sort(key=lambda p: (_tier(p), -imports.get(p, 0), -p.stat().st_mtime,
                                  len(p.parts), p.as_posix()))

    # Root-level files describe the project as a whole, so let that area go first.
    order = sorted(areas, key=lambda name: (name != "", name))
    interleaved: list[Path] = []
    for index in range(max((len(group) for group in areas.values()), default=0)):
        for name in order:
            group = areas[name]
            if index < len(group):
                interleaved.append(group[index])
    # Source code first across every area, then docs, then everything else.
    interleaved.sort(key=lambda p: _tier(p))
    return front + interleaved, imports


MAX_SEDIMENT_SAMPLES = 12


def _sediment_digest(root: Path) -> dict[str, Any]:
    """Summarise the archaeological layer without letting it into the evidence body.

    Excluding sediment entirely throws away the only record of what a project used
    to be — the raw material for a timeline or genesis Current. Including its
    contents lets superseded code be read as current, and teaches the model to
    invent more filenames in the same shape. So: counts and paths, never bodies,
    and always labelled as historical.
    """
    dated: list[str] = []
    areas: dict[str, int] = {}
    total = 0
    for path in sorted(root.rglob("*")):
        if total >= MAX_TREE_FILES * 4:
            break
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if {part.lower() for part in relative.parts} & {item.lower() for item in SKIP_DIRS}:
            continue
        if _is_archaeology(relative):
            top = next((part for part in relative.parts[:-1]
                        if part.lower().startswith(SKIP_DIR_PREFIXES)), relative.parts[0])
            areas[top] = areas.get(top, 0) + 1
            total += 1
        elif STALE_FILE_MARKERS.search(path.name):
            dated.append(relative.as_posix())
            total += 1
    return {
        "note": ROLE_GUIDANCE["sediment"],
        "total_files": total,
        "retired_areas": sorted(areas.items(), key=lambda item: -item[1])[:MAX_SEDIMENT_SAMPLES],
        "dated_copies": len(dated),
        "dated_copy_samples": sorted(dated)[:MAX_SEDIMENT_SAMPLES],
    }


def scan_project(root: Path) -> dict[str, Any]:
    """Collect bounded, reviewable project evidence for LLM classification."""
    root = root.resolve()
    files = []
    for path in sorted(root.rglob("*")):
        if len(files) >= MAX_TREE_FILES:
            break
        if path.is_file() and _safe_file(path, root):
            files.append(path)
    tree = [path.relative_to(root).as_posix() for path in files]
    candidates, imports = _rank_materials(files, root)
    # Prose is read in full within its role's budget: a README argues, and an
    # outline of an argument is worthless. Source is outlined instead — what a file
    # declares is what the scan needs, and it compresses about ten to one.
    prose = [
        (path, _evidence_role(path, path.relative_to(root)))
        for path in candidates
        if path.suffix.lower() in DOC_SUFFIXES | DATA_SUFFIXES or path.name in MATERIAL_NAMES
    ]
    prose = [(path, role) for path, role in prose if role in ROLE_BUDGETS]

    materials: list[dict[str, str]] = []
    spent = {role: 0 for role in ROLE_BUDGETS}
    taken: set[Path] = set()

    def _take(path: Path, role: str, allowance: int) -> None:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_CHARS]
        except OSError:
            return
        if not content.strip() or looks_like_credential(content):
            taken.add(path)
            return
        content = content[:allowance]
        materials.append({"role": role, "path": path.relative_to(root).as_posix(), "content": content})
        spent[role] += len(content)
        taken.add(path)

    # Each role first gets its own share, so a project with one CHANGELOG does not
    # lose it to fifty design notes.
    for path, role in prose:
        if len(materials) >= MAX_MATERIALS or spent[role] >= ROLE_BUDGETS[role]:
            continue
        _take(path, role, ROLE_BUDGETS[role] - spent[role])
    # A project without manifests or a changelog should not forfeit that budget.
    for path, role in prose:
        remaining = MAX_PROSE_CHARS - sum(spent.values())
        if len(materials) >= MAX_MATERIALS or remaining <= 0:
            break
        if path not in taken:
            _take(path, role, remaining)

    ranked = [(path, path.relative_to(root).as_posix(), imports.get(path, 0))
              for path in candidates if path.suffix.lower() in CODE_SUFFIXES]
    outline, coverage = structure_map(ranked, MAX_TOTAL_CHARS - sum(spent.values()))
    return {
        "root_name": root.name,
        "tree": tree,
        "evidence_roles": {role: ROLE_GUIDANCE[role] for role in ROLE_GUIDANCE},
        "materials": materials,
        "structure_map": outline,
        "structure_coverage": {**coverage, "code_files_found": len(ranked)},
        "sediment": _sediment_digest(root),
    }


_MAIN_BLOCK = re.compile(r"^if\s+__name__\s*==\s*[\"']__main__[\"']", re.M)


def _is_runnable(path: Path) -> bool:
    """A service entry point or cron script has no importers, and that is fine."""
    if path.suffix.lower() in {".sh", ".ps1"}:
        return True
    try:
        return bool(_MAIN_BLOCK.search(path.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return False


def scan_anomalies(root: Path) -> dict[str, Any]:
    """Cross-layer disagreements, written beside the knowledge base and never into it."""
    root = root.resolve()
    files = []
    for path in sorted(root.rglob("*")):
        if len(files) >= MAX_TREE_FILES:
            break
        if path.is_file() and _safe_file(path, root):
            files.append(path)
    # The graph is built from every file: an import graph missing five of six
    # callers reports a load-bearing module as unused. Prose is read from the
    # collapsed set instead, because 460 generated window summaries are not 460
    # project documents — counting them as documentation would both flood the
    # citation check and let a module look documented because a log mentioned it.
    sources, edges, requirements = _import_graph(files, root)
    counts = _import_counts(files, root)
    collapsed, _ = _collapse_generated(files, root)
    prose = {}
    for path in collapsed:
        if path.suffix.lower() in DOC_SUFFIXES or path.name in MATERIAL_NAMES:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_CHARS]
            except OSError:
                continue
            if not looks_like_credential(text):
                prose[path] = text
    live_tree = {path.relative_to(root).as_posix() for path in files}
    findings = detect(root, sources, counts, edges, prose, requirements, live_tree)
    grouped: dict[str, int] = {}
    for item in findings:
        grouped[item["kind"]] = grouped.get(item["kind"], 0) + 1
    return {
        "note": "Machine-checkable disagreements between layers. Leads for review, "
                "not project facts — never merge these into Stage bodies.",
        "scanned_sources": len(sources),
        "counts": dict(sorted(grouped.items(), key=lambda item: -item[1])),
        "findings": findings,
    }


def survey_terrain(root: Path) -> dict[str, Any]:
    """Report what a newcomer would trip over before they trip over it.

    This is not a linter. It answers one question — "what in this repository
    will mislead someone who has never seen it?" — because that is exactly what
    a fresh agent walks into on its first turn.
    """
    root = root.resolve()
    everything: list[Path] = []
    for path in sorted(root.rglob("*")):
        if len(everything) >= MAX_TREE_FILES * 4:
            break
        relative_parts = path.relative_to(root).parts
        if {part.lower() for part in relative_parts} & {item.lower() for item in SKIP_DIRS}:
            continue
        if path.is_file():
            everything.append(path)

    buried: dict[str, int] = {}
    stale: list[str] = []
    live: list[Path] = []
    for path in everything:
        relative = path.relative_to(root)
        if _is_archaeology(relative):
            top = next((part for part in relative.parts[:-1]
                        if part.lower().startswith(SKIP_DIR_PREFIXES)), relative.parts[0])
            buried[top] = buried.get(top, 0) + 1
        elif STALE_FILE_MARKERS.search(path.name):
            stale.append(relative.as_posix())
        else:
            live.append(path)

    _, generated = _collapse_generated(live, root)
    imports = _import_counts(live, root)
    unreferenced = sorted(
        path.relative_to(root).as_posix() for path, count in imports.items()
        if count == 0 and path.stem not in ENTRY_STEMS
        and not path.stem.startswith("test") and not _is_runnable(path)
    )
    shadowed = sorted({
        name.split(".bak")[0].split(".orig")[0].rstrip(".")
        for name in stale
    } & {path.relative_to(root).as_posix() for path in live})

    return {
        "live_files": len(live),
        "buried_files": sum(buried.values()),
        "buried_areas": sorted(buried.items(), key=lambda item: -item[1])[:10],
        "stale_copies": len(stale),
        "shadowed_originals": shadowed[:10],
        "generated_clusters": generated[:10],
        "unreferenced_sources": unreferenced,
    }


# A scan classifies what it can see, and it can only see code, so it produces
# Currents shaped like the codebase and none shaped like the knowledge that was
# never committed. Without these three, an agent that later learns why a design
# won, what must not be deleted, or what has to be done by hand has nowhere to
# put it — and the map silently becomes code-only forever. Guaranteed in code
# rather than requested in the prompt, because a structural guarantee should not
# depend on a model complying.
HUMAN_KNOWLEDGE_CURRENTS = [
    ("genesis", "Why it became this", "Decisions, rejected paths, incidents, and history",
     "why this design won, which alternatives were tried and rejected, what incidents shaped it"),
    ("bounds", "What must hold", "Contracts, permissions, invariants, and red lines",
     "what must never change without sign-off, what looks unused but must not be deleted"),
    ("manual", "How to operate it", "Deploy, diagnose, restore, and manual procedures",
     "what to check first when it breaks, what still has to be done by hand"),
]


def _human_knowledge_currents(existing: set[str]) -> list[dict[str, Any]]:
    currents = []
    for current_id, name, blurb, needs in HUMAN_KNOWLEDGE_CURRENTS:
        if current_id in existing:
            continue
        body = (
            f"# {name} overview\n\n"
            f"Purpose: Route questions about {blurb.lower()}.\n"
            f"Search hints: {current_id} {name.lower().replace(' ', ' ')}\n"
            "Summary: [Placeholder: not recoverable from the repository — ask the people who built it.]\n"
            "Verified: not yet verified\n"
            "Status: unresolved\n"
            f"Authority: {blurb}\n\n"
            "## Knowledge\n\n"
            f"[Placeholder: needs {needs}. A scan cannot supply this; it was never written down.]\n"
        )
        currents.append({
            "id": current_id, "name": name, "blurb": blurb,
            "stages": [{"id": f"{current_id}.overview", "title": f"{name} overview", "body": body}],
        })
    return currents


def _valid_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_-]*", value))


def _stage_body(stage: dict[str, Any]) -> str:
    paths = [str(path) for path in stage.get("evidence_paths", [])]
    evidence = "\n".join(f"- `{path}`" for path in paths) or "- [Placeholder: add an evidence path]"
    authority = stage.get("authority", "") or "unassigned"
    return (
        f"# {stage['title']}\n\n"
        f"Purpose: {stage['purpose']}\n"
        f"Search hints: {stage['search_hints']}\n"
        "Summary: [Placeholder: verify and describe this knowledge region.]\n"
        "Verified: not yet verified\n"
        "Status: unresolved\n"
        f"Authority: {authority}\n\n"
        "## Knowledge\n\n"
        "[Placeholder: fill from verified project evidence.]\n\n"
        "## Evidence to review\n\n"
        f"{evidence}\n"
    )


def generate_skeleton(
    root: Path,
    title: str,
    subtitle: str,
    client,
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = scan_project(root)
    prompt = (
        "Classify this long-running software project into 3-5 durable repository-derived knowledge Currents. "
        "The local program separately guarantees genesis, bounds, and manual Currents, so do not add filler. "
        "Create addressable Stage skeletons, not a code index. Use only the supplied project tree and materials. "
        "Stage titles, purposes, search hints, authority scopes, and relevant evidence paths are allowed. "
        "Do not assert unverified project facts; canonical bodies will be created locally as placeholders. "
        "Every Stage id must be current_id.topic, lowercase ASCII, and every evidence path must appear in the supplied tree.\n"
        "\nEVIDENCE FORMAT. 'tree' lists the bounded live-file sample used by this scan. Each entry in 'materials' "
        "carries a 'role', and 'evidence_roles' says what question that role can "
        "answer — the roles are not a ranking, they support different Currents. "
        "'structure_map' is a declaration outline of the source: each entry is a "
        "real file path, its inbound import count, and the classes and function "
        "signatures it declares; 'structure_coverage' states what fit in the budget. High import counts mark the modules the project is "
        "built out of; group Currents around those. The outline is not the source, "
        "so describe what a file is responsible for, never what its implementation "
        "does. 'sediment' is counts and paths only, for superseded and retired "
        "files: never cite it as evidence for current behaviour, but a large or "
        "dated sediment layer is itself evidence that a history Current is warranted.\n"
        + OUTPUT_CONTRACT +
        f"\nPROJECT EVIDENCE:\n{json.dumps(evidence, ensure_ascii=False)}"
    )
    result = client.complete_json(
        "You design conservative, evidence-routed project knowledge maps. You never invent canonical truth.",
        prompt, SKELETON_SCHEMA, "turritopsis_project_skeleton",
    )
    currents = result.get("currents", [])
    if not 3 <= len(currents) <= 5:
        raise ValueError("LLM skeleton must contain 3-5 repository-derived Currents")
    known_paths = set(evidence["tree"])
    seen_currents: set[str] = set()
    seen_stages: set[str] = set()
    invented: list[str] = []
    canonical_currents = []
    for current in currents:
        current_id = current["id"].strip()
        if not _valid_id(current_id) or current_id in seen_currents:
            raise ValueError(f"Invalid or duplicate Current id from LLM: {current_id}")
        seen_currents.add(current_id)
        canonical_stages = []
        for stage in current["stages"]:
            stage_id = stage["id"].strip()
            if not re.fullmatch(rf"{re.escape(current_id)}\.[a-z][a-z0-9_.-]*", stage_id) or stage_id in seen_stages:
                raise ValueError(f"Invalid or duplicate Stage id from LLM: {stage_id}")
            cited = list(dict.fromkeys(stage["evidence_paths"]))
            unknown = [path for path in cited if path not in known_paths]
            grounded = [path for path in cited if path in known_paths]
            if unknown and not grounded:
                raise ValueError(
                    f"LLM Stage {stage_id} cited only unknown evidence: {', '.join(sorted(unknown))}"
                )
            if unknown:
                # A model shown a tree full of xxx.py.bak-<date> files learns the
                # pattern and invents more of them. Drop the invented paths, keep
                # the Stage, and surface the count instead of failing the whole scan.
                invented.extend(f"{stage_id} -> {path}" for path in sorted(unknown))
                stage = {**stage, "evidence_paths": grounded}
            seen_stages.add(stage_id)
            canonical_stages.append({"id": stage_id, "title": stage["title"].strip(), "body": _stage_body(stage)})
        canonical_currents.append({
            "id": current_id, "name": current["name"].strip(),
            "blurb": current["blurb"].strip(), "stages": canonical_stages,
        })
    canonical_currents.extend(_human_knowledge_currents(seen_currents))
    if invented:
        evidence = {**evidence, "invented_evidence_paths": invented}
    return {
        "title": title, "subtitle": subtitle, "version": 1,
        "currents": canonical_currents,
    }, evidence

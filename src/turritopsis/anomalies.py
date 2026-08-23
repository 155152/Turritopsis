"""Cross-layer inconsistency detection.

What goes wrong in a long-running project is usually not a line of code being
wrong. It is that the layers have drifted out of agreement: the manifest declares
a dependency nothing imports, the README names an entry point that moved, a module
labelled legacy sits on the main path, a test covers a flow that no longer exists.
Each layer is self-consistent. The contradiction only exists between them, which
is why no single-file linter can see it.

Once a structure map exists these checks are nearly free — they are set operations
over data the scan already collected.

Everything here is a lead, not a fact, so it is written beside the knowledge base
and never into it. A Stage says what a module is responsible for and is meant to be
trusted; an anomaly says two layers disagree and is meant to be checked. Giving
them the same shelf would make the trustworthy half unusable. For the same reason
only machine-provable signals are emitted: every finding carries the paths, names
and values that produced it, so a reader can refute it without rerunning the scan.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Any

LEGACY_MARKERS = re.compile(r"(?i)\b(legacy|deprecated|obsolete|superseded|do not use)\b")
VERSION_SUFFIX = re.compile(r"^(?P<base>.+?)[._-]?(?:v\d+|\d+|new|old|next|copy|final)$", re.I)
HUB_THRESHOLD = 5
FORK_VALUE_TYPES = (ast.Constant,)
# Only words that promise something does not exist yet. "spec" and "design" were
# here first and silently swallowed CODEX_REVIEW_SPEC.md, which documents a system
# that shipped — an exemption that hides a true positive is worse than no exemption.
PLANNING_DOC = re.compile(r"(?i)(^|[_-])(plan|proposal|draft|todo|roadmap|wishlist)$")
PLACEHOLDER_PATH = re.compile(r"(?i)(path/to/|/your[-_]|<[^>]+>|example\.|foo\.|bar\.|\.\.\.)")
STALE_CITATION = re.compile(
    r"(?i)(^|/)(_?retired|_?dead|_?old|archive[ds]?|backups?|legacy)([._-]|/)")


def _module_constants(source: str) -> dict[str, str]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return {}
    constants: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                if isinstance(node.value, FORK_VALUE_TYPES):
                    try:
                        constants[target.id] = ast.unparse(node.value)
                    except Exception:  # pragma: no cover - unparse is total in 3.9+
                        continue
    return constants


def _same_thing_diverged(values: list[str]) -> bool:
    """Distinguish a forked definition from two modules that simply differ.

    Two modules each naming their own MODEL are not in conflict; they own separate
    settings that happen to share a variable name. But "memory_shadows" beside
    "memory_shadows_voyage4_1024" is one resource that grew a second version, and
    whichever module holds the older string is talking to the wrong place. The
    machine-checkable difference is a shared prefix.
    """
    literals = [value.strip("'\"") for value in values if value[:1] in "'\""]
    if len(literals) < 2:
        return False
    for index, first in enumerate(literals):
        for second in literals[index + 1:]:
            shorter, longer = sorted((first, second), key=len)
            if not shorter:
                continue
            if longer.startswith(shorter):
                return True
            common = 0
            for left, right in zip(first, second):
                if left != right:
                    break
                common += 1
            if common >= max(4, int(len(shorter) * 0.6)):
                return True
    return False


def _cycles(graph: dict[str, set[str]], limit: int = 12) -> list[list[str]]:
    """Find representative cycles in linear time, bounded by *limit*.

    Enumerating every simple path becomes exponential even for an acyclic import
    graph. A colour-marked DFS reports the back edges that prove cycles without
    making ``init --scan`` hang on a densely connected project.
    """
    found: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    colour: dict[str, int] = {}
    path: list[str] = []
    positions: dict[str, int] = {}

    def visit(node: str) -> None:
        if len(found) >= limit:
            return
        colour[node] = 1
        positions[node] = len(path)
        path.append(node)
        for neighbour in sorted(graph.get(node, ())):
            if len(found) >= limit:
                break
            state = colour.get(neighbour, 0)
            if state == 0:
                visit(neighbour)
            elif state == 1:
                cycle = path[positions[neighbour]:] + [neighbour]
                key = tuple(sorted(cycle[:-1]))
                if key not in seen:
                    seen.add(key)
                    found.append(cycle)
        path.pop()
        positions.pop(node, None)
        colour[node] = 2

    for start in sorted(graph):
        if colour.get(start, 0) == 0:
            visit(start)
        if len(found) >= limit:
            break
    return sorted(found, key=len)


def _finding(kind: str, summary: str, **evidence: Any) -> dict[str, Any]:
    return {"kind": kind, "summary": summary, "evidence": evidence}


def detect(
    root: Path,
    sources: dict[Path, str],
    imports: dict[Path, int],
    edges: dict[Path, set[Path]],
    prose: dict[Path, str],
    manifest_requirements: set[str],
    live_tree: set[str],
) -> list[dict[str, Any]]:
    """Cross-check the layers against each other. Provable disagreements only.

    ``live_tree`` is every live path, not just the source files: a document citing
    a config or data file must be checked against the whole tree, or every
    non-code citation reads as missing.
    """
    findings: list[dict[str, Any]] = []
    relative = {path: path.relative_to(root).as_posix() for path in sources}
    stems = {path.stem: path for path in sources}

    # A module labelled legacy that the live code still leans on. Either the label
    # is wrong or the callers are, and both are worth knowing before touching it.
    for path, source in sources.items():
        head = source[:600]
        if imports.get(path, 0) >= HUB_THRESHOLD and LEGACY_MARKERS.search(head):
            marker = LEGACY_MARKERS.search(head)
            findings.append(_finding(
                "legacy_still_load_bearing",
                f"{relative[path]} is marked '{marker.group(0)}' but {imports[path]} modules import it",
                path=relative[path], importers=imports[path], marker=marker.group(0),
            ))

    # The same constant maintained in two places, with the values already diverged.
    constants: dict[str, dict[str, str]] = {}
    for path, source in sources.items():
        for name, value in _module_constants(source).items():
            constants.setdefault(name, {})[relative[path]] = value
    for name, holders in sorted(constants.items()):
        values = sorted(set(holders.values()))
        if len(holders) > 1 and len(values) > 1 and _same_thing_diverged(values):
            findings.append(_finding(
                "constant_forked",
                f"{name} is defined in {len(holders)} modules with {len(values)} divergent values",
                name=name, definitions=holders,
            ))

    # Import cycles. Nothing subjective here: the graph either closes or it does not.
    graph = {relative[path]: {relative[target] for target in targets if target in relative}
             for path, targets in edges.items() if path in relative}
    for cycle in _cycles(graph):
        findings.append(_finding(
            "import_cycle",
            " -> ".join(cycle),
            cycle=cycle, length=len(cycle) - 1,
        ))

    # Load-bearing and unowned: imported everywhere, tested nowhere.
    test_targets = {
        path.stem[5:] if path.stem.startswith("test_") else path.stem[:-5]
        for path in sources if path.stem.startswith("test_") or path.stem.endswith("_test")
    }
    documented = " ".join(prose.values())
    for path, count in sorted(imports.items(), key=lambda item: -item[1]):
        if count < HUB_THRESHOLD or path not in relative:
            continue
        if path.stem in test_targets or path.stem in documented:
            continue
        findings.append(_finding(
            "unowned_hub",
            f"{relative[path]} is imported by {count} modules with no test file and no mention in project prose",
            path=relative[path], importers=count,
        ))

    # Several generations of one name alive at once: foo, foo_v2, foo_v2_runtime.
    # Grouping by ancestor rather than by one stripped suffix catches the whole
    # chain — a suffix rule only ever sees the generation directly above.
    families: dict[str, set[str]] = {}
    for stem in sorted(stems):
        for ancestor in sorted(stems):
            if ancestor == stem or not stem.startswith(ancestor):
                continue
            if VERSION_SUFFIX.match(stem[len(ancestor):].lstrip("._-") or "x") or \
                    re.fullmatch(r"[._-](v?\d+|new|old|next|copy|final|runtime|legacy)\b.*", stem[len(ancestor):], re.I):
                families.setdefault(ancestor, set()).add(stem)
    for base, members in sorted(families.items()):
        live = sorted(members | {base})
        findings.append(_finding(
            "parallel_generations",
            f"{len(live)} generations of '{base}' coexist: {', '.join(live)}",
            base=base, modules=[relative[stems[stem]] for stem in live if stem in stems],
        ))

    # A declared dependency nobody imports. Distribution names and import names can
    # differ, so this is reported as a lead with both sides shown.
    imported_roots: set[str] = set()
    for source in sources.values():
        for match in re.finditer(r"^\s*(?:from|import)\s+([\w.]+)", source, re.M):
            imported_roots.add(match.group(1).split(".")[0].lower())
    for requirement in sorted(manifest_requirements):
        normalised = requirement.lower().replace("-", "_")
        if normalised not in imported_roots and requirement.lower() not in imported_roots:
            findings.append(_finding(
                "dependency_never_imported",
                f"manifest requires '{requirement}' but no module imports it",
                requirement=requirement,
            ))

    # A test importing a module that is not in the tree any more. The previous
    # implementation checked ``imported_roots`` here, but that set necessarily
    # contains the missing import from the test itself, making this branch dead.
    project_roots = {path.split("/", 1)[0].removesuffix(".py") for path in relative.values()}
    declared = {
        requirement.lower().replace("-", "_") for requirement in manifest_requirements
    }
    stdlib = {name.lower() for name in getattr(sys, "stdlib_module_names", set())}
    for path, source in sources.items():
        if not (path.stem.startswith("test_") or path.stem.endswith("_test")):
            continue
        for match in re.finditer(r"^\s*(?:from|import)\s+([\w.]+)", source, re.M):
            token = match.group(1).split(".")[0]
            normalised = token.lower().replace("-", "_")
            if token in stems or token in project_roots or normalised in declared or normalised in stdlib:
                continue
            if normalised in {"pytest", "unittest"}:
                continue
            findings.append(_finding(
                "test_targets_missing_module",
                f"{relative[path]} imports '{token}', which is not a module in this project",
                path=relative[path], missing=token,
            ))
            break

    # Prose naming a file that no longer exists. Most citations that fail a naive
    # tree lookup are not drift at all, so each exemption below removes a whole
    # class of false positive rather than one case.
    live_paths = live_tree | set(relative.values())
    live_names = {Path(path).name for path in live_paths}
    reported: set[tuple[str, str]] = set()
    for doc_path, text in prose.items():
        if PLANNING_DOC.search(doc_path.stem):
            continue  # A plan describes what does not exist yet. That is its job.
        for match in re.finditer(r"[`'\"(](/?[\w./-]+\.(?:py|js|ts|rs|go|sh|toml|json|md))[`'\")]", text):
            raw = match.group(1)
            cited = raw.lstrip("./")
            if cited in live_paths or ("/" not in cited and cited in live_names):
                continue
            if PLACEHOLDER_PATH.search(raw):
                continue  # path/to/thing, <your-config>, example.com
            if raw.startswith("/"):
                # An absolute path is a claim about the filesystem, so check the
                # filesystem. Anything outside this project is another project's
                # business, not drift in this one.
                if Path(raw).exists() or not raw.startswith(f"/{root.name}/") and root.as_posix() not in raw:
                    continue
            if STALE_CITATION.search(cited):
                continue  # Prose discussing what was retired is prose doing its job.
            if (doc_path.name, cited) in reported:
                continue
            reported.add((doc_path.name, cited))
            findings.append(_finding(
                "prose_cites_missing_path",
                f"{doc_path.name} refers to {cited}, which is not in the live tree",
                document=doc_path.name, cited=cited,
            ))
    return findings

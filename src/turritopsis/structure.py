"""Structure extraction: what a file declares, not what it says.

Turritopsis exists so later agents do not have to re-read a project. If building
the map required the first agent to read every file, the cost would only move to
the first window instead of disappearing. Global coverage is not the same thing
as putting every line in the model.

A source file's declarations — classes, function signatures, who imports it —
compress roughly ten to one against its body while answering the question the
scan actually asks: what is this project made of? Same token budget, an order of
magnitude more of the project seen.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

MAX_SIGNATURES_PER_FILE = 40
MAX_DOC_CHARS = 110
PRIVATE_PREFIX = "_"


def _python_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    arguments = node.args
    names = [item.arg for item in arguments.posonlyargs + arguments.args]
    if arguments.vararg:
        names.append("*" + arguments.vararg.arg)
    names.extend(item.arg for item in arguments.kwonlyargs)
    if arguments.kwarg:
        names.append("**" + arguments.kwarg.arg)
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    keyword = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{keyword} {node.name}({', '.join(names)}){returns}"


def _python_outline(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return _regex_outline(source, ".py")
    lines: list[str] = []
    docstring = ast.get_docstring(tree)
    if docstring:
        lines.append(f'"""{docstring.strip().splitlines()[0][:MAX_DOC_CHARS]}"""')
    for node in tree.body:
        if len(lines) >= MAX_SIGNATURES_PER_FILE:
            break
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(base) for base in node.bases)
            lines.append(f"class {node.name}({bases})" if bases else f"class {node.name}")
            for member in node.body:
                if len(lines) >= MAX_SIGNATURES_PER_FILE:
                    break
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if member.name.startswith(PRIVATE_PREFIX) and member.name != "__init__":
                        continue
                    lines.append("  " + _python_signature(member))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith(PRIVATE_PREFIX):
                lines.append(_python_signature(node))
    if not lines:
        # A module of nothing but constants still shapes the project when the rest
        # of it imports the constants. Name them rather than dropping the file.
        names = [
            target.id
            for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            if isinstance(target, ast.Name) and not target.id.startswith(PRIVATE_PREFIX)
        ]
        if names:
            lines.append("names: " + ", ".join(names[:MAX_SIGNATURES_PER_FILE]))
    return lines


_DECLARATION = re.compile(
    r"^[ \t]*(?:export\s+)?(?:public\s+|private\s+|protected\s+|static\s+|async\s+|pub\s+)*"
    r"(?P<kind>class|interface|struct|enum|trait|impl|type|func|function|fn|def|sub)\s+"
    r"(?P<name>[A-Za-z_$][\w$]*)"
    r"(?P<rest>[^\n{;]{0,120})",
    re.M,
)

_ASSIGNED_ARROW = re.compile(
    r"^[ \t]*(?:export\s+)?(?:default\s+)?(?:const|let|var)\s+"
    r"(?P<name>[A-Za-z_$][\w$]*)\s*(?::[^=\n]+)?=\s*(?:async\s+)?"
    r"(?:\((?P<args>[^)\n]*)\)|(?P<single>[A-Za-z_$][\w$]*))\s*=>",
    re.M,
)
_ASSIGNED_FUNCTION = re.compile(
    r"^[ \t]*(?:export\s+)?(?:default\s+)?(?:const|let|var)\s+"
    r"(?P<name>[A-Za-z_$][\w$]*)\s*(?::[^=\n]+)?=\s*(?:async\s+)?function\s*"
    r"\((?P<args>[^)\n]*)\)",
    re.M,
)


def _regex_outline(source: str, suffix: str) -> list[str]:
    """Language-agnostic fallback: declaration keyword plus name and parameters."""
    declarations: list[tuple[int, str]] = []
    for match in _DECLARATION.finditer(source):
        rest = match.group("rest").strip().rstrip("=>").strip()
        line = f"{match.group('kind')} {match.group('name')}{(' ' + rest) if rest else ''}".rstrip()
        declarations.append((match.start(), line))
    for pattern in (_ASSIGNED_ARROW, _ASSIGNED_FUNCTION):
        for match in pattern.finditer(source):
            args = match.groupdict().get("args") or match.groupdict().get("single") or ""
            declarations.append((match.start(), f"const {match.group('name')}({args.strip()})"))
    lines: list[str] = []
    for _, declaration in sorted(declarations, key=lambda item: item[0]):
        if len(lines) >= MAX_SIGNATURES_PER_FILE:
            break
        if declaration not in lines:
            lines.append(declaration)
    return lines


def outline_source(path: Path, source: str) -> list[str]:
    if path.suffix.lower() in {".py", ".pyi"}:
        return _python_outline(source)
    return _regex_outline(source, path.suffix.lower())


def structure_card(path: Path, relative: str, source: str, imported_by: int) -> str:
    """One file's declarations, or "" when it declares nothing worth mapping."""
    from .init_scan import looks_like_credential

    # A hardcoded key can sit in a .py file, and a default argument carries it
    # straight into the signature. Same rule as prose: one match drops the file.
    if looks_like_credential(source):
        return ""
    outline = outline_source(path, source)
    if not outline:
        return ""
    header = f"{relative}  (imported by {imported_by})" if imported_by else relative
    return header + "\n" + "\n".join("  " + line for line in outline) + "\n"


def structure_map(
    ranked: list[tuple[Path, str, int]],
    budget: int,
    read: Any = None,
) -> tuple[str, dict[str, int]]:
    """Fill *budget* characters with the most-depended-on files' declarations.

    ``ranked`` is (path, relative_path, inbound_import_count), most important
    first. Returns the map and a stats dict — callers should surface ``skipped``
    rather than let a truncated map read as complete coverage.
    """
    reader = read or (lambda path: path.read_text(encoding="utf-8", errors="replace"))
    cards: list[str] = []
    used = 0
    covered = 0
    skipped = 0
    for path, relative, imported_by in ranked:
        try:
            source = reader(path)
        except OSError:
            continue
        card = structure_card(path, relative, source, imported_by)
        if not card:
            continue
        if used + len(card) > budget:
            skipped += 1
            continue
        cards.append(card)
        used += len(card)
        covered += 1
    return "\n".join(cards), {"files_mapped": covered, "files_skipped": skipped, "chars": used}

"""
Project Intelligence Layer — recursive structure analysis and noise filtering.

Recursive project structure; filter .git, node_modules, build artifacts;
optional future: dependency graph inference.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .memory import _tool_result

# Default dirs/files to skip (noise)
DEFAULT_IGNORE = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "coverage",
    "htmlcov",
    ".eggs",
    "*.egg-info",
    ".gravitas_brain.db",
    ".DS_Store",
    "Thumbs.db",
}


def _should_ignore(name: str, ignore_set: set[str]) -> bool:
    for skip in ignore_set:
        if skip.startswith("*"):
            if name.endswith(skip[1:]):
                return True
        elif name == skip or name.startswith(skip + os.sep):
            return True
    return False


def collect_structure(
    root: str | Path,
    max_depth: int = 8,
    max_entries: int = 2000,
    ignore: set[str] | None = None,
) -> dict[str, Any]:
    """
    Recursive project structure as nested dict.
    Keys are relative paths; values are either "FILE" or a dict of children.
    """
    root = Path(root).resolve()
    ignore_set = ignore or DEFAULT_IGNORE
    result: dict[str, Any] = {}
    count = [0]

    def walk(dir_path: Path, rel_prefix: str, depth: int) -> dict[str, Any]:
        if depth > max_depth or count[0] >= max_entries:
            return {}
        node: dict[str, Any] = {}
        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return {}
        for p in entries:
            if count[0] >= max_entries:
                break
            name = p.name
            if _should_ignore(name, ignore_set):
                continue
            rel = f"{rel_prefix}{name}" if rel_prefix else name
            if p.is_file():
                node[name] = "FILE"
                count[0] += 1
            else:
                child = walk(p, rel + os.sep, depth + 1)
                node[name] = child if child else "DIR"
                count[0] += 1
        return node

    result[""] = walk(root, "", 0)
    result["_meta"] = {"root": str(root), "max_depth": max_depth, "entries_count": count[0]}
    return result


def get_project_map(
    project_root: str | Path | None = None,
    max_depth: int = 8,
    max_entries: int = 2000,
    ignore: set[str] | None = None,
) -> dict[str, Any]:
    """
    Public API: return tool contract with project structure and metadata.
    """
    root = Path(project_root or os.getcwd()).resolve()
    if not root.is_dir():
        return _tool_result(
            "failure",
            errors=[f"Not a directory: {root}"],
            next_recommended_action="Set project_root to a valid directory.",
        )
    try:
        structure = collect_structure(root, max_depth=max_depth, max_entries=max_entries, ignore=ignore)
        return _tool_result(
            "success",
            observations={
                "project_root": str(root),
                "structure": structure,
                "entries_count": structure.get("_meta", {}).get("entries_count", 0),
            },
            next_recommended_action="Use structure to plan edits; respect safe_to_edit and do_not_touch from memory.",
        )
    except Exception as e:
        return _tool_result(
            "failure",
            errors=[str(e)],
            next_recommended_action="Check path and permissions.",
        )

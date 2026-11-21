"""Root pytest config: put the right project's tools/ folder on the import path.

bigcat/tools and gear/tools are folders of scripts that import each other as top-level modules
(`from common import ...`), and both have modules with the same names (common, validate, ...).
So one test session can't simply put both folders on sys.path. Instead, before collecting or
running a test under <project>/, this swaps that project's tools/ folder onto sys.path and its
already-imported modules back into sys.modules, stashing the other project's.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
TOOL_DIRS = {name: REPO / name / "tools" for name in ("bigcat", "gear")}

_stash: dict[str, dict[str, object]] = {name: {} for name in TOOL_DIRS}
_active: str | None = None


def _project_for(path: Path) -> str | None:
    try:
        rel = Path(path).resolve().relative_to(REPO)
    except ValueError:
        return None
    return rel.parts[0] if rel.parts and rel.parts[0] in TOOL_DIRS else None


def _module_dir(module) -> Path | None:
    file = getattr(module, "__file__", None)
    return Path(file).resolve().parent if file else None


def activate(project: str) -> None:
    """Make `import common` (etc.) resolve to <project>/tools/."""
    global _active
    if _active == project:
        return
    if _active is not None:
        tools = TOOL_DIRS[_active]
        for name, mod in list(sys.modules.items()):
            if _module_dir(mod) == tools:
                _stash[_active][name] = sys.modules.pop(name)
    for d in TOOL_DIRS.values():
        while str(d) in sys.path:
            sys.path.remove(str(d))
    sys.path.insert(0, str(TOOL_DIRS[project]))
    sys.modules.update(_stash[project])
    _active = project


def pytest_collectstart(collector):
    project = _project_for(collector.path)
    if project:
        activate(project)


@pytest.fixture(autouse=True)
def _tools_on_path(request):
    project = _project_for(request.path)
    if project:
        activate(project)

"""Package canonical PowerKit assets without duplicating their source tree."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


ROOT = Path(__file__).parent
if str(ROOT.resolve()) not in sys.path:
    sys.path.insert(0, str(ROOT.resolve()))

from tools.release_inventory import (  # noqa: E402
    git_tracked_files,
    select_distribution_files,
    validate_source_file,
)


SHARE_ROOT = Path("share/ai-engineering-powerkit")
ASSET_ROOTS = (
    Path(".agents/skills"),
    Path("adapters"),
    Path("hooks"),
    Path("manifests"),
    Path("templates"),
)
TOP_LEVEL_ASSETS = (Path("BOOTSTRAP.md"), Path("catalog.json"))


TRACKED_FILES = git_tracked_files(ROOT)


class TrackedBuildPy(build_py):
    """Exclude untracked Python modules and reject tracked symlink candidates."""

    def find_package_modules(self, package: str, package_dir: str):
        modules = super().find_package_modules(package, package_dir)
        selected = []
        for module_package, module_name, filename in modules:
            path = Path(filename).resolve()
            try:
                relative = path.relative_to(ROOT.resolve())
            except ValueError as exc:
                raise RuntimeError(f"wheel module escapes repository root: {path}") from exc
            if TRACKED_FILES is not None and relative not in TRACKED_FILES:
                continue
            validate_source_file(ROOT, relative, "wheel")
            selected.append((module_package, module_name, filename))
        return selected


def distribution_data_files() -> list[tuple[str, list[str]]]:
    grouped: dict[Path, list[str]] = defaultdict(list)
    selected = select_distribution_files(
        ROOT,
        TOP_LEVEL_ASSETS,
        ASSET_ROOTS,
        TRACKED_FILES,
    )
    for relative in selected:
        destination = SHARE_ROOT if relative in TOP_LEVEL_ASSETS else SHARE_ROOT / relative.parent
        grouped[destination].append(str(relative))
    return [(str(destination), sources) for destination, sources in sorted(grouped.items())]


setup(data_files=distribution_data_files(), cmdclass={"build_py": TrackedBuildPy})

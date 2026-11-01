"""The bridge's general part imports nothing of any workflow, and no instrument.

The twin of ``knows-no-workflow.test.js``, which keeps the page's framework
free of workflows. Until October 2026 the bridge's general part opened the
session, drove the stage, captured and served the pictures, so it imported
the controller and target acquisition's microscope, storage and analysis.
They all moved into the workflow's own Python half
(now ``examples/target_acquisition/bridge``). This test reads
the framework's modules and refuses an import of anything of the interface
outside ``framework/``, and of the controller, however it is written, so the
tie cannot come back without a red test saying where.

Author: Thom de Hoog, Center for Microscopy and Image Analysis (ZMB),
University of Zurich (thom.dehoog@zmb.uzh.ch, thomdehoog@gmail.com).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

FRAMEWORK = Path(__file__).resolve().parent
PACKAGE = "zmart_interface.framework"


def modules_of_the_framework() -> list[Path]:
    """Every Python module of the framework, leaving out the tests and their fixtures."""
    return sorted(
        path for path in FRAMEWORK.rglob("*.py")
        if not path.name.startswith("test_") and path.name != "conftest.py"
        and "__pycache__" not in path.parts and "fixtures" not in path.parts
    )


def imported_by(path: Path, root: Path = FRAMEWORK, package: str = PACKAGE) -> list[str]:
    """The full names of the modules ``path`` imports, relative imports resolved."""
    here = f"{package}.{'.'.join(path.relative_to(root).with_suffix('').parts)}"
    within = here if path.name == "__init__.py" else here.rpartition(".")[0]
    names = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parent = within.rsplit(".", node.level - 1)[0] if node.level > 1 else within
                base = f"{parent}.{base}" if base else parent
            names += [base, *(f"{base}.{alias.name}" for alias in node.names)]
    return names


def outside_the_framework(names: list[str]) -> list[str]:
    """The names that reach past the framework: the rest of the interface, or the controller."""
    return [
        name for name in names
        if (name.startswith("zmart_interface") and not name.startswith(PACKAGE) and name != "zmart_interface")
        or name.split(".")[0] == "zmart_controller"
    ]


def test_there_are_modules_to_read():
    assert modules_of_the_framework()


@pytest.mark.parametrize("path", modules_of_the_framework(), ids=lambda path: path.relative_to(FRAMEWORK).as_posix())
def test_a_framework_module_imports_nothing_outside_the_framework(path):
    reached = outside_the_framework(imported_by(path))
    assert reached == [], f"{path.relative_to(FRAMEWORK)} imports {reached}"


def test_the_check_would_catch_a_relative_import(monkeypatch):
    """The positive control: a relative import of a workflow is seen for what it is."""
    sneaky = FRAMEWORK / "bridge" / "sneaky_example_for_the_test.py"
    monkeypatch.setattr(Path, "read_text", lambda self, encoding=None: "from ...workflows.target_acquisition import bridge\n")
    assert outside_the_framework(imported_by(sneaky)) == [
        "zmart_interface.workflows.target_acquisition",
        "zmart_interface.workflows.target_acquisition.bridge",
    ]


def test_the_check_would_catch_the_controller(monkeypatch):
    sneaky = FRAMEWORK / "bridge" / "sneaky_example_for_the_test.py"
    monkeypatch.setattr(Path, "read_text", lambda self, encoding=None: "from zmart_controller import ZmartController\n")
    assert outside_the_framework(imported_by(sneaky)) == ["zmart_controller", "zmart_controller.ZmartController"]

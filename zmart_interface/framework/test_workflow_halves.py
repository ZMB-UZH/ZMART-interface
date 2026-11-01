"""Each workflow's Python half is wired into the bridge at start-up, under its own folder.

A workflow in the folder of workflows (the one ``ZMART_INTERFACE_WORKFLOWS``
names, or this repository's ``examples/``) may have a Python half, a package
``<folder>/bridge`` with ``routes(register)``. The bridge loads every one when
it starts, and each half's routes land under ``/api/<folder>/``. The folder can
be anywhere on the computer, which is what lets a workflow live in a repository
of its own. The
bridge has no routes of its own: what a workflow asks of a microscope is the
workflow's (target acquisition's are pinned in its ``bridge/test_the_routes.py``).

Author: Thom de Hoog, Center for Microscopy and Image Analysis (ZMB),
University of Zurich (thom.dehoog@zmb.uzh.ch, thomdehoog@gmail.com).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from zmart_interface.framework.bridge import server, workflows

#: The framework's own fixture: the smallest workflow, with a Python half.
THE_FIXTURE = Path(workflows.__file__).resolve().parents[1] / "fixtures" / "three_steps"


def test_the_bridge_registers_no_route_of_its_own():
    """Imported on its own, in a fresh process, before any half is loaded."""
    said = subprocess.run(
        [sys.executable, "-c", "from zmart_interface.framework.bridge import server; "
                               "print(len(server.ROUTES), len(server.PREFIX_ROUTES))"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert said == ["0", "0"]


def test_every_halfs_routes_land_under_its_folder(monkeypatch):
    monkeypatch.setattr(server, "ROUTES", {})
    monkeypatch.setattr(server, "PREFIX_ROUTES", {})
    loaded = workflows.load_halves(server.add_route)
    folders = {name for name, _ in loaded}
    for _, path in (*server.ROUTES, *server.PREFIX_ROUTES):
        assert path.split("/")[2] in folders, path


def test_the_halves_are_the_workflow_folders_with_a_bridge_package():
    assert workflows.halves() == ["target_acquisition"]


def test_in_a_checkout_the_workflows_are_the_examples():
    assert workflows.the_workflows_folder({}) == workflows.WHERE_THE_PACKAGE_IS / "examples"


def test_the_setting_names_the_folder_of_workflows(tmp_path):
    assert workflows.the_workflows_folder({workflows.SETTING: str(tmp_path)}) == tmp_path.resolve()


def test_the_page_is_served_from_the_folder_it_was_built_from(tmp_path):
    assert workflows.the_page(tmp_path) == tmp_path / "built-page"


def test_with_no_folder_of_workflows_the_bridge_says_what_to_set():
    with pytest.raises(workflows.NoWorkflows, match=workflows.SETTING):
        workflows.halves(None)


def test_a_folder_that_is_not_there_is_said_so(tmp_path):
    with pytest.raises(workflows.NoWorkflows, match="not a folder"):
        workflows.halves(tmp_path / "nowhere")


def test_a_workflow_outside_the_interface_brings_its_routes(monkeypatch, tmp_path):
    """A folder of workflows anywhere on the computer: its halves load by their own names."""
    shutil.copytree(THE_FIXTURE, tmp_path / "counting_outside", ignore=shutil.ignore_patterns("__pycache__"))
    monkeypatch.setattr(server, "ROUTES", {})
    monkeypatch.setattr(server, "PREFIX_ROUTES", {})
    monkeypatch.setattr(sys, "path", list(sys.path))
    loaded = workflows.load_halves(server.add_route, folder=tmp_path)
    assert [name for name, _ in loaded] == ["counting_outside"]
    assert loaded[0][1].__name__ == "counting_outside.bridge"
    assert ("GET", "/api/counting_outside/hello") in server.ROUTES

"""Where the workflows are, and each workflow's Python half wired into the bridge at start-up.

The interface is a framework and brings no workflow of its own. It runs the
workflows in one **folder of workflows**, which can be anywhere on the
computer: a folder in your own repository (in ZMART Microscopy,
``workflows/non-coders/interface/``), or, in a checkout of this repository,
its ``examples/`` folder. The folder is named by the environment variable
``ZMART_INTERFACE_WORKFLOWS``; in a checkout of this repository, where it is
not set, ``examples/`` is used, so the interface's own tests run on its
example. The page built from the folder sits inside it, as ``built-page/``
(``npm run build`` writes it there; see ``tools/the-workflows-folder.mjs``),
so the bridge serves the page that was built from the same workflows it runs.

A workflow in that folder may have a Python half: a package
``<folder>/bridge``. What the bridge asks of it, and what it may use of the
bridge, is :mod:`zmart_interface.framework.bridge.api`. Its routes land under
``/api/<folder>/``: ``register("GET", "hello", say_hello)`` in
``three_steps/bridge`` answers ``GET /api/three_steps/hello``.

A folder of workflows outside this package is put on Python's search path, so
each workflow is imported by its own folder's name (``target_acquisition``)
and its modules import each other by relative paths. That is also how pytest
names them when it runs a workflow's own tests, so a test and the bridge
always meet the same module. A half that fails to import is a fault in the
workflow, so the bridge does not start.

Author: Thom de Hoog, Center for Microscopy and Image Analysis (ZMB),
University of Zurich (thom.dehoog@zmb.uzh.ch, thomdehoog@gmail.com).
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

#: The environment variable that names the folder of workflows.
SETTING = "ZMART_INTERFACE_WORKFLOWS"

#: The folder the package ``zmart_interface`` sits in. In a checkout of this
#: repository it is the checkout, and holds ``examples/``.
WHERE_THE_PACKAGE_IS = Path(__file__).resolve().parents[3]

#: The name of the folder, inside a folder of workflows, that holds the page built from it.
BUILT_PAGE = "built-page"


class NoWorkflows(RuntimeError):
    """There is no folder of workflows to run; the message says what to set."""


def the_workflows_folder(environment=None) -> Path | None:
    """The folder of workflows to run, or None when there is none.

    It is the folder ``ZMART_INTERFACE_WORKFLOWS`` names, or, in a checkout of
    this repository, its ``examples/`` folder. An installed interface with the
    setting left out has no workflow to run, and answers None.
    """
    environment = os.environ if environment is None else environment
    named = environment.get(SETTING, "").strip()
    if named:
        return Path(named).resolve()
    examples = WHERE_THE_PACKAGE_IS / "examples"
    return examples if examples.is_dir() else None


#: Where the workflows live, decided once when the bridge is loaded.
WORKFLOWS = the_workflows_folder()


def the_page(folder: Path | None = WORKFLOWS) -> Path:
    """Where the page built from ``folder`` is: its ``built-page/``."""
    return there_are_workflows_in(folder) / BUILT_PAGE


def there_are_workflows_in(folder: Path | None) -> Path:
    """``folder``, when it is a folder; otherwise :class:`NoWorkflows`, saying what to do."""
    if folder is None:
        raise NoWorkflows(
            f"there are no workflows to run. Set {SETTING} to the folder that holds your "
            "workflows (in ZMART Microscopy: workflows/non-coders/interface), with the page "
            "built from it by `npm run build` in a checkout of ZMART-interface"
        )
    if not folder.is_dir():
        raise NoWorkflows(f"{SETTING} names {folder}, which is not a folder")
    return folder


def halves(folder: Path | None = WORKFLOWS) -> list[str]:
    """The workflows in ``folder`` that have a Python half, in order."""
    folder = there_are_workflows_in(folder)
    return sorted(
        one.name for one in folder.iterdir()
        if (one / "bridge" / "__init__.py").is_file()
    )


def routes_under(folder: str, add_route):
    """The ``register`` a half is handed: ``add_route`` with ``/api/<folder>/`` in front."""

    def register(method, path, handler, prefix=False):
        add_route(method.upper(), f"/api/{folder}/{str(path).lstrip('/')}", handler, prefix=prefix)

    return register


def _package_of(folder: Path) -> str:
    """The dotted name the workflows in ``folder`` are imported under.

    A folder inside this package (the framework's own fixtures) is reached by
    its full name. Any other folder is put on Python's search path, and its
    workflows are imported by their own names.
    """
    try:
        parts = folder.relative_to(WHERE_THE_PACKAGE_IS).parts
    except ValueError:
        return ""
    return ".".join(parts) if parts and parts[0] == "zmart_interface" else ""


def load_halves(add_route, folder: Path | None = WORKFLOWS) -> list[tuple[str, object]]:
    """Import every workflow's Python half in ``folder`` and register its routes.

    Answers the halves as ``(folder name, module)``, so whoever starts the
    bridge can hand each its options, start it and close it.
    """
    folder = there_are_workflows_in(folder).resolve()
    package = _package_of(folder)
    if not package and str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    loaded = []
    for name in halves(folder):
        module = importlib.import_module(f"{package}.{name}.bridge" if package else f"{name}.bridge")
        module.routes(routes_under(name, add_route))
        loaded.append((name, module))
    return loaded

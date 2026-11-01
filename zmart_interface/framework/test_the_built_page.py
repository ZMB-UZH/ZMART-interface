"""The built page: what is committed is what the build makes, every time.

The page the bridge hands out is built from a folder of workflows and lives
inside it, as ``built-page/``. Here that is the example's page,
``examples/built-page``, and it is committed, so the interface's own tests and
a microscope PC can run it without Node.js. That only holds if
the committed files are exactly what ``npm run build`` makes from the sources
beside them: a change to the page that was never rebuilt, or a build that
comes out differently each time, would ship a page nobody has tested.

The first two tests read only the checkout and always run. The third builds
the page twice and needs Node.js and ``npm ci`` in this checkout; it skips,
saying so, without them.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from zmart_interface.framework.bridge import THE_PAGE

CHECKOUT = Path(__file__).resolve().parents[2]


def _digest(folder: Path) -> dict[str, str]:
    """Every file under *folder*, by its path inside it, with its SHA-256."""
    return {
        path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def test_the_committed_page_is_three_files_with_neuroglancers_programs_compiled():
    """The page, and neuroglancer's two background programs beside it, ready to run.

    The background programs arrive from npm as twenty-line lists of imports a
    browser cannot follow; the build compiles them (``tools/neuroglancer-workers.mjs``).
    A page shipped with the lists instead opens and never draws, and says nothing.
    """
    names = sorted(_digest(THE_PAGE))
    workers = [name for name in names if name.endswith(".bundle.js") or ".bundle-" in name]
    assert "index.html" in names and len(names) == 3, names
    assert "async_computation.bundle.js" in workers, names
    assert any(name.startswith("chunk_worker.bundle-") for name in workers), names
    for name in workers:
        text = (THE_PAGE / name).read_text(encoding="utf-8")
        assert 'import "#src/' not in text and len(text) > 500_000, (
            f"{name} is neuroglancer's uncompiled list, not a finished program"
        )


def test_every_source_is_checked_out_with_unix_line_endings():
    """The build copies some sources into the page as they are, line endings and all.

    A Windows checkout that turned them into Windows line endings would build a
    page that differs from the one built on Linux, so neither could be checked
    against the committed one. ``.gitattributes`` keeps every checkout's text
    files as they are stored.
    """
    git = shutil.which("git")
    if git is None or not (CHECKOUT / ".git").exists():
        pytest.skip("needs git and a git checkout")
    listed = subprocess.run(
        [git, "ls-files", "--eol"], cwd=CHECKOUT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    windows = [line.split("\t", 1)[1] for line in listed if "w/crlf" in line.split("\t", 1)[0]]
    assert windows == [], f"checked out with Windows line endings: {windows}"


def _npm() -> str | None:
    return shutil.which("npm") or shutil.which("npm.cmd")


@pytest.mark.skipif(
    _npm() is None or not (CHECKOUT / "node_modules" / "vite").is_dir(),
    reason="needs Node.js, and `npm ci` run in this checkout",
)
def test_building_twice_gives_the_committed_page(tmp_path):
    """Two fresh builds agree with each other and with the committed page, byte for byte.

    The build reads neuroglancer's patches from the installed ZMART viewer, so
    it runs with this Python, the one the viewer is installed in.
    """
    built = []
    for attempt in ("first", "second"):
        out = tmp_path / attempt
        finished = subprocess.run(
            f'"{_npm()}" run build -- --outDir "{out}" --emptyOutDir',
            cwd=CHECKOUT,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "NO_COLOR": "1", "PYTHON": sys.executable},
        )
        assert finished.returncode == 0, finished.stdout + finished.stderr
        built.append(_digest(out))
    assert built[0] == built[1], "two builds of the same sources differ"
    assert built[0] == _digest(THE_PAGE), (
        "the committed page is not what the build makes: run `npm run build` and commit "
        "examples/built-page"
    )


@pytest.mark.skipif(
    _npm() is None or not (CHECKOUT / "node_modules" / "vite").is_dir(),
    reason="needs Node.js, and `npm ci` run in this checkout",
)
def test_the_page_is_the_same_wherever_the_workflows_folder_is(tmp_path):
    """A folder of workflows builds the same page wherever it sits on the disk.

    A repository of workflows commits its page and checks it against a fresh
    build, made from wherever this checkout happens to be beside it. A page that
    held the way from this checkout to the workflows would differ with every
    layout, so the check could pass on one computer only.
    """
    elsewhere = tmp_path / "somewhere" / "else" / "workflows"
    shutil.copytree(CHECKOUT / "examples", elsewhere,
                    ignore=shutil.ignore_patterns("built-page", "__pycache__"))
    built = []
    for folder in (None, elsewhere):
        out = tmp_path / ("here" if folder is None else "there")
        setting = {} if folder is None else {"ZMART_INTERFACE_WORKFLOWS": str(folder)}
        finished = subprocess.run(
            f'"{_npm()}" run build -- --outDir "{out}" --emptyOutDir',
            cwd=CHECKOUT,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "NO_COLOR": "1", "PYTHON": sys.executable, **setting},
        )
        assert finished.returncode == 0, finished.stdout + finished.stderr
        built.append(_digest(out))
    assert built[0] == built[1], "the page differs with where the folder of workflows is"

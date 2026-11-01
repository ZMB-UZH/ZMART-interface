"""The installed interface is the framework alone: it brings no workflow and no page.

A workflow, and the page built from it, live in a folder of workflows of their
own: this repository's example in ``examples/``, the workflows we run in ZMART
Microscopy. Installing the interface must not bring the example with it, or a
microscope would quietly run the example instead of the workflow it was meant
to run. This builds the wheel, the file ``pip install`` unpacks, and reads what
is in it.

Author: Thom de Hoog, Center for Microscopy and Image Analysis (ZMB),
University of Zurich (thom.dehoog@zmb.uzh.ch, thomdehoog@gmail.com).
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[2]


def test_the_wheel_holds_the_framework_and_no_workflow(tmp_path):
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-q",
         "-w", str(tmp_path), str(CHECKOUT)],
        check=True,
    )
    names = zipfile.ZipFile(next(tmp_path.glob("zmart_interface-*.whl"))).namelist()

    assert "zmart_interface/framework/bridge/server.py" in names
    assert "zmart_interface/launcher.py" in names
    assert not [name for name in names if "target_acquisition" in name or "examples/" in name]
    assert not [name for name in names if "built-page/" in name or name.endswith("index.html")]
    assert not [name for name in names if "mock_microscope" in name]

"""ZMART interface: the operator window for smart microscopy.

The operator walks a run step by step -- connect, define the carrier, plan the
overview, measure a focus map, scan, find the targets, choose them, acquire
them -- in a window that draws the sample as it is acquired. Behind the window
sits the ZMART Controller, so the same window drives any microscope that has a
ZMART driver.

What is where:

- ``framework/``: the shell that runs a workflow -- the window (``window/``,
  in JavaScript), the rules for steps, and ``bridge/``, the HTTP door through
  which the page reaches each workflow's Python half.
- ``parts/``: what more than one workflow is built from. Empty today: a part
  arrives here when a second workflow needs it (``parts/README.md``).
The interface brings no workflow of its own. The workflows it runs live in a
folder of workflows outside the package, named by the environment variable
``ZMART_INTERFACE_WORKFLOWS``, and the page is built from that folder and kept
in it (``docs/running-your-own-workflows.md``). The workflows we run at the ZMB
are in ZMART Microscopy. This repository's own example, Target acquisition,
is in ``examples/`` beside the package: the interface's tests run on it, and it
is not installed.

Author: Thom de Hoog, Center for Microscopy and Image Analysis (ZMB),
University of Zurich (thom.dehoog@zmb.uzh.ch, thomdehoog@gmail.com).
"""

__version__ = "0.2.0rc4"
__author__ = "Thom de Hoog"
__email__ = "thom.dehoog@zmb.uzh.ch, thomdehoog@gmail.com"
__affiliation__ = "Center for Microscopy and Image Analysis (ZMB), University of Zurich"

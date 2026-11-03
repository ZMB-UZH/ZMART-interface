# ZMART interface

[![python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/downloads/)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![tests](https://img.shields.io/badge/tests-pytest%20%7C%20vitest%20%7C%20playwright-blue)](#development-and-testing)
[![status](https://img.shields.io/badge/status-early%20alpha-red)](#status)

<img src="docs/zmart-interface-icon.png" align="left" width="170" alt="ZMART interface">

The **ZMART interface** provides a visual way to setup and control your smart microscopy workflow. It drives the microscope through  through the [ZMART Controller](https://github.com/ZMB-UZH/ZMART-controller), so it works on any microscope with a ZMART driver. The image analysis engine is provided by the ZMART Analysis pipeline engine.

It is part of [**ZMART**](https://github.com/ZMB-UZH/ZMART-microscopy) (ZMB's Microscopy-Agnostic Research Toolkit), the tools we use for smart microscopy at the Center for Microscopy and Image Analysis (ZMB), University of Zurich.
<br clear="left"/>
<br>

## The Problem
A smart microscopy workflow becomes easily very complex and can be hard to fine tune visualize, scale and simulate. 

<br>

## The Solution
The ZMART interface provides a unified interactive framework and playground that allows you to easily simulate, fine tune and automate your workflow. We are currently testing it on the leica stellaris, but it can easily adapted to any microscope because it build on top of the ZMART controller.

<br>

![The operator window, scanning the overview](docs/operator-window.png)

<br>

## Status
This is a release candidate, 0.2.0rc4. We are currently in the process of testing it on the Leica Stellaris.

## A framework, and the workflows you run in it
The interface is a framework: installing it gives you the operator window and
the bridge to the microscope, but no workflow. The workflows it runs, and the
page built from them, live in a folder of workflows that you name with the
setting `ZMART_INTERFACE_WORKFLOWS`. The workflows we run at the ZMB live in
[ZMART Microscopy](https://github.com/ZMB-UZH/ZMART-microscopy).

This repository keeps one complete example, *Target acquisition*, in
[`examples/`](examples). The interface's own tests run on it, and it is the
place to start when you write a workflow. It is not installed with the
interface.

## How a run's images are saved
On the Connect step you choose, once for the whole run, how its images are
saved. Each capture becomes one *position* of the run, kept beside the
microscope's own files:

- **OME-TIFF** (the default): one `.ome.tif` file per position, holding every
  channel and plane, with smaller copies of the picture inside it. It opens
  with a drag and drop in Fiji, napari, QuPath or Imaris. A stack's maximum
  projection is saved beside it as an OME-TIFF too.
- **OME-Zarr**: one `.ome.zarr` image per position, the better choice for very
  large data.

Both hold the same pixels, and the viewer, the analysis and every step of the
interface work the same way with either. Where a picture lies on the stage
follows the OME-Zarr rules in both: an OME-TIFF carries the same description
an OME-Zarr image would, in a small ZMART note inside the file that other
programs skip.

## Try it yourself
Install it and test it:

- [Install and run the interface with its dependencies](docs/install-on-a-microscope.md)
- [The example workflow, Target acquisition](examples/target_acquisition)
- [Run your own workflows, or write a new one](docs/running-your-own-workflows.md)
- Build a new workflow with Claude Code: open it here and ask for the
  `zmart-workflow-builder` agent ([.claude/agents/zmart-workflow-builder.md](.claude/agents/zmart-workflow-builder.md)),
  which starts with a conversation about your experiment
- [The workflow API a workflow is written against](docs/the-workflow-api.md)
- [How the interface is put together](docs/architecture.md)

## Author
Thom de Hoog, Center for Microscopy and Image Analysis (ZMB), University of
Zurich (thom.dehoog@zmb.uzh.ch, thomdehoog@gmail.com).

## License
MIT License. See LICENSE file for details.

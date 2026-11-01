# Installing the interface on a microscope

What to install, where it must live, and in which order, on a Windows microscope PC. Keep the
previous installation and environment until the new one has passed the first checks below, so
that you can go back to it.

## What runs where

Everything runs from one conda environment on the microscope PC:

| Part | What it is | Where it comes from |
| --- | --- | --- |
| The interface | the frame of the operator window, and its bridge | `ZMB-UZH/ZMART-interface` |
| The workflows | the steps the operator clicks through, and the page built from them | a checkout of `ZMB-UZH/ZMART-microscopy` (`workflows/non-coders/interface`) |
| The controller | the one vocabulary every microscope is driven with | `ZMB-UZH/ZMART-controller`, installed with the interface |
| The viewer | the picture server that shows the run as it is written | `ZMB-UZH/ZMART-viewer`, installed with the interface |
| The analysis engine | runs focus scoring and object detection | `ZMB-UZH/ZMART-analysis`, installed with the interface |
| The analysis pipelines | the pipelines, and the conda environments they run in | the workflows' own (in ZMART Microscopy, `workflows/non-coders/analysis`), or, for the example, a checkout of `ZMB-UZH/ZMART-analysis` |
| The driver | speaks to the microscope's own software | `ZMB-UZH/ZMART-drivers`, with the extra for your microscope |

## Where things must live

On the ZMB workstations AppLocker refuses to run programs from folders a user can write to.
Everything that runs goes under `C:\ProgramData\MinicondaZMB`: the environment, the
ZMART-analysis checkout, and (for the tests only) the Playwright browsers. A checkout on the
Desktop, in Downloads or under `AppData` can install cleanly and still fail to run. Never run
from a network share.

The temporary folder matters too: the analysis engine starts each workflow's environment
through a small script it writes into `%TEMP%`, and a `TEMP` outside the allowed folders is
refused with "This program is blocked by group policy".

The computer's ZMART configuration -- which drivers are registered, each driver's limits,
origin and calibration, the interface's saved protocols and the workflows installed as
packages -- lives under `C:\ProgramData\zmart-microscopy\` (or wherever
`ZMART_MICROSCOPY_ROOT` points). Saved protocols are in its `zmart-interface\protocols`
folder (`ZMART_PROTOCOL_LIBRARY` names another), installed workflows in
`zmart-interface\workflows` (`ZMART_WORKFLOW_LIBRARY` names another).

## Order of work

### 1. The environment

Conda-forge only; never the `defaults` channel.

```powershell
conda create -n zmart-interface -c conda-forge -c nodefaults python=3.12 pip git
conda activate zmart-interface
```

### 2. The interface, the controller, the viewer and the analysis engine

```powershell
pip install "zmart-interface[drivers] @ git+https://github.com/ZMB-UZH/ZMART-interface"
pip check
```

The interface is a framework and brings no workflow, and no page, of its own.

### 3. The workflows

The steps the operator clicks through come from a folder of workflows, with the
page already built inside it, so nothing is built on the microscope. For the
workflows we run at the ZMB, that folder is in ZMART Microscopy:

```powershell
cd C:\ProgramData\MinicondaZMB\home\<user>
git clone https://github.com/ZMB-UZH/ZMART-microscopy
setx ZMART_INTERFACE_WORKFLOWS C:\ProgramData\MinicondaZMB\home\<user>\ZMART-microscopy\workflows\non-coders\interface
```

To try the interface's own example workflow instead, clone ZMART-interface and
point the setting at its `examples` folder. `docs/running-your-own-workflows.md`
says how a folder of workflows is laid out and how its page is built.

### 4. The analysis pipelines

```powershell
cd C:\ProgramData\MinicondaZMB\home\<user>
git clone -b v0.6.0rc8 https://github.com/ZMB-UZH/ZMART-analysis
conda env create -f ZMART-analysis\examples\focus\environments\main.yml
conda env create -f ZMART-analysis\examples\object_analysis\environments\classical.yml
conda env create -f ZMART-analysis\examples\object_analysis\environments\cellpose.yml   # Robust detection only
conda env create -f ZMART-analysis\examples\object_analysis\environments\umap.yml       # the multidimensional plots
setx ZMART_ANALYSIS_WORKFLOWS C:\ProgramData\MinicondaZMB\home\<user>\ZMART-analysis
```

These are the commands for the interface's example workflow, which uses
ZMART-analysis's example pipelines. A workflow that brings its own pipelines,
like the ones in ZMART Microscopy, says in its README where they are and how
their environments are made. (Installing ZMART-analysis from this checkout with
`pip install -e` does the same without the variable.) Fast detection runs its fields twelve at a time in the classical environment;
the first press of a session pays the start-up of those workers once.

### 5. The driver

Install the driver's extra (for the Leica: `pip install "zmart-drivers[leica] @ git+https://github.com/ZMB-UZH/ZMART-drivers@v0.7.0b9"`),
and do the driver's own setup for this microscope -- its limits, origin and, for the Leica,
the image orientation and objective calibration. Each driver's README says how; the Leica
driver has a setup wizard for it: `python -m zmart_drivers.leica.stellaris.navigator_expert.driver_setup.wizard`. The driver
loads that setup every time it connects, and the interface's Connect step shows what it
loaded.

Then install the driver into the controller's registry, once on this computer, by pointing
it at the driver's folder, the one holding `zmart_controller_plugin/`. Its
`zmart_controller_plugin.json` gives the driver's name and the connection it needs; the
command prints the name:

```powershell
python -c "import zmart_drivers.leica.stellaris.navigator_expert as d, zmart_controller, pathlib; print(zmart_controller.register_driver(pathlib.Path(d.__file__).parent))"
```

The Connect step then offers it under that name, beside the interface's pretend microscope.

The interface's own mock microscope needs no registering: the interface offers it itself. A
computer that registered it by its folder anyway, before it moved into target acquisition
(`zmart_interface/mock_microscope`, under the name `interface-mock`), lists a driver whose
folder is gone. Take it off the list once:

```powershell
python -c "import zmart_controller; print(zmart_controller.remove_driver('interface-mock'))"
```

### 6. Launch

The vendor's software (LAS X, with the CAM API and the intended jobs set up, on the Leica) must
be running before the window connects.

```powershell
zmart-interface --output-root D:\ZMART-data
```

This opens the operator window with its bridge beside it. `--output-root` is where the interface
keeps its runs, one folder per run; choose it on the drive the microscope saves to, so each
capture's files are moved into the run rather than copied. Without it the window cannot connect.
For a browser instead of the window:
`python -m zmart_interface.framework.bridge --port 8600 --output-root D:\ZMART-data` and open
`http://127.0.0.1:8600`.
One controlling process at a time.

For a dry run without the instrument, choose **Mock** on the Connect step.

## First checks on a new instrument

1. Connect, and read the connection checks. If the limits are a fallback rather than this
   microscope's own, stop and do the driver's setup first; never work without limits.
2. In a safe region, one flat image and one small stack. Check the pixels, the XY placement and
   Z against the vendor's software.
3. Place three or four focus points spread over the area, not in a line. Read the map's label:
   "exact fit" means as many points as the model has parameters, an rms means the surface had
   points to spare.
4. Scan a few positions. The picture is the projection of each position; a stack is its
   brightest plane.
5. Test detection on one tile before the whole sample. The threshold is in raw counts.
6. Acquire a few targets and look at the pairs in the list.

Only after these, larger acquisitions. The mock and the LAS X simulator prove the software,
never the stage calibration, the optics or the throughput of the real instrument.

## Going back

Keep the previous environment. Going back is a matter of activating the old environment and
starting its window; run data written by the new one stays readable.

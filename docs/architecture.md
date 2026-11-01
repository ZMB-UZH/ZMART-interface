# How this is put together

Why it is built this way, and the rules for changing it, are in
`principles.md`.

The interface has two halves that meet over HTTP. The **page** runs in the
window (a web page, drawn by WebView2 on Windows) and is written in strict
TypeScript. The **bridge** runs in Python beside it. It is the only part that
talks to the microscope, through the ZMART Controller, and to the two ZMART
tools that sit beside the interface:

```
  the page (TypeScript)                the bridge (Python)               beside it
  ---------------------                -------------------               ---------
  framework/window/   the frame        framework/bridge/  the HTTP door
  workflows/<name>/   a workflow  -->  workflows/<name>/bridge/  -------> ZMART Controller --> driver --> microscope
    backend/live.ts   its verbs        workflows/<name>/microscope/        (any ZMART driver, or the mock)
                                       workflows/<name>/storage/   -----> ZMART-viewer (serves the run's pictures)
    canvas/engines/   the picture <--------------------------------------- (the viewer's own server)
                                       workflows/<name>/analysis/  -----> ZMART-analysis (focus, detection, plots)
```

`<name>` is `target_acquisition`, the one workflow there is. Everything about a
microscope -- the controller, the mock, the pictures, the analysis -- lives in
that workflow, its Python half included. The framework and the bridge's door
know no microscope.

## Three layers

```
zmart_interface/
  framework/     the engine. It runs any workflow and knows none.
    window/        the frame the operator sees: the rail, the chooser, the
                   panels, the channel, the press, the runner, and the
                   framework's half of the run document.
    rules/         step ordering and readiness, finding the workflow folders,
                   and the version check.
    bridge/        the Python door: serves the page, dispatches each
                   workflow's routes, knows no workflow. A workflow's Python
                   half imports of it only `bridge/api.py`.
    fixtures/      `three_steps/`, the framework's own test workflow, and
                   `three_steps_at_0_2_0/`, its copy frozen at API 0.2.0.
    types.ts       the types of the agreement, offered to workflows through
                   `api/`.
  api/           the workflow API: the one door a workflow uses into the
                 interface (`docs/the-workflow-api.md`).
  parts/         what more than one workflow is built from. Empty today.
  workflows/     one folder per workflow; the folder's name is the chooser's
                 entry.
```

**A part passes the oven test.** Could this module serve a workflow that has
nothing to do with a microscope -- an e-learning course on cleaning an oven,
say? If not, it is not a part: it belongs to the workflow that uses it. And a
module that passes the test still starts inside the workflow that needs it,
and moves to `parts/` when a second workflow needs it too, not before. That is
why `parts/` is empty: target acquisition is the only workflow, so its canvas,
its microscope seam, its storage and its analysis all live in its folder.

**Workflows share nothing.** A workflow imports its own files, the workflow
API and the npm packages the interface lists; nothing else. It can be dropped
into `workflows/` from another repository and built in
(`docs/running-your-own-workflows.md`).

A workflow folder, as target acquisition has it:

```
examples/target_acquisition/
  flow.ts          the front door: its steps, a sentence for the chooser, its
                   panels, how it wires itself to the page (`install`), which
                   backend it speaks to (`backendFor`), what a run holds
                   (`freshState`).
  workflow.json    its name, its own version, and the API versions it fits.
  types.ts         its run, its page and its steps, as the API's types filled
                   in for it.
  the-run.ts       the steps, in order.
  on-the-page.ts   what it lends its page, and its hooks.
  the-canvas.ts    what it puts on its canvas, wired to the page.
  steps/<step>/    one folder per step: its declaration (`step.ts`), its run
                   (`run.ts`), its controls (`channel.ts`), what it draws on the
                   picture (`layers.ts`), and its tests.
  shared/          what several of its steps use: the carrier geometry, the
                   scan-field arithmetic, the gating rules, the stage picture,
                   the run document (`run-document.ts`), the protocol file.
  backend/         its microscope seam: every verb its steps call
                   (`verbs.ts`), over the bridge (`live.ts`) or in the
                   browser alone (`pretend.ts`).
  canvas/          the picture the operator pans, zooms and draws on.
  microscope/      the instruments it offers, the pretend sample, and in Python
                   the reading of the controller's answers.
  bridge/          its Python half: its routes under `/api/target_acquisition/`.
  storage/, analysis/, mock_microscope/, testing/
  style.css        its own look, after the frame's.
```

Every test stands beside what it tests.

## The workflow API

What a workflow may use of the interface, and what it declares for the
interface to run it, is the workflow API: `zmart_interface/api/index.ts`,
explained in `docs/the-workflow-api.md`. It is at **0.2.0**
(`api/version.json`); each workflow states the range it fits in its
`workflow.json`, and the build stops with a sentence when one does not fit.

Two checks hold the API to its version. `api/report.txt` holds the
declaration of every name the API offers, and `npm run check:api` fails when
the API declares something else without a new version. And the fixture
frozen at 0.2.0 must still type-check and walk.

A workflow fills the API's types for itself. `WorkflowTypes` is one bag --
its run's keys, its backend, what it lends its page, what its steps show --
and `Page<W>`, `Run<W>` and `Step<W>` speak of that workflow. Target
acquisition fills it in its `types.ts`: its run is `freshState`'s keys
(`shared/run-document.ts`), its backend is `backend/verbs.ts`'s `Backend`,
and its lends are read off the functions it lends. Where a lend is an object
a function makes, its type is written out as an interface beside it
(`CanvasOnThePage`, `FocusOnThePage`, `CarrierOnThePage`), so the page's
type, made of its lends, never depends on itself.

## How the page is composed

`framework/window/main.ts` reads which workflow to open on and hands the
workflows to `framework/window/pages.ts`, which composes the page, naming no
workflow. In order:

1. The workflows are assembled from the folders under `workflows/`
   (`framework/rules/finding-workflows.ts`): every folder with a `flow.ts`.
2. The run document is made: the framework's keys, and beside them what the
   open workflow's `freshState` answers (`framework/window/run-state.ts`). It
   is one object of plain data, started over in place when another workflow
   is chosen.
3. The frame is one: the rail and its chooser, the runner, the tabs, the
   channel and the action bar.
4. Each workflow gets a page of its own over the frame, the first time it is
   opened: its panels are built, its backend is what its `backendFor` answers
   for the page's address, and its `install(page)` answers what it lends its
   page and its hooks.
5. The page renders on the first step.

Only the open workflow's hooks are called; the one being left hears
`onLeave`:

| hook | called | what target acquisition does |
| --- | --- | --- |
| `onRender` | after every full render | shows or hides the canvas's framing presses |
| `onPanelShown(step, key)` | whenever a panel is drawn | which picture the live overview shows |
| `onReset` | when the run starts over (Disconnect, or this workflow chosen) | stops the stage clock, asks for the instruments again, refits the picture |
| `onLeave` | when another workflow is chosen | stops the stage clock |
| `onChannelMounted(host, channel)` | after a step's controls are mounted | puts the protocol's progress over them |

A step that walks the others says `walks`; the framework finds it by that,
and the walk's Interrupt (`page.interruptWalk`) brakes the step in hand.

## What the framework owns

The run state, step ordering and reachability, the tabs, the action bar,
and the mount lifecycle. Workflows only declare. Readiness belongs to the
step (`ready(run, page)`); the runner (`framework/window/runner.ts`) knows only
how a run begins and ends -- finished, stopped by hand, failed -- and each step
carries its own `run` and `finished`. Adding a workflow is writing its
folder; if it means editing the framework, the framework is missing
something.

## One owner per fact

Every fact has one home, and everything else reads it there. The sample's
geometry is `microscope/pretend-sample/`; the peak rules are
`shared/focus-curves.ts`; the fitted surface is
`steps/focus_strategy/surface.ts`; where a carrier's wells are is
`shared/carriers.ts`. If a rule has to appear in two files, the split was
wrong -- merge them back rather than keeping both in step.

## Target acquisition's seam: `backend/`

No step knows which microscope it is talking to. A step never calls
`setTimeout`, never reaches for a synthetic sample, never touches hardware:
it calls the backend and awaits.

`backend/verbs.ts` lists every verb as one interface, `Backend`:

```ts
export interface Backend {
  instruments(): Promise<string[]>;
  connect(session, connecting?): Promise<{ info }>;   disconnect(); info();
  get_xyz(): Promise<XyzReading>;   set_xyz(place: Place): Promise<XyzReading>;
  get_acquisition_settings();   set_state(settings);   readSetting(type, how?);
  acquire(asked): Promise<ControllerAnswer<CaptureRecord>>;
  viewOf(acquisitionType);   viewerSources(onStatus?);
  measureFocus(points, how?);   stopFocusMeasure();
  scanOverview(how);   stopScan();
  discoverTargets(how?);   stopTargets();
  acquireTargets(how);   stopAcquireTargets();
  computePlot(how);   stopPlot();
  protocols(instrument?);   saveProtocol(protocol);   saveProtocolAs(protocol, name);
}
```

`live.ts` answers each over the bridge, under `/api/target_acquisition/`;
`pretend.ts` answers in the browser alone, for the page's own tests
(`?backend=pretend`). One interface, so the two cannot drift apart without the
type checker saying where. `backend-contract.ts` lists the promises the verbs
keep; its test holds the pretend backend to them on every change and a
running bridge to them when asked.

Behind the bridge, `microscope/instrument.py` reads the controller's answers
once for everyone. Every command answers `{"success": ..., "output": ...}`;
the bridge hands back the output and turns `success: False` into a sentence
the page shows where the operator pressed. A capture is the exception: its
answer goes to the page untouched, so the page reads the output's `files`
and `planes` exactly as a Python script would. `get_xyz` and `set_xyz` answer
the same thing: each axis's `position` in micrometres, its `unit`, the raw
reading of every motor under `actuator_readings`, the one it moved by as
`used_actuator`, and the `canvas` -- everywhere a
picture can show, the travel widened by half a field. The travel stays in
the driver: a move past it is refused with a sentence the operator sees.

Every capture is converted the moment it lands into one OME-Zarr image per
position (`storage/zarr_positions.py`). The viewer's server, started beside
the run by `storage/viewer_service.py`, links each acquisition's positions
into one live picture and serves it to the page's drawing engine. Focus
scoring, object detection and the population plots run as ZMART-analysis
pipelines; `analysis/warm.py` keeps one engine running for the whole session.

The mock microscope (`mock_microscope/`) is a complete ZMART driver with no
hardware. It plugs into the controller like any other driver, and it is what
every test runs on.

## Steps, channels and panels

A step is data:

```ts
export const focusStrategy: TaStep = {
  id: "focus",
  title: "Focus strategy",
  btn: "Run focus map",         // no btn: nothing to press
  panels: [],                   // panels of its own; the canvas stays from Connect on
  mode: "focus",                // what kind of work, for the layers
  ready: (run) => null,         // null = go; a phrase = what is missing
  run: runFocus,                // what it does, in its run.ts
  finished: focusFinished,      // what it files once it has run
  channel: focusChannel,        // its controls, in its channel.ts
};
```

Every field is written out in `examples/README.md`, and in
the API's types. Numbering comes from position; a step may set its own `n`.

A step's controls are its **channel**: the column beside the canvas. A
channel owns that column and nothing else. Its `mount(host, page, { locked })`
answers where the step's press goes and what to put away when the channel
changes hands. The framework mounts it once per step and lock state, so a
channel keeps its own state and redraws itself; it never asks the framework to
rebuild it, which would destroy the field being typed into.

**If a step is about the sample on the stage, it belongs on the canvas; a tab
is for something that is not the stage at all** (a plot, a gallery, a form).
The canvas appears at the step that first asks for it and stays for the rest
of the run.

A step stays editable while nothing has consumed its output, and locks once
something has. There is no held-and-applied edit: two copies of the plan, the
one on screen and the one the run would use, is the one-owner rule broken in
the way that fails silently.

## The canvas: `examples/target_acquisition/canvas/`

```
  surface.ts       the canvas's own surface: the view, the two gestures, a
                   drawing surface beneath and one above, a slot between
  viewer.ts        the canvas in a box: its layers, their buttons, the fade,
                   the lock, and where a press or a drag goes
  layers-above.ts  the stack, drawn beneath and over the picture
  engines/         the drawing engine, neuroglancer, behind the viewer slot
                   (`docs/viewer-slot.md`), and what it shares
  viewer-panel.ts  the picture's display settings: channels, windows, colours
  panel.ts         the canvas as the panel the workflow declares
```

The canvas is handed layers and, when the page wants them, functions to
answer a press with. It is never told which step it is in. What target
acquisition draws on it is its steps': each step's `layers.ts` says what it
draws and what a press on it means, handed a `StageRun`
(`shared/stage.ts`). The stage picture keeps only its own furniture -- the
travel, where the stage is, the scale bar -- and the order the stack is drawn
in, the one thing no step can know.

`engines/neuroglancer-under/viewer.ts` is the only file of the page that
knows neuroglancer exists. It steers it through the ZMART viewer's drawing
primitives (`zmart-viewer/drawing/primitives/`), the one way the viewer's own
window steers it too: making the engine with its interface off, keeping its
layers in step with a scene, feeding and refreshing stores, its axes and its
camera in micrometres. What stays in the file is the page's own: how the
run's acquisitions become a scene, where the view opens, and the handle the
canvas drives. The build takes the primitives from the installed viewer
(`tools/the-installed-viewer.mjs`); the type checker reads them by the copy of
their declarations in `engines/zmart-viewer-drawing/`, which a test holds
equal to the installed viewer's.

## The checks

Every commit holds to these; CI runs them.

- **Types.** `tsc --noEmit`, strict, on the whole page; the page is TypeScript
  throughout. What stays JavaScript is the build's own tooling
  (`tools/*.mjs`, the configs), which runs in Node.
- **Imports.** dependency-cruiser (`.dependency-cruiser.cjs`): no cycles; the
  framework knows no workflow; parts know no workflow; workflows share
  nothing; a workflow and the fixture use only the API; a step imports no
  other step, and nothing below the steps imports one.
- **Dead code.** knip: no file, export or dependency nothing uses.
- **The API.** `npm run check:api`, and the frozen fixture (above).
- **The fit.** The build checks every workflow's `workflow.json` against the
  API's version.
- **Tests.** vitest on the page's modules (`*.test.ts`), pytest on the Python
  (`test_*.py`), Playwright driving the real page (`*.spec.ts`). The
  Playwright tests are a smoke net, not a specification: the page is nearly
  all canvas, and driving it catches what reading the source does not.
  `examples/target_acquisition/walk.spec.ts` walks all ten steps on the built
  page through the real bridge. Playwright fails rather than skipping when it
  finds no browser.

How the page is built, and why the build is one HTML file with two
background programs beside it, is in `docs/building-the-page.md`.

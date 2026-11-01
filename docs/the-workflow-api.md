# The workflow API

The agreement between a workflow and the interface that runs it. A workflow is
a folder in a folder of workflows (`examples/` here; see `docs/running-your-own-workflows.md`); this page says what it may use of
the interface, what it declares for the interface to run it, and when the
interface calls what it declares. The types are in `zmart_interface/api/index.ts`;
this page is their explanation.

## Its edge

A workflow imports three things: its own files, `zmart_interface/api/index.ts`,
and the npm packages listed in the interface's `package.json`. Anything else
stops the build with a sentence naming the import (dependency-cruiser). Two
workflows share nothing, not even a panel.

Its Python half (`<folder>/bridge/`) imports of the interface only
`zmart_interface/framework/bridge/api.py`, and reaches its own folder by
relative imports, so the folder works under any name.

## Its version

`zmart_interface/api/version.json` holds the API's version, `API_VERSION` in the
types. Each workflow states the versions it works with in its own
`workflow.json`:

```json
{ "name": "target_acquisition", "version": "0.2.0", "api": "^0.2.0" }
```

The build, and the development server as it starts, stop with a sentence when
a workflow's range does not include the API's version, or when a workflow has
no `workflow.json`. The API is at 0.2.0, and stays at 0.x until a second
workflow has been written against it. Adding a hook or an optional field is an
addition; a new required field, a changed argument, a changed default type or a
changed moment of calling is a breaking change. While the API is 0.x, a
breaking change raises the minor (0.2.0 to 0.3.0) and an addition the patch;
from 1.0.0 on, a breaking change raises the major and an addition the minor.

Two checks hold the API to its version:

- **The declaration report.** `zmart_interface/api/report.txt` holds the
  declaration of every name the API offers, as the type checker writes it, under
  the version it belongs to. `npm run check:api` (in CI) fails when the API
  declares something else than the report says; `node tools/the-api-report.mjs
  --write` writes it again, and refuses to while `api/version.json` still names
  the version the report was written for. So a change to the API cannot reach
  `main` without its version.
- **The frozen fixture.** `framework/fixtures/three_steps_at_0_2_0/` is the
  framework's fixture as it stood at 0.2.0, never edited. It uses every field
  and hook the API offered then; it must still type-check, and
  `framework/window/the-frozen-fixture.test.ts` walks it. When it stops fitting,
  the API has broken its word to the workflows written for 0.2.0: that is a new
  breaking version, and a new frozen copy beside this one.

## What a workflow may use

- `API_VERSION`.
- The helpers a step reaches for: `el(id)`, `css(name)` and `sizeCanvas(canvas)`
  (the page's DOM and its colours), `sideGroup(title)` (one box down the
  channel), `status` (the bar's sentence), `atBridge(route)` (a route on the
  bridge as an address the page can fetch), `editedAt` and `staleSteps` (the
  rules about orange steps), and `StepShape`, what those rules read of a step.
- `ThemeVar`: the page's base colours and measures, as CSS custom properties.

## What a workflow declares

`flow.ts` exports, every one optional but the first two:

| export | what it is |
| --- | --- |
| `steps` | the steps, in order (`Step`) |
| `blurb` | the chooser's sentence |
| `name` | the chooser's entry, when the folder's name would misname it |
| `panels` | what it puts on screen (`Panel`) |
| `opensFirst` | the workflow a fresh page opens on |
| `install(page)` | how it wires itself to its page; answers `{ lends, hooks }` |
| `backendFor(search)` | what its steps speak to, given the page's address |
| `freshState({ backend })` | its keys of the run document, as a fresh run holds them |
| `keptAcrossSessions` | which of those keys survive a disconnect |
| `forTests(run)` | what a browser test may read of them |

A step's fields, a panel's, a channel's and the hooks are written out in
`examples/README.md` and typed in `api/index.ts`
(`Step`, `Panel`, `Channel`, `Hooks`).

`WorkflowTypes` is one bag a workflow fills in -- its `state`, `backend`,
`lends`, `shown` and its steps' own fields -- so `Page<W>`, `Run<W>` and
`Step<W>` speak of its own. `framework/fixtures/three_steps/flow.ts` does it
for the smallest workflow that uses every field and hook.

## What the page offers a step

`Page<W>`: `run` (the run document), `backend`, `panels`, `shown`, `steps()`,
`step(i)`, `indexOfStep(id)`, `activeStep()`, `renderAll()`, `renderRail()`,
`renderActionBar()`, `focusPanelsFor(i)`, `readiness(step)`,
`stateEdited(id)`, `runStep(i, options)`, `resetRun()`, `remountChannel()`,
`interruptWalk()` and `shownPanel()`, plus what the workflow lends. The
interface's own machinery (switching workflows, building pages) is not on it.

The run document is plain data. A workflow may write the framework's `done`,
`stale`, `ran`, `notes`, `activeIdx`, `walk` and `sideFolded`, and its own
keys; `wf`, `running`, `interrupting`, `failed`, `tabs`, `tab` and
`sideMounted` it only reads (`FrameworkRun`).

## When things are called

This is part of the agreement: a changed moment is a breaking change.

- `arrived(page)`: whenever the page focuses on a step (`focusPanelsFor`):
  a click in the rail, the page opening, a reset, after every run (finished
  or stopped), and wherever a walking step focuses.
- `settledByStanding(page)`: only on a click in the rail.
- `ready(run, page)`: whenever the press is drawn, and whenever a step asks
  `page.readiness(step)`.
- `run(page, step, options)`: on the step's press, or `runStep`; `finished`
  once it finished.
- `mount(host, page, { locked })`: once per step and per locked state, or on
  every render for a channel that says `rebuildsOnEveryRender`; `destroy()`
  when the channel changes hands.
- The hooks run only for the workflow that is open: `onRender` after every
  full render, `onPanelShown(step, key)` whenever a panel is drawn, `onReset`
  when the run starts over (Disconnect, or this workflow chosen),
  `onChannelMounted(host, channel)` after a step's controls are mounted, and
  `onLeave` when another workflow is chosen.

## The Python side

`zmart_interface/framework/bridge/api.py` is the one module of the framework a
Python half imports. A half defines `routes(register)`; `register(method, path,
handler, prefix=False)` puts a route under `/api/<folder>/`, and a prefix route
hands its handler the rest of the path. A handler takes the request's JSON body
and the raw query string and answers a dictionary, or `Bytes(body,
content_type)` (sent with `Cache-Control: no-store`). `Refusal(message,
status)` answers its status with the sentence; `KeyError`, `ValueError` and
`TypeError` answer 400. A half may also define `add_arguments(group)` (its own
command-line options), `start(args)` (which may answer the window's title) and
`close(wait_s)`. Handlers run on the bridge's request threads, with no lock
held. A workflow's folder name is a Python identifier.

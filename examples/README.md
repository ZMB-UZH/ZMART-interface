# The example workflows: one folder each, and the folder's name is its name

This is the interface's own **folder of workflows**, with one example in it.
It is here to test the framework with and to learn from, and it is not
installed with the interface: the workflows we run at the ZMB live in ZMART
Microscopy, in a folder of workflows of their own. A page is built from one
such folder, named by `ZMART_INTERFACE_WORKFLOWS`; when that is not set, in a
checkout of this repository, it is built from this one, into `built-page/`.

Every folder in here that contains a `flow.ts` is a workflow the operator can
choose. The folder's name is what the chooser at the top left of the window
shows — underscores read as spaces, first letter capitalised, so
`target_acquisition` appears as **Target acquisition**. A flow whose folder
rule would come out wrong may say its own name instead (`export const name`),
for an acronym the rule would lower-case. Adding a workflow means adding a
folder with a `flow.ts` and a `workflow.json` in it; nothing else in the
interface has to change,
because the framework finds these folders by looking
(`../zmart_interface/framework/rules/finding-workflows.ts` says how).

There is one example here:

- **`target_acquisition/`** — a run on a microscope that has already been set
  up: find the targets on an overview and acquire them.

A workflow of your own goes in a folder of workflows of your own, anywhere on
the computer, and the page is built from that folder;
`../docs/running-your-own-workflows.md` says how.

**A new workflow starts from the template**, the framework's own fixture
`../zmart_interface/framework/fixtures/three_steps/`: the smallest complete workflow, typed
against the workflow API alone and using every field and hook. Copy its
folder into your own folder of workflows under the new workflow's name, give its `workflow.json` that name,
and change it from there.

Setting a microscope up -- its travel limits, which way the picture is turned,
how the objectives line up, and where its coordinates count from -- is done
once per microscope with that microscope's driver, and is not a workflow of
this interface (see the README).

## What is inside a workflow's folder

```
target_acquisition/
  flow.ts        the front door: the steps, in order, plus a sentence for the
                 chooser. Open this first — it is the whole workflow in one
                 screenful.
  workflow.json  its name, its own version, and the workflow API versions it
                 fits ("api": "^0.2.0").
  types.ts       its run, its page and its steps, as the API's types filled in
                 for it (TaRun, TaPage, TaStep).
  steps/         one folder per step, connect/ to run_protocol/. Each holds
                 the step's declaration (step.ts); what the step does when it
                 is run (run.ts); the controls it docks in the channel beside
                 the canvas (channel.ts); what it draws on the picture
                 (layers.ts); and, where the step shows something of its own,
                 a file named for what that is — gate.ts, gallery.ts — rather
                 than for the kind of thing it is.
  shared/        what several steps of this workflow use: the carrier geometry,
                 the scan-field arithmetic, the layers the run draws, and the
                 small things they share on the page (page-helpers.ts).
  backend/       the workflow's own verbs: verbs.ts lists them, live.ts answers
                 them over the bridge, pretend.ts for the rehearsal, and the
                 promises both keep.
  bridge/        the workflow's Python half on the bridge: the focus map, the
                 scans, finding and taking the targets, the plots and the
                 protocols, with their routes under /api/target_acquisition/.
  the-canvas.ts  what the workflow puts on its canvas: the stage picture, the
                 live picture of the run, the axes under them.
  on-the-page.ts how the workflow is wired to the page when it opens: the
                 canvas, and the functions its steps lend the page.
  style.css      the workflow's own look, loaded after the frame's.
```

Its tests sit beside what they test, its browser walks included: nothing
outside the folder is about it, so taking the folder out takes all of it.

Target acquisition's microscope seam is its `backend/`: `live.ts`, which
speaks to the bridge, and `pretend.ts`, the in-browser rehearsal used by some
of the page's own tests, with the same verbs. Its runs on the bridge are in
its `bridge/`, the Python half with its routes under
`/api/target_acquisition/`. Every call to the instrument lives behind that
seam — a step only calls it and awaits.

The rule that decides where a file goes: **put it beside the things that use
it, at the lowest folder that covers them all.** Used by one step → in that
step's folder. Used by several steps of one workflow → that workflow's
`shared/`. Used by more than one workflow, and passing the oven test (could
it serve a workflow with nothing to do with a microscope?) → `../parts/`.

## A step belongs to its workflow

A workflow shares nothing with another: not a step, not a panel. A step that a
second workflow would also need is written again there, or, if it is truly
general, its general part becomes a part (`../parts/`).

## What a step is made of

A step is data, not code: a short description the framework reads, typed as
the API's `Step` (a workflow's own `TaStep` in target acquisition). These are
its fields, all optional except the first two.

- `id` — the short name the page files this step's result under.
- `title` — what the step is called in the rail down the left.
- `panels` — which modules the step wants on screen, named. An empty list means
  "nothing of my own"; see `../framework/rules/steps.ts`, which decides what that
  comes to once the canvas is in play.
- `btn` — the words on the button that carries the step out. A step with no
  `btn` has nothing to press: some steps are completed by doing the thing they
  are about — the carrier is settled by being configured, the scan fields by
  being drawn — and asking for a press afterwards would only ask the operator
  to confirm what they have already done.
- `ownButton` — the step's own panel builds its button, so the framework should not
  add a second one underneath.
- `ms` — how long the page waits before a step with no `run` of its own
  counts as finished: the rehearsal's pace, for a step whose work is done
  when its press is released.
- `mode` — what kind of work the step is about: `focus`, `scan`, `detect`,
  `targets`, and so on. The layers drawn on the picture read it to decide what
  to draw while this step is being looked at.
- `run(page, step, options)` — what the step does when its press is pressed:
  it calls the backend and answers a promise. Nothing back means the run
  finished; `{ stopped: true, note }` means the operator's hand put it down,
  with the sentence to say beside the press; `{ failed: why }` means it failed
  and has already said so in its own box. A run that throws is a failure the
  page reports. `options` is what a second press hands over, such as the one
  tile to take again.
- `finished(page, step)` — called once a run finished: where the step files
  what it came to, its note and whatever the next step now works with.
- `brake(page)` — how a running step is stopped, when it can be: the press
  becomes Interrupt while the step runs, and this is what it does.
- `again` — the words on the press once the step has run, instead of
  "Run again".
- `rerunCurrent(page)` — for a step that can take one item again: answers a
  function that gives `run` its `options`, or `null` when there is nothing
  current. The page then offers a "Rerun current" press before the main one.
- `walks` — this step walks the other steps in turn (Run protocol is the one
  today): `{ press(page), whileWalking }`. Its press calls `press` instead of
  running through the page; while the walk goes it sets `page.run.walk.running`,
  and reads `page.run.walk.interrupted` to end after the step in hand. The
  walk's Interrupt is the framework's (`page.interruptWalk()`): it latches
  `interrupted` and presses the step in hand's `brake`. A step that walks the
  others is never left orange or done by an edit above it, since it has no
  settings of its own to confirm. `whileWalking` is the sentence beside that
  Interrupt ("running the protocol"); without it the page says "running" and
  the step's title.
- `beside(run, { done })` — the sentence beside the press once nothing blocks
  it, instead of the step's note.
- `noHint` — nothing stands beside the press: what the step waits for and
  what it came to are in its own box.
- `afterThePress(host, page)` — anything else the step puts beside its press.
- `channel` — the step's controls in the column beside the canvas:
  `{ id, label, mount(host, page, { locked }) }`. Mounted once per step and
  kept, so a field being typed into is never destroyed; a channel that
  `rebuildsOnEveryRender` says so. `mount` may answer `{ actionSlot, destroy }`:
  `actionSlot` is the element at the end of the controls where the step's
  press goes (without one, the press goes in the foot of the panel being
  looked at, the `foot` its `build` handed back), and `destroy()` is called
  when the channel changes hands, to put away what it holds outside the
  column (an editor drawing on the canvas, say).
- `arrived(page)` — what the step does to the picture when the operator
  arrives on it: which layers to show, which acquisition to hide.
- `settledByStanding(page)` — for a step with no press: standing on it is
  what settles it, and this says what that means.
- `ready(run, page)` — what the step still needs before it may be carried
  out. It is handed the run so far, and the page for a rule that needs the
  other steps (`staleSteps(page.steps(), run.done, run.stale)`, say), and
  answers either `null`, meaning go ahead, or a short
  phrase saying what is missing, which the page shows beside the greyed-out
  button. A step with no rule is always ready. Readiness belongs to the step
  rather than the page around it: only the focus step knows what a focus map
  needs, and putting the rule on the step is what lets a new workflow be a list
  of steps instead of another rule added to the shell.
- `nothingWaitsOnThis` — the steps after this one do not wait for it. A run is
  walked in order because each step usually produces something the next one
  needs; a step that only shows the operator something produces nothing to wait
  for, and saying so here lets them walk straight past it. See
  `../framework/rules/steps.ts`, which is where the rule lives.

## What a step's run is handed: the page

Every hook above takes `page` first: the workflow's own page, built over
the frame in `../framework/window/pages.ts`. It carries everything a step
may need: `page.run`, the run document (the framework's keys from
`../framework/window/run-state.ts`, the workflow's from its own
`freshState`), one object shared by every workflow's page; `page.backend`,
the seam to whatever the workflow drives; `page.flow()`, the workflow as
assembled, and `page.steps()`; `page.panels`, the workflow's own panels,
each with what its `build` handed back; `page.shown`, the handles of the
boxes the workflow's steps put on screen; the page's render functions
(`renderAll`, `renderRail`, `renderActionBar`); `page.stateEdited(id)`, the
one call every edit goes through; and what the workflow lends its steps
(`page.surfaceZAt`, `page.pictureOf`, ...). A step reaches the rest of the
page only through it, which is what lets each step live in its own folder;
and a workflow reaches only its own page, so what one lends is never found
on another's.

A workflow's hooks are how the framework calls back into a workflow it knows
nothing about. Its `install` answers them, every one optional, and only the
open workflow's are called:

- `onRender()` — after every full render.
- `onPanelShown(step, key)` — whenever a panel is drawn.
- `onReset()` — when the run starts over: on Disconnect, or when this
  workflow is chosen. Target acquisition stops its stage clock here and asks
  for the instruments again.
- `onLeave()` — when another workflow is chosen. Target acquisition stops
  its stage clock.
- `onChannelMounted(host, channel)` — after the step's controls were
  mounted. Target acquisition puts the protocol's progress over them.

## What a flow is made of

`flow.ts` exports `steps` (the list) and `blurb` (the sentence), and may also
export any of these. Every one is optional: a workflow of plain steps that
drives nothing and keeps nothing of its own needs only the first two.

- `name` — the chooser's entry, when the folder rule would misname it (an
  acronym, mostly).
- `panels` — what the workflow puts on screen: the canvas, or a panel of its
  own. A panel is `{ key, label, stays, build(host) }`; the framework builds
  one element per key and the panel fills it through `build`, handing back
  whatever the steps need of it. Of what `build` hands back, the framework
  reads these, every one optional: `channel`, the column a step's controls
  are mounted in; `divider`, the draggable edge of that column, and `fold`,
  the press that puts the column away; `foot`, where a step's press goes
  when the step's controls have no slot of their own; and `shown()`, which
  the framework calls when the panel comes on screen or its room changes,
  since a hidden box has no size to draw into. A panel with a channel but no
  divider simply has a column of fixed width.
- `opensFirst` — the workflow a fresh page opens on.
- `install(page)` — how the workflow wires itself to its page, once, the
  first time a run of it begins: as the page opens on it, or when the
  operator chooses it. `page.run` is then a run of this workflow, with its
  own `freshState` keys in place, and its panels are built. Answers
  `{ lends, hooks }`: what it lends its page (target acquisition's canvas and
  its steps' functions) and its hooks (above).
- `backendFor(search)` — which backend the steps speak to, given the page's
  own address (a `URLSearchParams`): target acquisition puts the shared verbs
  and its own together, over the bridge, or the in-browser rehearsal for
  `?backend=pretend`, and its `connect` names the run folder
  (`target-acquisition_<hash>`). A workflow that drives
  nothing leaves this out and is handed an empty object.
- `freshState({ backend })` — the workflow's half of the run document: every
  key its steps read, with the value it has before anything was done. The
  framework lays these beside its own keys (which step is active, what is
  done, what is running — `../framework/window/run-state.ts`), so a step
  finds both on `page.run`. The framework's keys cannot be overwritten.
- `keptAcrossSessions` — which of those keys survive a disconnect or a change
  of workflow. Target acquisition keeps the session and the list of
  instruments, since editing them is the reason to disconnect.
- `forTests(state)` — what a browser test may read of the workflow's state,
  through `window.__theRunState()`, beside the framework's own fields.

The framework's own fixture, `../framework/fixtures/three_steps/flow.ts`,
is the smallest flow that uses all of these, typed against the workflow API
(imported as `zmart-interface/api`, which is `../zmart_interface/api/index.ts`,
explained in `docs/the-workflow-api.md`); read it next to
this list. A workflow imports nothing of the interface but that API, and says
which versions of it it works with in its `workflow.json`.

# Running your own workflows

The interface is a framework: it runs any workflow it is handed, and brings
none of its own. Installing it gives you the frame of the operator window and
the bridge to the microscope, but no steps to click through. The steps come
from a **folder of workflows**, which you keep wherever suits you: in a
repository of your own, or, for the workflows we run at the ZMB, in ZMART
Microscopy (`workflows/non-coders/interface/`).

A folder of workflows holds one folder per workflow, and, once it has been
built, the page built from them:

```
my_workflows/
  my_workflow/       one workflow (below)
  another_one/       a second workflow, if you have one
  built-page/        the page, built from the workflows beside it
```

You tell the interface where that folder is with one setting, the environment
variable `ZMART_INTERFACE_WORKFLOWS`. The page is built from it, and the bridge
loads the workflows' Python halves and serves the page from it, so the page and
the workflows always match. The interface's own repository has one such
folder, `examples/`, which holds the example workflow *Target acquisition*:
it is what the interface's tests run, and it is used when the setting is left
out in a checkout of this repository. It is not installed with the interface.

This page says how to write a workflow, build its page and run it. It assumes
you have read `examples/README.md`, which explains what a step and a flow are
made of.

## What the folder holds

A workflow is a folder with a `flow.ts` in it, written in TypeScript like the
rest of the page and checked with it (`npm run check:types`). Beside it go whatever the
workflow needs -- its steps in folders of their own, shared code, a stylesheet,
a piece of markup read in as text -- and, if it has one, its Python half:

```
my_workflow/
  workflow.json      its name, its version, and the workflow API it works with
  flow.ts            the front door: the steps, the blurb, the panels, install, ...
  steps/
    begin/step.ts
    ...
  bridge/            its Python half, a package (optional; below)
    __init__.py
```

The folder's name is the workflow's name in the chooser, and the first part
of its routes at the bridge (`/api/my_workflow/...`).

## What a workflow may import

A workflow imports its own files, the workflow API, and the npm packages the
interface lists. The API is imported by a fixed name, wherever the workflow
sits:

```ts
import type { Flow } from "zmart-interface/api";
```

The build maps that name onto `zmart_interface/api/index.ts` in the
interface's checkout (`tools/the-workflows-folder.mjs`), which is why a
workflow does not have to live inside the interface. Anything else stops the
build with a sentence naming the import, and so does an import of another
workflow: two workflows share nothing. `docs/the-workflow-api.md` says what the
API holds and when the interface calls what a workflow declares.

**Start from the template**: the framework's own fixture,
`zmart_interface/framework/fixtures/three_steps/`, is a complete workflow that
uses every field and hook of the API and imports nothing else -- steps, a card
panel, a Python half with one route, no microscope. Copy its folder into your
folder of workflows under your workflow's name, rename it in its
`workflow.json`, and change it from there. For a complete workflow that drives
a microscope, read `examples/target_acquisition/`. Its `Three` type shows how a
workflow fills the API's types (`WorkflowTypes`) for itself.

## Which API it was written for

Beside `flow.ts` goes a `workflow.json` naming the workflow, its own version,
and the versions of the workflow API it works with:

```json
{ "name": "my_workflow", "version": "0.1.0", "api": "^0.2.0" }
```

The build stops, saying so, when the interface's API is outside that range.

## Its dependencies

An npm package the workflow imports must be one the interface lists in its
`package.json`; the build takes it from the interface's own `node_modules`,
wherever the workflow sits, so the page holds one copy of each. A Python
package its half imports must be installed in the same Python environment as
the interface. There is one page and one Python environment.

## Building the page

The page is built in a checkout of the interface, on a computer with Node.js,
with the setting naming your folder of workflows:

```bash
cd ZMART-interface
npm ci                                                   # once
ZMART_INTERFACE_WORKFLOWS=/path/to/my_workflows npm run build
```

On Windows, in PowerShell:

```powershell
$env:ZMART_INTERFACE_WORKFLOWS = "C:\path\to\my_workflows"; npm run build
```

`docs/building-the-page.md` says what the build needs. The page is written to
`built-page/` inside your folder of workflows. Commit it there, beside the
workflows it was built from: the microscope PC has no Node.js and cannot build
it, so it runs the committed page.

## Running

On the computer that runs the interface, set the same variable and start it:

```bash
ZMART_INTERFACE_WORKFLOWS=/path/to/my_workflows zmart-interface
```

The bridge loads every workflow's Python half from that folder and serves its
`built-page/`. With the setting left out, an installed interface has nothing
to run and says so.

## A Python half

A workflow that needs the computer to do something the page cannot -- read a
file, drive an instrument, run an analysis -- gives the bridge a Python half:
a package `bridge/` in its folder that defines one function:

```python
def routes(register):
    """Add this workflow's routes to the bridge, under /api/<folder>/."""
    register("GET", "hello", say_hello)
    register("POST", "count", count_to)


def say_hello(asked, query):
    return {"hello": "world"}


def count_to(asked, query):
    to = int(asked.get("to", 3))
    if to < 0:
        raise ValueError("counting to a negative number is not something I can do")
    return {"counted": to}
```

The bridge imports every workflow's half when it starts and calls `routes`.
Your folder of workflows is put on Python's search path, so a half is imported
by its own folder's name (`my_workflow.bridge`), and its modules import each
other with relative imports (`from . import state`).
Each route lands under `/api/<folder>/`, so the two above answer
`GET /api/my_workflow/hello` and `POST /api/my_workflow/count`. A handler is
written the way the bridge's own are: it takes the request's JSON body as a
dictionary (empty for a GET) and the raw query string, and answers a
dictionary; an exception it raises reaches the page as a sentence, with status
400 for a `ValueError`. A half that fails to import stops the bridge, saying
why.

A half may also answer bytes (a picture, a file), refuse with a status of its
own, take every path under a prefix, and take part in starting and closing the
interface: its own command-line options, what it does at start (which may name
the window), and what it closes at the end. All of that is
`zmart_interface/framework/bridge/api.py`, the one module of the framework a
half imports.

Target acquisition's half, `examples/target_acquisition/bridge/`,
is the complete example to read, with its own routes for the focus map, the
scans, finding and taking the targets, the plots and the protocols.

## A half that drives a microscope

The bridge knows no microscope: it serves the page and hands each request to
the half that registered its route. A half that drives an instrument does so
itself, through the ZMART Controller, and keeps the session, its run folder
and a lock of its own, so two requests never move the stage at once.
Target acquisition's half shows how: `bridge/connecting.py` opens the session
and makes the run folder, `bridge/state.py` holds the session and the lock,
and its routes take that lock around every command to the instrument.

From the page, your steps reach the routes at the bridge's address, which
`framework/window/bridge-address.ts` knows:

```js
import { atBridge } from "zmart-interface/api";

const answer = await fetch(atBridge("/api/my_workflow/count"), {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ to: 3 }),
});
const { counted } = await answer.json();
```

A handler runs on the bridge's request thread with no lock held.

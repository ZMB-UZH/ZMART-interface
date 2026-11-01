# Building the page

The operator page is written in strict TypeScript: the frame under
`zmart_interface/`, and the workflows in a folder of workflows of their own
(`examples/` in this repository; see `docs/running-your-own-workflows.md`). It is
built with Vite into three files, which are written into that folder of
workflows as `built-page/` and committed there. Node 22.12 or
newer is needed for the build, on a developer machine; the microscope PC never
builds anything.

```bash
npm ci            # the page's packages, and neuroglancer's patch
npm run build     # the page and two files beside it -> examples/built-page/
ZMART_INTERFACE_WORKFLOWS=/path/to/my_workflows npm run build   # -> /path/to/my_workflows/built-page/
npm run dev       # http://127.0.0.1:5174, reloads on save; open it with `zmart-interface --dev`
```

The build also needs ZMART-viewer installed in the Python it runs with
(`PYTHON=` names that Python when it is not the one on the path). This page
draws exactly as the viewer's own window does, and the rules for that belong
to the viewer, in its package's `drawing` folder: the shader programs that turn
a stored value into a colour (`programs.js`, imported as
`zmart-viewer/drawing/programs.js`), and the edits that let neuroglancer keep
an image's transparency, keep a refreshed picture on screen, and let a picture
grow while it is on screen (`neuroglancer-patches.mjs`, `neuroglancer-growth.mjs`). The build takes them
from the installed viewer (`tools/the-installed-viewer.mjs` finds them), so the page
and the viewer cannot drift apart. The one neuroglancer edit only this page
needs stays in `patches/neuroglancer+2.41.2.patch`.

The viewer is pinned to a release in `pyproject.toml`, and the build stops
when the installed viewer is another one: another viewer builds another page.
Every checkout keeps Unix line endings (`.gitattributes`), because the build
copies some sources into the page as they are. So a build on any machine gives
the committed page, byte for byte.

On the ZMB workstations AppLocker runs programs only from
`C:\ProgramData\MinicondaZMB`, so the checkout, `node_modules` and the
Playwright browsers must live there.

## Checking the page

The page is TypeScript throughout; what stays JavaScript is the build's own
tooling (`tools/*.mjs` and the configs), which runs in Node. Four checks read
the sources without running them:

```bash
npm run check:types     # the page's types (tsc, strict), file and line
npm run check:imports   # which module may import which (dependency-cruiser, .dependency-cruiser.cjs)
npm run check:unused    # exports, files and packages nothing uses (knip, knip.json)
npm run check:api       # the workflow API still declares what api/report.txt says, under its version
```

`npm test` runs the types with the unit and browser tests, and so does CI. CI
fails on a wrong import, on code nothing uses and on a changed API without a
new version, too.

## What the build produces, and why it is three files rather than one

`npm run build` writes three files into `built-page/` in the folder of
workflows it built from (`examples/built-page/` here):

| file | what it is | how large |
| --- | --- | --- |
| `index.html` | the whole page — every script, every stylesheet, folded in | ~4 MB |
| `chunk_worker.bundle-*.js` | neuroglancer fetches pieces of image in this | ~0.9 MB |
| `async_computation.bundle.js` | neuroglancer unpacks them in this | ~1.6 MB |

Those three are what has to reach the microscope computer, and they have to stay
in one folder together: neuroglancer, which draws the picture, needs the two
programs beside the page.

Everything is folded into the page because the microscope PC has no toolchain
and no network: the build happens on a developer machine, the three files ship
inside the Python package, and the bridge hands them out.

### Why neuroglancer cannot be folded in

Neuroglancer hands two jobs to *background programs* — separate pieces of
JavaScript running alongside the page, so that fetching and unpacking pieces of
image does not freeze what the operator is looking at. A browser will only start
one of those from a file of its own.

Folding them into the page was tried properly before this was accepted, and it
failed twice over:

1. **The build tool will not compile them.** Neuroglancer ships each background
   program as a twenty-line list of imports written in a shorthand only a build
   tool can read. Vite does not read it: where neuroglancer asks for a background
   program, Vite copies the file across exactly as it found it. Folded into the
   page that way, the browser cannot make sense of it, the program never starts,
   and nothing reports an error — the description of a run loads and the picture
   never appears. The only place Vite will accept a compiled program is the file
   on disk inside `node_modules`, which is why `tools/neuroglancer-workers.mjs` writes
   there; a plugin handing Vite the compiled program instead was tried and Vite
   never asked for it.
2. **Even compiled, it is too large to fold in.** A background program folded
   into a page stops being a file and becomes a very long address — about a
   third longer than the program itself, because of how it has to be written
   down — and Chromium refuses to start one from an address longer than about
   2 MB. Measured in this browser: a 1.5 MB program started, a 2 MB one did not,
   and the one that did not throw nothing, warn about nothing, and appear
   nowhere. It simply never ran. The two programs come to about 2.5 MB together,
   and they have to be folded together, because a folded program cannot look up
   a file beside itself and the fetching one starts the unpacking one that way.

So the page is folded into one file and the two background programs sit beside
it. `tools/neuroglancer-workers.mjs` compiles them; `vite.config.js` places them.

### What that costs

Three things, and it is worth being honest about which of them actually matter.

**Copying a folder rather than a file.** This turns out to be very little. None
of the reasons for one file were about the copying: the microscope PC still does
not build anything, the files still arrive already built, and Python still hands
them out. A folder copies as easily as a file so long as it is copied *whole* —
which is the one new way to get this wrong, and why the build produces exactly
three files and `examples/target_acquisition/the-built-page.spec.ts` says so out loud.

**Opened straight off the disk — a `file:///…` address, which double-clicking
the page does — the picture cannot be drawn.** A browser gives such a page no
address of its own and refuses to start a background program for it, so
neuroglancer never starts. Serve the folder over HTTP and it does; the
`zmart-interface` window does exactly that, which is also how the page is
really handed out.

`build.outDir` points at `built-page/` in the folder of workflows: everything
else is source, and that folder is what the window opens. The built files are
committed beside the workflows they were built from, because the microscope PC
cannot build them; rebuild and commit them after any change to the page's
sources or to the workflows. Nothing of the page goes into the Python package:
the interface installs as the framework alone.

`zmart_interface/framework/test_the_built_page.py` holds the two to each other.
It builds the page twice into a temporary folder and fails unless both builds
and the committed folder agree, file for file and byte for byte. So a change to
the page that was never rebuilt is caught, and so is a build that comes out
differently each time. It skips, and says why, where Node.js or `npm ci` is
missing. `.gitattributes` keeps the built files exactly as the build wrote them,
so a Windows checkout does not change their line endings and set the two apart.


# The viewer slot

The canvas the operator pans and zooms has its own surface (`examples/target_acquisition/canvas/surface.ts`): the
view, the two gestures, a drawing surface beneath and one above, and a **middle slot** between
them. The picture of the run sits in that slot, drawn by a **drawing engine**. This page says
what an engine has to offer to fill it.

One engine fills the slot: `neuroglancer-under`, in `examples/target_acquisition/canvas/engines/`,
which draws the run's OME-Zarr images, served by ZMART-viewer, with neuroglancer. "Under"
names the arrangement: the picture lies **underneath** the operator's own drawing (the
carrier, the scan fields, the focus points, the targets), which the canvas draws above it.
It steers neuroglancer through ZMART-viewer's drawing primitives, the same ones the viewer's
own window uses, so the two draw a run the same way.

## What an engine is

A folder holding a `viewer.ts` that exports exactly one function:

```js
openViewer(element, options) → Promise<handle>
```

`element` is the box the picture fills. `options` says what to draw:

- `acquisitions` -- the run's images, as `[{ url, name, channels? }]`, drawn in order with
  the first at the bottom. Every `url` is a whole address (scheme and host included); an
  engine never works one out. `channels` may say each channel's name, colour, brightness
  window and whether it is shown; left out, the engine reads them from the image's own
  description.
- `background`, `transparentBackground` -- the page's colour, or a transparent ground so the
  canvas's drawing beneath shows through where nothing was imaged.
- `presentation: "2d-overlay"` -- the run's stacks stand on one table, every stack's lowest
  plane at z = 0.

Everything is in **micrometres on the stage**: the centre of the view, the zoom (micrometres
per screen pixel), the plane. No engine may expose its own notion of zoom, because the picture
and the canvas's drawings would then put the same field in two places.

## What the handle must offer

**1. Show an acquisition.** Draw what `acquisitions` names, each placed by the voxel size *and*
the position it states in its own description (two images at different voxel sizes have only
that position in common). `setChannel(index, { visible, colour, window })` changes how one
channel is drawn; `showPicture(on)` turns the whole picture off and on without closing
anything; `setPlane(z)` steps through a stack; `setMoment(t)` and
`theMomentsItCanShow()` through a time-lapse.

**2. Follow it while it grows.** A run is drawn while the microscope is still writing it.
`addSources(acquisitions)` adds the fields that have landed since -- it answers `true` when the
new list only grows the old one (the view, the colours and the brightness stay as they were),
and `false` when something was removed or replaced, so the page opens the picture again.

**3. Named views.** ZMART-viewer publishes, beside each acquisition, views of it that have names
-- the brightest plane of every stack (a maximum projection), the top of the stack, a slice.
They arrive in `acquisitions` as channels carrying a `view` description, and the acquisition
carries `embeddingUrl`, the address of the viewer's own `embedding.js`, which says which views
there are and which one is chosen. An engine draws a named view as a flat picture and keeps it
in view at every depth, since a projection has no depth of its own.

**4. Follow the canvas.** The canvas owns the view; the picture follows it. `getView()` and
`setView({ centre, zoom })` read and move the picture's view, and the page sets it from every
view the canvas reports, so the picture never lags a wheel tick behind the drawings around it.

And `destroy()`, which leaves the box empty. An engine keeps nothing in module variables, so a
page can hold two at once.

## How the picture is opened

`examples/target_acquisition/canvas/engines.ts` loads the engine by name (`openerFor`), only when it
is first needed. Target acquisition opens the run's picture inside the canvas's middle slot
once the run has sources to draw (`steps/scan_the_overview/watching-the-run.ts`). An engine
that is asked for and cannot be opened is said in words, never replaced in silence: a picture
that never arrives looks exactly like one still loading.

Neuroglancer needs two background programs, which a browser starts only from files of their
own and only in a page served over HTTP: what is copied to the microscope is the page and those
two programs beside it (`docs/building-the-page.md`).

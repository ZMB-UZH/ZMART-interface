import path from "node:path";
import { realpathSync } from "node:fs";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";
import {
  THE_UNPACKING_PROGRAM, WHERE_THE_WORKERS_LIVE, theUnpackingProgram,
} from "./tools/neuroglancer-workers.mjs";
import { theViewersDrawingFolder } from "./tools/the-installed-viewer.mjs";
import { theWorkflowsFitTheApi } from "./tools/the-workflows-fit.mjs";
import {
  BUILT_PAGE, THE_API, theWorkflowNames, theWorkflowsAddress, theWorkflowsFolder,
} from "./tools/the-workflows-folder.mjs";

const here = import.meta.dirname;

/* The folder of workflows this page is built from: the one
   `ZMART_INTERFACE_WORKFLOWS` names, or this repository's own `examples/`.
   `tools/the-workflows-folder.mjs` says why, and how a workflow outside this
   repository imports the API. */
const theWorkflows = theWorkflowsFolder();

/* Neuroglancer, one of the drawing engines in `examples/target_acquisition/canvas/
   engines/`, offers its insides under names beginning `neuroglancer/unstable/`,
   which are not folder names: its package description maps them onto a folder
   called `lib`. The mapping is written out here, so whatever an engine asks of
   neuroglancer resolves to this page's one copy of it. */
const WHERE_NEUROGLANCER_KEEPS_ITS_INSIDES = {
  find: /^neuroglancer\/unstable\//,
  replacement: `${path.join(here, "node_modules", "neuroglancer", "lib")}/`,
};

/* The drawing rules this page shares with the ZMART viewer -- the shader
   programs that turn a stored value into a colour -- are the viewer's, and are
   imported under the bare name `zmart-viewer/drawing/<file>` from the viewer
   installed in the Python that builds the page (see `tools/the-installed-viewer.mjs`). */
const theViewersDrawing = theViewersDrawingFolder();
const THE_VIEWERS_DRAWING = {
  find: /^zmart-viewer\/drawing\//,
  replacement: `${theViewersDrawing}/`,
};

/**
 * Neuroglancer's two background programs, and what the build has to do about
 * them.
 *
 * One of the three engines does part of its work in background programs, which
 * a browser will only start from a file of its own — never from something folded
 * into the page. `tools/neuroglancer-workers.mjs` explains that at length and gets the
 * two programs ready; these two plugins are the build's side of it.
 *
 * `assetsInlineLimit` below is what keeps the fetching program out of the page.
 * Everything else — every script, every stylesheet, every image — is folded in,
 * because that is what the microscope computer is meant to receive. The two
 * background programs are the exception, and the page will not draw with
 * neuroglancer without them.
 */
const THE_BACKGROUND_PROGRAMS = /\.bundle\.js$/;

/* The fetching program starts the unpacking program itself, so Vite never sees
   it asked for and would not put it in the build. Placing it here means it lands
   beside the page, which is where the fetching program now looks. */
const placeTheUnpackingProgram = {
  name: "zmart:place-neuroglancers-unpacking-program",
  apply: "build",
  async generateBundle() {
    this.emitFile({
      type: "asset",
      fileName: THE_UNPACKING_PROGRAM,
      source: await theUnpackingProgram(),
    });
  },
};

/* Neuroglancer carries two small sign-in pages for image servers we do not use.
   They arrive in the build as extra HTML, and the single-file plugin treats
   every piece of HTML as a page to fold things into and stops with an error it
   cannot explain. Dropping them first is why the build gets as far as the page
   we actually want, and nothing is lost: they belong to sign-in routes this
   application never takes. */
const dropTheSignInPagesWeDoNotUse = {
  name: "zmart:drop-neuroglancers-sign-in-pages",
  apply: "build",
  generateBundle(_options, bundle) {
    for (const name of Object.keys(bundle)) {
      if (name.endsWith(".html") && name !== "index.html") delete bundle[name];
    }
  },
};

/* The microscope PC has no toolchain and no network: the build happens on a
   developer machine, the result ships inside the Python package, and the
   bridge hands it out. Everything is therefore folded into one file.

   Everything, that is, except neuroglancer's two background programs, which a
   browser refuses to start from anything but a file. So what gets copied to the
   microscope is one folder holding three files: `index.html`, which is the whole
   page, and the two programs beside it; neuroglancer draws only with them.
   `docs/building-the-page.md` says what that costs and why it was accepted. */
export default defineConfig({
  base: "./",
  plugins: [
    /* Every workflow names the workflow API versions it works with; one that
       does not fit stops the build, and the development server, with a
       sentence naming it. */
    theWorkflowsFitTheApi({ workflows: theWorkflows, api: THE_API }),
    /* In the development server, `/@zmart-workflows/...` is the folder of
       workflows, wherever it is; the browser tests load modules by it. */
    theWorkflowsAddress(theWorkflows),
    placeTheUnpackingProgram,
    dropTheSignInPagesWeDoNotUse,
    /* The single-file plugin normally sets a handful of build options for you,
       one of which folds *everything* into the page — background programs
       included, where they cannot run. Its recommendations are therefore
       declined and written out under `build` below instead, so that the one that
       has to differ can differ, and a reader can see all of them at once. */
    viteSingleFile({ useRecommendedBuildConfig: false }),
  ],
  build: {
    /* The built page goes into the folder of workflows it was built from, so
       the two always travel together: `examples/built-page/` for this
       repository's example, or `built-page/` in your own workflows folder. */
    outDir: path.join(theWorkflows, BUILT_PAGE),
    emptyOutDir: true,
    /* Fold everything into the page except neuroglancer's background programs,
       which have to stay files of their own. */
    assetsInlineLimit: (file) => !THE_BACKGROUND_PROGRAMS.test(file),
    /* Everything in one folder, rather than the usual `assets/` beneath it.
       This looks like tidiness and is not: put back, the page draws nothing, in
       two different ways.

       Vite works out where the fetching program is *relative to the piece of
       JavaScript that starts it* — and that piece is then folded into
       `index.html`, one folder higher up. The address it was given no longer
       points anywhere. And the fetching program looks for the unpacking one
       beside itself, so the two must in any case share a folder. Both were met
       and measured; both are silent. */
    assetsDir: "",
    cssCodeSplit: false,
    reportCompressedSize: false,
    // One page's worth of JavaScript in one file is large by the usual measure,
    // and being told so on every build helps nobody.
    chunkSizeWarningLimit: 100_000_000,
    rollupOptions: { output: { codeSplitting: false } },
  },
  /* The drawing engine is only reached through a dynamic import — it is fetched
     when there is a run to watch and not before — so the development server does
     not find it while looking over the page at start-up. It would instead meet
     it the first time somebody opened the scan step, prepare it then, and reload
     the page to use it, which throws away whatever the operator was in the
     middle of. Naming the packages here has them made ready before the server
     starts answering. */
  optimizeDeps: {
    include: [
      "@vivjs/loaders",
      /* Neuroglancer is the one package that must *not* be made ready this way,
         because doing so rewrites the line where it starts its background
         program and the program then never starts. It is left out just below.
         What it needs, though, are these: a handful of older libraries it uses
         which are written in a style browsers cannot read directly. Left alone
         they stop the page with errors that name the library rather than
         neuroglancer — "require is not defined", "CodeMirror is not defined" —
         which is a long way to travel from the real cause. */
      "neuroglancer > codemirror",
      "neuroglancer > codemirror/addon/fold/brace-fold.js",
      "neuroglancer > codemirror/addon/fold/foldcode.js",
      "neuroglancer > codemirror/addon/fold/foldgutter.js",
      "neuroglancer > codemirror/addon/lint/lint.js",
      "neuroglancer > codemirror/mode/javascript/javascript.js",
      "neuroglancer > core-js/actual/symbol/dispose.js",
      "neuroglancer > core-js/actual/symbol/async-dispose.js",
      "neuroglancer > crc-32",
      "neuroglancer > gl-matrix",
      "neuroglancer > msgpackr",
      "neuroglancer > nifti-reader-js",
    ],
    exclude: ["neuroglancer"],
  },
  resolve: {
    alias: [WHERE_NEUROGLANCER_KEEPS_ITS_INSIDES, THE_VIEWERS_DRAWING, ...theWorkflowNames(theWorkflows)],
    /* A workflow outside this repository imports the page's npm packages too,
       and from where it sits there is no `node_modules` to find them in. These
       are taken from this repository's own copy, wherever the importing file
       is, so the page always holds one copy of each. */
    dedupe: ["@vivjs/loaders", "neuroglancer"],
  },
  server: {
    host: "127.0.0.1",
    port: 5174,
    /* While the page is being developed, Vite serves the files it needs straight
       off the disk, and refuses anything outside the folders named here. The
       background programs are named by where they really are, since
       `node_modules` may be a link to a folder elsewhere. */
    fs: { allow: [here, theWorkflows, realpathSync(WHERE_THE_WORKERS_LIVE), theViewersDrawing] },
    watch: {
      /* The browser tests leave photographs here. Vite reloads the page when a
         file in the project changes, which is exactly what you want while
         editing and exactly what you do not want in the middle of a test: the
         page would jump back to its first step and the run being watched would
         be lost. */
      /* Nor a run written under the page's tree: the watcher opened each
         store's files as they appeared, and on Windows the writer's rename
         into place was then denied -- one position in three lost, on the
         operator's PC, with the interface's own bridge writing beside the
         page. */
      ignored: ["**/test-results/**", "**/playwright-report/**", "**/mock-output/**"],
    },
  },
});

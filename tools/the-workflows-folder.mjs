/**
 * Which folder of workflows the page is built from, and the names a workflow
 * imports the interface by.
 *
 * The interface is a framework: it brings no workflow of its own. A page is
 * built from a folder that holds one or more workflows, each in a folder of its
 * own, and that folder can be anywhere on the computer -- in this repository,
 * or in a repository of your own such as ZMART Microscopy. It is named by the
 * environment variable `ZMART_INTERFACE_WORKFLOWS`:
 *
 *     ZMART_INTERFACE_WORKFLOWS=/path/to/my/workflows npm run build
 *
 * When it is not set, the page is built from this repository's own
 * `examples/` folder, which holds the example workflow the interface's tests
 * run on. The built page is written into the workflows folder, as
 * `built-page/`, so a page always sits beside the workflows it was built from.
 * The bridge finds it there by the same setting (see
 * `zmart_interface/framework/bridge/workflows.py`).
 *
 * A workflow outside this repository cannot reach the workflow API by a
 * relative path such as `../../zmart_interface/api/index.ts`, because the API
 * is not beside it. So every workflow imports it by a fixed name instead:
 *
 *     import type { Flow } from "zmart-interface/api";
 *
 * and the build, the unit tests and the type checker all map that name onto
 * `zmart_interface/api/index.ts`. The page's npm packages are found in this
 * repository's `node_modules`, wherever the workflow sits.
 *
 * Author: Thom de Hoog, Center for Microscopy and Image Analysis (ZMB),
 * University of Zurich (thom.dehoog@zmb.uzh.ch, thomdehoog@gmail.com).
 */

import fs from "node:fs";
import path from "node:path";

const here = path.resolve(import.meta.dirname, "..");

/** The environment variable that names the folder of workflows. */
export const SETTING = "ZMART_INTERFACE_WORKFLOWS";

/** This repository's own folder of example workflows, used when nothing else is named. */
export const THE_EXAMPLES = path.join(here, "examples");

/** The workflow API every workflow imports, by the name `zmart-interface/api`. */
export const THE_API = path.join(here, "zmart_interface", "api");

/** The name of the folder, inside a workflows folder, that the built page is written to. */
export const BUILT_PAGE = "built-page";

/** The name the page's code uses for the folder of workflows: `@zmart-workflows/<folder>/flow.ts`. */
export const WORKFLOWS_ALIAS = "@zmart-workflows";

/**
 * The folder of workflows to build from: the one `ZMART_INTERFACE_WORKFLOWS`
 * names, or this repository's `examples/`. A folder that is named but does not
 * exist stops the build with a sentence saying so, rather than building a page
 * with no workflow in it.
 */
export function theWorkflowsFolder(environment = process.env) {
  const named = (environment[SETTING] || "").trim();
  const folder = named ? path.resolve(named) : THE_EXAMPLES;
  if (!fs.existsSync(folder) || !fs.statSync(folder).isDirectory()) {
    throw new Error(
      named
        ? `${SETTING} names ${named}, which is not a folder; point it at the folder that holds your workflows`
        : `there is no examples/ folder at ${THE_EXAMPLES}, and ${SETTING} is not set; point it at the folder that holds your workflows`,
    );
  }
  return folder;
}

/**
 * The development server's address for the folder of workflows: a browser test
 * that loads a workflow's module inside the page asks for
 * `/@zmart-workflows/<workflow>/<file>`, and is handed that file from wherever
 * the folder is, so the same test runs on a workflow in this repository and on
 * one in a repository of its own.
 */
export function theWorkflowsAddress(folder) {
  return {
    name: "zmart:the-workflows-address",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use((request, _response, next) => {
        if (request.url?.startsWith(`/${WORKFLOWS_ALIAS}/`)) {
          const rest = request.url.slice(WORKFLOWS_ALIAS.length + 2);
          request.url = `/@fs/${folder.replaceAll("\\", "/").replace(/^\//, "")}/${rest}`;
        }
        next();
      });
    },
  };
}

/** The module the page reads its workflows from (`theWorkflowsList`). */
export const THE_WORKFLOWS_LIST = "zmart-interface/the-workflows-list";

/**
 * The workflows in the folder, as one module the page imports: every folder
 * in it with a `flow.js` or `flow.ts`, each imported by `@zmart-workflows/` and
 * listed under `<folder>/flow.ts`.
 *
 * The build tool's own folder scan, `import.meta.glob`, would list each flow
 * under its path from this repository, which is written into the page. A
 * folder of workflows in another repository would then build a different page
 * on every computer where the two checkouts sit differently, and the page that
 * repository commits could be checked on one layout only. Listed here, the page
 * holds the folder names and nothing of where they are.
 *
 * The list is read when the build, the development server or the unit tests
 * start; a workflow folder added later needs the development server restarted.
 */
export function theWorkflowsList(folder) {
  const resolved = `\0${THE_WORKFLOWS_LIST}`;
  return {
    name: "zmart:the-workflows-list",
    resolveId: (name) => (name === THE_WORKFLOWS_LIST ? resolved : undefined),
    load(id) {
      if (id !== resolved) return undefined;
      const flows = fs.readdirSync(folder, { withFileTypes: true })
        .filter((entry) => entry.isDirectory())
        .flatMap((entry) => ["flow.ts", "flow.js"]
          .filter((file) => fs.existsSync(path.join(folder, entry.name, file)))
          .map((file) => `${entry.name}/${file}`))
        .sort();
      const imports = flows.map((flow, number) => `import * as flow${number} from "${WORKFLOWS_ALIAS}/${flow}";`);
      const listed = flows.map((flow, number) => `  ${JSON.stringify(flow)}: flow${number},`);
      return [...imports, "export default {", ...listed, "};", ""].join("\n");
    },
  };
}

/**
 * The names a workflow's code is resolved by, for the build and the unit tests
 * alike: the folder of workflows, and the workflow API.
 */
export function theWorkflowNames(folder) {
  return [
    { find: /^@zmart-workflows\//, replacement: `${folder}/` },
    { find: /^zmart-interface\/api$/, replacement: path.join(THE_API, "index.ts") },
    /* A workflow's own tests may reach further into the framework than the
       workflow may (the import rules hold the workflow itself to the API);
       they do so by the same kind of fixed name, so they run from anywhere. */
    { find: /^zmart-interface\/framework\//, replacement: `${path.join(here, "zmart_interface", "framework")}/` },
  ];
}

/**
 * Let the workflows in an outside folder reach this repository's npm packages.
 *
 * The build and the unit tests resolve a workflow's imports themselves, so
 * they need nothing here. The browser tests are different: Playwright loads a
 * workflow's `.spec.ts` with Node, and Node looks for a package such as
 * `@playwright/test` only in a `node_modules` folder beside the file or above
 * it. A folder of workflows outside this repository has none, so this puts a
 * link called `node_modules` in it that leads to this repository's own (on
 * Windows a junction, which needs no administrator rights). Nothing is copied
 * or installed there; the folder only has to keep `node_modules` out of git,
 * as ZMART Microscopy does. A folder that already has a `node_modules` is left
 * alone, and so is this repository's own `examples/`.
 */
export function letTheWorkflowsReachThePackages(folder) {
  const link = path.join(folder, "node_modules");
  if (path.resolve(folder) === THE_EXAMPLES || fs.existsSync(link)) return;
  fs.symlinkSync(path.join(here, "node_modules"), link, "junction");
}

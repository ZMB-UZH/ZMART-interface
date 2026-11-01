import path from "node:path";
import { defineConfig } from "vitest/config";
import { theWorkflowNames, theWorkflowsFolder } from "./tools/the-workflows-folder.mjs";

/* Every test stands beside what it tests — a part's in the part, a step's in
   the step — so there is no tests folder to point at. What separates the two
   kinds is what they need: a `.test` file runs on nothing but Node, and a
   `.spec` file needs a browser and a dev server, which is Playwright's business
   and would only fail confusingly here.

   The example workflow lives in `examples/`, outside the package, and its
   tests run here too. A workflow imports the API as `zmart-interface/api` and
   the page finds the workflows as `@zmart-workflows/...`; the same names are
   resolved here as in the build (`tools/the-workflows-folder.mjs`). */
const theWorkflows = theWorkflowsFolder();

export default defineConfig({
  resolve: { alias: theWorkflowNames(theWorkflows) },
  /* The folder of workflows may sit outside this repository; its tests are
     found there and run here, with the same names resolved. */
  server: { fs: { allow: [import.meta.dirname, theWorkflows] } },
  test: {
    dir: import.meta.dirname,
    include: [
      "zmart_interface/**/*.test.{js,ts}",
      "tools/**/*.test.mjs",
      `${path.relative(import.meta.dirname, theWorkflows).replaceAll("\\", "/") || "."}/**/*.test.{js,ts}`,
    ],
    exclude: ["**/node_modules/**", "**/built-page/**"],
    environment: "node",
  },
});

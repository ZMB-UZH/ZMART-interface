/**
 * Which part of the page may import which, as dependency-cruiser checks it.
 *
 * The three layers have a direction: a workflow uses the parts and the
 * framework; the parts use the framework's base pieces; the framework uses no
 * workflow. Workflows share nothing with each other. Nothing goes round in a
 * circle. `npm run check:imports` says, file and line, where an import breaks
 * one of these.
 */
module.exports = {
  forbidden: [
    {
      name: "no-circle",
      comment: "Two modules that import each other, however far round, cannot be understood or moved one at a time.",
      severity: "warn",
      from: {},
      to: { circular: true },
    },
    {
      name: "framework-knows-no-workflow",
      comment: "The framework runs any workflow and knows none.",
      severity: "error",
      from: { path: "^zmart_interface/framework/" },
      to: { path: "^examples/" },
    },
    {
      name: "parts-know-no-workflow",
      comment: "A part is a general piece any workflow may use; nothing in it belongs to one workflow.",
      severity: "error",
      from: { path: "^zmart_interface/parts/" },
      to: { path: "^examples/" },
    },
    {
      name: "workflows-share-nothing",
      comment: "A piece two workflows need is general, and moves into parts/.",
      severity: "error",
      from: { path: "^examples/([^/]+)/" },
      to: { path: "^examples/", pathNot: "^examples/$1/" },
    },
    {
      name: "a-workflow-uses-only-the-api",
      comment: "A workflow imports its own files, the workflow API (zmart-interface/api, which is zmart_interface/api/) and npm packages; anything else of the interface could change under it. Its tests may reach further.",
      severity: "error",
      from: { path: "^examples/([^/]+)/", pathNot: "\\.(test|spec)\\.[jt]s$" },
      to: { path: "^(zmart_interface|examples)/", pathNot: ["^examples/$1/", "^zmart_interface/api/"] },
    },
    {
      name: "the-fixture-uses-only-the-api",
      comment: "The framework's own fixture is the smallest workflow, and is held to the same edge.",
      severity: "error",
      from: { path: "^zmart_interface/framework/fixtures/([^/]+)/", pathNot: "\\.(test|spec)\\.[jt]s$" },
      to: { path: "^zmart_interface/", pathNot: ["^zmart_interface/framework/fixtures/$1/", "^zmart_interface/api/"] },
    },
    {
      name: "a-step-imports-no-step",
      comment: "A step is its own folder. What two steps use sits below them, in the workflow's shared/; only the workflow's root composes the steps.",
      severity: "error",
      from: { path: "^examples/[^/]+/steps/([^/]+)/" },
      to: { path: "^examples/[^/]+/steps/", pathNot: "^examples/[^/]+/steps/$1/" },
    },
    {
      name: "below-the-steps-imports-no-step",
      comment: "What several steps use sits below them -- shared code, the canvas, the microscope seam, the backend, the test helpers -- and imports no step; only the workflow's root composes the steps.",
      severity: "error",
      from: { path: "^examples/[^/]+/(shared|canvas|microscope|backend|testing)/" },
      to: { path: "^examples/[^/]+/steps/" },
    },
    {
      name: "resolvable",
      comment: "An import that leads nowhere fails in the build; say so before it does. The viewer's drawing files are found by the build itself, in the installed viewer (tools/the-installed-viewer.mjs); the checker reads them by the committed copy of their declarations.",
      severity: "error",
      from: {},
      to: { couldNotResolve: true, pathNot: "^zmart-viewer/drawing/" },
    },
  ],
  options: {
    /* The copy of the viewer's declarations is the viewer's, read as it is:
       what it imports beside itself (its stylesheet) is in the viewer. */
    doNotFollow: { path: ["node_modules", "/canvas/engines/zmart-viewer-drawing/"] },
    exclude: { path: "^examples/built-page/" },
    tsConfig: { fileName: "tsconfig.json" },
    enhancedResolveOptions: {
      exportsFields: ["exports"],
      conditionNames: ["import", "require", "node", "default"],
      extensions: [".js", ".mjs", ".ts", ".d.ts"],
    },
    reporterOptions: {
      text: { highlightFocused: true },
    },
  },
};

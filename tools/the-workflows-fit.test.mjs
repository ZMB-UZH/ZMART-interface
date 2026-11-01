/* The build's check that every workflow was written for this workflow API:
   tried on folders made up here, and on the interface's own. */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, it, expect } from "vitest";
import { theApiVersion, workflowsThatDoNotFit } from "./the-workflows-fit.mjs";

const here = import.meta.dirname;

function aWorkflowsFolder(workflows) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "workflows-"));
  for (const [name, { flow = true, declared }] of Object.entries(workflows)) {
    fs.mkdirSync(path.join(root, name));
    if (flow) fs.writeFileSync(path.join(root, name, "flow.js"), "export const steps = [];\n");
    if (declared !== undefined) fs.writeFileSync(path.join(root, name, "workflow.json"), declared);
  }
  return root;
}

describe("whether the workflows fit the API", () => {
  it("lets through a workflow whose range holds the API's version", () => {
    const root = aWorkflowsFolder({ fits: { declared: JSON.stringify({ api: "^0.1.0" }) } });
    expect(workflowsThatDoNotFit("0.1.3", root)).toEqual([]);
  });

  it("names a workflow written for another API, and says which", () => {
    const root = aWorkflowsFolder({ old: { declared: JSON.stringify({ api: "^0.1.0" }) } });
    expect(workflowsThatDoNotFit("0.2.0", root)).toEqual([
      "the workflow old works with workflow API ^0.1.0, and this interface's is 0.2.0",
    ]);
  });

  it("names a workflow that says nothing, or nothing readable", () => {
    const root = aWorkflowsFolder({
      silent: {},
      empty: { declared: JSON.stringify({ name: "empty" }) },
      broken: { declared: "{ not json" },
    });
    const said = workflowsThatDoNotFit("0.1.0", root);
    expect(said).toHaveLength(3);
    expect(said.some((one) => one.startsWith("the workflow silent has no workflow.json"))).toBe(true);
    expect(said).toContain("the workflow empty's workflow.json names no \"api\" range");
    expect(said.some((one) => one.startsWith("the workflow broken's workflow.json cannot be read"))).toBe(true);
  });

  it("passes over a folder that is not a workflow", () => {
    const root = aWorkflowsFolder({ notes: { flow: false } });
    expect(workflowsThatDoNotFit("0.1.0", root)).toEqual([]);
  });

  it("finds the example workflows, and the framework's own fixture, fitting", () => {
    const api = path.join(here, "..", "zmart_interface", "api");
    const version = theApiVersion(api);
    expect(workflowsThatDoNotFit(version, path.join(here, "..", "examples"))).toEqual([]);
    expect(workflowsThatDoNotFit(version, path.join(here, "..", "zmart_interface", "framework", "fixtures"))).toEqual([]);
  });
});

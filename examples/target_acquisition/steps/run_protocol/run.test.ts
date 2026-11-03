import { describe, it, expect } from "vitest";
import { protocolBlockers, runProtocol } from "./run.ts";
import type { TaPage } from "../../types.ts";

describe("the protocol run", () => {
  it("clears the canvas of earlier runs before its first step", async () => {
    const said: string[] = [];
    const run = { running: false, walk: { running: false }, focus: { applied: true }, done: new Set(),
      stale: new Set(), ran: new Set(), notes: {}, cells: new Map(), gated: new Set(), acquired: [] };
    const page = {
      run, step: () => ({ title: "a step" }), indexOfStep: () => 0, focusPanelsFor() {}, renderAll() {},
      remountChannel() {}, readiness: () => null,
      runStep: async () => { said.push("step"); return { outcome: "finished" }; },
      backend: { protocolBegan: async () => { said.push("began"); }, saveProtocol: async () => ({}) },
    } as unknown as TaPage;
    await runProtocol(page);
    expect(said[0]).toBe("began");
    expect(said.slice(1)).not.toContain("began");
  });
});

describe("what holds the protocol back", () => {
  it("a gate on computed axes", () => {
    const run = { focus: { applied: true }, plan: [], targetFocusOn: false,
      gates: [{ fx: "umap_1", fy: "umap_2", vertices: [[0, 0], [1, 0], [1, 1]] }] };
    const page = { run, step: () => ({}), indexOfStep: () => 0 } as unknown as TaPage;
    expect(protocolBlockers(page)).toContain("Discover Targets: a gate on umap_1 × umap_2 cannot go into "
      + "a protocol: PCA and UMAP are fitted anew on every run; gate on measured features instead");
  });
});

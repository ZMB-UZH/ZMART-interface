/* The rules about steps, which every workflow is walked by: how steps are
 * numbered, which one may be reached, what goes stale when one is edited, and
 * which panels each stands on. They are tried on steps made up here and on the
 * framework's own fixture, `framework/fixtures/three_steps/`; each workflow
 * tests its own steps in its own folder.
 */

import { describe, it, expect } from "vitest";
import {
  numbered, firstIncomplete, isReachable, panelsFor, editedAt, staleSteps, blockedBecause,
} from "./steps.ts";
import { assembleWorkflows } from "./finding-workflows.ts";

const { WORKFLOWS } = assembleWorkflows(
  import.meta.glob("@zmart-workflows/*/flow.{js,ts}", { eager: true }),
);

describe("numbering is derived, so reordering costs nothing", () => {
  it("numbers by position", () => {
    expect(numbered([{ id: "a" }, { id: "b" }, { id: "c" }]).map((s) => s.n))
      .toEqual(["1", "2", "3"]);
  });

  it("lets sub-steps opt out and does not reuse their number", () => {
    const out = numbered([{ id: "a" }, { id: "b", n: "2a" }, { id: "c", n: "2b" }, { id: "d" }]);
    expect(out.map((s) => s.n)).toEqual(["1", "2a", "2b", "3"]);
  });

});

/* A step that was settled once and then had something before it changed is
   done but stale: orange on the rail, asking to be confirmed or run again.
   Editing a step stales every done step after it and leaves the edited step
   green — the operator just settled it. */
describe("editing a step stales the ones after it", () => {
  const steps = ["a", "b", "c", "d", "e"].map((id) => ({ id }));
  const all = new Set(steps.map((s) => s.id));

  it("stales every done step after the edited one, not the edited one", () => {
    expect([...editedAt(steps, all, new Set(), "b")]).toEqual(["c", "d", "e"]);
  });

  it("leaves steps that are not done alone", () => {
    expect([...editedAt(steps, new Set(["a", "b", "c"]), new Set(), "a")]).toEqual(["b", "c"]);
  });

  it("keeps what was already stale", () => {
    expect([...editedAt(steps, all, new Set(["e"]), "c")].sort()).toEqual(["d", "e"]);
  });

  it("editing the edited step again unstales it", () => {
    const stale = editedAt(steps, all, new Set(["b", "c"]), "b");
    expect(stale.has("b")).toBe(false);
    expect(stale.has("c")).toBe(true);
  });

  it("names the stale steps in rail order", () => {
    expect(staleSteps(steps, all, new Set(["e", "b", "a"])).map((s) => s.id)).toEqual(["a", "b", "e"]);
  });

  it("a step that is not done is never stale, whatever the set says", () => {
    expect(staleSteps(steps, new Set(["a"]), new Set(["b"]))).toEqual([]);
  });
});

describe("ordering", () => {
  const steps = ["a", "b", "c", "d"].map((id) => ({ id }));

  it("only the next unfinished step is reachable", () => {
    const done = new Set(["a"]);
    expect(isReachable(steps, done, 0)).toBe(true);
    expect(isReachable(steps, done, 1)).toBe(true);
    expect(isReachable(steps, done, 2)).toBe(false);
  });

  it("finds the first gap, not the last completed step", () => {
    expect(firstIncomplete(steps, new Set(["a", "b"]))).toBe(2);
    expect(firstIncomplete(steps, new Set())).toBe(0);
  });

  /* A step that only shows the operator something produces nothing, so there is
     nothing for the steps after it to wait for and it says so. Without this a
     workflow made of such steps would be stuck on its first one for ever: the
     operator has no way to finish a step there is nothing to finish. */
  it("a step that holds nothing up lets the run walk straight past it", () => {
    const shown = [
      { id: "look", nothingWaitsOnThis: true },
      { id: "look-again", nothingWaitsOnThis: true },
      { id: "act" },
      { id: "after" },
    ];
    expect(firstIncomplete(shown, new Set())).toBe(2);
    expect(isReachable(shown, new Set(), 0)).toBe(true);
    expect(isReachable(shown, new Set(), 1)).toBe(true);
    expect(isReachable(shown, new Set(), 2)).toBe(true);
    // and it does not open the gate for what comes after the step that does act
    expect(isReachable(shown, new Set(), 3)).toBe(false);
  });
});

describe("what a step still waits for", () => {
  it("asks the step's own rule, with the run and the page", () => {
    const page = { steps: () => [] };
    const run = { done: new Set() };
    let asked: unknown[] = [];
    const step = { id: "x", ready: (r: unknown, p: unknown) => { asked = [r, p]; return "not yet"; } };
    expect(blockedBecause(step, run, page)).toBe("not yet");
    expect(asked[0]).toBe(run);
    expect(asked[1]).toBe(page);
  });

  it("is nothing for a step without a rule", () => {
    expect(blockedBecause({ id: "x" }, {}, {})).toBe(null);
  });
});

describe("panels follow the step", () => {
  /* Which panels stay once asked for is the workflow's own declaration: the
     rule is handed the keys and knows nothing about what any of them draws. */
  it("a workflow that declares no panel that stays gives each step its own", () => {
    /* The point of the rule: nothing in it is about a canvas. A run whose
       steps each bring their own panel — a report, a set of forms — keeps
       none of them past the step that asked. */
    const steps = [
      { id: "one", panels: ["form"] },
      { id: "two", panels: [] },
      { id: "three", panels: ["report"] },
    ];
    expect(steps.map((_, i) => panelsFor(steps, i))).toEqual([["form"], [], ["report"]]);
  });

  it("keeps a staying panel from the step that first asks, and not before", () => {
    const steps = [
      { id: "one", panels: [] },
      { id: "two", panels: ["map"] },
      { id: "three", panels: ["notes"] },
    ];
    expect(steps.map((_, i) => panelsFor(steps, i, ["map"])))
      .toEqual([[], ["map"], ["map", "notes"]]);
  });
});

/* A workflow's front door is `flow.js` or, once it is converted, `flow.ts`;
   the folder is found either way. */
describe("finding a workflow's folder", () => {
  it("finds a flow written in JavaScript or in TypeScript", () => {
    const { WORKFLOWS } = assembleWorkflows({
      "workflows/in_js/flow.js": { blurb: "", steps: [{ id: "a", title: "A" }] },
      "workflows/in_ts/flow.ts": { blurb: "", steps: [{ id: "b", title: "B" }] },
      "workflows/neither/flow.css": { blurb: "", steps: [{ id: "c", title: "C" }] },
    });
    expect(Object.keys(WORKFLOWS)).toEqual(["in_js", "in_ts"]);
  });
});

/* The framework runs a workflow that knows nothing about a microscope. The
   fixture under `framework/fixtures/three_steps/` is assembled the way the
   page assembles the folders under `workflows/`, and comes out as a
   workflow the page could offer: numbered steps, its own panel, its own
   declarations carried through. It is not under `workflows/`, so the
   chooser never offers it. */
describe("a workflow that knows nothing about a microscope", () => {
  const { WORKFLOWS: FIXTURES, DEFAULT_WORKFLOW } = assembleWorkflows(
    import.meta.glob("../fixtures/*/flow.{js,ts}", { eager: true }),
  );
  const three = FIXTURES.three_steps;

  it("is assembled from its folder like any other, and named from it", () => {
    /* Beside it, its copy frozen at API 0.2.0 (`window/the-frozen-fixture.test.ts`). */
    expect(Object.keys(FIXTURES)).toEqual(["three_steps", "three_steps_at_0_2_0"]);
    expect(DEFAULT_WORKFLOW).toBe("three_steps");
    expect(three.name).toBe("Three steps");
    expect(three.blurb).toBeTruthy();
  });

  it("has its steps numbered in order, the one that says its own number included", () => {
    expect(three.steps.map((s) => [s.n, s.id])).toEqual(
      [["1", "begin"], ["2", "count"], ["3", "finish"], ["4", "look"], ["5", "walk"]]);
  });

  it("brings its own panel, and every step stands on it", () => {
    expect(three.panels.map((p) => p.key)).toEqual(["card"]);
    const staying = three.panels.filter((p) => p.stays).map((p) => p.key);
    expect(three.steps.map((_, i) => panelsFor(three.steps, i, staying)))
      .toEqual(three.steps.map(() => ["card"]));
  });

  it("carries every declaration the page reads", () => {
    expect(typeof three.freshState).toBe("function");
    expect(three.keptAcrossSessions).toEqual([]);
    expect(typeof three.forTests).toBe("function");
    expect(typeof three.install).toBe("function");
    expect(typeof three.backendFor).toBe("function");
  });

  it("is the shape the rail expects: begin settles by standing, count has a brake, finish a press", () => {
    const [begin, count, finish] = three.steps;
    expect(typeof begin.settledByStanding).toBe("function");
    expect(begin.btn).toBeUndefined();
    expect(count.btn).toBe("Count");
    expect(typeof count.run).toBe("function");
    expect(typeof count.brake).toBe("function");
    expect(finish.btn).toBe("Finish");
    expect(finish.walks).toBeUndefined();
    /* Walked in order: nothing in it may be skipped. */
    expect(firstIncomplete(three.steps, new Set())).toBe(0);
    expect(firstIncomplete(three.steps, new Set(["begin"]))).toBe(1);
    expect(isReachable(three.steps, new Set(["begin"]), 2)).toBe(false);
  });

  it("names the step that walks the others", () => {
    expect(three.steps.filter((s) => s.walks).map((s) => s.id)).toEqual(["walk"]);
  });
});

describe("every workflow in the chooser", () => {
  /* A name has to fit the rail, which is a fixed column, and no workflow name
     may be longer than the longest one this page has always carried. That is
     not fussiness about tidiness: the chooser used to take whatever width its
     longest name wanted and push the Restart button beside it off the rail
     altogether, where it could not be pressed. The layout no longer allows
     that, and this keeps the names readable rather than trailing off. */
  it("names every workflow briefly enough for the rail to show it", () => {
    for (const w of Object.values(WORKFLOWS)) {
      expect(w.name.length, `"${w.name}" is too long for the chooser`)
        .toBeLessThanOrEqual(28);
    }
  });

});


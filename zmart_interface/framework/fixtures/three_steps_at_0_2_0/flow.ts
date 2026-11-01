/**
 * Three steps, as it stood when the workflow API was 0.2.0 -- frozen.
 *
 * A copy of `../three_steps/flow.ts` that is never edited. It uses every field
 * and hook the API offered at 0.2.0, so while it still type-checks against the
 * API and walks (`window/the-frozen-fixture.test.ts`), every workflow written
 * for 0.2.0 still fits. When it stops fitting, the API has broken its word:
 * that is a new breaking version, and a new frozen copy beside this one.
 *
 * What follows is the fixture's own description, as it was.
 *
 * This is the framework's own acceptance fixture: the smallest workflow that
 * uses every field and every hook the workflow API offers, with no Python
 * behind it besides one route and no canvas. It imports nothing but the
 * API. It stands under `framework/fixtures/` rather than under `workflows/`,
 * so the operator's chooser never offers it; the unit tests assemble it the
 * way the page assembles the real workflows. It is also where to start a
 * new workflow from.
 *
 * What it does is deliberately dull. Begin is settled by standing on it;
 * Count to three runs for a moment, can be interrupted, can count one more
 * again, and says what it counted to; Finish runs at once and writes a note;
 * Look back can be stood on in any order and holds nothing up; Walk them
 * all walks Count and Finish in turn. Its one panel is a card with a
 * heading and a line of text that follows the run.
 *
 * Author: Thom de Hoog, Center for Microscopy and Image Analysis (ZMB),
 * University of Zurich (thom.dehoog@zmb.uzh.ch, thomdehoog@gmail.com).
 */

import { sideGroup, staleSteps } from "zmart-interface/api";
import type { Flow, Hooks, Page, Panel, Step, WorkflowTypes } from "zmart-interface/api";

/** What a run of this workflow holds beside the framework's keys. */
interface CountState {
  counted: number;
  stopAsked: boolean;
}

/** What its backend is: a pretend clock it waits on. */
interface CountBackend {
  wait(ms: number): Promise<void>;
}

/** What it lends its page. */
interface CountLends {
  sayTheLine(): void;
}

/** What its steps put on screen. */
interface CountShown {
  extra?: HTMLElement;
}

interface Three extends WorkflowTypes {
  state: CountState;
  backend: CountBackend;
  lends: CountLends;
  shown: CountShown;
  step: { hint?: string };
}

export const name = "Three steps";

export const blurb = "Three steps that know nothing about a microscope: begin, count to three, finish.";

/* The card: this workflow's one panel. The framework builds the box and
   this fills it -- a heading, a line that follows the run, a column for a
   step's controls, and the foot the framework puts a step's press in. */
const cardPanel: Panel = {
  key: "card",
  label: "Card",
  stays: true,
  build(host) {
    const box = document.createElement("div");
    box.className = "three-steps-card";
    const made = sideGroup("Three steps");
    const line = document.createElement("p");
    line.id = "three-steps-line";
    line.textContent = "Nothing counted yet.";
    made.body.append(line);
    box.append(made.group);
    const channel = document.createElement("div");
    channel.className = "three-steps-channel";
    const foot = document.createElement("div");
    foot.className = "panel-foot";
    host.append(box, channel, foot);
    return { foot, channel, line, shown: () => undefined };
  },
};

export const panels: Panel[] = [cardPanel];

const begin: Step<Three> = {
  id: "begin",
  title: "Begin",
  panels: ["card"],
  hint: "standing here begins the run",
  arrived(page) {
    page.sayTheLine();
  },
  settledByStanding(page) {
    page.run.done.add("begin");
    page.run.notes.begin = "begun";
  },
};

const countToThree: Step<Three> = {
  id: "count",
  title: "Count to three",
  btn: "Count",
  again: "Count again",
  mode: "counting",
  panels: ["card"],
  ms: 0,
  async run(page, step, options) {
    const state = page.run;
    const upTo = typeof options.upTo === "number" ? options.upTo : 3;
    state.counted = 0;
    state.stopAsked = false;
    for (let next = 1; next <= upTo; next += 1) {
      await page.backend.wait(400);
      if (state.stopAsked) return { stopped: true, note: `stopped at ${state.counted}` };
      state.counted = next;
      page.renderAll();
    }
    return undefined;
  },
  finished(page) {
    page.run.notes.count = `counted to ${page.run.counted}`;
  },
  brake(page) {
    page.run.stopAsked = true;
  },
  rerunCurrent: (page) => (page.run.counted ? () => ({ upTo: 1 }) : null),
  beside: (run, { done }) => (done ? `counted to ${run.counted}` : null),
  afterThePress(host) {
    const said = document.createElement("span");
    said.className = "three-steps-after";
    host.append(said);
  },
  ready: (run) => (run.done.has("begin") ? null : "begin first"),
  channel: {
    id: "count",
    label: "Count",
    mount(host, page, { locked }) {
      const note = document.createElement("p");
      note.textContent = locked ? "counting…" : "Count to three, or one more again.";
      const slot = document.createElement("div");
      host.append(note, slot);
      page.shown.extra = note;
      return {
        actionSlot: slot,
        destroy() {
          page.shown.extra = undefined;
        },
      };
    },
  },
};

const finish: Step<Three> = {
  id: "finish",
  title: "Finish",
  btn: "Finish",
  panels: ["card"],
  ms: 0,
  noHint: true,
  finished(page) {
    page.run.notes.finish = "finished";
  },
};

const lookBack: Step<Three> = {
  id: "look",
  title: "Look back",
  n: "4",
  panels: ["card"],
  ownButton: true,
  nothingWaitsOnThis: true,
};

const walkThemAll: Step<Three> = {
  id: "walk",
  title: "Walk them all",
  btn: "Walk",
  panels: ["card"],
  ready: (run, page) => {
    const stale = staleSteps(page.steps(), run.done, run.stale);
    return stale.length ? `confirm ${stale.map((s) => s.title).join(", ")} first` : null;
  },
  walks: {
    async press(page) {
      page.run.walk = { running: true, interrupted: false };
      for (const id of ["count", "finish"]) {
        if (page.run.walk.interrupted) break;
        const { outcome } = await page.runStep(page.indexOfStep(id));
        if (outcome !== "finished") break;
      }
      page.run.walk = { running: false, interrupted: false };
      page.renderAll();
    },
    whileWalking: "walking the steps",
  },
};

export const steps: Step<Three>[] = [begin, countToThree, finish, lookBack, walkThemAll];

/** A pretend clock: time passing, as the count waits for it. */
export const backendFor = (): CountBackend => ({
  wait: (ms) => new Promise((done) => setTimeout(done, ms)),
});

export const freshState = (): CountState => ({ counted: 0, stopAsked: false });

/** Nothing of it outlives a change of workflow. */
export const keptAcrossSessions: string[] = [];

/** What a browser test may read of it. */
export const forTests = (state: CountState) => ({ counted: state.counted });

/** The card's line follows the run; every hook says it heard, on the card. */
export function install(page: Page<Three>) {
  const sayTheLine = () => {
    const line = page.panels.card?.line as HTMLElement | undefined;
    if (!line) return;
    const state = page.run;
    line.textContent = state.done.has("finish") ? "Finished."
      : state.running === "count" ? `Counting: ${state.counted} so far.`
        : state.counted ? `Counted to ${state.counted}.` : "Nothing counted yet.";
  };
  const hooks: Hooks<Three> = {
    onRender: sayTheLine,
    onPanelShown: () => sayTheLine(),
    onReset: sayTheLine,
    onLeave: () => undefined,
    onChannelMounted: () => sayTheLine(),
  };
  return { lends: { sayTheLine }, hooks };
}

/** Not the workflow a fresh page opens on: it is the framework's fixture. */
export const opensFirst = false;

/* The whole of it, held to the API's own shape: a field misspelt or of the
   wrong type is a type error here. */
({
  name, blurb, panels, steps, opensFirst, backendFor, freshState, keptAcrossSessions, forTests, install,
}) satisfies Flow<Three>;

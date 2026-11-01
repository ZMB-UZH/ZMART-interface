/**
 * The operator page, put together.
 *
 * This file starts the page and nothing else: it reads which workflow to
 * open on, hands the workflows the build found to the composition
 * (`pages.ts`), which builds the frame and each workflow's page over it, and
 * opens the page. Nothing here names a workflow, a backend or a panel: the
 * page would compose the same way for a workflow about e-learning or about
 * image analysis.
 *
 * What a workflow's page carries -- the run document, its steps and panels,
 * its backend, the boxes its steps show, what it lends and its hooks -- is
 * written out in `pages.ts`, and what a workflow may rely on of it in
 * `workflows/README.md`.
 */

import "./style.css";
import { composeThePages } from "./pages.ts";
import { exposeTheRunForTests } from "./run-state.ts";
import { DEFAULT_WORKFLOW, WORKFLOWS } from "./the-workflows.ts";

/* Which workflow to open on — `?workflow=target_acquisition`.
 *
 * For pointing this page at a run and looking at it, which is what somebody
 * with an acquisition in their hand wants. A name that is not a workflow is
 * ignored rather than refused: the page is still perfectly usable on its
 * ordinary workflow, and an address that opens something slightly
 * unexpected is a smaller failure than one that opens nothing. There is no
 * `?step=`: a workflow whose first step is not where you want to start is a
 * workflow that has its steps in the wrong order.
 */
const search = new URLSearchParams(location.search);
const asked = search.get("workflow");
const opensOn = asked && WORKFLOWS[asked] ? asked : DEFAULT_WORKFLOW;
if (!opensOn) throw new Error("the page was built with no workflow in its folder of workflows (ZMART_INTERFACE_WORKFLOWS)");

const pages = composeThePages({ WORKFLOWS, opensOn, search });

/* Left where a test can reach it: the framework's fields, and whatever the
   workflow open now exposes of its own. */
exposeTheRunForTests(pages.run, () => WORKFLOWS[pages.run.wf]);

pages.open();

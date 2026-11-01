/**
 * The workflows this page offers: every folder in the folder of workflows
 * the page is built from (`@zmart-workflows`, which the build maps onto the
 * folder `ZMART_INTERFACE_WORKFLOWS` names, or onto `examples/`; see
 * `tools/the-workflows-folder.mjs`) with a
 * `flow.js` or `flow.ts` inside it, listed by the build (`theWorkflowsList`) and assembled by
 * the framework. The unit tests read the same folders, so a workflow the tests
 * can see is a workflow the operator can choose. The list used to be written
 * out by hand — twice, at one point — and the copies drifted apart in silence,
 * which is why it is now read off the disk instead.
 *
 * A module of its own because the build puts the list's imports at the
 * top of the module that holds it: here, they come after `main.ts` has
 * imported the frame's stylesheet, so each workflow's stylesheet follows it.
 */

import { assembleWorkflows } from "../rules/finding-workflows.ts";
import flowFiles from "zmart-interface/the-workflows-list";

export const { WORKFLOWS, DEFAULT_WORKFLOW } = assembleWorkflows(flowFiles);

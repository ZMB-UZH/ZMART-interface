/* The list of workflows the build hands the page (`theWorkflowsList` in
   `tools/the-workflows-folder.mjs`): each flow module under `<folder>/flow.ts`. */
declare module "zmart-interface/the-workflows-list" {
  const flowFiles: Record<string, unknown>;
  export default flowFiles;
}

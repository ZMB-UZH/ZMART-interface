/* The page's own code reads no test hook.
 *
 * A `window.__name` is a hook: the module that owns a thing leaves it there
 * for the browser tests to look in. It is not a way for one part of the page
 * to reach another -- that is a side door, and a tie nothing else can see:
 * no import says it is there, so moving or renaming the owner breaks the
 * reader without a word from the type checker or the import rules.
 * `docs/principles.md` says so; this test holds it.
 *
 * It reads every page file under `zmart_interface/` and the example workflows
 * in `examples/` (not the tests, which are
 * what the hooks are for, and not the build), finds which module sets each
 * hook, and refuses any other module that names it. Comments are left out:
 * a comment may say where a test looks. */

import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const PACKAGE = join(dirname(fileURLToPath(import.meta.url)), "..");
const THE_EXAMPLES = join(PACKAGE, "..", "examples");

const pageFiles = (folder: string): string[] => readdirSync(folder, { withFileTypes: true }).flatMap((entry) => {
  const at = join(folder, entry.name);
  if (entry.isDirectory()) return ["node_modules", "build", "built-page", "__pycache__"].includes(entry.name) ? [] : pageFiles(at);
  return /\.ts$/.test(entry.name) && !/\.(test|spec)\.ts$/.test(entry.name) ? [at] : [];
});

/** The code of a file, its comments taken out. */
const codeOf = (file: string) => readFileSync(file, "utf8")
  .replace(/\/\*[\s\S]*?\*\//g, "")
  .replace(/(^|[^:"'`])\/\/.*$/gm, "$1");

const name = (file: string) => relative(PACKAGE, file).replaceAll("\\", "/");

const HOOK = /window\.(__[A-Za-z]+)/g;
const SET = /window\.(__[A-Za-z]+)\s*=(?!=)/g;

describe("the page's own code reads no test hook", () => {
  const files = [...pageFiles(PACKAGE), ...pageFiles(THE_EXAMPLES)].map((file) => ({ file, code: codeOf(file) }));
  const owners = new Map<string, Set<string>>();
  for (const { file, code } of files) {
    for (const [, hook] of code.matchAll(SET)) {
      if (!owners.has(hook)) owners.set(hook, new Set());
      owners.get(hook)!.add(name(file));
    }
  }

  it("has hooks to look at", () => {
    expect(owners.size).toBeGreaterThan(3);
  });

  for (const { file, code } of files) {
    const named = new Set([...code.matchAll(HOOK)].map(([, hook]) => hook));
    if (!named.size) continue;
    it(`${name(file)} names only the hooks it sets`, () => {
      const others = [...named].filter((hook) => !owners.get(hook)?.has(name(file)));
      expect(others, `${name(file)} reaches into another module's hook`).toEqual([]);
    });
  }
});

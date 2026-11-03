/**
 * Where the installed ZMART viewer keeps the drawing rules this page shares.
 *
 * This page and the viewer's own window draw with the same neuroglancer, and
 * they must draw the same way: the same primitives that steer it (making it,
 * keeping its layers in step, feeding and refreshing stores, its axes and
 * camera), the same little shader programs that turn a stored value into a
 * colour, and the same edits to neuroglancer that let a picture keep its
 * transparency and grow while it is on screen. The viewer owns all of these,
 * in its package's `drawing` folder, and this page takes them from there
 * rather than keeping copies of its own. Copies kept in line by hand drifted;
 * one owner cannot.
 *
 * So the viewer has to be installed in the Python that builds the page, and
 * it has to be the release `pyproject.toml` pins: another viewer builds
 * another page. `PYTHON=` names that Python when it is not the one on the path.
 */

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

/** The viewer release `pyproject.toml` pins, as `0.5.0rc10`. */
function thePinnedViewer() {
  const project = readFileSync(join(import.meta.dirname, "..", "pyproject.toml"), "utf8");
  const pinned = project.match(/"zmart-viewer @ git\+https:\/\/github\.com\/(?:ZMB-UZH|thomdehoog)\/ZMART-viewer@v([^"]+)"/);
  if (!pinned) throw new Error("pyproject.toml does not pin zmart-viewer to a release tag");
  return pinned[1];
}

/** The files this page reads from the viewer, all in its `drawing` folder. */
export const THE_SHARED_DRAWING_FILES = [
  "programs.js",
  "embedding.js",
  "neuroglancer-growth.mjs",
  "neuroglancer-patches.mjs",
  "primitives/viewer.ts",
  "primitives/sync.ts",
  "primitives/feeding.ts",
  "primitives/description.ts",
  "primitives/revisions.ts",
  "primitives/axes.ts",
  "primitives/camera.ts",
  "primitives/chrome.css",
];

/**
 * The installed viewer's `drawing` folder, checked to hold what this page needs.
 *
 * @throws when the viewer is not installed in that Python, is not the pinned
 *   release, or does not offer every shared file — saying which, and what to
 *   install.
 */
export function theViewersDrawingFolder() {
  const [version, folder] = execFileSync(process.env.PYTHON || "python", ["-c",
    "from pathlib import Path; import zmart_viewer; " +
    "print(zmart_viewer.__version__); print(Path(zmart_viewer.__file__).parent / 'drawing')"],
    { encoding: "utf8", windowsHide: true }).trim().split(/\r?\n/);
  const pinned = thePinnedViewer();
  if (version !== pinned) {
    throw new Error(
      `the installed ZMART viewer is ${version}, but this page is built with ${pinned}. ` +
        `Install zmart-viewer v${pinned} in the Python that builds this page ` +
        "(`pip install -e .` does), or name that Python with PYTHON=.",
    );
  }
  const missing = THE_SHARED_DRAWING_FILES.filter(name => !existsSync(join(folder, name)));
  if (missing.length) {
    throw new Error(
      `the installed ZMART viewer has no ${missing.join(", ")} in ${folder}. ` +
        `Install zmart-viewer v${pinned} in the Python that builds this page, ` +
        "or name that Python with PYTHON=.",
    );
  }
  return folder;
}

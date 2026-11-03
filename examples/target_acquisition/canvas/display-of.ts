/**
 * The picture's display settings, as a request for a copy drawn with them.
 *
 * The Neuroglancer picture draws each channel through a linear window and
 * its own colour, added together. The small copies the bridge makes wear a
 * scan-wide stretch instead, so the preview in the Discover panel and the
 * gallery's pairs showed the operator a different sample from the one on the
 * canvas. A copy asked for with the panel's own state -- one entry per
 * channel row of the acquisition, its visibility, window and colour -- is
 * drawn by the bridge exactly as the canvas draws it.
 */

/**
 * A colour as `#rrggbb`, from the panel's own forms: the viewer's triple of
 * 0..1, or a CSS `rgb(r,g,b)` / `#rrggbb` string. Null when there is none.
 * The bridge reads six hex digits and draws white for anything else, which
 * is how every copy came back grey.
 */
/** One channel row of the display panel, as its snapshot reports it. */
export interface SnapshotRow {
  acquisition?: string;
  name?: string;
  /** Where the channel sits in the picture's store, counted from 0. */
  within?: number;
  requested?: {
    window?: { low: number; high: number } | null;
    effectiveVisible?: boolean;
    visible?: boolean;
    colour?: unknown;
    color?: unknown;
  };
  [more: string]: unknown;
}

/** What the display panel reports of itself: a row per channel. */
export interface PanelSnapshot {
  channels?: SnapshotRow[];
  [more: string]: unknown;
}

/** One channel as the bridge is asked to draw it. */
interface Display {
  c: number | null;
  visible: boolean;
  window: [number, number] | null;
  color: string | null;
}

export function hexColour(colour: unknown, color: unknown): string | null {
  const hex = (parts: number[]) => `#${parts.map((v) => Math.round(Math.min(255, Math.max(0, v)))
    .toString(16).padStart(2, "0")).join("")}`;
  if (Array.isArray(colour) && colour.length === 3 && colour.every(Number.isFinite)) {
    return hex(colour.map((v: number) => v * 255));
  }
  if (typeof color !== "string") return null;
  const rgb = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)/i.exec(color);
  if (rgb) return hex([Number(rgb[1]), Number(rgb[2]), Number(rgb[3])]);
  return /^#[0-9a-f]{6}$/i.test(color) ? color.toLowerCase() : null;
}

/** The channel index a row's name carries: "channel 2" -> 2, else null. */
const channelIndexOf = (name: unknown): number | null => {
  const found = /channel\s+(\d+)/i.exec(String(name ?? ""));
  return found ? Number(found[1]) : null;
};

/**
 * Where a row's channel sits in the store: the position the panel keeps, and
 * only without one the number in its name. A microscope names its channels
 * after their dyes ("ALEXA 405"), so on the STELLARIS no name carried a number
 * and every copy came back in the plain red and green (2026-11-02).
 */
const channelOf = (row: SnapshotRow): number | null =>
  Number.isInteger(row.within) && (row.within as number) >= 0 ? (row.within as number) : channelIndexOf(row.name);

/**
 * The display entries for one acquisition, from the panel's snapshot; `[]`
 * when the panel has no rows for it. Requested state is what the operator
 * asked for, which is what the canvas is told to draw.
 */
export function displayFor(snapshot: PanelSnapshot | null | undefined, acquisition: string): Display[] {
  const rows = snapshot?.channels ?? [];
  return rows
    .filter((row) => row.acquisition === acquisition && channelOf(row) !== null)
    .map((row): Display => {
      const asked = row.requested ?? {};
      /* The panel keeps a window as the engine does, `low` to `high`. */
      const window: [number, number] | null = asked.window && Number.isFinite(asked.window.low)
        && Number.isFinite(asked.window.high) ? [asked.window.low, asked.window.high] : null;
      return {
        c: channelOf(row),
        visible: asked.effectiveVisible ?? asked.visible ?? true,
        window,
        color: hexColour(asked.colour, asked.color),
      };
    })
    .filter((one) => one.window !== null);
}

/**
 * One small copy, drawn with the picture's display settings, or null while
 * the panel has none for this acquisition: a copy in other colours than the
 * canvas's showed the operator a different sample. The panel says when its
 * settings arrive, and the copy is asked for then.
 */
export function displayedPictureAddress(
  where: string | null | undefined, label: string | null | undefined,
  snapshot: PanelSnapshot | null | undefined, acquisition: string,
): string | null {
  const display = displayFor(snapshot, acquisition);
  if (!where || !label || !display.length) return null;
  return `${where}/${label}.jpg?display=${encodeURIComponent(JSON.stringify(display))}`;
}

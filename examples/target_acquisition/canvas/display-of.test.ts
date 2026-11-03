import { describe, expect, it } from "vitest";
import {
  displayedPictureAddress,
  displayFor,
  hexColour,
} from "./display-of.ts";

const snapshot = {
  channels: [
    { acquisition: "overview", name: "channel 0",
      requested: { visible: true, effectiveVisible: true, color: "#22c55e", window: { low: 225, high: 3863 } } },
    { acquisition: "overview", name: "channel 1",
      requested: { visible: false, effectiveVisible: false, color: "#d946ef", window: { low: 0, high: 4000 } } },
    { acquisition: "target", name: "channel 0",
      requested: { visible: true, effectiveVisible: true, color: "#22c55e", window: { low: 100, high: 900 } } },
    { acquisition: "overview", name: "something else",
      requested: { visible: true, effectiveVisible: true, color: "#ffffff", window: { low: 0, high: 1 } } },
  ],
};

describe("the display the copies are asked with", () => {
  it("is one entry per channel row of the acquisition, with its window, colour and visibility", () => {
    expect(displayFor(snapshot, "overview")).toEqual([
      { c: 0, visible: true, window: [225, 3863], color: "#22c55e" },
      { c: 1, visible: false, window: [0, 4000], color: "#d946ef" },
    ]);
    expect(displayFor(snapshot, "target")).toEqual([
      { c: 0, visible: true, window: [100, 900], color: "#22c55e" },
    ]);
  });

  it("finds each channel by where it sits in the store, whatever the microscope calls it", () => {
    /* The STELLARIS names its channels after their dyes; no name carries a number. */
    const named = { channels: [
      { acquisition: "overview", name: "ALEXA 405", within: 0,
        requested: { visible: true, effectiveVisible: true, color: "#2563eb", window: { low: 10, high: 900 } } },
      { acquisition: "overview", name: "ALEXA 488", within: 1,
        requested: { visible: true, effectiveVisible: true, color: "#22c55e", window: { low: 20, high: 800 } } },
    ] };
    expect(displayFor(named, "overview")).toEqual([
      { c: 0, visible: true, window: [10, 900], color: "#2563eb" },
      { c: 1, visible: true, window: [20, 800], color: "#22c55e" },
    ]);
    expect(displayedPictureAddress("/view/overview", "P0001", named, "overview"))
      .toContain("/view/overview/P0001.jpg?display=");
  });

  it("is what the whole group shows, not only what the row asked: a hidden group hides its rows", () => {
    const hidden = { channels: [{ acquisition: "overview", name: "channel 0",
      requested: { visible: true, effectiveVisible: false, color: "#22c55e", window: { low: 0, high: 10 } } }] };
    expect(displayFor(hidden, "overview")[0].visible).toBe(false);
  });

  it("leaves out a row with no window", () => {
    const bare = { channels: [{ acquisition: "overview", name: "channel 0", requested: { visible: true, color: "#fff", window: null } }] };
    expect(displayFor(bare, "overview")).toEqual([]);
  });

  it("asks with the canvas's settings, in a query the bridge can read back", () => {
    const address = displayedPictureAddress("/view/target", "P0001", snapshot, "target")!;
    expect(address.startsWith("/view/target/P0001.jpg?display=")).toBe(true);
    expect(JSON.parse(decodeURIComponent(address.slice(address.indexOf("=") + 1))))
      .toEqual([{ c: 0, visible: true, window: [100, 900], color: "#22c55e" }]);
  });

  it("asks for no copy until the canvas has settings to draw it with", () => {
    /* A copy in other colours than the canvas's showed a different sample. */
    expect(displayedPictureAddress("/view/targets", "P0002", null, "targets")).toBeNull();
    expect(displayedPictureAddress("/view/overview", "P0001", { channels: [] }, "overview")).toBeNull();
  });
});

describe("the colour a copy is asked for", () => {
  it("is six hex digits whatever form the panel keeps it in", () => {
    expect(hexColour([0.2, 0.8, 1.0], null)).toBe("#33ccff");
    expect(hexColour(null, "rgb(51,204,255)")).toBe("#33ccff");
    expect(hexColour(null, "#22C55E")).toBe("#22c55e");
    expect(hexColour(null, "#d8dee6")).toBe("#d8dee6");
  });
  it("is nothing when the panel has no colour to give", () => {
    expect(hexColour(null, null)).toBeNull();
    expect(hexColour(null, "grey")).toBeNull();
  });
  it("a row that keeps the viewer's triple asks with it", () => {
    const snapshot = { channels: [{ acquisition: "overview", name: "channel 0",
      requested: { visible: true, effectiveVisible: true, color: "rgb(0,255,102)", colour: [0, 1, 0.4], window: { low: 1, high: 9 } } }] };
    expect(displayFor(snapshot, "overview")).toEqual([{ c: 0, visible: true, window: [1, 9], color: "#00ff66" }]);
  });
});

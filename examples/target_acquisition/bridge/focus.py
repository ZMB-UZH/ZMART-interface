"""The focus map, one stack at a time: the page drives, the bridge files and scores.

Begin starts a focus run when the whole map is measured, or stays in the
current one when only some points are, and names the stacks; the page
drives and captures each; score files the stack, scores it through the
warm analysis and answers the point; end closes the map. The ledger of the
points scored so far is ``ledgers.focus``.

Author: Thom de Hoog, Center for Microscopy and Image Analysis (ZMB),
University of Zurich (thom.dehoog@zmb.uzh.ch, thomdehoog@gmail.com).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from ..analysis import focus_score, warm
from ..microscope.focus_run import FOCUSSING, measure_one_stack
from ..storage import output
from ..storage.output import position_label, prepare_acquisition
from . import ledgers, pictures, stage, state, views


def score_a_stack():
    """How a captured stack becomes a height and a curve.

    Through the warm analysis, which is shared with every other step that
    measures pixels and outlives any one focus map. See
    :mod:`target_acquisition.analysis.warm`.
    """
    return focus_score.through(warm.the_analysis())


def begin_focus(asked: dict) -> dict:
    """The page begins measuring: the whole map, or some of its points.

    Measuring the whole map starts a new focus run,
    ``focussing/overview/run_NN``. Measuring some points again, or only the
    points added since, stays in the current run: ``at`` names those points
    by their place in the map, and each keeps its own label, so point 7 is
    ``...P000007`` however often it is measured. A point's new stack stands
    beside its earlier one, and the map uses the new one. ``settings`` is
    what the stacks are taken with; it goes into the run's record.

    The page drives every point itself from here -- ``/api/xyz``, then
    ``/api/acquire`` with the label named here, then ``/api/focus/score`` --
    and ends the map with ``/api/focus/end``. Between two answers the page
    decides, and a stop is its own decision; nothing runs here on its own.
    Refused while a scan or a map has the stage.
    """
    if ledgers.a_run_has_the_stage():
        raise RuntimeError("the instrument is driving a run; a focus map cannot begin now")
    of = int(asked.get("of", 0))
    at = asked.get("at")
    if at is None or output.current_run(state.the_run(), FOCUSSING) is None:
        at = list(range(of)) if at is None else at
        pictures.begin_a_run(FOCUSSING, settings=asked.get("settings"))
        focus_map.clear()
    at = [int(index) for index in at]
    if len(at) != of:
        raise ValueError(f"{of} points are to be measured, but {len(at)} places in the map were named")
    ledgers.focus.update(
        running=True, done=0, of=of, error=None, stopped=False, points=[], doing=None, at=at,
        settings=asked.get("settings"),
    )
    return {**dict(ledgers.focus), "labels": [position_label(index) for index in at]}


def score_focus(asked: dict) -> dict:
    """One stack the page just captured: file it, score it, answer the point.

    ``record`` is the driver's own answer to the capture, ``centre`` the
    height the stack was taken around (the drive's answer), ``point`` what
    the page asked with. The point comes back as the map reports it -- the
    height, the curves, the slice copies -- and is kept in the ledger.
    ``startZ`` said where to begin this search; echoing it back would have
    the next run silently begin where this one did.
    """
    if not ledgers.focus["running"]:
        raise RuntimeError("no focus map has begun")
    record = asked["record"]
    # The interface's own grouping, from what it asked for (see ``state.records``).
    record["acquisition_type"] = FOCUSSING
    point = dict(asked.get("point") or {})
    # The point's place in the map, which names its stack: the same point
    # measured again keeps its label.
    index = ledgers.focus["at"][len(ledgers.focus["points"])]
    measurement = measure_one_stack(
        record, x=float(point["x"]), y=float(point["y"]), centre=float(asked["centre"]),
        score=score_a_stack(), index=index,
        output=prepare_acquisition(state.the_run(), FOCUSSING),
        # Every focus stack also stands as a position of the run, so the
        # focussing is a source of its own in the viewer.
        keep=lambda landed: pictures.keep_the_position(landed, FOCUSSING),
        cost=asked.get("cost_s"),
    )
    stage.the_stage_was_sent_to(
        measurement["x_um"], measurement["y_um"],
        measurement["z_um"] if measurement.get("z_um") is not None else 0.0,
    )
    landed = {
        **{key: value for key, value in point.items() if key != "startZ"},
        "zAuto": measurement["z_um"], "z": measurement["z_um"],
        "lost": measurement["z_um"] is None, "traces": measurement["traces"],
        "cost_s": measurement.get("cost_s"),
        "slices": views.the_slice_copies_of(measurement.get("planes") or [],
                                      store=measurement.get("position_path")),
    }
    ledgers.focus["points"].append(landed)
    ledgers.focus["done"] = len(ledgers.focus["points"])
    the_map_changed(index, landed, measurement)
    return landed


#: The focus map as it stands in the current run, point by point: what
#: ``focus_map.json`` in the run's folder says.
focus_map: dict[int, dict] = {}


def the_map_changed(index: int, landed: dict, measurement: dict) -> None:
    """Write ``focus_map.json`` again: every point, where it is, its height and its stack.

    A point measured again keeps the stacks it had before under
    ``superseded``, so the record says both which stack the map uses now and
    which were taken before it.
    """
    folder = output.current_run(state.the_run(), FOCUSSING)
    if folder is None:
        return
    stack = measurement.get("position_path")
    earlier = focus_map.get(index)
    superseded = list(earlier.get("superseded", [])) if earlier else []
    if earlier and earlier.get("stack"):
        superseded.append(earlier["stack"])
    focus_map[index] = {
        "point": index,
        "label": position_label(index),
        "x_um": landed.get("x"), "y_um": landed.get("y"),
        "z_um": None if landed.get("lost") else landed.get("z"),
        "found": not landed.get("lost"),
        "stack": _relative(stack, folder),
        "superseded": superseded,
        "taken_with": ledgers.focus.get("settings"),
        "measured": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    said = {"points": [focus_map[key] for key in sorted(focus_map)]}
    writing = folder / ".focus_map.writing.json"
    writing.write_text(json.dumps(said, indent=2, default=str), encoding="utf-8")
    os.replace(writing, folder / "focus_map.json")


def _relative(path, folder) -> str | None:
    """*path* as seen from *folder*, so the record stays true when the experiment is moved."""
    if not path:
        return None
    try:
        return Path(path).relative_to(folder).as_posix()
    except ValueError:
        return str(path)


def stop_focus() -> dict:
    """The operator's Interrupt for a focus map: reach a point whose scoring has hung.

    The page stops its own loop between two points, but a point whose
    scoring never answers keeps its request open for ever, and the map with
    it. Putting the analysis workers down makes that scoring answer at once
    with an error, as stopping discovery does; the workers start again on
    the next request. The capture in hand is already on disk, so nothing is
    lost. The page still ends the map itself, with ``/api/focus/end``.
    """
    if ledgers.focus["running"]:
        warm.close()
    return dict(ledgers.focus)


def end_focus(asked: dict) -> dict:
    """The page ends the map, stopped by its hand or complete."""
    ledgers.focus.update(running=False, doing=None, stopped=bool(asked.get("stopped")))
    pictures.end_the_run(FOCUSSING, stopped=bool(asked.get("stopped")))
    return dict(ledgers.focus)

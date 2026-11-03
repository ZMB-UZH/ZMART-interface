"""A step run again gets a run folder of its own; a small correction stays in the run it corrects.

Every run of the focus map, the overview scan and the targets is a numbered
folder, ``run_01``, ``run_02``, ... beside the earlier ones, and nothing of an
earlier run is overwritten. Measuring one focus point again, or the points
added since, is a correction to the current map: it stays in its run, the
point keeps its label, and ``focus_map.json`` says which stack each point uses
now and which it used before. The targets run keeps ``selection.json``: why
these targets, down to the numbered plot their gates were drawn on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..storage import output, viewer_service
from . import focus, ledgers, pictures, plots, state, targets


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    folder = output.prepare_experiment(tmp_path, "screen", hash6="abc123")
    monkeypatch.setattr(state, "run", folder)
    monkeypatch.setattr(state, "records", {})
    monkeypatch.setattr(state, "shown_positions", {})
    monkeypatch.setattr(viewer_service, "a_run_began", lambda kind: None)
    monkeypatch.setattr(viewer_service, "forget_a_store", lambda kind, name: None)
    monkeypatch.setattr(focus, "focus_map", {})
    monkeypatch.setitem(ledgers.focus, "running", False)
    monkeypatch.setitem(ledgers.acquired, "running", False)
    monkeypatch.setitem(ledgers.scan, "running", False)
    return folder


@pytest.fixture
def a_stack_is_measured(monkeypatch):
    """A focus stack that lands as a position named after its label, at a fixed height."""
    taken = []

    def measure(record, *, x, y, centre, score, index, output, keep, cost=None):
        stack = output / "data" / f"focussing_{record['position_label']}_{len(taken):03d}.ome.zarr"
        stack.mkdir(parents=True)
        taken.append(stack)
        return {"x_um": x, "y_um": y, "z_um": 10.0 + index, "traces": [], "planes": [],
                "position_path": str(stack)}

    monkeypatch.setattr(focus, "measure_one_stack", measure)
    monkeypatch.setattr(focus, "score_a_stack", lambda: None)
    monkeypatch.setattr(focus.stage, "the_stage_was_sent_to", lambda *args: None)
    monkeypatch.setattr(focus.views, "the_slice_copies_of", lambda *args, **kwargs: [])
    return taken


def measure(points, *, at=None):
    """The page's measuring, as live.ts drives it: begin, one stack per point, end."""
    begun = focus.begin_focus({"of": len(points), **({"at": at} if at is not None else {})})
    for label, (x, y) in zip(begun["labels"], points, strict=True):
        focus.score_focus({"record": {"position_label": label, "planes": []}, "centre": 0.0,
                           "point": {"x": x, "y": y}})
    focus.end_focus({})
    return begun["labels"]


def the_map(experiment):
    folder = output.current_run(experiment, "focussing")
    return folder, json.loads((folder / "focus_map.json").read_text(encoding="utf-8"))


def test_measuring_one_point_again_stays_in_the_map_it_corrects(experiment, a_stack_is_measured):
    labels = measure([(0, 0), (100, 0), (200, 0)])
    first_run, _ = the_map(experiment)

    again = measure([(100, 0)], at=[1])

    folder, said = the_map(experiment)
    assert folder == first_run == experiment / "focussing" / "overview" / "run_01"
    assert again == [labels[1]], "point 1 keeps its label"
    one = said["points"][1]
    assert one["stack"].endswith("_003.ome.zarr"), "the map uses the new stack"
    assert one["superseded"] == ["data/focussing_" + labels[1] + "_001.ome.zarr"]
    assert [point["point"] for point in said["points"]] == [0, 1, 2]
    assert all(Path(folder, point["stack"]).exists() for point in said["points"])
    assert (folder / "data" / f"focussing_{labels[1]}_001.ome.zarr").exists(), "nothing is deleted"


def test_points_added_later_join_the_same_map(experiment, a_stack_is_measured):
    measure([(0, 0), (100, 0)])
    measure([(300, 0)], at=[2])
    folder, said = the_map(experiment)
    assert folder.name == "run_01"
    assert [point["point"] for point in said["points"]] == [0, 1, 2]


def test_measuring_the_whole_map_again_is_a_new_run(experiment, a_stack_is_measured):
    measure([(0, 0), (100, 0)])
    measure([(0, 0), (100, 0)])
    folder, said = the_map(experiment)
    assert folder.name == "run_02"
    assert all(not point["superseded"] for point in said["points"]), "a new map starts fresh"
    assert (experiment / "focussing" / "overview" / "run_01" / "focus_map.json").exists()
    ended = json.loads((folder / "attempt.json").read_text(encoding="utf-8"))
    assert ended["how_it_ended"] == "finished"


def test_every_plot_is_kept_under_its_own_number(experiment, monkeypatch):
    table = plots.the_analysis_folder() / "overview_abc123_objects.csv"
    table.parent.mkdir(parents=True)
    table.write_text("id,a\n", encoding="utf-8")
    for coordinates in ("id,umap_1,umap_2\nA,1,2\n", "id,umap_1,umap_2\nA,5,6\n"):
        table.with_name("overview_abc123_umap.csv").write_text(coordinates, encoding="utf-8")
        plots.keep_the_plot("umap", table, None)

    kept = table.parent / "plots"
    assert sorted(path.name for path in kept.iterdir()) == [
        "umap_01.csv", "umap_01.json", "umap_02.csv", "umap_02.json",
    ]
    assert (kept / "umap_01.csv").read_text(encoding="utf-8").endswith("A,1,2\n"), "never overwritten"
    assert plots.latest["umap"] == kept / "umap_02.csv"


def test_the_targets_run_keeps_why_its_targets_were_chosen(experiment, monkeypatch):
    umap = experiment / "overview" / "run_01" / "analysis" / "plots" / "umap_02.csv"
    monkeypatch.setattr(plots, "latest", {"umap": umap, "pca": umap.with_name("pca_01.csv")})
    gates = [{"fx": "umap_1", "fy": "umap_2", "vertices": [[0, 0], [1, 0], [1, 1]]}]

    targets.begin_target_run({
        "positions": [{"x": 10.0, "y": 20.0}],
        "selection": {"gates": gates, "objects": ["A", "B"]},
    })
    targets.end_target_run({})

    folder = output.current_run(experiment, "targets")
    said = json.loads((folder / "selection.json").read_text(encoding="utf-8"))
    assert folder == experiment / "targets" / "run_01"
    assert said["gates"] == gates and said["objects"] == ["A", "B"]
    assert said["plots"] == {"umap": str(umap)}, "the very plot the gates were drawn on, and no other"
    assert said["fields"] == [{"x": 10.0, "y": 20.0}]
    assert output.current_run(experiment, "target-focussing") == (
        experiment / "focussing" / "targets" / "run_01"
    )


def test_one_target_taken_again_stays_in_its_run(experiment):
    targets.begin_target_run({"positions": [{"x": 0.0, "y": 0.0}], "selection": {}})
    targets.end_target_run({})
    targets.begin_target_run({"positions": [{"x": 0.0, "y": 0.0}], "append": True})
    targets.end_target_run({})
    assert output.current_run(experiment, "targets").name == "run_01"
    assert not (experiment / "targets" / "run_02").exists()


def test_a_label_shown_again_hides_its_earlier_position(experiment, monkeypatch):
    forgotten = []
    monkeypatch.setattr(viewer_service, "forget_a_store", lambda kind, name: forgotten.append(name))
    monkeypatch.setattr(viewer_service, "a_position_landed", lambda *args, **kwargs: None)
    monkeypatch.setattr(pictures.positions, "frame_um_of", lambda path: 1.0)
    data = output.prepare_acquisition(experiment, "targets") / "data"
    for name in ("targets_T1_a.ome.zarr", "targets_T1_b.ome.zarr"):
        (data / name).mkdir(parents=True)
        monkeypatch.setattr(pictures, "the_drivers_position", lambda record, n=name: data / n)
        pictures.keep_the_position({"position_label": "T1", "planes": [{"z": 0}]}, "targets")
    assert forgotten == ["targets_T1_a.ome.zarr"]


def test_the_protocol_starts_on_a_clean_canvas_but_the_focus_map(monkeypatch):
    """Step 10 starts with nothing of the earlier overview and targets on the
    canvas; the focus map stays, as the run keeps it. Nothing leaves the disk."""
    shown = [{"name": kind} for kind in ("focussing", "overview", "targets", "target-focussing")]
    monkeypatch.setattr(viewer_service, "_viewer", {
        "source_versions": {("overview", "overview_A1.ome.zarr"): 1}, "source_order": {"overview": ["overview_A1.ome.zarr"]},
        "projections_in": {}, "folder_types": {"/run/overview/run_01/data": "overview"}, "pending": set(),
        "sources": {one["name"]: [] for one in shown}, "acquisitions": list(shown),
    })
    monkeypatch.setattr(state, "shown_positions", {("overview", "A1"): "overview_A1.ome.zarr"})
    monkeypatch.setattr(state, "displayed_pictures", {})

    pictures.a_protocol_began()

    assert viewer_service.kinds() == {"focussing"}
    assert state.shown_positions == {}

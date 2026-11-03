"""A capture lands as one position in the format chosen on the Connect step.

The microscope's own files stay where they are. Beside them, each capture
becomes one position: an OME-TIFF file or an OME-Zarr image. An OME-TIFF run
also keeps each stack's projection over z as an OME-TIFF, because the viewer
makes projections only for OME-Zarr, and a person looking through the run's
folder expects to open them. A position the driver already saved is used as
it is, in whichever format it came.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("tifffile")
pytest.importorskip("zarr")

from ..storage import positions, viewer_service  # noqa: E402
from ..storage.test_positions import a_z_stack, one_file_per_plane  # noqa: E402
from . import connecting, pictures, state  # noqa: E402


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "run", tmp_path / "run")
    (tmp_path / "run").mkdir()
    return tmp_path / "run"


@pytest.fixture
def announced(monkeypatch):
    told = []
    monkeypatch.setattr(
        viewer_service,
        "a_position_landed",
        lambda kind, folder, *, store, projections_in=None: told.append(
            (kind, Path(folder), Path(store), projections_in and Path(projections_in))
        ),
    )
    return told


def test_a_stack_in_an_ome_tiff_run_lands_as_one_file_with_its_projection(
    run, announced, monkeypatch, tmp_path
):
    monkeypatch.setattr(state, "image_format", "ome-tiff")
    (tmp_path / "raw").mkdir()
    record = a_z_stack(tmp_path / "raw")

    pictures.keep_the_position(record, "focussing")

    assert "position_error" not in record
    position = Path(record["position_path"])
    the_run = run / "focussing" / "overview" / "run_01"
    assert position.parent == the_run / "positions"
    assert positions.format_of(position) == "ome-tiff"
    projection = the_run / "projections" / position.name
    assert positions.format_of(projection) == "ome-tiff"
    assert record["frame_um"] == pytest.approx(positions.frame_um_of(position))
    assert announced == [("focussing", position.parent, position, projection.parent)]


def test_a_single_plane_is_its_own_projection(run, announced, monkeypatch, tmp_path):
    monkeypatch.setattr(state, "image_format", "ome-tiff")
    record = one_file_per_plane(tmp_path / "raw")

    pictures.keep_the_position(record, "overview")

    position = Path(record["position_path"])
    assert announced == [("overview", position.parent, position, position.parent)]
    assert not (run / "overview" / "run_01" / "projections").exists(), "nothing is written twice"


def test_an_ome_zarr_run_lands_as_before(run, announced, monkeypatch, tmp_path):
    monkeypatch.setattr(state, "image_format", "ome-zarr")
    (tmp_path / "raw").mkdir()
    record = a_z_stack(tmp_path / "raw")

    pictures.keep_the_position(record, "focussing")

    position = Path(record["position_path"])
    assert positions.format_of(position) == "ome-zarr"
    assert announced == [("focussing", position.parent, position, None)], "the viewer projects it"


def test_a_tiff_position_the_driver_saved_is_used_as_it_is(run, announced, monkeypatch, tmp_path):
    monkeypatch.setattr(state, "image_format", "ome-tiff")
    (tmp_path / "raw").mkdir()
    saved = positions.position_from_record(
        a_z_stack(tmp_path / "raw"), run / "focussing" / "data", format="ome-tiff"
    )
    record = {
        "position_label": "F1",
        "files": [str(saved)],
        "planes": [
            {"path": str(saved), "t": 0, "c": 0, "z": z, "x_um": 1000.0, "y_um": 2000.0, "z_um": z}
            for z in range(3)
        ],
    }

    pictures.keep_the_position(record, "focussing")

    assert record["position_path"] == str(saved)
    assert not (run / "positions").exists(), "no second copy of the capture"
    [(_, folder, store, projections_in)] = announced
    assert (folder, store) == (saved.parent, saved)
    assert projections_in == run / "focussing" / "projections"


def test_a_rerun_keeps_the_earlier_runs_positions_and_projections(run, monkeypatch, tmp_path):
    """A new run never deletes an earlier one: both stay on disk, each in its own folder."""
    monkeypatch.setattr(state, "image_format", "ome-tiff")
    monkeypatch.setattr(viewer_service, "a_position_landed", lambda *args, **kwargs: None)
    monkeypatch.setattr(viewer_service, "a_run_began", lambda kind: None)
    (tmp_path / "raw").mkdir()
    record = a_z_stack(tmp_path / "raw")
    pictures.keep_the_position(record, "focussing")
    position = Path(record["position_path"])
    projection = position.parent.parent / "projections" / position.name

    pictures.begin_a_run("focussing")
    pictures.keep_the_position(a_z_stack(tmp_path / "raw"), "focussing")

    assert position.exists() and projection.exists()
    assert (run / "focussing" / "overview" / "run_02" / "positions").is_dir()



def test_an_unknown_format_is_refused_before_anything_opens(monkeypatch):
    monkeypatch.setitem(connecting.offered, "never", (object, {}))
    with pytest.raises(ValueError, match="a run is saved as one of"):
        connecting.connect({"instrument": "never", "format": "ome-tif"})

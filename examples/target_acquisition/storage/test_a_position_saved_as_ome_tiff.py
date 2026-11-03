"""A position saved as OME-TIFF holds what the same position saved as OME-Zarr holds.

A run is saved in the format chosen on the Connect step. These tests write the
same capture both ways and check that nothing is lost on the OME-TIFF side:
the pixels at every size, the pixel size, where the picture sits on the stage
and ZMART's own record of how the planes were taken. They also check that the
file is an ordinary OME-TIFF that other programs open, and that its
projection over z is what a person expects to see.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

tifffile = pytest.importorskip("tifffile")
zarr = pytest.importorskip("zarr")
ome_types = pytest.importorskip("ome_types")

# After the skips, so a machine without them skips rather than fails.
from . import positions  # noqa: E402
from .test_positions import (  # noqa: E402
    a_z_stack,
    one_file_per_plane,
    one_file_whole_capture,
)

CAPTURES = {
    "one file per plane": lambda folder: one_file_per_plane(folder, channels=2, size=300),
    "one file for the capture": lambda folder: one_file_whole_capture(folder, channels=3, size=128),
    "a z-stack": lambda folder: a_z_stack(folder),
}


def both_ways(tmp_path, capture):
    """The same capture written once as OME-Zarr and once as OME-TIFF."""
    (tmp_path / "raw").mkdir()
    record = CAPTURES[capture](tmp_path / "raw")
    as_zarr = positions.position_from_record(record, tmp_path / "zarr", format="ome-zarr")
    as_tiff = positions.position_from_record(record, tmp_path / "tiff", format="ome-tiff")
    return as_zarr, as_tiff


def five_axes(level) -> np.ndarray:
    """One size of the OME-TIFF, as (t, c, z, y, x)."""
    return positions._in_five_axes(level.asarray(), level.axes)


@pytest.mark.parametrize("capture", list(CAPTURES))
def test_the_same_capture_holds_the_same_picture_either_way(tmp_path, capture):
    as_zarr, as_tiff = both_ways(tmp_path, capture)
    assert as_tiff.name == as_zarr.name.replace(".ome.zarr", ".ome.tif")

    group = zarr.open_group(str(as_zarr), mode="r")
    with tifffile.TiffFile(as_tiff) as tif:
        levels = tif.series[0].levels
        assert len(levels) == len([key for key in group.array_keys()])
        for index, level in enumerate(levels):
            np.testing.assert_array_equal(five_axes(level), group[str(index)][...])
        root = ome_types.from_xml(tif.ome_metadata)

    assert positions.pixel_size_um_of(as_tiff) == pytest.approx(positions.pixel_size_um_of(as_zarr))
    assert positions.frame_um_of(as_tiff) == pytest.approx(positions.frame_um_of(as_zarr))

    # Where the picture sits follows the OME-Zarr rules in both formats: the
    # note carries the very description the OME-Zarr image has, every
    # level's scale and the centre of its first voxel.
    note = positions._the_note_in(str(as_tiff), *_stamp(as_tiff))
    assert json.loads(note["multiscales"]) == group.attrs["ome"]["multiscales"]
    # The planes' heights are written for other programs too, from the same place.
    translation = group.attrs["ome"]["multiscales"][0]["datasets"][0]["coordinateTransformations"][1]["translation"]
    assert root.images[0].pixels.planes[0].position_z == pytest.approx(translation[2])

    # ZMART's own record of how the planes were taken travels along.
    assert json.loads(note["zmart_microscopy"]) == group.attrs["zmart_microscopy"]
    # Each channel opens with the colour and brightness window the OME-Zarr says:
    # OME-XML has no place for a window, and without it the run opens nearly black.
    assert json.loads(note["omero"]) == group.attrs["ome"]["omero"]


def test_an_ome_tiff_position_is_an_ordinary_ome_tiff(tmp_path):
    """Other programs read the standard part: pixel size, channels, one image."""
    _, as_tiff = both_ways(tmp_path, "a z-stack")
    with tifffile.TiffFile(as_tiff) as tif:
        assert tif.is_ome
        assert len(tif.series) == 1, "one position, so Fiji opens it without asking which"
        described = ome_types.from_xml(tif.ome_metadata)  # checked against the OME schema
    pixels = described.images[0].pixels
    assert (pixels.size_z, pixels.size_c, pixels.size_t) == (3, 1, 1)
    assert pixels.physical_size_x > 0 and pixels.physical_size_z == pytest.approx(2.0)
    assert [channel.name for channel in pixels.channels] == ["channel 0"]
    assert not list(as_tiff.parent.glob(".*")), "nothing half-written is left beside it"


def test_only_a_tiff_with_zmarts_note_counts_as_a_position(tmp_path):
    as_zarr, as_tiff = both_ways(tmp_path, "one file per plane")
    plane_file = tmp_path / "raw" / "plane_c0.ome.tif"
    assert positions.format_of(as_tiff) == "ome-tiff"
    assert positions.format_of(as_zarr) == "ome-zarr"
    assert positions.format_of(plane_file) is None, "a vendor's plane does not carry ZMART's note"
    assert positions.is_a_position_name(as_tiff.name) and positions.is_a_position_name(as_zarr.name)


def test_the_projection_is_the_brightest_of_every_plane_at_the_same_place(tmp_path):
    _, as_tiff = both_ways(tmp_path, "a z-stack")
    projection = positions.write_a_projection(as_tiff, tmp_path / "projections")
    assert projection.name == as_tiff.name
    with tifffile.TiffFile(as_tiff) as tif:
        stack = five_axes(tif.series[0])
    with tifffile.TiffFile(projection) as tif:
        flat = five_axes(tif.series[0])
    np.testing.assert_array_equal(flat, stack.max(axis=2, keepdims=True))
    assert positions._the_note_in(str(projection), *_stamp(projection))["omero"] == (
        positions._the_note_in(str(as_tiff), *_stamp(as_tiff))["omero"]
    ), "the projection opens looking like its stack"
    placed = json.loads(positions._the_note_in(str(projection), *_stamp(projection))["multiscales"])
    stack_at = json.loads(positions._the_note_in(str(as_tiff), *_stamp(as_tiff))["multiscales"])
    for flat_level, stack_level in zip(placed[0]["datasets"], stack_at[0]["datasets"], strict=False):
        flat_xy = flat_level["coordinateTransformations"][1]["translation"][3:]
        stack_xy = stack_level["coordinateTransformations"][1]["translation"][3:]
        assert flat_xy == pytest.approx(stack_xy), "the projection lies where its stack does"
    assert positions.format_of(projection) == "ome-tiff"


def test_a_label_taken_again_stands_beside_the_earlier_file(tmp_path):
    (tmp_path / "raw").mkdir()
    record = one_file_per_plane(tmp_path / "raw")
    first = positions.position_from_record(record, tmp_path / "tiff", format="ome-tiff")
    second = positions.position_from_record(record, tmp_path / "tiff", format="ome-tiff")
    assert second.name == first.name.replace(".ome.tif", "_001.ome.tif")
    assert sorted(path.name for path in (tmp_path / "tiff").iterdir()) == [first.name, second.name]


def test_an_unknown_format_is_refused_by_name():
    assert positions.checked_format(None) == "ome-tiff"
    with pytest.raises(ValueError, match="ome-tiff"):
        positions.checked_format("tiff")


def _stamp(path):
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size

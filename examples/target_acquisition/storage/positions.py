"""Each capture becomes one position of the run, in the format chosen at Connect.

The instrument writes what it writes — LAS X's autosave leaves OME-TIFFs, and
fighting a vendor's own export is a losing game — so the vendor's files are
used as well as possible and then, the moment a capture lands, converted into
the run's own form: **one position per capture, axes t/c/z/y/x**, where it
was taken recorded inside it where nobody can rename it away. The vendor's
files stay untouched in ``data/``; the positions stand in ``positions/``
beside them.

A run is saved in one of two formats, chosen when connecting (:data:`FORMATS`):

- **OME-TIFF** (the default): one ``.ome.tif`` file per position, holding
  every channel and plane, with smaller copies stored inside it the standard
  way. It opens with a drag and drop in Fiji, napari, QuPath or Imaris.
- **OME-Zarr 0.5**: one ``.ome.zarr`` image per position.

Both are placed by the same rules, those of OME-Zarr. An OME-TIFF position
carries the very description its OME-Zarr twin would have (each level's
scale, and the centre of its first voxel as its translation), its channels'
display and how the planes were taken, in ZMART's note inside its OME-XML
(:data:`ZMART_NOTE`). Other programs skip the note. This module is the one
place in the interface that knows the two formats apart: the rest asks it
whether something is a position, how large its pixels are and how wide its
frame is.

One folder per acquisition type, holding nothing but position stores, is
exactly the shape the ZMART viewer opens as one acquisition — the overview,
the focussing, and the target scans each become a source of their own, and the
viewer links a folder's positions into one picture without copying a voxel.

The declaration of the store is not done here:
:func:`target_acquisition.storage.images.declare_image`
already writes the five axes, the per-level scale and translation, and the
channel description, and saying any of that twice is how the two copies drift.
This module reads the vendor's planes into the declared arrays and builds each
smaller level by averaging 2 × 2 pixels. A position is complete before it is
published, so unlike a live sparse canvas it can preserve all of its signal at
every level of detail without baking the positions into a second mosaic.

What the vendor's file does not say, the run's record does: a TIFF's OME block
carries the pixel size, but where a capture was taken comes from the record's
own planes (``x_um``/``y_um``/``z_um``), because the acquisition is the only
party that knows. The image axes are taken to lie along the stage axes — the
same single-place assumption as ``detection.IMAGE_TO_STAGE`` — and the
recorded stage point is the centre of the frame. The store says where it lies
the way OME-NGFF does (RFC-5: the centre of a voxel is the origin of the
coordinates): by the centre of its first voxel, half a frame less half a pixel
up and left of the stage point.

Author: Thom de Hoog (ZMB, University of Zurich).
License: MIT
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import time
import uuid
import xml.etree.ElementTree as ElementTree
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import numpy as np

from .images import (
    Channel,
    declare_image,
    how_many_copies_a_position_can_keep,
)

#: The two formats a run's positions can be saved in, as the Connect step
#: offers them: OME-TIFF first, and the default.
FORMATS = ("ome-tiff", "ome-zarr")
DEFAULT_FORMAT = "ome-tiff"

#: The ending each format's positions are named with.
ENDINGS = {"ome-tiff": ".ome.tif", "ome-zarr": ".ome.zarr"}

#: The endings an OME-TIFF may have, written by ZMART or by another program.
_TIFF_ENDINGS = (".ome.tif", ".ome.tiff")

#: The namespace of ZMART's note inside an OME-TIFF position, which the ZMART
#: viewer reads too. Its entries are JSON, each what an OME-Zarr position
#: keeps under the same name: ``multiscales`` (each level's scale and the
#: centre of its first voxel, which is what places the position), ``omero``
#: (each channel's name, colour and the brightness window it opens with) and
#: ``zmart_microscopy`` (how the planes of a stack were taken). An OME-TIFF
#: without the note is not a position: its own ``PositionX`` and
#: ``PositionY`` are never used, because programs disagree on which point of
#: the picture they name.
ZMART_NOTE = "zmart/position"

#: How hard an OME-TIFF's pixels are packed: deflate, at its fastest level.
#: Measured on fluorescence stacks, it writes a file about a third of the raw
#: size in a third of a second per 100 MB, quick enough for a live run, and
#: Fiji, QuPath and Imaris (through Bio-Formats) and napari all read it.
_DEFLATE_LEVEL = 1

#: The chunk edge in y and x, matching the run stores ZMART's writer makes.
#: An OME-TIFF position is cut into tiles of the same size.
PIECE = 128

#: Metres and friends, as OME spells them, into micrometres. OME's default
#: unit for a physical size is µm, so a missing unit multiplies by one.
_TO_UM = {"m": 1e6, "mm": 1e3, "µm": 1.0, "um": 1.0, "nm": 1e-3, "": 1.0}


#: How many times a position is written before a denied rename is given up
#: on, and how long to wait between tries. Windows refuses to rename a file
#: another process holds open -- a scanner, a folder watcher -- for a moment;
#: the interface's own bridge lost one position in three that way, with the
#: development server watching the folder it wrote to.
WRITE_ATTEMPTS = 3
WRITE_RETRY_S = 0.3


def checked_format(asked: str | None) -> str:
    """The format a run is saved in: the one asked for, or the default when none was.

    Raises ``ValueError`` naming the formats when the word is not one of them.
    """
    chosen = asked or DEFAULT_FORMAT
    if chosen not in FORMATS:
        raise ValueError(f"a run is saved as one of {list(FORMATS)}, not {chosen!r}")
    return chosen


def position_from_record(record: dict, into: Path | str, *, format: str) -> Path:
    """Write one position from a capture's record, in the run's format, and return it.

    ``record`` is what the driver's acquire returned — its ``planes`` name the
    vendor's files and where each was taken. ``into`` is the acquisition's
    ``positions`` folder; the position lands there as
    ``<acquisition type>_<position_label>`` with the format's ending, an
    ordinary OME-TIFF or OME-Zarr image that opens on its own in Fiji, napari
    or the ZMART viewer. ``format`` is one of :data:`FORMATS`.

    A rename the file system denies is tried again, in a fresh place, up to
    :data:`WRITE_ATTEMPTS` times; one denied for good raises as itself.
    """
    for attempt in range(WRITE_ATTEMPTS):
        try:
            return _write_a_position(record, into, format=format)
        except PermissionError as denied:
            if attempt == WRITE_ATTEMPTS - 1:
                raise
            time.sleep(WRITE_RETRY_S * (attempt + 1))
            last = denied
    raise last  # pragma: no cover -- the loop above always returns or raises


def frame_um_of(position: Path | str) -> float:
    """How wide one position is on the sample, in micrometres: its full-size
    width times the pixel size the writer recorded. The position is the
    capture's own word on its size, where a recording made before the run is
    only what was promised."""
    position = Path(position)
    if position.name.lower().endswith(_TIFF_ENDINGS):
        import tifffile

        with tifffile.TiffFile(position) as tif:
            width_px = tif.series[0].shape[-1]
    else:
        import zarr  # noqa: PLC0415

        full_size = _the_description_of(position)["datasets"][0]["path"]
        width_px = zarr.open_array(str(position / full_size), mode="r").shape[-1]
    return float(width_px * pixel_size_um_of(position))


def pixel_size_um_of(position: Path | str) -> float:
    """The width of one full-size pixel of a position, in micrometres.

    Only the position's description is read, never its pixels. Raises
    ``RuntimeError`` when the position does not say.
    """
    multiscale = _the_description_of(Path(position))
    axes = [axis.get("name") for axis in multiscale.get("axes", [])]
    for transform in multiscale["datasets"][0].get("coordinateTransformations", []):
        if transform.get("type") == "scale":
            return float(transform["scale"][axes.index("x") if "x" in axes else -1])
    raise RuntimeError(f"the position {position} does not say its pixel size")


def name_of_a_position(kind: str, label: str, format: str) -> str:
    """What a position is called: ``overview_P000001.ome.tif``, say."""
    return f"{kind}_{label}{ENDINGS[format]}"


def is_a_position_name(name: str) -> bool:
    """Whether a name is that of a position, in either format."""
    return name.endswith(ENDINGS["ome-zarr"]) or name.lower().endswith(_TIFF_ENDINGS)


def format_of(path: Path | str) -> str | None:
    """The format a finished position is in, or None when ``path`` is not one.

    An OME-Zarr image is a folder. An OME-TIFF counts only when ZMART's note
    (:data:`ZMART_NOTE`) is inside it, because only the note says where the
    picture lies on the stage, by the same rules an OME-Zarr image follows.
    An OME-TIFF without it, such as one a microscope wrote by itself, does
    not say that in a form ZMART can trust.
    """
    path = Path(path)
    if path.name.endswith(ENDINGS["ome-zarr"]) and path.is_dir():
        return "ome-zarr"
    if path.name.lower().endswith(_TIFF_ENDINGS) and path.is_file():
        if _the_note_in(str(path), *_the_stamp_of(path)):
            return "ome-tiff"
    return None


def is_a_position(path: Path | str) -> bool:
    """Whether ``path`` is a finished position, in either format."""
    return format_of(path) is not None


def _write_a_position(record: dict, into: Path | str, *, format: str) -> Path:
    """One attempt at :func:`position_from_record`."""
    planes = record.get("planes") or []
    if not planes:
        raise RuntimeError("the capture reported no planes, so there is nothing to keep")

    z_model = _the_z_model(record, planes)
    volume, pixel_size_um = _the_volume_of(planes, depth_order=z_model["array_order"])
    frames, channels, nz, ny, nx = volume.shape
    dz = z_model["spacing_um"]
    first_voxel_um = the_first_voxel_centre_of(
        planes, (ny, nx), pixel_size_um, z_origin_um=z_model["lowest_plane_um"],
    )

    into = Path(into)
    into.mkdir(parents=True, exist_ok=True)
    # The store's name leads with the acquisition type, the way the run
    # writers name theirs (``overview_pos00000.ome.zarr``): the viewer reads
    # which stores belong together off the names, and a store named only by
    # its position would stand under a heading of its own. The type is the
    # interface's own, stamped on the record by the bridge from what it asked
    # for; drivers do not report it.
    kind = record.get("acquisition_type") or "capture"
    published = into / name_of_a_position(kind, record["position_label"], format)
    # Written somewhere the viewer is not looking, and moved into place only
    # once every level is filled. The viewer watches ``positions/<type>`` and
    # shows a store the moment its description exists, so a store filled in
    # place was visible while its coarser copies were still empty: the
    # picture asked for a zoomed-out copy, was told there was none, and
    # showed a hole until it happened to ask again. Renaming a finished
    # folder is one step the file system does whole, so the viewer now sees
    # either nothing or the complete store, never something in between.
    store = _a_place_to_write(into, published.name)
    if format == "ome-tiff":
        # The OME-Zarr description is declared as for an OME-Zarr position,
        # without a pixel, and carried into the OME-TIFF as it is: the two
        # formats are placed by the one description, never by two that drift.
        try:
            arrays, description = _declared(store, volume, dz, pixel_size_um, first_voxel_um, z_model)
        finally:
            shutil.rmtree(store.parent, ignore_errors=True)
        return _write_a_tiff(published, _smaller_copies(volume, len(arrays)), description)
    arrays, description = _declared(store, volume, dz, pixel_size_um, first_voxel_um, z_model)

    # Fill the levels from the finest down, keeping every second voxel along
    # y and x — the run stores' own convention, declared in their description.
    for array, copy in zip(arrays, _smaller_copies(volume, len(arrays)), strict=True):
        array[:] = copy
    return _publish(store, published)


def _smaller_copies(volume: np.ndarray, levels: int) -> list[np.ndarray]:
    """The full-size volume and its smaller copies, each the mean of 2 × 2 pixels of the one before."""
    copies = [volume]
    for _ in range(levels - 1):
        copies.append(_mean_downsample_yx(copies[-1]))
    return copies


def _declared(store: Path, volume: np.ndarray, dz: float, pixel_size_um, first_voxel_um, z_model: dict):
    """Declare ``store`` as an OME-Zarr position for ``volume``; return its levels and its attributes.

    The attributes hold the OME-Zarr description (``ome``: ``multiscales``
    and ``omero``) and ZMART's record of how the planes were taken
    (``zmart_microscopy``), exactly as the store keeps them.
    """
    frames, channels, nz, ny, nx = volume.shape
    depth_max = _the_depth_of(volume.dtype)
    tile_shape = (nz, ny, nx)
    arrays = declare_image(
        store,
        canvas_shape=tile_shape,
        frames=frames,
        channels=channels,
        dtype=str(volume.dtype),
        chunk=PIECE,
        levels=how_many_copies_a_position_can_keep(tile_shape, PIECE),
        voxel_size_um=(dz, pixel_size_um[0], pixel_size_um[1]),
        first_voxel_um=first_voxel_um,
        # Each channel opens on a window measured from its own pixels — the
        # pixels are already in hand, so this costs nothing. Declaring the
        # camera's whole range instead is honest but useless on screen: a
        # real acquisition sits in the bottom few per cent of it, and the
        # picture opened very nearly black.
        channel_blocks=[
            Channel(
                f"channel {index}",
                window=_a_window_onto(volume[:, index], depth_max),
            ).described(depth_max)
            for index in range(channels)
        ],
        ome_zarr_version="0.5",
    )
    description_path = store / "zarr.json"
    description = json.loads(description_path.read_text(encoding="utf-8"))
    description.setdefault("attributes", {})["zmart_microscopy"] = {
        "z_coordinate": z_model,
    }
    _describe_mean_pyramid(description)
    description_path.write_text(json.dumps(description, indent=2), encoding="utf-8")
    return arrays, description["attributes"]


def _a_place_to_write(into: Path, name: str) -> Path:
    """A folder beside the acquisition's positions where a store can be built.

    It sits next to the watched folder rather than inside it, so nothing the
    viewer lists can ever be half-written. Its name says what it is, so a
    folder left behind by a crash is recognisable and safe to delete.

    Short, on purpose: Windows counts a path to 260 characters unless told
    otherwise, and a chunk file carries a 40-character suffix while zarr
    writes it. Under a staging folder named after the store, a fine
    focussing stack's chunk ran to 270 and the store was never written.
    The name the store is published under (*name*) is the only long one.
    """
    staging = into.parent / ".writing" / uuid.uuid4().hex[:8]
    staging.mkdir(parents=True, exist_ok=True)
    return staging / "store.zarr"


def _publish(built: Path, published: Path) -> Path:
    """Move a finished store into the watched folder, replacing an older one.

    A rerun writes the same position again. The old store is moved aside
    first and the new one moved in, two renames rather than a slow delete
    with the name missing in between; the old pixels are removed last.
    """
    retired = None
    if published.exists():
        retired = built.parent / f"{published.name}.retired-{uuid.uuid4().hex[:8]}"
        published.rename(retired)
    built.rename(published)
    if retired is not None:
        shutil.rmtree(retired, ignore_errors=True)
    for staging in (built.parent, built.parent.parent):
        try:
            staging.rmdir()  # only succeeds once nothing else is being written
        except OSError:
            pass
    return published


# -- reading what the vendor wrote ------------------------------------------


def _the_volume_of(
    planes: list[dict], depth_order: list[int] | None = None,
) -> tuple[np.ndarray, tuple[float, float]]:
    """The capture as one ``(t, c, z, y, x)`` array, and its (y, x) µm/voxel.

    The vendor may have written one file per plane or one file for the whole
    capture — the record's plane entries say which slot each file (or slice of
    a file) fills, so both arrive the same way here.

    ``depth_order`` is the vendor's z numbers in the order the array should
    hold them — ascending stage z, as :func:`_the_z_model` decides. Without
    it the vendor's own numbering is kept.
    """
    import tifffile

    files: dict[str, tifffile.TiffFile] = {}
    try:
        for plane in planes:
            path = str(plane["path"])
            if path not in files:
                files[path] = tifffile.TiffFile(path)

        first = files[str(planes[0]["path"])]
        pixel_size_um = _the_pixel_size_of(first.ome_metadata or "")

        # The vendor's own numbering is packed down to 0..n-1 per axis: a
        # Leica job numbers its channels from 1, and taking the numbers as
        # array indices left channel 0 an empty black plane.
        frames = _packed(planes, "t")
        channels = _packed(planes, "c")
        depth = (
            {number: index for index, number in enumerate(depth_order)}
            if depth_order is not None else _packed(planes, "z")
        )
        slots = {tuple(int(p.get(axis, 0)) for axis in ("t", "c", "z")) for p in planes}
        if len(slots) != len(planes) or len(slots) != len(frames) * len(channels) * len(depth):
            raise ValueError("A completed position requires exactly one saved plane per T/C/Z slot")

        volume: np.ndarray | None = None
        for plane in planes:
            held = files[str(plane["path"])]
            image = _one_plane_of(held, plane)
            if volume is None:
                volume = np.zeros(
                    (len(frames), len(channels), len(depth), *image.shape),
                    dtype=image.dtype,
                )
            volume[
                frames[int(plane.get("t", 0))],
                channels[int(plane.get("c", 0))],
                depth[int(plane.get("z", 0))],
            ] = image
        assert volume is not None  # planes was checked non-empty above
        return volume, pixel_size_um
    finally:
        for held in files.values():
            held.close()


def _packed(planes: list[dict], axis: str) -> dict[int, int]:
    """The vendor's numbers along one axis, packed down to 0..n-1 in order."""
    seen = sorted({int(p.get(axis, 0)) for p in planes})
    return {number: index for index, number in enumerate(seen)}


def _one_plane_of(held, plane: dict) -> np.ndarray:
    """One y/x image out of a vendor file, whichever axes the file declares."""
    series = held.series[0]
    axes = series.axes.upper()
    data = series.asarray()
    if axes == "YX":
        return data
    # Everything before the trailing YX is indexed by the record's own
    # numbers; an axis the record does not speak of would be silently
    # mis-sliced, so it is refused by name instead.
    if not axes.endswith("YX"):
        raise RuntimeError(f"the vendor file's axes are {axes!r}, which do not end in YX")
    taken = {"T": int(plane.get("t", 0)), "C": int(plane.get("c", 0)), "Z": int(plane.get("z", 0))}
    index = []
    for axis in axes[:-2]:
        if axis not in taken:
            raise RuntimeError(
                f"the vendor file declares a {axis!r} axis the record says nothing about"
            )
        index.append(taken[axis])
    return data[tuple(index)]


def _the_pixel_size_of(ome_xml: str) -> tuple[float, float]:
    """The (y, x) µm per voxel, read from the vendor's own OME description.

    A file that says nothing gets 1 µm — honest enough to draw, and plainly
    wrong enough to notice — rather than a refusal that would cost the pixels.
    """

    def one(name: str) -> float:
        size = re.search(rf'PhysicalSize{name}="([^"]+)"', ome_xml)
        if not size:
            return 1.0
        unit = re.search(rf'PhysicalSize{name}Unit="([^"]+)"', ome_xml)
        return float(size.group(1)) * _TO_UM.get(unit.group(1) if unit else "", 1.0)

    return one("Y"), one("X")


def _the_z_model(record: dict, planes: list[dict]) -> dict:
    """Where the capture stands in z, in specimen space.

    Every store is placed in specimen coordinates in all three axes -- the
    frame the driver drives in, x and y from the origin on the carrier and z
    the height above the coverslip face, physical up on every stand:
    ``scale`` is the size of a voxel and is always positive, and
    ``translation`` is where the centre of the first voxel sits, positive or
    negative as the stamps say. A flat capture retains its measured height;
    placing it on a shared display plane belongs to the viewer aggregate.
    A stack is written **ascending**: its lowest plane first, and the rest above it at
    the spacing it was acquired with. Which way the drive swept is not the
    store's business: a downward sweep is reversed on the way in, and the
    two stores that result are
    indistinguishable. The sweep as it happened is kept beside, as
    provenance, for anyone who wants the story rather than the picture.

    Why not keep the sign: a negative ``scale`` is not an OME-Zarr transform.
    neuroglancer refuses it outright ("Expected positive finite
    floating-point number"), and one refused layer nulls the scene's shared
    depth, which blanked a perfectly good overview beside it.

    Returns the array order (vendor z numbers, ascending specimen z), the
    positive spacing, the lowest plane's specimen z, and the provenance.
    """
    numbered = sorted({int(plane.get("z", 0)) for plane in planes})
    centres: list[float | None] = []
    for number in numbered:
        found = [
            float(plane["z_um"])
            for plane in planes
            if int(plane.get("z", 0)) == number
            and plane.get("z_um") is not None
            and math.isfinite(float(plane["z_um"]))
        ]
        centres.append(float(np.median(found)) if found else None)

    requested = record.get("requested_position_um") or record.get("position") or {}
    requested_z = requested.get("z") if isinstance(requested, dict) else None
    if requested_z is not None:
        requested_z = float(requested_z)
        if not math.isfinite(requested_z):
            requested_z = None

    known = [(centre, number) for centre, number in zip(centres, numbered, strict=True) if centre is not None]
    if not known and len(numbered) > 1:
        # A stack with no height on any plane has no stage z to stand at and
        # no spacing: a store made up for it would stand at z 0, one
        # micrometre a plane, and draw as if that were true.
        raise RuntimeError(
            "the capture's planes report no stage z, so the stack cannot be placed"
        )
    if known:
        # Ascending stage z; a plane whose height is unknown keeps its vendor
        # place after the known ones, so nothing is invented for it.
        ascending = [number for _centre, number in sorted(known)]
        ascending += [number for centre, number in zip(centres, numbered, strict=True) if centre is None]
        heights = sorted(centre for centre, _number in known)
        lowest = heights[0]
    else:
        # One flat plane with no height: the requested focus is the only
        # account there is of where it was taken, and the stage origin
        # failing that.
        ascending = list(numbered)
        heights = []
        lowest = requested_z if requested_z is not None else 0.0

    steps = [b - a for a, b in zip(heights, heights[1:], strict=False)]
    spacing = abs(float(np.median(steps))) if steps else 1.0
    if not math.isfinite(spacing) or spacing == 0:
        spacing = 1.0

    if len(numbered) == 1:
        sweep = "single-plane"
    elif len(known) < 2:
        sweep = "unknown"
    else:
        first, last = known[0][0], known[-1][0]
        sweep = "increasing" if last >= first else "decreasing"

    return {
        "model": "zmart-microscopy-specimen-z-v1",
        "frame": "specimen",
        "array_order": ascending,
        "spacing_um": spacing,
        "lowest_plane_um": float(lowest),
        "unit": "micrometer",
        "acquisition_provenance": {
            "plane_order_as_acquired": numbered,
            "plane_centres_um": centres,
            "sweep_direction": sweep,
            "requested_stage_focus_z_um": requested_z,
            "unit": "micrometer",
        },
    }


def the_first_voxel_centre_of(
    planes: list[dict],
    frame_yx: tuple[int, int],
    pixel_size_um: tuple[float, float],
    *,
    z_origin_um: float,
) -> tuple[float, float, float]:
    """Where the centre of the store's first voxel sits on the stage, in (z, y, x) µm.

    The record's stage point is the centre of the frame, and ``n`` pixels
    across put the first pixel's centre ``(n - 1) / 2`` pixels before it.

    The z origin was decided once by :func:`_the_z_model`: the specimen z
    of the lowest plane, so a store's z is the specimen's like its x and y.
    A plane that does not say where it was taken is refused: placed at the
    stage's zero, it showed in the corner of the canvas as if taken there.
    """
    for axis in ("x_um", "y_um"):
        if planes[0].get(axis) is None:
            raise ValueError(
                f"the capture does not say where it was taken (its first plane has no {axis}), "
                "so it cannot be placed on the stage"
            )
    x_um = float(planes[0]["x_um"])
    y_um = float(planes[0]["y_um"])
    return (
        z_origin_um,
        y_um - (frame_yx[0] - 1) * pixel_size_um[0] / 2.0,
        x_um - (frame_yx[1] - 1) * pixel_size_um[1] / 2.0,
    )


def _a_window_onto(channel: np.ndarray, depth_max: int) -> tuple[int, int]:
    """The brightness range this channel should first be shown with.

    The darkest percentile to just past the brightest, so a stray hot pixel
    cannot stretch the window and flatten everything else. A channel with
    nothing in it (all one value) falls back to the camera's whole range —
    a degenerate window is refused by readers.
    """
    low, high = np.percentile(channel, [1.0, 99.9])
    low, high = int(low), int(np.ceil(high))
    if high <= low:
        return (0, depth_max)
    return (low, min(high, depth_max))


def _mean_downsample_yx(values: np.ndarray) -> np.ndarray:
    """Average adjacent 2 × 2 pixels while preserving the camera dtype."""
    height = (values.shape[-2] // 2) * 2
    width = (values.shape[-1] // 2) * 2
    blocks = values[..., :height, :width].reshape(
        *values.shape[:-2], height // 2, 2, width // 2, 2
    )
    averaged = blocks.mean(axis=(-3, -1), dtype=np.float32)
    if np.issubdtype(values.dtype, np.integer):
        averaged = np.rint(averaged)
    return averaged.astype(values.dtype, copy=False)


def _describe_mean_pyramid(description: dict) -> None:
    """Say truthfully how the position's reduced-resolution copies were made."""
    multiscales = description.get("attributes", {}).get("ome", {}).get("multiscales", [])
    for multiscale in multiscales:
        multiscale["type"] = "mean"
        multiscale["metadata"] = {
            "description": "Each y/x level is the mean of adjacent 2 by 2 pixels.",
            "method": "2x2-mean",
        }


def _the_depth_of(dtype: np.dtype) -> int:
    """The brightest value the dtype can hold, for the channel description."""
    try:
        return int(np.iinfo(dtype).max)
    except ValueError:
        return 65535


# -- OME-TIFF positions ---------------------------------------------------------


def write_a_projection(position: Path | str, into: Path | str) -> Path:
    """Write the maximum projection over z of an OME-TIFF position, and return it.

    The projection lands in ``into`` under the position's own name, as an
    OME-TIFF of one plane per channel. It lies where the position lies, with
    its channels' display, so a person opens it to see a stack at a glance and
    the viewer shows it as the run's projection. (For OME-Zarr runs the
    viewer makes its projections itself.)
    """
    import tifffile

    position = Path(position)
    with tifffile.TiffFile(position) as tif:
        series = tif.series[0]
        volume = _in_five_axes(series.asarray(), series.axes)
    note = _the_note_in(str(position), *_the_stamp_of(position))
    attributes = {
        "ome": {
            "multiscales": json.loads(note["multiscales"]),
            **({"omero": json.loads(note["omero"])} if note.get("omero") else {}),
        }
    }
    flat = volume.max(axis=2, keepdims=True)
    multiscale = attributes["ome"]["multiscales"][0]
    return _write_a_tiff(
        Path(into) / position.name, _smaller_copies(flat, len(multiscale["datasets"])), attributes
    )


def _write_a_tiff(published: Path, copies: list[np.ndarray], attributes: dict) -> Path:
    """Write ``copies`` (the full size first, each t, c, z, y, x) as one OME-TIFF at ``published``.

    ``attributes`` are the OME-Zarr position's own (``ome`` and, for a stack,
    ``zmart_microscopy``); they go into ZMART's note unchanged, so the file is
    placed exactly as the OME-Zarr twin would be. The smaller copies are kept
    inside the file as sub-images of each plane, where Fiji, QuPath and napari
    look for them. The file is written under a temporary name beside its place
    and moved there in one step, so the viewer never finds it half-written.
    """
    import tifffile

    volume = copies[0]
    planes = [copy.reshape(-1, *copy.shape[-2:]) for copy in copies]
    described = _ome_xml(published.name, volume, attributes)
    options = {
        "tile": (PIECE, PIECE),
        "photometric": "minisblack",
        "compression": "zlib",
        "compressionargs": {"level": _DEFLATE_LEVEL},
        "metadata": None,
    }
    published.parent.mkdir(parents=True, exist_ok=True)
    staging = published.with_name(f".{published.name}.{uuid.uuid4().hex[:8]}.writing")
    try:
        # A classic TIFF cannot be larger than 4 GB; the larger kind can.
        with tifffile.TiffWriter(staging, bigtiff=volume.nbytes >= 2**31) as tif:
            for index, plane in enumerate(planes[0]):
                tif.write(
                    plane,
                    subifds=len(copies) - 1,
                    description=described if index == 0 else None,
                    **options,
                )
                for smaller in planes[1:]:
                    tif.write(smaller[index], subfiletype=1, **options)
        os.replace(staging, published)
    finally:
        staging.unlink(missing_ok=True)
    return published


def _ome_xml(name: str, volume: np.ndarray, attributes: dict) -> bytes:
    """The OME-XML description of one position, with ZMART's note in it.

    The standard part says what any OME reader needs: the pixel size, each
    channel's name and colour, and every plane's height. Planes are stored
    with z changing fastest, then the channel, then time
    (``DimensionOrder="XYZCT"``). No ``PositionX`` or ``PositionY`` is written:
    the position is placed by the note's OME-Zarr description.
    """
    frames, channels, depth, height, width = volume.shape
    ome = attributes["ome"]
    multiscale = ome["multiscales"][0]
    scale, translation = (
        next(t[kind] for t in multiscale["datasets"][0]["coordinateTransformations"] if t["type"] == kind)
        for kind in ("scale", "translation")
    )
    dz, dy, dx = scale[-3:]
    z0 = translation[-3]
    kind = {"float32": "float", "float64": "double"}.get(volume.dtype.name, volume.dtype.name)
    blocks = (ome.get("omero") or {}).get("channels") or []
    channel_elements = "".join(
        f'<Channel ID="Channel:0:{index}" Name={quoteattr(str(block.get("label") or ""))}'
        + (f' Color="{_ome_colour_of(block["color"])}"' if block.get("color") else "")
        + ' SamplesPerPixel="1"/>'
        for index, block in enumerate(blocks[:channels])
    ) or "".join(f'<Channel ID="Channel:0:{c}" SamplesPerPixel="1"/>' for c in range(channels))
    plane_elements = "".join(
        f'<Plane TheT="{t}" TheC="{c}" TheZ="{z}" PositionZ="{z0 + z * dz}" PositionZUnit="µm"/>'
        for t in range(frames)
        for c in range(channels)
        for z in range(depth)
    )
    note = {"multiscales": json.dumps(ome["multiscales"], sort_keys=True)}
    if ome.get("omero"):
        note["omero"] = json.dumps(ome["omero"], sort_keys=True)
    if attributes.get("zmart_microscopy"):
        note["zmart_microscopy"] = json.dumps(attributes["zmart_microscopy"], sort_keys=True)
    entries = "".join(f"<M K={quoteattr(key)}>{escape(value)}</M>" for key, value in note.items())
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06" Creator="ZMART interface">'
        f'<Image ID="Image:0" Name={quoteattr(name)}>'
        f'<Pixels ID="Pixels:0" DimensionOrder="XYZCT" Type="{kind}" '
        f'SizeX="{width}" SizeY="{height}" SizeZ="{depth}" SizeC="{channels}" SizeT="{frames}" '
        f'PhysicalSizeX="{dx}" PhysicalSizeXUnit="µm" PhysicalSizeY="{dy}" PhysicalSizeYUnit="µm" '
        f'PhysicalSizeZ="{dz}" PhysicalSizeZUnit="µm">'
        f"{channel_elements}"
        f'<TiffData PlaneCount="{frames * channels * depth}"/>'
        f"{plane_elements}"
        "</Pixels>"
        '<AnnotationRef ID="Annotation:0"/>'
        "</Image>"
        f'<StructuredAnnotations><MapAnnotation ID="Annotation:0" Namespace="{ZMART_NOTE}">'
        f"<Value>{entries}</Value></MapAnnotation></StructuredAnnotations>"
        "</OME>"
    ).encode()


def _the_description_of(position: Path) -> dict:
    """A position's OME-Zarr description of its levels (one ``multiscales`` entry).

    Both formats answer from it: an OME-Zarr image from its own
    ``zarr.json``, an OME-TIFF from ZMART's note. Raises ``RuntimeError``
    when the position carries none.
    """
    if position.name.lower().endswith(_TIFF_ENDINGS):
        described = _the_note_in(str(position), *_the_stamp_of(position)).get("multiscales")
        multiscales = json.loads(described) if described else []
    else:
        attributes = json.loads((position / "zarr.json").read_text(encoding="utf-8")).get("attributes", {})
        multiscales = (attributes.get("ome") or attributes).get("multiscales") or []
    if not multiscales or not multiscales[0].get("datasets"):
        raise RuntimeError(f"the position {position} carries no description of its pixels")
    return multiscales[0]


def _the_stamp_of(path: Path) -> tuple[int, int]:
    """When a file was last written, and its size: a replaced file differs in one."""
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


@lru_cache(maxsize=4096)
def _the_note_in(path: str, written_ns: int, size: int) -> dict:
    """ZMART's note inside an OME-TIFF, or an empty one. Remembered while the
    file is unchanged: the time it was written and its size are part of the key."""
    import tifffile

    del written_ns, size  # only part of the key
    try:
        with tifffile.TiffFile(path) as tif:
            root = ElementTree.fromstring(tif.ome_metadata or "<OME/>")
    except (OSError, ValueError, ElementTree.ParseError, tifffile.TiffFileError):
        return {}
    for note in root.iter():
        if note.tag.endswith("}MapAnnotation") and note.get("Namespace") == ZMART_NOTE:
            return {entry.get("K"): entry.text or "" for entry in note.iter() if entry.tag.endswith("}M")}
    return {}


def _in_five_axes(held: np.ndarray, axes: str) -> np.ndarray:
    """An array in the file's own axis order, given as (t, c, z, y, x)."""
    order = [axes.index(axis) for axis in "TCZYX" if axis in axes]
    held = np.transpose(held, order)
    present = [axis for axis in "TCZYX" if axis in axes]
    return held.reshape([held.shape[present.index(axis)] if axis in present else 1 for axis in "TCZYX"])


def _ome_colour_of(hex_colour: str) -> int:
    """``RRGGBB`` as OME-XML writes a colour: one signed number holding red, green, blue and alpha."""
    value = int(hex_colour.lstrip("#")[:6], 16) << 8 | 0xFF
    return value - (1 << 32) if value >= 1 << 31 else value

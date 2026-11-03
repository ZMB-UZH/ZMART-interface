"""Where an experiment's files go: its folder, and one folder per run of each step.

The workflow owns the experiment folder and the folders inside it, and gives
a driver the folder to save each capture in. Inside that folder the driver
owns the layout and the file names, and returns the files it saved; this
module only files those a driver saved in a place of its own, keeping the
layout and the names it gave them.

Every time a step acquires again -- the first time, a rerun, or after an
interrupt -- it gets a folder of its own, ``run_01``, ``run_02``, ..., inside
the folder of what it acquires::

    <experiment>_<hash>/
      overview/run_01/              the overview scan
      targets/run_01/               the targets
      focussing/overview/run_01/    the focus map the overview is scanned with
      focussing/targets/run_01/     each target's own focus stack

Nothing of an earlier run is overwritten or deleted, and the canvas shows the
newest run of each. Each run folder holds ``attempt.json``: when it started,
when and how it ended, and the settings it ran with.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

_NAME_RE = re.compile(r"^[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*$")
_HASH_RE = re.compile(r"^[0-9a-z]{6}$")
_CREATE_ATTEMPTS = 16


def checked_name(value: str, *, field: str) -> str:
    """``value`` itself, when it can safely become one folder name; otherwise a ValueError.

    Letters and digits, joined by single ``-`` or ``_``. Such a name can never
    be a path: it has no slash, no backslash, no drive letter and no ``..``,
    so a folder made from it always stays inside the folder it is joined
    onto. Names that arrive from the page are checked with this before they
    reach the disk, because some of them decide what is deleted.
    """
    if not isinstance(value, str) or not _NAME_RE.fullmatch(value):
        raise ValueError(
            f"the {field} {value!r} cannot be used as a folder name; it may hold only letters "
            "and digits, joined by single '-' or '_'"
        )
    return value


def _validate_hash(value: str) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise ValueError(f"hash6 must be exactly 6 lowercase base36 characters, got {value!r}")
    return value


def _new_hash() -> str:
    return uuid.uuid4().hex[:6]


def _create_hashed_dir(parent: Path, name: str, hash6: str | None) -> tuple[str, Path]:
    parent.mkdir(parents=True, exist_ok=True)
    if hash6 is not None:
        value = _validate_hash(hash6)
        path = parent / f"{name}_{value}"
        path.mkdir(parents=False, exist_ok=False)
        return value, path

    for _ in range(_CREATE_ATTEMPTS):
        value = _new_hash()
        path = parent / f"{name}_{value}"
        try:
            path.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            continue
        return value, path
    raise RuntimeError(f"could not allocate a unique output directory for {name!r} under {parent}")


def prepare_experiment(output_root: Any, experiment: str, *, hash6: str | None = None) -> Path:
    """Create and return ``<output_root>/<experiment>_<hash6>``."""

    name = checked_name(experiment, field="experiment")
    _hash, path = _create_hashed_dir(Path(output_root).expanduser().resolve(), name, hash6)
    return path


#: Where each kind of acquisition keeps its runs, inside the experiment folder.
#: Focussing is one folder, split by what it focusses for: the focus map the
#: overview is scanned with, and each target's own stack. Any other kind keeps
#: its runs in a folder of its own name.
WHERE_RUNS_GO = {
    "focussing": ("focussing", "overview"),
    "target-focussing": ("focussing", "targets"),
}

#: The runs that the target focussing goes with: a target focussing run takes
#: the number of the targets run it was taken for.
RUNS_TAKEN_WITH = {"target-focussing": "targets"}

#: What each run folder is called: ``run_`` and its number, two digits, so
#: that ``run_10`` sorts after ``run_09`` in a file browser.
RUN_NAME = re.compile(r"^run_(\d{2,})$")

#: The run each kind of acquisition is on now, per experiment folder.
_current_runs: dict[tuple[str, str], Path] = {}


def runs_folder_of(experiment_root: Any, acquisition_type: str) -> Path:
    """``<experiment>/<where this kind keeps its runs>``: the folder holding its ``run_NN`` folders."""
    kind = checked_name(acquisition_type, field="acquisition_type")
    return Path(experiment_root).joinpath(*WHERE_RUNS_GO.get(kind, (kind,)))


def start_a_run(experiment_root: Any, acquisition_type: str, *, settings: Any = None) -> Path:
    """Begin the next run of this kind: create ``run_NN`` and make it the current one.

    The number is one above the highest already in the folder, so an earlier
    run is never written into again. A target focussing run takes the number
    of the targets run it goes with. ``settings`` is what the run was started
    with; it is kept in the run's ``attempt.json``.
    """
    holder = runs_folder_of(experiment_root, acquisition_type)
    holder.mkdir(parents=True, exist_ok=True)
    paired = RUNS_TAKEN_WITH.get(acquisition_type)
    number = None
    if paired is not None:
        partner = _current_runs.get((str(experiment_root), paired))
        found = RUN_NAME.fullmatch(partner.name) if partner is not None else None
        number = int(found.group(1)) if found else None
    if number is None or (holder / f"run_{number:02d}").exists():
        taken = [int(found.group(1)) for child in holder.iterdir()
                 if child.is_dir() and (found := RUN_NAME.fullmatch(child.name))]
        number = max(taken, default=0) + 1
    folder = holder / f"run_{number:02d}"
    folder.mkdir()
    _write_attempt(folder, {
        "acquisition_type": acquisition_type,
        "run": folder.name,
        "started": _now(),
        "ended": None,
        "how_it_ended": None,
        "settings": settings,
    })
    _current_runs[(str(experiment_root), acquisition_type)] = folder
    return folder


def current_run(experiment_root: Any, acquisition_type: str) -> Path | None:
    """The run this kind is on now, or None before its first run began."""
    return _current_runs.get((str(experiment_root), checked_name(acquisition_type, field="acquisition_type")))


def end_a_run(experiment_root: Any, acquisition_type: str, how: str) -> None:
    """Say in the current run's ``attempt.json`` that it ended, and how: ``finished``, ``stopped`` or ``failed``.

    A run that is changed afterwards -- one point measured again, one target
    taken again -- is ended again, and the record says when it last ended.
    """
    folder = current_run(experiment_root, acquisition_type)
    if folder is None:
        return
    said = _read_attempt(folder)
    said.update(ended=_now(), how_it_ended=how)
    _write_attempt(folder, said)


def prepare_acquisition(experiment_root: Any, acquisition_type: str) -> Path:
    """The folder a driver saves this kind's captures in: its current run, created when there is none.

    A capture asked for before its step started a run (a script, a single
    test capture) lands in a first run of its own, never loose in the
    experiment folder.
    """
    folder = current_run(experiment_root, acquisition_type)
    if folder is None or not folder.is_dir():
        folder = start_a_run(experiment_root, acquisition_type)
    return folder


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _read_attempt(folder: Path) -> dict:
    try:
        return json.loads((folder / "attempt.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"run": folder.name}


def _write_attempt(folder: Path, said: dict) -> None:
    # Written beside and moved into place in one step, so a reader never finds half a file.
    writing = folder / f".attempt.{uuid.uuid4().hex[:8]}.json"
    writing.write_text(json.dumps(said, indent=2, default=str), encoding="utf-8")
    os.replace(writing, folder / "attempt.json")


def run_hash(run: Any) -> str:
    """The hash of a run folder ``<experiment>_<hash6>``: what tells this run's files from another's."""
    return _validate_hash(Path(run).name.rsplit("_", 1)[-1])


def free_name(folder: Any, stem: str, ending: str) -> Path:
    """``folder/<stem><ending>``, or ``<stem>_001<ending>``, ...: the first no earlier file took.

    What the interface writes about a capture -- its focus curve, the objects
    found in it -- is named after the capture's acquisition type and label. A
    position taken again keeps its label, so what is written about it takes
    the next free name, and what was said about the earlier capture stays.
    The captures themselves are the driver's to name: it never overwrites an
    earlier file (the controller's contract).
    """
    folder = Path(folder)
    candidate, number = stem, 0
    while (folder / f"{candidate}{ending}").exists():
        number += 1
        candidate = f"{stem}_{number:03d}"
    return folder / f"{candidate}{ending}"


def position_label(
    position: int,
    *,
    carrier: int = 0,
    compartment: int = 0,
    group: int = 0,
    view: int = 0,
) -> str:
    """Return the canonical workflow location label (time/channel/z are planes)."""

    fields = {
        "carrier": (carrier, 2),
        "compartment": (compartment, 6),
        "group": (group, 6),
        "position": (position, 6),
        "view": (view, 2),
    }
    for name, (value, width) in fields.items():
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 10**width:
            raise ValueError(f"{name} must be a whole number from 0 through {10**width - 1}")
    return f"K{carrier:02d}_M{compartment:06d}_G{group:06d}_P{position:06d}_V{view:02d}"


def move_record_images(record: dict, acquisition: Any) -> dict:
    """File every file a capture saved in the run, unchanged, and update the record's paths.

    ``files`` is where the driver lists every file it saved, the name the
    ZMART Controller's contract fixes so the interface finds the pictures on
    any microscope. Every file a plane names must be one of them, so that the
    record can never disagree with itself about what was saved.

    The layout is the driver's. A driver given the *acquisition* folder saves
    straight into it, in folders of its own (the Leica keeps its stores in
    ``data``, its projections and its log beside it), so its files are
    already where they belong and stay there. A driver whose software saves
    in a place of its own has its files moved into *acquisition*, keeping the
    layout they have under their common folder.

    Every source and destination is checked before the first move. If a later
    move fails, the files already moved go back where they were, so one
    capture is never left half in staging and half in the run.
    """

    files = record.get("files")
    if not isinstance(files, list) or not files:
        raise RuntimeError(
            "the acquisition listed no files: a driver must name every file it saved under 'files'"
        )
    sources = list(dict.fromkeys(Path(value) for value in files))
    named = [plane["path"] for plane in record.get("planes", [])]
    unlisted = [value for value in named if Path(value) not in sources]
    if unlisted:
        raise RuntimeError(f"the capture names {unlisted}, not among the files it saved")

    destination = Path(acquisition)
    if all(source.resolve().is_relative_to(destination.resolve()) for source in sources):
        saved_in = destination
    else:
        saved_in = Path(os.path.commonpath([source.parent for source in sources]))
    filed = [(source, destination / source.relative_to(saved_in)) for source in sources]
    targets = [target for _, target in filed]
    if len(targets) != len(set(targets)):
        raise RuntimeError("acquire returned different files with the same filename")
    for source, _ in filed:
        if not source.exists():
            raise FileNotFoundError(f"acquired file does not exist: {source}")
    moves = [(source, target) for source, target in filed if source.resolve() != target.resolve()]
    for _, target in moves:
        if target.exists():
            raise FileExistsError(f"refusing to replace an existing acquisition file: {target}")

    moved: list[tuple[Path, Path]] = []
    try:
        for source, target in moves:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            moved.append((source, target))
    except Exception:
        for source, target in reversed(moved):
            if target.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target), str(source))
        raise

    mapped = {source: str(target) for source, target in filed}
    record["files"] = [mapped[source] for source in sources]
    for plane in record.get("planes", []):
        plane["path"] = mapped[Path(plane["path"])]
    return record

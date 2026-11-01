"""Finding the analysis pipelines: named by the environment, or beside the installed engine."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from . import workflows


@pytest.fixture(autouse=True)
def _forget_what_was_loaded():
    workflows.step_module.cache_clear()
    yield
    workflows.step_module.cache_clear()


def _a_checkout(root, folder="examples"):
    (root / folder / "focus" / "pipelines").mkdir(parents=True)
    (root / folder / "focus" / "pipelines" / "focus.yaml").write_text("steps: []\n")
    (root / folder / "object_analysis" / "steps").mkdir(parents=True)
    (root / folder / "object_analysis" / "steps" / "read_images.py").write_text("WHERE = 'the checkout'\n")
    return root


@pytest.mark.parametrize("folder", ["examples", "workflows"])
def test_the_environment_variable_names_the_checkout_or_its_folder_of_pipelines(tmp_path, monkeypatch, folder):
    """ZMART-analysis keeps them in ``examples`` from 0.6.0rc8 on, and in ``workflows`` before."""
    checkout = _a_checkout(tmp_path / "ZMART-analysis", folder)
    monkeypatch.setenv(workflows.ENV, str(checkout))
    assert workflows.workflows_root() == (checkout / folder).resolve()
    monkeypatch.setenv(workflows.ENV, str(checkout / folder))
    assert workflows.workflows_root() == (checkout / folder).resolve()
    assert workflows.pipeline_yaml("focus").name == "focus.yaml"
    assert workflows.step_module("object_analysis", "read_images").WHERE == "the checkout"


def test_a_folder_without_workflows_is_said_plainly(tmp_path, monkeypatch):
    monkeypatch.setenv(workflows.ENV, str(tmp_path))
    with pytest.raises(workflows.WorkflowsNotFound, match="holds no analysis pipelines"):
        workflows.workflows_root()


def test_without_the_variable_the_workflows_beside_the_engine_are_used(monkeypatch):
    """An editable install of a ZMART-analysis checkout is found without the variable.

    Installed as a plain package (as on GitHub's machines) the workflows are not
    beside the engine at all, so there is nothing for this test to find.
    """
    monkeypatch.delenv(workflows.ENV, raising=False)
    spec = importlib.util.find_spec("zmart_analysis")
    beside = Path(spec.origin).resolve().parent.parent if spec else None
    if beside is None or not any((beside / name).is_dir() for name in workflows.FOLDER_NAMES):
        pytest.skip("ZMART-analysis is installed as a package here, not as a checkout")
    root = workflows.workflows_root()
    assert root.name in workflows.FOLDER_NAMES
    # The pipelines the interface runs: focus, detection both ways, and the plots.
    for name in ("focus", "object_analysis_cellpose", "object_analysis_watershed", "reduce_dimensions"):
        assert workflows.pipeline_yaml(name).is_file(), name
    assert callable(workflows.step_module("object_analysis", "read_images").load_plane)
    with pytest.raises(FileNotFoundError, match="no workflow under"):
        workflows.pipeline_yaml("no_such_pipeline")

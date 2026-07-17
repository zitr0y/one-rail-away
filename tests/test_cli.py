"""Stage selection for `ose all --from <stage>`."""

import pytest

from pipeline.cli import stages_from


def test_default_start_runs_full_pipeline():
    assert stages_from("fetch") == ["fetch", "build", "compute"]


def test_mid_pipeline_start_runs_remaining_stages():
    assert stages_from("build") == ["build", "compute"]


def test_last_stage_runs_alone():
    assert stages_from("compute") == ["compute"]


def test_removed_paths_stage_rejected():
    # The OSM paths stage was deleted 2026-07-17 (smoothed line trees, backlog I).
    with pytest.raises(ValueError):
        stages_from("paths")


def test_unknown_stage_rejected():
    with pytest.raises(ValueError):
        stages_from("frobnicate")

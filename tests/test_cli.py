"""Stage selection for `ose all --from <stage>`."""

import pytest

from pipeline.cli import stages_from


def test_default_start_runs_full_pipeline():
    assert stages_from("fetch") == ["fetch", "build", "compute", "paths"]


def test_mid_pipeline_start_runs_remaining_stages():
    assert stages_from("compute") == ["compute", "paths"]


def test_last_stage_runs_alone():
    assert stages_from("paths") == ["paths"]


def test_unknown_stage_rejected():
    with pytest.raises(ValueError):
        stages_from("frobnicate")

"""Tests for the project-level model (Delta T min and stream list)."""

import pytest

from backend.project import ProjectValidationError, TotalSiteProfile
from backend.streams import Stream


def test_delta_t_min_defaults_to_zero():
    assert TotalSiteProfile().delta_t_min == 0.0


def test_delta_t_min_can_be_set():
    assert TotalSiteProfile(delta_t_min=10.0).delta_t_min == 10.0


def test_negative_delta_t_min_rejected():
    with pytest.raises(ProjectValidationError):
        TotalSiteProfile(delta_t_min=-1.0)


def test_non_numeric_delta_t_min_rejected():
    with pytest.raises(ProjectValidationError):
        TotalSiteProfile(delta_t_min="ten")


def test_add_remove_clear_streams():
    tsp = TotalSiteProfile()
    s1 = Stream(tin=100.0, tout=40.0, energy=600.0)
    s2 = Stream(tin=25.0, tout=85.0, cp=2.5)

    tsp.add_stream(s1)
    tsp.add_stream(s2)
    assert len(tsp) == 2

    tsp.remove_stream(s1)
    assert len(tsp) == 1
    assert tsp.streams == [s2]

    tsp.clear_streams()
    assert len(tsp) == 0


def test_removing_missing_stream_raises():
    tsp = TotalSiteProfile()
    with pytest.raises(ValueError):
        tsp.remove_stream(Stream(tin=100.0, tout=40.0, energy=600.0))

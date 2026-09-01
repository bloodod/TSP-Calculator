"""Tests for saving and loading the problem data."""

import json

import pytest

from backend import (
    Stream,
    TotalSiteProfile,
    UtilityStream,
    load_profile,
    save_profile,
)


def _sample_tsp() -> TotalSiteProfile:
    tsp = TotalSiteProfile(delta_t_min=10.0)
    tsp.add_stream(Stream(name="H1", tin=200, tout=50, cp=10))
    tsp.add_stream(Stream(name="C1", tin=10, tout=100, energy=900))
    tsp.add_utility_stream(UtilityStream(name="a", temperature=25.0))
    tsp.add_utility_stream(UtilityStream(name="g", temperature=350.0))
    return tsp


def test_save_load_round_trip(tmp_path):
    path = tmp_path / "problem.json"
    save_profile(_sample_tsp(), path)
    loaded = load_profile(path)

    assert [s.name for s in loaded.streams] == ["H1", "C1"]
    h1 = loaded.streams[0]
    assert h1.tin == 200.0
    assert h1.tout == 50.0
    assert h1.cp == 10.0
    assert h1.energy is None  # cp was the given input
    c1 = loaded.streams[1]
    assert c1.energy == 900.0
    assert c1.cp is None  # energy was the given input
    assert c1.heat_capacity_flow == pytest.approx(10.0)

    assert [(u.name, u.temperature) for u in loaded.utility_streams] == [
        ("a", 25.0),
        ("g", 350.0),
    ]
    # Only streams and utility streams are persisted for now.
    assert loaded.delta_t_min == 0.0


def test_save_writes_json_structure(tmp_path):
    path = tmp_path / "p.json"
    save_profile(_sample_tsp(), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {"streams", "utility_streams"}
    assert len(data["streams"]) == 2
    assert len(data["utility_streams"]) == 2
    assert data["streams"][0]["cp"] == 10.0
    assert data["streams"][0]["energy"] is None


def test_load_missing_file(tmp_path):
    with pytest.raises(OSError):
        load_profile(tmp_path / "nope.json")


def test_load_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_profile(path)


def test_load_invalid_stream_data(tmp_path):
    path = tmp_path / "bad_stream.json"
    path.write_text(
        json.dumps({"streams": [{"name": "X", "tin": 100, "tout": 100}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_profile(path)

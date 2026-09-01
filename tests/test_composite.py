"""Tests for composite curve construction."""

import pytest

from backend import (
    Stream,
    StreamKind,
    build_composite,
    build_gcc,
    build_tsp_curves,
    build_utility_targets,
    enthalpy_at,
)


def test_single_hot_stream():
    curve = build_composite([Stream(tin=100, tout=40, cp=10)], StreamKind.HOT)
    # Starts at the lowest temperature with Q = 0, ends at the highest.
    assert curve.temperatures == (40.0, 100.0)
    assert curve.enthalpy == (0.0, 600.0)
    assert curve.total_enthalpy == pytest.approx(600.0)


def test_single_cold_stream():
    curve = build_composite([Stream(tin=25, tout=85, cp=2.5)], StreamKind.COLD)
    assert curve.temperatures == (25.0, 85.0)
    assert curve.enthalpy == (0.0, 150.0)
    assert curve.total_enthalpy == pytest.approx(150.0)


def test_two_hot_streams_with_overlapping_ranges():
    h1 = Stream(tin=100, tout=40, cp=10)
    h2 = Stream(tin=80, tout=60, cp=5)
    curve = build_composite([h1, h2], StreamKind.HOT)
    # (40-60): only h1 -> 10*20 = 200
    # (60-80): h1 + h2 -> 15*20 = 300
    # (80-100): only h1 -> 10*20 = 200
    assert curve.temperatures == (40.0, 60.0, 80.0, 100.0)
    assert curve.enthalpy == (0.0, 200.0, 500.0, 700.0)
    assert curve.total_enthalpy == pytest.approx(700.0)


def test_two_cold_streams_with_overlapping_ranges():
    c1 = Stream(tin=25, tout=85, cp=2.0)
    c2 = Stream(tin=60, tout=100, cp=3.0)
    curve = build_composite([c1, c2], StreamKind.COLD)
    # (25-60): only c1 -> 2*35 = 70
    # (60-85): c1 + c2 -> 5*25 = 125
    # (85-100): only c2 -> 3*15 = 45
    assert curve.temperatures == (25.0, 60.0, 85.0, 100.0)
    assert curve.enthalpy == (0.0, 70.0, 195.0, 240.0)


def test_only_matching_kind_contributes():
    hot = Stream(tin=100, tout=40, cp=10)
    cold = Stream(tin=25, tout=85, cp=2.5)
    streams = [hot, cold]
    assert build_composite(streams, StreamKind.HOT).total_enthalpy == pytest.approx(600.0)
    assert build_composite(streams, StreamKind.COLD).total_enthalpy == pytest.approx(150.0)


def test_stream_with_energy_input_uses_derived_cp():
    # 600 kW over 60 C -> CP = 10 kW/C
    curve = build_composite([Stream(tin=100, tout=40, energy=600)], StreamKind.HOT)
    assert curve.total_enthalpy == pytest.approx(600.0)


def test_empty_streams_gives_empty_curve():
    curve = build_composite([], StreamKind.HOT)
    assert curve.temperatures == ()
    assert curve.enthalpy == ()
    assert curve.total_enthalpy == 0.0
    assert curve.points() == []


class TestShifted:
    def test_hot_shifted_down(self):
        curve = build_composite([Stream(tin=100, tout=40, cp=10)], StreamKind.HOT)
        shifted = curve.shifted(10)
        assert shifted.temperatures == (30.0, 90.0)
        assert shifted.enthalpy == curve.enthalpy

    def test_cold_shifted_up(self):
        curve = build_composite([Stream(tin=25, tout=85, cp=2.5)], StreamKind.COLD)
        shifted = curve.shifted(10)
        assert shifted.temperatures == (35.0, 95.0)
        assert shifted.enthalpy == curve.enthalpy

    def test_zero_shift_is_identity(self):
        curve = build_composite([Stream(tin=25, tout=85, cp=2.5)], StreamKind.COLD)
        assert curve.shifted(0) == curve


class TestUtilityTargets:
    def test_simple_case_cold_shifts_by_qc_min(self):
        h = Stream(tin=100, tout=40, cp=10)  # 600 kW
        c = Stream(tin=25, tout=85, cp=2.5)  # 150 kW
        u = build_utility_targets([h, c], 0.0)
        assert u.min_hot == 0.0
        assert u.min_cold == pytest.approx(450.0)
        assert u.pinch_temperature == 100.0
        # Plain curves: hot unchanged, cold shifted right by exactly QC,min.
        assert u.hot.temperatures == (40.0, 100.0)
        assert u.hot.enthalpy == (0.0, 600.0)
        assert u.cold.temperatures == (25.0, 85.0)
        assert u.cold.enthalpy == (450.0, 600.0)

    def test_curves_touch_at_pinch_when_delta_t_min_zero(self):
        h1 = Stream(tin=200, tout=100, cp=2)
        h2 = Stream(tin=60, tout=40, cp=10)
        c1 = Stream(tin=50, tout=150, cp=4)
        c2 = Stream(tin=30, tout=45, cp=6)
        u = build_utility_targets([h1, h2, c1, c2], 0.0)
        assert u.min_hot == pytest.approx(160.0)
        assert u.min_cold == pytest.approx(70.0)
        assert u.pinch_temperature == 60.0
        # No extensions: curves keep their plain point sets.
        assert u.hot.temperatures == (40.0, 60.0, 100.0, 200.0)
        assert u.hot.enthalpy == (0.0, 200.0, 200.0, 400.0)
        assert u.cold.temperatures == (30.0, 45.0, 50.0, 150.0)
        assert u.cold.enthalpy == (70.0, 160.0, 160.0, 560.0)
        # With delta_t_min = 0 both curves pass through (200 kW, 60 C).
        assert enthalpy_at(u.hot, 60.0) == pytest.approx(200.0)
        assert enthalpy_at(u.cold, 60.0) == pytest.approx(200.0)

    def test_gap_at_pinch_equals_delta_t_min(self):
        h1 = Stream(tin=200, tout=100, cp=2)
        h2 = Stream(tin=60, tout=40, cp=10)
        c1 = Stream(tin=50, tout=150, cp=4)
        c2 = Stream(tin=30, tout=45, cp=6)
        u = build_utility_targets([h1, h2, c1, c2], 10.0)
        assert u.min_hot == pytest.approx(200.0)
        assert u.min_cold == pytest.approx(110.0)
        assert u.pinch_temperature == 55.0  # shifted scale
        # At the pinch both curves sit at the same enthalpy (200 kW) but
        # 10 C apart: hot at 60 C (pinch + dT/2), cold at 50 C (pinch - dT/2).
        assert enthalpy_at(u.hot, 60.0) == pytest.approx(200.0)
        assert enthalpy_at(u.cold, 50.0) == pytest.approx(200.0)
        assert enthalpy_at(u.hot, 50.0) < enthalpy_at(u.cold, 50.0)

    def test_delta_t_min_keeps_actual_temperatures(self):
        h = Stream(tin=100, tout=40, cp=10)
        c = Stream(tin=25, tout=85, cp=2.5)
        u = build_utility_targets([h, c], 10.0)
        assert u.hot.temperatures == (40.0, 100.0)  # no shift applied
        assert u.cold.temperatures == (25.0, 85.0)
        assert u.min_cold == pytest.approx(450.0)
        assert u.pinch_temperature == 95.0  # shifted scale from the PTA

    def test_enthalpy_at_clamps_outside_range(self):
        h = Stream(tin=100, tout=40, cp=10)
        u = build_utility_targets([h], 0.0)
        assert enthalpy_at(u.hot, 10.0) == 0.0
        assert enthalpy_at(u.hot, 500.0) == u.hot.total_enthalpy

    def test_only_cold_streams(self):
        c = Stream(tin=25, tout=85, cp=2.5)
        u = build_utility_targets([c], 0.0)
        assert u.min_hot == pytest.approx(150.0)  # hot utility = cold duty
        assert u.min_cold == 0.0
        assert u.hot.enthalpy == ()
        # QC,min = 0, so the cold curve is unchanged (no shift).
        assert u.cold.enthalpy == (0.0, 150.0)


class TestGrandCompositeCurve:
    def test_gcc_from_combined_pta(self):
        h1 = Stream(tin=200, tout=100, cp=2)
        h2 = Stream(tin=60, tout=40, cp=10)
        c1 = Stream(tin=50, tout=150, cp=4)
        c2 = Stream(tin=30, tout=45, cp=6)
        gcc = build_gcc([h1, h2, c1, c2], 0.0)
        assert gcc.heat_flow == (160.0, 260.0, 160.0, 0.0, 60.0, 110.0, 130.0, 70.0)
        assert gcc.temperatures == (200.0, 150.0, 100.0, 60.0, 50.0, 45.0, 40.0, 30.0)
        assert gcc.min_hot == pytest.approx(160.0)
        assert gcc.min_cold == pytest.approx(70.0)
        assert gcc.pinch_temperature == 60.0

    def test_gcc_uses_shifted_temperatures(self):
        h = Stream(tin=100, tout=40, cp=10)
        c = Stream(tin=25, tout=85, cp=2.5)
        gcc = build_gcc([h, c], 10.0)
        assert gcc.temperatures == (95.0, 90.0, 35.0, 30.0)
        assert gcc.min_cold == pytest.approx(450.0)
        assert gcc.pinch_temperature == 95.0

    def test_gcc_empty_streams(self):
        gcc = build_gcc([], 0.0)
        assert gcc.heat_flow == ()
        assert gcc.temperatures == ()
        assert gcc.pinch_temperature is None
        assert gcc.min_hot == 0.0
        assert gcc.min_cold == 0.0


class TestTspCurves:
    def test_cold_positive_hot_negative(self):
        h = Stream(tin=100, tout=40, cp=10)  # 600 kW
        c = Stream(tin=25, tout=85, cp=2.5)  # 150 kW
        tsp = build_tsp_curves([h, c], 0.0)
        # Both curves start at energy 0: hot at its highest temperature on
        # the negative side, cold at its lowest temperature on the positive
        # side (plain composites, no utility shift).
        assert tsp.hot.enthalpy == (-600.0, 0.0)
        assert tsp.cold.enthalpy == (0.0, 150.0)
        assert all(q <= 0 for q in tsp.hot.enthalpy)
        assert all(q >= 0 for q in tsp.cold.enthalpy)
        assert tsp.hot.temperatures == (40.0, 100.0)
        assert tsp.cold.temperatures == (25.0, 85.0)

    def test_tsp_empty_streams(self):
        tsp = build_tsp_curves([], 0.0)
        assert tsp.hot.enthalpy == ()
        assert tsp.cold.enthalpy == ()

"""Tests for the stream input model and its energy/CP derivation rules."""

import pytest

from backend.streams import Stream, StreamKind, StreamValidationError, UtilityStream


class TestUtilityStream:
    def test_utility_stream(self):
        u = UtilityStream(name="HP steam", temperature=250.0)
        assert u.name == "HP steam"
        assert u.temperature == 250.0

    def test_non_finite_temperature_rejected(self):
        with pytest.raises(StreamValidationError):
            UtilityStream(name="CW", temperature=float("nan"))


class TestEnergyToCp:
    def test_cp_derived_from_energy(self):
        s = Stream(tin=100.0, tout=40.0, energy=600.0)
        assert s.temperature_difference == 60.0
        assert s.heat_capacity_flow == pytest.approx(10.0)
        assert s.total_energy == pytest.approx(600.0)

    def test_cp_derived_from_energy_other_direction(self):
        s = Stream(tin=40.0, tout=100.0, energy=600.0)
        assert s.heat_capacity_flow == pytest.approx(10.0)
        assert s.total_energy == pytest.approx(600.0)


class TestCpToEnergy:
    def test_energy_derived_from_cp(self):
        s = Stream(tin=25.0, tout=85.0, cp=2.5)
        assert s.temperature_difference == 60.0
        assert s.total_energy == pytest.approx(150.0)
        assert s.heat_capacity_flow == pytest.approx(2.5)

    def test_energy_derived_from_cp_other_direction(self):
        s = Stream(tin=85.0, tout=25.0, cp=2.5)
        assert s.total_energy == pytest.approx(150.0)


class TestValidation:
    def test_zero_temperature_difference_rejected(self):
        with pytest.raises(StreamValidationError):
            Stream(tin=50.0, tout=50.0, energy=100.0)

    def test_both_energy_and_cp_rejected(self):
        with pytest.raises(StreamValidationError):
            Stream(tin=100.0, tout=40.0, energy=600.0, cp=10.0)

    def test_neither_energy_nor_cp_rejected(self):
        with pytest.raises(StreamValidationError):
            Stream(tin=100.0, tout=40.0)

    def test_negative_energy_rejected(self):
        with pytest.raises(StreamValidationError):
            Stream(tin=100.0, tout=40.0, energy=-5.0)

    def test_negative_cp_rejected(self):
        with pytest.raises(StreamValidationError):
            Stream(tin=100.0, tout=40.0, cp=-2.0)

    def test_non_finite_temperature_rejected(self):
        with pytest.raises(StreamValidationError):
            Stream(tin=float("nan"), tout=40.0, energy=600.0)

    def test_non_numeric_rejected(self):
        with pytest.raises(StreamValidationError):
            Stream(tin="hot", tout=40.0, energy=600.0)


class TestKind:
    def test_hot_when_cooling_down(self):
        assert Stream(tin=120.0, tout=60.0, energy=300.0).kind is StreamKind.HOT

    def test_cold_when_heating_up(self):
        assert Stream(tin=20.0, tout=90.0, cp=4.0).kind is StreamKind.COLD


class TestMisc:
    def test_name_is_optional(self):
        assert Stream(tin=100.0, tout=40.0, energy=600.0).name == ""

    def test_named_stream(self):
        assert Stream(tin=25.0, tout=85.0, name="reactor feed", cp=2.5).name == "reactor feed"

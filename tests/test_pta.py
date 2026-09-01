"""Tests for the Problem Table Algorithm."""

import pytest

from backend import Stream, problem_table

# Hand-verified example streams (delta T min = 0).
H1 = Stream(tin=200, tout=100, cp=2)   # hot, 200 kW
H2 = Stream(tin=60, tout=40, cp=10)    # hot, 200 kW
C1 = Stream(tin=50, tout=150, cp=4)    # cold, 400 kW
C2 = Stream(tin=30, tout=45, cp=6)     # cold, 90 kW

ALL = [H1, H2, C1, C2]


class TestHotPta:
    def test_cascade_and_total_duty(self):
        pt = problem_table([H1, H2], "hot", 0.0)
        assert pt.levels == (200.0, 100.0, 60.0, 40.0)
        assert [iv.delta_h for iv in pt.intervals] == [200.0, 0.0, 200.0]
        assert pt.cascade == (0.0, 200.0, 200.0, 400.0)
        assert pt.total_duty == pytest.approx(400.0)
        assert pt.min_hot_utility is None

    def test_hot_streams_ignored_in_cold_table(self):
        pt = problem_table(ALL, "cold", 0.0)
        assert pt.levels == (150.0, 50.0, 45.0, 30.0)
        assert [iv.delta_h for iv in pt.intervals] == [400.0, 0.0, 90.0]
        assert pt.cascade == (0.0, 400.0, 400.0, 490.0)
        assert pt.total_duty == pytest.approx(490.0)


class TestCombined:
    def test_utility_targets_and_pinch(self):
        pt = problem_table(ALL, "combined", 0.0)
        # Intervals: (200,150):+100, (150,100):-100, (100,60):-160,
        #            (60,50):+60, (50,45):+50, (45,40):+20, (40,30):-60
        assert [iv.delta_h for iv in pt.intervals] == [
            100.0, -100.0, -160.0, 60.0, 50.0, 20.0, -60.0,
        ]
        assert pt.min_hot_utility == pytest.approx(160.0)
        assert pt.min_cold_utility == pytest.approx(70.0)
        assert pt.pinch_temperatures == (60.0,)

    def test_simple_case_hot_surplus(self):
        h = Stream(tin=100, tout=40, cp=10)  # 600 kW
        c = Stream(tin=25, tout=85, cp=2.5)  # 150 kW
        pt = problem_table([h, c], "combined", 0.0)
        assert pt.min_hot_utility == 0.0
        assert pt.min_cold_utility == pytest.approx(450.0)
        assert pt.pinch_temperatures == (100.0,)

    def test_interval_details(self):
        pt = problem_table(ALL, "combined", 0.0)
        assert pt.intervals[0].cp_sum == 2.0  # H1 only, hottest interval
        assert pt.intervals[0].delta_t == 50.0
        iv3 = pt.intervals[2]  # (100, 60): only C1
        assert iv3.cp_sum == -4.0
        assert iv3.delta_h == -160.0
        # Net CPs: hot surplus above the pinch, cold deficit below it.
        assert [iv.cp_sum for iv in pt.intervals] == [
            2.0, -2.0, -4.0, 6.0, 10.0, 4.0, -6.0,
        ]
        assert pt.intervals[-1].cp_sum == -6.0  # C2 only, coldest interval


class TestShift:
    def test_shifted_levels_use_delta_t_min(self):
        h = Stream(tin=100, tout=40, cp=10)
        c = Stream(tin=25, tout=85, cp=2.5)
        pt = problem_table([h, c], "combined", 10.0)
        # hot shifted down 5 C: 95, 35; cold shifted up 5 C: 30, 90
        assert pt.levels == (95.0, 90.0, 35.0, 30.0)
        assert pt.pinch_temperatures == (95.0,)

    def test_no_shift_when_delta_t_min_is_zero(self):
        pt = problem_table(ALL, "combined", 0.0)
        assert pt.levels == (200.0, 150.0, 100.0, 60.0, 50.0, 45.0, 40.0, 30.0)


class TestEdgeCases:
    def test_empty_streams(self):
        pt = problem_table([], "combined", 0.0)
        assert pt.intervals == ()
        assert pt.levels == ()
        assert pt.cascade == (0.0,)
        assert pt.min_hot_utility == 0.0
        assert pt.min_cold_utility == 0.0

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError):
            problem_table([], "bogus", 0.0)

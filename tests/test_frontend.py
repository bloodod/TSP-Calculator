"""Headless smoke tests for the PyQt6 main window (offscreen platform)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

from frontend.main_window import MainWindow


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def window(app):
    win = MainWindow()
    win.show()
    app.processEvents()
    yield win
    win.close()


def _add(window, tin, tout, value, use_cp=False):
    window.tin_spin.setValue(tin)
    window.tout_spin.setValue(tout)
    window.duty_spin.setValue(value)
    window.energy_radio.setChecked(not use_cp)
    window.cp_radio.setChecked(use_cp)
    window.add_button.click()


def _cell_text(window, row, col):
    item = window.table.item(row, col)
    return item.text() if item else None


class TestLayout:
    def test_title(self, window):
        assert window.title_label.text() == "Total Site Profile Calculator"

    def test_delta_t_min_defaults_to_zero(self, window):
        assert window.dtmin_spin.value() == 0.0
        assert window.tsp.delta_t_min == 0.0


class TestStreamNaming:
    def test_hot_and_cold_sequence(self, window):
        _add(window, 100, 40, 600)  # hot
        _add(window, 120, 60, 300)  # hot
        _add(window, 25, 85, 2.5, use_cp=True)  # cold
        names = [_cell_text(window, r, 0) for r in range(window.table.rowCount())]
        types = [_cell_text(window, r, 1) for r in range(window.table.rowCount())]
        assert names == ["H1", "H2", "C1"]
        assert types == ["H", "H", "C"]

    def test_numbering_reuses_freed_numbers(self, window):
        _add(window, 100, 40, 600)
        _add(window, 120, 60, 300)
        window.table.selectRow(1)
        window.delete_button.click()
        _add(window, 80, 30, 200)
        assert _cell_text(window, 1, 0) == "H2"
        assert [s.name for s in window.tsp.streams] == ["H1", "H2"]

    def test_name_preview_updates(self, window):
        window.tin_spin.setValue(100)
        window.tout_spin.setValue(40)
        assert "H1" in window.name_preview.text()
        _add(window, 100, 40, 600)
        assert "H2" in window.name_preview.text()
        window.tin_spin.setValue(25)
        window.tout_spin.setValue(85)
        assert "C1" in window.name_preview.text()


class TestDerivedValues:
    def test_energy_input_shows_derived_cp(self, window):
        _add(window, 100, 40, 600)
        assert _cell_text(window, 0, 4) == "600"
        assert _cell_text(window, 0, 5) == "10"

    def test_cp_input_shows_derived_energy(self, window):
        _add(window, 25, 85, 2.5, use_cp=True)
        assert _cell_text(window, 0, 4) == "150"
        assert _cell_text(window, 0, 5) == "2.5"


class TestEditing:
    def test_edit_energy_cell_switches_given_input(self, window):
        _add(window, 100, 40, 600)
        # setText on an attached item emits itemChanged naturally
        window.table.item(0, 4).setText("1200")
        stream = window.tsp.streams[0]
        assert stream.energy == 1200.0
        assert stream.cp is None
        assert _cell_text(window, 0, 5) == "20"

    def test_edit_temperature_recomputes_derived_values(self, window):
        _add(window, 100, 40, 600)
        window.table.item(0, 2).setText("150")
        stream = window.tsp.streams[0]
        assert stream.tin == 150.0
        assert stream.total_energy == 600.0  # energy is the given input
        assert stream.heat_capacity_flow == pytest.approx(600.0 / 110.0)
        assert _cell_text(window, 0, 4) == "600"
        assert _cell_text(window, 0, 5) == "5.45455"

    def test_invalid_temperature_reverts_cell(self, window, monkeypatch):
        _add(window, 100, 40, 600)
        dialogs = []
        monkeypatch.setattr(
            "frontend.main_window.QMessageBox.warning",
            lambda *a, **k: dialogs.append(a),
        )
        item = window.table.item(0, 2)
        item.setText("40")  # equals the outlet temperature
        assert dialogs  # a warning was shown
        assert window.tsp.streams[0].tin == 100.0
        assert _cell_text(window, 0, 2) == "100"

    def test_edit_name(self, window):
        _add(window, 100, 40, 600)
        item = window.table.item(0, 0)
        item.setText("Reactor cooler")
        window.table.itemChanged.emit(item)
        assert window.tsp.streams[0].name == "Reactor cooler"


class TestDelete:
    def test_delete_selected_row(self, window):
        _add(window, 100, 40, 600)
        _add(window, 25, 85, 2.5, use_cp=True)
        window.table.selectRow(0)
        window.delete_button.click()
        assert window.table.rowCount() == 1
        assert len(window.tsp) == 1
        assert window.tsp.streams[0].name == "C1"

    def test_delete_without_selection_shows_info(self, window, monkeypatch):
        dialogs = []
        monkeypatch.setattr(
            "frontend.main_window.QMessageBox.information",
            lambda *a, **k: dialogs.append(a),
        )
        window.delete_button.click()
        assert dialogs
        assert window.table.rowCount() == 0


class TestDeltaTMin:
    def test_delta_t_min_syncs_to_backend(self, window):
        window.dtmin_spin.setValue(10.0)
        assert window.tsp.delta_t_min == 10.0


class TestCompositePage:
    def test_switch_to_composite_tab_plots_curves(self, window):
        _add(window, 100, 40, 600)  # hot
        _add(window, 25, 85, 2.5, use_cp=True)  # cold
        window.tabs.setCurrentIndex(1)
        assert window.composite_page.hot_curve is not None
        assert window.composite_page.cold_curve is not None
        assert window.composite_page.hot_curve.total_enthalpy == pytest.approx(600.0)
        assert window.composite_page.cold_curve.total_enthalpy == pytest.approx(150.0)

    def test_empty_profile_shows_placeholder(self, window):
        window.tabs.setCurrentIndex(1)
        assert window.composite_page.hot_curve.enthalpy == ()
        assert window.composite_page.cold_curve.enthalpy == ()

    def test_refresh_after_stream_change(self, window):
        _add(window, 100, 40, 600)
        window.tabs.setCurrentIndex(1)
        assert window.composite_page.hot_curve.total_enthalpy == pytest.approx(600.0)
        window.tabs.setCurrentIndex(0)
        window.table.selectRow(0)
        window.delete_button.click()
        window.tabs.setCurrentIndex(1)
        assert window.composite_page.hot_curve.enthalpy == ()

    def test_delta_t_min_shifts_cold_composite(self, window):
        _add(window, 100, 40, 600)
        _add(window, 25, 85, 2.5, use_cp=True)
        window.dtmin_spin.setValue(10.0)
        window.tabs.setCurrentIndex(1)
        shifted = window.composite_page.cold_curve.shifted(10.0)
        assert shifted.temperatures == (35.0, 95.0)


class TestPtaPage:
    def test_switch_to_pta_tab_builds_hot_table(self, window):
        _add(window, 100, 40, 600)
        _add(window, 25, 85, 2.5, use_cp=True)
        window.tabs.setCurrentIndex(2)
        pt = window.pta_page.result
        assert pt.kind == "hot"
        assert pt.cascade[-1] == pytest.approx(600.0)

    def test_combo_switches_to_combined(self, window):
        _add(window, 100, 40, 600)
        _add(window, 25, 85, 2.5, use_cp=True)
        window.pta_page.refresh(window.tsp)
        window.pta_page.kind_combo.setCurrentText("Combined")
        pt = window.pta_page.result
        assert pt.kind == "combined"
        assert pt.min_hot_utility == 0.0
        assert pt.min_cold_utility == pytest.approx(450.0)

    def test_combo_switches_to_cold(self, window):
        _add(window, 100, 40, 600)
        _add(window, 25, 85, 2.5, use_cp=True)
        window.pta_page.refresh(window.tsp)
        window.pta_page.kind_combo.setCurrentText("Cold")
        pt = window.pta_page.result
        assert pt.kind == "cold"
        assert pt.cascade[-1] == pytest.approx(150.0)

    def test_empty_profile_shows_placeholder(self, window):
        window.tabs.setCurrentIndex(2)
        assert window.pta_page.result.intervals == ()


class TestUtilityPlot:
    def test_utilities_from_combined_pta(self, window):
        _add(window, 100, 40, 600)
        _add(window, 25, 85, 2.5, use_cp=True)
        window.tabs.setCurrentIndex(1)
        u = window.composite_page.utilities
        assert u.min_hot == 0.0
        assert u.min_cold == pytest.approx(450.0)
        assert u.pinch_temperature == 100.0

    def test_utilities_view_is_default(self, window):
        _add(window, 100, 40, 600)
        _add(window, 25, 85, 2.5, use_cp=True)
        window.tabs.setCurrentIndex(1)
        u = window.composite_page.utilities
        assert u is not None
        # The cold composite is shifted right by QC,min = 450 kW.
        assert u.cold.enthalpy == (450.0, 600.0)
        assert window.composite_page.hot_curve.total_enthalpy == pytest.approx(600.0)

    def test_utilities_none_without_streams(self, window):
        window.tabs.setCurrentIndex(1)
        assert window.composite_page.utilities is None

    def test_plot_style_and_title(self, window):
        _add(window, 100, 40, 600)
        _add(window, 25, 85, 2.5, use_cp=True)
        window.dtmin_spin.setValue(10.0)
        window.tabs.setCurrentIndex(1)
        ax = window.composite_page.figure.axes[0]
        assert {line.get_marker() for line in ax.lines} == {"x", "o"}
        assert "ΔT min of 10" in ax.get_title()

    def test_arrow_anchors_on_higher_and_lower_curves(self, window):
        _add(window, 100, 40, 600)  # hot, top 100 C
        _add(window, 25, 85, 2.5, use_cp=True)  # cold, top 85 C
        window.tabs.setCurrentIndex(1)
        u = window.composite_page.utilities
        # The hot curve ends higher in temperature, the cold one lower.
        assert window.composite_page._top_anchor(u) == (600.0, 100.0, True)
        assert window.composite_page._bottom_anchor(u) == (450.0, 25.0, False)

    def test_arrow_anchor_switches_when_cold_is_higher(self, window):
        _add(window, 100, 40, 5.0, use_cp=True)  # hot 300 kW, top 100 C
        _add(window, 85, 150, 10.0, use_cp=True)  # cold 650 kW, top 150 C
        window.tabs.setCurrentIndex(1)
        u = window.composite_page.utilities
        assert u.min_hot == pytest.approx(575.0)
        assert u.min_cold == pytest.approx(225.0)
        # The cold curve is now the higher one, the hot curve the lower one:
        # the QH,min arrow anchors on cold (points left), the QC,min arrow
        # anchors on hot (points right).
        assert window.composite_page._top_anchor(u) == (875.0, 150.0, False)
        assert window.composite_page._bottom_anchor(u) == (0.0, 40.0, True)


class TestGccPage:
    def test_switch_to_gcc_tab_uses_combined_pta(self, window):
        _add(window, 100, 40, 600)
        _add(window, 25, 85, 2.5, use_cp=True)
        window.tabs.setCurrentIndex(3)
        gcc = window.gcc_page.gcc
        assert gcc is not None
        assert gcc.min_hot == 0.0
        assert gcc.min_cold == pytest.approx(450.0)
        assert gcc.pinch_temperature == 100.0

    def test_gcc_shifts_with_delta_t_min(self, window):
        _add(window, 100, 40, 600)
        _add(window, 25, 85, 2.5, use_cp=True)
        window.dtmin_spin.setValue(10.0)
        window.tabs.setCurrentIndex(3)
        assert window.gcc_page.gcc.temperatures == (95.0, 90.0, 35.0, 30.0)

    def test_gcc_empty_profile(self, window):
        window.tabs.setCurrentIndex(3)
        assert window.gcc_page.gcc is None


class TestTspPage:
    def test_switch_to_tsp_tab(self, window):
        _add(window, 100, 40, 600)
        _add(window, 25, 85, 2.5, use_cp=True)
        window.tabs.setCurrentIndex(4)
        curves = window.tsp_page.curves
        assert curves is not None
        # Hot: negative side, ends at 0 at its highest temperature.
        assert curves.hot.enthalpy == (-600.0, 0.0)
        # Cold: positive side, starts at 0 at its lowest temperature.
        assert curves.cold.enthalpy == (0.0, 150.0)

    def test_tsp_plot_hot_negative_cold_positive(self, window):
        _add(window, 100, 40, 600)
        _add(window, 25, 85, 2.5, use_cp=True)
        window.tabs.setCurrentIndex(4)
        ax = window.tsp_page.figure.axes[0]
        # Exclude the zero-axis vline; keep the two composite curve lines.
        lines = [line for line in ax.lines if line.get_marker() in ("x", "o")]
        assert len(lines) == 2
        hot, cold = sorted(lines, key=lambda line: min(line.get_xdata()))
        assert max(hot.get_xdata()) <= 0.0  # hot on the negative side
        assert min(cold.get_xdata()) >= 0.0  # cold on the positive side
        assert {line.get_marker() for line in lines} == {"x", "o"}

    def test_tsp_empty_profile(self, window):
        window.tabs.setCurrentIndex(4)
        assert window.tsp_page.curves is None


class TestTspUtilities:
    def test_add_utility_stream(self, window):
        window.tabs.setCurrentIndex(4)
        page = window.tsp_page
        page.utility_name_edit.setText("HP steam")
        page.utility_temp_spin.setValue(250.0)
        page.utility_add_button.click()
        assert page.utility_table.rowCount() == 1
        assert page.utility_table.item(0, 0).text() == "HP steam"
        assert page.utility_table.item(0, 1).text() == "250"
        assert len(window.tsp.utility_streams) == 1
        assert window.tsp.utility_streams[0].name == "HP steam"
        assert window.tsp.utility_streams[0].temperature == 250.0

    def test_add_multiple_utility_streams(self, window):
        window.tabs.setCurrentIndex(4)
        page = window.tsp_page
        for name, temp in [("HP steam", 250.0), ("CW", 25.0)]:
            page.utility_name_edit.setText(name)
            page.utility_temp_spin.setValue(temp)
            page.utility_add_button.click()
        assert page.utility_table.rowCount() == 2
        assert [u.name for u in window.tsp.utility_streams] == ["HP steam", "CW"]
        assert [u.temperature for u in window.tsp.utility_streams] == [250.0, 25.0]


class TestQualityOfLife:
    def test_cp_is_default_duty_input(self, window):
        assert window.cp_radio.isChecked()
        assert not window.energy_radio.isChecked()
        assert window.duty_label.text() == "Heat capacity flow rate (kW/°C)"

    def test_add_returns_focus_to_inlet_temperature(self, window):
        _add(window, 100, 40, 2.5, use_cp=True)
        assert window.tin_spin.hasFocus()

    def test_enter_in_input_panel_adds_stream(self, window):
        window.tin_spin.setValue(100)
        window.tout_spin.setValue(40)
        window.duty_spin.setValue(2.5)
        window.cp_radio.setChecked(True)
        window.tin_spin.setFocus()
        QTest.keyClick(window.tin_spin, Qt.Key.Key_Return)
        assert window.table.rowCount() == 1
        assert _cell_text(window, 0, 0) == "H1"
        assert window.tin_spin.hasFocus()

    def test_enter_on_delete_button_deletes(self, window):
        _add(window, 100, 40, 600)
        window.table.selectRow(0)
        window.delete_button.setFocus()
        QTest.keyClick(window.delete_button, Qt.Key.Key_Return)
        assert window.table.rowCount() == 0


class TestMoreButtons:
    def test_button_loads_test_streams(self, window):
        from frontend.main_window import TEST_STREAMS

        window.test_button.click()
        assert window.table.rowCount() == len(TEST_STREAMS)
        # Names: H1..Hn for hot streams first, then C1..Cm for cold.
        expected_names = []
        counters = {"H": 0, "C": 0}
        for tin, tout, _ in TEST_STREAMS:
            key = "H" if tout < tin else "C"
            counters[key] += 1
            expected_names.append(f"{key}{counters[key]}")
        names = [_cell_text(window, r, 0) for r in range(window.table.rowCount())]
        assert names == expected_names
        # Every row shows consistent values: Q = CP * |Tout - Tin|.
        for r, (tin, tout, cp) in enumerate(TEST_STREAMS):
            assert _cell_text(window, r, 2) == f"{tin:g}"
            assert _cell_text(window, r, 3) == f"{tout:g}"
            assert _cell_text(window, r, 5) == f"{cp:g}"
            assert _cell_text(window, r, 4) == f"{cp * abs(tout - tin):g}"

    def test_button_replaces_existing_streams(self, window):
        from frontend.main_window import TEST_STREAMS

        _add(window, 100, 40, 600)
        assert window.table.rowCount() == 1
        window.test_button.click()
        assert window.table.rowCount() == len(TEST_STREAMS)
        assert len(window.tsp) == len(TEST_STREAMS)

    def test_button_loads_into_backend(self, window):
        from frontend.main_window import TEST_STREAMS

        window.test_button.click()
        assert len(window.tsp) == len(TEST_STREAMS)
        for stream, (tin, tout, cp) in zip(window.tsp.streams, TEST_STREAMS):
            assert stream.tin == tin
            assert stream.tout == tout
            assert stream.cp == cp
            assert stream.total_energy == pytest.approx(cp * abs(tout - tin))

    def test_delete_all_clears_table_after_confirmation(self, window, monkeypatch):
        _add(window, 100, 40, 600)
        _add(window, 25, 85, 2.5, use_cp=True)
        monkeypatch.setattr(
            "frontend.main_window.QMessageBox.question",
            lambda *a, **k: QMessageBox.StandardButton.Yes,
        )
        window.delete_all_button.click()
        assert window.table.rowCount() == 0
        assert len(window.tsp) == 0

    def test_delete_all_aborts_when_declined(self, window, monkeypatch):
        _add(window, 100, 40, 600)
        answers = []
        monkeypatch.setattr(
            "frontend.main_window.QMessageBox.question",
            lambda *a, **k: answers.append(a) or QMessageBox.StandardButton.No,
        )
        window.delete_all_button.click()
        assert answers  # the confirmation was shown
        assert window.table.rowCount() == 1
        assert len(window.tsp) == 1

    def test_delete_all_with_no_streams_shows_info(self, window, monkeypatch):
        dialogs = []
        monkeypatch.setattr(
            "frontend.main_window.QMessageBox.information",
            lambda *a, **k: dialogs.append(a),
        )
        window.delete_all_button.click()
        assert dialogs
        assert window.table.rowCount() == 0

"""Headless smoke tests for the PyQt6 main window (offscreen platform)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from frontend.main_window import MainWindow


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def window(app):
    win = MainWindow()
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

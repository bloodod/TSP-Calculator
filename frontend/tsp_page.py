"""Total Site Profile page: composite curves mirrored on the energy axis.

The plot shows the cold composite on the positive energy side and the hot
composite on the negative side, both starting at energy 0. On the right, a
narrow panel manages the site's utility streams (name + temperature): a
tall editable table at the top, the input fields and all action buttons
below it, and the shared figure options panel (size, fit, export) under
the buttons.
"""

from __future__ import annotations

import math

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backend import (
    TotalSiteProfile,
    TotalSiteProfileCurves,
    UtilityStream,
    build_tsp_curves,
    cold_utility_staircase,
    tsp_shift_amount,
    utility_staircase,
)

from .figure_controls import FigureControls, ScrollableCanvas

HOT_COLOR = "#C0392B"
COLD_COLOR = "#2471A3"
SOURCE_COMPOSITE_COLOR = "#85C1E9"  # light blue
SINK_COMPOSITE_COLOR = "#F1948A"  # light red

# Built-in utility streams loaded by the Test button, as (name, temperature).
TEST_UTILITIES = [
    ("a", 25.0),
    ("b", 50.0),
    ("c", 100.0),
    ("d", 150.0),
    ("e", 170.0),
    ("f", 200.0),
    ("g", 350.0),
]


class TspPage(QWidget):
    """Total site profile: cold composite on +energy, hot on -energy."""

    # Emitted when the SUGCC button is pressed; the main window switches to
    # the SUGCC tab, where the curve is already plotted.
    sugcc_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tsp: TotalSiteProfile | None = None
        self._updating = False  # guards itemChanged against refresh recursion

        root = QVBoxLayout(self)
        body = QHBoxLayout()
        body.setSpacing(8)
        body.addWidget(self._build_plot(), 9)
        body.addLayout(self._build_utility_panel(), 1)
        root.addLayout(body, 1)

        self.curves: TotalSiteProfileCurves | None = None
        self._placeholder()

    # ------------------------------------------------------------------
    # Plot
    # ------------------------------------------------------------------

    def _build_plot(self) -> QWidget:
        self.figure = Figure(figsize=(7, 5), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas_view = ScrollableCanvas(self.canvas)
        return self.canvas_view

    def refresh(self, tsp: TotalSiteProfile) -> None:
        """Rebuild and redraw the TSP from the profile's streams."""
        self.tsp = tsp
        self._reload_utility_table()
        self.curves = (
            build_tsp_curves(tsp.streams, tsp.delta_t_min) if tsp.streams else None
        )
        if self.curves is None or (
            not self.curves.hot.enthalpy and not self.curves.cold.enthalpy
        ):
            self._placeholder()
            self._update_sugcc_button()
            return
        self._plot()
        self._update_sugcc_button()

    def _reload_utility_table(self) -> None:
        """Rebuild the utility table from the model (used on refresh/load)."""
        self._updating = True
        try:
            self.utility_table.setRowCount(0)
            for utility in self.tsp.utility_streams:
                row = self.utility_table.rowCount()
                self.utility_table.insertRow(row)
                self._set_utility_row(row, utility)
        finally:
            self._updating = False

    def _placeholder(self) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            "Add streams to see the total site profile",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color="gray",
            fontsize=12,
        )
        ax.set_axis_off()
        self.canvas.draw()

    def _plot(self) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        temps = (
            [u.temperature for u in self.tsp.utility_streams]
            if self.tsp is not None
            else []
        )
        hot_steps = (
            utility_staircase(self.curves.hot, temps)
            if temps and self.curves.hot.enthalpy
            else []
        )
        cold_steps = (
            cold_utility_staircase(self.curves.cold, temps)
            if temps and self.curves.cold.enthalpy
            else []
        )
        # TSP shift: shortest distance between the staircases' verticals; the
        # cold composite and the cold utility staircase both move left by it.
        shift = (
            tsp_shift_amount(hot_steps, cold_steps)
            if self.tsp_shift_button.isChecked() and hot_steps and cold_steps
            else None
        )

        if self.curves.hot.enthalpy:
            ax.plot(
                self.curves.hot.enthalpy,
                self.curves.hot.temperatures,
                color=HOT_COLOR,
                linewidth=2.4,
                marker="x",
                markersize=5,
                label=(
                    "Site Source Profile "
                    f"({abs(self.curves.hot.enthalpy[0]):g} kW)"
                ),
            )
        if self.curves.cold.enthalpy:
            cold_enthalpy = self.curves.cold.enthalpy
            if shift is not None:
                cold_enthalpy = tuple(q - shift for q in cold_enthalpy)
            ax.plot(
                cold_enthalpy,
                self.curves.cold.temperatures,
                color=COLD_COLOR,
                linewidth=2.4,
                marker="o",
                markersize=4,
                label=(
                    "Site Sink Profile "
                    f"({self.curves.cold.total_enthalpy:g} kW)"
                ),
            )
        ax.axvline(0.0, color="gray", linestyle="--", linewidth=0.8)

        # Site source/sink composites: thin dotted staircases tracing the
        # source profile on the negative side and the sink profile on the
        # positive side.
        if self.plot_utilities_button.isChecked() and (hot_steps or cold_steps):
            if hot_steps:
                self._plot_staircase(
                    ax, hot_steps, "Site Source Composite", SOURCE_COMPOSITE_COLOR
                )
            if cold_steps:
                if shift is not None:
                    cold_steps = [(x - shift, t) for x, t in cold_steps]
                self._plot_staircase(
                    ax, cold_steps, "Site Sink Composite", SINK_COMPOSITE_COLOR
                )

        if shift is not None:
            ax.text(
                0.02,
                0.98,
                f"TSP shift: {shift:g} kW",
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=9,
                color="#2C3E50",
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    facecolor="white",
                    alpha=0.85,
                ),
            )

        ax.set_xlabel("Energy (kW)")
        ax.set_ylabel("Temperature (\u00b0C)")
        ax.set_title(
            f"Total Site Profile (\u0394T min = {self.tsp.delta_t_min:g} \u00b0C)"
        )
        ax.grid(True, linestyle=":", alpha=0.4)
        ax.legend(frameon=False)
        self.canvas.draw()

    def _plot_staircase(
        self, ax, steps: list[tuple[float, float]], label: str, color: str
    ) -> None:
        ax.plot(
            [p[0] for p in steps],
            [p[1] for p in steps],
            color=color,
            linestyle=":",
            linewidth=1.3,
            label=label,
        )

    # ------------------------------------------------------------------
    # Utility stream panel
    # ------------------------------------------------------------------

    def _build_utility_panel(self) -> QVBoxLayout:
        panel = QVBoxLayout()
        panel.setSpacing(6)

        title = QLabel("Utility streams")
        title.setStyleSheet("font-weight: bold;")
        panel.addWidget(title)

        # Editable table of utility streams at the top of the panel.
        self.utility_table = QTableWidget(0, 2)
        self.utility_table.setHorizontalHeaderLabels(["Name", "T (\u00b0C)"])
        self.utility_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.utility_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.utility_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.utility_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.utility_table.setFixedHeight(150)
        self.utility_table.itemChanged.connect(self._on_utility_cell_changed)
        panel.addWidget(self.utility_table)

        form = QFormLayout()
        self.utility_name_edit = QLineEdit()
        self.utility_temp_spin = QDoubleSpinBox()
        self.utility_temp_spin.setRange(-1000.0, 2000.0)
        self.utility_temp_spin.setDecimals(2)
        form.addRow("Name:", self.utility_name_edit)
        form.addRow("T (\u00b0C):", self.utility_temp_spin)
        panel.addLayout(form)

        # All buttons sit below the table, in a single group.
        self.utility_add_button = QPushButton("Add utility")
        self.utility_add_button.clicked.connect(self._on_utility_add_clicked)
        # Enter in the name field adds the stream (like the main input panel).
        self.utility_name_edit.returnPressed.connect(
            self.utility_add_button.click
        )
        panel.addWidget(self.utility_add_button)

        self.utility_test_button = QPushButton("Test")
        self.utility_test_button.clicked.connect(self._on_utility_test_clicked)
        panel.addWidget(self.utility_test_button)

        self.plot_utilities_button = QPushButton("Plot utility streams")
        self.plot_utilities_button.setCheckable(True)
        self.plot_utilities_button.toggled.connect(self._on_plot_utilities_toggled)
        panel.addWidget(self.plot_utilities_button)

        # TSP Shift and SUGCC share one row (SUGCC is enabled by the shift).
        shift_row = QHBoxLayout()
        self.tsp_shift_button = QPushButton("TSP Shift")
        self.tsp_shift_button.setCheckable(True)
        self.tsp_shift_button.toggled.connect(self._on_tsp_shift_toggled)
        shift_row.addWidget(self.tsp_shift_button)
        self.sugcc_button = QPushButton("SUGCC")
        self.sugcc_button.setEnabled(False)  # only after the TSP shift
        self.sugcc_button.clicked.connect(self.sugcc_requested.emit)
        shift_row.addWidget(self.sugcc_button)
        panel.addLayout(shift_row)

        delete_row = QHBoxLayout()
        self.utility_delete_button = QPushButton("Delete stream")
        self.utility_delete_button.clicked.connect(self._on_utility_delete_clicked)
        delete_row.addWidget(self.utility_delete_button)
        self.utility_delete_all_button = QPushButton("Delete all")
        self.utility_delete_all_button.clicked.connect(
            self._on_utility_delete_all_clicked
        )
        delete_row.addWidget(self.utility_delete_all_button)
        panel.addLayout(delete_row)

        # Same figure options as on the composite curves page: width/height,
        # fit to tab, aspect ratio, reset size and image export.
        self.controls = FigureControls(
            self.figure,
            canvas_host=self.canvas_view,
            default_size=(7.0, 5.0),
        )
        panel.addWidget(self.controls)

        panel.addStretch(1)
        return panel

    # -- handlers -------------------------------------------------------

    def _on_utility_add_clicked(self) -> None:
        if self.tsp is None:
            return
        utility = UtilityStream(
            name=self.utility_name_edit.text().strip(),
            temperature=self.utility_temp_spin.value(),
        )
        self.tsp.add_utility_stream(utility)
        self._append_utility_row(utility)
        self.utility_name_edit.clear()
        self.utility_name_edit.setFocus()

    def _on_utility_test_clicked(self) -> None:
        """Load the built-in test utilities, replacing the current list."""
        if self.tsp is None:
            return
        self.tsp.clear_utility_streams()
        self.utility_table.setRowCount(0)
        for name, temperature in TEST_UTILITIES:
            utility = UtilityStream(name=name, temperature=temperature)
            self.tsp.add_utility_stream(utility)
            self._append_utility_row(utility)
        self.utility_name_edit.clear()
        self.utility_name_edit.setFocus()

    def _on_plot_utilities_toggled(self, checked: bool) -> None:
        if self.curves is not None and (
            self.curves.hot.enthalpy or self.curves.cold.enthalpy
        ):
            self._plot()

    def _on_tsp_shift_toggled(self, checked: bool) -> None:
        self._update_sugcc_button()
        self._on_plot_utilities_toggled(checked)

    def _update_sugcc_button(self) -> None:
        """The SUGCC button needs the TSP shift with both staircases present."""
        if (
            not self.tsp_shift_button.isChecked()
            or self.tsp is None
            or self.curves is None
        ):
            self.sugcc_button.setEnabled(False)
            return
        temps = [u.temperature for u in self.tsp.utility_streams]
        hot_steps = (
            utility_staircase(self.curves.hot, temps)
            if temps and self.curves.hot.enthalpy
            else []
        )
        cold_steps = (
            cold_utility_staircase(self.curves.cold, temps)
            if temps and self.curves.cold.enthalpy
            else []
        )
        self.sugcc_button.setEnabled(bool(hot_steps and cold_steps))

    def _on_utility_delete_clicked(self) -> None:
        if self.tsp is None:
            return
        row = self.utility_table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Delete utility", "Select a utility stream to delete first."
            )
            return
        utility = self.tsp.utility_streams[row]
        self.tsp.remove_utility_stream(utility)
        self.utility_table.removeRow(row)

    def _on_utility_delete_all_clicked(self) -> None:
        if self.tsp is None or not self.tsp.utility_streams:
            QMessageBox.information(
                self, "Delete all utilities", "There are no utility streams to delete."
            )
            return
        answer = QMessageBox.question(
            self,
            "Delete all utilities",
            f"Delete all {len(self.tsp.utility_streams)} utility streams?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.tsp.clear_utility_streams()
        self.utility_table.setRowCount(0)

    # -- table handling -------------------------------------------------

    def _append_utility_row(self, utility: UtilityStream) -> None:
        row = self.utility_table.rowCount()
        self.utility_table.insertRow(row)
        self._set_utility_row(row, utility)

    def _set_utility_row(self, row: int, utility: UtilityStream) -> None:
        self._updating = True
        try:
            name_item = QTableWidgetItem(utility.name)
            temp_item = QTableWidgetItem(f"{utility.temperature:g}")
            temp_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.utility_table.setItem(row, 0, name_item)
            self.utility_table.setItem(row, 1, temp_item)
        finally:
            self._updating = False

    def _on_utility_cell_changed(self, item: QTableWidgetItem) -> None:
        if self._updating or self.tsp is None:
            return
        row, col = item.row(), item.column()
        utility = self.tsp.utility_streams[row]
        text = item.text().strip()
        try:
            if col == 0:  # Name
                utility.name = text
            elif col == 1:  # Temperature
                value = float(text)
                if not math.isfinite(value):
                    raise ValueError("temperature must be a finite number")
                utility.temperature = value
            else:
                return
        except ValueError as exc:
            self._set_utility_row(row, utility)  # revert the cell
            QMessageBox.warning(self, "Invalid value", str(exc))
            return
        # Refresh the row so values are formatted consistently.
        self._set_utility_row(row, utility)

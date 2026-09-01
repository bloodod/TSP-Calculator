"""Total Site Profile page: composite curves mirrored on the energy axis.

The cold composite lies on the positive energy side, the hot composite on
the negative side; both start at energy 0 (cold at its lowest temperature,
hot at its highest). A narrow panel on the right holds the utility streams:
a table of the added utility streams above, and the input (name and
temperature in C) below.
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backend import TotalSiteProfile, TotalSiteProfileCurves, UtilityStream, build_tsp_curves

HOT_COLOR = "#C0392B"
COLD_COLOR = "#2471A3"


class TspPage(QWidget):
    """Total site profile: cold composite on +energy, hot on -energy."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)

        body = QHBoxLayout()
        body.setSpacing(8)
        self.figure = Figure(figsize=(7, 5), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        body.addWidget(self.canvas, 9)
        body.addLayout(self._build_utility_panel(), 1)
        root.addLayout(body, 1)

        self.curves: TotalSiteProfileCurves | None = None
        self.tsp: TotalSiteProfile | None = None
        self._delta_t_min = 0.0
        self._placeholder()

    def _build_utility_panel(self) -> QVBoxLayout:
        panel = QVBoxLayout()
        panel.setSpacing(6)

        panel.addWidget(QLabel("Utility streams"))

        # Table of the utility streams, above the input.
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
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        panel.addWidget(self.utility_table, 1)

        # Input for a new utility stream, below the table.
        form = QFormLayout()
        self.utility_name_edit = QLineEdit()
        form.addRow("Name:", self.utility_name_edit)

        self.utility_temp_spin = QDoubleSpinBox()
        self.utility_temp_spin.setRange(-1000.0, 2000.0)
        self.utility_temp_spin.setDecimals(2)
        form.addRow("Temperature (\u00b0C):", self.utility_temp_spin)
        panel.addLayout(form)

        self.utility_add_button = QPushButton("Add utility")
        self.utility_add_button.clicked.connect(self._on_utility_add_clicked)
        panel.addWidget(self.utility_add_button)

        return panel

    def refresh(self, tsp: TotalSiteProfile) -> None:
        """Rebuild and redraw the profile from the profile's streams."""
        self.tsp = tsp
        self._delta_t_min = tsp.delta_t_min
        self.curves = (
            build_tsp_curves(tsp.streams, tsp.delta_t_min) if tsp.streams else None
        )
        if self.curves is None or (
            not self.curves.hot.enthalpy and not self.curves.cold.enthalpy
        ):
            self._placeholder()
            return
        self._plot()

    def _on_utility_add_clicked(self) -> None:
        """Add the entered utility stream to the profile and the table."""
        name = self.utility_name_edit.text().strip()
        utility = UtilityStream(
            name=name, temperature=self.utility_temp_spin.value()
        )
        self.tsp.add_utility_stream(utility)

        row = self.utility_table.rowCount()
        self.utility_table.insertRow(row)
        self.utility_table.setItem(row, 0, QTableWidgetItem(name))
        self.utility_table.setItem(
            row, 1, QTableWidgetItem(f"{utility.temperature:g}")
        )

        self.utility_name_edit.clear()
        self.utility_name_edit.setFocus()

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
        if self.curves.hot.enthalpy:
            ax.plot(
                self.curves.hot.enthalpy,
                self.curves.hot.temperatures,
                color=HOT_COLOR,
                linewidth=2.4,
                marker="x",
                markersize=5,
                label=f"Hot composite ({abs(self.curves.hot.total_enthalpy):g} kW)",
            )
        if self.curves.cold.enthalpy:
            ax.plot(
                self.curves.cold.enthalpy,
                self.curves.cold.temperatures,
                color=COLD_COLOR,
                linewidth=2.4,
                marker="o",
                markersize=4,
                label=f"Cold composite ({self.curves.cold.total_enthalpy:g} kW)",
            )
        ax.axvline(0.0, color="gray", linestyle="--", linewidth=0.8)
        ax.set_xlabel("Energy (kW)")
        ax.set_ylabel("Temperature (\u00b0C)")
        ax.set_title(
            f"Total Site Profile (\u0394T min = {self._delta_t_min:g} \u00b0C)"
        )
        ax.grid(True, linestyle=":", alpha=0.4)
        ax.legend(frameon=False)
        self.canvas.draw()

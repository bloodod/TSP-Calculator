"""Grand Composite Curve page: the combined PTA heat cascade vs temperature.

The GCC plots the heat cascade from the combined problem table against the
shifted temperature: it starts at the minimum hot utility at the top,
touches zero at the pinch and ends at the minimum cold utility at the
bottom. In the side panel under the figure options, one table lists every
point of the curve (enthalpy and temperature).
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backend import GrandCompositeCurve, TotalSiteProfile, build_gcc

from .figure_controls import FigureControls, ScrollableCanvas

CURVE_COLOR = "#2C3E50"
FILL_COLOR = "#AED6F1"
PINCH_COLOR = "#C0392B"


class GccPage(QWidget):
    """A matplotlib page showing the grand composite curve."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        body = QHBoxLayout()
        body.setSpacing(8)
        self.figure = Figure(figsize=(7, 5), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas_view = ScrollableCanvas(self.canvas)
        body.addWidget(self.canvas_view, 1)
        self.controls = FigureControls(
            self.figure,
            canvas_host=self.canvas_view,
            default_size=(7.0, 5.0),
            show_cursor=True,
        )
        self.controls.points_toggled.connect(self._on_points_toggled)
        self.controls.point_color_changed.connect(self._on_point_color_changed)

        # Side column: figure options on top, the curve point table under
        # them, like on the composite curves page.
        right_column = QWidget()
        column = QVBoxLayout(right_column)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        column.addWidget(self.controls, 1)
        self.points_table = QTableWidget(0, 2)
        self.points_table.setHorizontalHeaderLabels(
            ["Enthalpy (kW)", "Temperature (\u00b0C)"]
        )
        self.points_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.points_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.points_table.setFixedHeight(60)
        column.addWidget(self.points_table)
        body.addWidget(right_column, 0)
        layout.addLayout(body, 1)

        self.gcc: GrandCompositeCurve | None = None
        self._placeholder()

    def refresh(self, tsp: TotalSiteProfile) -> None:
        """Rebuild and redraw the GCC from the profile's streams."""
        self.gcc = build_gcc(tsp.streams, tsp.delta_t_min) if tsp.streams else None
        if self.gcc is None or not self.gcc.heat_flow:
            self._placeholder()
            self._reload_points_table()
            return
        self._plot()
        self._reload_points_table()

    def _reload_points_table(self) -> None:
        """(Re)fill the table with every point of the GCC curve."""
        self.points_table.setRowCount(0)
        if self.gcc is not None and self.gcc.heat_flow:
            for q, t in zip(self.gcc.heat_flow, self.gcc.temperatures):
                row = self.points_table.rowCount()
                self.points_table.insertRow(row)
                for col, value in enumerate((q, t)):
                    item = QTableWidgetItem(f"{value:g}")
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                    self.points_table.setItem(row, col, item)

        # Size the table to its content (up to a cap); it scrolls if the
        # GCC has more points than fit.
        header = self.points_table.horizontalHeader().height()
        per_row = self.points_table.verticalHeader().defaultSectionSize()
        height = header + self.points_table.rowCount() * per_row
        self.points_table.setFixedHeight(max(min(height + 8, 170), 60))

    def _placeholder(self) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            "Add streams to see the grand composite curve",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color="gray",
            fontsize=12,
        )
        ax.set_axis_off()
        self.canvas.draw()

    def _on_points_toggled(self, checked: bool) -> None:
        if self.gcc is not None and self.gcc.heat_flow:
            self._plot()

    def _on_point_color_changed(self, _color: str) -> None:
        """Redraw so the markers pick up the newly chosen point color."""
        self._on_points_toggled(True)

    def _plot(self) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        q = self.gcc.heat_flow
        t = self.gcc.temperatures

        marker_kwargs = {}
        if self.controls.points_enabled():
            marker_kwargs = dict(
                marker="x",
                markersize=4,
                markeredgecolor=self.controls.point_color(),
                markerfacecolor=self.controls.point_color(),
            )

        ax.fill_betweenx(t, 0.0, q, color=FILL_COLOR, alpha=0.5)
        ax.plot(
            q,
            t,
            color=CURVE_COLOR,
            linewidth=2.4,
            **marker_kwargs,
        )

        span = (t[0] - t[-1]) if len(t) > 1 else 1.0
        dy = max(span * 0.04, 1.0)

        # Utility targets at the two ends of the cascade.
        ax.text(
            q[0], t[0] + dy,
            f"QH,min = {q[0]:g} kW",
            ha="center", va="bottom", fontsize=9, color=CURVE_COLOR,
        )
        ax.text(
            q[-1], t[-1] - dy,
            f"QC,min = {q[-1]:g} kW",
            ha="center", va="top", fontsize=9, color=CURVE_COLOR,
        )

        # Pinch: where the cascade is zero.
        if self.gcc.pinch_temperature is not None:
            pinch_t = self.gcc.pinch_temperature
            ax.axhline(pinch_t, color=PINCH_COLOR, linestyle="--", linewidth=1.1)
            ax.plot([0.0], [pinch_t], "o", color=PINCH_COLOR, markersize=5)
            ax.text(
                0.99, pinch_t,
                f"Pinch = {pinch_t:g} \u00b0C (shifted)",
                ha="right", va="bottom", fontsize=8, color=PINCH_COLOR,
                transform=ax.get_yaxis_transform(),
            )

        ax.set_xlabel("Heat flow (kW)")
        ax.set_ylabel("Shifted temperature (\u00b0C)")
        ax.set_title("Grand Composite Curve")
        ax.grid(True, linestyle=":", alpha=0.4)
        self.controls.refresh_annotations()
        self.canvas.draw()

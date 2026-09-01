"""Site Utility Grand Composite Curve (SUGCC) page.

After the TSP shift, the areas enclosed between the vertical utility stream
lines of the hot and cold staircases become horizontal bars: for each
temperature interval between consecutive utilities, a bar from energy 0 to
the net heat (the shifted horizontal distance between the verticals). The
plot shows those bars against temperature.

To the right of the plot, a table gives the cogeneration targets: each
expansion zone (named after its bounding utilities, e.g. "g/f") with its
temperature span, net heat Q and cogeneration target
W = 0.00133 * delta T * Q, plus a total row.
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backend import (
    CARNOT_FACTOR,
    CogenerationRow,
    SugccSegment,
    TotalSiteProfile,
    build_cogeneration_table,
    build_sugcc,
    build_tsp_curves,
    cold_utility_staircase,
    tsp_shift_amount,
    utility_staircase,
)

BAR_COLOR = "#117A65"
BAR_FILL = "#D5F5E3"


class SugccPage(QWidget):
    """A matplotlib page showing the site utility grand composite curve."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rows: list[CogenerationRow] = []

        root = QVBoxLayout(self)
        body = QHBoxLayout()
        body.setSpacing(8)
        body.addWidget(self._build_plot(), 7)
        body.addWidget(self._build_targets_panel(), 3)
        root.addLayout(body, 1)

        self.segments: list[SugccSegment] | None = None
        self._shift: float | None = None
        self._placeholder()

    # ------------------------------------------------------------------
    # Panels
    # ------------------------------------------------------------------

    def _build_plot(self) -> QWidget:
        self.figure = Figure(figsize=(7, 5), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        return self.canvas

    def _build_targets_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        title = QLabel("Cogeneration targets")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        self.target_table = QTableWidget(0, 6)
        self.target_table.setHorizontalHeaderLabels(
            [
                "Expansion zone",
                "T high (\u00b0C)",
                "T low (\u00b0C)",
                "\u0394T (\u00b0C)",
                "Q (kW)",
                "W (kW)",
            ]
        )
        self.target_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.target_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.target_table.verticalHeader().setVisible(False)
        layout.addWidget(self.target_table, 1)

        note = QLabel(f"W = {CARNOT_FACTOR:g} \u00b7 \u0394T \u00b7 Q (Carnot factor)")
        note.setStyleSheet("color: gray;")
        note.setWordWrap(True)
        layout.addWidget(note)
        return panel

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self, tsp: TotalSiteProfile) -> None:
        """Rebuild the SUGCC and the cogeneration table from the profile."""
        self.segments = None
        self._shift = None
        self.rows = []
        self.target_table.setRowCount(0)
        if tsp is None or not tsp.utility_streams:
            self._placeholder()
            return
        curves = (
            build_tsp_curves(tsp.streams, tsp.delta_t_min) if tsp.streams else None
        )
        if curves is None:
            self._placeholder()
            return
        temps = [u.temperature for u in tsp.utility_streams]
        hot_steps = (
            utility_staircase(curves.hot, temps) if curves.hot.enthalpy else []
        )
        cold_steps = (
            cold_utility_staircase(curves.cold, temps) if curves.cold.enthalpy else []
        )
        shift = tsp_shift_amount(hot_steps, cold_steps)
        if shift is None:
            self._placeholder()
            return
        self._shift = shift
        self.segments = build_sugcc(hot_steps, cold_steps, shift)
        self.rows = build_cogeneration_table(self.segments, tsp.utility_streams)
        self._reload_target_table()
        self._plot()

    def _reload_target_table(self) -> None:
        total_q = 0.0
        total_w = 0.0
        for row in self.rows:
            r = self.target_table.rowCount()
            self.target_table.insertRow(r)
            values = [
                row.zone,
                f"{row.t_high:g}",
                f"{row.t_low:g}",
                f"{row.delta_t:g}",
                f"{row.heat:g}",
                f"{row.power:g}",
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col >= 1:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.target_table.setItem(r, col, item)
            total_q += row.heat
            total_w += row.power

        r = self.target_table.rowCount()
        self.target_table.insertRow(r)
        bold = QFont()
        bold.setBold(True)
        total_items = ["Total", "", "", "", f"{total_q:g}", f"{total_w:g}"]
        for col, text in enumerate(total_items):
            item = QTableWidgetItem(text)
            if col >= 1:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            item.setFont(bold)
            self.target_table.setItem(r, col, item)

    def _placeholder(self) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            "Enable TSP Shift with streams and utilities to see the SUGCC",
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

        temps = []
        for seg in self.segments:
            width = seg.heat
            temps.extend((seg.t_low, seg.t_high))
            if width <= 1e-9:
                continue  # the touching interval has no area
            height = seg.t_high - seg.t_low
            ax.add_patch(
                Rectangle(
                    (0.0, seg.t_low),
                    width,
                    height,
                    facecolor=BAR_FILL,
                    edgecolor=BAR_COLOR,
                    linewidth=1.4,
                )
            )
            ax.text(
                width,
                (seg.t_low + seg.t_high) / 2,
                f"{width:g}",
                ha="left",
                va="center",
                fontsize=8,
                color=BAR_COLOR,
            )

        ax.set_xlim(0, max((s.heat for s in self.segments), default=1.0) * 1.15)
        ax.set_ylim(min(temps) - 5, max(temps) + 5)
        ax.set_xlabel("Energy (kW)")
        ax.set_ylabel("Temperature (\u00b0C)")
        ax.set_title(
            "Site Utility Grand Composite Curve "
            f"(TSP shift = {self._shift:g} kW)"
        )
        ax.grid(True, linestyle=":", alpha=0.4)
        self.canvas.draw()

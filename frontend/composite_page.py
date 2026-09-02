"""Composite curves page: plots the hot and cold composite curves.

The curves are rebuilt from the :class:`backend.TotalSiteProfile` model on
every :meth:`refresh`. The view uses the combined problem table: the cold
composite is shifted right by exactly QC,min and the QH,min / QC,min amounts
are drawn as arrows next to the curves. The curves themselves are never
extended: with delta_t_min = 0 they touch at the pinch, with delta_t_min > 0
the smallest vertical gap equals delta_t_min.

Hot composite is drawn with x markers, cold composite with o markers. The
QH,min arrow starts at the top of whichever curve is higher in temperature;
the QC,min arrow starts at the bottom of whichever curve is lower. An arrow
anchored on the hot composite gets its label above (QH,min) or below
(QC,min); anchored on the cold composite the sides are swapped. Arrows and
labels are dark grey and can be hidden with the "Show utility arrows"
option. Point coordinate labels sit to the left of the hot-composite points
and to the right of the cold-composite points, so each label shows clear of
its curve. In the side panel under the figure options, one table lists
every vertex of both curves, split into HOT COMPOSITE and COLD
COMPOSITE sections, listing the enthalpy (kW)
and temperature (\u00b0C) of each point.
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

from backend import (
    CompositeCurve,
    TotalSiteProfile,
    UtilityTargets,
    build_composite,
    build_utility_targets,
    StreamKind,
)

from .figure_controls import FigureControls, ScrollableCanvas

HOT_COLOR = "#C0392B"
COLD_COLOR = "#2471A3"
UTILITY_ARROW_COLOR = "#404040"  # dark grey, arrows and their labels


class CompositePage(QWidget):
    """A matplotlib page showing the site's composite curves."""

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
            show_utilities=True,
            # hot composite ('x') labels sit fully to the left of the point
            # (right-anchored), cold ('o') labels fully to the right.
            marker_offsets={
                "x": (-6, 3, "right"),
                "o": (6, 3, "left"),
            },
        )
        self.controls.points_toggled.connect(self._on_points_toggled)
        self.controls.point_color_changed.connect(self._on_point_color_changed)
        self.controls.utilities_toggled.connect(self._on_utilities_toggled)

        # Side column: figure options on top, the vertex table under them.
        # One table, hot and cold sections, with the x (enthalpy) and the
        # y (temperature) of every curve point.
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

        self.hot_curve: CompositeCurve | None = None
        self.cold_curve: CompositeCurve | None = None
        self.utilities: UtilityTargets | None = None
        self._delta_t_min = 0.0
        self._placeholder()

    def refresh(self, tsp: TotalSiteProfile) -> None:
        """Rebuild and redraw the curves from the profile's streams."""
        self._delta_t_min = tsp.delta_t_min
        self.hot_curve = build_composite(tsp.streams, StreamKind.HOT)
        self.cold_curve = build_composite(tsp.streams, StreamKind.COLD)
        self.utilities = (
            build_utility_targets(tsp.streams, tsp.delta_t_min)
            if tsp.streams
            else None
        )
        if not self.hot_curve.enthalpy and not self.cold_curve.enthalpy:
            self._placeholder()
            self._reload_points_table()
            return
        self._plot()
        self._reload_points_table()

    def _reload_points_table(self) -> None:
        """(Re)fill the table with every vertex of both composite curves."""
        self.points_table.setRowCount(0)
        u = self.utilities
        if u is not None:
            for title, curve in (
                ("HOT COMPOSITE", u.hot),
                ("COLD COMPOSITE", u.cold),
            ):
                if not curve.enthalpy:
                    continue
                row = self.points_table.rowCount()
                self.points_table.insertRow(row)
                heading = QTableWidgetItem(title)
                heading.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                font = heading.font()
                font.setBold(True)
                heading.setFont(font)
                self.points_table.setItem(row, 0, heading)
                self.points_table.setSpan(row, 0, 1, 2)
                for x, y in zip(curve.enthalpy, curve.temperatures):
                    row = self.points_table.rowCount()
                    self.points_table.insertRow(row)
                    for col, value in enumerate((x, y)):
                        item = QTableWidgetItem(f"{value:g}")
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight
                            | Qt.AlignmentFlag.AlignVCenter
                        )
                        self.points_table.setItem(row, col, item)

        # Size the table to its content (up to a cap); it scrolls if the
        # composite has more vertices than fit.
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
            "Add streams to see the composite curves",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color="gray",
            fontsize=12,
        )
        ax.set_axis_off()
        self.canvas.draw()

    def _on_points_toggled(self, checked: bool) -> None:
        if self.hot_curve is not None and (
            self.hot_curve.enthalpy or self.cold_curve.enthalpy
        ):
            self._plot()

    def _on_point_color_changed(self, _color: str) -> None:
        """Redraw so the markers pick up the newly chosen point color."""
        self._on_points_toggled(True)

    def _on_utilities_toggled(self, checked: bool) -> None:
        """Redraw so the utility arrows appear or disappear."""
        self._on_points_toggled(True)

    def _plot(self) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        self._plot_utilities(ax)

        ax.set_xlabel("Enthalpy (kW)")
        ax.set_ylabel("Temperature (\u00b0C)")
        ax.set_title(
            f"Composite curves with \u0394T min of {self._delta_t_min:g} \u00b0C"
        )
        ax.grid(True, linestyle=":", alpha=0.4)
        ax.legend(frameon=False)
        self.controls.refresh_annotations()
        self.canvas.draw()

    def _plot_utilities(self, ax) -> None:
        u = self.utilities
        hot_marker = self._point_marker("x", 5)
        cold_marker = self._point_marker("o", 4)
        if u.hot.enthalpy:
            ax.plot(
                u.hot.enthalpy,
                u.hot.temperatures,
                color=HOT_COLOR,
                linewidth=2.4,
                **hot_marker,
                label=f"Hot composite + QH,min = {u.min_hot:g} kW",
            )
        if u.cold.enthalpy:
            ax.plot(
                u.cold.enthalpy,
                u.cold.temperatures,
                color=COLD_COLOR,
                linewidth=2.4,
                **cold_marker,
                label=f"Cold composite + QC,min = {u.min_cold:g} kW",
            )

        span = self._temperature_span()
        dy = max(span * 0.04, 1.0)
        show_arrows = self.controls.utilities_enabled()

        # QH,min: arrow starts at the top of whichever curve is higher on T.
        # Anchored on the hot composite it points right; on the cold
        # composite it points left. Its label goes above the arrow when
        # anchored on hot, below it when anchored on cold.
        if u.min_hot > 0 and show_arrows:
            anchor = self._top_anchor(u)
            if anchor is not None:
                x0, t0, on_hot = anchor
                x1 = x0 + u.min_hot if on_hot else x0 - u.min_hot
                y, va = (t0 + dy, "bottom") if on_hot else (t0 - dy, "top")
                ax.annotate(
                    "",
                    xy=(x1, t0),
                    xytext=(x0, t0),
                    arrowprops=dict(
                        arrowstyle="<->",
                        color=UTILITY_ARROW_COLOR,
                        lw=1.1,
                    ),
                )
                ax.text(
                    (x0 + x1) / 2, y,
                    f"QH,min = {u.min_hot:g} kW",
                    ha="center", va=va, fontsize=8,
                    color=UTILITY_ARROW_COLOR,
                )

        # QC,min: arrow starts at the bottom of whichever curve is lower on T.
        # Anchored on the hot composite it points right; on the cold
        # composite it points left (back to x = 0). Its label goes below the
        # arrow when anchored on hot, above it when anchored on cold.
        if u.min_cold > 0 and show_arrows:
            anchor = self._bottom_anchor(u)
            if anchor is not None:
                x0, t0, on_hot = anchor
                x1 = x0 + u.min_cold if on_hot else x0 - u.min_cold
                y, va = (t0 - dy, "top") if on_hot else (t0 + dy, "bottom")
                ax.annotate(
                    "",
                    xy=(x1, t0),
                    xytext=(x0, t0),
                    arrowprops=dict(
                        arrowstyle="<->",
                        color=UTILITY_ARROW_COLOR,
                        lw=1.1,
                    ),
                )
                ax.text(
                    (x0 + x1) / 2, y,
                    f"QC,min = {u.min_cold:g} kW",
                    ha="center", va=va, fontsize=8,
                    color=UTILITY_ARROW_COLOR,
                )

    def _point_marker(self, marker: str, size: int) -> dict:
        """Marker kwargs for the data points toggle (chosen point color)."""
        if not self.controls.points_enabled():
            return {}
        color = self.controls.point_color()
        return {
            "marker": marker,
            "markersize": size,
            "markeredgecolor": color,
            "markerfacecolor": color,
        }

    def _top_anchor(self, u: UtilityTargets) -> tuple[float, float, bool] | None:
        """(x, T, on_hot) at the top of whichever curve ends higher on T."""
        candidates = []
        if u.hot.enthalpy:
            candidates.append((u.hot.total_enthalpy, u.hot.temperatures[-1], True))
        if u.cold.enthalpy:
            candidates.append((u.cold.total_enthalpy, u.cold.temperatures[-1], False))
        return max(candidates, key=lambda p: p[1]) if candidates else None

    def _bottom_anchor(self, u: UtilityTargets) -> tuple[float, float, bool] | None:
        """(x, T, on_hot) at the bottom of whichever curve starts lower on T."""
        candidates = []
        if u.hot.enthalpy:
            candidates.append((0.0, u.hot.temperatures[0], True))
        if u.cold.enthalpy:
            candidates.append((u.min_cold, u.cold.temperatures[0], False))
        return min(candidates, key=lambda p: p[1]) if candidates else None

    def _temperature_span(self) -> float:
        temps = []
        if self.hot_curve and self.hot_curve.temperatures:
            temps.extend(self.hot_curve.temperatures)
        if self.cold_curve and self.cold_curve.temperatures:
            temps.extend(self.cold_curve.temperatures)
        return (max(temps) - min(temps)) if temps else 0.0

"""Composite curves page: plots the hot and cold composite curves.

The curves are rebuilt from the :class:`backend.TotalSiteProfile` model on
every :meth:`refresh`. The view uses the combined problem table: the cold
composite is shifted right by exactly QC,min and the QH,min / QC,min amounts
are drawn as arrows next to the curves. The curves themselves are never
extended: with delta_t_min = 0 they touch at the pinch, with delta_t_min > 0
the smallest vertical gap equals delta_t_min.

Hot composite is drawn with x markers, cold composite with o markers. The
QH,min arrow starts at the top of whichever curve is higher in temperature;
the QC,min arrow starts at the bottom of whichever curve is lower.
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from backend import (
    CompositeCurve,
    TotalSiteProfile,
    UtilityTargets,
    build_composite,
    build_utility_targets,
    StreamKind,
)

HOT_COLOR = "#C0392B"
COLD_COLOR = "#2471A3"


class CompositePage(QWidget):
    """A matplotlib page showing the site's composite curves."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.figure = Figure(figsize=(7, 5), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas, 1)

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
            return
        self._plot()

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
        self.canvas.draw()

    def _plot_utilities(self, ax) -> None:
        u = self.utilities
        if u.hot.enthalpy:
            ax.plot(
                u.hot.enthalpy,
                u.hot.temperatures,
                color=HOT_COLOR,
                linewidth=2.4,
                marker="x",
                markersize=5,
                label=f"Hot composite + QH,min = {u.min_hot:g} kW",
            )
        if u.cold.enthalpy:
            ax.plot(
                u.cold.enthalpy,
                u.cold.temperatures,
                color=COLD_COLOR,
                linewidth=2.4,
                marker="o",
                markersize=4,
                label=f"Cold composite + QC,min = {u.min_cold:g} kW",
            )

        span = self._temperature_span()
        dy = max(span * 0.04, 1.0)

        # QH,min: arrow starts at the top of whichever curve is higher on T.
        # Anchored on the hot composite it points right; on the cold
        # composite it points left.
        if u.min_hot > 0:
            anchor = self._top_anchor(u)
            if anchor is not None:
                x0, t0, on_hot = anchor
                x1 = x0 + u.min_hot if on_hot else x0 - u.min_hot
                ax.annotate(
                    "",
                    xy=(x1, t0),
                    xytext=(x0, t0),
                    arrowprops=dict(arrowstyle="<->", color="gray", lw=1.1),
                )
                ax.text(
                    (x0 + x1) / 2, t0 + dy,
                    f"QH,min = {u.min_hot:g} kW",
                    ha="center", va="bottom", fontsize=8, color="gray",
                )

        # QC,min: arrow starts at the bottom of whichever curve is lower on T.
        # Anchored on the hot composite it points right; on the cold
        # composite it points left (back to x = 0).
        if u.min_cold > 0:
            anchor = self._bottom_anchor(u)
            if anchor is not None:
                x0, t0, on_hot = anchor
                x1 = x0 + u.min_cold if on_hot else x0 - u.min_cold
                ax.annotate(
                    "",
                    xy=(x1, t0),
                    xytext=(x0, t0),
                    arrowprops=dict(arrowstyle="<->", color="gray", lw=1.1),
                )
                ax.text(
                    (x0 + x1) / 2, t0 - dy,
                    f"QC,min = {u.min_cold:g} kW",
                    ha="center", va="top", fontsize=8, color="gray",
                )

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

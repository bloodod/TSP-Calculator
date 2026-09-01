"""Grand Composite Curve page: the combined PTA heat cascade vs temperature.

The GCC plots the heat cascade from the combined problem table against the
shifted temperature: it starts at the minimum hot utility at the top,
touches zero at the pinch and ends at the minimum cold utility at the
bottom.
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from backend import GrandCompositeCurve, TotalSiteProfile, build_gcc

CURVE_COLOR = "#2C3E50"
FILL_COLOR = "#AED6F1"
PINCH_COLOR = "#C0392B"


class GccPage(QWidget):
    """A matplotlib page showing the grand composite curve."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.figure = Figure(figsize=(7, 5), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas, 1)

        self.gcc: GrandCompositeCurve | None = None
        self._placeholder()

    def refresh(self, tsp: TotalSiteProfile) -> None:
        """Rebuild and redraw the GCC from the profile's streams."""
        self.gcc = build_gcc(tsp.streams, tsp.delta_t_min) if tsp.streams else None
        if self.gcc is None or not self.gcc.heat_flow:
            self._placeholder()
            return
        self._plot()

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

    def _plot(self) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        q = self.gcc.heat_flow
        t = self.gcc.temperatures

        ax.fill_betweenx(t, 0.0, q, color=FILL_COLOR, alpha=0.5)
        ax.plot(q, t, color=CURVE_COLOR, linewidth=2.4)

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
        self.canvas.draw()

"""Problem Table Algorithm page: box diagram of the heat cascade.

Each temperature interval is drawn as a box whose height is proportional to
the interval width (the y axis is the shifted temperature), labelled with
its net CP and heat flow. On the right, arrows cascade the heat down level
by level with the cascade value at each level. The combined table also shows
the minimum hot utility entering at the top and the pinch level(s).
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from backend import ProblemTable, TotalSiteProfile, problem_table

from .figure_controls import FigureControls, ScrollableCanvas

HOT_FILL = "#FADBD8"  # light red
COLD_FILL = "#D6EAF8"  # light blue
COMBINED_FILL = "#EAECEE"  # light gray
EDGE = "#2C3E50"
PINCH_COLOR = "#C0392B"

FILLS = {"hot": HOT_FILL, "cold": COLD_FILL, "combined": COMBINED_FILL}

BOX_LEFT, BOX_RIGHT = 0.5, 5.0
CASCADE_X = 6.3
LABEL_X = 6.8
NOTE_X = 8.4


class PtaPage(QWidget):
    """Box-cascade visualization of the hot, cold or combined PTA."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        selector = QHBoxLayout()
        selector.addWidget(QLabel("Problem table:"))
        self.kind_combo = QComboBox()
        self.kind_combo.addItems(["Hot", "Cold", "Combined"])
        self.kind_combo.currentTextChanged.connect(self._on_kind_changed)
        selector.addWidget(self.kind_combo)
        selector.addStretch(1)
        layout.addLayout(selector)

        self.figure = Figure(figsize=(5.5, 7), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)

        body = QHBoxLayout()
        body.setSpacing(8)
        self.canvas_view = ScrollableCanvas(self.canvas)
        body.addWidget(self.canvas_view, 1)
        self.controls = FigureControls(
            self.figure,
            canvas_host=self.canvas_view,
            default_size=(5.5, 7.0),
        )
        body.addWidget(self.controls, 0)
        layout.addLayout(body, 1)

        self.tsp: TotalSiteProfile | None = None
        self.result: ProblemTable | None = None
        self._placeholder()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self, tsp: TotalSiteProfile) -> None:
        """Recompute the selected problem table from the profile's streams."""
        self.tsp = tsp
        kind = self.kind_combo.currentText().lower()
        self.result = problem_table(tsp.streams, kind, tsp.delta_t_min)
        if not self.result.intervals:
            self._placeholder()
            return
        self._plot()

    def _on_kind_changed(self, _text: str) -> None:
        if self.tsp is not None:
            self.refresh(self.tsp)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _placeholder(self) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            "Add streams to see the problem table",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color="gray",
            fontsize=12,
        )
        ax.set_axis_off()
        self.canvas.draw()

    def _plot(self) -> None:
        pt = self.result
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        span = pt.levels[0] - pt.levels[-1]
        pad = 0.06 * span if span else 1.0

        # -- interval boxes ------------------------------------------------
        for iv in pt.intervals:
            height = iv.t_high - iv.t_low
            ax.add_patch(
                Rectangle(
                    (BOX_LEFT, iv.t_low),
                    BOX_RIGHT - BOX_LEFT,
                    height,
                    facecolor=FILLS[pt.kind],
                    edgecolor=EDGE,
                    linewidth=1.2,
                    zorder=2,
                )
            )
            ax.text(
                (BOX_LEFT + BOX_RIGHT) / 2,
                (iv.t_low + iv.t_high) / 2,
                f"{iv.index}\n\u03a3CP = {iv.cp_sum:g} kW/\u00b0C\n"
                f"\u0394H = {iv.delta_h:g} kW",
                ha="center",
                va="center",
                fontsize=8,
                zorder=3,
            )

        # -- cascade arrows and values -------------------------------------
        for i in range(len(pt.levels) - 1):
            ax.annotate(
                "",
                xy=(CASCADE_X, pt.levels[i + 1]),
                xytext=(CASCADE_X, pt.levels[i]),
                arrowprops=dict(arrowstyle="-|>", color=EDGE, lw=1.4),
                zorder=4,
            )
        for i, value in enumerate(pt.cascade):
            ax.text(
                LABEL_X,
                pt.levels[i],
                f"{value:g}",
                va="center",
                fontsize=9,
                zorder=5,
            )

        # -- combined extras: hot utility at the top, pinch level(s) -------
        if pt.kind == "combined":
            if pt.min_hot_utility > 0:
                top = pt.levels[0]
                ax.annotate(
                    "",
                    xy=(CASCADE_X, top),
                    xytext=(CASCADE_X, top + 0.5 * pad),
                    arrowprops=dict(arrowstyle="-|>", color=PINCH_COLOR, lw=1.6),
                    zorder=4,
                )
                ax.text(
                    LABEL_X,
                    top + 0.5 * pad,
                    f"+QH,min = {pt.min_hot_utility:g} kW",
                    va="bottom",
                    fontsize=9,
                    color=PINCH_COLOR,
                    zorder=5,
                )
            for pinch_t in pt.pinch_temperatures:
                ax.axhline(
                    pinch_t,
                    color=PINCH_COLOR,
                    linestyle="--",
                    linewidth=1.3,
                    zorder=1,
                )
                ax.text(
                    NOTE_X,
                    pinch_t,
                    "pinch",
                    va="center",
                    fontsize=9,
                    color=PINCH_COLOR,
                    zorder=5,
                )

        # -- axes and title -------------------------------------------------
        ax.set_xlim(0.0, 9.0)
        ax.set_ylim(pt.levels[-1] - pad, pt.levels[0] + pad)
        ax.set_yticks(pt.levels)
        ax.tick_params(labelsize=8)
        ax.set_xticks([])
        ax.set_ylabel("Shifted temperature (\u00b0C)")

        if pt.kind == "combined":
            title = (
                f"Problem table - {pt.kind.capitalize()}  "
                f"(\u0394T min = {pt.delta_t_min:g} \u00b0C)\n"
                f"QH,min = {pt.min_hot_utility:g} kW  ·  "
                f"QC,min = {pt.min_cold_utility:g} kW  ·  "
                f"Pinch at {pt.pinch_temperatures[0]:g} \u00b0C (shifted)"
            )
        else:
            title = (
                f"Problem table - {pt.kind.capitalize()}  "
                f"(\u0394T min = {pt.delta_t_min:g} \u00b0C)\n"
                f"Total {pt.kind} duty = {pt.total_duty:g} kW"
            )
        ax.set_title(title, fontsize=10)
        self.canvas.draw()

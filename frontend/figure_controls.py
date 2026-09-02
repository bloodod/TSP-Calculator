"""Shared figure controls: size, aspect ratio, point labels and export.

A small right-side panel attached to the plotting tabs:

* Width and height spinners (inches) resize the figure; with "keep aspect
  ratio" checked, changing one dimension scales the other proportionally.
  The spinners always mirror the figure's actual size.
* "Fit to tab" (default on) makes the figure follow the size of the tab and
  window (scrollbars appear when the pinned size exceeds the tab). Turning
  it off pins the figure to the manual size; scrollbars appear as needed.
* "Reset size" restores the figure's original default dimensions (and turns
  fit-to-tab off so the reset is visible).
* Optional "Show point coordinates": every plotted data point (the x and o
  markers) gets a small label with its (x, y) coordinates next to it.
* With point coordinates on, a "Point color" slider picks the green used by
  the markers and their labels, from the greenest green down to black.
* Optional "Show utility arrows" (composite page): draws or hides the
  QH,min / QC,min arrows with their labels.
* Image export with a PNG/JPG format choice.
"""

from __future__ import annotations

from matplotlib.figure import Figure
from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

# (display name, file extension)
EXPORT_FORMATS = [("PNG", "png"), ("JPG", "jpg")]

NEON_GREEN = "#39FF14"


def green_ramp(fraction: float) -> str:
    """Point color for ``fraction``: greenest green (0.0) to black (1.0)."""
    r, g, b = 0x39, 0xFF, 0x14
    t = max(0.0, min(1.0, fraction))
    return "#{:02X}{:02X}{:02X}".format(
        round(r * (1.0 - t)), round(g * (1.0 - t)), round(b * (1.0 - t))
    )


class ScrollableCanvas(QScrollArea):
    """Hosts a matplotlib canvas with horizontal and vertical scrollbars.

    With ``setWidgetResizable(True)`` the canvas fills the viewport (fit to
    tab); with ``False`` it keeps the figure's own size and scrollbars appear
    when the viewport is smaller.
    """

    def __init__(self, canvas: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setWidget(canvas)


class DataPointLabeler:
    """Labels the plotted data points (markers) with their coordinates.

    Every vertex of every marker-bearing line on the figure's axes gets a
    small "(x, y)" text next to it. ``offsets`` maps a marker character to
    its label placement as ``(dx, dy[, ha])`` -- an offset in points and an
    optional horizontal anchor ("left"/"right") -- so different curves can
    keep their labels fully on different sides of their points.
    """

    def __init__(
        self,
        figure: Figure,
        color: str = NEON_GREEN,
        offsets: dict | None = None,
    ) -> None:
        self.figure = figure
        self.color = color  # hex color used by the coordinate labels
        self.offsets = dict(offsets) if offsets else {}
        self.enabled = False
        self.labels: list = []

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.clear()

    def refresh(self) -> None:
        """(Re)label every marker point; call after the figure is redrawn."""
        if not self.enabled:
            return
        self.clear()
        for ax in self.figure.axes:
            for line in ax.lines:
                marker = line.get_marker()
                if marker in ("", "None", None):
                    continue
                for x, y in zip(line.get_xdata(), line.get_ydata()):
                    offset = self.offsets.get(marker, (3, 3, "left"))
                    dx, dy = offset[0], offset[1]
                    ha = offset[2] if len(offset) > 2 else "left"
                    self.labels.append(
                        ax.annotate(
                            f"({x:g}, {y:g})",
                            xy=(x, y),
                            xytext=(dx, dy),
                            textcoords="offset points",
                            ha=ha,
                            fontsize=7,
                            color=self.color,
                        )
                    )

    def clear(self) -> None:
        for label in self.labels:
            if label.axes is None:
                continue  # already detached by a figure redraw
            try:
                label.remove()
            except (ValueError, NotImplementedError):
                pass
        self.labels = []


class FigureControls(QWidget):
    """Resize a matplotlib figure, label data points and export it."""

    #: emitted when the "Show data points" toggle changes (checked state)
    points_toggled = pyqtSignal(bool)

    #: emitted when the point (marker/label) green changes (hex string)
    point_color_changed = pyqtSignal(str)

    #: emitted when the "Show utility arrows" toggle changes (checked state)
    utilities_toggled = pyqtSignal(bool)

    def __init__(
        self,
        figure: Figure,
        canvas_host: QScrollArea | None = None,
        default_size: tuple[float, float] | None = None,
        show_cursor: bool = False,
        show_utilities: bool = False,
        marker_offsets: dict | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.figure = figure
        self.canvas_host = canvas_host
        self.default_size = tuple(
            figure.get_size_inches() if default_size is None else default_size
        )
        self.tracker = (
            DataPointLabeler(figure, offsets=marker_offsets)
            if show_cursor
            else None
        )
        self._updating = False  # guards against feedback between the spinners

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Figure")
        form = QFormLayout(group)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(1.0, 40.0)
        self.width_spin.setDecimals(1)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.valueChanged.connect(self._on_width_changed)
        form.addRow("Width (in):", self.width_spin)

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(1.0, 40.0)
        self.height_spin.setDecimals(1)
        self.height_spin.setSingleStep(0.5)
        self.height_spin.valueChanged.connect(self._on_height_changed)
        form.addRow("Height (in):", self.height_spin)

        if self.tracker is not None:
            self.cursor_check = QCheckBox("Show data points")
            self.cursor_check.toggled.connect(self._on_cursor_toggled)
            self.cursor_check.setChecked(True)  # markers + coordinates on
            form.addRow(self.cursor_check)

            color_row = QWidget()
            color_layout = QHBoxLayout(color_row)
            color_layout.setContentsMargins(0, 0, 0, 0)
            self.green_slider = QSlider(Qt.Orientation.Horizontal)
            self.green_slider.setRange(0, 100)
            self.green_slider.setToolTip(
                "Green used for the data point markers and labels: "
                "greenest green (left) to black (right)."
            )
            self.green_slider.valueChanged.connect(self._on_green_changed)
            self.color_swatch = QLabel()
            self.color_swatch.setFixedSize(18, 14)
            color_layout.addWidget(self.green_slider, 1)
            color_layout.addWidget(self.color_swatch)
            form.addRow("Point color:", color_row)
            # Default to black; the change below also paints the swatch and
            # colours the tracker's labels.
            self.green_slider.setValue(100)

        if show_utilities:
            self.utilities_check = QCheckBox("Show utility arrows")
            self.utilities_check.setChecked(True)
            self.utilities_check.setToolTip(
                "Draw the QH,min and QC,min arrows showing the utility "
                "loads the site needs."
            )
            self.utilities_check.toggled.connect(self.utilities_toggled.emit)
            form.addRow(self.utilities_check)

        self.fit_check = QCheckBox("Fit to tab")
        self.fit_check.toggled.connect(self._on_fit_toggled)
        form.addRow(self.fit_check)

        self.aspect_check = QCheckBox("Keep aspect ratio")
        self.aspect_check.setChecked(True)
        form.addRow(self.aspect_check)

        self.reset_button = QPushButton("Reset size")
        self.reset_button.clicked.connect(self._on_reset)
        form.addRow(self.reset_button)

        export_row = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems([name for name, _ in EXPORT_FORMATS])
        self.export_button = QPushButton("Export image")
        self.export_button.clicked.connect(self._on_export)
        export_row.addWidget(self.format_combo)
        export_row.addWidget(self.export_button)
        form.addRow(export_row)

        layout.addWidget(group)
        layout.addStretch(1)

        # Watch the canvas: whenever the window/layout resizes it, mirror the
        # resulting figure size back into the spinners.
        canvas = self.figure.canvas
        if canvas is not None:
            canvas.installEventFilter(self)

        width, height = self.figure.get_size_inches()
        self._set_spins(width, height)
        self.fit_check.setChecked(True)  # triggers _on_fit_toggled

    # -- size changes ----------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        if obj is self.figure.canvas and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self._sync_from_figure)
        return super().eventFilter(obj, event)

    def _set_spins(self, width: float, height: float) -> None:
        self._updating = True
        try:
            self.width_spin.setValue(round(width, 1))
            self.height_spin.setValue(round(height, 1))
        finally:
            self._updating = False

    def _sync_from_figure(self) -> None:
        if self._updating:
            return
        width, height = self.figure.get_size_inches()
        self._set_spins(width, height)

    def _on_fit_toggled(self, checked: bool) -> None:
        if self.canvas_host is not None:
            self.canvas_host.setWidgetResizable(checked)
        if checked:
            QTimer.singleShot(0, self._sync_from_figure)

    def _on_width_changed(self, value: float) -> None:
        if self._updating:
            return
        if self.aspect_check.isChecked() and not self.fit_check.isChecked():
            w0, h0 = self.figure.get_size_inches()
            if w0 > 0:
                self._set_spins(value, round(value * h0 / w0, 1))
        self._apply_size()

    def _on_height_changed(self, value: float) -> None:
        if self._updating:
            return
        if self.aspect_check.isChecked() and not self.fit_check.isChecked():
            w0, h0 = self.figure.get_size_inches()
            if h0 > 0:
                self._set_spins(round(value * w0 / h0, 1), value)
        self._apply_size()

    def _apply_size(self) -> None:
        self.figure.set_size_inches(
            self.width_spin.value(), self.height_spin.value(), forward=True
        )
        canvas = self.figure.canvas
        if canvas is not None:
            canvas.draw_idle()

    def _on_reset(self) -> None:
        """Restore the original default dimensions (pinned, not fitted)."""
        self.fit_check.setChecked(False)
        self._set_spins(*self.default_size)
        self._apply_size()

    # -- data points ----------------------------------------------------

    def points_enabled(self) -> bool:
        """Whether the data point markers and their coordinates are shown."""
        return bool(self.tracker is not None and self.tracker.enabled)

    def refresh_annotations(self) -> None:
        """Re-label the data points; call after the page redraws its plot."""
        if self.tracker is not None:
            self.tracker.refresh()

    def _on_cursor_toggled(self, checked: bool) -> None:
        if self.tracker is not None:
            self.tracker.set_enabled(checked)
            self.points_toggled.emit(checked)
            canvas = self.figure.canvas
            if canvas is not None:
                canvas.draw_idle()

    # -- point color ------------------------------------------------------

    def point_color(self) -> str:
        """Current green used by the data point markers and their labels."""
        if self.tracker is None:
            return NEON_GREEN
        return green_ramp(self.green_slider.value() / 100.0)

    def _set_swatch(self, color: str) -> None:
        self.color_swatch.setStyleSheet(
            f"background-color: {color}; border: 1px solid #9aa0a6;"
        )

    def _on_green_changed(self, value: int) -> None:
        color = green_ramp(value / 100.0)
        if self.tracker is not None:
            self.tracker.color = color
        self._set_swatch(color)
        self.point_color_changed.emit(color)

    # -- utility arrows ---------------------------------------------------

    def utilities_enabled(self) -> bool:
        """Whether the QH,min / QC,min utility arrows should be drawn."""
        check = getattr(self, "utilities_check", None)
        return check is None or check.isChecked()

    # -- export ----------------------------------------------------------

    def _on_export(self) -> None:
        label, ext = EXPORT_FORMATS[self.format_combo.currentIndex()]
        path, _ = QFileDialog.getSaveFileName(
            self, "Export image", f"figure.{ext}", f"{label} image (*.{ext})"
        )
        if not path:
            return
        if not path.lower().endswith(f".{ext}"):
            path = f"{path}.{ext}"
        try:
            self.figure.savefig(path)
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return

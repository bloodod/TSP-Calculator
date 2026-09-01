"""Main window of the Total Site Profile calculator.

Layout: title bar at the top, stream input form on the left, and an editable
stream table on the right. The window keeps a backend
:class:`backend.TotalSiteProfile` model in sync with the table:

* Streams are auto-named H1, H2, ... for hot streams (cooling down) and
  C1, C2, ... for cold streams (heating up); freed numbers are reused so
  the sequence stays compact.
* The type (H/C) is derived from the temperatures and cannot be edited.
* Editing a duty cell (Energy or CP) makes that value the stream's given
  input; the other column is then recomputed from it.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backend import Stream, StreamKind, StreamValidationError, TotalSiteProfile

from .composite_page import CompositePage
from .gcc_page import GccPage
from .pta_page import PtaPage


def _fmt(value: float) -> str:
    """Compact decimal formatting for table cells."""
    return f"{value:g}"


def _parse_number(text: str, label: str) -> float:
    """Parse a table cell as a finite number or raise ValueError."""
    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"{label} must be a number, got {text!r}") from None
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return value


# Built-in demo data loaded by the Test button, as (tin, tout, cp).
TEST_STREAMS = [
    (200.0, 50.0, 10.0),  # hot
    (150.0, 100.0, 50.0),  # hot
    (120.0, 40.0, 20.0),  # hot
    (10.0, 100.0, 10.0),  # cold
    (70.0, 250.0, 20.0),  # cold
    (40.0, 150.0, 15.0),  # cold

]


class MainWindow(QMainWindow):
    """Front page of the calculator: inputs left, stream table right."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Total Site Profile Calculator")
        self.resize(1000, 620)
        self.setMinimumSize(860, 520)

        self.tsp = TotalSiteProfile()  # backend model kept in sync with the table
        self._updating = False  # guards itemChanged against refresh recursion

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setSpacing(12)

        self.title_label = QLabel("Total Site Profile Calculator")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        root.addWidget(self.title_label)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_streams_page(), "Streams")
        self.composite_page = CompositePage()
        self.tabs.addTab(self.composite_page, "Composite Curves")
        self.pta_page = PtaPage()
        self.tabs.addTab(self.pta_page, "Problem Table")
        self.gcc_page = GccPage()
        self.tabs.addTab(self.gcc_page, "GCC")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabs, 1)

        self.setCentralWidget(central)
        self.statusBar().showMessage("Ready")

    def _build_streams_page(self) -> QWidget:
        page = QWidget()
        body = QHBoxLayout(page)
        body.setSpacing(12)
        body.addWidget(self._build_input_panel(), 0)
        body.addWidget(self._build_table_panel(), 1)
        return page

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if widget is self.composite_page:
            self.composite_page.refresh(self.tsp)
        elif widget is self.pta_page:
            self.pta_page.refresh(self.tsp)
        elif widget is self.gcc_page:
            self.gcc_page.refresh(self.tsp)

    def _build_input_panel(self) -> QGroupBox:
        box = QGroupBox("Stream input")
        self.input_panel = box
        layout = QVBoxLayout(box)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.tin_spin = QDoubleSpinBox()
        self.tin_spin.setRange(-1000.0, 2000.0)
        self.tin_spin.setDecimals(2)
        self.tin_spin.valueChanged.connect(self._update_name_preview)
        form.addRow("Inlet temperature (°C):", self.tin_spin)

        self.tout_spin = QDoubleSpinBox()
        self.tout_spin.setRange(-1000.0, 2000.0)
        self.tout_spin.setDecimals(2)
        self.tout_spin.valueChanged.connect(self._update_name_preview)
        form.addRow("Outlet temperature (°C):", self.tout_spin)

        duty_row = QHBoxLayout()
        self.energy_radio = QRadioButton("Total energy (kW)")
        self.cp_radio = QRadioButton("Heat cap. flow (kW/°C)")
        self.cp_radio.setChecked(True)  # heat capacity flow is the default
        self.energy_radio.toggled.connect(self._update_duty_label)
        self.cp_radio.toggled.connect(self._update_duty_label)
        duty_row.addWidget(self.energy_radio)
        duty_row.addWidget(self.cp_radio)
        form.addRow("Duty input:", duty_row)

        self.duty_label = QLabel("Heat capacity flow rate (kW/°C)")
        self.duty_spin = QDoubleSpinBox()
        self.duty_spin.setRange(0.0, 1e9)
        self.duty_spin.setDecimals(2)
        form.addRow(self.duty_label, self.duty_spin)

        layout.addLayout(form)

        hint = QLabel(
            "Only one duty input is used: CP = Q / |Tout − Tin| "
            "when energy is given."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray;")
        layout.addWidget(hint)

        self.name_preview = QLabel("Will be added as: —")
        layout.addWidget(self.name_preview)

        self.add_button = QPushButton("Add stream")
        self.add_button.clicked.connect(self._on_add_clicked)
        layout.addWidget(self.add_button)

        # Enter anywhere in the input panel adds the stream.
        enter_shortcut = QShortcut(
            QKeySequence(Qt.Key.Key_Return),
            self.input_panel,
            activated=self._on_add_clicked,
        )
        enter_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        dt_form = QFormLayout()
        self.dtmin_spin = QDoubleSpinBox()
        self.dtmin_spin.setRange(0.0, 1000.0)
        self.dtmin_spin.setDecimals(2)
        self.dtmin_spin.setValue(0.0)
        self.dtmin_spin.valueChanged.connect(self._on_dtmin_changed)
        dt_form.addRow("ΔT min (°C):", self.dtmin_spin)
        layout.addLayout(dt_form)

        layout.addStretch(1)

        self.test_button = QPushButton("Test")
        self.test_button.clicked.connect(self._on_test_clicked)
        layout.addWidget(self.test_button)
        return box

    def _build_table_panel(self) -> QGroupBox:
        box = QGroupBox("Streams")
        layout = QVBoxLayout(box)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Type", "Tin (°C)", "Tout (°C)", "Energy (kW)", "CP (kW/°C)"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.itemChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table, 1)

        button_row = QHBoxLayout()
        self.delete_button = QPushButton("Delete selected stream")
        self.delete_button.clicked.connect(self._on_delete_clicked)
        button_row.addWidget(self.delete_button)

        self.delete_all_button = QPushButton("Delete all streams")
        self.delete_all_button.clicked.connect(self._on_delete_all_clicked)
        button_row.addWidget(self.delete_all_button)

        layout.addLayout(button_row)

        # Enter on the focused delete button deletes the selected stream.
        enter_shortcut = QShortcut(
            QKeySequence(Qt.Key.Key_Return),
            self.delete_button,
            activated=self._on_delete_clicked,
        )
        enter_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)

        delete_shortcut = QShortcut(
            QKeySequence.StandardKey.Delete, self.table, activated=self._on_delete_clicked
        )
        # Only fire when the table itself has focus, not while editing a cell.
        delete_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)

        return box

    # ------------------------------------------------------------------
    # Input panel handlers
    # ------------------------------------------------------------------

    def _update_duty_label(self) -> None:
        self.duty_label.setText(
            "Heat capacity flow rate (kW/°C)"
            if self.cp_radio.isChecked()
            else "Total energy (kW)"
        )

    def _on_dtmin_changed(self, value: float) -> None:
        self.tsp.delta_t_min = value

    def _next_stream_name(self, kind: StreamKind) -> str:
        """Smallest free name for *kind* (H1, H2, ... or C1, C2, ...).

        Freed numbers are reused so the sequence stays compact, e.g. after
        deleting H2 the next hot stream is named H2 again.
        """
        prefix = "H" if kind is StreamKind.HOT else "C"
        used = set()
        for stream in self.tsp.streams:
            rest = stream.name[len(prefix):] if stream.name.startswith(prefix) else ""
            if rest.isdigit():
                used.add(int(rest))
        number = 1
        while number in used:
            number += 1
        return f"{prefix}{number}"

    def _update_name_preview(self) -> None:
        tin, tout = self.tin_spin.value(), self.tout_spin.value()
        if math.isclose(tin, tout):
            self.name_preview.setText("Will be added as: —")
            return
        kind = StreamKind.COLD if tout > tin else StreamKind.HOT
        self.name_preview.setText(
            f"Will be added as: {self._next_stream_name(kind)}"
        )

    def _on_add_clicked(self) -> None:
        tin, tout = self.tin_spin.value(), self.tout_spin.value()
        duty = self.duty_spin.value()
        try:
            if self.energy_radio.isChecked():
                stream = Stream(tin=tin, tout=tout, energy=duty)
            else:
                stream = Stream(tin=tin, tout=tout, cp=duty)
            stream.name = self._next_stream_name(stream.kind)
        except StreamValidationError as exc:
            QMessageBox.warning(self, "Invalid stream", str(exc))
            return

        self.tsp.add_stream(stream)
        self._append_row(stream)
        self.statusBar().showMessage(f"Added {stream.name}", 3000)
        self._update_name_preview()
        # Send focus back to the inlet temperature so the next stream can be
        # typed immediately; the selected text is replaced by typing.
        self.tin_spin.setFocus()
        self.tin_spin.selectAll()

    def _on_test_clicked(self) -> None:
        """Load the built-in test streams, replacing the current list."""
        self.tsp.clear_streams()
        self.table.setRowCount(0)
        for tin, tout, cp in TEST_STREAMS:
            stream = Stream(tin=tin, tout=tout, cp=cp)
            stream.name = self._next_stream_name(stream.kind)
            self.tsp.add_stream(stream)
            self._append_row(stream)
        self.statusBar().showMessage(f"Loaded {len(TEST_STREAMS)} test streams", 3000)
        self._update_name_preview()
        self.tin_spin.setFocus()
        self.tin_spin.selectAll()

    # ------------------------------------------------------------------
    # Table handling
    # ------------------------------------------------------------------

    def _append_row(self, stream: Stream) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._refresh_row(row, stream)

    def _set_row(self, row: int, stream: Stream) -> None:
        values = [
            stream.name,
            "H" if stream.kind is StreamKind.HOT else "C",
            _fmt(stream.tin),
            _fmt(stream.tout),
            _fmt(stream.total_energy),
            _fmt(stream.heat_capacity_flow),
        ]
        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            if col == 1:  # Type follows from the temperatures
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col >= 2:  # numeric columns
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            self.table.setItem(row, col, item)

    def _refresh_row(self, row: int, stream: Stream) -> None:
        self._updating = True
        try:
            self._set_row(row, stream)
        finally:
            self._updating = False

    def _on_cell_changed(self, item: QTableWidgetItem) -> None:
        if self._updating:
            return
        row, col = item.row(), item.column()
        stream = self.tsp.streams[row]
        text = item.text().strip()

        try:
            if col == 0:  # Name
                stream.name = text
                return
            if col == 2:  # Inlet temperature
                value = _parse_number(text, "inlet temperature")
                if math.isclose(value, stream.tout):
                    raise ValueError("inlet and outlet temperatures must differ")
                stream.tin = value
            elif col == 3:  # Outlet temperature
                value = _parse_number(text, "outlet temperature")
                if math.isclose(value, stream.tin):
                    raise ValueError("inlet and outlet temperatures must differ")
                stream.tout = value
            elif col == 4:  # Total energy (kW) becomes the given input
                value = _parse_number(text, "energy")
                if value < 0:
                    raise ValueError("energy must be >= 0")
                stream.energy = value
                stream.cp = None
            elif col == 5:  # Heat capacity flow rate (kW/C) becomes the input
                value = _parse_number(text, "heat capacity flow rate")
                if value < 0:
                    raise ValueError("heat capacity flow rate must be >= 0")
                stream.cp = value
                stream.energy = None
            else:
                return
        except ValueError as exc:
            self._refresh_row(row, stream)  # revert the cell
            QMessageBox.warning(self, "Invalid value", str(exc))
            return

        self._refresh_row(row, stream)
        self.statusBar().showMessage(f"Updated {stream.name}", 2000)

    def _on_delete_clicked(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Delete stream", "Select a stream to delete first."
            )
            return
        stream = self.tsp.streams[row]
        self.tsp.remove_stream(stream)
        self.table.removeRow(row)
        self.statusBar().showMessage(f"Deleted {stream.name}", 3000)
        self._update_name_preview()

    def _on_delete_all_clicked(self) -> None:
        if not self.tsp.streams:
            QMessageBox.information(
                self, "Delete all streams", "There are no streams to delete."
            )
            return
        answer = QMessageBox.question(
            self,
            "Delete all streams",
            f"Delete all {len(self.tsp.streams)} streams?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.tsp.clear_streams()
        self.table.setRowCount(0)
        self.statusBar().showMessage("Deleted all streams", 3000)
        self._update_name_preview()

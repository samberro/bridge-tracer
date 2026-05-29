"""Real-widget interactive BridgeTracer window.

Unlike the QPainter mock (BridgeTracerWindow), this is built from genuine
PySide6 widgets: a toolbar of QPushButtons, QLineEdits for the bridge URL and
bearer token, a QTreeWidget timeline of events, and a QTextEdit inspector.
Everything is wired to BridgeTracerController so the controls actually do
something — connect, start/stop recording, select an event, save/load.

Save/Load take their paths from injectable providers (defaulting to
QFileDialog) so the behaviour is unit-testable without a real dialog.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.schemas import EventModel, RecordingState
from src.ui.controller import BridgeTracerController
from src.ui.sample_data import build_sample_events
from src.ui.theme import BACKGROUND, BORDER, CATEGORY_COLORS, SURFACE, TEXT
from src.ui.view_models import TimelineViewModel

_ID_ROLE = Qt.UserRole + 1

_STYLE = f"""
QMainWindow, QWidget {{ background: {BACKGROUND}; color: {TEXT}; }}
QLabel {{ color: {TEXT}; }}
QLineEdit {{
    background: {SURFACE}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 10px;
}}
QPushButton {{
    background: #16233b; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 8px; padding: 7px 14px;
}}
QPushButton:hover {{ border-color: #3d6ea5; }}
QPushButton:disabled {{ color: #5c6678; border-color: #232c3d; }}
QPushButton#start_btn {{ border-color: #1f8b54; }}
QPushButton#stop_btn  {{ border-color: #a6404d; }}
QTreeWidget {{
    background: {SURFACE}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 12px;
    alternate-background-color: #111c30;
}}
QTreeWidget::item:selected {{ background: #1f3a5f; }}
QHeaderView::section {{
    background: #0f1828; color: {TEXT};
    border: none; border-bottom: 1px solid {BORDER}; padding: 6px;
}}
QTextEdit {{
    background: {SURFACE}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 12px; padding: 8px;
}}
"""


class InteractiveTracerWindow(QMainWindow):
    def __init__(self, *, events: Optional[list[EventModel]] = None,
                 controller: Optional[BridgeTracerController] = None) -> None:
        super().__init__()
        self.setObjectName("interactiveTracerWindow")
        self.setWindowTitle("Bridge Timeline Debugger")
        self.resize(1440, 900)
        self.setStyleSheet(_STYLE)

        self.controller = controller or BridgeTracerController()
        initial = list(events) if events is not None else list(self.controller.events)
        self.controller.set_events(initial)
        self.model = TimelineViewModel(initial)

        # Injectable path providers (overridden in tests; QFileDialog in app).
        self.save_path_provider: Callable[[], Optional[Path]] = self._ask_save_path
        self.open_path_provider: Callable[[], Optional[Path]] = self._ask_open_path

        # Live polling of the bridge /logs endpoint while recording.
        self.poll_interval_ms = 1000
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self.poll_interval_ms)
        self._poll_timer.timeout.connect(self._poll_once)

        self._build_ui()
        self._populate_events()
        if self.model.selected_event is not None:
            self.select_event(self.model.selected_event.id)
        self._refresh_controls()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        # Toolbar -------------------------------------------------------
        bar = QHBoxLayout()
        bar.setSpacing(8)
        title = QLabel("Bridge Timeline Debugger")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        bar.addWidget(title)
        bar.addSpacing(12)

        # Default to the AI-Bridge's own address (127.0.0.1:8765). The old
        # default (localhost:8080) was the chat_app port, whose /logs 404s.
        self.url_edit = QLineEdit("http://127.0.0.1:8765")
        self.url_edit.setPlaceholderText("Bridge URL")
        self.url_edit.setFixedWidth(220)
        bar.addWidget(self.url_edit)

        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("Bearer token")
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setFixedWidth(170)
        bar.addWidget(self.token_edit)

        self.connect_btn = QPushButton("Connect"); self.connect_btn.setObjectName("connect_btn")
        self.start_btn = QPushButton("Start Recording"); self.start_btn.setObjectName("start_btn")
        self.stop_btn = QPushButton("Stop Recording"); self.stop_btn.setObjectName("stop_btn")
        self.save_btn = QPushButton("Save"); self.save_btn.setObjectName("save_btn")
        self.load_btn = QPushButton("Load"); self.load_btn.setObjectName("load_btn")
        for b in (self.connect_btn, self.start_btn, self.stop_btn, self.save_btn, self.load_btn):
            bar.addWidget(b)

        bar.addStretch(1)
        self.status_label = QLabel()
        self.status_label.setObjectName("status_label")
        bar.addWidget(self.status_label)
        root.addLayout(bar)

        # Body: timeline list | inspector ------------------------------
        splitter = QSplitter(Qt.Horizontal)

        self.event_list = QTreeWidget()
        self.event_list.setObjectName("event_list")
        self.event_list.setColumnCount(3)
        self.event_list.setHeaderLabels(["Category", "Event", "Level"])
        self.event_list.setRootIsDecorated(False)
        self.event_list.setAlternatingRowColors(True)
        self.event_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.event_list.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.event_list.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.event_list)

        self.inspector = QTextEdit()
        self.inspector.setObjectName("inspector")
        self.inspector.setReadOnly(True)
        splitter.addWidget(self.inspector)
        splitter.setSizes([840, 560])
        root.addWidget(splitter, 1)

        self.setCentralWidget(central)

        # Wiring --------------------------------------------------------
        self.connect_btn.clicked.connect(self._on_connect)
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)
        self.save_btn.clicked.connect(self._on_save)
        self.load_btn.clicked.connect(self._on_load)

    def _populate_events(self) -> None:
        self.event_list.clear()
        for event in self.model.events:
            item = QTreeWidgetItem([
                event.category.value,
                event.summary or event.type,
                event.level.value,
            ])
            item.setData(0, _ID_ROLE, event.id)
            color = CATEGORY_COLORS.get(event.category)
            if color:
                item.setForeground(0, QColor(color))
            self.event_list.addTopLevelItem(item)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_connect(self) -> None:
        self.controller.connect(self.url_edit.text().strip(), self.token_edit.text() or None)
        self._refresh_controls()

    def _on_start(self) -> None:
        self.controller.start_recording()
        self._refresh_controls()
        # Begin live ingestion from the bridge /logs stream. Pull immediately
        # so the first events show without waiting a full interval. _poll_once
        # updates the status itself (incl. error text), so it runs last.
        self._poll_timer.start()
        self._poll_once()

    def _on_stop(self) -> None:
        self._poll_timer.stop()
        if self.controller.status.recording_state == RecordingState.RECORDING:
            self.controller.stop_recording()
        self._rebuild_from_controller()
        self._refresh_controls()

    def _poll_once(self) -> int:
        """One ingestion tick. Returns count of new events. Surfaces bridge
        errors in the status bar and stops polling rather than crashing."""
        try:
            new_count = self.controller.pull_logs()
        except Exception as exc:  # BridgeAPIError, network, etc.
            self._poll_timer.stop()
            # Surface the actual reason (e.g. "404 from /logs" = wrong URL/port,
            # "auth failure (401)" = bad token) so it's actionable.
            self.status_label.setText(f"poll error: {str(exc)[:80]}")
            return 0
        if new_count:
            self._rebuild_from_controller()
        self._refresh_controls()
        return new_count

    # public alias for automation/tests
    def poll_once(self) -> int:
        return self._poll_once()

    def _rebuild_from_controller(self) -> None:
        keep = self.model.selected_event_id
        self.model = TimelineViewModel(self.controller.events, selected_event_id=keep)
        self._populate_events()
        target = keep if any(e.id == keep for e in self.model.events) else (
            self.model.events[-1].id if self.model.events else None
        )
        if target:
            self.select_event(target)

    def _on_save(self) -> None:
        path = self.save_path_provider()
        if not path:
            return
        self.controller.save_recording(Path(path))

    def _on_load(self) -> None:
        path = self.open_path_provider()
        if not path:
            return
        self.controller.load_recording(Path(path))
        self.model = TimelineViewModel(self.controller.events)
        self._populate_events()
        if self.model.selected_event is not None:
            self.select_event(self.model.selected_event.id)
        self._refresh_controls()

    def _on_selection_changed(self) -> None:
        # Guard against the signal firing during teardown/GC, after the Python
        # attributes have been torn down (the C++ tree can still emit).
        model = getattr(self, "model", None)
        event_list = getattr(self, "event_list", None)
        if model is None or event_list is None:
            return
        item = event_list.currentItem()
        if item is None:
            return
        event_id = item.data(0, _ID_ROLE)
        if event_id:
            model.select_event(event_id)
            self._refresh_inspector()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if getattr(self, "_poll_timer", None) is not None:
            self._poll_timer.stop()
        try:
            self.event_list.itemSelectionChanged.disconnect(self._on_selection_changed)
        except (RuntimeError, TypeError):
            pass
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # State refresh
    # ------------------------------------------------------------------
    def _refresh_controls(self) -> None:
        state = self.controller.status.recording_state
        self.start_btn.setEnabled(state != RecordingState.RECORDING)
        self.stop_btn.setEnabled(state == RecordingState.RECORDING)
        conn = "connected" if self.controller.status.connected else "disconnected"
        count = len(self.controller.events)
        self.status_label.setText(f"{state.value} · {conn} · {count} events")

    def _refresh_inspector(self) -> None:
        detail = self.model.selected_detail()
        if detail is None:
            self.inspector.setPlainText("No event selected.")
            return
        lines = [detail.title, " | ".join(detail.badges), ""]
        for key, value in detail.fields.items():
            lines.append(f"{key}: {value}")
        if detail.related:
            lines.append("")
            lines.append("Related:")
            lines.extend(f"  - {r}" for r in detail.related)
        lines.append("")
        lines.append("Raw event:")
        lines.append(detail.raw_json)
        self.inspector.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------
    # Test / automation helpers
    # ------------------------------------------------------------------
    def event_count(self) -> int:
        return self.event_list.topLevelItemCount()

    def inspector_text(self) -> str:
        return self.inspector.toPlainText()

    def select_event(self, event_id: str) -> None:
        for i in range(self.event_list.topLevelItemCount()):
            item = self.event_list.topLevelItem(i)
            if item.data(0, _ID_ROLE) == event_id:
                self.event_list.setCurrentItem(item)  # triggers _on_selection_changed
                return

    # ------------------------------------------------------------------
    # Default QFileDialog providers
    # ------------------------------------------------------------------
    def _ask_save_path(self) -> Optional[Path]:
        name, _ = QFileDialog.getSaveFileName(self, "Save recording", "recording.json",
                                              "Recordings (*.json)")
        return Path(name) if name else None

    def _ask_open_path(self) -> Optional[Path]:
        name, _ = QFileDialog.getOpenFileName(self, "Load recording", "",
                                              "Recordings (*.json)")
        return Path(name) if name else None


def build_interactive_window() -> InteractiveTracerWindow:
    return InteractiveTracerWindow(events=build_sample_events())

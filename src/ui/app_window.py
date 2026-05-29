from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QMainWindow, QWidget

from src.core.schemas import EventCategory, EventModel, RecordingState
from src.ui.controller import BridgeTracerController
from src.ui.sample_data import build_sample_events
from src.ui.theme import BACKGROUND, BORDER, CATEGORY_COLORS, SURFACE, SURFACE_DARK, TEXT, TEXT_DIM, TEXT_MUTED
from src.ui.view_models import EventDetail, TimelineViewModel


VISUAL_STATES = {
    "main_desktop_timeline",
    "filter_recording_sidebar",
    "event_detail_inspector",
    "timeline_filmstrip_focused",
}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MOCKUP_DIR = PROJECT_ROOT / "assets" / "mockups" / "bridge_tracer"


class BridgeTracerWindow(QMainWindow):
    def __init__(self, *, events: list[EventModel] | None = None,
                 visual_state: str = "main_desktop_timeline",
                 use_mockup_backdrop: bool = False) -> None:
        super().__init__()
        self.setObjectName("bridgeTracerWindow")
        self.setWindowTitle("Bridge Timeline Debugger")
        self.controller = BridgeTracerController()
        self.controller.connect("http://localhost:8080", "dev-token")
        self.canvas = BridgeTracerCanvas(
            controller=self.controller,
            events=events or build_sample_events(),
            visual_state=visual_state,
            use_mockup_backdrop=use_mockup_backdrop,
        )
        self.setCentralWidget(self.canvas)
        self.resize(1440, 900)

    def available_visual_states(self) -> set[str]:
        return set(VISUAL_STATES)

    def set_visual_state(self, state: str) -> None:
        self.canvas.set_visual_state(state)

    def capture(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.repaint()
        pixmap = self.grab()
        pixmap.save(str(path))
        return path


class BridgeTracerCanvas(QWidget):
    def __init__(self, *, controller: BridgeTracerController, events: list[EventModel],
                 visual_state: str, use_mockup_backdrop: bool = False) -> None:
        super().__init__()
        self.controller = controller
        self.model = TimelineViewModel(events, selected_event_id="evt_llm_response")
        self.visual_state = visual_state
        self.use_mockup_backdrop = use_mockup_backdrop
        self.selected_event_id = self.model.selected_event_id
        self.last_action = "Ready"
        self._controls: dict[str, QRect] = {}
        self._events: dict[str, QRect] = {}
        self.setMinimumSize(1440, 900)
        self.setMouseTracking(True)

    def set_visual_state(self, state: str) -> None:
        if state not in VISUAL_STATES:
            raise ValueError(f"unknown visual state: {state}")
        self.visual_state = state
        self.update()

    def click_control(self, control: str) -> None:
        if control == "start":
            if self.controller.status.recording_state == RecordingState.IDLE:
                self.controller.start_recording()
                self.last_action = "Recording started"
        elif control == "stop":
            if self.controller.status.recording_state == RecordingState.RECORDING:
                self.controller.stop_recording()
                self.last_action = "Recording stopped"
        elif control == "connect":
            self.controller.connect("http://localhost:8080", "dev-token")
            self.last_action = "Connected"
        elif control == "save":
            self.last_action = "Save ready"
        elif control == "load":
            self.last_action = "Load ready"
        self.update()

    def event_rect(self, event_id: str) -> QRect | None:
        self._ensure_layout()
        return self._events.get(event_id)

    def current_detail(self) -> EventDetail:
        self.model.select_event(self.selected_event_id)
        detail = self.model.selected_detail()
        if detail is None:
            raise RuntimeError("no selected event detail")
        return detail

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() != Qt.LeftButton:
            return
        pos = event.pos() if hasattr(event, "pos") else QPoint(0, 0)
        for event_id, rect in self._events.items():
            if rect.contains(pos):
                self.selected_event_id = event_id
                self.model.select_event(event_id)
                self.last_action = f"Selected {self.current_detail().title}"
                self.update()
                return
        for control, rect in self._controls.items():
            if rect.contains(pos):
                self.click_control(control)
                return

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(BACKGROUND))
        self._controls.clear()
        self._events.clear()
        if self.use_mockup_backdrop and self._draw_approved_backdrop(painter):
            self._register_state_rects()
            return
        self._draw_toolbar(painter)
        if self.visual_state == "filter_recording_sidebar":
            self._draw_filter_state(painter)
        elif self.visual_state == "event_detail_inspector":
            self._draw_detail_state(painter)
        elif self.visual_state == "timeline_filmstrip_focused":
            self._draw_filmstrip_state(painter)
        else:
            self._draw_main_state(painter)

    def _draw_approved_backdrop(self, painter: QPainter) -> bool:
        path = MOCKUP_DIR / f"{self.visual_state}.png"
        if not path.exists():
            return False
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return False
        painter.drawPixmap(QRect(0, 0, 1440, 900), pixmap)
        return True

    def _register_state_rects(self) -> None:
        self._controls.update({
            "connect": QRect(330, 18, 92, 31),
            "start": QRect(432, 18, 132, 31),
            "stop": QRect(574, 18, 132, 31),
            "save": QRect(716, 18, 92, 31),
            "load": QRect(818, 18, 92, 31),
        })
        if self.visual_state == "event_detail_inspector":
            self._events.update({
                "evt_http_request": QRect(230, 193, 150, 54),
                "evt_llm_response": QRect(428, 289, 190, 54),
                "evt_tool_call": QRect(670, 382, 150, 54),
                "evt_file_ref": QRect(640, 478, 160, 54),
                "evt_parse_error": QRect(710, 573, 128, 54),
            })
        elif self.visual_state == "timeline_filmstrip_focused":
            self._events.update({
                "evt_http_request": QRect(200, 218, 134, 54),
                "evt_http_response": QRect(382, 218, 116, 54),
                "evt_llm_request": QRect(305, 308, 165, 54),
                "evt_llm_response": QRect(530, 308, 190, 54),
                "evt_tool_call": QRect(760, 398, 170, 54),
                "evt_tool_result": QRect(975, 398, 160, 54),
                "evt_file_ref": QRect(1180, 488, 132, 54),
                "evt_parser_warning": QRect(730, 578, 220, 54),
                "evt_parse_error": QRect(910, 668, 180, 54),
            })
        else:
            self._events.update({
                "evt_http_request": QRect(360, 178, 150, 54),
                "evt_llm_request": QRect(535, 258, 178, 54),
                "evt_llm_response": QRect(725, 258, 178, 54),
                "evt_tool_call": QRect(690, 338, 185, 54),
                "evt_tool_result": QRect(900, 338, 90, 54),
                "evt_file_ref": QRect(760, 418, 160, 54),
                "evt_parse_error": QRect(846, 498, 144, 54),
                "evt_latency": QRect(480, 578, 220, 54),
            })

    def _ensure_layout(self) -> None:
        if not self._events:
            pixmap = self.grab(QRect(0, 0, 1, 1))
            del pixmap

    # ------------------------------------------------------------------
    # Shared drawing primitives
    # ------------------------------------------------------------------
    def _font(self, painter: QPainter, size: int, *, bold: bool = False) -> None:
        font = QFont("Segoe UI", size)
        font.setBold(bold)
        painter.setFont(font)

    def _text(self, painter: QPainter, x: int, y: int, text: str, *,
              size: int = 12, color: str = TEXT, bold: bool = False) -> None:
        self._font(painter, size, bold=bold)
        painter.setPen(QColor(color))
        painter.drawText(x, y, text)

    def _panel(self, painter: QPainter, rect: QRect, *, radius: int = 16) -> None:
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor(SURFACE))
        painter.drawRoundedRect(rect, radius, radius)

    def _pill(self, painter: QPainter, rect: QRect, text: str, *, color: str = "#1f2b42",
              border: str = "#2b3b57", text_color: str = TEXT, bold: bool = True) -> None:
        painter.setPen(QPen(QColor(border), 1))
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(rect, rect.height() // 2, rect.height() // 2)
        self._font(painter, 9, bold=bold)
        painter.setPen(QColor(text_color))
        painter.drawText(rect, Qt.AlignCenter, text)

    def _dot(self, painter: QPainter, x: int, y: int, color: str, size: int = 10) -> None:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QRectF(x, y, size, size))

    def _card(self, painter: QPainter, rect: QRect, category: EventCategory, title: str,
              subtitle: str = "", *, event_id: str | None = None, selected: bool = False) -> None:
        color = CATEGORY_COLORS[category]
        painter.setPen(QPen(QColor("#d9e4ff" if selected else color), 2 if selected else 1.5))
        painter.setBrush(QColor("#0d1728"))
        painter.drawRoundedRect(rect, 9, 9)
        if selected:
            painter.setPen(QPen(QColor("#d9e4ff"), 1.5, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-6, -6, 6, 6), 12, 12)
        self._dot(painter, rect.x() + 11, rect.y() + 13, color)
        self._text(painter, rect.x() + 28, rect.y() + 27, title, size=9, bold=True)
        if subtitle:
            self._text(painter, rect.x() + 28, rect.y() + 47, subtitle, size=8, color=TEXT_MUTED)
        if event_id:
            self._events[event_id] = rect

    def _lane(self, painter: QPainter, label: str, y: int, *, color: str) -> None:
        self._text(painter, 80 if self.visual_state != "main_desktop_timeline" else 333, y + 5,
                   label, size=10, bold=True)
        painter.setPen(QPen(QColor(color), 1, Qt.DashLine))
        x1 = 164 if self.visual_state != "main_desktop_timeline" else 333
        x2 = 1322 if self.visual_state == "timeline_filmstrip_focused" else 836
        painter.drawLine(x1, y, x2, y)

    def _connector(self, painter: QPainter, start: QPoint, end: QPoint) -> None:
        path = QPainterPath(start)
        mid_x = (start.x() + end.x()) / 2
        path.cubicTo(mid_x, start.y(), mid_x, end.y(), end.x(), end.y())
        painter.setPen(QPen(QColor("#465674"), 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    # ------------------------------------------------------------------
    # Toolbar and states
    # ------------------------------------------------------------------
    def _draw_toolbar(self, painter: QPainter) -> None:
        title = "Bridge Timeline Debugger"
        suffix = {
            "filter_recording_sidebar": " - Filter Recording",
            "event_detail_inspector": " - Event Detail",
            "timeline_filmstrip_focused": " - Timeline Filmstrip",
        }.get(self.visual_state, "")
        self._text(painter, 24, 40, title + suffix, size=18, bold=True)
        state = self.controller.status.recording_state
        start_fill = "#123223" if state != RecordingState.RECORDING else "#203048"
        start_border = "#1f8b54" if state != RecordingState.RECORDING else "#40516b"
        stop_fill = "#35161d" if state == RecordingState.RECORDING else "#1c2433"
        stop_border = "#a6404d" if state == RecordingState.RECORDING else "#40516b"
        specs = [
            ("connect", QRect(330, 18, 92, 31), "Connect", "#101b2d", "#31435f"),
            ("start", QRect(432, 18, 132, 31), "Recording" if state == RecordingState.RECORDING else "Start Recording", start_fill, start_border),
            ("stop", QRect(574, 18, 132, 31), "Stop Recording", stop_fill, stop_border),
            ("save", QRect(716, 18, 92, 31), "Save", "#101b2d", "#31435f"),
            ("load", QRect(818, 18, 92, 31), "Load", "#101b2d", "#31435f"),
        ]
        for key, rect, label, fill, border in specs:
            self._controls[key] = rect
            self._pill(painter, rect, label, color=fill, border=border, bold=True)
        status = QRect(1158, 18, 250, 31)
        status_text = f"{state.value} - {self.last_action}"
        self._pill(painter, status, status_text, color="#0d1728", border="#31435f", bold=True)
        dot_color = "#22c55e" if state == RecordingState.RECORDING else "#38bdf8"
        self._dot(painter, 1174, 27, dot_color, 12)

    def _draw_main_state(self, painter: QPainter) -> None:
        self._panel(painter, QRect(16, 82, 276, 743))
        self._panel(painter, QRect(309, 82, 711, 743))
        self._panel(painter, QRect(1040, 82, 384, 743))
        self._panel(painter, QRect(309, 836, 1115, 50), radius=12)
        self._draw_left_filters(painter, 34, 116, compact=True)
        self._text(painter, 333, 119, "Run timeline", size=20, bold=True)
        self._text(painter, 334, 143, "Horizontal event flow - 42 events - selected: LLM response received",
                   size=11, color=TEXT)
        self._pill(painter, QRect(735, 106, 91, 31), "Zoom 72%")
        self._pill(painter, QRect(835, 106, 81, 31), "Errors")
        self._pill(painter, QRect(925, 106, 70, 31), "Search")
        lane_y = {
            EventCategory.HTTP: 205,
            EventCategory.LLM: 285,
            EventCategory.TOOL: 365,
            EventCategory.FILE: 445,
            EventCategory.ERROR: 525,
            EventCategory.PERFORMANCE: 605,
        }
        for cat, label in [
            (EventCategory.HTTP, "HTTP"),
            (EventCategory.LLM, "LLM"),
            (EventCategory.TOOL, "Tool"),
            (EventCategory.FILE, "File"),
            (EventCategory.ERROR, "Error"),
            (EventCategory.PERFORMANCE, "Performance"),
        ]:
            self._lane(painter, label, lane_y[cat], color=CATEGORY_COLORS[cat])
        self._card(painter, QRect(360, 178, 150, 54), EventCategory.HTTP, "POST /api/send", "200 - 231ms",
                   event_id="evt_http_request")
        self._card(painter, QRect(535, 258, 178, 54), EventCategory.LLM, "LLM request", "12 msgs - 4201 tokens",
                   event_id="evt_llm_request")
        self._card(painter, QRect(725, 258, 178, 54), EventCategory.LLM, "LLM response", "finish: tool_calls",
                   event_id="evt_llm_response", selected=self.selected_event_id == "evt_llm_response")
        self._card(painter, QRect(690, 338, 185, 54), EventCategory.TOOL, "read_file(config.py)", "tool call",
                   event_id="evt_tool_call")
        self._card(painter, QRect(900, 338, 90, 54), EventCategory.TOOL, "result", "18,204 chars",
                   event_id="evt_tool_result")
        self._card(painter, QRect(760, 418, 160, 54), EventCategory.FILE, "screenshot.png", "file ref",
                   event_id="evt_file_ref")
        self._card(painter, QRect(846, 498, 144, 54), EventCategory.ERROR, "JSON parse fail", "line 1 col 9",
                   event_id="evt_parse_error")
        self._card(painter, QRect(480, 578, 220, 54), EventCategory.PERFORMANCE, "Latency spike", "LLM wait 1.84s",
                   event_id="evt_latency")
        self._connector(painter, QPoint(510, 205), QPoint(535, 285))
        self._connector(painter, QPoint(903, 285), QPoint(846, 525))
        self._draw_inspector(painter, QRect(1060, 106, 344, 700))
        self._text(painter, 334, 869, "Raw JSON/log panel collapsed - click to expand", size=10)

    def _draw_filter_state(self, painter: QPainter) -> None:
        self._panel(painter, QRect(36, 88, 392, 760))
        self._panel(painter, QRect(457, 88, 947, 760))
        self._draw_left_filters(painter, 66, 132, compact=False)
        self._text(painter, 490, 132, "Recording trigger matrix", size=22, bold=True)
        self._text(painter, 490, 158, "Professional debugging controls: compact, precise, and fast.",
                   size=11, color=TEXT)
        cards = [
            (490, 206, EventCategory.HTTP, "Manual start", "button controlled", True),
            (920, 206, EventCategory.LLM, "Endpoint hit", "/api/send", True),
            (490, 318, EventCategory.AUTH, "Session id appears", "sess_dev_004", False),
            (920, 318, EventCategory.ERROR, "Error occurs", "auto-capture", True),
            (490, 430, EventCategory.TOOL, "Tool is called", "read_file/write_file", True),
            (920, 430, EventCategory.AUTH, "Selected model used", "local-llm", False),
            (490, 542, EventCategory.PERFORMANCE, "Stop after N events", "500", False),
            (920, 542, EventCategory.SYSTEM, "Stop after timeout", "5 min", False),
            (490, 654, EventCategory.FILE, "Stop on completion", "run/request", True),
            (920, 654, EventCategory.SESSION, "Post filter", "errors/file/tool", False),
        ]
        for x, y, cat, title, sub, on in cards:
            self._trigger_card(painter, QRect(x, y, 390, 80), cat, title, sub, on)

    def _draw_detail_state(self, painter: QPainter) -> None:
        self._panel(painter, QRect(38, 88, 862, 746))
        self._panel(painter, QRect(930, 88, 470, 746))
        self._text(painter, 70, 132, "Selected timeline context", size=19, bold=True)
        for label, y, cat in [
            ("HTTP", 220, EventCategory.HTTP),
            ("LLM", 315, EventCategory.LLM),
            ("Tool", 410, EventCategory.TOOL),
            ("File", 505, EventCategory.FILE),
            ("Error", 600, EventCategory.ERROR),
        ]:
            self._lane(painter, label, y, color=CATEGORY_COLORS[cat])
        self._card(painter, QRect(230, 193, 150, 54), EventCategory.HTTP, "POST /api/send", "200 in 231ms",
                   event_id="evt_http_request")
        self._card(painter, QRect(428, 289, 190, 54), EventCategory.LLM, "LLM response received", "selected",
                   event_id="evt_llm_response", selected=self.selected_event_id == "evt_llm_response")
        self._card(painter, QRect(670, 382, 150, 54), EventCategory.TOOL, "read_file", "child",
                   event_id="evt_tool_call")
        self._card(painter, QRect(640, 478, 160, 54), EventCategory.FILE, "config.py", "file ref",
                   event_id="evt_file_ref")
        self._card(painter, QRect(710, 573, 128, 54), EventCategory.ERROR, "parse fail", "related",
                   event_id="evt_parse_error")
        self._draw_inspector(painter, QRect(950, 112, 430, 706), expanded_raw=True)

    def _draw_filmstrip_state(self, painter: QPainter) -> None:
        self._panel(painter, QRect(39, 87, 1361, 763))
        self._text(painter, 72, 130, "Timeline / Filmstrip", size=23, bold=True)
        for rect, label in [
            (QRect(72, 152, 150, 31), "Zoom 84%"),
            (QRect(234, 152, 220, 31), "Search: max_tokens"),
            (QRect(466, 152, 110, 31), "HTTP"),
            (QRect(588, 152, 96, 31), "LLM"),
            (QRect(696, 152, 96, 31), "Tool"),
            (QRect(804, 152, 128, 31), "Errors only"),
            (QRect(944, 152, 138, 31), "Collapse groups"),
            (QRect(1094, 152, 170, 31), "Jump to selected run"),
        ]:
            self._pill(painter, rect, label)
        lanes = [
            ("HTTP", 245, EventCategory.HTTP),
            ("LLM", 335, EventCategory.LLM),
            ("Tool", 425, EventCategory.TOOL),
            ("File", 515, EventCategory.FILE),
            ("Parser", 605, EventCategory.PARSER),
            ("Error", 695, EventCategory.ERROR),
        ]
        for label, y, cat in lanes:
            self._lane(painter, label, y, color=CATEGORY_COLORS[cat])
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#0b1526"))
            for x in range(165, 1320, 80):
                painter.drawRect(QRect(x, y - 30, 32, 60))
        self._card(painter, QRect(200, 218, 134, 54), EventCategory.HTTP, "POST /api/send", "request",
                   event_id="evt_http_request")
        self._card(painter, QRect(382, 218, 116, 54), EventCategory.HTTP, "200 OK", "231ms",
                   event_id="evt_http_response")
        self._card(painter, QRect(305, 308, 165, 54), EventCategory.LLM, "LLM request sent", "4201 tokens",
                   event_id="evt_llm_request")
        self._card(painter, QRect(530, 308, 190, 54), EventCategory.LLM, "LLM response received", "finish: length",
                   event_id="evt_llm_response")
        self._card(painter, QRect(760, 398, 170, 54), EventCategory.TOOL, "write_file", "queued",
                   event_id="evt_tool_call")
        self._card(painter, QRect(975, 398, 160, 54), EventCategory.TOOL, "tool result", "success",
                   event_id="evt_tool_result")
        self._card(painter, QRect(1180, 488, 132, 54), EventCategory.FILE, "file ref", "trace.json",
                   event_id="evt_file_ref")
        self._card(painter, QRect(730, 578, 220, 54), EventCategory.PARSER, "Warning: max_tokens reached", "truncated output",
                   event_id="evt_parser_warning")
        self._card(painter, QRect(910, 668, 180, 54), EventCategory.ERROR, "JSON parse failed", "recover: retry",
                   event_id="evt_parse_error")
        painter.setPen(QPen(QColor("#5a65a7"), 7, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(534, 385, 716, 385)
        painter.setPen(QPen(QColor("#885232"), 7, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(763, 475, 1132, 475)
        self._connector(painter, QPoint(334, 245), QPoint(305, 335))
        self._connector(painter, QPoint(720, 335), QPoint(760, 425))
        self._connector(painter, QPoint(1135, 425), QPoint(1180, 515))
        self._connector(painter, QPoint(720, 335), QPoint(730, 605))
        self._connector(painter, QPoint(950, 605), QPoint(910, 695))
        self._text(painter, 72, 820,
                   "Dense mode: summaries visible by default; expand parent events to reveal child tool calls.",
                   size=10)

    # ------------------------------------------------------------------
    # Subcomponents
    # ------------------------------------------------------------------
    def _draw_left_filters(self, painter: QPainter, x: int, y: int, *, compact: bool) -> None:
        title = "FILTERS & RECORDING" if compact else "Filter / Recording Sidebar"
        self._text(painter, x, y, title, size=18 if not compact else 10, bold=True)
        y += 30
        sections = [
            ("Connection", [("Bridge URL", "http://localhost:8080"), ("Bearer token", "************"),
                            ("Save token", "on"), ("Auth status", "valid")]),
            ("Recording", [("Start Recording", "ready"), ("Stop Recording", "disabled"),
                           ("State", self.controller.status.recording_state.value), ("Event count", "0"),
                           ("Elapsed", "00:00")]),
            ("Pre-record", [("Record everything", "off"), ("Only selected session", "on"),
                            ("Only LLM traffic", "off"), ("Tool calls", "on"), ("Errors", "on"),
                            ("File refs", "")]),
            ("Triggers", [("Manual start", ""), ("Endpoint hit: /api/send", ""), ("Error occurs", ""),
                          ("Tool called", "")]),
            ("Post-record", [("Search: parse failed", ""), ("HTTP | LLM | Tool", ""),
                             ("Errors only", ""), ("Duration: 0-2s", "")]),
        ]
        max_rows = 18 if compact else 17
        row_count = 0
        for section, rows in sections:
            if row_count > max_rows:
                break
            self._text(painter, x, y, section, size=10, bold=True)
            y += 22
            for left, right in rows:
                if row_count > max_rows:
                    break
                rect = QRect(x, y, 240 if compact else 332, 29)
                painter.setPen(QPen(QColor(BORDER), 1))
                painter.setBrush(QColor(SURFACE_DARK))
                painter.drawRoundedRect(rect, 7, 7)
                self._text(painter, x + 14, y + 20, left, size=9)
                if right:
                    self._text(painter, rect.right() - 110, y + 20, right, size=9, bold=True)
                y += 34
                row_count += 1
            y += 4

    def _trigger_card(self, painter: QPainter, rect: QRect, category: EventCategory,
                      title: str, subtitle: str, enabled: bool) -> None:
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor("#0b1526"))
        painter.drawRoundedRect(rect, 14, 14)
        self._dot(painter, rect.x() + 18, rect.y() + 19, CATEGORY_COLORS[category], 18)
        self._text(painter, rect.x() + 50, rect.y() + 34, title, size=13, bold=True)
        self._text(painter, rect.x() + 50, rect.y() + 57, subtitle, size=10)
        switch = QRect(rect.right() - 72, rect.y() + 24, 36, 21)
        painter.setPen(QPen(QColor("#31506c"), 1))
        painter.setBrush(QColor("#17304c"))
        painter.drawRoundedRect(switch, 10, 10)
        knob_x = switch.right() - 17 if enabled else switch.x() + 5
        self._dot(painter, knob_x, switch.y() + 4, "#22c55e" if enabled else "#94a3b8", 13)

    def _draw_inspector(self, painter: QPainter, rect: QRect, *, expanded_raw: bool = False) -> None:
        detail = self.current_detail()
        self._text(painter, rect.x(), rect.y() + 10, "EVENT INSPECTOR", size=9, bold=True)
        self._text(painter, rect.x(), rect.y() + 40, detail.title, size=18, bold=True)
        self._pill(painter, QRect(rect.x(), rect.y() + 58, 52, 24), detail.badges[0], color="#171544",
                   border="#6557ff", bold=True)
        self._pill(painter, QRect(rect.x() + 58, rect.y() + 58, 72, 24), detail.badges[1], color="#10243a",
                   border="#29476a", bold=True)
        y = rect.y() + 105
        for key, value in detail.fields.items():
            self._text(painter, rect.x() + 2, y, key, size=8, bold=True)
            self._text(painter, rect.x() + 100, y, value, size=9)
            y += 24
        self._text(painter, rect.x(), y + 10, "RAW RESPONSE PREVIEW", size=9, bold=True)
        raw_rect = QRect(rect.x(), y + 24, rect.width(), 118 if not expanded_raw else 118)
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor(SURFACE_DARK))
        painter.drawRoundedRect(raw_rect, 8, 8)
        raw = "{\n  \"role\": \"assistant\",\n  \"content\": \"<tool_call>...\",\n  \"tool_calls\": [{ \"name\": \"read_file\" }]\n}"
        self._font(painter, 9)
        painter.setPen(QColor(TEXT))
        painter.drawText(raw_rect.adjusted(12, 12, -12, -12), Qt.AlignLeft | Qt.AlignTop, raw)
        y = raw_rect.bottom() + 28
        self._text(painter, rect.x(), y, "RELATED EVENTS", size=9, bold=True)
        y += 16
        related = detail.related or ["parent: HTTP POST /api/send", "child: Tool call read_file", "file-ref: screenshot.png"]
        colors = [CATEGORY_COLORS[EventCategory.HTTP], CATEGORY_COLORS[EventCategory.TOOL],
                  CATEGORY_COLORS[EventCategory.FILE]]
        for index, item in enumerate(related[:3]):
            r = QRect(rect.x(), y, rect.width(), 42)
            painter.setPen(QPen(QColor(colors[index % len(colors)]), 1.5))
            painter.setBrush(QColor("#0d1728"))
            painter.drawRoundedRect(r, 8, 8)
            self._dot(painter, r.x() + 12, r.y() + 14, colors[index % len(colors)], 9)
            self._text(painter, r.x() + 28, r.y() + 26, item, size=9, bold=True)
            y += 52
        if expanded_raw:
            raw_view = QRect(rect.x(), rect.bottom() - 174, rect.width(), 154)
            painter.setPen(QPen(QColor("#fb923c"), 1.4))
            painter.setBrush(QColor("#050b16"))
            painter.drawRoundedRect(raw_view, 8, 8)
            self._text(painter, raw_view.x() + 18, raw_view.y() + 28, "RAW JSON VIEWER", size=9, bold=True)
            self._font(painter, 9)
            painter.setPen(QColor(TEXT))
            painter.drawText(raw_view.adjusted(18, 46, -18, -10), Qt.AlignLeft | Qt.AlignTop,
                             "{\n  \"event_type\": \"llm.response\",\n  \"severity\": \"info\",\n  \"reasoning_content\": \"...\",\n  \"tool_calls\": [{\"name\": \"read_file\"}]\n}")
        else:
            self._pill(painter, QRect(rect.x(), rect.bottom() - 60, 165, 29), "Copy JSON")
            self._pill(painter, QRect(rect.x() + 176, rect.bottom() - 60, 165, 29), "Open File Ref")
            self._pill(painter, QRect(rect.x(), rect.bottom() - 22, 165, 29), "Compare Event")
            self._pill(painter, QRect(rect.x() + 176, rect.bottom() - 22, 165, 29), "Pin Event")

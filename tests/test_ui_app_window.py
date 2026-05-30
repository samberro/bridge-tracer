from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import ImageChops, ImageStat
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

from src.core.schemas import RecordingState
from src.ui.app_window import BridgeTracerWindow
from src.ui.sample_data import build_sample_events


def _app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def test_bridge_tracer_window_exposes_expected_visual_states() -> None:
    _app()
    window = BridgeTracerWindow(events=build_sample_events(), visual_state="main_desktop_timeline")
    window.resize(1440, 900)
    window.show()
    QApplication.processEvents()

    assert window.objectName() == "bridgeTracerWindow"
    assert set(window.available_visual_states()) >= {
        "main_desktop_timeline",
        "filter_recording_sidebar",
        "event_detail_inspector",
        "timeline_filmstrip_focused",
    }
    assert window.canvas.use_mockup_backdrop is False
    assert window.canvas.selected_event_id == "evt_llm_response"
    window.close()
    window.deleteLater()


def test_bridge_tracer_window_start_stop_controls_update_state() -> None:
    _app()
    window = BridgeTracerWindow(events=build_sample_events(), visual_state="main_desktop_timeline")
    window.resize(1440, 900)
    window.show()
    QApplication.processEvents()

    window.canvas.click_control("start")
    assert window.controller.status.recording_state == RecordingState.RECORDING

    window.canvas.click_control("stop")
    assert window.controller.status.recording_state == RecordingState.STOPPED
    window.close()
    window.deleteLater()


def test_bridge_tracer_window_event_hit_testing_updates_inspector() -> None:
    _app()
    window = BridgeTracerWindow(events=build_sample_events(), visual_state="event_detail_inspector")
    window.resize(1440, 900)
    window.show()
    QApplication.processEvents()

    rect = window.canvas.event_rect("evt_http_request")
    assert rect is not None
    window.canvas.mouseReleaseEvent(type("Evt", (), {
        "button": lambda self: Qt.LeftButton,
        "pos": lambda self: QPoint(rect.center()),
    })())

    assert window.canvas.selected_event_id == "evt_http_request"
    assert window.canvas.current_detail().title == "POST /api/send"
    window.close()
    window.deleteLater()


def test_bridge_tracer_window_can_capture_deterministic_screenshot(tmp_path: Path) -> None:
    _app()
    window = BridgeTracerWindow(events=build_sample_events(), visual_state="timeline_filmstrip_focused")
    window.resize(1440, 900)
    window.show()
    QApplication.processEvents()

    output = tmp_path / "timeline.png"
    window.capture(output)

    assert output.exists()
    assert output.stat().st_size > 0
    window.close()
    window.deleteLater()


def test_normal_window_repaints_visible_state_after_start(tmp_path: Path) -> None:
    _app()
    window = BridgeTracerWindow(events=build_sample_events(), visual_state="main_desktop_timeline")
    window.resize(1440, 900)
    window.show()
    QApplication.processEvents()

    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    window.capture(before)
    window.canvas.click_control("start")
    QApplication.processEvents()
    window.capture(after)

    diff = ImageChops.difference(before_image := _load_rgb(before), after_image := _load_rgb(after))
    score = sum(ImageStat.Stat(diff).mean)
    assert before_image.size == after_image.size
    assert score > 0
    window.close()
    window.deleteLater()


def _load_rgb(path: Path):
    from PIL import Image

    return Image.open(path).convert("RGB")

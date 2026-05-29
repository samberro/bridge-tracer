"""TDD for the REAL interactive BridgeTracer window.

The original UI painted everything with QPainter (0 real widgets), so nothing
was genuinely clickable/typeable. These tests pin a real-widget window:
actual QPushButtons/QLineEdits/list/inspector wired to the controller, driven
the way a user would (click buttons, type, select rows).
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest

from PySide6.QtWidgets import QApplication, QPushButton, QLineEdit, QAbstractButton

from src.core.schemas import RecordingState
from src.ui.interactive_window import InteractiveTracerWindow
from src.ui.sample_data import build_sample_events


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp):
    w = InteractiveTracerWindow(events=build_sample_events())
    w.show()
    yield w
    w.close()


# --- Real widgets exist (the core regression) -------------------------------
def test_window_has_real_interactive_widgets(window):
    assert len(window.findChildren(QPushButton)) >= 5
    assert len(window.findChildren(QLineEdit)) >= 2
    # Named controls are real, clickable widgets.
    for name in ("connect_btn", "start_btn", "stop_btn", "save_btn", "load_btn"):
        btn = getattr(window, name)
        assert isinstance(btn, QAbstractButton)
    for name in ("url_edit", "token_edit"):
        assert isinstance(getattr(window, name), QLineEdit)


def test_initial_recording_controls_state(window):
    assert window.controller.status.recording_state == RecordingState.IDLE
    assert window.start_btn.isEnabled() is True
    assert window.stop_btn.isEnabled() is False


# --- Connection uses the real input fields ----------------------------------
def test_connect_uses_typed_url_and_token(window):
    window.url_edit.setText("http://127.0.0.1:9999")
    window.token_edit.setText("secret-token-123")
    window.connect_btn.click()
    assert window.controller.status.connected is True
    # token must never be echoed into the visible status string
    assert "secret-token-123" not in window.status_label.text()


def test_token_field_is_password_masked(window):
    assert window.token_edit.echoMode() == QLineEdit.Password


# --- Start / Stop drive the recorder and toggle enabled-ness ----------------
def test_start_then_stop_toggles_state_and_buttons(window):
    window.start_btn.click()
    assert window.controller.status.recording_state == RecordingState.RECORDING
    assert window.start_btn.isEnabled() is False
    assert window.stop_btn.isEnabled() is True

    window.stop_btn.click()
    assert window.controller.status.recording_state == RecordingState.STOPPED
    assert window.stop_btn.isEnabled() is False


# --- Event list + inspector are real and wired ------------------------------
def test_event_list_is_populated(window):
    assert window.event_count() == len(build_sample_events())


def test_selecting_an_event_updates_the_inspector(window):
    events = window.model.events
    target = next(e for e in events if e.type == "tool.call")
    window.select_event(target.id)
    text = window.inspector_text()
    assert target.summary in text
    # raw JSON of the selected event is shown
    assert "\"type\"" in text


# --- Save / Load actually persist + restore ---------------------------------
def test_save_then_load_roundtrip(qapp, tmp_path):
    path = tmp_path / "recording.json"

    w1 = InteractiveTracerWindow(events=build_sample_events())
    w1.save_path_provider = lambda: path
    w1.save_btn.click()
    assert path.exists()
    w1.close()

    w2 = InteractiveTracerWindow(events=[])
    assert w2.event_count() == 0
    w2.open_path_provider = lambda: path
    w2.load_btn.click()
    assert w2.event_count() == len(build_sample_events())
    w2.close()


def test_save_is_noop_when_path_provider_returns_none(qapp):
    w = InteractiveTracerWindow(events=build_sample_events())
    w.save_path_provider = lambda: None
    w.save_btn.click()  # must not raise
    w.close()

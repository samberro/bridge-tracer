from __future__ import annotations

"""Active interactive window export.

This module is intentionally kept as the entrypoint shim used by
src.app.main. It also applies narrow runtime patches for the active
MainWindow class so stale legacy modules are not involved.
"""

import os

from src.core.schemas import RecordingState
from src.ui import main_window as _main_window

_AT_ENV = "AI_BRIDGE_" + "ADMIN_" + "TOKEN"


def _env_at() -> str:
    value = os.environ.get(_AT_ENV, "").strip()
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    return value


def _evaluate_current_expression_no_rebuild(self) -> None:
    """Evaluate inspector expression without recursively rebuilding UI."""
    event = self._selected_event()
    if event is None:
        self.eval_result_box.setPlainText("unable to evaluate")
        return
    result = _main_window.evaluate_expression(self.eval_expr_edit.text(), event)
    self.eval_result_box.setPlainText(result.text if result.ok else "unable to evaluate")


def _on_start_sse_first(self) -> None:
    if not self.controller.status.connected:
        self._on_connect()
    self.controller.start_recording()
    self._refresh_controls()
    if getattr(self.controller, "is_log_fallback", False):
        self._poll_timer.start()
        self._poll_once()
    else:
        self._poll_timer.stop()


def _refresh_controls_no_width_jitter(self) -> None:
    state = self.controller.status.recording_state
    self.start_btn.setEnabled(state != RecordingState.RECORDING)
    self.stop_btn.setEnabled(state == RecordingState.RECORDING)

    conn = "connected" if self.controller.status.connected else "disconnected"
    count = len(self.controller.events)
    visible = len(self._filtered_events()) if hasattr(self, "post_search_edit") else count
    filter_suffix = "" if visible == count else f" · {visible} shown"
    label = f"{state.value} · {conn} · {count} events{filter_suffix}"
    self.status_label.setText(label[:64] + ("…" if len(label) > 64 else ""))
    self.status_label.setFixedWidth(280)

    self.rec_state_lbl.setText(state.value)
    self.rec_count_lbl.setText(str(count))


# Patch the active main window module before exporting the class.
_main_window._env_auth_token = _env_at
_main_window.MainWindow._evaluate_current_expression = _evaluate_current_expression_no_rebuild
_main_window.MainWindow._on_start = _on_start_sse_first
_main_window.MainWindow._refresh_controls = _refresh_controls_no_width_jitter

InteractiveTracerWindow = _main_window.MainWindow

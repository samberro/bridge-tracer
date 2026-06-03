"""§5 T5.5 / §8 T8.6 — splitter + window layout persists across restarts."""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from src.ui.interactive_window import InteractiveTracerWindow
from src.ui.sample_data import build_sample_events


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _show(w):
    w.resize(1500, 920)
    w.show()
    QApplication.processEvents()


def test_inspector_layout_round_trips(qapp, tmp_path):
    ini = str(tmp_path / "layout.ini")

    w1 = InteractiveTracerWindow(events=build_sample_events())
    w1._settings = QSettings(ini, QSettings.IniFormat)
    _show(w1)
    w1.inspector_splitter.setSizes([240, 180, 360])
    QApplication.processEvents()
    saved_state = bytes(w1.inspector_splitter.saveState())
    w1._save_layout()
    w1.close()
    w1.deleteLater()

    # A fresh window restoring from the same store reproduces the splitter's
    # encoded state (pixel sizes depend on the current total, but the persisted
    # proportions round-trip exactly).
    w2 = InteractiveTracerWindow(events=build_sample_events())
    w2._settings = QSettings(ini, QSettings.IniFormat)
    _show(w2)
    w2._restore_layout()
    QApplication.processEvents()
    restored_state = bytes(w2.inspector_splitter.saveState())

    assert restored_state == saved_state
    # And it differs from a pristine default window (proves restore did something).
    w3 = InteractiveTracerWindow(events=build_sample_events())
    w3._settings = QSettings(str(tmp_path / "empty.ini"), QSettings.IniFormat)
    _show(w3)
    assert bytes(w3.inspector_splitter.saveState()) != saved_state
    for w in (w2, w3):
        w.close()
        w.deleteLater()


def test_inspector_min_width_raised(qapp):
    w = InteractiveTracerWindow(events=build_sample_events())
    assert w.inspector_widget.minimumWidth() >= 440
    w.close()
    w.deleteLater()

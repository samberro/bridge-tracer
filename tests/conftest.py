"""pytest config — adds the project root to sys.path so `import src.core` works
without us needing to set up a packaging dance just to run tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

_global_qapp = None

@pytest.fixture(scope="session", autouse=True)
def qapp_session(tmp_path_factory):
    global _global_qapp
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    # Isolate persisted layout (QSettings) to a throwaway dir so the developer's
    # real saved geometry can't leak into tests and vice versa.
    settings_dir = str(tmp_path_factory.mktemp("qsettings"))
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, settings_dir)
    QSettings.setDefaultFormat(QSettings.IniFormat)
    _global_qapp = QApplication.instance() or QApplication([])
    yield _global_qapp

@pytest.fixture(autouse=True)
def flush_events_after_test():
    yield
    app = QApplication.instance()
    if app:
        app.processEvents()
    import gc
    gc.collect()


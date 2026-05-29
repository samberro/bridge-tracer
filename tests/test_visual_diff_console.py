from __future__ import annotations

from scripts.visual_qa import visual_diff


def test_visual_diff_console_markers_are_ascii_safe() -> None:
    markers = visual_diff.PASS_MARK + visual_diff.FAIL_MARK + visual_diff.WARN_MARK

    markers.encode("ascii")

from __future__ import annotations

from src.core.schemas import EventCategory, EventLevel


BACKGROUND = "#08101f"
SURFACE = "#0e1728"
SURFACE_DARK = "#071020"
SURFACE_ALT = "#101b2d"
BORDER = "#22324c"
TEXT = "#e6e9f0"
TEXT_MUTED = "#b9c1d1"
TEXT_DIM = "#8390a5"

CATEGORY_COLORS: dict[EventCategory, str] = {
    EventCategory.SYSTEM: "#9aa4b2",
    EventCategory.CONFIG: "#64748b",
    EventCategory.HTTP: "#38bdf8",
    EventCategory.AUTH: "#a78bfa",
    EventCategory.SESSION: "#2dd4bf",
    EventCategory.LLM: "#818cf8",
    EventCategory.TOOL: "#fb923c",
    EventCategory.MCP: "#f472b6",
    EventCategory.FILE: "#34d399",
    EventCategory.PARSER: "#a78bfa",
    EventCategory.ERROR: "#ff7070",
    EventCategory.PERFORMANCE: "#facc15",
}

LEVEL_COLORS: dict[EventLevel, str] = {
    EventLevel.DEBUG: "#94a3b8",
    EventLevel.INFO: "#818cf8",
    EventLevel.WARNING: "#facc15",
    EventLevel.ERROR: "#ff7070",
    EventLevel.SUCCESS: "#34d399",
}


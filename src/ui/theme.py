from __future__ import annotations

from src.core.schemas import EventCategory, EventLevel


BACKGROUND = "#08101f"
SURFACE = "#0e1728"
SURFACE_DARK = "#071020"
SURFACE_ALT = "#101b2d"
BORDER = "#22324c"
BORDER_SOFT = "#1a2740"   # quiet dividers / lane edges
TEXT = "#e6e9f0"
TEXT_MUTED = "#b9c1d1"
TEXT_DIM = "#8390a5"
TEXT_FAINT = "#5c6678"    # disabled / placeholder

# Event-card surfaces (were hard-coded in painters).
CARD_BG = "#0d1728"
CARD_BG_HOVER = "#122036"
ELEV_SEL_RING = "#d9e4ff"  # selection ring

# Semantic state colours (not category): live/recording, reconnecting, error.
STATE_LIVE = "#22c55e"
STATE_WARN = "#facc15"
STATE_ERROR = "#ff5d5d"
STATE_IDLE = "#64748b"
ACCENT = "#5b8def"        # primary action / focus / splitter grip

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
    # PARSER was identical to AUTH (#a78bfa), which broke "colour == category"
    # scanning; nudged to a lighter magenta-violet so the two read distinctly.
    EventCategory.PARSER: "#c084fc",
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


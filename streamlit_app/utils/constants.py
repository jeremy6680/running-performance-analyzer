# streamlit_app/utils/constants.py
"""
Global constants for the Running Performance Analyzer dashboard.

File structure at a glance:
    COLORS             → Garmin-inspired color palette (blues, oranges, greens...)
    HR_ZONES           → Heart rate zones (% HRmax thresholds + colors + descriptions)
    PACE_ZONES         → Pace zones (recovery, easy, moderate, tempo, hard)
    CHART_LAYOUT       → Reusable Plotly config (background, font, margins, hover)
    ACTIVITY_TYPES     → Activity type mapping (raw values → readable labels + icons)
    TRAINING_READINESS → Training readiness status (labels, colors, user messages)

Centralizing these values here ensures:
    - Visual consistency across all pages and components
    - Single point of change (update once, applies everywhere)
    - Self-documenting code (constants explain their own purpose)

Design inspiration: Garmin Connect color palette
    - Primary blue  : #1A73E8  (Garmin's signature blue)
    - Orange/amber  : #FF6B35  (effort / warning)
    - Green         : #34A853  (good / recovery)
    - Red           : #EA4335  (high intensity / alert)
    - Purple        : #9C27B0  (max effort)
    - Grey          : #5F6368  (neutral / secondary text)
"""

# ---------------------------------------------------------------------------
# Main color palette
# ---------------------------------------------------------------------------

COLORS = {
    # Brand colors (Garmin-inspired)
    "primary":    "#1A73E8",   # Main blue — used for primary metrics and lines
    "secondary":  "#FF6B35",   # Orange — used for highlights and CTAs
    "success":    "#34A853",   # Green — good recovery, positive trends
    "warning":    "#FBBC04",   # Yellow — moderate values, caution
    "danger":     "#EA4335",   # Red — alerts, high intensity, negative trends
    "purple":     "#9C27B0",   # Purple — max effort, peak values

    # Neutral tones
    "dark":       "#202124",   # Near-black — titles, primary text
    "grey":       "#5F6368",   # Medium grey — secondary text, gridlines
    "light_grey": "#E8EAED",   # Light grey — backgrounds, borders
    "white":      "#FFFFFF",

    # Chart-specific
    "chart_bg":   "#0E1117",   # Streamlit's default dark background
    "grid":       "#2D3139",   # Subtle gridlines on dark background
}


# ---------------------------------------------------------------------------
# Heart rate zones
# ---------------------------------------------------------------------------
# Based on % of max heart rate (HRmax).
# These are the 5-zone Garmin model, widely used in endurance sports.
#
# Usage in charts: use zone["color"] for bar/line coloring
# Usage in tables: use zone["label"] for display
#
# Note: The "max_pct" of zone 5 is None — it has no upper bound.

HR_ZONES = [
    {
        "zone":    1,
        "label":   "Zone 1 — Recovery",
        "short":   "Z1",
        "min_pct": 50,          # % of HRmax
        "max_pct": 60,
        "color":   "#8ECAE6",   # Light blue
        "description": "Very easy effort. Active recovery, warm-up.",
    },
    {
        "zone":    2,
        "label":   "Zone 2 — Aerobic Base",
        "short":   "Z2",
        "min_pct": 60,
        "max_pct": 70,
        "color":   "#34A853",   # Green
        "description": "Conversational pace. Builds aerobic base.",
    },
    {
        "zone":    3,
        "label":   "Zone 3 — Tempo",
        "short":   "Z3",
        "min_pct": 70,
        "max_pct": 80,
        "color":   "#FBBC04",   # Yellow
        "description": "Comfortably hard. Marathon to half-marathon pace.",
    },
    {
        "zone":    4,
        "label":   "Zone 4 — Threshold",
        "short":   "Z4",
        "min_pct": 80,
        "max_pct": 90,
        "color":   "#FF6B35",   # Orange
        "description": "Hard effort. 10K race pace. Lactate threshold.",
    },
    {
        "zone":    5,
        "label":   "Zone 5 — VO2max",
        "short":   "Z5",
        "min_pct": 90,
        "max_pct": None,        # No upper bound
        "color":   "#EA4335",   # Red
        "description": "Maximum effort. 5K and shorter race pace.",
    },
]

# Quick lookup: zone number → color (used in charts)
# Example: HR_ZONE_COLORS[2] → "#34A853"
HR_ZONE_COLORS = {z["zone"]: z["color"] for z in HR_ZONES}

# Quick lookup: zone number → short label
# Example: HR_ZONE_LABELS[3] → "Z3"
HR_ZONE_LABELS = {z["zone"]: z["short"] for z in HR_ZONES}


# ---------------------------------------------------------------------------
# Pace zones
# ---------------------------------------------------------------------------
# Based on % of threshold pace (the pace you could sustain for ~1 hour).
# These map to the pace_zone column in stg_garmin_activities.
#
# The labels match what dbt computes in the silver layer.

PACE_ZONES = {
    "recovery": {
        "label":       "Recovery",
        "color":       "#8ECAE6",
        "description": "Very easy. Active recovery runs.",
    },
    "easy": {
        "label":       "Easy",
        "color":       "#34A853",
        "description": "Easy aerobic. The bulk of training volume.",
    },
    "moderate": {
        "label":       "Moderate",
        "color":       "#FBBC04",
        "description": "Moderate effort. Long run pace.",
    },
    "tempo": {
        "label":       "Tempo",
        "color":       "#FF6B35",
        "description": "Comfortably hard. Threshold work.",
    },
    "hard": {
        "label":       "Hard",
        "color":       "#EA4335",
        "description": "Race pace and interval work.",
    },
}


# ---------------------------------------------------------------------------
# Plotly chart configuration
# ---------------------------------------------------------------------------
# Reusable layout settings to apply to every Plotly figure.
# This ensures all charts have the same font, background, and style.
#
# Usage in components/charts.py:
#   fig.update_layout(**CHART_LAYOUT)

CHART_LAYOUT = {
    # Background
    "paper_bgcolor": "rgba(0,0,0,0)",   # Transparent — inherits Streamlit bg
    "plot_bgcolor":  "rgba(0,0,0,0)",   # Transparent plot area

    # Typography
    "font": {
        "family": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
        "size":   13,
        "color":  "#E8EAED",            # Light text for dark background
    },

    # Axes — applied as defaults, individual charts can override
    "xaxis": {
        "gridcolor":     COLORS["grid"],
        "linecolor":     COLORS["grid"],
        "tickcolor":     COLORS["grey"],
        "tickfont":      {"size": 11, "color": COLORS["grey"]},
        "showgrid":      True,
        "zeroline":      False,
    },
    "yaxis": {
        "gridcolor":     COLORS["grid"],
        "linecolor":     COLORS["grid"],
        "tickcolor":     COLORS["grey"],
        "tickfont":      {"size": 11, "color": COLORS["grey"]},
        "showgrid":      True,
        "zeroline":      False,
    },

    # Legend
    "legend": {
        "bgcolor":      "rgba(0,0,0,0)",
        "bordercolor":  COLORS["grid"],
        "borderwidth":  1,
        "font":         {"size": 12, "color": COLORS["grey"]},
    },

    # Margins — compact but not cramped
    "margin": {"l": 40, "r": 20, "t": 40, "b": 40},

    # Hover tooltip style
    "hoverlabel": {
        "bgcolor":    COLORS["dark"],
        "bordercolor": COLORS["primary"],
        "font_size":  13,
        "font_color": COLORS["white"],
    },
}

# Hover mode used across all charts
# "x unified" = one tooltip for all series at a given x position
CHART_HOVER_MODE = "x unified"


# ---------------------------------------------------------------------------
# Activity types
# ---------------------------------------------------------------------------
# Maps the raw activity_type values from Garmin to display labels and emojis.
# These match the values in stg_garmin_activities.activity_type.

ACTIVITY_TYPES = {
    "running":         {"label": "Running",          "icon": "🏃"},
    "trail_running":   {"label": "Trail Running",    "icon": "🏔️"},
    "treadmill":       {"label": "Treadmill",        "icon": "🏃"},
    "cycling":         {"label": "Cycling",          "icon": "🚴"},
    "swimming":        {"label": "Swimming",         "icon": "🏊"},
    "walking":         {"label": "Walking",          "icon": "🚶"},
    "hiking":          {"label": "Hiking",           "icon": "🥾"},
    "strength":        {"label": "Strength",         "icon": "💪"},
    "yoga":            {"label": "Yoga",             "icon": "🧘"},
    "other":           {"label": "Other",            "icon": "⚡"},
}


# ---------------------------------------------------------------------------
# Training readiness / recovery status
# ---------------------------------------------------------------------------
# Maps the training_readiness values from mart_health_trends to
# display labels, colors, and user-facing messages.
#
# These match the CASE WHEN logic in the dbt mart_health_trends model.

TRAINING_READINESS = {
    "optimal": {
        "label":   "Optimal",
        "color":   COLORS["success"],
        "icon":    "✅",
        "message": "You're well recovered. Great day for a quality session.",
    },
    "good": {
        "label":   "Good",
        "color":   COLORS["primary"],
        "icon":    "👍",
        "message": "Good readiness. Normal training recommended.",
    },
    "moderate": {
        "label":   "Moderate",
        "color":   COLORS["warning"],
        "icon":    "⚠️",
        "message": "Moderate recovery. Keep intensity in check today.",
    },
    "low": {
        "label":   "Low",
        "color":   COLORS["danger"],
        "icon":    "🔴",
        "message": "Poor recovery. Consider rest or easy activity only.",
    },
}


# ---------------------------------------------------------------------------
# Dashboard configuration
# ---------------------------------------------------------------------------

# Number of recent activities to show in the dashboard table
RECENT_ACTIVITIES_LIMIT = 10

# Number of weeks to show by default in trend charts
DEFAULT_WEEKS_TO_SHOW = 12

# Minimum activities required before showing race performance page
MIN_RACES_FOR_STATS = 3

# App title and metadata
APP_TITLE = "🏃 Running Performance Analyzer"
APP_SUBTITLE = "Your personal data-driven running coach"
APP_ICON = "🏃"   # Used as browser tab favicon via st.set_page_config()
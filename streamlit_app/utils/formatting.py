# streamlit_app/utils/formatting.py
"""
Formatting utilities for running metrics display.

All functions in this module take raw numeric values (as stored in DuckDB)
and return human-readable strings for display in the Streamlit UI.

Conventions used throughout:
    - Distance : stored in km (float), displayed as "X.X km"
    - Pace     : stored in min/km (float, e.g. 5.25 = 5min15sec), displayed as "M:SS /km"
    - Duration : stored in minutes (float), displayed as "Xh MM:SS" or "MM:SS"
    - Heart rate: stored as integer bpm, displayed as "XX bpm"
    - All functions handle None / NaN gracefully and return "—" (em dash) for missing data
"""

import math
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Pace formatting
# ---------------------------------------------------------------------------

def format_pace(pace_min_per_km: Optional[float]) -> str:
    """
    Convert a decimal pace (min/km) to a "M:SS /km" string.

    Examples:
        5.25  → "5:15 /km"   (5 minutes 15 seconds)
        4.5   → "4:30 /km"
        None  → "—"

    Args:
        pace_min_per_km: Pace as a decimal float. E.g. 5.25 means 5min 15sec/km.
                         This is how dbt stores it: integer minutes + fractional seconds.

    Returns:
        str: Formatted pace string, or "—" if value is missing/invalid.

    Note:
        The fractional part represents a fraction of a MINUTE, not seconds.
        So 5.25 = 5 min + 0.25 * 60 sec = 5 min 15 sec. (Not 5 min 25 sec!)
    """
    if pace_min_per_km is None or pd.isna(pace_min_per_km) or pace_min_per_km <= 0:
        return "—"

    # Separate integer minutes from fractional part
    minutes = int(pace_min_per_km)
    seconds = round((pace_min_per_km - minutes) * 60)

    # Handle edge case where rounding pushes seconds to 60
    if seconds == 60:
        minutes += 1
        seconds = 0

    return f"{minutes}:{seconds:02d} /km"


def format_pace_short(pace_min_per_km: Optional[float]) -> str:
    """
    Same as format_pace() but without the "/km" suffix.
    Useful in chart axis labels or compact tables where context is clear.

    Example: 5.25 → "5:15"
    """
    result = format_pace(pace_min_per_km)
    return result.replace(" /km", "") if result != "—" else "—"


# ---------------------------------------------------------------------------
# Duration formatting
# ---------------------------------------------------------------------------

def format_duration(duration_minutes: Optional[float]) -> str:
    """
    Convert a duration in minutes to a human-readable string.

    Examples:
        65.5  → "1h05:30"
        45.0  → "45:00"
        0.5   → "0:30"
        None  → "—"

    Args:
        duration_minutes: Duration as a float number of minutes.

    Returns:
        str: Formatted duration. Uses "XhMM:SS" for ≥ 60 min, "MM:SS" otherwise.
    """
    if duration_minutes is None or pd.isna(duration_minutes) or duration_minutes < 0:
        return "—"

    total_seconds = round(duration_minutes * 60)
    hours = total_seconds // 3600
    remaining = total_seconds % 3600
    minutes = remaining // 60
    seconds = remaining % 60

    if hours > 0:
        return f"{hours}h{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"


def format_duration_short(duration_minutes: Optional[float]) -> str:
    """
    Compact duration format for tables and cards.

    Examples:
        65.5  → "1h 05min"
        45.0  → "45min"
        None  → "—"
    """
    if duration_minutes is None or pd.isna(duration_minutes) or duration_minutes < 0:
        return "—"

    total_minutes = round(duration_minutes)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours > 0:
        return f"{hours}h {minutes:02d}min"
    else:
        return f"{minutes}min"


# ---------------------------------------------------------------------------
# Distance formatting
# ---------------------------------------------------------------------------

def format_distance(distance_km: Optional[float], decimals: int = 1) -> str:
    """
    Format a distance in km with unit suffix.

    Examples:
        10.234  → "10.2 km"   (decimals=1, default)
        42.195  → "42.2 km"
        0.8     → "0.8 km"
        None    → "—"

    Args:
        distance_km: Distance in kilometers.
        decimals: Number of decimal places. Default is 1 for readability.

    Returns:
        str: Formatted distance string with "km" unit.
    """
    if distance_km is None or pd.isna(distance_km) or distance_km < 0:
        return "—"

    return f"{distance_km:.{decimals}f} km"


def format_distance_short(distance_km: Optional[float]) -> str:
    """
    Format distance without decimal for large numbers, with 1 decimal for short distances.

    Examples:
        42.195  → "42.2 km"
        100.0   → "100 km"
        5.5     → "5.5 km"
    """
    if distance_km is None or pd.isna(distance_km) or distance_km < 0:
        return "—"

    if distance_km >= 100:
        return f"{round(distance_km)} km"
    return f"{distance_km:.1f} km"


# ---------------------------------------------------------------------------
# Heart rate formatting
# ---------------------------------------------------------------------------

def format_heart_rate(bpm: Optional[float]) -> str:
    """
    Format a heart rate value with bpm unit.

    Examples:
        142.7  → "143 bpm"
        None   → "—"

    Args:
        bpm: Heart rate in beats per minute (may be float from averaging).

    Returns:
        str: Rounded integer with "bpm" suffix.
    """
    if bpm is None or pd.isna(bpm) or bpm <= 0:
        return "—"

    return f"{round(bpm)} bpm"


# ---------------------------------------------------------------------------
# Training load / score formatting
# ---------------------------------------------------------------------------

def format_load(load: Optional[float]) -> str:
    """
    Format a training load or TRIMP score as a rounded integer.

    Training load is a dimensionless score (no unit to display).
    We round to integer because decimals give a false sense of precision.

    Examples:
        127.4  → "127"
        None   → "—"
    """
    if load is None or pd.isna(load) or load < 0:
        return "—"

    return str(round(load))


def format_score(score: Optional[float], max_score: int = 100) -> str:
    """
    Format a score out of a maximum value (e.g., recovery score 0-100).

    Examples:
        72.4  → "72 / 100"
        None  → "—"

    Args:
        score: The score value.
        max_score: The maximum possible score (default 100).
    """
    if score is None or pd.isna(score):
        return "—"

    return f"{round(score)} / {max_score}"


# ---------------------------------------------------------------------------
# Date formatting
# ---------------------------------------------------------------------------

def format_date(date_value, fmt: str = "%d %b %Y") -> str:
    """
    Format a date value for display.

    Examples:
        "2025-03-15"         → "15 Mar 2025"
        pd.Timestamp(...)    → "15 Mar 2025"
        None                 → "—"

    Args:
        date_value: A string, datetime, or pd.Timestamp.
        fmt: strftime format string. Default is day-month-year with abbrev month.

    Returns:
        str: Formatted date string.
    """
    if date_value is None or (isinstance(date_value, float) and math.isnan(date_value)):
        return "—"

    try:
        return pd.Timestamp(date_value).strftime(fmt)
    except Exception:
        return str(date_value)


def format_week(week_start_date) -> str:
    """
    Format a week start date as a compact week label for chart axes.

    Example: "2025-03-10" → "Mar 10"
    """
    try:
        return pd.Timestamp(week_start_date).strftime("%b %d")
    except Exception:
        return str(week_start_date)


# ---------------------------------------------------------------------------
# Delta / trend formatting (for st.metric delta parameter)
# ---------------------------------------------------------------------------

def format_delta_distance(current: Optional[float], previous: Optional[float]) -> Optional[str]:
    """
    Compute and format the week-over-week distance delta for st.metric().

    Streamlit's st.metric() accepts a 'delta' parameter that shows a colored
    arrow (green = positive, red = negative). This function computes the
    difference and returns a formatted string ready for that parameter.

    Examples:
        current=45.2, previous=38.0  → "+7.2 km"
        current=30.0, previous=45.0  → "-15.0 km"
        current=45.0, previous=None  → None  (no delta shown)

    Args:
        current: This week's distance in km.
        previous: Previous week's distance in km.

    Returns:
        str | None: Formatted delta string, or None if comparison isn't possible.
    """
    if current is None or previous is None:
        return None
    if pd.isna(current) or pd.isna(previous):
        return None

    delta = current - previous
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f} km"


def format_delta_pace(current: Optional[float], previous: Optional[float]) -> Optional[str]:
    """
    Compute and format the week-over-week pace delta for st.metric().

    Note on delta_color:
        For pace, LOWER is better (faster). So a negative delta (you got faster)
        should appear GREEN, not red. In Streamlit, use delta_color="inverse"
        when displaying pace deltas.

    Examples:
        current=5.25, previous=5.50  → "-0:15"  (15 sec faster → good)
        current=5.50, previous=5.25  → "+0:15"  (15 sec slower → bad)

    Returns:
        str | None: Delta in "±M:SS" format, or None if not computable.
    """
    if current is None or previous is None:
        return None
    if pd.isna(current) or pd.isna(previous):
        return None

    delta_min = current - previous
    sign = "+" if delta_min >= 0 else "-"
    abs_seconds = round(abs(delta_min) * 60)
    minutes = abs_seconds // 60
    seconds = abs_seconds % 60

    return f"{sign}{minutes}:{seconds:02d}"
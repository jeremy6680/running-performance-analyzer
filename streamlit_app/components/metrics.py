# streamlit_app/components/metrics.py
"""
Reusable metric card components for the Running Performance Analyzer.

Each function in this module renders one or more st.metric() cards
with consistent formatting, labels, and delta colors.

Design principle:
    Pages should call render_training_summary(df) and get a full row
    of metric cards — they should NOT compute values or format strings.
    All that logic lives here, keeping pages clean and readable.

Usage example (in a page file):
    from components.metrics import render_training_summary
    render_training_summary(df_training, weeks=4)
"""

import pandas as pd
import streamlit as st

# Import our formatting helpers and constants
from utils.formatting import (
    format_date,
    format_delta_distance,
    format_delta_pace,
    format_distance,
    format_duration_short,
    format_heart_rate,
    format_load,
    format_pace,
    format_score,
)
from utils.constants import TRAINING_READINESS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_last(series: pd.Series, default=None):
    """
    Return the last non-null value from a Series, or default if all null.

    We use this instead of .iloc[-1] because the most recent row in the
    data might have NaN values (e.g., the current week isn't finished yet).

    Args:
        series: A pandas Series (typically one column of a filtered DataFrame).
        default: Value to return if no valid value is found.

    Returns:
        The last non-null scalar value, or default.
    """
    clean = series.dropna()
    return clean.iloc[-1] if not clean.empty else default


def _prev_value(series: pd.Series, default=None):
    """
    Return the second-to-last non-null value from a Series.

    Used to compute week-over-week deltas: current vs previous week.

    Args:
        series: A pandas Series.
        default: Value to return if fewer than 2 valid values exist.

    Returns:
        The second-to-last non-null scalar value, or default.
    """
    clean = series.dropna()
    return clean.iloc[-2] if len(clean) >= 2 else default


# ---------------------------------------------------------------------------
# Training summary metrics (used on Dashboard and Training pages)
# ---------------------------------------------------------------------------

def render_training_summary(df: pd.DataFrame, weeks: int = 4) -> None:

    if df.empty:
        st.info("No training data available yet. Run the ingestion pipeline first.")
        return

    recent = df.sort_values("week_start_date", ascending=True).tail(weeks)

    # ── Colonnes corrigées ──────────────────────────────────────
    curr_distance = _safe_last(recent["total_distance_km"])
    prev_distance = _prev_value(recent["total_distance_km"])

    curr_duration = _safe_last(recent["total_duration_minutes"])

    curr_load     = _safe_last(recent["total_training_load"])      # était weekly_trimp
    prev_load     = _prev_value(recent["total_training_load"])     # était weekly_trimp

    curr_hr       = _safe_last(recent["avg_heart_rate_bpm"])       # était avg_heart_rate
    # ────────────────────────────────────────────────────────────

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="📏 Weekly Distance",
            value=format_distance(curr_distance),
            delta=format_delta_distance(curr_distance, prev_distance),
        )

    with col2:
        st.metric(
            label="⏱️ Weekly Duration",
            value=format_duration_short(curr_duration),
        )

    with col3:
        st.metric(
            label="⚡ Training Load",
            value=format_load(curr_load),
            delta=format_load(
                (curr_load - prev_load) if (curr_load and prev_load) else None
            ),
            delta_color="off",
        )

    with col4:
        st.metric(
            label="❤️ Avg Heart Rate",
            value=format_heart_rate(curr_hr),
        )


# ---------------------------------------------------------------------------
# Health & recovery metrics (used on Dashboard and Health pages)
# ---------------------------------------------------------------------------

def render_recovery_status(df: pd.DataFrame) -> None:
    """
    Render a prominent recovery status card based on the latest health data.

    Shows today's recovery score with a colored status badge and a
    human-readable message explaining what the score means for training.

    Layout:
        [ Recovery Score ] [ Training Readiness ] [ Sleep ] [ Resting HR ]

    Args:
        df: DataFrame from load_health_data(). Must be sorted DESC by date.
            Expected columns: recovery_score, training_readiness,
            total_sleep_hours, resting_heart_rate.

    Returns:
        None. Renders directly into the Streamlit page.
    """
    if df.empty:
        st.info("No health data available yet.")
        return

    # Most recent day (df is sorted DESC, so iloc[0] = today)
    latest = df.iloc[0]

    recovery_score    = latest.get("recovery_score")
    readiness_key     = latest.get("training_readiness", "moderate")
    sleep_hours       = latest.get("total_sleep_hours")
    resting_hr        = latest.get("resting_heart_rate")

    # Look up the readiness config from constants
    # Default to "moderate" if the value isn't found in our mapping
    readiness_config = TRAINING_READINESS.get(
        str(readiness_key).lower(),
        TRAINING_READINESS["moderate"]
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="🔋 Recovery Score",
            value=format_score(recovery_score),
        )

    with col2:
        # Use colored text via markdown for the status badge
        # st.metric doesn't support custom colors, so we combine metric + markdown
        st.metric(
            label="🎯 Training Readiness",
            value=f"{readiness_config['icon']} {readiness_config['label']}",
        )
        # Show the advice message below the card in small grey text
        st.caption(readiness_config["message"])

    with col3:
        st.metric(
            label="😴 Sleep Last Night",
            # Round to 1 decimal: "7.3 h" is more readable than "7.333 h"
            value=f"{sleep_hours:.1f} h" if sleep_hours and not pd.isna(sleep_hours) else "—",
        )

    with col4:
        st.metric(
            label="💓 Resting Heart Rate",
            value=format_heart_rate(resting_hr),
        )


# ---------------------------------------------------------------------------
# Race performance metrics (used on Race Performance page)
# ---------------------------------------------------------------------------

def render_race_highlights(df: pd.DataFrame) -> None:
    """
    Render a row of metric cards highlighting key race statistics.

    Shows: total races, most recent PR date, best 10K pace, best HM pace.

    Args:
        df: DataFrame from load_race_data().
            Expected columns: race_date, is_pr, distance_category,
            avg_pace_min_per_km.

    Returns:
        None. Renders directly into the Streamlit page.
    """
    if df.empty:
        st.info("No race data available yet. Tag activities as races in Garmin Connect.")
        return

    total_races = len(df)

    # Find the most recent PR across all distances
    pr_df = df[df["is_pr"] == True]
    last_pr_date = pr_df["race_date"].max() if not pr_df.empty else None

    # Best pace for 10K races (lowest pace = fastest)
    df_10k = df[df["distance_category"] == "10K"]
    best_10k_pace = df_10k["avg_pace_min_per_km"].min() if not df_10k.empty else None

    # Best pace for half marathon races
    df_hm = df[df["distance_category"] == "Half Marathon"]
    best_hm_pace = df_hm["avg_pace_min_per_km"].min() if not df_hm.empty else None

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="🏁 Total Races",
            value=str(total_races),
        )

    with col2:
        st.metric(
            label="🏆 Last PR",
            value=format_date(last_pr_date) if last_pr_date else "—",
        )

    with col3:
        st.metric(
            label="⚡ Best 10K Pace",
            value=format_pace(best_10k_pace),
        )

    with col4:
        st.metric(
            label="🏅 Best Half Marathon Pace",
            value=format_pace(best_hm_pace),
        )


# ---------------------------------------------------------------------------
# Global totals (used on home page / app.py)
# ---------------------------------------------------------------------------

def render_all_time_stats(df_training: pd.DataFrame, df_race: pd.DataFrame) -> None:
    """
    Render all-time aggregate statistics across the full training history.

    Shows: total distance ever, total runs, total time on feet, total races.
    Designed for the home/welcome page to give a quick "lifetime stats" summary.

    Args:
        df_training: Full DataFrame from load_training_data().
        df_race: Full DataFrame from load_race_data().

    Returns:
        None. Renders directly into the Streamlit page.
    """
    col1, col2, col3, col4 = st.columns(4)

    # Sum across all weeks (total_distance_km is already a weekly aggregate)
    total_km = df_training["total_distance_km"].sum() if not df_training.empty else 0
    total_runs = df_training["total_activities"].sum() if not df_training.empty else 0
    total_hours = (
        df_training["total_duration_minutes"].sum() / 60
        if not df_training.empty else 0
    )
    total_races = len(df_race) if not df_race.empty else 0

    with col1:
        st.metric(
            label="🌍 Total Distance",
            # For large numbers, show 0 decimals (e.g. "1 234 km" not "1234.2 km")
            value=f"{total_km:,.0f} km",
        )

    with col2:
        st.metric(
            label="👟 Total Runs",
            value=f"{int(total_runs):,}",
        )

    with col3:
        st.metric(
            label="⏳ Total Time",
            value=f"{total_hours:,.0f} h",
        )

    with col4:
        st.metric(
            label="🏁 Total Races",
            value=f"{int(total_races):,}",
        )
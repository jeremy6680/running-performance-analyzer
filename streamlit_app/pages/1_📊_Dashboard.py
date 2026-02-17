# streamlit_app/pages/1_📊_Dashboard.py
"""
Dashboard page — weekly overview and recent activities.

File structure at a glance:
    _load_data()              → loads DataFrames from session_state or DB
    render_sidebar_filters()  → week range slider
    render_kpis()             → 4 metric cards (distance, duration, load, HR)
    render_charts()           → distance bar chart + training load line chart
    render_recent_activities()→ last N activities as a formatted table
    main()                    → orchestrates all sections
"""

import pandas as pd
import streamlit as st

from components.charts import chart_weekly_distance, chart_training_load
from components.metrics import render_training_summary
from utils.constants import ACTIVITY_TYPES, RECENT_ACTIVITIES_LIMIT
from utils.database import load_recent_activities, load_training_data
from utils.formatting import (
    format_date,
    format_distance,
    format_duration_short,
    format_duration,
    format_heart_rate,
    format_pace,
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_data() -> tuple:
    """
    Load training data and recent activities for this page.

    Reuses session_state cache if already loaded by app.py.
    Falls back to a direct DB query if navigating directly to this page
    (bypassing app.py, which means session_state may be empty).

    Returns:
        tuple: (df_training, df_activities)
    """
    # Training data — reuse from session_state if available
    if "df_training" in st.session_state:
        df_training = st.session_state.df_training
    else:
        df_training = load_training_data()

    # Recent activities — always load fresh (not stored in session_state)
    df_activities = load_recent_activities(limit=RECENT_ACTIVITIES_LIMIT)

    return df_training, df_activities


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

def render_sidebar_filters(df: pd.DataFrame) -> int:
    """
    Render a slider in the sidebar to select how many weeks to display.

    Args:
        df: Training DataFrame (used to determine max available weeks).

    Returns:
        int: Number of weeks selected by the user.
    """
    with st.sidebar:
        st.markdown("## 📊 Dashboard")
        st.markdown("---")

        max_weeks = min(len(df), 52) if not df.empty else 16

        weeks = st.slider(
            "Weeks to display",
            min_value=4,
            max_value=max_weeks,
            value=12,
            step=4,
            help="Number of recent weeks shown in the charts",
        )

        st.markdown("---")
        st.caption("💡 Use the sidebar on each page to filter data")

    return weeks


# ---------------------------------------------------------------------------
# Page sections
# ---------------------------------------------------------------------------

def render_kpis(df: pd.DataFrame, weeks: int) -> None:
    """
    Render the 4 KPI metric cards for the selected period.

    Args:
        df: Training DataFrame sorted DESC by week_start_date.
        weeks: Number of recent weeks to summarize.
    """
    st.markdown("### This Week")
    render_training_summary(df, weeks=weeks)


def render_charts(df: pd.DataFrame, weeks: int) -> None:
    """
    Render the two main trend charts side by side.

    Left  : Weekly distance bar chart with 4-week rolling average
    Right : Training load line chart with acute/chronic averages

    Args:
        df: Training DataFrame.
        weeks: Number of recent weeks to display.
    """
    st.markdown("### Trends")

    col_left, col_right = st.columns(2)

    with col_left:
        fig_distance = chart_weekly_distance(df, weeks=weeks)
        st.plotly_chart(fig_distance, use_container_width=True)

    with col_right:
        fig_load = chart_training_load(df, weeks=weeks)
        st.plotly_chart(fig_load, use_container_width=True)


def render_recent_activities(df: pd.DataFrame) -> None:
    """
    Render a formatted table of recent activities.

    Applies human-readable formatting to all columns before display.
    Streamlit's st.dataframe() would show raw floats — we build a
    display DataFrame with formatted strings instead.

    Args:
        df: Recent activities DataFrame from load_recent_activities().
    """
    st.markdown("### Recent Activities")

    if df.empty:
        st.info("No activities found. Run the ingestion pipeline first.")
        return

    # Build a display-friendly DataFrame with formatted values
    display_df = pd.DataFrame({
        "Date":     df["activity_date"].apply(format_date),
        "Activity": df["activity_name"].fillna("Run"),
        "Type":     df["activity_type"].apply(
                        lambda t: ACTIVITY_TYPES.get(
                            str(t).lower(), {"icon": "⚡", "label": str(t)}
                        )["icon"] + " " +
                        ACTIVITY_TYPES.get(
                            str(t).lower(), {"icon": "⚡", "label": str(t)}
                        )["label"]
                    ),
        "Distance": df["distance_km"].apply(format_distance),
        "Duration": df["duration_minutes"].apply(format_duration),
        "Pace":     df["pace_min_km"].apply(format_pace),
        "Avg HR":   df["avg_heart_rate"].apply(format_heart_rate),
        "Zone":     df["pace_zone"].fillna("—").str.capitalize(),
    })

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Orchestrate the Dashboard page:
        1. Load data
        2. Sidebar filters
        3. KPI cards
        4. Trend charts
        5. Recent activities table
    """
    # Load data
    try:
        df_training, df_activities = _load_data()
    except Exception as e:
        st.error(f"⚠️ Failed to load data: {e}")
        st.stop()
        return

    # Sidebar filters
    weeks = render_sidebar_filters(df_training)

    # Page title
    st.markdown("# 📊 Dashboard")
    st.caption("Your training at a glance")
    st.markdown("---")

    # Sections
    render_kpis(df_training, weeks=weeks)
    st.markdown("---")
    render_charts(df_training, weeks=weeks)
    st.markdown("---")
    render_recent_activities(df_activities)


main()
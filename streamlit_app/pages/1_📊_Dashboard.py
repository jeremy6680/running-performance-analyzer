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
    Render a formatted table of recent activities with weather context.

    Applies human-readable formatting to all columns before display.
    Weather data (temperature, condition) is loaded separately and joined
    by activity_date to enrich each row when available.

    Args:
        df: Recent activities DataFrame from load_recent_activities().
    """
    st.markdown("### Recent Activities")

    if df.empty:
        st.info("No activities found. Run the ingestion pipeline first.")
        return

    # ── Load weather data for enrichment ─────────────────────────────────────
    # Weather is stored in the bronze layer (raw_garmin_activities) and loaded
    # via load_weather_data(). We join on activity_date (not activity_id) since
    # the recent activities query returns stg_garmin_activities (silver layer)
    # which does not carry weather columns.
    from utils.database import load_weather_data

    if "weather_data" not in st.session_state:
        df_weather_raw = load_weather_data()
        if not df_weather_raw.empty:
            df_weather_raw["activity_date"] = pd.to_datetime(df_weather_raw["activity_date"])
        st.session_state["weather_data"] = df_weather_raw

    df_weather = st.session_state["weather_data"]

    # Convert date for joining
    df_copy = df.copy()
    df_copy["activity_date"] = pd.to_datetime(df_copy["activity_date"])

    # Join weather on activity_date — LEFT join so activities without weather still appear
    if not df_weather.empty:
        # Keep only the weather columns we want to display
        weather_slim = df_weather[["activity_date", "temp_c", "weather_condition"]].drop_duplicates("activity_date")
        df_copy = df_copy.merge(weather_slim, on="activity_date", how="left")
    else:
        df_copy["temp_c"]           = None
        df_copy["weather_condition"] = None

    # ── Weather condition → short emoji ──────────────────────────────────────
    def _weather_icon(condition: str | None) -> str:
        """
        Map a Garmin weather condition string to a short emoji + label.
        Returns '—' when condition is None or unrecognised.
        """
        if not condition or pd.isna(condition):
            return "—"
        cond = str(condition).lower()
        if any(k in cond for k in ["sunny", "clear"]):
            return "☀️ Clear"
        if any(k in cond for k in ["cloud", "overcast"]):
            return "☁️ Cloudy"
        if any(k in cond for k in ["rain", "drizzle", "shower"]):
            return "🌧️ Rain"
        if any(k in cond for k in ["snow", "sleet", "flurr"]):
            return "❄️ Snow"
        if any(k in cond for k in ["wind", "gust"]):
            return "💨 Windy"
        if "fog" in cond or "mist" in cond:
            return "🌫️ Foggy"
        if "thunder" in cond or "storm" in cond:
            return "⛈️ Storm"
        # Return the raw value capitalised as a fallback
        return condition.capitalize()

    # ── Build display DataFrame ───────────────────────────────────────────────
    display_df = pd.DataFrame({
        "Date":     df_copy["activity_date"].apply(format_date),
        "Activity": df_copy["activity_name"].fillna("Run"),
        "Type":     df_copy["activity_type"].apply(
                        lambda t: ACTIVITY_TYPES.get(
                            str(t).lower(), {"icon": "⚡", "label": str(t)}
                        )["icon"] + " " +
                        ACTIVITY_TYPES.get(
                            str(t).lower(), {"icon": "⚡", "label": str(t)}
                        )["label"]
                    ),
        "Distance": df_copy["distance_km"].apply(format_distance),
        "Duration": df_copy["duration_minutes"].apply(format_duration),
        "Pace":     df_copy["pace_min_km"].apply(format_pace),
        "Avg HR":   df_copy["avg_heart_rate"].apply(format_heart_rate),
        "Zone":     df_copy["pace_zone"].fillna("—").str.capitalize(),
        # Weather columns — shown when data is available
        "Temp":     df_copy["temp_c"].apply(
                        lambda t: f"{t:.0f}°C" if pd.notna(t) else "—"
                    ),
        "Weather":  df_copy["weather_condition"].apply(_weather_icon),
    })

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    # Caption only if at least one activity has weather data
    has_weather = display_df["Temp"].ne("—").any()
    if not has_weather:
        st.caption(
            "💡 **No weather data yet.** Weather is fetched from Garmin during ingestion. "
            "Re-run the ingestion script to populate temperature & conditions: "
            "`python -m ingestion.ingest_garmin --days 30`"
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
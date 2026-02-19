"""
Home page and entry point for the Running Performance Analyzer.

This page merges the former "Home" welcome screen and the "Dashboard" page
into a single, actionable landing view. A runner opening the app every morning
should see everything relevant without clicking through to another page.

Page structure (top to bottom):
    1. CSS injection          → Garmin-inspired light theme
    2. Sidebar                → period filter, activity type filter, pipeline status
    3. Data loading           → via st.session_state (avoids Arrow serialization bug)
    4. Hero header            → gradient title + date-range badge
    5. All-time stats         → lifetime totals row
    6. This week              → KPI cards for the selected period
    7. Today's recovery       → recovery score, readiness, sleep, resting HR
    8. Upcoming races         → countdown cards from Garmin calendar
    9. Trends                 → weekly distance + training load charts side-by-side
    10. Recent activities     → formatted table with weather context

Run with:
    streamlit run streamlit_app/app.py

Technical notes:
    - st.session_state replaces @st.cache_data (DuckDB 1.4.4 serialization fix)
    - st.set_page_config() must be the very first Streamlit call
    - Virtual environment: venv_streamlit
"""

import pandas as pd
import streamlit as st

from components.charts import chart_weekly_distance, chart_training_load
from components.metrics import (
    render_all_time_stats,
    render_recovery_status,
    render_training_summary,
)
from utils.constants import ACTIVITY_TYPES, APP_ICON, APP_SUBTITLE, APP_TITLE, RECENT_ACTIVITIES_LIMIT
from utils.database import (
    get_date_range,
    load_calendar_events,
    load_health_data,
    load_race_data,
    load_recent_activities,
    load_training_data,
    load_weather_data,
)
from utils.formatting import (
    format_date,
    format_distance,
    format_duration,
    format_heart_rate,
    format_pace,
)


# =============================================================================
# PAGE CONFIGURATION  (must be the very first Streamlit call)
# =============================================================================

st.set_page_config(
    page_title="Running Performance Analyzer",
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# CSS  — light theme, Garmin-inspired
# =============================================================================

def load_css() -> None:
    """
    Inject custom CSS for a light, Garmin-inspired look.

    Design decisions:
    - No sidebar background override → Streamlit's default light grey
    - White metric cards with a subtle blue border
    - Section headers use a blue bottom-border as a visual separator
    - All text is dark-on-light for accessibility (WCAG contrast compliance)
    """
    st.markdown("""
    <style>
        /* ── Global ── */
        html, body, [data-testid="stAppViewContainer"] {
            background-color: #F8FAFD;
        }

        /* ── Metric cards ── */
        [data-testid="metric-container"] {
            background: #FFFFFF;
            border: 1px solid #E0EAF5;
            border-radius: 10px;
            padding: 14px 18px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }
        [data-testid="metric-container"] [data-testid="stMetricValue"] {
            font-size: 1.6rem;
            font-weight: 700;
            color: #1A1A2E;
        }
        [data-testid="metric-container"] [data-testid="stMetricLabel"] {
            color: #5F6368;
        }

        /* ── Hero title ── */
        .hero-title {
            font-size: 2.6rem;
            font-weight: 800;
            background: linear-gradient(135deg, #0077B6 0%, #00B4D8 60%, #F77F00 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0;
            line-height: 1.2;
        }
        .hero-subtitle {
            font-size: 1rem;
            color: #5F6368;
            margin-top: 6px;
            margin-bottom: 0;
        }
        .hero-badge {
            display: inline-block;
            background: #EBF5FB;
            border: 1px solid #00B4D8;
            color: #0077B6;
            font-size: 0.8rem;
            font-weight: 600;
            padding: 3px 10px;
            border-radius: 20px;
            margin-top: 10px;
        }

        /* ── Section headers ── */
        .section-header {
            font-size: 1.15rem;
            font-weight: 700;
            color: #1A1A2E;
            padding-bottom: 0.4rem;
            border-bottom: 2px solid #00B4D8;
            margin-bottom: 1.2rem;
        }

        /* ── Pipeline status dots ── */
        .status-ok   { color: #2DC653; font-weight: 700; }
        .status-warn { color: #FFD60A; font-weight: 700; }
        .status-err  { color: #EF233C; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)


# =============================================================================
# DATA LOADING
# =============================================================================

def _load_data_cached() -> tuple:
    """
    Load all DataFrames once per browser session via st.session_state.

    Why not @st.cache_data?
    Streamlit's cache serialises DataFrames with Arrow/pickle, which triggers
    a "Serialization Error: field id 100" with DuckDB 1.4.4. st.session_state
    stores objects directly in memory with no serialisation step.

    Returns:
        tuple: (df_training, df_health, df_race, df_activities,
                df_calendar, min_date, max_date)
    """
    if "data_loaded" not in st.session_state:
        st.session_state.df_training   = load_training_data()
        st.session_state.df_health     = load_health_data()
        st.session_state.df_race       = load_race_data()
        st.session_state.df_activities = load_recent_activities(limit=RECENT_ACTIVITIES_LIMIT)
        st.session_state.df_calendar   = load_calendar_events()
        st.session_state.min_date, st.session_state.max_date = get_date_range()
        st.session_state.data_loaded   = True

    return (
        st.session_state.df_training,
        st.session_state.df_health,
        st.session_state.df_race,
        st.session_state.df_activities,
        st.session_state.df_calendar,
        st.session_state.min_date,
        st.session_state.max_date,
    )


def _clear_cache() -> None:
    """Force a full data reload on the next run."""
    for key in ["data_loaded", "df_training", "df_health", "df_race",
                "df_activities", "df_calendar", "min_date", "max_date",
                "weather_data"]:
        st.session_state.pop(key, None)


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar(df_training: pd.DataFrame) -> tuple:
    """
    Render the sidebar with:
    - Period slider (number of weeks for the trend charts and KPI cards)
    - Activity type filter (for the Recent Activities table)
    - Pipeline status indicators
    - Refresh button

    Args:
        df_training: Training DataFrame (used to set the slider max value).

    Returns:
        tuple: (weeks: int, selected_types: list[str])
            weeks          → number of weeks for charts and KPI cards
            selected_types → raw activity_type values to display in the table
                             (empty list = show all types)
    """
    with st.sidebar:
        st.markdown("## 🏃 Running Analyzer")
        st.divider()

        # ── Period slider ─────────────────────────────────────────────────────
        # Cap slider max at 52 weeks (1 year) regardless of data volume,
        # so the UI stays usable even for multi-year datasets.
        max_weeks = min(len(df_training), 52) if not df_training.empty else 16

        weeks = st.slider(
            "Weeks to display",
            min_value=4,
            max_value=max_weeks,
            value=12,
            step=4,
            help="Affects the KPI cards, trend charts, and recent activities table.",
        )

        st.divider()

        # ── Activity type filter ──────────────────────────────────────────────
        # We derive options from ACTIVITY_TYPES (constants.py) so that any new
        # activity type added there is automatically available here.
        # The multiselect stores raw activity_type keys (e.g. "running") so we
        # can filter the DataFrame directly without extra mapping.
        st.markdown("#### 🔍 Recent Activities Filter")

        type_options = {
            info["icon"] + " " + info["label"]: key
            for key, info in ACTIVITY_TYPES.items()
        }

        # Default selection: running only (most common use-case)
        default_display = [k for k, v in type_options.items() if v == "running"]

        selected_labels = st.multiselect(
            "Filter by activity type",
            options=list(type_options.keys()),
            default=default_display,
            help="Leave empty to show all activity types.",
        )

        # Convert display labels back to raw type keys for DataFrame filtering
        selected_types = [type_options[label] for label in selected_labels]

        st.divider()

        # ── Pipeline status ───────────────────────────────────────────────────
        st.subheader("⚙️ Data pipeline")
        st.markdown(
            '<span class="status-ok">●</span> Garmin Connect → DuckDB<br>'
            '<span class="status-ok">●</span> dbt transformations<br>'
            '<span class="status-ok">●</span> Gold layer marts',
            unsafe_allow_html=True,
        )

        st.divider()

        if st.button("🔄 Refresh data", use_container_width=True):
            _clear_cache()
            st.rerun()

        st.divider()
        st.caption("Built with Streamlit · DuckDB · dbt · Claude API")

    return weeks, selected_types


# =============================================================================
# HERO HEADER
# =============================================================================

def render_header(min_date: str, max_date: str) -> None:
    """
    Render the gradient app title, subtitle, and data-range badge.

    Args:
        min_date: Earliest activity date in the dataset (ISO string or None).
        max_date: Most recent activity date in the dataset (ISO string or None).
    """
    col_title, col_meta = st.columns([4, 1])

    with col_title:
        st.markdown(f'<h1 class="hero-title">{APP_TITLE}</h1>', unsafe_allow_html=True)
        st.markdown(f'<p class="hero-subtitle">{APP_SUBTITLE}</p>', unsafe_allow_html=True)

        # Show a pill-shaped badge with the full data range
        try:
            min_fmt = pd.Timestamp(min_date).strftime("%b %d, %Y")
            max_fmt = pd.Timestamp(max_date).strftime("%b %d, %Y")
            st.markdown(
                f'<span class="hero-badge">📅 Data: {min_fmt} → {max_fmt}</span>',
                unsafe_allow_html=True,
            )
        except Exception:
            pass

    with col_meta:
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("🗄️ DuckDB · 🔄 dbt · 📊 Streamlit")

    st.markdown("<br>", unsafe_allow_html=True)


# =============================================================================
# UPCOMING RACES
# =============================================================================

def render_upcoming_races(df_calendar: pd.DataFrame) -> None:
    """
    Render upcoming race countdown cards sourced from the Garmin calendar.

    Each card shows a countdown badge, race name, distance category, and date.
    Badge colour shifts from blue → orange → red as race day approaches.
    Only upcoming events are shown (is_upcoming = True), capped at 4 cards.

    Args:
        df_calendar: DataFrame from load_calendar_events(). May be empty.
    """
    st.markdown('<p class="section-header">🗓️ Upcoming Races</p>', unsafe_allow_html=True)

    if df_calendar is None or df_calendar.empty:
        st.info(
            "📋 No upcoming races found in your Garmin calendar. "
            "Register for a race in the Garmin Connect app and sync again."
        )
        return

    # Filter to future events only
    df_upcoming = df_calendar[
        df_calendar["is_upcoming"].astype(bool) == True
    ].copy()

    if df_upcoming.empty:
        st.info(
            "📋 All calendar events are in the past. "
            "Check the Race Performance page to review your history."
        )
        return

    df_upcoming["event_date"] = pd.to_datetime(df_upcoming["event_date"])
    df_upcoming = df_upcoming.sort_values("event_date").head(4)

    cols = st.columns(len(df_upcoming), gap="medium")

    # Distance → emoji mapping for visual recognition at a glance
    dist_icons = {
        "5K":            "5️⃣",
        "10K":           "🔟",
        "Half Marathon": "🏅",
        "Marathon":      "🏆",
        "Ultra":         "💪",
    }

    for col, (_, row) in zip(cols, df_upcoming.iterrows()):
        with col:
            days_left = int(row.get("days_until_race", 0))
            race_date = row["event_date"].strftime("%b %d, %Y")
            title     = row.get("title") or "Race"
            dist_cat  = row.get("race_distance_category") or ""
            location  = row.get("location") or ""
            race_url  = row.get("url") or ""

            # Countdown badge: red < 14 days, orange < 30 days, blue otherwise
            if days_left <= 14:
                badge_color = "#EF233C"
            elif days_left <= 30:
                badge_color = "#F77F00"
            else:
                badge_color = "#0077B6"

            dist_icon = dist_icons.get(dist_cat, "🏁")
            countdown_label = "TODAY" if days_left == 0 else f"In {days_left} day{'s' if days_left != 1 else ''}"

            # Build optional HTML blocks as plain strings first — nested
            # f-string conditionals inside st.markdown() f-strings can be
            # rendered as raw text by Streamlit instead of as HTML.
            location_block = (
                f'<div style="font-size:0.78rem; color:#6C757D; text-align:center; margin-top:2px;">'
                f'📍 {location}</div>'
            ) if location else ""

            link_block = (
                f'<div style="text-align:center; margin-top:8px;">'
                f'<a href="{race_url}" target="_blank" style="font-size:0.75rem; color:#0077B6;">'
                f'🔗 Race info</a></div>'
            ) if race_url else ""

            card_html = f"""
            <div style="background:#FFFFFF; border:1px solid #E0EAF5;
                        border-radius:12px; padding:16px 14px;
                        border-top:4px solid {badge_color};
                        box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                <div style="text-align:center; margin-bottom:10px;">
                    <span style="background:{badge_color}; color:white;
                                font-size:0.8rem; font-weight:700;
                                padding:3px 10px; border-radius:20px;">
                        {countdown_label}
                    </span>
                </div>
                <div style="font-size:1.4rem; text-align:center;">{dist_icon}</div>
                <div style="font-size:0.95rem; font-weight:700; color:#1A1A2E;
                            text-align:center; margin:6px 0 4px;">{title}</div>
                <div style="font-size:0.8rem; color:#6C757D; text-align:center;">📅 {race_date}</div>
                {location_block}
                {link_block}
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)


# =============================================================================
# TREND CHARTS
# =============================================================================

def render_trends(df_training: pd.DataFrame, weeks: int) -> None:
    """
    Render the two main trend charts side by side.

    Left  → Weekly distance bar chart with 4-week rolling average overlay
    Right → Training load (TRIMP) bar chart with rolling average overlay

    These charts give the runner the "shape" of their training week at a glance,
    which is more actionable than raw numbers alone.

    Args:
        df_training: Training DataFrame from mart_training_summary.
        weeks: Number of recent weeks to show (controlled by sidebar slider).
    """
    st.markdown('<p class="section-header">📈 Training Trends</p>', unsafe_allow_html=True)

    col_left, col_right = st.columns(2)

    with col_left:
        fig_distance = chart_weekly_distance(df_training, weeks=weeks)
        st.plotly_chart(fig_distance, use_container_width=True)

    with col_right:
        fig_load = chart_training_load(df_training, weeks=weeks)
        st.plotly_chart(fig_load, use_container_width=True)


# =============================================================================
# RECENT ACTIVITIES TABLE
# =============================================================================

def render_recent_activities(df: pd.DataFrame, selected_types: list | None = None) -> None:
    """
    Render a formatted table of recent activities enriched with weather data.

    Weather columns (temperature, condition) are fetched separately from the
    bronze layer and joined by activity_date, because weather is not yet
    propagated to the silver/gold layers.

    Args:
        df: Recent activities DataFrame from load_recent_activities().
        selected_types: Raw activity_type values to display (e.g. ["running"]).
                        Pass an empty list or None to show all types.
    """
    st.markdown('<p class="section-header">🏃 Recent Activities</p>', unsafe_allow_html=True)

    if df.empty:
        st.info("No activities found. Run the ingestion pipeline first.")
        return

    # ── Activity type filter ──────────────────────────────────────────────────
    if selected_types:
        df = df[df["activity_type"].str.lower().isin(
            [t.lower() for t in selected_types]
        )]
        if df.empty:
            st.info(
                "No activities match the selected type filter. "
                "Try adding more types in the sidebar."
            )
            return

    # ── Load and cache weather data ───────────────────────────────────────────
    # Weather is stored in the bronze layer and not yet in staging/marts,
    # so we join on activity_date after loading it separately.
    if "weather_data" not in st.session_state:
        df_weather_raw = load_weather_data()
        if not df_weather_raw.empty:
            df_weather_raw["activity_date"] = pd.to_datetime(df_weather_raw["activity_date"])
        st.session_state["weather_data"] = df_weather_raw

    df_weather = st.session_state["weather_data"]

    # Prepare a copy for merging (avoid mutating the cached DataFrame)
    df_copy = df.copy()
    df_copy["activity_date"] = pd.to_datetime(df_copy["activity_date"])

    if not df_weather.empty:
        weather_slim = (
            df_weather[["activity_date", "temp_c", "weather_condition"]]
            .drop_duplicates("activity_date")
        )
        df_copy = df_copy.merge(weather_slim, on="activity_date", how="left")
    else:
        df_copy["temp_c"]            = None
        df_copy["weather_condition"] = None

    # ── Weather condition → short emoji label ─────────────────────────────────
    def _weather_icon(condition: str | None) -> str:
        """Map a Garmin weather condition string to an emoji + short label."""
        if not condition or pd.isna(condition):
            return "—"
        cond = str(condition).lower()
        if any(k in cond for k in ["sunny", "clear"]):      return "☀️ Clear"
        if any(k in cond for k in ["cloud", "overcast"]):   return "☁️ Cloudy"
        if any(k in cond for k in ["rain", "drizzle"]):     return "🌧️ Rain"
        if any(k in cond for k in ["snow", "sleet"]):       return "❄️ Snow"
        if any(k in cond for k in ["wind", "gust"]):        return "💨 Windy"
        if "fog" in cond or "mist" in cond:                 return "🌫️ Foggy"
        if "thunder" in cond or "storm" in cond:            return "⛈️ Storm"
        return condition.capitalize()

    # ── Build the display DataFrame ───────────────────────────────────────────
    # All values are formatted as human-readable strings before passing to
    # st.dataframe(), so Streamlit renders them as text (not raw floats).
    display_df = pd.DataFrame({
        "Date":     df_copy["activity_date"].apply(format_date),
        "Activity": df_copy["activity_name"].fillna("Run"),
        "Type":     df_copy["activity_type"].apply(
                        lambda t: (
                            ACTIVITY_TYPES.get(str(t).lower(), {"icon": "⚡", "label": str(t)})["icon"]
                            + " "
                            + ACTIVITY_TYPES.get(str(t).lower(), {"icon": "⚡", "label": str(t)})["label"]
                        )
                    ),
        "Distance": df_copy["distance_km"].apply(format_distance),
        "Duration": df_copy["duration_minutes"].apply(format_duration),
        "Pace":     df_copy["pace_min_km"].apply(format_pace),
        "Avg HR":   df_copy["avg_heart_rate"].apply(format_heart_rate),
        "Zone":     df_copy["pace_zone"].fillna("—").str.capitalize(),
        "Temp":     df_copy["temp_c"].apply(
                        lambda t: f"{t:.0f}°C" if pd.notna(t) else "—"
                    ),
        "Weather":  df_copy["weather_condition"].apply(_weather_icon),
    })

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Inform the user if weather columns are all empty
    if display_df["Temp"].eq("—").all():
        st.caption(
            "💡 **No weather data yet.** Re-run the ingestion script to populate "
            "temperature and conditions: `python -m ingestion.ingest_garmin --days 30`"
        )


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    """
    Orchestrate the home page (merged home + dashboard):
        1. CSS
        2. Data load
        3. Sidebar (needs df_training for the slider max)
        4. Hero header
        5. All-time stats
        6. This week's KPIs
        7. Today's recovery
        8. Upcoming races
        9. Training trends (charts)
        10. Recent activities table
        11. Footer
    """
    load_css()

    # Load data — show a helpful error if the database isn't ready yet
    try:
        (df_training, df_health, df_race,
         df_activities, df_calendar,
         min_date, max_date) = _load_data_cached()
    except FileNotFoundError:
        st.error(
            "⚠️ **Database not found.**\n\n"
            "Run the ingestion script at least once:\n"
            "```bash\npython -m ingestion.ingest_garmin --days 30\n```"
        )
        st.stop()
        return
    except Exception as e:
        st.error(f"⚠️ Failed to load data: {e}")
        st.stop()
        return

    # Sidebar must come after data load (needs df_training for slider max)
    weeks, selected_types = render_sidebar(df_training)

    # ── Hero header ───────────────────────────────────────────────────────────
    render_header(min_date, max_date)

    # ── All-time stats ────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">🏆 All-Time Stats</p>', unsafe_allow_html=True)
    render_all_time_stats(df_training, df_race)

    st.divider()

    # ── This week's KPIs ──────────────────────────────────────────────────────
    # render_training_summary shows the last `weeks` weeks of data, but the
    # most actionable summary for "this week" is always the most recent entry.
    st.markdown('<p class="section-header">📊 This Period</p>', unsafe_allow_html=True)
    render_training_summary(df_training, weeks=weeks)

    st.divider()

    # ── Today's recovery ──────────────────────────────────────────────────────
    st.markdown('<p class="section-header">⚡ Today\'s Recovery</p>', unsafe_allow_html=True)
    render_recovery_status(df_health)

    st.divider()

    # ── Upcoming races ────────────────────────────────────────────────────────
    render_upcoming_races(df_calendar)

    st.divider()

    # ── Training trends (charts) ──────────────────────────────────────────────
    render_trends(df_training, weeks=weeks)

    st.divider()

    # ── Recent activities table ───────────────────────────────────────────────
    render_recent_activities(df_activities, selected_types=selected_types)

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.caption(
        "Running Performance Analyzer · "
        "Data from Garmin Connect API · "
        "Transformed with dbt · "
        "Built for portfolio & personal analytics"
    )


if __name__ == "__main__":
    main()
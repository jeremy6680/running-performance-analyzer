"""
Race Performance Page - Running Performance Analyzer
=====================================================
Displays race history, PR tracking, and performance trends.

Data source: main_gold.mart_race_performance
Grain: one row per race (activities flagged as races via Garmin event_type = 'race'
       or keyword detection in activity name)

Real schema columns (verified 2026-02-17):
    race_id, race_date, race_year, race_month, race_quarter, race_season,
    race_number, race_number_this_year,
    race_distance_category, distance_km, distance_meters,
    duration_minutes, finish_time_formatted, pace_min_per_km,
    avg_heart_rate_bpm, max_heart_rate_bpm, elevation_gain_m,
    training_load, effort_level,
    is_personal_record, pr_duration_minutes, pr_pace_min_per_km,
    minutes_off_pr, pct_off_pr,
    avg_training_pace_30d, total_training_distance_30d, training_runs_30d,
    race_vs_training_pace_diff, race_readiness_score,
    days_since_last_race,
    pace_ma_3_races, pace_change_vs_last_race,
    performance_rating, pacing_assessment, recovery_status,
    goal_race_name, goal_time_formatted_target, goal_time_seconds,
    seconds_vs_goal, goal_achievement, goal_notes

Technical notes:
- Uses st.session_state instead of @st.cache_data (DuckDB 1.4.4 compatibility)
- Environment: venv_streamlit
"""

import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="Race Performance | Running Performance Analyzer",
    page_icon="🏃",
    layout="wide",
)

# =============================================================================
# CONSTANTS
# =============================================================================

DB_PATH = str(Path(__file__).parent.parent.parent / "data" / "duckdb" / "running_analytics.duckdb")

# Garmin-inspired color palette (consistent across all pages)
COLORS = {
    "primary":   "#00B4D8",  # Garmin blue
    "secondary": "#0077B6",  # Darker blue
    "accent":    "#F77F00",  # Orange
    "success":   "#2DC653",  # Green — PR / good performance
    "warning":   "#FFD60A",  # Yellow — near PR
    "danger":    "#EF233C",  # Red — off day
    "card_bg":   "#FFFFFF",
    "text":      "#1A1A2E",
    "muted":     "#6C757D",
}

# Performance rating → color mapping
RATING_COLORS = {
    "PR":       COLORS["success"],
    "Near PR":  COLORS["warning"],
    "Good":     COLORS["primary"],
    "Fair":     COLORS["accent"],
    "Off Day":  COLORS["danger"],
}

# Standard race distances for ordering / filtering
DISTANCE_ORDER = ["5K", "10K", "Half Marathon", "Marathon", "Ultra"]

# =============================================================================
# CUSTOM CSS
# =============================================================================

st.markdown("""
<style>
    .section-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #1A1A2E;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #00B4D8;
        margin-bottom: 1.2rem;
    }

    /* PR badge */
    .pr-badge {
        display: inline-block;
        background: #2DC653;
        color: white;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 10px;
        letter-spacing: 0.05em;
    }

    /* Performance rating pill */
    .rating-pill {
        display: inline-block;
        font-size: 0.8rem;
        font-weight: 600;
        padding: 2px 10px;
        border-radius: 10px;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# DATABASE HELPERS
# =============================================================================

def get_db_connection():
    """Open a read-only DuckDB connection. Returns None on error."""
    try:
        return duckdb.connect(DB_PATH, read_only=True)
    except Exception as e:
        st.error(f"❌ Cannot connect to database: {e}")
        return None


def load_races() -> pd.DataFrame:
    """
    Load all race records from mart_race_performance.
    Caches result in st.session_state for the duration of the session.

    Returns:
        pd.DataFrame: All races, empty DataFrame on error.
    """
    if "race_performance" in st.session_state:
        return st.session_state["race_performance"]

    conn = get_db_connection()
    if conn is None:
        return pd.DataFrame()

    try:
        df = conn.execute("""
            SELECT *
            FROM main_gold.mart_race_performance
            ORDER BY race_date ASC
        """).df()

        df["race_date"] = pd.to_datetime(df["race_date"])
        st.session_state["race_performance"] = df
        return df

    except Exception as e:
        st.warning(f"⚠️ Could not load race data: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def load_calendar() -> pd.DataFrame:
    """
    Load upcoming calendar race events from the silver layer.
    Caches result in st.session_state for the session duration.

    Returns:
        pd.DataFrame: Calendar events (empty DataFrame on error).
    """
    if "calendar_events" in st.session_state:
        return st.session_state["calendar_events"]

    conn = get_db_connection()
    if conn is None:
        return pd.DataFrame()

    try:
        df = conn.execute("""
            SELECT
                event_uuid,
                title,
                event_date,
                location,
                distance_km,
                race_distance_category,
                is_upcoming,
                days_until_race,
                race_season,
                start_time,
                url
            FROM main_silver.stg_garmin_calendar_events
            ORDER BY event_date ASC
        """).df()

        df["event_date"] = pd.to_datetime(df["event_date"])
        st.session_state["calendar_events"] = df
        return df

    except Exception as e:
        # Table may not exist yet — silently return empty
        return pd.DataFrame()
    finally:
        conn.close()


def clear_cache():
    """Clear cached race data to force a refresh."""
    for key in ["race_performance", "calendar_events"]:
        if key in st.session_state:
            del st.session_state[key]

# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    st.header("⚙️ Filters")

    if st.button("🔄 Refresh data", use_container_width=True):
        clear_cache()
        st.rerun()

    st.divider()

    # Distance filter — populated dynamically from data
    st.subheader("🏅 Distance")
    distance_filter = st.multiselect(
        "Race distance",
        options=DISTANCE_ORDER,
        default=[],
        placeholder="All distances",
    )

    st.divider()

    # Year filter
    st.subheader("📅 Year")
    year_filter = st.multiselect(
        "Race year",
        options=[],   # populated below after data loads
        default=[],
        placeholder="All years",
        key="year_filter_placeholder",
    )

# =============================================================================
# PAGE HEADER
# =============================================================================

st.title("🏃 Race Performance")
st.caption("Personal records, race history, and performance trends.")

# =============================================================================
# UPCOMING RACES (from Garmin calendar)
# =============================================================================
# Displayed at the top of the page so the user sees what’s coming up next.
# Goal times (from race_goals seed) are joined to calendar events by
# matching race_distance_category so the runner can see target vs. plan.

df_calendar = load_calendar()

# Load race_goals seed to show target times alongside calendar events
# We load them from DuckDB directly (seeded by dbt) rather than reading the CSV
_goals_conn = get_db_connection()
_goals_df   = pd.DataFrame()
if _goals_conn is not None:
    try:
        _goals_df = _goals_conn.execute("""
            SELECT race_date, race_name, race_distance_category,
                   goal_time_formatted, notes
            FROM main_seeds.race_goals
        """).df()
        _goals_df["race_date"] = pd.to_datetime(_goals_df["race_date"])
    except Exception:
        pass
    finally:
        _goals_conn.close()

if not df_calendar.empty:
    st.markdown('<p class="section-header">🗓️ Upcoming Races</p>', unsafe_allow_html=True)

    df_upcoming = df_calendar[df_calendar["is_upcoming"].astype(bool)].copy()

    if df_upcoming.empty:
        st.info("📋 No upcoming races in your Garmin calendar. All scheduled events are in the past.")
    else:
        df_upcoming = df_upcoming.sort_values("event_date")

        # Join goal times to calendar events (match on date first, then distance category)
        if not _goals_df.empty:
            df_upcoming = df_upcoming.merge(
                _goals_df.rename(columns={
                    "race_date":              "goal_match_date",
                    "race_name":              "goal_name",
                    "goal_time_formatted":    "goal_time",
                    "notes":                  "goal_notes",
                    "race_distance_category": "goal_dist_cat",
                }),
                left_on="event_date",
                right_on="goal_match_date",
                how="left",
            )
        else:
            df_upcoming["goal_time"]  = None
            df_upcoming["goal_notes"] = None

        cols = st.columns(min(len(df_upcoming), 4), gap="medium")

        for i, (_, row) in enumerate(df_upcoming.iterrows()):
            with cols[i % min(len(df_upcoming), 4)]:
                days_left = int(row.get("days_until_race", 0))
                race_date = row["event_date"].strftime("%b %d, %Y")
                title     = row.get("title") or "Race"
                dist_cat  = row.get("race_distance_category") or ""
                location  = row.get("location") or ""
                race_url  = row.get("url") or ""
                goal_time = row.get("goal_time") or ""
                goal_note = row.get("goal_notes") or ""

                if days_left <= 14:
                    border_color = "#EF233C"
                elif days_left <= 30:
                    border_color = "#F77F00"
                else:
                    border_color = "#0077B6"

                dist_icons = {
                    "5K": "5️⃣", "10K": "🔟",
                    "Half Marathon": "🏅", "Marathon": "🏆", "Ultra": "💪",
                }
                dist_icon = dist_icons.get(dist_cat, "🏁")

                countdown_label = "TODAY" if days_left == 0 else f"In {days_left} day{'s' if days_left != 1 else ''}"

                goal_block = (
                    f'<div style="margin-top:8px; background:#EBF5FB; border-radius:6px; padding:6px 8px;">'
                    f'<span style="font-size:0.75rem; color:#0077B6; font-weight:700;">🎯 Goal: {goal_time}</span>'
                    + (f'<br><span style="font-size:0.72rem; color:#5F6368;">{goal_note}</span>' if goal_note else "")
                    + "</div>"
                ) if goal_time else ""

                # Build the link as a bare <a> tag only — the wrapping <div> is
                # added conditionally in the f-string below. This mirrors the
                # pattern used in app.py and avoids Streamlit 1.45 markdown
                # stripping the HTML when a full block-level <div> is injected
                # as a Python variable rather than as literal template text.
                link_html = (
                    f'<a href="{race_url}" target="_blank" '
                    f'style="font-size:0.75rem; color:#0077B6;">🔗 Race info</a>'
                ) if race_url else ""

                st.markdown(f"""
                <div style="background:#FFFFFF; border:1px solid #E0EAF5;
                            border-radius:12px; padding:16px 14px;
                            border-top:4px solid {border_color};
                            box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                    <div style="text-align:center; margin-bottom:10px;">
                        <span style="background:{border_color}; color:white;
                                    font-size:0.8rem; font-weight:700;
                                    padding:3px 10px; border-radius:20px;">
                            {countdown_label}
                        </span>
                    </div>
                    <div style="font-size:1.4rem; text-align:center;">{dist_icon}</div>
                    <div style="font-size:1rem; font-weight:700; color:#1A1A2E;
                                text-align:center; margin:6px 0 4px;">{title}</div>
                    <div style="font-size:0.8rem; color:#6C757D; text-align:center;">📅 {race_date}</div>
                    {f'<div style="font-size:0.78rem; color:#6C757D; text-align:center; margin-top:2px;">📍 {location}</div>' if location else ''}
                    {goal_block}
                    {f'<div style="text-align:center; margin-top:8px;">{link_html}</div>' if link_html else ''}
                </div>
                """, unsafe_allow_html=True)

    st.divider()

# =============================================================================
# LOAD DATA
# =============================================================================

df_all = load_races()

# --- Empty state ---
if df_all.empty:
    st.info(
        "**No race data found yet.**\n\n"
        "Races are detected automatically when:\n"
        "- You tag an activity as **Race** in Garmin Connect (most reliable)\n"
        "- The activity name contains keywords like *race*, *marathon*, *10K*, *trail*\n\n"
        "Your next race will appear here automatically after the next data sync.",
        icon="🏅",
    )
    st.stop()

# --- Populate year filter now that data is loaded ---
available_years = sorted(df_all["race_year"].dropna().unique().astype(int).tolist(), reverse=True)

# Re-render sidebar year filter with real options
with st.sidebar:
    year_filter = st.multiselect(
        "Race year",
        options=available_years,
        default=[],
        placeholder="All years",
        key="year_filter_real",
    )

# --- Apply filters ---
df = df_all.copy()

if distance_filter:
    df = df[df["race_distance_category"].isin(distance_filter)]

if year_filter:
    df = df[df["race_year"].isin(year_filter)]

if df.empty:
    st.warning("No races match the selected filters. Try broadening your selection.")
    st.stop()

# =============================================================================
# SECTION 1 — SUMMARY METRICS
# =============================================================================

st.markdown('<p class="section-header">🏅 Career Summary</p>', unsafe_allow_html=True)

total_races   = len(df)
total_prs     = int(df["is_personal_record"].sum())
distances_run = df["race_distance_category"].dropna().nunique()
best_rating   = df["performance_rating"].value_counts().idxmax() if not df.empty else "—"

# Best 10K pace (most common distance)
best_pace_row = df[df["race_distance_category"] == "10K"].sort_values("pace_min_per_km").head(1)
best_10k_pace = f"{best_pace_row['pace_min_per_km'].values[0]:.2f} min/km" if not best_pace_row.empty else "—"

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("🏁 Total Races", total_races)
with col2:
    st.metric("🥇 Personal Records", total_prs)
with col3:
    st.metric("📏 Distances Raced", distances_run)
with col4:
    st.metric("⚡ Best 10K Pace", best_10k_pace)
with col5:
    st.metric("📊 Most Common Rating", best_rating)

st.divider()

# =============================================================================
# SECTION 2 — RACE HISTORY TABLE
# =============================================================================

st.markdown('<p class="section-header">📋 Race History</p>', unsafe_allow_html=True)

# Build a clean display DataFrame
display_cols = {
    "race_date":              "Date",
    "race_distance_category": "Distance",
    "distance_km":            "Dist (km)",
    "finish_time_formatted":  "Finish Time",
    "pace_min_per_km":        "Pace (min/km)",
    "avg_heart_rate_bpm":     "Avg HR",
    "performance_rating":     "Rating",
    "is_personal_record":     "PR",
    "pct_off_pr":             "% off PR",
    "race_readiness_score":   "Readiness",
    "recovery_status":        "Recovery",
}

# Only include columns that exist in the DataFrame
available_display_cols = {k: v for k, v in display_cols.items() if k in df.columns}

df_display = (
    df[list(available_display_cols.keys())]
    .copy()
    .sort_values("race_date", ascending=False)
    .rename(columns=available_display_cols)
)

# Format date for display
df_display["Date"] = pd.to_datetime(df_display["Date"]).dt.strftime("%b %d, %Y")

# Format PR column as emoji
if "PR" in df_display.columns:
    df_display["PR"] = df_display["PR"].apply(lambda x: "🥇" if x else "")

# Format % off PR
if "% off PR" in df_display.columns:
    df_display["% off PR"] = df_display["% off PR"].apply(
        lambda x: f"+{x:.1f}%" if pd.notna(x) and x > 0 else ("PR" if pd.notna(x) else "—")
    )

# Round numeric columns
for col, decimals in [("Dist (km)", 2), ("Pace (min/km)", 2), ("Avg HR", 0)]:
    if col in df_display.columns:
        df_display[col] = df_display[col].round(decimals)

st.dataframe(
    df_display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Rating": st.column_config.TextColumn("Rating"),
        "Readiness": st.column_config.NumberColumn(
            "Readiness (1-10)",
            help="Training readiness score based on volume and recovery in the 30 days before the race",
            format="%d / 10",
        ),
    },
)

st.divider()

# =============================================================================
# SECTION 3 — PACE PROGRESSION CHART
# =============================================================================

st.markdown('<p class="section-header">📈 Pace Progression</p>', unsafe_allow_html=True)

# Only chart distances with at least one race
chartable = df.dropna(subset=["race_distance_category", "pace_min_per_km"])

if not chartable.empty:
    # Color by performance rating so PRs stand out
    fig_pace = px.scatter(
        chartable,
        x="race_date",
        y="pace_min_per_km",
        color="performance_rating",
        symbol="race_distance_category",
        size="distance_km",
        size_max=18,
        color_discrete_map=RATING_COLORS,
        category_orders={"performance_rating": list(RATING_COLORS.keys())},
        hover_name="race_distance_category",
        hover_data={
            "race_date":             "|%b %d, %Y",
            "pace_min_per_km":       ":.2f",
            "finish_time_formatted": True,
            "performance_rating":    True,
            "is_personal_record":    True,
            "distance_km":           False,  # hidden (used for size only)
        },
        labels={
            "race_date":         "Race Date",
            "pace_min_per_km":   "Pace (min/km)",
            "performance_rating": "Rating",
            "race_distance_category": "Distance",
        },
    )

    # Add PR annotation lines per distance category
    for dist_cat in chartable["race_distance_category"].unique():
        dist_df = chartable[chartable["race_distance_category"] == dist_cat]
        pr_pace = dist_df["pace_min_per_km"].min()
        fig_pace.add_hline(
            y=pr_pace,
            line_dash="dot",
            line_color=COLORS["success"],
            opacity=0.5,
            annotation_text=f"{dist_cat} PR: {pr_pace:.2f}",
            annotation_position="top right",
            annotation_font_size=11,
        )

    fig_pace.update_layout(
        height=380,
        margin=dict(t=30, b=10, l=10, r=10),
        plot_bgcolor=COLORS["card_bg"],
        paper_bgcolor=COLORS["card_bg"],
        yaxis=dict(
            title="Pace (min/km) — lower = faster",
            autorange="reversed",  # faster pace (lower number) at top
            gridcolor="#E8ECF0",
        ),
        xaxis=dict(title=None, showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig_pace, use_container_width=True)
    st.caption(
        "Pace axis is inverted — lower on screen = faster pace. "
        "Green dashed lines mark your current PR at each distance. "
        "🥇 Green dots = Personal Records."
    )

else:
    st.info("Not enough race data to plot pace progression.")

st.divider()

# =============================================================================
# SECTION 4 — PR CARDS PER DISTANCE
# =============================================================================

st.markdown('<p class="section-header">🥇 Personal Records</p>', unsafe_allow_html=True)

# Group PRs by distance category — one row per distance (the fastest race).
# We use idxmin() to find the index of the fastest pace per group, then
# select those rows directly from the DataFrame. This is simpler and faster
# than groupby.apply(), and avoids the pandas 2.2 FutureWarning about
# grouping columns being included in apply callbacks.
_df_races = df.dropna(subset=["race_distance_category", "pace_min_per_km"])
pr_idx = _df_races.groupby("race_distance_category")["pace_min_per_km"].idxmin()
pr_distances = _df_races.loc[pr_idx].reset_index(drop=True)

# Order by standard race distances
pr_distances["_order"] = pr_distances["race_distance_category"].apply(
    lambda d: DISTANCE_ORDER.index(d) if d in DISTANCE_ORDER else 99
)
pr_distances = pr_distances.sort_values("_order")

if not pr_distances.empty:
    cols = st.columns(min(len(pr_distances), 4))

    for i, (_, row) in enumerate(pr_distances.iterrows()):
        with cols[i % len(cols)]:
            race_date_str = pd.to_datetime(row["race_date"]).strftime("%b %d, %Y")
            pace = f"{row['pace_min_per_km']:.2f} min/km"
            finish = row.get("finish_time_formatted", "—")

            st.markdown(f"""
            <div style="background:#FFFFFF; border:1px solid #E8ECF0; border-radius:10px;
                        padding:1rem 1.2rem; text-align:center; border-top: 4px solid #2DC653;">
                <div style="font-size:1.8rem; margin-bottom:0.3rem;">🥇</div>
                <div style="font-size:1.1rem; font-weight:700; color:#1A1A2E;">
                    {row['race_distance_category']}
                </div>
                <div style="font-size:1.4rem; font-weight:700; color:#2DC653; margin:0.4rem 0;">
                    {finish}
                </div>
                <div style="font-size:0.9rem; color:#6C757D;">{pace}</div>
                <div style="font-size:0.8rem; color:#6C757D; margin-top:0.3rem;">{race_date_str}</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("")  # spacing

else:
    st.info("No PR data available for the selected filters.")

st.divider()

# =============================================================================
# SECTION 4b — GOAL ACHIEVEMENT
# =============================================================================
# Show planned vs actual times for races that have a goal set in race_goals.csv
# Columns: goal_race_name, goal_time_formatted_target, seconds_vs_goal, goal_achievement

goal_races = df[df["goal_race_name"].notna()].sort_values("race_date") if "goal_race_name" in df.columns else pd.DataFrame()

if not goal_races.empty:
    st.markdown('<p class="section-header">🎯 Goal Achievement</p>', unsafe_allow_html=True)

    # Summary row: how many goals achieved?
    total_goals    = len(goal_races)
    achieved       = (goal_races["goal_achievement"] == "Goal achieved ✅").sum()
    just_missed    = (goal_races["goal_achievement"] == "Just missed (<2%)").sum()
    missed         = total_goals - achieved - just_missed

    col_g1, col_g2, col_g3 = st.columns(3)
    with col_g1:
        st.metric("🎯 Goals set", total_goals)
    with col_g2:
        st.metric("✅ Achieved", achieved)
    with col_g3:
        st.metric("❌ Missed", missed)

    st.markdown("")

    # One card per goal race
    goal_cols = st.columns(min(len(goal_races), 3))

    for i, (_, row) in enumerate(goal_races.iterrows()):
        with goal_cols[i % len(goal_cols)]:
            race_date_str = pd.to_datetime(row["race_date"]).strftime("%b %d, %Y")
            actual        = row.get("finish_time_formatted", "—")
            target        = row.get("goal_time_formatted_target", "—")
            achievement   = row.get("goal_achievement", "No goal set")
            dist_cat      = row.get("race_distance_category", "")
            notes         = row.get("goal_notes", "")

            # Seconds vs goal — format as +/- string
            secs = row.get("seconds_vs_goal")
            if pd.notna(secs):
                sign    = "+" if secs > 0 else ""
                abs_min = int(abs(secs) // 60)
                abs_sec = int(abs(secs) % 60)
                delta_str = f"{sign}{abs_min}:{abs_sec:02d}"
                delta_color = "#EF233C" if secs > 0 else "#2DC653"
            else:
                delta_str   = "—"
                delta_color = "#6C757D"

            # Card border color by achievement
            if "achieved" in achievement:
                border_color = "#2DC653"
                icon = "✅"
            elif "Just missed" in achievement:
                border_color = "#FFD60A"
                icon = "🔶"
            elif "No goal" in achievement:
                border_color = "#6C757D"
                icon = "📋"
            else:
                border_color = "#EF233C"
                icon = "❌"

            st.markdown(f"""
            <div style="background:#FFF; border:1px solid #E8ECF0; border-radius:10px;
                        padding:1rem 1.2rem; border-left:5px solid {border_color};">
                <div style="font-size:1rem; font-weight:700; color:#1A1A2E;">
                    {icon} {row.get('goal_race_name', dist_cat)}
                </div>
                <div style="font-size:0.8rem; color:#6C757D; margin-top:2px;">
                    {dist_cat} · {race_date_str}
                </div>
                <div style="display:flex; justify-content:space-between; margin-top:0.8rem;">
                    <div>
                        <div style="font-size:0.75rem; color:#6C757D; text-transform:uppercase;">Target</div>
                        <div style="font-size:1.2rem; font-weight:700; color:#1A1A2E;">{target}</div>
                    </div>
                    <div>
                        <div style="font-size:0.75rem; color:#6C757D; text-transform:uppercase;">Actual</div>
                        <div style="font-size:1.2rem; font-weight:700; color:#1A1A2E;">{actual}</div>
                    </div>
                    <div>
                        <div style="font-size:0.75rem; color:#6C757D; text-transform:uppercase;">Delta</div>
                        <div style="font-size:1.2rem; font-weight:700; color:{delta_color};">{delta_str}</div>
                    </div>
                </div>
                {f'<div style="font-size:0.78rem; color:#6C757D; margin-top:0.6rem; font-style:italic;">{notes}</div>' if notes else ''}
            </div>
            """, unsafe_allow_html=True)
            st.markdown("")

    st.divider()

# =============================================================================
# SECTION 5 — TRAINING CONTEXT (race readiness)
# =============================================================================

if "race_readiness_score" in df.columns and df["race_readiness_score"].notna().any():

    st.markdown('<p class="section-header">🎯 Race Readiness & Training Context</p>', unsafe_allow_html=True)

    df_context = df.dropna(subset=["race_readiness_score"]).sort_values("race_date")

    if len(df_context) > 0:
        col_chart, col_table = st.columns([3, 2])

        with col_chart:
            fig_ready = go.Figure()

            fig_ready.add_trace(go.Bar(
                x=df_context["race_date"].dt.strftime("%b %d, %Y"),
                y=df_context["race_readiness_score"],
                marker_color=[
                    COLORS["success"] if v >= 8
                    else COLORS["warning"] if v >= 6
                    else COLORS["danger"]
                    for v in df_context["race_readiness_score"]
                ],
                text=df_context["race_readiness_score"].astype(str) + " / 10",
                textposition="outside",
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Readiness: %{y}/10<extra></extra>"
                ),
            ))

            fig_ready.update_layout(
                height=280,
                margin=dict(t=20, b=10, l=10, r=10),
                plot_bgcolor=COLORS["card_bg"],
                paper_bgcolor=COLORS["card_bg"],
                yaxis=dict(range=[0, 11], gridcolor="#E8ECF0", title="Score (1–10)"),
                xaxis=dict(showgrid=False),
                showlegend=False,
            )

            st.plotly_chart(fig_ready, use_container_width=True)
            st.caption(
                "Readiness score (1–10) based on training volume and recovery "
                "in the 30 days before each race. Green ≥ 8, Yellow ≥ 6, Red < 6."
            )

        with col_table:
            # Training context table
            ctx_cols = {
                "race_date":                   "Race",
                "total_training_distance_30d": "Volume 30d (km)",
                "training_runs_30d":           "Runs 30d",
                "avg_training_pace_30d":       "Avg Pace 30d",
                "race_vs_training_pace_diff":  "Pace diff",
                "pacing_assessment":           "Assessment",
            }
            available_ctx = {k: v for k, v in ctx_cols.items() if k in df_context.columns}
            df_ctx_display = df_context[list(available_ctx.keys())].rename(columns=available_ctx).copy()
            df_ctx_display["Race"] = pd.to_datetime(df_ctx_display["Race"]).dt.strftime("%b %d")

            for col in ["Volume 30d (km)", "Avg Pace 30d", "Pace diff"]:
                if col in df_ctx_display.columns:
                    df_ctx_display[col] = df_ctx_display[col].round(2)

            st.dataframe(df_ctx_display, use_container_width=True, hide_index=True)

    st.divider()

# =============================================================================
# SECTION 6 — RAW DATA (collapsible)
# =============================================================================

with st.expander("🗃️ View full race data", expanded=False):
    if not df.empty:
        df_raw = df.copy()
        df_raw["race_date"] = df_raw["race_date"].dt.strftime("%b %d, %Y")
        st.dataframe(df_raw, use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False)
        st.download_button(
            "⬇️ Download as CSV",
            data=csv,
            file_name="race_performance.csv",
            mime="text/csv",
        )

# =============================================================================
# FOOTER
# =============================================================================

st.markdown("---")
st.caption(
    "Data source: Garmin Connect API → DuckDB (main_gold.mart_race_performance). "
    "Races detected via Garmin event_type = 'race' or activity name keywords. "
    "PR = best pace per distance category across all synced history."
)

# streamlit_app/pages/1_📈_Training_Analysis.py
# Renumbered from 2 → 1 after merging the old Dashboard page into app.py.
"""
Training Analysis Page - Running Performance Analyzer
======================================================
Displays training load, pace progression, heart rate zones,
and distance/duration analysis with interactive filters.

Technical notes:
- Uses st.session_state instead of @st.cache_data (DuckDB 1.4.4 compatibility)
- Table: mart_training_summary (column names verified against real schema)
- Table: stg_garmin_activities (for individual activity detail)
- Environment: venv_streamlit
"""

import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="Training Analysis | Running Performance Analyzer",
    page_icon="📈",
    layout="wide",
)

# =============================================================================
# CONSTANTS
# =============================================================================

# Path to DuckDB database (relative to project root)
DB_PATH = str(Path(__file__).parent.parent.parent / "data" / "duckdb" / "running_analytics.duckdb")

# Garmin-inspired color palette (consistent with page 1)
COLORS = {
    "primary":    "#00B4D8",  # Garmin blue
    "secondary":  "#0077B6",  # Darker blue
    "accent":     "#F77F00",  # Orange for load / effort
    "success":    "#2DC653",  # Green
    "warning":    "#FFD60A",  # Yellow
    "danger":     "#EF233C",  # Red
    "light_bg":   "#F0F4F8",
    "card_bg":    "#FFFFFF",
    "text":       "#1A1A2E",
    "muted":      "#6C757D",
}

# Heart rate zones (standard Garmin zones, % of max HR)
HR_ZONES = {
    "Zone 1 – Easy":       {"color": "#2DC653", "range": "< 60% max HR"},
    "Zone 2 – Aerobic":    {"color": "#00B4D8", "range": "60-70% max HR"},
    "Zone 3 – Tempo":      {"color": "#FFD60A", "range": "70-80% max HR"},
    "Zone 4 – Threshold":  {"color": "#F77F00", "range": "80-90% max HR"},
    "Zone 5 – VO2max":     {"color": "#EF233C", "range": "90-100% max HR"},
}

# Pace zone labels mapped to activity fields
PACE_ZONE_LABELS = {
    "zone_1": "Z1 Easy",
    "zone_2": "Z2 Aerobic",
    "zone_3": "Z3 Tempo",
    "zone_4": "Z4 Threshold",
    "zone_5": "Z5 VO2max",
}

# =============================================================================
# CUSTOM CSS
# =============================================================================

st.markdown("""
<style>
    /* Section headers */
    .section-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #1A1A2E;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #00B4D8;
        margin-bottom: 1.2rem;
    }

    /* Info banner */
    .info-banner {
        background: #EBF5FB;
        border-left: 4px solid #00B4D8;
        border-radius: 4px;
        padding: 0.8rem 1rem;
        margin-bottom: 1.2rem;
        font-size: 0.9rem;
        color: #1A1A2E;
    }

    /* Insight card */
    .insight-card {
        background: #FFFFFF;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        border: 1px solid #E8ECF0;
        margin-bottom: 0.8rem;
    }

    .insight-card .label {
        font-size: 0.8rem;
        color: #6C757D;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .insight-card .value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1A1A2E;
    }

    .insight-card .delta {
        font-size: 0.85rem;
        margin-top: 0.2rem;
    }

    .delta-positive { color: #2DC653; }
    .delta-negative { color: #EF233C; }
    .delta-neutral  { color: #6C757D; }

    /* Zone legend pill */
    .zone-pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.78rem;
        font-weight: 600;
        color: #fff;
        margin-right: 4px;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# DATABASE CONNECTION & DATA LOADING
# =============================================================================

def get_db_connection():
    """
    Open a read-only DuckDB connection.
    Returns connection or None on error.
    """
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        return conn
    except Exception as e:
        st.error(f"❌ Cannot connect to database: {e}")
        return None


def get_table_columns(table: str, schema: str = "main_gold") -> list:
    """
    Utility: return the real column names for a given table.
    Useful for debugging schema mismatches.

    Args:
        table:  Table name (e.g. "mart_training_summary")
        schema: DuckDB schema name (default "main_gold")

    Returns:
        list of column name strings, or empty list on error
    """
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        result = conn.execute(
            f"SELECT column_name FROM information_schema.columns "
            f"WHERE table_schema = '{schema}' AND table_name = '{table}' "
            f"ORDER BY ordinal_position"
        ).fetchall()
        return [row[0] for row in result]
    except Exception:
        return []
    finally:
        conn.close()


def load_training_summary():
    """
    Load weekly aggregated training data from mart_training_summary.
    Uses st.session_state to avoid Arrow serialization issues with DuckDB 1.4.4.

    Column name mapping (real schema vs initial assumptions):
        total_activities        ← was: total_runs
        total_duration_minutes  ← was: total_duration_hours  (converted below)
        avg_pace_min_km         ← was: avg_pace_min_per_km
        avg_heart_rate          ← was: avg_heart_rate_bpm (aliased below)

    Returns:
        pd.DataFrame: Weekly training summary (empty DataFrame on error)
    """
    # Return cached data if already loaded this session
    if "training_summary" in st.session_state:
        return st.session_state["training_summary"]

    conn = get_db_connection()
    if conn is None:
        return pd.DataFrame()

    try:
        query = """
            SELECT *
            FROM main_gold.mart_training_summary
            ORDER BY week_start_date ASC
        """
        result = conn.execute(query)
        columns = [desc[0] for desc in result.description]
        df = pd.DataFrame(result.fetchall(), columns=columns)

        # ── Normalise column names to what the rest of the page expects ──────
        rename_map = {
            "avg_pace_min_km": "avg_pace_min_per_km",
            "avg_heart_rate":  "avg_heart_rate_bpm",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        # Convert duration: if total_duration_minutes exists but total_duration_hours does not
        if "total_duration_minutes" in df.columns and "total_duration_hours" not in df.columns:
            df["total_duration_hours"] = df["total_duration_minutes"] / 60.0

        # ── Compute total_runs (running activities only) per week ─────────────
        try:
            runs_per_week_query = """
                SELECT
                    DATE_TRUNC('week', activity_date) AS week_start_date,
                    COUNT(*)                          AS total_runs
                FROM main_silver.stg_garmin_activities
                WHERE activity_type = 'running'
                GROUP BY 1
            """
            r2 = conn.execute(runs_per_week_query)
            df_runs = pd.DataFrame(r2.fetchall(), columns=[d[0] for d in r2.description])
            df_runs["week_start_date"] = pd.to_datetime(df_runs["week_start_date"])
            df = df.merge(df_runs, on="week_start_date", how="left")
            df["total_runs"] = df["total_runs"].fillna(0).astype(int)
        except Exception:
            if "total_activities" in df.columns:
                df["total_runs"] = df["total_activities"]
                df["_runs_count_approximate"] = True

        df["week_start_date"] = pd.to_datetime(df["week_start_date"])
        st.session_state["training_summary"] = df
        return df

    except Exception as e:
        st.warning(f"⚠️ Could not load training summary: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def load_activities():
    """
    Load individual activity records from stg_garmin_activities.
    Used for pace scatter and recent activity detail.

    Returns:
        pd.DataFrame: Activity records (empty DataFrame on error)
    """
    if "activities_detail" in st.session_state:
        return st.session_state["activities_detail"]

    conn = get_db_connection()
    if conn is None:
        return pd.DataFrame()

    try:
        query = """
            SELECT
                activity_id,
                activity_name,
                activity_date,
                activity_type,
                event_type,
                distance_km,
                duration_minutes,
                moving_duration_minutes,
                CASE
                    WHEN avg_pace_min_km >= 2.0
                     AND avg_pace_min_km <= 20.0  THEN avg_pace_min_km
                    WHEN distance_km > 0           THEN ROUND(duration_minutes / distance_km, 3)
                    ELSE NULL
                END AS avg_pace_min_km,
                avg_speed_kmh,
                avg_heart_rate,
                max_heart_rate,
                elevation_gain_m,
                elevation_loss_m,
                calories,
                training_load,
                effort_level,
                pace_zone,
                hr_zone,
                is_race,
                race_distance_category,
                terrain_type,
                time_of_day,
                is_weekend,
                has_data_quality_issues,
                has_unrealistic_pace
            FROM main_silver.stg_garmin_activities
            WHERE activity_type = 'running'
            ORDER BY activity_date ASC
        """
        result = conn.execute(query)
        columns = [desc[0] for desc in result.description]
        df = pd.DataFrame(result.fetchall(), columns=columns)

        rename_map = {
            "avg_pace_min_km":  "avg_pace_min_per_km",
            "avg_heart_rate":   "avg_heart_rate_bpm",
            "max_heart_rate":   "max_heart_rate_bpm",
            "elevation_gain":   "elevation_gain_m",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        if "duration_seconds" in df.columns and "duration_minutes" not in df.columns:
            df["duration_minutes"] = df["duration_seconds"] / 60.0

        df["activity_date"] = pd.to_datetime(df["activity_date"])
        st.session_state["activities_detail"] = df
        return df

    except Exception as e:
        st.warning(f"⚠️ Could not load activity data: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def clear_session_cache():
    """Clear cached DataFrames to force a data refresh on next load."""
    for key in ["training_summary", "activities_detail"]:
        if key in st.session_state:
            del st.session_state[key]

# =============================================================================
# SIDEBAR – FILTERS
# =============================================================================

with st.sidebar:
    st.header("⚙️ Filters")

    if st.button("🔄 Refresh data", use_container_width=True):
        clear_session_cache()
        st.rerun()

    st.divider()

    st.subheader("📅 Period")

    period_option = st.radio(
        "Quick select",
        ["Last 4 weeks", "Last 3 months", "Last 6 months", "Last 12 months", "All time", "Custom"],
        index=1,
    )

    today = pd.Timestamp.today().normalize()

    if period_option == "Last 4 weeks":
        date_start = today - pd.DateOffset(weeks=4)
        date_end   = today
    elif period_option == "Last 3 months":
        date_start = today - pd.DateOffset(months=3)
        date_end   = today
    elif period_option == "Last 6 months":
        date_start = today - pd.DateOffset(months=6)
        date_end   = today
    elif period_option == "Last 12 months":
        date_start = today - pd.DateOffset(months=12)
        date_end   = today
    elif period_option == "All time":
        date_start = pd.Timestamp("2000-01-01")
        date_end   = today
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            date_start = pd.Timestamp(
                st.date_input("From", value=today - pd.DateOffset(months=3))
            )
        with col_b:
            date_end = pd.Timestamp(
                st.date_input("To", value=today)
            )

    st.divider()

    st.subheader("📊 Chart options")
    show_rolling = st.toggle("Show 4-week rolling avg", value=True)
    show_targets = st.toggle("Show effort level on scatter", value=True)

# =============================================================================
# PAGE HEADER
# =============================================================================

st.title("📈 Training Analysis")
st.caption("Weekly training load, pace progression, and heart rate zone distribution.")

with st.expander("🔧 Debug: inspect real column names", expanded=False):
    st.markdown("Use this to verify exact column names in your DuckDB tables.")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.markdown("**mart_training_summary**")
        cols_summary = get_table_columns("mart_training_summary", "main_gold")
        if cols_summary:
            st.code("\n".join(cols_summary))
        else:
            st.warning("Could not read columns.")
    with col_d2:
        st.markdown("**stg_garmin_activities**")
        cols_act = get_table_columns("stg_garmin_activities", "main_silver")
        if cols_act:
            st.code("\n".join(cols_act))
        else:
            st.warning("Could not read columns.")

# =============================================================================
# LOAD & FILTER DATA
# =============================================================================

df_summary  = load_training_summary()
df_activity = load_activities()

if not df_summary.empty:
    mask_s = (df_summary["week_start_date"] >= date_start) & \
             (df_summary["week_start_date"] <= date_end)
    df_summary_filtered = df_summary[mask_s].copy()
else:
    df_summary_filtered = df_summary.copy()

if not df_activity.empty:
    mask_a = (df_activity["activity_date"] >= date_start) & \
             (df_activity["activity_date"] <= date_end)
    df_activity_filtered = df_activity[mask_a].copy()
else:
    df_activity_filtered = df_activity.copy()

if df_summary_filtered.empty and df_activity_filtered.empty:
    st.markdown("""
    <div class="info-banner">
        ℹ️ No training data found for the selected period.
        Try a wider date range or sync your Garmin data first.
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# =============================================================================
# SECTION 1 – KEY METRICS ROW
# =============================================================================

st.markdown('<p class="section-header">📊 Period Summary</p>', unsafe_allow_html=True)

if not df_summary_filtered.empty:

    total_runs      = int(df_summary_filtered["total_runs"].sum())
    total_distance  = df_summary_filtered["total_distance_km"].sum()
    total_hours     = df_summary_filtered["total_duration_hours"].sum()
    avg_weekly_dist = df_summary_filtered["total_distance_km"].mean()
    total_load      = df_summary_filtered["total_training_load"].sum()

    mid = len(df_summary_filtered) // 2
    if mid > 0:
        dist_first  = df_summary_filtered.iloc[:mid]["total_distance_km"].mean()
        dist_second = df_summary_filtered.iloc[mid:]["total_distance_km"].mean()
        dist_delta  = ((dist_second - dist_first) / dist_first * 100) if dist_first > 0 else 0
        load_first  = df_summary_filtered.iloc[:mid]["total_training_load"].mean()
        load_second = df_summary_filtered.iloc[mid:]["total_training_load"].mean()
        load_delta  = ((load_second - load_first) / load_first * 100) if load_first > 0 else 0
    else:
        dist_delta = load_delta = 0.0

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("🏃 Total Runs", f"{total_runs}")
    with col2:
        st.metric(
            "📏 Total Distance",
            f"{total_distance:.0f} km",
            delta=f"{dist_delta:+.1f}% vs first half" if mid > 0 else None,
        )
    with col3:
        hours = int(total_hours)
        minutes = int((total_hours - hours) * 60)
        st.metric("⏱ Total Time", f"{hours}h {minutes:02d}m")
    with col4:
        st.metric("📅 Avg/Week", f"{avg_weekly_dist:.1f} km")
    with col5:
        st.metric(
            "⚡ Total Load",
            f"{total_load:.0f}",
            delta=f"{load_delta:+.1f}% vs first half" if mid > 0 else None,
            help="Training Stress Score (TRIMP) — cumulative training impulse over the period",
        )

    st.divider()

# =============================================================================
# SECTION 2 – TRAINING LOAD CHART
# =============================================================================

st.markdown('<p class="section-header">⚡ Weekly Training Load</p>', unsafe_allow_html=True)

if not df_summary_filtered.empty:

    fig_load = go.Figure()

    fig_load.add_trace(go.Bar(
        x=df_summary_filtered["week_start_date"],
        y=df_summary_filtered["total_training_load"],
        name="Weekly Load (TRIMP)",
        marker_color=COLORS["accent"],
        opacity=0.8,
        hovertemplate=(
            "<b>Week of %{x|%b %d, %Y}</b><br>"
            "Training Load: %{y:.0f} TRIMP<extra></extra>"
        ),
    ))

    if show_rolling and "rolling_4wk_avg_training_load" in df_summary_filtered.columns:
        fig_load.add_trace(go.Scatter(
            x=df_summary_filtered["week_start_date"],
            y=df_summary_filtered["rolling_4wk_avg_training_load"],
            name="4-week Rolling Avg",
            mode="lines",
            line=dict(color=COLORS["secondary"], width=2.5, dash="solid"),
            hovertemplate=(
                "<b>Week of %{x|%b %d, %Y}</b><br>"
                "4-wk Avg Load: %{y:.0f} TRIMP<extra></extra>"
            ),
        ))

    fig_load.update_layout(
        height=340,
        margin=dict(t=20, b=10, l=10, r=10),
        plot_bgcolor=COLORS["card_bg"],
        paper_bgcolor=COLORS["card_bg"],
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title=None, showgrid=False, tickformat="%b %Y"),
        yaxis=dict(title="TRIMP (Training Impulse)", gridcolor="#E8ECF0", zeroline=False),
        hovermode="x unified",
        bargap=0.3,
    )

    st.plotly_chart(fig_load, use_container_width=True)
    st.caption(
        "TRIMP (Training Impulse) combines workout duration and heart rate intensity. "
        "A steady load trend (blue line) signals consistent training without spikes."
    )

else:
    st.info("No training load data available for this period.")

st.divider()

# =============================================================================
# SECTION 3 – WEEKLY DISTANCE + PACE PROGRESSION (dual axis)
# =============================================================================

st.markdown('<p class="section-header">📏 Distance & Pace Progression</p>', unsafe_allow_html=True)

if not df_summary_filtered.empty:

    fig_dist = make_subplots(specs=[[{"secondary_y": True}]])

    fig_dist.add_trace(
        go.Bar(
            x=df_summary_filtered["week_start_date"],
            y=df_summary_filtered["total_distance_km"],
            name="Weekly Distance (km)",
            marker_color=COLORS["primary"],
            opacity=0.75,
            hovertemplate=(
                "<b>Week of %{x|%b %d, %Y}</b><br>"
                "Distance: %{y:.1f} km<extra></extra>"
            ),
        ),
        secondary_y=False,
    )

    if show_rolling and "rolling_4wk_avg_distance_km" in df_summary_filtered.columns:
        fig_dist.add_trace(
            go.Scatter(
                x=df_summary_filtered["week_start_date"],
                y=df_summary_filtered["rolling_4wk_avg_distance_km"],
                name="4-wk Avg Distance",
                mode="lines",
                line=dict(color=COLORS["secondary"], width=2.5),
                hovertemplate=(
                    "<b>Week of %{x|%b %d, %Y}</b><br>"
                    "4-wk Avg: %{y:.1f} km<extra></extra>"
                ),
            ),
            secondary_y=False,
        )

    if "avg_pace_min_per_km" in df_summary_filtered.columns:
        df_pace = df_summary_filtered.dropna(subset=["avg_pace_min_per_km"])
        if not df_pace.empty:
            fig_dist.add_trace(
                go.Scatter(
                    x=df_pace["week_start_date"],
                    y=df_pace["avg_pace_min_per_km"],
                    name="Avg Pace (min/km)",
                    mode="lines+markers",
                    line=dict(color=COLORS["danger"], width=2),
                    marker=dict(size=5),
                    hovertemplate=(
                        "<b>Week of %{x|%b %d, %Y}</b><br>"
                        "Avg Pace: %{y:.2f} min/km<extra></extra>"
                    ),
                ),
                secondary_y=True,
            )

    fig_dist.update_layout(
        height=340,
        margin=dict(t=20, b=10, l=10, r=10),
        plot_bgcolor=COLORS["card_bg"],
        paper_bgcolor=COLORS["card_bg"],
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        bargap=0.3,
    )
    fig_dist.update_xaxes(showgrid=False, tickformat="%b %Y")
    fig_dist.update_yaxes(title_text="Distance (km)", gridcolor="#E8ECF0", zeroline=False, secondary_y=False)
    fig_dist.update_yaxes(title_text="Pace (min/km) — lower = faster", secondary_y=True, showgrid=False, autorange="reversed")

    st.plotly_chart(fig_dist, use_container_width=True)
    st.caption(
        "Pace axis is inverted: a lower position means a faster average pace. "
        "Look for distance growth paired with stable or improving (downward) pace — that's fitness progress."
    )

else:
    st.info("No distance/pace data available for this period.")

st.divider()

# =============================================================================
# SECTION 4 – HEART RATE ZONE DISTRIBUTION
# =============================================================================

st.markdown('<p class="section-header">❤️ Heart Rate Zone Distribution</p>', unsafe_allow_html=True)

def _find_zone_cols(df: pd.DataFrame) -> list:
    """
    Try multiple naming conventions to locate HR zone percentage columns.
    Returns 5 column names in Z1–Z5 order, or an empty list if not found.
    """
    candidates = [
        ["pct_zone1_easy", "pct_zone2_moderate", "pct_zone3_tempo", "pct_zone4_threshold", "pct_zone5_max"],
        ["zone_1_pct", "zone_2_pct", "zone_3_pct", "zone_4_pct", "zone_5_pct"],
        ["hr_zone_1_pct", "hr_zone_2_pct", "hr_zone_3_pct", "hr_zone_4_pct", "hr_zone_5_pct"],
        ["pct_zone_1", "pct_zone_2", "pct_zone_3", "pct_zone_4", "pct_zone_5"],
        ["zone1_pct", "zone2_pct", "zone3_pct", "zone4_pct", "zone5_pct"],
    ]
    for pattern in candidates:
        if all(c in df.columns for c in pattern):
            return pattern
    return []

zone_cols = _find_zone_cols(df_summary_filtered)
has_zones = not df_summary_filtered.empty and len(zone_cols) == 5

if has_zones:
    col_chart, col_legend = st.columns([2, 1])

    with col_chart:
        avg_zones = {
            "Zone 1 – Easy":      df_summary_filtered[zone_cols[0]].mean(),
            "Zone 2 – Aerobic":   df_summary_filtered[zone_cols[1]].mean(),
            "Zone 3 – Tempo":     df_summary_filtered[zone_cols[2]].mean(),
            "Zone 4 – Threshold": df_summary_filtered[zone_cols[3]].mean(),
            "Zone 5 – VO2max":    df_summary_filtered[zone_cols[4]].mean(),
        }

        zone_colors = [z["color"] for z in HR_ZONES.values()]

        fig_zones = go.Figure(go.Bar(
            x=list(avg_zones.keys()),
            y=list(avg_zones.values()),
            marker_color=zone_colors,
            text=[f"{v:.1f}%" for v in avg_zones.values()],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Average: %{y:.1f}%<extra></extra>",
        ))

        fig_zones.update_layout(
            height=300,
            margin=dict(t=30, b=10, l=10, r=10),
            plot_bgcolor=COLORS["card_bg"],
            paper_bgcolor=COLORS["card_bg"],
            showlegend=False,
            yaxis=dict(
                title="% of time in zone",
                range=[0, max(avg_zones.values()) * 1.25],
                gridcolor="#E8ECF0",
                ticksuffix="%",
            ),
            xaxis=dict(showgrid=False),
        )

        st.plotly_chart(fig_zones, use_container_width=True)

    with col_legend:
        st.markdown("**Zones explained:**")
        for zone_name, zone_info in HR_ZONES.items():
            st.markdown(
                f'<span class="zone-pill" style="background:{zone_info["color"]}">{zone_name.split("–")[0].strip()}</span>'
                f' {zone_name.split("–")[1].strip()} — {zone_info["range"]}',
                unsafe_allow_html=True,
            )
            st.markdown("")

        st.divider()
        z1 = df_summary_filtered[zone_cols[0]].mean()
        z2 = df_summary_filtered[zone_cols[1]].mean()
        easy_pct = z1 + z2

        if easy_pct >= 70:
            st.success(f"✅ {easy_pct:.0f}% easy running — great aerobic base!")
        elif easy_pct >= 50:
            st.warning(f"⚠️ {easy_pct:.0f}% easy running — consider slowing down more.")
        else:
            st.error(f"❗ Only {easy_pct:.0f}% easy running — injury risk if sustained.")

        st.caption("The '80/20 rule': 80% of runs should be easy (Z1-Z2), 20% hard.")

else:
    st.info("Heart rate zone data not yet available. Make sure your Garmin activities include heart rate data.")

st.divider()

# =============================================================================
# SECTION 5 – DISTANCE vs DURATION SCATTER
# =============================================================================

st.markdown('<p class="section-header">🔍 Activity Detail: Distance vs Duration</p>', unsafe_allow_html=True)

if not df_activity_filtered.empty:

    if show_targets and "effort_level" in df_activity_filtered.columns:
        color_col   = "effort_level"
        color_label = "Effort Level"
    elif "pace_zone" in df_activity_filtered.columns:
        color_col   = "pace_zone"
        color_label = "Pace Zone"
    else:
        color_col   = None
        color_label = None

    scatter_df = df_activity_filtered.dropna(subset=["distance_km", "duration_minutes"])
    fig_scatter = px.scatter(
        scatter_df,
        x="distance_km",
        y="duration_minutes",
        color=color_col if color_col else None,
        size="training_load" if "training_load" in scatter_df.columns else None,
        size_max=20,
        hover_name="activity_name",
        hover_data={
            "activity_date": "|%b %d, %Y",
            "distance_km":    ":.2f",
            "duration_minutes": ":.0f",
            "avg_pace_min_per_km": ":.2f",
            "avg_heart_rate_bpm": ":.0f",
            color_col: True,
        },
        labels={
            "distance_km":         "Distance (km)",
            "duration_minutes":    "Duration (min)",
            "avg_pace_min_per_km": "Avg Pace (min/km)",
            "avg_heart_rate_bpm":  "Avg HR (bpm)",
            color_col:             color_label,
        },
        color_discrete_sequence=px.colors.qualitative.Safe,
    )

    fig_scatter.update_layout(
        height=380,
        margin=dict(t=20, b=10, l=10, r=10),
        plot_bgcolor=COLORS["card_bg"],
        paper_bgcolor=COLORS["card_bg"],
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(gridcolor="#E8ECF0", title="Distance (km)"),
        yaxis=dict(gridcolor="#E8ECF0", title="Duration (minutes)"),
    )

    st.plotly_chart(fig_scatter, use_container_width=True)
    st.caption(
        f"Each dot = one run. Size = training load. Color = {color_label.lower() if color_label else 'none'}. "
        "Points should form a consistent diagonal band — outliers may indicate unusual conditions."
    )

else:
    st.info("No individual activity data available for this period.")

st.divider()

# =============================================================================
# SECTION 5b – WEATHER ANALYSIS
# =============================================================================

if "weather_data" not in st.session_state:
    from utils.database import load_weather_data
    raw_weather = load_weather_data()
    if not raw_weather.empty:
        raw_weather["activity_date"] = pd.to_datetime(raw_weather["activity_date"])
    st.session_state["weather_data"] = raw_weather

df_weather_all = st.session_state["weather_data"]

if not df_weather_all.empty:
    df_weather = df_weather_all[
        (df_weather_all["activity_date"] >= date_start) &
        (df_weather_all["activity_date"] <= date_end) &
        (df_weather_all["activity_type"] == "running")
    ].copy()
else:
    df_weather = pd.DataFrame()

if not df_weather.empty:
    st.divider()
    st.markdown('<p class="section-header">☀️ Weather & Performance</p>', unsafe_allow_html=True)

    avg_temp  = df_weather["temp_c"].mean()
    avg_humid = df_weather["humidity_pct"].mean()
    avg_wind  = df_weather["wind_kmh"].mean()
    n_weather = len(df_weather)

    wc1, wc2, wc3, wc4 = st.columns(4)
    with wc1:
        st.metric("🌡️ Avg Temperature", f"{avg_temp:.1f}°C")
    with wc2:
        st.metric("💧 Avg Humidity", f"{avg_humid:.0f}%")
    with wc3:
        st.metric("💨 Avg Wind", f"{avg_wind:.1f} km/h")
    with wc4:
        st.metric("📦 Runs with data", n_weather)

    st.markdown("")

    wcol_left, wcol_right = st.columns(2)

    with wcol_left:
        st.markdown("**🌡️ Temperature vs Pace**")
        st.caption("Does heat slow you down? Ideally you want consistent pace across temperatures.")

        fig_temp_pace = px.scatter(
            df_weather.dropna(subset=["temp_c", "avg_pace_min_km"]),
            x="temp_c",
            y="avg_pace_min_km",
            color="humidity_pct",
            size="distance_km",
            size_max=18,
            color_continuous_scale="Blues",
            hover_name="activity_name",
            hover_data={
                "activity_date":   "|%b %d, %Y",
                "temp_c":          ":.1f",
                "avg_pace_min_km": ":.2f",
                "humidity_pct":    ":.0f",
                "wind_kmh":        ":.1f",
                "distance_km":     False,
            },
            labels={
                "temp_c":          "Temperature (°C)",
                "avg_pace_min_km": "Pace (min/km)",
                "humidity_pct":    "Humidity (%)",
            },
        )

        weather_clean = df_weather.dropna(subset=["temp_c", "avg_pace_min_km"])
        if len(weather_clean) >= 3:
            import numpy as np
            z = np.polyfit(weather_clean["temp_c"], weather_clean["avg_pace_min_km"], 1)
            p = np.poly1d(z)
            x_range = pd.Series(sorted([weather_clean["temp_c"].min(), weather_clean["temp_c"].max()]))
            fig_temp_pace.add_scatter(
                x=x_range,
                y=p(x_range),
                mode="lines",
                line=dict(color=COLORS["danger"], dash="dot", width=2),
                name="Trend",
                showlegend=True,
            )

        fig_temp_pace.update_layout(
            height=320,
            margin=dict(t=20, b=10, l=10, r=10),
            plot_bgcolor=COLORS["card_bg"],
            paper_bgcolor=COLORS["card_bg"],
            yaxis=dict(autorange="reversed", title="Pace (min/km) — lower = faster", gridcolor="#E8ECF0"),
            xaxis=dict(title="Temperature (°C)", gridcolor="#E8ECF0"),
            coloraxis_colorbar=dict(title="Humidity %"),
        )
        st.plotly_chart(fig_temp_pace, use_container_width=True)

    with wcol_right:
        st.markdown("**💨 Wind vs Pace**")
        st.caption("High wind typically increases effort. Look for upward trend with wind.")

        fig_wind_pace = px.scatter(
            df_weather.dropna(subset=["wind_kmh", "avg_pace_min_km"]),
            x="wind_kmh",
            y="avg_pace_min_km",
            color="temp_c",
            size="distance_km",
            size_max=18,
            color_continuous_scale="RdYlBu_r",
            hover_name="activity_name",
            hover_data={
                "activity_date":   "|%b %d, %Y",
                "wind_kmh":        ":.1f",
                "avg_pace_min_km": ":.2f",
                "temp_c":          ":.1f",
                "humidity_pct":    ":.0f",
                "distance_km":     False,
            },
            labels={
                "wind_kmh":        "Wind Speed (km/h)",
                "avg_pace_min_km": "Pace (min/km)",
                "temp_c":          "Temp (°C)",
            },
        )

        fig_wind_pace.update_layout(
            height=320,
            margin=dict(t=20, b=10, l=10, r=10),
            plot_bgcolor=COLORS["card_bg"],
            paper_bgcolor=COLORS["card_bg"],
            yaxis=dict(autorange="reversed", title="Pace (min/km) — lower = faster", gridcolor="#E8ECF0"),
            xaxis=dict(title="Wind Speed (km/h)", gridcolor="#E8ECF0"),
            coloraxis_colorbar=dict(title="Temp °C"),
        )
        st.plotly_chart(fig_wind_pace, use_container_width=True)

    st.markdown("**📅 Temperature Over Time**")

    fig_temp_time = px.scatter(
        df_weather.sort_values("activity_date"),
        x="activity_date",
        y="temp_c",
        color="avg_pace_min_km",
        size="distance_km",
        size_max=15,
        color_continuous_scale="RdYlBu_r",
        hover_name="activity_name",
        hover_data={
            "activity_date":   "|%b %d, %Y",
            "temp_c":          ":.1f",
            "humidity_pct":    ":.0f",
            "wind_kmh":        ":.1f",
            "avg_pace_min_km": ":.2f",
            "distance_km":     False,
        },
        labels={
            "activity_date":   "Date",
            "temp_c":          "Temperature (°C)",
            "avg_pace_min_km": "Pace (min/km)",
        },
    )
    fig_temp_time.update_layout(
        height=260,
        margin=dict(t=20, b=10, l=10, r=10),
        plot_bgcolor=COLORS["card_bg"],
        paper_bgcolor=COLORS["card_bg"],
        xaxis=dict(showgrid=False, tickformat="%b %Y"),
        yaxis=dict(gridcolor="#E8ECF0", title="Temp (°C)"),
        coloraxis_colorbar=dict(title="Pace min/km"),
    )
    st.plotly_chart(fig_temp_time, use_container_width=True)
    st.caption(
        "💡 Dot colour = pace (red = fast, blue = slow). Dot size = distance. "
        "Temperature is auto-detected and converted from Fahrenheit if needed."
    )

# =============================================================================
# SECTION 6 – RAW DATA TABLE (collapsible)
# =============================================================================

with st.expander("🗃️ View raw weekly data", expanded=False):

    if not df_summary_filtered.empty:

        display_df = df_summary_filtered.copy()
        display_df["week_start_date"] = display_df["week_start_date"].dt.strftime("%b %d, %Y")

        round_cols = {
            "total_distance_km":    1,
            "total_duration_hours": 2,
            "avg_pace_min_per_km":  2,
            "avg_heart_rate_bpm":   0,
            "total_training_load":  0,
        }
        for col, decimals in round_cols.items():
            if col in display_df.columns:
                display_df[col] = display_df[col].round(decimals)

        st.dataframe(display_df, use_container_width=True, hide_index=True)

        csv = df_summary_filtered.to_csv(index=False)
        st.download_button(
            label="⬇️ Download as CSV",
            data=csv,
            file_name="training_analysis.csv",
            mime="text/csv",
        )
    else:
        st.info("No data to display.")

# =============================================================================
# FOOTER
# =============================================================================

st.markdown("---")
st.caption(
    "Data source: Garmin Connect API → DuckDB (main_gold.mart_training_summary). "
    "TRIMP calculated from duration × avg HR intensity factor. "
    "HR zones based on standard Garmin 5-zone model."
)

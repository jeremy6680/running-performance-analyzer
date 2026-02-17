"""
Health & Recovery Page - Running Performance Analyzer
======================================================
Displays sleep trends, resting heart rate, HRV, stress,
body battery, and overall recovery score over time.

Data source: main_gold.mart_health_trends
Grain: one row per day

Real schema columns (verified 2026-02-17):
    date, day_of_week, week_start_date, month_start_date,
    -- Sleep
    total_sleep_hours, deep_sleep_hours, light_sleep_hours,
    rem_sleep_hours, awake_hours, sleep_quality_category,
    sleep_efficiency_pct, sleep_debt_hours, sleep_debt_7day_cumulative,
    sleep_7day_avg, sleep_28day_avg, sleep_change_vs_prev_day,
    sleep_change_vs_prev_week, sleep_vs_7day_avg,
    -- Heart Rate
    resting_heart_rate, min_heart_rate, max_heart_rate,
    rhr_7day_avg, rhr_28day_avg, rhr_change_vs_prev_day,
    rhr_change_vs_prev_week, rhr_vs_7day_avg,
    -- HRV
    hrv_numeric, hrv_status, hrv_category,
    -- Stress
    average_stress_level, stress_category, stress_7day_avg,
    stress_change_vs_prev_day, stress_vs_7day_avg,
    -- Body Battery
    body_battery_charged, body_battery_drained, body_battery_high,
    body_battery_low, body_battery_net_change, body_battery_status,
    -- Activity
    total_steps, total_distance_km, steps_7day_avg,
    -- Recovery
    recovery_score, stg_recovery_score, training_readiness,
    -- Weekly aggregates
    week_avg_sleep, week_avg_rhr, week_avg_stress, week_total_steps

Technical notes:
- Uses st.session_state instead of @st.cache_data (DuckDB 1.4.4 compatibility)
- Environment: venv_streamlit
"""

import streamlit as st
import duckdb
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="Health & Recovery | Running Performance Analyzer",
    page_icon="❤️",
    layout="wide",
)

# =============================================================================
# CONSTANTS
# =============================================================================

DB_PATH = str(
    Path(__file__).parent.parent.parent / "data" / "duckdb" / "running_analytics.duckdb"
)

COLORS = {
    "primary":   "#00B4D8",  # Garmin blue
    "secondary": "#0077B6",
    "accent":    "#F77F00",  # Orange
    "success":   "#2DC653",  # Green -- good recovery
    "warning":   "#FFD60A",  # Yellow -- moderate
    "danger":    "#EF233C",  # Red -- poor
    "hr":        "#EF233C",  # Red -- heart rate
    "hrv":       "#00B4D8",  # Blue -- HRV
    "battery":   "#2DC653",  # Green -- body battery
    "card_bg":   "#FFFFFF",
    "muted":     "#6C757D",
}

# Training readiness label -> color
READINESS_COLORS = {
    "optimal":  COLORS["success"],
    "good":     COLORS["primary"],
    "moderate": COLORS["warning"],
    "low":      COLORS["danger"],
}

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
    .readiness-badge {
        display: inline-block;
        font-size: 0.85rem;
        font-weight: 700;
        padding: 3px 12px;
        border-radius: 12px;
        color: white;
        text-transform: capitalize;
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
        st.error(f"Cannot connect to database: {e}")
        return None


def load_health_trends() -> pd.DataFrame:
    """
    Load daily health records from mart_health_trends.
    Caches result in st.session_state for the duration of the browser session.

    Returns:
        pd.DataFrame sorted ascending by date, or empty DataFrame on error.
    """
    if "health_trends" in st.session_state:
        return st.session_state["health_trends"]

    conn = get_db_connection()
    if conn is None:
        return pd.DataFrame()

    try:
        df = conn.execute("""
            SELECT *
            FROM main_gold.mart_health_trends
            ORDER BY date ASC
        """).df()

        df["date"] = pd.to_datetime(df["date"])

        # week_total_steps is stored as HUGEINT in DuckDB.
        # Plotly cannot serialize Python's arbitrary-precision int128,
        # so we cast to int64 (safe: step counts never exceed int64 range).
        if "week_total_steps" in df.columns:
            df["week_total_steps"] = df["week_total_steps"].astype("int64")

        st.session_state["health_trends"] = df
        return df

    except Exception as e:
        st.warning(f"Could not load health data: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def clear_cache():
    """Remove cached health data so the next load re-queries DuckDB."""
    if "health_trends" in st.session_state:
        del st.session_state["health_trends"]

# =============================================================================
# SIDEBAR -- FILTERS
# =============================================================================

with st.sidebar:
    st.header("⚙️ Filters")

    if st.button("🔄 Refresh data", use_container_width=True):
        clear_cache()
        st.rerun()

    st.divider()

    st.subheader("📅 Period")
    period_option = st.radio(
        "Quick select",
        ["Last 2 weeks", "Last 4 weeks", "Last 3 months", "All time", "Custom"],
        index=1,   # default: last 4 weeks
    )

    today = pd.Timestamp.today().normalize()

    if period_option == "Last 2 weeks":
        date_start = today - pd.DateOffset(weeks=2)
        date_end   = today
    elif period_option == "Last 4 weeks":
        date_start = today - pd.DateOffset(weeks=4)
        date_end   = today
    elif period_option == "Last 3 months":
        date_start = today - pd.DateOffset(months=3)
        date_end   = today
    elif period_option == "All time":
        date_start = pd.Timestamp("2000-01-01")
        date_end   = today
    else:  # Custom
        col_a, col_b = st.columns(2)
        with col_a:
            date_start = pd.Timestamp(
                st.date_input("From", value=today - pd.DateOffset(weeks=4))
            )
        with col_b:
            date_end = pd.Timestamp(st.date_input("To", value=today))

    st.divider()
    st.subheader("📊 Chart options")
    show_7day_avg = st.toggle("Show 7-day rolling avg", value=True)

# =============================================================================
# PAGE HEADER
# =============================================================================

st.title("❤️ Health & Recovery")
st.caption("Sleep, heart rate, HRV, stress, and recovery trends from Garmin health data.")

# =============================================================================
# LOAD & FILTER DATA
# =============================================================================

df_all = load_health_trends()

if df_all.empty:
    st.info(
        "**No health data found yet.**\n\n"
        "Health data (sleep, HRV, stress, body battery) is synced daily from Garmin Connect. "
        "Run the ingestion script to populate this page:\n\n"
        "```bash\npython -m ingestion.ingest_garmin --days 30\n```",
        icon="❤️",
    )
    st.stop()

# Apply date filter
mask = (df_all["date"] >= date_start) & (df_all["date"] <= date_end)
df = df_all[mask].copy()

if df.empty:
    st.warning("No health data found for the selected period. Try a wider date range.")
    st.stop()

# =============================================================================
# SECTION 1 -- SUMMARY METRICS
# =============================================================================

st.markdown('<p class="section-header">📊 Period Summary</p>', unsafe_allow_html=True)

# Most recent day for the readiness badge
latest          = df.sort_values("date").iloc[-1]
readiness_now   = str(latest.get("training_readiness", "")).lower()
readiness_color = READINESS_COLORS.get(readiness_now, COLORS["muted"])

# Period averages -- guard against all-null columns
avg_sleep    = df["total_sleep_hours"].mean()
avg_rhr      = df["resting_heart_rate"].dropna().mean()
avg_hrv      = df["hrv_numeric"].dropna().mean()       if "hrv_numeric"       in df.columns else None
avg_stress   = df["average_stress_level"].dropna().mean()
avg_recovery = df["recovery_score"].dropna().mean()    if "recovery_score"    in df.columns else None
avg_steps    = df["total_steps"].dropna().mean()

col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    st.metric("😴 Avg Sleep",     f"{avg_sleep:.1f}h")
with col2:
    st.metric("❤️ Avg RHR",      f"{avg_rhr:.0f} bpm"    if pd.notna(avg_rhr)    else "—")
with col3:
    st.metric("📡 Avg HRV",      f"{avg_hrv:.0f} ms"     if avg_hrv is not None and pd.notna(avg_hrv) else "—")
with col4:
    st.metric("😰 Avg Stress",   f"{avg_stress:.0f}/100" if pd.notna(avg_stress) else "—")
with col5:
    st.metric("⚡ Avg Recovery",  f"{avg_recovery:.0f}/100" if avg_recovery is not None and pd.notna(avg_recovery) else "—")
with col6:
    st.metric("👟 Avg Steps",    f"{avg_steps:,.0f}"     if pd.notna(avg_steps)  else "—")

# Readiness badge for the most recent day
if readiness_now:
    st.markdown(
        f"**Latest training readiness:** "
        f'<span class="readiness-badge" style="background:{readiness_color}">'
        f"{readiness_now.capitalize()}</span>",
        unsafe_allow_html=True,
    )

st.divider()

# =============================================================================
# SECTION 2 -- SLEEP TRENDS
# =============================================================================

st.markdown('<p class="section-header">😴 Sleep Trends</p>', unsafe_allow_html=True)

col_sleep_chart, col_sleep_stages = st.columns([3, 2])

with col_sleep_chart:
    fig_sleep = go.Figure()

    # Bar: total sleep per night, color-coded by quality threshold
    fig_sleep.add_trace(go.Bar(
        x=df["date"],
        y=df["total_sleep_hours"],
        name="Total Sleep",
        marker_color=[
            COLORS["success"] if v >= 7.5
            else COLORS["warning"] if v >= 6.0
            else COLORS["danger"]
            for v in df["total_sleep_hours"].fillna(0)
        ],
        opacity=0.8,
        hovertemplate="<b>%{x|%b %d, %Y}</b><br>Sleep: %{y:.1f}h<extra></extra>",
    ))

    # Line: 7-day rolling average (toggle-able from sidebar)
    if show_7day_avg and "sleep_7day_avg" in df.columns:
        fig_sleep.add_trace(go.Scatter(
            x=df["date"],
            y=df["sleep_7day_avg"],
            name="7-day avg",
            mode="lines",
            line=dict(color=COLORS["secondary"], width=2.5),
            hovertemplate="7d avg: %{y:.1f}h<extra></extra>",
        ))

    # Horizontal reference line at 8 hours (widely recommended minimum)
    fig_sleep.add_hline(
        y=8.0,
        line_dash="dot",
        line_color=COLORS["success"],
        opacity=0.5,
        annotation_text="8h target",
        annotation_position="top right",
        annotation_font_size=11,
    )

    fig_sleep.update_layout(
        height=280,
        margin=dict(t=20, b=10, l=10, r=10),
        plot_bgcolor=COLORS["card_bg"],
        paper_bgcolor=COLORS["card_bg"],
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title="Hours", gridcolor="#E8ECF0", range=[0, 11]),
        xaxis=dict(showgrid=False, tickformat="%b %d"),
        bargap=0.2,
    )
    st.plotly_chart(fig_sleep, use_container_width=True)
    st.caption("Green >= 7.5h  |  Yellow 6–7.5h  |  Red < 6h.  Dashed = 8h target.")

with col_sleep_stages:
    # Stacked bar: sleep stages for the most recent 7 nights
    stage_cols   = ["deep_sleep_hours", "rem_sleep_hours", "light_sleep_hours", "awake_hours"]
    stage_labels = {
        "deep_sleep_hours":  "Deep",
        "rem_sleep_hours":   "REM",
        "light_sleep_hours": "Light",
        "awake_hours":       "Awake",
    }
    stage_colors = {
        "deep_sleep_hours":  "#0077B6",
        "rem_sleep_hours":   "#7B2FBE",
        "light_sleep_hours": "#00B4D8",
        "awake_hours":       "#FFD60A",
    }

    available_stages = [c for c in stage_cols if c in df.columns]
    df_stages = df[["date"] + available_stages].dropna().tail(7)

    if not df_stages.empty and available_stages:
        fig_stages = go.Figure()
        for col in available_stages:
            fig_stages.add_trace(go.Bar(
                name=stage_labels.get(col, col),
                x=df_stages["date"].dt.strftime("%a %d"),
                y=df_stages[col],
                marker_color=stage_colors.get(col, COLORS["muted"]),
                hovertemplate=f"{stage_labels.get(col, col)}: %{{y:.1f}}h<extra></extra>",
            ))
        fig_stages.update_layout(
            barmode="stack",
            height=280,
            margin=dict(t=35, b=10, l=10, r=10),
            plot_bgcolor=COLORS["card_bg"],
            paper_bgcolor=COLORS["card_bg"],
            title=dict(text="Sleep stages · last 7 nights", font_size=13),
            legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="right", x=1),
            yaxis=dict(title="Hours", gridcolor="#E8ECF0"),
            xaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig_stages, use_container_width=True)
    else:
        st.info("Sleep stage breakdown not available.")

st.divider()

# =============================================================================
# SECTION 3 -- RESTING HEART RATE & HRV
# =============================================================================

st.markdown('<p class="section-header">❤️ Resting Heart Rate & HRV</p>', unsafe_allow_html=True)

col_rhr, col_hrv = st.columns(2)

with col_rhr:
    df_rhr = df.dropna(subset=["resting_heart_rate"])
    if not df_rhr.empty:
        fig_rhr = go.Figure()
        fig_rhr.add_trace(go.Scatter(
            x=df_rhr["date"],
            y=df_rhr["resting_heart_rate"],
            name="RHR",
            mode="lines+markers",
            line=dict(color=COLORS["hr"], width=2),
            marker=dict(size=5),
            hovertemplate="<b>%{x|%b %d}</b><br>RHR: %{y} bpm<extra></extra>",
        ))
        if show_7day_avg and "rhr_7day_avg" in df_rhr.columns:
            fig_rhr.add_trace(go.Scatter(
                x=df_rhr["date"],
                y=df_rhr["rhr_7day_avg"],
                name="7-day avg",
                mode="lines",
                line=dict(color=COLORS["secondary"], width=2, dash="dash"),
                hovertemplate="7d avg: %{y:.1f} bpm<extra></extra>",
            ))
        fig_rhr.update_layout(
            height=260,
            margin=dict(t=20, b=10, l=10, r=10),
            plot_bgcolor=COLORS["card_bg"],
            paper_bgcolor=COLORS["card_bg"],
            title=dict(text="Resting Heart Rate (bpm)", font_size=13),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(gridcolor="#E8ECF0", title="bpm"),
            xaxis=dict(showgrid=False, tickformat="%b %d"),
        )
        st.plotly_chart(fig_rhr, use_container_width=True)
        st.caption("A sustained downward trend signals improving aerobic fitness.")
    else:
        st.info("No resting heart rate data available.")

with col_hrv:
    df_hrv = df.dropna(subset=["hrv_numeric"]) if "hrv_numeric" in df.columns else pd.DataFrame()
    if not df_hrv.empty:
        fig_hrv = go.Figure()
        fig_hrv.add_trace(go.Scatter(
            x=df_hrv["date"],
            y=df_hrv["hrv_numeric"],
            name="HRV",
            mode="lines+markers",
            line=dict(color=COLORS["hrv"], width=2),
            marker=dict(size=5),
            fill="tozeroy",
            fillcolor="rgba(0,180,216,0.10)",
            hovertemplate="<b>%{x|%b %d}</b><br>HRV: %{y:.0f} ms<extra></extra>",
        ))
        fig_hrv.update_layout(
            height=260,
            margin=dict(t=20, b=10, l=10, r=10),
            plot_bgcolor=COLORS["card_bg"],
            paper_bgcolor=COLORS["card_bg"],
            title=dict(text="Heart Rate Variability (ms)", font_size=13),
            showlegend=False,
            yaxis=dict(gridcolor="#E8ECF0", title="ms"),
            xaxis=dict(showgrid=False, tickformat="%b %d"),
        )
        st.plotly_chart(fig_hrv, use_container_width=True)
        st.caption(
            "Higher HRV = better recovery capacity. "
            "Sustained low HRV after hard training signals accumulated fatigue."
        )
    else:
        st.info("No HRV data available for this period.")

st.divider()

# =============================================================================
# SECTION 4 -- STRESS & BODY BATTERY
# =============================================================================

st.markdown('<p class="section-header">😰 Stress & Body Battery</p>', unsafe_allow_html=True)

col_stress, col_battery = st.columns(2)

with col_stress:
    df_stress = df.dropna(subset=["average_stress_level"])
    if not df_stress.empty:
        fig_stress = go.Figure()
        fig_stress.add_trace(go.Bar(
            x=df_stress["date"],
            y=df_stress["average_stress_level"],
            name="Stress",
            marker_color=[
                COLORS["success"] if v < 25
                else COLORS["warning"] if v < 50
                else COLORS["accent"] if v < 75
                else COLORS["danger"]
                for v in df_stress["average_stress_level"].fillna(0)
            ],
            opacity=0.8,
            hovertemplate="<b>%{x|%b %d}</b><br>Stress: %{y}/100<extra></extra>",
        ))
        if show_7day_avg and "stress_7day_avg" in df_stress.columns:
            fig_stress.add_trace(go.Scatter(
                x=df_stress["date"],
                y=df_stress["stress_7day_avg"],
                name="7-day avg",
                mode="lines",
                line=dict(color=COLORS["secondary"], width=2),
                hovertemplate="7d avg: %{y:.1f}<extra></extra>",
            ))
        fig_stress.update_layout(
            height=260,
            margin=dict(t=20, b=10, l=10, r=10),
            plot_bgcolor=COLORS["card_bg"],
            paper_bgcolor=COLORS["card_bg"],
            title=dict(text="Daily Stress Level (0–100)", font_size=13),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(range=[0, 100], gridcolor="#E8ECF0", title="Stress"),
            xaxis=dict(showgrid=False, tickformat="%b %d"),
            bargap=0.2,
        )
        st.plotly_chart(fig_stress, use_container_width=True)
        st.caption("Green < 25  |  Yellow 25–50  |  Orange 50–75  |  Red > 75.")
    else:
        st.info("No stress data available for this period.")

with col_battery:
    battery_req = ["body_battery_high", "body_battery_low"]
    has_battery = all(c in df.columns for c in battery_req)
    df_battery  = df.dropna(subset=battery_req) if has_battery else pd.DataFrame()

    if not df_battery.empty:
        fig_battery = go.Figure()

        # Shaded area between daily high and low battery level
        fig_battery.add_trace(go.Scatter(
            x=pd.concat([df_battery["date"], df_battery["date"].iloc[::-1]]),
            y=pd.concat([
                df_battery["body_battery_high"],
                df_battery["body_battery_low"].iloc[::-1],
            ]),
            fill="toself",
            fillcolor="rgba(45,198,83,0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            name="Battery range",
            hoverinfo="skip",
        ))
        fig_battery.add_trace(go.Scatter(
            x=df_battery["date"],
            y=df_battery["body_battery_high"],
            name="Peak",
            mode="lines",
            line=dict(color=COLORS["battery"], width=2),
            hovertemplate="<b>%{x|%b %d}</b><br>Peak: %{y}<extra></extra>",
        ))
        fig_battery.add_trace(go.Scatter(
            x=df_battery["date"],
            y=df_battery["body_battery_low"],
            name="Low",
            mode="lines",
            line=dict(color=COLORS["danger"], width=1.5, dash="dash"),
            hovertemplate="<b>%{x|%b %d}</b><br>Low: %{y}<extra></extra>",
        ))
        fig_battery.update_layout(
            height=260,
            margin=dict(t=20, b=10, l=10, r=10),
            plot_bgcolor=COLORS["card_bg"],
            paper_bgcolor=COLORS["card_bg"],
            title=dict(text="Body Battery (0–100)", font_size=13),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(range=[0, 105], gridcolor="#E8ECF0", title="Battery"),
            xaxis=dict(showgrid=False, tickformat="%b %d"),
        )
        st.plotly_chart(fig_battery, use_container_width=True)
        st.caption(
            "Green = peak battery (after sleep).  Red dashed = daily low point. "
            "A wide gap = heavy daily drain, typical on hard training days."
        )
    else:
        st.info("No Body Battery data available for this period.")

st.divider()

# =============================================================================
# SECTION 5 -- RECOVERY SCORE & TRAINING READINESS
# =============================================================================

st.markdown('<p class="section-header">⚡ Recovery Score & Training Readiness</p>', unsafe_allow_html=True)

df_recovery = (
    df.dropna(subset=["recovery_score"])
    if "recovery_score" in df.columns
    else pd.DataFrame()
)

if not df_recovery.empty:
    col_rec_chart, col_rec_legend = st.columns([3, 1])

    with col_rec_chart:
        fig_rec = go.Figure()

        # Background bands for each score tier
        for y0, y1, color in [
            (75, 100, COLORS["success"]),
            (50, 75,  COLORS["primary"]),
            (25, 50,  COLORS["warning"]),
            (0,  25,  COLORS["danger"]),
        ]:
            fig_rec.add_hrect(y0=y0, y1=y1, fillcolor=color, opacity=0.05, line_width=0)

        # Line + colored markers (marker color encodes the score value)
        fig_rec.add_trace(go.Scatter(
            x=df_recovery["date"],
            y=df_recovery["recovery_score"],
            name="Recovery Score",
            mode="lines+markers",
            line=dict(width=2.5, color=COLORS["primary"]),
            marker=dict(
                size=8,
                color=df_recovery["recovery_score"],
                colorscale=[
                    [0.0, "#EF233C"],
                    [0.4, "#F77F00"],
                    [0.6, "#FFD60A"],
                    [0.8, "#00B4D8"],
                    [1.0, "#2DC653"],
                ],
                cmin=0, cmax=100,
                showscale=True,
                colorbar=dict(title="Score", thickness=12, len=0.7),
            ),
            hovertemplate="<b>%{x|%b %d, %Y}</b><br>Recovery: %{y:.0f}/100<extra></extra>",
        ))

        fig_rec.update_layout(
            height=300,
            margin=dict(t=20, b=10, l=10, r=60),
            plot_bgcolor=COLORS["card_bg"],
            paper_bgcolor=COLORS["card_bg"],
            showlegend=False,
            yaxis=dict(range=[0, 100], gridcolor="#E8ECF0", title="Score (0–100)"),
            xaxis=dict(showgrid=False, tickformat="%b %d"),
        )
        st.plotly_chart(fig_rec, use_container_width=True)
        st.caption(
            "Recovery score is calculated from sleep quality, resting HR trend, "
            "HRV, stress level, and Body Battery. Higher = more ready to train hard."
        )

    with col_rec_legend:
        st.markdown("**Score ranges:**")
        for label, color, rng in [
            ("Optimal",  COLORS["success"], "75–100"),
            ("Good",     COLORS["primary"], "50–75"),
            ("Moderate", COLORS["warning"], "25–50"),
            ("Low",      COLORS["danger"],  "0–25"),
        ]:
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
                f'<div style="width:14px;height:14px;border-radius:50%;background:{color}"></div>'
                f'<span style="font-size:0.9rem;"><b>{label}</b> ({rng})</span></div>',
                unsafe_allow_html=True,
            )

        st.divider()

        # Readiness distribution across the selected period
        if "training_readiness" in df.columns:
            readiness_counts = df["training_readiness"].value_counts()
            n_days = len(df)
            st.markdown("**Readiness breakdown:**")
            for level in ["optimal", "good", "moderate", "low"]:
                count = readiness_counts.get(level, 0)
                pct   = count / n_days * 100 if n_days > 0 else 0
                color = READINESS_COLORS.get(level, COLORS["muted"])
                st.markdown(
                    f'<div style="margin-bottom:4px;">'
                    f'<span style="font-size:0.85rem;font-weight:600;color:{color};">'
                    f'{level.capitalize()}</span>'
                    f'<span style="font-size:0.85rem;color:#6C757D;">'
                    f" — {pct:.0f}% ({count}d)</span></div>",
                    unsafe_allow_html=True,
                )
else:
    st.info("Recovery score data not available for this period.")

st.divider()

# =============================================================================
# SECTION 6 -- DAILY STEPS
# =============================================================================

st.markdown('<p class="section-header">👟 Daily Steps</p>', unsafe_allow_html=True)

df_steps = df.dropna(subset=["total_steps"])

if not df_steps.empty:
    fig_steps = go.Figure()

    fig_steps.add_trace(go.Bar(
        x=df_steps["date"],
        y=df_steps["total_steps"],
        name="Steps",
        marker_color=[
            COLORS["success"] if v >= 10000
            else COLORS["warning"] if v >= 7500
            else COLORS["danger"]
            for v in df_steps["total_steps"].fillna(0)
        ],
        opacity=0.8,
        hovertemplate="<b>%{x|%b %d}</b><br>Steps: %{y:,.0f}<extra></extra>",
    ))

    if show_7day_avg and "steps_7day_avg" in df_steps.columns:
        fig_steps.add_trace(go.Scatter(
            x=df_steps["date"],
            y=df_steps["steps_7day_avg"],
            name="7-day avg",
            mode="lines",
            line=dict(color=COLORS["secondary"], width=2),
            hovertemplate="7d avg: %{y:,.0f}<extra></extra>",
        ))

    # 10,000-step reference line (WHO daily activity recommendation)
    fig_steps.add_hline(
        y=10000,
        line_dash="dot",
        line_color=COLORS["success"],
        opacity=0.5,
        annotation_text="10,000 target",
        annotation_position="top right",
        annotation_font_size=11,
    )

    fig_steps.update_layout(
        height=260,
        margin=dict(t=20, b=10, l=10, r=10),
        plot_bgcolor=COLORS["card_bg"],
        paper_bgcolor=COLORS["card_bg"],
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(gridcolor="#E8ECF0", title="Steps", tickformat=","),
        xaxis=dict(showgrid=False, tickformat="%b %d"),
        bargap=0.2,
    )
    st.plotly_chart(fig_steps, use_container_width=True)
    st.caption("Green >= 10,000  |  Yellow 7,500–10,000  |  Red < 7,500.")
else:
    st.info("No step data available for this period.")

st.divider()

# =============================================================================
# SECTION 7 -- RAW DATA (collapsible)
# =============================================================================

with st.expander("View raw daily health data", expanded=False):
    display_cols = [
        "date", "total_sleep_hours", "sleep_quality_category",
        "resting_heart_rate", "hrv_numeric", "hrv_category",
        "average_stress_level", "stress_category",
        "body_battery_high", "body_battery_low",
        "total_steps", "recovery_score", "training_readiness",
    ]
    available = [c for c in display_cols if c in df.columns]

    df_raw = df[available].copy().sort_values("date", ascending=False)
    df_raw["date"] = df_raw["date"].dt.strftime("%b %d, %Y")

    st.dataframe(df_raw, use_container_width=True, hide_index=True)

    csv = df[available].to_csv(index=False)
    st.download_button(
        "Download as CSV",
        data=csv,
        file_name="health_trends.csv",
        mime="text/csv",
    )

# =============================================================================
# FOOTER
# =============================================================================

st.markdown("---")
st.caption(
    "Data source: Garmin Connect API -> DuckDB (main_gold.mart_health_trends). "
    "Recovery score combines sleep quality, RHR trend, HRV, stress, and Body Battery. "
    "HRV = Heart Rate Variability (ms).  RHR = Resting Heart Rate (bpm)."
)

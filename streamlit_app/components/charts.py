# streamlit_app/components/charts.py
"""
Reusable Plotly chart components for the Running Performance Analyzer.

File structure at a glance:
    _apply_layout()          → applies CHART_LAYOUT (dark theme, fonts) to any figure
    _empty_figure()          → returns a blank figure with a "no data" annotation
    _format_week_labels()    → converts date column to "Mon DD" axis labels

    chart_weekly_distance()  → bar chart of weekly distance + 4-week rolling avg
    chart_training_load()    → line chart of TRIMP load + acute/chronic averages
    chart_hr_zones()         → horizontal stacked bars of time in each HR zone
    chart_pace_trend()       → line chart of average pace over time (Y-axis inverted)

    chart_sleep_trend()      → line chart of sleep duration + ideal zone band (7-9h)
    chart_recovery_score()   → area chart of recovery score (0-100) with color zones
    chart_hrv_trend()        → line chart of HRV with 7-day smoothing overlay

    chart_race_paces()       → bar chart of race paces with PR races highlighted

Design principles:
    - Functions return Figure objects — they do NOT call st.plotly_chart() themselves.
      This keeps charts testable and reusable outside Streamlit if needed.
    - All figures apply CHART_LAYOUT for visual consistency (dark theme, fonts, etc.)
    - Empty DataFrames are handled gracefully — functions return a blank annotated
      figure rather than crashing.

Usage example (in a page file):
    from components.charts import chart_weekly_distance
    fig = chart_weekly_distance(df_training)
    st.plotly_chart(fig, use_container_width=True)
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from utils.constants import (
    CHART_LAYOUT,
    CHART_HOVER_MODE,
    COLORS,
    HR_ZONE_COLORS,
    HR_ZONE_LABELS,
)
from utils.formatting import format_pace_short, format_week


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _apply_layout(fig: go.Figure, title: str = "") -> go.Figure:
    """
    Apply the global chart layout (dark theme, fonts, colors) to a figure.

    This is called at the end of every chart function to ensure consistency.
    Individual charts can still override specific properties after this call.

    Args:
        fig: The Plotly figure to style.
        title: Optional chart title. Empty string = no title displayed.

    Returns:
        go.Figure: The same figure, mutated in place and returned for chaining.
    """
    fig.update_layout(
        **CHART_LAYOUT,
        title={
            "text": title,
            "font": {"size": 15, "color": COLORS["light_grey"]},
            "x": 0.01,          # Left-aligned title (more modern than centered)
            "xanchor": "left",
        } if title else None,
        hovermode=CHART_HOVER_MODE,
    )
    return fig


def _empty_figure(message: str = "No data available") -> go.Figure:
    """
    Return a blank figure with a centered annotation message.

    Used when the DataFrame passed to a chart function is empty,
    so pages render a placeholder instead of crashing or showing
    a confusing empty chart.

    Args:
        message: Text to display in the center of the empty chart.

    Returns:
        go.Figure: Blank dark figure with the message as annotation.
    """
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font={"size": 14, "color": COLORS["grey"]},
    )
    return _apply_layout(fig)


def _format_week_labels(df: pd.DataFrame, col: str = "week_start_date") -> list[str]:
    """
    Convert a date column to compact "Mon DD" labels for chart x-axes.

    Example: "2025-03-10" → "Mar 10"

    Args:
        df: DataFrame containing the date column.
        col: Name of the date column. Defaults to "week_start_date".

    Returns:
        list[str]: Formatted labels in the same order as the DataFrame rows.
    """
    return [format_week(d) for d in df[col]]


# ---------------------------------------------------------------------------
# Training charts
# ---------------------------------------------------------------------------

def chart_weekly_distance(df: pd.DataFrame, weeks: int = 16) -> go.Figure:
    """
    Bar chart showing weekly running distance over the last N weeks.

    Each bar represents one week. The 4-week rolling average is overlaid
    as a line to show the underlying trend without week-to-week noise.

    Args:
        df: DataFrame from load_training_data(), sorted ASC by date.
            Expected columns: week_start_date, total_distance_km,
            rolling_4w_distance_km (optional).
        weeks: Number of recent weeks to display. Defaults to 16.

    Returns:
        go.Figure: Bar + line combo chart.
    """
    if df.empty:
        return _empty_figure("No training data available")

    # Take the N most recent weeks, sorted ascending for left-to-right display
    data = (
        df.sort_values("week_start_date", ascending=True)
        .tail(weeks)
        .reset_index(drop=True)
    )

    x_labels = _format_week_labels(data)

    fig = go.Figure()

    # --- Bars: weekly distance ---
    fig.add_trace(go.Bar(
        x=x_labels,
        y=data["total_distance_km"],
        name="Weekly Distance",
        marker_color=COLORS["primary"],
        marker_opacity=0.8,
        # Hover: show exact value with 1 decimal
        hovertemplate="<b>%{x}</b><br>Distance: %{y:.1f} km<extra></extra>",
    ))

    # --- Line: 4-week rolling average (if column exists) ---
    if "rolling_4wk_avg_distance_km" in data.columns:   # était rolling_4w_distance_km
        fig.add_trace(go.Scatter(
            x=x_labels,
            y=data["rolling_4wk_avg_distance_km"],
            name="4-week avg",
            mode="lines",
            line={"color": COLORS["secondary"], "width": 2, "dash": "dot"},
            hovertemplate="<b>%{x}</b><br>4w avg: %{y:.1f} km<extra></extra>",
        ))

    fig.update_layout(
        yaxis_title="Distance (km)",
        legend={"orientation": "h", "y": -0.2},   # Legend below the chart
        bargap=0.2,
    )

    return _apply_layout(fig, title="Weekly Distance")


def chart_training_load(df: pd.DataFrame, weeks: int = 16) -> go.Figure:
    """
    Line chart showing weekly TRIMP (Training Impulse) training load.

    TRIMP combines volume and intensity into a single load score.
    The chart overlays the acute (4-week) and chronic (8-week) load lines
    to give a visual representation of freshness vs. fitness.

    Args:
        df: DataFrame from load_training_data().
            Expected columns: week_start_date, total_training_load,
            rolling_4wk_avg_training_load (optional), rolling_8wk_avg_training_load (optional).
        weeks: Number of recent weeks to display.

    Returns:
        go.Figure: Multi-line chart with TRIMP and rolling averages.
    """
    if df.empty:
        return _empty_figure("No training load data available")

    data = (
        df.sort_values("week_start_date", ascending=True)
        .tail(weeks)
        .reset_index(drop=True)
    )

    x_labels = _format_week_labels(data)
    fig = go.Figure()

    # --- Area fill: weekly TRIMP ---
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=data["total_training_load"],
        name="Weekly Load (TRIMP)",
        mode="lines+markers",
        fill="tozeroy",                             # Fill area under the line
        fillcolor=f"rgba(26, 115, 232, 0.15)",      # Semi-transparent primary blue
        line={"color": COLORS["primary"], "width": 2},
        marker={"size": 5},
        hovertemplate="<b>%{x}</b><br>Load: %{y:.0f}<extra></extra>",
    ))

    # --- Acute load (4-week rolling average) ---
    if "rolling_4wk_avg_training_load" in data.columns:   # était rolling_4w_trimp
        fig.add_trace(go.Scatter(
            x=x_labels,
            y=data["rolling_4wk_avg_training_load"],
            name="Acute (4w avg)",
            mode="lines",
            line={"color": COLORS["secondary"], "width": 2},
            hovertemplate="<b>%{x}</b><br>Acute: %{y:.0f}<extra></extra>",
        ))

    # --- Chronic load (8-week rolling average) ---
    if "rolling_8wk_avg_training_load" in data.columns:   # était rolling_8w_trimp
        fig.add_trace(go.Scatter(
            x=x_labels,
            y=data["rolling_8wk_avg_training_load"],
            name="Chronic (8w avg)",
            mode="lines",
            line={"color": COLORS["success"], "width": 2, "dash": "dash"},
            hovertemplate="<b>%{x}</b><br>Chronic: %{y:.0f}<extra></extra>",
        ))

    fig.update_layout(
        yaxis_title="Training Load",
        legend={"orientation": "h", "y": -0.2},
    )

    return _apply_layout(fig, title="Training Load")


def chart_hr_zones(df: pd.DataFrame, weeks: int = 4) -> go.Figure:

    # Colonnes réelles : pct_zone1_easy, pct_zone2_moderate, pct_zone3_tempo,
    #                    pct_zone4_threshold, pct_zone5_max
    zone_cols = ["pct_zone1_easy", "pct_zone2_moderate", "pct_zone3_tempo",
                 "pct_zone4_threshold", "pct_zone5_max"]

    if df.empty or not all(col in df.columns for col in zone_cols):
        return _empty_figure("No heart rate zone data available")

    recent = df.sort_values("week_start_date", ascending=True).tail(weeks)

    # Average the percentages across the selected weeks
    zone_data = {
        "Zone 1": recent["pct_zone1_easy"].mean(),
        "Zone 2": recent["pct_zone2_moderate"].mean(),
        "Zone 3": recent["pct_zone3_tempo"].mean(),
        "Zone 4": recent["pct_zone4_threshold"].mean(),
        "Zone 5": recent["pct_zone5_max"].mean(),
    }

    fig = go.Figure()

    for i, (zone_name, pct) in enumerate(zone_data.items(), start=1):
        fig.add_trace(go.Bar(
            name=zone_name,
            x=[pct],
            y=["Zone Distribution"],
            orientation="h",
            marker_color=HR_ZONE_COLORS[i],
            hovertemplate=(
                f"<b>{zone_name}</b><br>"
                f"{pct:.1f}% of activities<extra></extra>"
            ),
        ))

    fig.update_layout(
        barmode="stack",
        xaxis_title="% of activities",   # était "Hours" — corrigé
        yaxis={"showticklabels": False},
        showlegend=True,
        legend={"orientation": "h", "y": -0.3},
        height=180,
    )

    return _apply_layout(fig, title=f"Heart Rate Zones (last {weeks} weeks)")


def chart_pace_trend(df: pd.DataFrame, weeks: int = 16) -> go.Figure:
    """
    Line chart showing average pace evolution over time.

    Note on Y-axis inversion:
        Pace charts are traditionally displayed with the Y-axis inverted —
        faster paces (lower min/km values) appear at the TOP of the chart.
        This is more intuitive: "going up" visually = getting faster.
        We achieve this with autorange="reversed" on the y-axis.

    Args:
        df: DataFrame from load_training_data().
            Expected columns: week_start_date, avg_pace_min_per_km.
        weeks: Number of recent weeks to display.

    Returns:
        go.Figure: Inverted-Y line chart of average weekly pace.
    """
    if df.empty or "avg_pace_min_per_km" not in df.columns:
        return _empty_figure("No pace data available")

    data = (
        df.sort_values("week_start_date", ascending=True)
        .tail(weeks)
        .dropna(subset=["avg_pace_min_per_km"])
        .reset_index(drop=True)
    )

    if data.empty:
        return _empty_figure("No pace data for this period")

    x_labels = _format_week_labels(data)

    # Format pace values for hover tooltip
    hover_paces = [format_pace_short(p) for p in data["avg_pace_min_per_km"]]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=x_labels,
        y=data["avg_pace_min_per_km"],
        name="Avg Pace",
        mode="lines+markers",
        line={"color": COLORS["secondary"], "width": 2},
        marker={"size": 5, "color": COLORS["secondary"]},
        # Use custom hover text (formatted pace) instead of raw decimal
        text=hover_paces,
        hovertemplate="<b>%{x}</b><br>Pace: %{text} /km<extra></extra>",
    ))

    fig.update_layout(
        yaxis={
            "title": "Pace (min/km)",
            "autorange": "reversed",    # KEY: lower value (faster) = higher on chart
            # Format y-axis ticks as "M:SS" instead of decimal
            "tickvals": data["avg_pace_min_per_km"].tolist(),
            "ticktext": hover_paces,
        },
    )

    return _apply_layout(fig, title="Average Pace Trend")


# ---------------------------------------------------------------------------
# Health & recovery charts
# ---------------------------------------------------------------------------

def chart_sleep_trend(df: pd.DataFrame, days: int = 30) -> go.Figure:
    """
    Line chart showing sleep duration over the last N days.

    Adds a shaded "ideal sleep zone" band (7-9 hours) as a visual reference.
    Most sports scientists recommend 7-9h for athletes.

    Args:
        df: DataFrame from load_health_data(), sorted DESC by date.
            Expected columns: date, total_sleep_hours.
        days: Number of recent days to display. Defaults to 30.

    Returns:
        go.Figure: Line chart with ideal sleep zone band.
    """
    if df.empty or "total_sleep_hours" not in df.columns:
        return _empty_figure("No sleep data available")

    data = (
        df.sort_values("date", ascending=True)
        .tail(days)
        .dropna(subset=["total_sleep_hours"])
        .reset_index(drop=True)
    )

    if data.empty:
        return _empty_figure("No sleep data for this period")

    fig = go.Figure()

    # --- Ideal sleep zone: shaded band between 7h and 9h ---
    # We use add_hrect() which adds a horizontal rectangle spanning full x range
    fig.add_hrect(
        y0=7, y1=9,
        fillcolor=f"rgba(52, 168, 83, 0.1)",    # Semi-transparent green
        line_width=0,
        annotation_text="Ideal (7-9h)",
        annotation_position="top right",
        annotation_font={"size": 11, "color": COLORS["success"]},
    )

    # --- Sleep duration line ---
    fig.add_trace(go.Scatter(
        x=data["date"].astype(str),
        y=data["total_sleep_hours"],
        name="Sleep Duration",
        mode="lines+markers",
        fill="tozeroy",
        fillcolor="rgba(26, 115, 232, 0.08)",
        line={"color": COLORS["primary"], "width": 2},
        marker={"size": 4},
        hovertemplate="<b>%{x}</b><br>Sleep: %{y:.1f} h<extra></extra>",
    ))

    fig.update_layout(
        yaxis_title="Hours",
        yaxis={"range": [0, 12]},       # Fixed range: sleep rarely exceeds 12h
    )

    return _apply_layout(fig, title="Sleep Duration")


def chart_recovery_score(df: pd.DataFrame, days: int = 30) -> go.Figure:
    """
    Area chart showing daily recovery score (0-100) over time.

    The background is divided into colored zones:
        < 33  = low recovery (red zone)
        33-66 = moderate recovery (yellow zone)
        > 66  = good recovery (green zone)

    Args:
        df: DataFrame from load_health_data().
            Expected columns: date, recovery_score.
        days: Number of recent days to display.

    Returns:
        go.Figure: Area chart with colored background zones.
    """
    if df.empty or "recovery_score" not in df.columns:
        return _empty_figure("No recovery data available")

    data = (
        df.sort_values("date", ascending=True)
        .tail(days)
        .dropna(subset=["recovery_score"])
        .reset_index(drop=True)
    )

    if data.empty:
        return _empty_figure("No recovery data for this period")

    fig = go.Figure()

    # --- Background zones (colored bands) ---
    # Low recovery: 0-33 (red)
    fig.add_hrect(y0=0,  y1=33,  fillcolor="rgba(234, 67, 53, 0.08)",  line_width=0)
    # Moderate: 33-66 (yellow)
    fig.add_hrect(y0=33, y1=66,  fillcolor="rgba(251, 188, 4, 0.08)",  line_width=0)
    # Good: 66-100 (green)
    fig.add_hrect(y0=66, y1=100, fillcolor="rgba(52, 168, 83, 0.08)",  line_width=0)

    # --- Recovery score area ---
    fig.add_trace(go.Scatter(
        x=data["date"].astype(str),
        y=data["recovery_score"],
        name="Recovery Score",
        mode="lines+markers",
        fill="tozeroy",
        fillcolor="rgba(26, 115, 232, 0.15)",
        line={"color": COLORS["primary"], "width": 2},
        marker={"size": 4},
        hovertemplate="<b>%{x}</b><br>Recovery: %{y:.0f}/100<extra></extra>",
    ))

    fig.update_layout(
        yaxis_title="Recovery Score",
        yaxis={"range": [0, 100]},
    )

    return _apply_layout(fig, title="Recovery Score")


def chart_hrv_trend(df: pd.DataFrame, days: int = 30) -> go.Figure:
    """
    Line chart showing Heart Rate Variability (HRV) trend over time.

    HRV is one of the best recovery indicators: higher = better recovered.
    We show the raw daily value + a 7-day rolling average to reduce noise.

    Args:
        df: DataFrame from load_health_data().
            Expected columns: date, hrv_numeric,
            hrv_7day_avg (optional).
        days: Number of recent days to display.

    Returns:
        go.Figure: Line chart with raw HRV and 7-day smoothing.
    """
    if df.empty or "hrv_numeric" not in df.columns:
        return _empty_figure("No HRV data available")

    data = (
        df.sort_values("date", ascending=True)
        .tail(days)
        .dropna(subset=["hrv_numeric"])
        .reset_index(drop=True)
    )

    if data.empty:
        return _empty_figure("No HRV data for this period")

    fig = go.Figure()

    # --- Raw HRV (thin, transparent line — noisy by nature) ---
    fig.add_trace(go.Scatter(
        x=data["date"].astype(str),
        y=data["hrv_numeric"],
        name="HRV (daily)",
        mode="lines",
        line={"color": COLORS["primary"], "width": 1, "dash": "dot"},
        opacity=0.5,
        hovertemplate="<b>%{x}</b><br>HRV: %{y:.0f} ms<extra></extra>",
    ))

    # --- 7-day rolling average (bold, smooth — the signal) ---
    if "hrv_7day_avg" in data.columns:
        fig.add_trace(go.Scatter(
            x=data["date"].astype(str),
            y=data["hrv_7day_avg"],
            name="7-day avg",
            mode="lines",
            line={"color": COLORS["success"], "width": 2},
            hovertemplate="<b>%{x}</b><br>7d avg: %{y:.0f} ms<extra></extra>",
        ))

    fig.update_layout(
        yaxis_title="HRV (ms)",
    )

    return _apply_layout(fig, title="Heart Rate Variability (HRV)")


# ---------------------------------------------------------------------------
# Race performance charts
# ---------------------------------------------------------------------------

def chart_race_paces(df: pd.DataFrame) -> go.Figure:
    """
    Bar chart showing pace for each race, with PR races highlighted.

    Bars are colored differently for PR races (gold) vs regular races (blue).
    A lower bar = faster race = better result, so the y-axis is inverted.

    Args:
        df: DataFrame from load_race_data(), sorted ASC by date for
            left-to-right chronological display.
            Expected columns: race_date, pace_min_per_km,
            is_personal_record, race_distance_category.

    Returns:
        go.Figure: Bar chart with PR highlights and inverted Y-axis.
    """
    if df.empty:
        return _empty_figure("No race data available")

    data = (
        df.sort_values("race_date", ascending=True)
        .dropna(subset=["pace_min_per_km"])
        .reset_index(drop=True)
    )

    if data.empty:
        return _empty_figure("No races with pace data")

    # Color each bar: gold for PR, primary blue for regular race
    bar_colors = [
        COLORS["warning"] if is_pr else COLORS["primary"]
        for is_pr in data["is_personal_record"]
    ]

    # Format labels for x-axis: "Mar 15" + distance category
    x_labels = [
        f"{pd.Timestamp(d).strftime('%b %y')}<br>{cat}"
        for d, cat in zip(data["race_date"], data["race_distance_category"])
    ]

    hover_paces = [format_pace_short(p) for p in data["pace_min_per_km"]]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=x_labels,
        y=data["pace_min_per_km"],
        marker_color=bar_colors,
        text=hover_paces,
        textposition="outside",         # Show pace label above each bar
        hovertemplate="<b>%{x}</b><br>Pace: %{text} /km<extra></extra>",
        name="Race Pace",
    ))

    # Add a legend entry for PR (can't do it via Bar marker directly)
    fig.add_trace(go.Bar(
        x=[None], y=[None],             # Invisible bar just for legend entry
        name="🏆 Personal Record",
        marker_color=COLORS["warning"],
    ))

    fig.update_layout(
        yaxis={
            "title": "Pace (min/km)",
            "autorange": "reversed",    # Faster (lower) = higher on chart
            "tickvals": data["pace_min_per_km"].tolist(),
            "ticktext": hover_paces,
        },
        showlegend=True,
        bargap=0.3,
    )

    return _apply_layout(fig, title="Race Performances")
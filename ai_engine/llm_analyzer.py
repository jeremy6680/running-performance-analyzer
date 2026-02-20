"""
ai_engine/llm_analyzer.py
--------------------------
Core AI coaching engine for the Running Performance Analyzer.

Responsibilities:
1. Calculate deterministic alerts from training/health data (no LLM needed)
2. Build a compact, token-efficient context string from the last 4 weeks of data
3. Call the Claude API and return the structured markdown response

Design decision: alerts are computed locally (fast, cheap, deterministic).
The LLM is only called for nuanced interpretation and planning — things
that require contextual reasoning, not threshold checks.
"""

import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import anthropic
import pandas as pd
from dotenv import load_dotenv
from loguru import logger

# Load .env from the project root (two levels up from ai_engine/).
# This ensures ANTHROPIC_API_KEY is available regardless of how the app is launched.
# override=False means existing shell env variables take precedence.
_env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_env_path, override=False)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    """A single alert to display above the LLM response."""
    level: str          # "red" | "yellow"
    emoji: str          # visual indicator
    message: str        # human-readable description


@dataclass
class CoachingContext:
    """
    All data needed to build the LLM prompt.
    Populated by build_coaching_context() before the API call.
    """
    # Training summary (4-week window)
    avg_weekly_km: float
    avg_weekly_load: float          # TRIMP
    load_trend_pct: float           # % change vs previous 4 weeks
    acwr: float                     # Acute-to-Chronic Workload Ratio
    avg_pace_min_per_km: float
    pct_easy: float                 # zone 1+2
    pct_hard: float                 # zone 3+4+5

    # Health (7-day window)
    avg_sleep_hours: float
    avg_hrv: Optional[float]
    hrv_trend_pct: Optional[float]  # % change vs 4-week avg
    avg_resting_hr: Optional[float]
    avg_stress: Optional[float]
    avg_recovery_score: Optional[float]
    avg_readiness: Optional[float]

    # Race history
    last_race_distance: Optional[str]
    last_race_pace_min_per_km: Optional[float]
    pr_5k_pace: Optional[float]
    pr_10k_pace: Optional[float]
    pr_half_pace: Optional[float]
    pr_marathon_pace: Optional[float]

    # Goal
    goal_distance: str
    goal_time_minutes: float
    goal_pace_min_per_km: float
    weeks_to_race: int


# ---------------------------------------------------------------------------
# Alert calculation (deterministic — no LLM)
# ---------------------------------------------------------------------------

def calculate_alerts(ctx: CoachingContext) -> list[Alert]:
    """
    Compute training and health alerts from thresholds.
    Returns a list of Alert objects sorted by severity (red first).

    These alerts are shown *above* the LLM response so the user
    sees critical signals immediately, before reading the full analysis.
    """
    alerts = []

    # --- Training load alerts ---

    if ctx.acwr > 1.5:
        alerts.append(Alert(
            level="red",
            emoji="🔴",
            message=f"Training load spike: ACWR is {ctx.acwr:.2f} (>1.5 = high injury risk). "
                    f"Acute load is {ctx.acwr:.0%} of your chronic baseline."
        ))
    elif ctx.acwr > 1.3:
        alerts.append(Alert(
            level="yellow",
            emoji="🟡",
            message=f"Training load increasing quickly: ACWR is {ctx.acwr:.2f} "
                    f"(optimal range: 0.8–1.3). Monitor for fatigue signs."
        ))

    # --- HRV alerts ---

    if ctx.hrv_trend_pct is not None:
        if ctx.hrv_trend_pct < -20:
            alerts.append(Alert(
                level="red",
                emoji="🔴",
                message=f"HRV dropped {abs(ctx.hrv_trend_pct):.0f}% vs your 4-week average "
                        f"(now {ctx.avg_hrv:.0f}ms). Strong recovery signal — consider an easy week."
            ))
        elif ctx.hrv_trend_pct < -10:
            alerts.append(Alert(
                level="yellow",
                emoji="🟡",
                message=f"HRV trending down: {ctx.hrv_trend_pct:.0f}% vs 4-week average "
                        f"({ctx.avg_hrv:.0f}ms). Mild fatigue accumulation."
            ))

    # --- Sleep alerts ---

    if ctx.avg_sleep_hours < 5.0:
        alerts.append(Alert(
            level="red",
            emoji="🔴",
            message=f"Critical sleep deficit: averaging {ctx.avg_sleep_hours:.1f}h/night this week "
                    f"(minimum recommended for athletes: 7h). Performance will be impaired."
        ))
    elif ctx.avg_sleep_hours < 6.5:
        alerts.append(Alert(
            level="yellow",
            emoji="🟡",
            message=f"Insufficient sleep: {ctx.avg_sleep_hours:.1f}h/night average this week. "
                    f"Athletes typically need 7–9h for optimal recovery."
        ))

    # --- Recovery score alerts ---

    if ctx.avg_recovery_score is not None and ctx.avg_recovery_score < 40:
        alerts.append(Alert(
            level="red",
            emoji="🔴",
            message=f"Low recovery score: {ctx.avg_recovery_score:.0f}/100 average this week. "
                    f"Body is not fully recovering between sessions."
        ))

    # --- Goal feasibility pre-check ---

    current_pace = _get_current_race_pace(ctx)
    if current_pace is not None:
        gap_pct = (ctx.goal_pace_min_per_km - current_pace) / current_pace * 100
        if gap_pct < -25:
            alerts.append(Alert(
                level="yellow",
                emoji="🎯",
                message=f"Ambitious goal: your current {ctx.goal_distance} pace is "
                        f"{_format_pace(current_pace)}/km — your target requires "
                        f"{_format_pace(ctx.goal_pace_min_per_km)}/km "
                        f"({abs(gap_pct):.0f}% faster). Worth discussing with your coach."
            ))

    # Sort: red alerts first
    return sorted(alerts, key=lambda a: 0 if a.level == "red" else 1)


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def build_coaching_context(
    training_df: pd.DataFrame,
    health_df: pd.DataFrame,
    race_df: pd.DataFrame,
    goal_distance: str,
    goal_time_minutes: float,
    race_date: date,
) -> CoachingContext:
    """
    Aggregate raw DataFrames into a CoachingContext dataclass.

    Args:
        training_df: mart_training_summary rows (last 8 weeks for ACWR calculation)
        health_df:   mart_health_trends rows (last 7 days)
        race_df:     mart_race_performance rows (all races for PRs)
        goal_distance: e.g. "Half Marathon"
        goal_time_minutes: target finish time in minutes
        race_date: target race date

    Returns:
        A populated CoachingContext ready for prompt building and alert calculation.
    """
    today = date.today()
    weeks_to_race = max(0, (race_date - today).days // 7)

    # --- Training: split into acute (last 4 weeks) and chronic (previous 4 weeks) ---
    training_df = training_df.sort_values("week_start_date", ascending=False)

    acute = training_df.head(4)       # most recent 4 weeks
    chronic = training_df.iloc[4:8]   # previous 4 weeks

    avg_weekly_km = acute["total_distance_km"].mean() if not acute.empty else 0.0
    avg_weekly_load = acute["total_training_load"].mean() if "total_training_load" in acute.columns else 0.0

    # ACWR: this week's load vs 4-week average
    current_week_load = training_df.head(1)["total_training_load"].values
    acwr = (current_week_load[0] / avg_weekly_load) if avg_weekly_load > 0 and len(current_week_load) > 0 else 1.0

    # Load trend: compare last 4 weeks to previous 4 weeks
    chronic_avg_load = chronic["total_training_load"].mean() if not chronic.empty else avg_weekly_load
    load_trend_pct = ((avg_weekly_load - chronic_avg_load) / chronic_avg_load * 100) if chronic_avg_load > 0 else 0.0

    # Pace: real column name in mart_training_summary is avg_pace_min_per_km
    avg_pace_col = "avg_pace_min_per_km" if "avg_pace_min_per_km" in acute.columns else None
    avg_pace = acute[avg_pace_col].mean() if avg_pace_col and not acute.empty else 0.0

    # HR zone distribution (average across last 4 weeks)
    pct_easy = (
        (acute.get("pct_zone1_easy", pd.Series([0])).mean() +
         acute.get("pct_zone2_moderate", pd.Series([0])).mean())
        if not acute.empty else 0.0
    )
    pct_hard = 100.0 - pct_easy

    # --- Health: last 7 days ---
    health_7d = health_df.sort_values("date", ascending=False).head(7) if not health_df.empty else pd.DataFrame()

    def _col_mean(df: pd.DataFrame, col: str):
        """
        Safely compute the mean of a column, coercing values to numeric first.

        The _query() helper in database.py uses fetchall() which returns all
        values as Python objects (often strings). Without explicit coercion,
        pandas .mean() on an object-dtype column concatenates strings instead
        of averaging numbers — e.g. 'goodoptimalgood...' for hrv_status.
        pd.to_numeric(..., errors='coerce') converts non-numeric values to NaN
        so they are silently ignored by .mean().
        """
        if col not in df.columns or df.empty:
            return None
        numeric = pd.to_numeric(df[col], errors="coerce")
        result = numeric.mean()
        return None if pd.isna(result) else result

    avg_sleep     = _col_mean(health_7d, "total_sleep_hours") or 0.0
    avg_hrv       = _col_mean(health_7d, "hrv_numeric")
    avg_rhr       = _col_mean(health_7d, "resting_heart_rate")
    avg_stress    = _col_mean(health_7d, "average_stress_level")
    avg_recovery  = _col_mean(health_7d, "recovery_score")
    avg_readiness = _col_mean(health_7d, "training_readiness")

    # HRV trend: compare 7-day avg to 4-week avg from health_df
    health_4wk  = health_df.sort_values("date", ascending=False).head(28) if not health_df.empty else pd.DataFrame()
    hrv_4wk_avg = _col_mean(health_4wk, "hrv_numeric")
    hrv_trend_pct = (
        ((avg_hrv - hrv_4wk_avg) / hrv_4wk_avg * 100)
        if avg_hrv is not None and hrv_4wk_avg is not None and hrv_4wk_avg > 0
        else None
    )

    # --- Race history: extract PRs by distance ---
    def get_pr_pace(distance_label: str) -> Optional[float]:
        """Return the best (fastest) pace for a given race distance category.
        Real column name in mart_race_performance is pace_min_per_km.
        """
        if race_df.empty or "race_distance_category" not in race_df.columns:
            return None
        subset = race_df[race_df["race_distance_category"] == distance_label]
        if subset.empty or "pace_min_per_km" not in subset.columns:
            return None
        return subset["pace_min_per_km"].min()

    # Last race info
    last_race_row = race_df.sort_values("race_date", ascending=False).head(1) if not race_df.empty else pd.DataFrame()
    last_race_distance = last_race_row["race_distance_category"].values[0] if not last_race_row.empty else None
    last_race_pace = (
        last_race_row["pace_min_per_km"].values[0]
        if not last_race_row.empty and "pace_min_per_km" in last_race_row.columns
        else None
    )

    # Goal pace calculation (minutes per km)
    distance_km_map = {
        "5K": 5.0,
        "10K": 10.0,
        "Half Marathon": 21.0975,
        "Marathon": 42.195,
    }
    goal_km = distance_km_map.get(goal_distance, 21.0975)
    goal_pace = goal_time_minutes / goal_km

    return CoachingContext(
        avg_weekly_km=round(avg_weekly_km, 1),
        avg_weekly_load=round(avg_weekly_load, 1),
        load_trend_pct=round(load_trend_pct, 1),
        acwr=round(acwr, 2),
        avg_pace_min_per_km=round(avg_pace, 2),
        pct_easy=round(pct_easy, 1),
        pct_hard=round(pct_hard, 1),
        avg_sleep_hours=round(avg_sleep, 1),
        avg_hrv=round(avg_hrv, 1) if avg_hrv is not None else None,
        hrv_trend_pct=round(hrv_trend_pct, 1) if hrv_trend_pct is not None else None,
        avg_resting_hr=round(avg_rhr, 0) if avg_rhr is not None else None,
        avg_stress=round(avg_stress, 0) if avg_stress is not None else None,
        avg_recovery_score=round(avg_recovery, 0) if avg_recovery is not None else None,
        avg_readiness=round(avg_readiness, 0) if avg_readiness is not None else None,
        last_race_distance=last_race_distance,
        last_race_pace_min_per_km=round(last_race_pace, 2) if last_race_pace is not None else None,
        pr_5k_pace=get_pr_pace("5K"),
        pr_10k_pace=get_pr_pace("10K"),
        pr_half_pace=get_pr_pace("Half Marathon"),
        pr_marathon_pace=get_pr_pace("Marathon"),
        goal_distance=goal_distance,
        goal_time_minutes=goal_time_minutes,
        goal_pace_min_per_km=round(goal_pace, 2),
        weeks_to_race=weeks_to_race,
    )


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(ctx: CoachingContext) -> str:
    """
    Convert a CoachingContext into a compact, token-efficient prompt string.

    Design principles:
    - Pass aggregated metrics, not raw rows (saves tokens)
    - Use clear labels so the LLM can parse the data correctly
    - Include units for every number (km, ms, bpm, etc.)
    - Mark missing data explicitly rather than omitting it
    """

    def fmt_pace(pace: Optional[float]) -> str:
        """Format a pace float (min/km) as M:SS/km string."""
        if pace is None:
            return "N/A"
        return _format_pace(pace)

    def fmt_opt(value, suffix: str = "") -> str:
        """Format an optional value, showing 'N/A' if None."""
        return f"{value}{suffix}" if value is not None else "N/A"

    prompt = f"""ATHLETE DATA — last 4 weeks

TRAINING LOAD
- Weekly volume: {ctx.avg_weekly_km} km/week (4-week avg)
- Training load (TRIMP): {ctx.avg_weekly_load}/week (4-week avg)
- Load trend: {ctx.load_trend_pct:+.0f}% vs previous 4 weeks
- ACWR (injury risk ratio): {ctx.acwr} (optimal: 0.8–1.3 | caution: >1.3 | danger: >1.5)
- Average pace: {fmt_pace(ctx.avg_pace_min_per_km if ctx.avg_pace_min_per_km > 0 else None)}/km
- HR zone split: {ctx.pct_easy:.0f}% easy (zones 1–2) / {ctx.pct_hard:.0f}% hard (zones 3–5)
  Note: 80/20 rule = ~80% easy / 20% hard

HEALTH — last 7 days
- Sleep: {ctx.avg_sleep_hours}h/night avg
- HRV: {fmt_opt(ctx.avg_hrv, 'ms')} (trend vs 4-week avg: {fmt_opt(ctx.hrv_trend_pct, '%')})
- Resting HR: {fmt_opt(ctx.avg_resting_hr, ' bpm')}
- Stress: {fmt_opt(ctx.avg_stress, '/100')}
- Recovery score: {fmt_opt(ctx.avg_recovery_score, '/100')}
- Training readiness: {fmt_opt(ctx.avg_readiness, '/100')}

RACE HISTORY
- Last race: {ctx.last_race_distance or 'N/A'} at {fmt_pace(ctx.last_race_pace_min_per_km)}/km
- PRs: 5K {fmt_pace(ctx.pr_5k_pace)} | 10K {fmt_pace(ctx.pr_10k_pace)} | Half {fmt_pace(ctx.pr_half_pace)} | Marathon {fmt_pace(ctx.pr_marathon_pace)}

GOAL
- Race: {ctx.goal_distance}
- Target time: {int(ctx.goal_time_minutes // 60)}h{int(ctx.goal_time_minutes % 60):02d}
- Required pace: {fmt_pace(ctx.goal_pace_min_per_km)}/km
- Time to race: {ctx.weeks_to_race} weeks
"""
    return prompt.strip()


# ---------------------------------------------------------------------------
# Claude API call
# ---------------------------------------------------------------------------

def get_coaching_analysis(ctx: CoachingContext) -> tuple[str, str]:
    """
    Send the athlete context to Claude and return the markdown response.

    Uses the system prompt from coach_analysis.txt to enforce a structured
    four-section response format that Streamlit will render directly.

    Args:
        ctx: Populated CoachingContext from build_coaching_context()

    Returns:
        Tuple of (markdown_response, model_name) so the Streamlit page can
        display which model generated the analysis in the footer.

    Raises:
        RuntimeError: if the API call fails (caught in the Streamlit page).
    """
    # Load system prompt from file (makes it easy to iterate on without touching code)
    prompt_path = Path(__file__).parent / "prompts" / "coach_analysis.txt"
    system_prompt = prompt_path.read_text(encoding="utf-8")

    # Build the user message from the context dataclass
    user_message = build_prompt(ctx)

    logger.info(f"Calling Claude API for coaching analysis — goal: {ctx.goal_distance}, "
                f"{ctx.weeks_to_race} weeks out")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not found. "
            "Make sure it is set in your .env file at the project root."
        )

    try:
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-opus-4-6",          # best reasoning for coaching nuance
            max_tokens=1024,                 # four concise sections fit comfortably
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        response_text = message.content[0].text
        model_used = message.model   # e.g. "claude-opus-4-6-20250514"
        logger.info(f"Claude API call successful — model: {model_used}")
        return response_text, model_used

    except anthropic.AuthenticationError:
        logger.error("Invalid Anthropic API key")
        raise RuntimeError("Invalid API key. Check your ANTHROPIC_API_KEY in .env")
    except anthropic.RateLimitError:
        logger.error("Anthropic rate limit reached")
        raise RuntimeError("API rate limit reached. Please wait a moment and try again.")
    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        raise RuntimeError(f"API call failed: {e}")


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _format_pace(pace_min_per_km: float) -> str:
    """Convert a float pace (e.g. 5.5) to a readable string (e.g. '5:30')."""
    minutes = int(pace_min_per_km)
    seconds = int(round((pace_min_per_km - minutes) * 60))
    return f"{minutes}:{seconds:02d}"


def _get_current_race_pace(ctx: CoachingContext) -> Optional[float]:
    """
    Return the athlete's most relevant current race pace for the goal distance.
    Falls back to adjacent distances if the exact distance has no PR.
    """
    distance_map = {
        "5K": ctx.pr_5k_pace,
        "10K": ctx.pr_10k_pace,
        "Half Marathon": ctx.pr_half_pace,
        "Marathon": ctx.pr_marathon_pace,
    }
    # Try the goal distance first, then last race pace as fallback
    return distance_map.get(ctx.goal_distance) or ctx.last_race_pace_min_per_km
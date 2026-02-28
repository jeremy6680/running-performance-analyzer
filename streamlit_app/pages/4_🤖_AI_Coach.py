"""
streamlit_app/pages/4_🤖_AI_Coach.py
--------------------------------------
AI-powered coaching page for the Running Performance Analyzer.

Layout:
  1. Goal inputs  (race distance, target time, race date)
  2. Weather city input (default from .env, overrideable)
  3. [Generate] button
  4. Deterministic alerts (calculated locally — no LLM cost)
  5. Expander: raw context sent to Claude (pedagogical / portfolio)
  6. LLM response rendered as Markdown
  7. [Save this analysis] button → stored in DuckDB coach_analyses table

New in this version:
  - Weather forecast via Open-Meteo (free, no API key)
  - Historical weather-pace correlation from DuckDB activities
  - Save / delete coaching analyses (persisted to DuckDB)
"""

import os
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st

# ---------------------------------------------------------------------------
# Path setup — allow imports from the project root
# ---------------------------------------------------------------------------

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Load .env so os.getenv('DEFAULT_CITY') works regardless of how Streamlit is launched
load_dotenv(os.path.join(ROOT_DIR, ".env"), override=False)

from ai_engine.llm_analyzer import (
    build_coaching_context,
    build_prompt,
    calculate_alerts,
    get_coaching_analysis,
)
from ai_engine.weather import format_weather_for_prompt, get_weather_context
from ingestion.config import database_config
from streamlit_app.utils.database import (
    load_health_data,
    load_race_data,
    load_training_data,
)
from streamlit_app.utils.formatting import format_pace

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AI Coach · Running Analyzer",
    page_icon="🤖",
    layout="wide",
)

st.markdown("""
<style>
    .coach-hero {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem 2.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
    }
    .coach-hero h1 { color: #ffffff; margin: 0; font-size: 2rem; }
    .coach-hero p  { color: #a0aec0; margin: 0.5rem 0 0; font-size: 1rem; }

    .alert-red    { background: #fff5f5; border-left: 4px solid #e53e3e;
                    padding: 0.75rem 1rem; border-radius: 6px; margin-bottom: 0.5rem; }
    .alert-yellow { background: #fffff0; border-left: 4px solid #d69e2e;
                    padding: 0.75rem 1rem; border-radius: 6px; margin-bottom: 0.5rem; }
    .alert-info   { background: #ebf8ff; border-left: 4px solid #3182ce;
                    padding: 0.75rem 1rem; border-radius: 6px; margin-bottom: 0.5rem; }
    .alert-green  { background: #f0fff4; border-left: 4px solid #38a169;
                    padding: 0.75rem 1rem; border-radius: 6px; margin-bottom: 0.5rem; }

    .section-divider { border-top: 1px solid #e2e8f0; margin: 1.5rem 0; }

    .save-box {
        background: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1.25rem 1.5rem;
        margin-top: 1.5rem;
    }
    .save-box h4 { margin: 0 0 0.5rem; color: #2d3748; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown("""
<div class="coach-hero">
    <h1>🤖 AI Running Coach</h1>
    <p>Personalised analysis powered by Claude — based on your last 4 weeks of training,
    health data, and upcoming weather forecast.</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Load training / health / race data into session state
# (avoids re-querying DuckDB on every widget interaction)
# ---------------------------------------------------------------------------

if "training_summary" not in st.session_state:
    st.session_state["training_summary"] = load_training_data()

if "health_trends" not in st.session_state:
    st.session_state["health_trends"] = load_health_data()

if "race_performance" not in st.session_state:
    st.session_state["race_performance"] = load_race_data()

training_df = st.session_state["training_summary"]
health_df   = st.session_state["health_trends"]
race_df     = st.session_state["race_performance"]

# ---------------------------------------------------------------------------
# Goal inputs
# ---------------------------------------------------------------------------

st.subheader("🎯 Set Your Goal")

col1, col2, col3 = st.columns(3)

with col1:
    goal_distance = st.selectbox(
        "Target race",
        options=["5K", "10K", "Half Marathon", "Marathon"],
        index=2,
        help="Select the race distance you are training for.",
    )

with col2:
    time_col1, time_col2 = st.columns(2)
    with time_col1:
        goal_hours = st.number_input(
            "Hours", min_value=0, max_value=6, value=1,
            help="Target finish time — hours part.",
        )
    with time_col2:
        goal_minutes = st.number_input(
            "Minutes", min_value=0, max_value=59, value=55,
            help="Target finish time — minutes part.",
        )
    goal_time_total_minutes = goal_hours * 60 + goal_minutes

with col3:
    default_race_date = date.today() + timedelta(weeks=10)
    race_date = st.date_input(
        "Race date",
        value=default_race_date,
        min_value=date.today() + timedelta(days=1),
        help="When is your target race? Determines weeks remaining.",
    )

# Derived metrics shown to the user immediately
distance_km_map = {
    "5K": 5.0, "10K": 10.0, "Half Marathon": 21.0975, "Marathon": 42.195
}
goal_km       = distance_km_map[goal_distance]
required_pace = goal_time_total_minutes / goal_km
weeks_to_race = (race_date - date.today()).days // 7

st.info(
    f"**Required pace:** {format_pace(required_pace)}/km  "
    f"to finish {goal_distance} in {goal_hours}h{goal_minutes:02d}  "
    f"· **{weeks_to_race} weeks** to go"
)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Weather city input
# ---------------------------------------------------------------------------

st.subheader("🌤️ Weather (optional)")

# Read the default city from .env — falls back to empty string if not set.
# Operators set DEFAULT_CITY in .env, user can override per session in the UI.
default_city = os.getenv("DEFAULT_CITY", "")

city_name = st.text_input(
    "City for weather forecast",
    value=default_city,
    placeholder="e.g. Nice, France",
    help=(
        "The AI coach will include a 7-day forecast and analyse how past weather "
        "conditions affected your pace. Leave blank to skip weather context."
    ),
)

if city_name:
    st.caption(
        "🌍 Weather data via [Open-Meteo](https://open-meteo.com/) — "
        "free, no API key required."
    )

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# API key input
# ---------------------------------------------------------------------------

st.subheader("🔑 Your Anthropic API Key")

# Retrieve the key from session state so it persists across widget interactions
# (Streamlit reruns the script on every interaction — session_state survives reruns).
# The key is NEVER written to disk, logs, or any persistent storage.
if "anthropic_api_key" not in st.session_state:
    st.session_state["anthropic_api_key"] = ""

api_key_input = st.text_input(
    "Anthropic API key",
    value=st.session_state["anthropic_api_key"],
    type="password",
    placeholder="sk-ant-...",
    help=(
        "Your key is used only for this request and is never stored. "
        "Get yours at console.anthropic.com"
    ),
    label_visibility="collapsed",
)

# Persist the key in session state so it survives widget reruns
st.session_state["anthropic_api_key"] = api_key_input

st.caption(
    "🔒 Your key is stored only in your browser session — never on the server. "
    "[Get a free API key](https://console.anthropic.com)"
)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Generate button
# ---------------------------------------------------------------------------

generate = st.button(
    "🤖 Generate coaching analysis",
    type="primary",
    use_container_width=False,
    help="Sends your training and health data to Claude for personalised analysis.",
)

# ---------------------------------------------------------------------------
# Analysis output — shown only after clicking Generate
# ---------------------------------------------------------------------------

if generate:

    # Basic validation
    if goal_time_total_minutes < 10:
        st.error("Please enter a valid target time (at least 10 minutes).")
        st.stop()

    # ── Step 1: Weather context ─────────────────────────────────────────────
    weather_str  = None          # text injected into the LLM prompt
    weather_city = None          # resolved city name for saving

    if city_name.strip():
        with st.spinner(f"📡 Fetching weather forecast for {city_name}…"):
            weather_ctx = get_weather_context(
                city_name=city_name.strip(),
                db_path=database_config.path,
            )
        weather_str  = format_weather_for_prompt(weather_ctx)
        weather_city = weather_ctx.city_name

        if weather_ctx.forecast:
            st.markdown(
                f'<div class="alert-info">🌤️ Weather loaded for '
                f'<strong>{weather_city}</strong> — '
                f'{len(weather_ctx.forecast)} days of forecast included in the analysis.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.warning(
                f"Could not fetch weather for **{city_name}**. "
                "The analysis will proceed without weather context."
            )
            weather_str  = None
            weather_city = None

    # ── Step 2: Build coaching context ─────────────────────────────────────
    with st.spinner("Crunching your training data…"):
        try:
            ctx = build_coaching_context(
                training_df=training_df,
                health_df=health_df,
                race_df=race_df,
                goal_distance=goal_distance,
                goal_time_minutes=float(goal_time_total_minutes),
                race_date=race_date,
            )
            # Attach the weather string so build_prompt() and the LLM see it
            ctx.weather_prompt_str = weather_str or None
        except Exception as e:
            st.error(f"Failed to build coaching context: {e}")
            st.stop()

    # ── Step 3: Deterministic alerts ───────────────────────────────────────
    alerts = calculate_alerts(ctx)

    if alerts:
        st.subheader("⚠️ Signals Detected")
        for alert in alerts:
            css = "alert-red" if alert.level == "red" else "alert-yellow"
            st.markdown(
                f'<div class="{css}">{alert.emoji} {alert.message}</div>',
                unsafe_allow_html=True,
            )
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="alert-green">✅ No major training or health alerts. '
            "Your load and recovery metrics look balanced.</div>",
            unsafe_allow_html=True,
        )
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # ── Step 4: Expander — raw context (pedagogical / portfolio) ───────────
    prompt_text = build_prompt(ctx)
    with st.expander("📋 Data sent to Claude — click to inspect", expanded=False):
        st.markdown(
            "This is the exact context string sent to the AI. "
            "Aggregated metrics are used (not raw rows) to keep the prompt "
            "compact and cost-efficient."
        )
        st.code(prompt_text, language="text")

    # ── Step 5: Claude API call ─────────────────────────────────────────────
    st.subheader("🤖 Coach Analysis")

    with st.spinner("Asking Claude for your personalised analysis… (5–15 seconds)"):
        try:
            response_md, model_used = get_coaching_analysis(
                ctx,
                api_key=st.session_state.get("anthropic_api_key", ""),
            )
        except RuntimeError as e:
            st.error(str(e))
            st.stop()

    # Render the LLM markdown response
    st.markdown(response_md)

    # Footer
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.caption(
        f"⚡ Analysis generated by **{model_used}** (Anthropic). "
        "Always cross-reference AI recommendations with your own experience and, "
        "for competitive goals, a certified running coach."
    )

    # ── Step 6: Save button ────────────────────────────────────────────────
    # Store the current analysis data in session state so the save action
    # (which triggers a Streamlit rerun) can still access it.
    st.session_state["_pending_analysis"] = {
        "analysis_id":    str(uuid.uuid4()),
        "generated_at":   datetime.now(),
        "goal_distance":  goal_distance,
        "goal_hours":     int(goal_hours),
        "goal_minutes":   int(goal_minutes),
        "race_date":      race_date,
        "city_name":      weather_city,
        "prompt_context": prompt_text,
        "response_md":    response_md,
        "model_used":     model_used,
    }

# ---------------------------------------------------------------------------
# Save section — shown whenever a pending analysis exists in session state
# (survives the rerun triggered by the Save button click)
# ---------------------------------------------------------------------------

if "_pending_analysis" in st.session_state:
    pending = st.session_state["_pending_analysis"]

    st.markdown('<div class="save-box">', unsafe_allow_html=True)
    st.markdown("#### 💾 Save this analysis")
    st.markdown(
        f"Save the coaching analysis for **{pending['goal_distance']}** "
        f"in **{pending['goal_hours']}h{pending['goal_minutes']:02d}** "
        f"(race: {pending['race_date']}) to your history?"
    )

    save_col, discard_col, _ = st.columns([1, 1, 4])

    with save_col:
        if st.button("💾 Save", type="primary", key="btn_save"):
            # Import here to avoid loading DuckDB at module level in Streamlit
            from ingestion.duckdb_manager import DuckDBManager

            try:
                mgr = DuckDBManager()
                mgr.save_coach_analysis(**pending)
                mgr.close()

                # Clear pending so the save box disappears
                del st.session_state["_pending_analysis"]

                st.success(
                    "✅ Analysis saved! View it in **📋 Past Analyses** "
                    "(page 5 in the sidebar)."
                )
            except Exception as e:
                st.error(f"Could not save analysis: {e}")

    with discard_col:
        if st.button("🗑️ Discard", key="btn_discard"):
            del st.session_state["_pending_analysis"]
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Empty state — shown before any analysis is generated
# ---------------------------------------------------------------------------

elif "generate" not in dir() or not generate:
    # Only show the empty state when no analysis has been generated yet
    if "_pending_analysis" not in st.session_state:
        st.markdown("""
        <div style="text-align: center; padding: 3rem 1rem; color: #718096;">
            <div style="font-size: 4rem; margin-bottom: 1rem;">🏃</div>
            <p style="font-size: 1.1rem;">Set your goal above, then click
            <strong>Generate coaching analysis</strong>.</p>
            <p>Claude will analyse your last 4 weeks of training and health data<br>
            and produce a personalised weekly plan and goal assessment.</p>
        </div>
        """, unsafe_allow_html=True)

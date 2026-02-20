"""
streamlit_app/pages/5_📋_Past_Analyses.py
------------------------------------------
Browse and review previously saved AI coaching analyses.

Layout:
  - Summary list: date, goal, race date, city (if weather was used)
  - Click a row to expand the full analysis (rendered as Markdown)
  - Delete button per analysis (with confirmation)
  - Empty state when no analyses have been saved yet
"""

import os
import sys

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ingestion.duckdb_manager import DuckDBManager

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Past Analyses · Running Analyzer",
    page_icon="📋",
    layout="wide",
)

st.markdown("""
<style>
    .past-hero {
        background: linear-gradient(135deg, #1a1a2e 0%, #2d3748 100%);
        padding: 2rem 2.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
    }
    .past-hero h1 { color: #ffffff; margin: 0; font-size: 2rem; }
    .past-hero p  { color: #a0aec0; margin: 0.5rem 0 0; font-size: 1rem; }

    .analysis-card {
        background: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 0.75rem;
    }
    .analysis-card h4 { margin: 0 0 0.25rem; color: #2d3748; font-size: 1.1rem; }
    .analysis-card .meta { color: #718096; font-size: 0.85rem; margin-bottom: 0.5rem; }
    .section-divider { border-top: 1px solid #e2e8f0; margin: 1.5rem 0; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown("""
<div class="past-hero">
    <h1>📋 Past Analyses</h1>
    <p>All your saved AI coaching analyses, most recent first.
    Click any entry to read the full report.</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Load saved analyses from DuckDB
# ---------------------------------------------------------------------------

@st.cache_data(ttl=5)   # short TTL so a fresh save appears quickly
def _load_analyses() -> pd.DataFrame:
    """Fetch all coach_analyses rows from DuckDB."""
    mgr = DuckDBManager()
    df  = mgr.load_coach_analyses()
    mgr.close()
    return df


def _refresh():
    """Clear the cached analyses so the next render re-queries DuckDB."""
    st.cache_data.clear()
    st.rerun()


df = _load_analyses()

# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------

if df.empty:
    st.markdown("""
    <div style="text-align: center; padding: 4rem 1rem; color: #718096;">
        <div style="font-size: 4rem; margin-bottom: 1rem;">🗂️</div>
        <p style="font-size: 1.1rem;"><strong>No analyses saved yet.</strong></p>
        <p>Go to the <strong>🤖 AI Coach</strong> page, generate an analysis,<br>
        then click <strong>💾 Save this analysis</strong>.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------------------
# Summary stats banner
# ---------------------------------------------------------------------------

total     = len(df)
distances = df["goal_distance"].value_counts().to_dict()
dist_str  = " · ".join(f"{v}× {k}" for k, v in distances.items())

col_a, col_b, col_c = st.columns(3)
col_a.metric("Total analyses saved", total)
col_b.metric("Most recent", str(df["generated_at"].iloc[0])[:10] if total else "—")
col_c.metric("Goal breakdown", dist_str if dist_str else "—")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Delete confirmation state
# (stored in session state so a rerun caused by the delete button
# doesn't lose which row was targeted)
# ---------------------------------------------------------------------------

if "_confirm_delete" not in st.session_state:
    st.session_state["_confirm_delete"] = None   # holds analysis_id to delete

# ---------------------------------------------------------------------------
# Render each analysis as an expander
# ---------------------------------------------------------------------------

for _, row in df.iterrows():
    analysis_id  = row["analysis_id"]
    generated_at = str(row["generated_at"])[:16]      # "YYYY-MM-DD HH:MM"
    goal_str     = (
        f"{row['goal_distance']}  ·  "
        f"{int(row['goal_hours'])}h{int(row['goal_minutes']):02d}  ·  "
        f"Race: {row['race_date']}"
    )
    city_str     = f"  ·  📍 {row['city_name']}" if row["city_name"] else ""
    model_str    = row["model_used"] if row["model_used"] else "unknown model"
    expander_label = f"📅 {generated_at}  —  {goal_str}{city_str}"

    with st.expander(expander_label, expanded=False):

        # ── Goal summary row ───────────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Race", row["goal_distance"])
        m2.metric("Target time", f"{int(row['goal_hours'])}h{int(row['goal_minutes']):02d}")
        m3.metric("Race date", str(row["race_date"]))
        m4.metric("City (weather)", row["city_name"] if row["city_name"] else "—")

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        # ── Full LLM response ──────────────────────────────────────────────
        st.markdown(row["response_md"])

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        # ── Context sent to Claude (collapsible) ──────────────────────────
        with st.expander("📋 Context that was sent to Claude", expanded=False):
            st.code(row["prompt_context"], language="text")

        # ── Footer + delete ────────────────────────────────────────────────
        footer_col, delete_col = st.columns([6, 1])

        with footer_col:
            saved_at = str(row["saved_at"])[:16] if row["saved_at"] else "—"
            st.caption(f"Generated by **{model_str}** · Saved {saved_at}")

        with delete_col:
            # Show "Delete" button, then confirm before actually deleting
            if st.session_state["_confirm_delete"] == analysis_id:
                # Confirmation step — two inline buttons
                st.warning("Delete this analysis?")
                yes_col, no_col = st.columns(2)
                with yes_col:
                    if st.button("Yes, delete", key=f"yes_{analysis_id}", type="primary"):
                        try:
                            mgr = DuckDBManager()
                            mgr.delete_coach_analysis(analysis_id)
                            mgr.close()
                            st.session_state["_confirm_delete"] = None
                            _refresh()    # re-query and rerun
                        except Exception as e:
                            st.error(f"Delete failed: {e}")
                with no_col:
                    if st.button("Cancel", key=f"no_{analysis_id}"):
                        st.session_state["_confirm_delete"] = None
                        st.rerun()
            else:
                if st.button("🗑️ Delete", key=f"del_{analysis_id}"):
                    # First click → show confirmation
                    st.session_state["_confirm_delete"] = analysis_id
                    st.rerun()

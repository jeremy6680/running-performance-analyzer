# streamlit_app/app.py
"""
Home page and entry point for the Running Performance Analyzer.

File structure at a glance:
    st.set_page_config()      → MUST be the first Streamlit call in the app
    load_css()                → injects custom CSS for Garmin-like styling
    _load_data_cached()       → loads all DataFrames once per session via st.session_state
    render_sidebar()          → pipeline status and app info
    render_header()           → gradient title + data date range
    render_quick_nav()        → clickable cards linking to each page
    main()                    → orchestrates all sections in order

Run with:
    streamlit run streamlit_app/app.py

Note on caching:
    We use st.session_state instead of @st.cache_data to avoid a serialization
    incompatibility between DuckDB and Streamlit's Arrow-based cache.
    st.session_state stores DataFrames in memory (no serialization) for the
    duration of the browser session.
"""

import pandas as pd
import streamlit as st

from components.metrics import render_all_time_stats, render_recovery_status
from utils.constants import APP_ICON, APP_SUBTITLE, APP_TITLE
from utils.database import get_date_range, load_health_data, load_race_data, load_training_data


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
# st.set_page_config() MUST be the very first Streamlit call in the app.
# It configures the browser tab title, icon, and sidebar behavior.
# Placing it at module level (outside any function) guarantees it runs
# before anything else — even before main() is called.

st.set_page_config(
    page_title="Running Performance Analyzer",
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def load_css() -> None:
    """
    Inject custom CSS for Garmin-inspired styling.

    Streamlit doesn't expose a CSS file — the only way to add custom styles
    is to inject a <style> block via st.markdown(unsafe_allow_html=True).
    This function centralizes all custom styles in one place.
    """
    st.markdown("""
    <style>
        /* ── Metric cards ── */
        [data-testid="metric-container"] {
            background-color: rgba(26, 115, 232, 0.05);
            border: 1px solid rgba(26, 115, 232, 0.2);
            border-radius: 8px;
            padding: 12px 16px;
        }
        [data-testid="metric-container"] [data-testid="stMetricValue"] {
            font-size: 1.6rem;
            font-weight: 700;
            color: #E8EAED;
        }

        /* ── Page title ── */
        .app-title {
            font-size: 2.4rem;
            font-weight: 800;
            background: linear-gradient(135deg, #1A73E8, #FF6B35);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0;
        }
        .app-subtitle {
            font-size: 1rem;
            color: #5F6368;
            margin-top: 4px;
            margin-bottom: 24px;
        }

        /* ── Navigation cards ── */
        .nav-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            transition: all 0.2s ease;
        }
        .nav-card:hover {
            background: rgba(26, 115, 232, 0.1);
            border-color: rgba(26, 115, 232, 0.4);
            transform: translateY(-2px);
        }
        .nav-card-icon  { font-size: 2rem; margin-bottom: 8px; }
        .nav-card-title { font-size: 1rem; font-weight: 600; color: #E8EAED; margin-bottom: 4px; }
        .nav-card-desc  { font-size: 0.8rem; color: #5F6368; }

        /* ── Sidebar ── */
        [data-testid="stSidebar"] { background-color: #161B22; }

        /* ── Section divider ── */
        .divider {
            border: none;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            margin: 24px 0;
        }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_data_cached() -> tuple:
    """
    Load all DataFrames once per browser session using st.session_state.

    Why st.session_state instead of @st.cache_data?
        @st.cache_data serializes DataFrames to disk using Arrow/pickle.
        This causes a 'Serialization Error: field id 100' with certain
        DuckDB versions. st.session_state stores objects directly in memory
        with no serialization — fully compatible with all DuckDB versions.

    How it works:
        - First call  : queries DuckDB, stores results in st.session_state
        - Subsequent calls (reruns triggered by clicks, filters, etc.)
                       : reads from st.session_state, no DB query

    Returns:
        tuple: (df_training, df_health, df_race, min_date, max_date)
    """
    if "data_loaded" not in st.session_state:
        st.session_state.df_training = load_training_data()
        st.session_state.df_health   = load_health_data()
        st.session_state.df_race     = load_race_data()
        st.session_state.min_date, st.session_state.max_date = get_date_range()
        st.session_state.data_loaded = True

    return (
        st.session_state.df_training,
        st.session_state.df_health,
        st.session_state.df_race,
        st.session_state.min_date,
        st.session_state.max_date,
    )


# ---------------------------------------------------------------------------
# Page sections
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    """Render pipeline status and app info in the sidebar."""
    with st.sidebar:
        st.markdown("## 🏃 Running Analyzer")
        st.markdown("---")
        st.markdown("""
        **Data pipeline status:**
        - 🟢 Garmin Connect → DuckDB
        - 🟢 dbt transformations
        - 🟢 Gold layer marts
        """)
        st.markdown("---")
        st.caption("Built with Streamlit · DuckDB · dbt · Claude API")


def render_header(min_date: str, max_date: str) -> None:
    """
    Render the gradient app title and data date range.

    Args:
        min_date: Earliest date in the dataset ("YYYY-MM-DD").
        max_date: Most recent date in the dataset ("YYYY-MM-DD").
    """
    col_title, col_info = st.columns([3, 1])

    with col_title:
        st.markdown(f'<h1 class="app-title">{APP_TITLE}</h1>', unsafe_allow_html=True)
        st.markdown(f'<p class="app-subtitle">{APP_SUBTITLE}</p>', unsafe_allow_html=True)

    with col_info:
        st.markdown("<br>", unsafe_allow_html=True)
        try:
            min_fmt = pd.Timestamp(min_date).strftime("%b %d, %Y")
            max_fmt = pd.Timestamp(max_date).strftime("%b %d, %Y")
            st.caption(f"📅 Data: **{min_fmt}** → **{max_fmt}**")
        except Exception:
            st.caption("📅 Data range unavailable")


def render_quick_nav() -> None:
    """
    Render 4 navigation cards linking to each dashboard page.

    Each card combines an HTML div (for hover styling) with st.page_link()
    (for actual Streamlit navigation). st.page_link() requires Streamlit 1.31+.
    """
    st.markdown("### Navigate")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    pages = [
            {
                "path":  "pages/1_📊_Dashboard.py",       
                "icon":  "📊",
                "title": "Dashboard",
                "desc":  "Weekly overview, recent activities, key trends",
            },
            {
                "path":  "pages/2_📈_Training_Analysis.py", 
                "icon":  "📈",
                "title": "Training Analysis",
                "desc":  "Load, pace progression, heart rate zones",
            },
            {
                "path":  "pages/3_🏃_Race_Performance.py", 
                "icon":  "🏃",
                "title": "Race Performance",
                "desc":  "Personal records, race history, pace analysis",
            },
            {
                "path":  "pages/4_❤️_Health.py",           
                "icon":  "❤️",
                "title": "Health & Recovery",
                "desc":  "Sleep, HRV, resting HR, recovery score",
            },
        ]

    cols = st.columns(4)

    for col, page in zip(cols, pages):
        with col:
            st.markdown(f"""
            <div class="nav-card">
                <div class="nav-card-icon">{page['icon']}</div>
                <div class="nav-card-title">{page['title']}</div>
                <div class="nav-card-desc">{page['desc']}</div>
            </div>
            """, unsafe_allow_html=True)
            st.page_link(page["path"], label=f"Go to {page['title']} →")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Orchestrate the home page in order:
        1. CSS injection
        2. Sidebar
        3. Data loading (session_state cache)
        4. Header
        5. All-time stats
        6. Today's recovery
        7. Navigation cards
    """
    load_css()
    render_sidebar()

    # Load data — stop with a friendly error if the DB isn't ready
    try:
        df_training, df_health, df_race, min_date, max_date = _load_data_cached()
    except FileNotFoundError as e:
        st.error(f"⚠️ Database not found.\n\n{e}")
        st.stop()
        return
    except Exception as e:
        st.error(f"⚠️ Failed to load data: {e}")
        st.stop()
        return

    render_header(min_date, max_date)

    st.markdown("### All-Time Stats")
    render_all_time_stats(df_training, df_race)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    st.markdown("### Today's Recovery")
    render_recovery_status(df_health)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    render_quick_nav()


if __name__ == "__main__":
    main()
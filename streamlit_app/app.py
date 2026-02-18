"""
Home page and entry point for the Running Performance Analyzer.

Sections (in order):
    1. CSS injection        → Garmin-inspired light theme
    2. Sidebar              → pipeline status + quick links
    3. Data loading         → via st.session_state (avoids Arrow serialization bug)
    4. Hero header          → gradient title, date range badge
    5. All-time stats       → key metrics row
    6. Today's recovery     → recovery score + readiness
    7. Navigation cards     → links to the 4 sub-pages

Run with:
    streamlit run streamlit_app/app.py

Technical notes:
    - st.session_state replaces @st.cache_data (DuckDB 1.4.4 serialization fix)
    - st.set_page_config() must be the very first Streamlit call
    - Environment: venv_streamlit
"""

import pandas as pd
import streamlit as st

from components.metrics import render_all_time_stats, render_recovery_status
from utils.constants import APP_ICON, APP_SUBTITLE, APP_TITLE
from utils.database import get_date_range, load_calendar_events, load_health_data, load_race_data, load_training_data


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
# CSS  — light theme, consistent with Pages 1-4
# =============================================================================

def load_css() -> None:
    """
    Inject custom CSS for a light, Garmin-inspired look.

    Key design decisions:
    - No sidebar background override  → Streamlit's default light grey
    - White metric cards with a subtle blue border
    - Navigation cards use white background + blue accent on hover
    - All text uses dark-on-light (not light-on-dark) for readability
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

        /* ── Navigation cards ── */
        .nav-card {
            background: #FFFFFF;
            border: 1px solid #E0EAF5;
            border-radius: 14px;
            padding: 22px 18px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
            height: 100%;
        }
        .nav-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(0,119,182,0.15);
            border-color: #00B4D8;
        }
        .nav-card-icon {
            font-size: 2.2rem;
            margin-bottom: 10px;
        }
        .nav-card-title {
            font-size: 1rem;
            font-weight: 700;
            color: #1A1A2E;
            margin-bottom: 6px;
        }
        .nav-card-desc {
            font-size: 0.8rem;
            color: #6C757D;
            line-height: 1.4;
        }

        /* ── Pipeline status dots ── */
        .status-ok   { color: #2DC653; font-weight: 700; }
        .status-warn { color: #FFD60A; font-weight: 700; }
        .status-err  { color: #EF233C; font-weight: 700; }

        /* ── page_link button overrides ── */
        [data-testid="stPageLink"] {
            margin-top: 8px;
        }
        [data-testid="stPageLink"] a {
            font-size: 0.85rem !important;
            color: #0077B6 !important;
            font-weight: 600 !important;
        }
    </style>
    """, unsafe_allow_html=True)


# =============================================================================
# DATA LOADING
# =============================================================================

def _load_data_cached() -> tuple:
    """
    Load all DataFrames once per browser session via st.session_state.

    We avoid @st.cache_data because it serialises DataFrames with Arrow,
    which triggers a 'Serialization Error: field id 100' with DuckDB 1.4.4.
    st.session_state stores objects directly in memory — no serialisation.

    Returns:
        tuple: (df_training, df_health, df_race, df_calendar, min_date, max_date)
    """
    if "data_loaded" not in st.session_state:
        st.session_state.df_training = load_training_data()
        st.session_state.df_health   = load_health_data()
        st.session_state.df_race     = load_race_data()
        st.session_state.df_calendar = load_calendar_events()
        st.session_state.min_date, st.session_state.max_date = get_date_range()
        st.session_state.data_loaded = True

    return (
        st.session_state.df_training,
        st.session_state.df_health,
        st.session_state.df_race,
        st.session_state.df_calendar,
        st.session_state.min_date,
        st.session_state.max_date,
    )


def _clear_cache() -> None:
    """Force a full data refresh on next load."""
    for key in ["data_loaded", "df_training", "df_health", "df_race",
                "df_calendar", "min_date", "max_date"]:
        st.session_state.pop(key, None)


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar() -> None:
    """
    Render the sidebar with pipeline status indicators and quick navigation.
    Uses Streamlit's default light-grey sidebar (no background override).
    """
    with st.sidebar:
        st.markdown("## 🏃 Running Analyzer")
        st.divider()

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

        st.subheader("📌 Quick links")
        st.page_link("pages/1_📊_Dashboard.py",         label="📊 Dashboard")
        st.page_link("pages/2_📈_Training_Analysis.py", label="📈 Training Analysis")
        st.page_link("pages/3_🏃_Race_Performance.py",  label="🏃 Race Performance")
        st.page_link("pages/4_❤️_Health.py",             label="❤️ Health & Recovery")

        st.divider()
        st.caption("Built with Streamlit · DuckDB · dbt · Claude API")


# =============================================================================
# HERO HEADER
# =============================================================================

def render_header(min_date: str, max_date: str) -> None:
    """
    Render the gradient app title, subtitle, and data-range badge.

    Args:
        min_date: Earliest date in the dataset (ISO string or None).
        max_date: Most recent date in the dataset (ISO string or None).
    """
    col_title, col_logo = st.columns([4, 1])

    with col_title:
        st.markdown(f'<h1 class="hero-title">{APP_TITLE}</h1>', unsafe_allow_html=True)
        st.markdown(f'<p class="hero-subtitle">{APP_SUBTITLE}</p>', unsafe_allow_html=True)

        # Date range badge
        try:
            min_fmt = pd.Timestamp(min_date).strftime("%b %d, %Y")
            max_fmt = pd.Timestamp(max_date).strftime("%b %d, %Y")
            st.markdown(
                f'<span class="hero-badge">📅 Data: {min_fmt} → {max_fmt}</span>',
                unsafe_allow_html=True,
            )
        except Exception:
            pass

    with col_logo:
        # Stack badges top-right
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("🗄️ DuckDB · 🔄 dbt · 📊 Streamlit")

    st.markdown("<br>", unsafe_allow_html=True)


# =============================================================================
# NAVIGATION CARDS
# =============================================================================

def render_quick_nav() -> None:
    """
    Render 4 clickable navigation cards, one per sub-page.
    Each card has an icon, title, description, and a st.page_link button.
    """
    st.markdown('<p class="section-header">🗺️ Explore the Dashboard</p>', unsafe_allow_html=True)

    pages = [
        {
            "path":  "pages/1_📊_Dashboard.py",
            "icon":  "📊",
            "title": "Dashboard",
            "desc":  "Weekly overview, recent activities & key trends",
        },
        {
            "path":  "pages/2_📈_Training_Analysis.py",
            "icon":  "📈",
            "title": "Training Analysis",
            "desc":  "Load, pace progression & heart rate zones",
        },
        {
            "path":  "pages/3_🏃_Race_Performance.py",
            "icon":  "🏃",
            "title": "Race Performance",
            "desc":  "Personal records, race history & pace analysis",
        },
        {
            "path":  "pages/4_❤️_Health.py",
            "icon":  "❤️",
            "title": "Health & Recovery",
            "desc":  "Sleep, HRV, resting HR & recovery score",
        },
    ]

    cols = st.columns(4, gap="medium")

    for col, page in zip(cols, pages):
        with col:
            st.markdown(f"""
            <div class="nav-card">
                <div class="nav-card-icon">{page['icon']}</div>
                <div class="nav-card-title">{page['title']}</div>
                <div class="nav-card-desc">{page['desc']}</div>
            </div>
            """, unsafe_allow_html=True)
            st.page_link(page["path"], label=f"Open {page['title']} →")


# =============================================================================
# UPCOMING RACES
# =============================================================================

def _render_upcoming_races(df_calendar: pd.DataFrame) -> None:
    """
    Render upcoming race countdown cards from the Garmin calendar.

    Shows each future race as a card with:
    - Days until race (countdown badge)
    - Race name, distance category, location
    - Direct link to the race page (if available)

    Only displays races where is_upcoming = True.
    Shows a maximum of 4 upcoming races to keep the home page concise.

    Args:
        df_calendar: DataFrame from load_calendar_events(), may be empty.
    """
    st.markdown('<p class="section-header">🗓️ Upcoming Races</p>', unsafe_allow_html=True)

    # Guard: no calendar data at all
    if df_calendar is None or df_calendar.empty:
        st.info(
            "📋 No upcoming races found in your Garmin calendar. "
            "Register for a race in the Garmin Connect app and sync again."
        )
        return

    # Filter to upcoming events only (is_upcoming may be bool or int)
    df_upcoming = df_calendar[
        df_calendar["is_upcoming"].astype(bool) == True
    ].copy()

    if df_upcoming.empty:
        st.info(
            "📋 No upcoming races. All events in your calendar are in the past. "
            "Check the Race Performance page to review your history."
        )
        return

    # Ensure date column is a proper datetime for formatting
    df_upcoming["event_date"] = pd.to_datetime(df_upcoming["event_date"])

    # Sort ascending (soonest first) and cap at 4 cards
    df_upcoming = df_upcoming.sort_values("event_date").head(4)

    # Render one card per upcoming race
    cols = st.columns(len(df_upcoming), gap="medium")

    for col, (_, row) in zip(cols, df_upcoming.iterrows()):
        with col:
            days_left   = int(row.get("days_until_race", 0))
            race_date   = row["event_date"].strftime("%b %d, %Y")
            title       = row.get("title") or "Race"
            dist_cat    = row.get("race_distance_category") or ""
            location    = row.get("location") or ""
            race_url    = row.get("url") or ""

            # Countdown badge color: red < 14d, orange < 30d, blue otherwise
            if days_left <= 14:
                badge_color = "#EF233C"
            elif days_left <= 30:
                badge_color = "#F77F00"
            else:
                badge_color = "#0077B6"

            # Distance emoji mapping
            dist_icons = {
                "5K":           "5️⃣",
                "10K":          "🔟",
                "Half Marathon": "🏅",
                "Marathon":     "🏆",
                "Ultra":        "💪",
            }
            dist_icon = dist_icons.get(dist_cat, "🏁")

            # Build the optional link line
            link_html = (
                f'<a href="{race_url}" target="_blank" '
                f'style="font-size:0.75rem; color:#0077B6;">🔗 Race info</a>'
                if race_url else ""
            )

            st.markdown(f"""
            <div style="background:#FFFFFF; border:1px solid #E0EAF5;
                        border-radius:12px; padding:16px 14px;
                        border-top:4px solid {badge_color};
                        box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                <div style="text-align:center; margin-bottom:10px;">
                    <span style="background:{badge_color}; color:white;
                                font-size:0.8rem; font-weight:700;
                                padding:3px 10px; border-radius:20px;">
                        {'TODAY' if days_left == 0 else f'In {days_left} day{"s" if days_left != 1 else ""}'}
                    </span>
                </div>
                <div style="font-size:1.4rem; text-align:center;">{dist_icon}</div>
                <div style="font-size:0.95rem; font-weight:700; color:#1A1A2E;
                            text-align:center; margin:6px 0 4px;">{title}</div>
                <div style="font-size:0.8rem; color:#6C757D; text-align:center;">📅 {race_date}</div>
                {f'<div style="font-size:0.78rem; color:#6C757D; text-align:center; margin-top:2px;">📍 {location}</div>' if location else ''}
                {f'<div style="text-align:center; margin-top:8px;">{link_html}</div>' if link_html else ''}
            </div>
            """, unsafe_allow_html=True)


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    """
    Orchestrate the home page:
        1. CSS
        2. Sidebar
        3. Data load
        4. Hero header
        5. All-time stats
        6. Recovery status
        7. Navigation cards
    """
    load_css()
    render_sidebar()

    # Load data — show friendly error if DB isn't ready yet
    try:
        df_training, df_health, df_race, df_calendar, min_date, max_date = _load_data_cached()
    except FileNotFoundError as e:
        st.error(
            "⚠️ **Database not found.**\n\n"
            "Make sure you've run the ingestion script at least once:\n"
            "```bash\npython -m ingestion.ingest_garmin --days 30\n```"
        )
        st.stop()
        return
    except Exception as e:
        st.error(f"⚠️ Failed to load data: {e}")
        st.stop()
        return

    render_header(min_date, max_date)

    # ── All-time stats ────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">🏆 All-Time Stats</p>', unsafe_allow_html=True)
    render_all_time_stats(df_training, df_race)

    st.divider()

    # ── Recovery status ───────────────────────────────────────────────────────
    st.markdown('<p class="section-header">⚡ Today\'s Recovery</p>', unsafe_allow_html=True)
    render_recovery_status(df_health)

    st.divider()

    # ── Upcoming races (from Garmin calendar events) ─────────────────────────
    _render_upcoming_races(df_calendar)

    st.divider()

    # ── Navigation cards ──────────────────────────────────────────────────────
    render_quick_nav()

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

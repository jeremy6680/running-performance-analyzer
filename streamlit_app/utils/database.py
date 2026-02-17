# streamlit_app/utils/database.py
"""
Database connection and data loading utilities for the Streamlit app.

File structure at a glance:
    _query()                 → opens a short-lived DuckDB connection, returns DataFrame
    load_training_data()     → main_gold.mart_training_summary
    load_health_data()       → main_gold.mart_health_trends
    load_race_data()         → main_gold.mart_race_performance
    load_ai_features()       → main_gold.mart_ai_features (returns empty if not exists)
    load_recent_activities() → main_silver.stg_garmin_activities
    get_date_range()         → (min_date, max_date) from training data

NOTE on caching strategy:
    @st.cache_data serializes DataFrames using pickle/Arrow — this fails with
    some DuckDB versions due to internal type metadata (field id: 100 error).
    Solution: NO cache decorator on load_*() functions. Instead, we cache at
    the page level using st.session_state, which stores objects in memory
    without serialization. Each page calls load_*() once and stores the result
    in st.session_state for the duration of the session.
"""

import os
from pathlib import Path

import duckdb
import pandas as pd


# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------

def _find_db_path() -> Path:
    """
    Locate the DuckDB database by walking up the directory tree from this file.

    Search order:
        1. DUCKDB_PATH environment variable (Docker / CI / explicit override)
        2. Walk upward from database.py looking for data/duckdb/running_analytics.duckdb
        3. Fallback to expected path (will raise a clear FileNotFoundError)
    """
    env_path = os.getenv("DUCKDB_PATH")
    if env_path:
        return Path(env_path)

    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data" / "duckdb" / "running_analytics.duckdb"
        if candidate.exists():
            return candidate

    return Path(__file__).resolve().parents[2] / "data" / "duckdb" / "running_analytics.duckdb"


DB_PATH = _find_db_path()


# ---------------------------------------------------------------------------
# Private query helper
# ---------------------------------------------------------------------------

def _query(sql: str) -> pd.DataFrame:
    """
    Open a short-lived read-only DuckDB connection, execute a query,
    return a DataFrame, then close the connection immediately.

    No caching here — caching is handled at the session level via
    st.session_state in each page file.

    Args:
        sql: SQL query to execute.

    Returns:
        pd.DataFrame: Query results.

    Raises:
        FileNotFoundError: If the DuckDB file does not exist.
        duckdb.Error: If the query fails.
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"DuckDB database not found at: {DB_PATH}\n"
            "Run the ingestion pipeline first:\n"
            "  python -m ingestion.ingest_garmin"
        )

    with duckdb.connect(str(DB_PATH), read_only=True) as conn:
        return conn.execute(sql).df()


# ---------------------------------------------------------------------------
# Data loaders — NO @st.cache_data (avoids serialization errors)
# Caching is handled by the caller via st.session_state
# ---------------------------------------------------------------------------

def load_training_data() -> pd.DataFrame:
    """
    Load mart_training_summary from the gold layer.

    Returns:
        pd.DataFrame: Weekly training data, one row per week, sorted DESC.
    """
    return _query("""
        SELECT *
        FROM main_gold.mart_training_summary
        ORDER BY week_start_date DESC
    """)


def load_health_data() -> pd.DataFrame:
    """
    Load mart_health_trends from the gold layer.

    Returns:
        pd.DataFrame: Daily health metrics, sorted DESC by date.
    """
    return _query("""
        SELECT *
        FROM main_gold.mart_health_trends
        ORDER BY date DESC
    """)


def load_race_data() -> pd.DataFrame:
    """
    Load mart_race_performance from the gold layer.

    Returns:
        pd.DataFrame: Race results, sorted DESC by date.
    """
    return _query("""
        SELECT *
        FROM main_gold.mart_race_performance
        ORDER BY race_date DESC
    """)


def load_ai_features() -> pd.DataFrame:
    """
    Load mart_ai_features from the gold layer.
    Returns empty DataFrame if the table doesn't exist yet.

    Returns:
        pd.DataFrame: AI features, or empty DataFrame.
    """
    try:
        return _query("""
            SELECT *
            FROM main_gold.mart_ai_features
            ORDER BY week_start_date DESC
        """)
    except Exception:
        return pd.DataFrame()


def load_recent_activities(limit: int = 10) -> pd.DataFrame:
    """
    Load the most recent individual activities from the silver layer.

    Args:
        limit: Number of activities to return. Defaults to 10.

    Returns:
        pd.DataFrame: Recent activities with key metrics.
    """
    return _query(f"""
        SELECT
            activity_date,
            activity_name,
            activity_type,
            distance_km,
            duration_minutes,
            avg_pace_min_km,
            avg_heart_rate,
            elevation_gain_m,
            training_load,
            pace_zone
        FROM main_silver.stg_garmin_activities
        ORDER BY activity_date DESC
        LIMIT {limit}
    """)


def get_date_range() -> tuple[str, str]:
    """
    Return the earliest and latest dates in the training data.

    Returns:
        tuple[str, str]: (min_date, max_date) as "YYYY-MM-DD" strings.
    """
    try:
        result = _query("""
            SELECT
                MIN(week_start_date)::VARCHAR AS min_date,
                MAX(week_start_date)::VARCHAR AS max_date
            FROM main_gold.mart_training_summary
        """)
        if result.empty or result["min_date"].iloc[0] is None:
            today = pd.Timestamp.today().strftime("%Y-%m-%d")
            return ("2020-01-01", today)

        return (result["min_date"].iloc[0], result["max_date"].iloc[0])

    except Exception:
        today = pd.Timestamp.today().strftime("%Y-%m-%d")
        return ("2020-01-01", today)
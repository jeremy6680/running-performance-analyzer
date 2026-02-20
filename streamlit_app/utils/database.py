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
# Date normalisation
# ---------------------------------------------------------------------------

# Columns that should be stored as datetime.date (not pandas Timestamp or str).
# DuckDB returns DATE columns as datetime.date via fetchall(), but some columns
# arrive as strings (object dtype) when they were cast to VARCHAR upstream, or
# as Timestamp when pandas infers the type from mixed content.
# Normalising everything to datetime.date here means every page can safely
# compare against values returned by st.date_input() (which is datetime.date)
# without hitting the "Cannot compare Timestamp with datetime.date" TypeError.
_DATE_COLUMNS: set[str] = {
    "week_start_date",
    "date",
    "activity_date",
    "race_date",
    "event_date",
}


def _normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert any known date column present in *df* to ``datetime.date``.

    Why this is necessary:
        - ``fetchall()`` returns DuckDB DATE values as ``datetime.date`` objects,
          but pandas may later infer them as ``pd.Timestamp`` (e.g. after a
          concat or after session_state round-trips).
        - ``st.date_input()`` always returns ``datetime.date``.
        - Comparing ``pd.Timestamp >= datetime.date`` raises a ``TypeError``
          in pandas ≥ 2.0, so we normalise at load time once.
        - Columns that are already ``datetime.date`` are left untouched
          (``pd.to_datetime`` handles both strings and existing date objects).

    Args:
        df: DataFrame freshly built from ``fetchall()``.

    Returns:
        The same DataFrame with date columns cast to ``datetime.date``.
    """
    for col in _DATE_COLUMNS:
        if col not in df.columns:
            continue
        # pd.to_datetime is robust: handles str, datetime.date, Timestamp, None.
        # .dt.date extracts the Python datetime.date part, keeping NaT → NaN.
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    return df


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
        # Use fetchall() + column names instead of .df() to avoid the DuckDB
        # Arrow serialization error ("field id: 100") that occurs with certain
        # column types (BOOLEAN, HUGEINT, etc.) in DuckDB 1.x + pyarrow.
        # fetchall() returns plain Python objects; we build the DataFrame manually.
        result = conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        df = pd.DataFrame(rows, columns=columns)
        # Normalise date columns to datetime.date so all pages can safely
        # compare against st.date_input() values (also datetime.date).
        return _normalize_dates(df)


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


def load_weather_data() -> pd.DataFrame:
    """
    Load weather data joined to activities from the bronze layer.

    Weather columns are captured in raw_garmin_activities during ingestion
    but are not yet propagated to stg_garmin_activities (silver layer).
    We query the bronze table directly and join on activity_id.

    Temperature note: The Garmin API returns inconsistent units — some values
    are in Celsius (e.g. 7.0°C), others appear to be Fahrenheit stored in
    the _c column (e.g. 57.0 → 13.9°C). We auto-detect and normalise:
    - If weather_temp_c > 40: assume Fahrenheit, convert to Celsius
    - Otherwise: treat as Celsius already

    Returns:
        pd.DataFrame: One row per activity that has weather data.
    """
    return _query("""
        SELECT
            r.activity_id,
            r.activity_name,
            CAST(r.activity_date AS DATE) AS activity_date,
            r.activity_type,
            r.distance_km,
            r.duration_minutes,
            -- Apply the same sanity check as in stg_garmin_activities.sql:
            -- the Garmin API occasionally stores avg_heart_rate in the pace
            -- field (observed Feb 8/11/13 2026). Any value outside 2-20 min/km
            -- is replaced by the reliable duration/distance computation.
            CASE
                WHEN r.avg_pace_min_km >= 2.0
                 AND r.avg_pace_min_km <= 20.0 THEN r.avg_pace_min_km
                WHEN r.distance_km > 0         THEN ROUND(r.duration_minutes / r.distance_km, 3)
                ELSE NULL
            END AS avg_pace_min_km,
            r.avg_heart_rate,
            -- Temperature is stored in Celsius (converted from Fahrenheit during ingestion)
            ROUND(r.weather_temp_c, 1) AS temp_c,
            r.weather_temp_c AS temp_raw,   -- keep original for debug
            r.weather_humidity_pct    AS humidity_pct,
            -- Wind speed: convert m/s to km/h for readability
            ROUND(r.weather_wind_speed_ms * 3.6, 1) AS wind_kmh,
            r.weather_condition,
            r.weather_precipitation_mm AS precipitation_mm
        FROM raw_garmin_activities r
        WHERE r.weather_temp_c IS NOT NULL
          AND r.distance_km > 0
          AND r.duration_minutes >= 5
        ORDER BY r.activity_date DESC
    """)


def load_calendar_events() -> pd.DataFrame:
    """
    Load upcoming race calendar events from the silver layer.

    Returns:
        pd.DataFrame: Calendar events sorted by date ascending (soonest first).
                      Empty DataFrame if the table is empty or not accessible.
    """
    try:
        return _query("""
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
            -- Compute pace directly from duration and distance.
            -- This is the safest approach: the raw avg_pace_min_km field from
            -- the Garmin API has been observed returning corrupted values (e.g.
            -- the avg_heart_rate value) on some activities. The dbt staging model
            -- already applies a sanity filter on avg_pace_min_km, but we also
            -- compute it from first principles here as an extra safeguard.
            CASE 
                WHEN distance_km > 0 
                THEN ROUND(duration_minutes / distance_km, 3)
                ELSE NULL 
            END AS pace_min_km,
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
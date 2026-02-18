#!/usr/bin/env python3
"""
Diagnostic script — shows exactly what's in the DB for calendar events and weather.
Run from project root with the Streamlit venv (NOT venv_dbt):
    source venv/bin/activate
    python scripts/debug_db.py
"""
from pathlib import Path
import duckdb

DB_PATH = Path(__file__).parent.parent / "data" / "duckdb" / "running_analytics.duckdb"

print(f"\nDB path: {DB_PATH}")
print(f"DB exists: {DB_PATH.exists()}\n")

conn = duckdb.connect(str(DB_PATH), read_only=True)

# ── List ALL tables and schemas ──────────────────────────────────────────────
print("=" * 60)
print("ALL TABLES IN DB")
print("=" * 60)
tables = conn.execute("""
    SELECT table_schema, table_name
    FROM information_schema.tables
    WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
    ORDER BY table_schema, table_name
""").df()
print(tables.to_string(index=False))

# ── raw_garmin_calendar_events ───────────────────────────────────────────────
print("\n" + "=" * 60)
print("raw_garmin_calendar_events (bronze)")
print("=" * 60)
try:
    count = conn.execute("SELECT COUNT(*) FROM raw_garmin_calendar_events").fetchone()[0]
    print(f"Row count: {count}")
    if count > 0:
        df = conn.execute("""
            SELECT event_uuid, title, event_date, race_distance_category,
                   is_race, is_upcoming IF EXISTS ELSE NULL, subscribed
            FROM raw_garmin_calendar_events
            ORDER BY event_date
        """).df()
        print(df.to_string(index=False))
except Exception as e:
    # Try simpler query
    try:
        count = conn.execute("SELECT COUNT(*) FROM raw_garmin_calendar_events").fetchone()[0]
        print(f"Row count: {count}")
        df = conn.execute("SELECT * FROM raw_garmin_calendar_events LIMIT 5").df()
        print(df.to_string(index=False))
    except Exception as e2:
        print(f"ERROR: {e2}")

# ── stg_garmin_calendar_events ───────────────────────────────────────────────
print("\n" + "=" * 60)
print("main_silver.stg_garmin_calendar_events (dbt view)")
print("=" * 60)
try:
    count = conn.execute("SELECT COUNT(*) FROM main_silver.stg_garmin_calendar_events").fetchone()[0]
    print(f"Row count: {count}")
    if count > 0:
        df = conn.execute("""
            SELECT event_uuid, title, event_date, race_distance_category,
                   is_upcoming, days_until_race
            FROM main_silver.stg_garmin_calendar_events
            ORDER BY event_date
        """).df()
        print(df.to_string(index=False))
except Exception as e:
    print(f"ERROR: {e}")

# ── Weather in raw_garmin_activities ─────────────────────────────────────────
print("\n" + "=" * 60)
print("Weather in raw_garmin_activities (bronze)")
print("=" * 60)
try:
    total = conn.execute("SELECT COUNT(*) FROM raw_garmin_activities").fetchone()[0]
    with_weather = conn.execute(
        "SELECT COUNT(*) FROM raw_garmin_activities WHERE weather_temp_c IS NOT NULL"
    ).fetchone()[0]
    print(f"Total activities:        {total}")
    print(f"With weather_temp_c:     {with_weather}")
    print(f"Without weather_temp_c:  {total - with_weather}")

    print("\nLast 10 activities (weather columns):")
    df = conn.execute("""
        SELECT activity_id, CAST(activity_date AS DATE) AS date,
               distance_km,
               weather_temp_c, weather_condition, weather_humidity_pct
        FROM raw_garmin_activities
        ORDER BY activity_date DESC
        LIMIT 10
    """).df()
    print(df.to_string(index=False))
except Exception as e:
    print(f"ERROR: {e}")

conn.close()
print("\nDone.")

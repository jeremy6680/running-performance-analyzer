#!/usr/bin/env python3
"""
Diagnostic script v2 — checks weather fetch and calendar API directly.
Run from project root with the main venv:
    source venv/bin/activate
    python scripts/debug_weather_calendar.py
"""
from pathlib import Path
import duckdb
import json

DB_PATH = Path(__file__).parent.parent / "data" / "duckdb" / "running_analytics.duckdb"

# ── 1. Show real NULL situation ──────────────────────────────────────────────
print("=" * 60)
print("1. WEATHER NULL CHECK (SQL level)")
print("=" * 60)
conn = duckdb.connect(str(DB_PATH), read_only=True)
r = conn.execute("""
    SELECT
        COUNT(*) AS total,
        COUNT(weather_temp_c) AS non_null_temp,        -- COUNT() skips NULLs
        SUM(CASE WHEN weather_temp_c IS NOT NULL THEN 1 ELSE 0 END) AS is_not_null_temp
    FROM raw_garmin_activities
""").df()
print(r.to_string(index=False))

# Show the 3 most recent activity_ids so we can test weather fetch on them
recent_ids = conn.execute("""
    SELECT activity_id, CAST(activity_date AS DATE) AS date, distance_km
    FROM raw_garmin_activities
    WHERE distance_km > 1
    ORDER BY activity_date DESC
    LIMIT 3
""").df()
print("\nMost recent activities (to test weather fetch):")
print(recent_ids.to_string(index=False))
conn.close()

# ── 2. Test weather fetch on one real activity ───────────────────────────────
print("\n" + "=" * 60)
print("2. LIVE WEATHER FETCH TEST")
print("=" * 60)
from ingestion.garmin_connector import GarminConnector

connector = GarminConnector()
if not connector.login():
    print("❌ Login failed — cannot test weather fetch")
else:
    test_id = str(recent_ids["activity_id"].iloc[0])
    print(f"\nTesting weather fetch for activity_id: {test_id}")
    try:
        raw = connector.client.get_activity_weather(test_id)
        print(f"\nRAW API response (type={type(raw).__name__}):")
        print(json.dumps(raw, indent=2, default=str) if raw else "None / empty")
    except Exception as e:
        print(f"ERROR calling get_activity_weather: {e}")

    # Also test calendar API for current month
    print("\n" + "=" * 60)
    print("3. LIVE CALENDAR API TEST (current + next 3 months)")
    print("=" * 60)
    from datetime import datetime
    today = datetime.today()
    for offset in range(4):
        m_raw = today.month - 1 + offset
        y = today.year + m_raw // 12
        m = m_raw % 12 + 1
        try:
            raw_cal = connector.client.get_calendar(y, m - 1)   # 0-indexed month
            items = raw_cal.get("calendarItems", []) if raw_cal else []
            race_items = [i for i in items if i.get("isRace")]
            print(f"\n{y}-{m:02d}: {len(items)} total items, {len(race_items)} with isRace=True")
            if race_items:
                for item in race_items:
                    print(f"  → title={item.get('title')!r}, "
                          f"itemType={item.get('itemType')!r}, "
                          f"isRace={item.get('isRace')}, "
                          f"date={item.get('date')}")
        except Exception as e:
            print(f"  ERROR for {y}-{m:02d}: {e}")

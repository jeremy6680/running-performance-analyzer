"""
Garmin Calendar API Explorer.

This script explores what the Garmin Connect API returns for calendar events
and goals, so we can decide whether future races are available programmatically.

Run this BEFORE implementing the full ingestion pipeline for events:
    python scripts/explore_garmin_calendar.py

What it tests:
    1. get_active_goals()   — active wellness goals (steps, weight, etc.)
    2. get_future_goals()   — upcoming goals/events
    3. get_past_goals()     — historical goals
    4. A direct call to the calendar API endpoint for the current month

The output will show you exactly what JSON structure Garmin returns for your
account, which determines how (or whether) we store and transform this data.
"""

import json
import sys
from datetime import date
from pathlib import Path

# Add project root to path so we can import from ingestion/
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from ingestion.garmin_connector import GarminConnector


def pretty(label: str, data) -> None:
    """Print labelled JSON output for inspection."""
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print("=" * 60)
    if data is None:
        print("  → None (no data returned)")
    elif isinstance(data, (list, dict)):
        if not data:
            print("  → Empty ([] or {})")
        else:
            print(json.dumps(data, indent=2, default=str)[:3000])  # Truncate at 3000 chars
            if len(json.dumps(data, default=str)) > 3000:
                print("  ... [truncated — full response is larger]")
    else:
        print(f"  → {data}")


def main():
    """Explore Garmin calendar and goal API endpoints."""
    print("\n" + "=" * 60)
    print("  Garmin Calendar & Goals API Explorer")
    print("=" * 60)

    # Initialize and login
    connector = GarminConnector()
    if not connector.login():
        print("❌ Login failed. Check your credentials in .env")
        sys.exit(1)

    client = connector.client
    today = date.today()

    # ─── 1. Active Goals ───────────────────────────────────────────────────────
    # These are typically step/distance/weight goals set in Garmin Connect.
    # May include race events if they were added as goals.
    try:
        active_goals = client.get_active_goals()
        pretty("1. get_active_goals()", active_goals)
    except Exception as e:
        pretty("1. get_active_goals()", f"ERROR: {e}")

    # ─── 2. Future Goals ───────────────────────────────────────────────────────
    try:
        future_goals = client.get_future_goals()
        pretty("2. get_future_goals()", future_goals)
    except Exception as e:
        pretty("2. get_future_goals()", f"ERROR: {e}")

    # ─── 3. Past Goals ─────────────────────────────────────────────────────────
    try:
        past_goals = client.get_past_goals()
        pretty("3. get_past_goals()", past_goals)
    except Exception as e:
        pretty("3. get_past_goals()", f"ERROR: {e}")

    # ─── 4. Raw Calendar Endpoint ──────────────────────────────────────────────
    # The Garmin Connect calendar is at /calendar-service/year/{year}/month/{month}
    # This is undocumented but mirrors what the Connect web UI fetches.
    # Month is 0-indexed in Garmin's API (January = 0, December = 11).
    try:
        year = today.year
        month = today.month - 1  # Garmin uses 0-indexed months
        url = f"/calendar-service/year/{year}/month/{month}"
        calendar_data = client.connectapi(url)
        pretty(f"4. Calendar endpoint ({today.strftime('%B %Y')})", calendar_data)
    except Exception as e:
        pretty("4. Calendar endpoint", f"ERROR: {e}")

    # ─── 5. Next month (to catch upcoming races) ───────────────────────────────
    try:
        next_month = today.month  # month + 1, but still 0-indexed = today.month
        next_year = today.year if today.month < 12 else today.year + 1
        if today.month == 12:
            next_month = 0
        url = f"/calendar-service/year/{next_year}/month/{next_month}"
        calendar_next = client.connectapi(url)
        pretty(f"5. Calendar endpoint (next month)", calendar_next)
    except Exception as e:
        pretty("5. Calendar endpoint (next month)", f"ERROR: {e}")

    # ─── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Exploration complete!")
    print("=" * 60)
    print("""
Next steps based on results:
  - If get_future_goals() returns race events → we can ingest them directly
  - If calendar endpoint returns events with names/dates → we can parse those
  - If neither returns races → we manage future races in the seed CSV
  
Share the output with Claude to decide the ingestion strategy.
""")


if __name__ == "__main__":
    main()

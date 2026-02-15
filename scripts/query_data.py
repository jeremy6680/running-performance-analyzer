#!/usr/bin/env python3
"""
Query DuckDB database for running analytics.

This script provides an easy way to explore your running data stored in DuckDB.

Usage:
    # Show all data
    python scripts/query_data.py
    
    # Show only activities
    python scripts/query_data.py --activities
    
    # Show only health data
    python scripts/query_data.py --health
    
    # Show statistics
    python scripts/query_data.py --stats
    
    # Limit results
    python scripts/query_data.py --limit 5
"""

import argparse
from pathlib import Path

import duckdb
import pandas as pd

# Database path
DB_PATH = Path(__file__).parent.parent / "data/duckdb/running_analytics.duckdb"


def query_activities(conn: duckdb.DuckDBPyConnection, limit: int = None) -> pd.DataFrame:
    """Query activities from database."""
    query = """
        SELECT 
            activity_date,
            activity_type,
            distance_km,
            duration_minutes,
            avg_pace_min_km,
            avg_heart_rate,
            calories,
            elevation_gain_m
        FROM raw_garmin_activities
        ORDER BY activity_date DESC
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    return conn.execute(query).df()


def query_health(conn: duckdb.DuckDBPyConnection, limit: int = None) -> pd.DataFrame:
    """Query daily health data from database."""
    query = """
        SELECT 
            date,
            steps,
            resting_heart_rate,
            hrv_avg,
            ROUND(sleep_seconds / 3600.0, 1) as sleep_hours,
            stress_avg,
            body_battery_high,
            body_battery_low
        FROM raw_garmin_daily_health
        ORDER BY date DESC
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    return conn.execute(query).df()


def query_stats(conn: duckdb.DuckDBPyConnection) -> dict:
    """Get database statistics."""
    stats = {}
    
    # Activity stats
    activity_stats = conn.execute("""
        SELECT 
            COUNT(*) as total_runs,
            ROUND(SUM(distance_km), 2) as total_distance_km,
            ROUND(AVG(distance_km), 2) as avg_distance_km,
            ROUND(SUM(duration_minutes) / 60, 1) as total_hours,
            ROUND(AVG(avg_heart_rate), 0) as avg_heart_rate,
            ROUND(AVG(avg_pace_min_km), 2) as avg_pace_min_km,
            MIN(activity_date) as first_activity,
            MAX(activity_date) as last_activity
        FROM raw_garmin_activities
    """).fetchone()
    
    stats['activities'] = {
        'total_runs': activity_stats[0],
        'total_distance_km': activity_stats[1],
        'avg_distance_km': activity_stats[2],
        'total_hours': activity_stats[3],
        'avg_heart_rate': activity_stats[4],
        'avg_pace_min_km': activity_stats[5],
        'first_activity': activity_stats[6],
        'last_activity': activity_stats[7],
    }
    
    # Health stats
    health_stats = conn.execute("""
        SELECT 
            COUNT(*) as total_days,
            ROUND(AVG(steps), 0) as avg_steps,
            ROUND(AVG(resting_heart_rate), 0) as avg_resting_hr,
            ROUND(AVG(hrv_avg), 0) as avg_hrv,
            ROUND(AVG(sleep_seconds) / 3600, 1) as avg_sleep_hours,
            ROUND(AVG(stress_avg), 0) as avg_stress,
            MIN(date) as first_record,
            MAX(date) as last_record
        FROM raw_garmin_daily_health
    """).fetchone()
    
    stats['health'] = {
        'total_days': health_stats[0],
        'avg_steps': health_stats[1],
        'avg_resting_hr': health_stats[2],
        'avg_hrv': health_stats[3],
        'avg_sleep_hours': health_stats[4],
        'avg_stress': health_stats[5],
        'first_record': health_stats[6],
        'last_record': health_stats[7],
    }
    
    # Activity type breakdown
    activity_types = conn.execute("""
        SELECT 
            activity_type,
            COUNT(*) as count,
            ROUND(SUM(distance_km), 2) as total_distance_km
        FROM raw_garmin_activities
        GROUP BY activity_type
        ORDER BY count DESC
    """).df()
    
    stats['activity_types'] = activity_types
    
    return stats


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Query running analytics data from DuckDB"
    )
    
    parser.add_argument(
        "--activities",
        action="store_true",
        help="Show only activities"
    )
    
    parser.add_argument(
        "--health",
        action="store_true",
        help="Show only health data"
    )
    
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show only statistics"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of results"
    )
    
    args = parser.parse_args()
    
    # Check if database exists
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        print("Run ingestion first: python -m ingestion.ingest_garmin")
        return
    
    # Connect to database
    conn = duckdb.connect(str(DB_PATH))
    
    # Determine what to show
    show_all = not (args.activities or args.health or args.stats)
    
    try:
        # Activities
        if args.activities or show_all:
            print_section("🏃 ACTIVITIES")
            activities = query_activities(conn, limit=args.limit)
            if not activities.empty:
                print(activities.to_string(index=False))
            else:
                print("No activities found")
        
        # Health
        if args.health or show_all:
            print_section("❤️  DAILY HEALTH")
            health = query_health(conn, limit=args.limit)
            if not health.empty:
                print(health.to_string(index=False))
            else:
                print("No health data found")
        
        # Stats
        if args.stats or show_all:
            print_section("📊 STATISTICS")
            stats = query_stats(conn)
            
            # Activity stats
            print("\n🏃 Activity Statistics:")
            act_stats = stats['activities']
            print(f"  Total runs: {act_stats['total_runs']}")
            print(f"  Total distance: {act_stats['total_distance_km']} km")
            print(f"  Average distance: {act_stats['avg_distance_km']} km")
            print(f"  Total time: {act_stats['total_hours']} hours")
            print(f"  Average heart rate: {act_stats['avg_heart_rate']} bpm")
            print(f"  Average pace: {act_stats['avg_pace_min_km']} min/km")
            print(f"  First activity: {act_stats['first_activity']}")
            print(f"  Last activity: {act_stats['last_activity']}")
            
            # Health stats
            print("\n❤️  Health Statistics:")
            health_stats = stats['health']
            print(f"  Total days: {health_stats['total_days']}")
            print(f"  Average steps: {health_stats['avg_steps']:,.0f} steps/day")
            print(f"  Average resting HR: {health_stats['avg_resting_hr']} bpm")
            print(f"  Average HRV: {health_stats['avg_hrv']} ms")
            print(f"  Average sleep: {health_stats['avg_sleep_hours']} hours")
            print(f"  Average stress: {health_stats['avg_stress']}/100")
            print(f"  First record: {health_stats['first_record']}")
            print(f"  Last record: {health_stats['last_record']}")
            
            # Activity types
            print("\n📈 Activity Types:")
            for _, row in stats['activity_types'].iterrows():
                print(f"  {row['activity_type']}: {row['count']} activities, {row['total_distance_km']} km")
        
        print("\n" + "=" * 70)
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
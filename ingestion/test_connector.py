"""
Simple test script for Garmin connector.

This script demonstrates how to use the GarminConnector to fetch data.
Run this to verify your Garmin credentials are working.

Usage:
    python -m ingestion.test_connector
    
    # Or with custom parameters:
    python -m ingestion.test_connector --days 30
"""

import argparse
from pathlib import Path

from loguru import logger

from ingestion.garmin_connector import GarminConnector


def main(days: int = 7):
    """
    Test Garmin connector and fetch sample data.
    
    Args:
        days: Number of days to fetch (default: 7)
    """
    print("=" * 70)
    print("🏃 GARMIN CONNECTOR TEST")
    print("=" * 70)
    
    # Initialize connector
    logger.info("Initializing Garmin connector...")
    connector = GarminConnector()
    
    # Login
    print("\n🔐 Logging in to Garmin Connect...")
    if not connector.login():
        print("\n❌ Login failed. Please check your credentials in .env file.")
        print("   Required variables:")
        print("   - GARMIN_EMAIL=your_email@example.com")
        print("   - GARMIN_PASSWORD=your_password")
        return
    
    print("\n✅ Login successful!")
    
    # Fetch user profile
    print("\n" + "=" * 70)
    print("👤 USER PROFILE")
    print("=" * 70)
    try:
        profile = connector.get_user_profile()
        print(f"Name: {profile['full_name']}")
        print(f"Email: {profile['email']}")
    except Exception as e:
        print(f"❌ Could not fetch profile: {e}")
    
    # Fetch activities
    print("\n" + "=" * 70)
    print(f"🏃 ACTIVITIES (Last {days} days)")
    print("=" * 70)
    try:
        activities = connector.fetch_activities(days=days)
        
        if activities.empty:
            print(f"No activities found in the last {days} days")
        else:
            print(f"\n✅ Found {len(activities)} activities")
            print("\nActivity Summary:")
            print(activities[[
                "activity_date",
                "activity_type",
                "distance_km",
                "duration_minutes",
                "avg_pace_min_km",
                "avg_heart_rate"
            ]].to_string(index=False))
            
            # Statistics
            print("\n📊 Statistics:")
            total_distance = activities["distance_km"].sum()
            total_time = activities["duration_minutes"].sum()
            avg_hr = activities["avg_heart_rate"].mean()
            
            print(f"  Total distance: {total_distance:.2f} km")
            print(f"  Total time: {total_time:.2f} minutes ({total_time/60:.1f} hours)")
            print(f"  Average heart rate: {avg_hr:.0f} bpm")
            
            # Activity type breakdown
            print("\n📈 Activity Types:")
            type_counts = activities["activity_type"].value_counts()
            for activity_type, count in type_counts.items():
                print(f"  {activity_type}: {count} activities")
    
    except Exception as e:
        print(f"❌ Error fetching activities: {e}")
    
    # Fetch daily health
    print("\n" + "=" * 70)
    print(f"❤️  DAILY HEALTH (Last {days} days)")
    print("=" * 70)
    try:
        health = connector.fetch_daily_health(days=days)
        
        if health.empty:
            print(f"No health data found in the last {days} days")
        else:
            print(f"\n✅ Found health data for {len(health)} days")
            print("\nHealth Summary:")
            print(health[[
                "date",
                "steps",
                "resting_heart_rate",
                "hrv_avg",
                "sleep_seconds",
                "stress_avg"
            ]].to_string(index=False))
            
            # Statistics
            print("\n📊 Statistics:")
            avg_steps = health["steps"].mean()
            avg_rhr = health["resting_heart_rate"].mean()
            avg_hrv = health["hrv_avg"].mean()
            avg_sleep_hours = health["sleep_seconds"].mean() / 3600
            
            print(f"  Average steps: {avg_steps:.0f} steps/day")
            print(f"  Average resting HR: {avg_rhr:.0f} bpm")
            print(f"  Average HRV: {avg_hrv:.0f} ms")
            print(f"  Average sleep: {avg_sleep_hours:.1f} hours/night")
    
    except Exception as e:
        print(f"❌ Error fetching health data: {e}")
    
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETED")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Check that the data looks correct")
    print("2. If successful, you can now run the full ingestion script")
    print("3. Data will be loaded into DuckDB for further analysis")
    print("=" * 70)


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Test Garmin Connect API connection and fetch sample data"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to fetch (default: 7)"
    )
    
    args = parser.parse_args()
    
    # Run test
    main(days=args.days)

"""
Garmin data ingestion script.

This script fetches data from Garmin Connect API and loads it into DuckDB.
Can be run manually or via Airflow DAG (later).

Usage:
    # Fetch last 7 days
    python -m ingestion.ingest_garmin
    
    # Fetch last 30 days
    python -m ingestion.ingest_garmin --days 30
    
    # Initial full sync (365 days)
    python -m ingestion.ingest_garmin --initial
"""

import argparse
from datetime import datetime

from loguru import logger

from ingestion.config import app_config
from ingestion.duckdb_manager import DuckDBManager
from ingestion.garmin_connector import GarminConnector


def ingest_garmin_data(days: int = 7, mode: str = "upsert") -> dict:
    """
    Fetch data from Garmin and load into DuckDB.
    
    Args:
        days: Number of days to fetch (default: 7)
        mode: Insert mode - 'append', 'replace', or 'upsert' (default: upsert)
    
    Returns:
        Dictionary with ingestion statistics
    
    Example:
        >>> stats = ingest_garmin_data(days=30, mode='upsert')
        >>> print(f"Loaded {stats['activities_count']} activities")
    """
    stats = {
        'start_time': datetime.now(),
        'days': days,
        'mode': mode,
        'activities_count': 0,
        'health_count': 0,
        'success': False,
        'error': None,
    }
    
    try:
        # Initialize Garmin connector
        logger.info("=" * 70)
        logger.info("🏃 GARMIN DATA INGESTION")
        logger.info("=" * 70)
        logger.info(f"Mode: {mode} | Days: {days}")
        
        connector = GarminConnector()
        
        # Login
        logger.info("\n🔐 Logging in to Garmin Connect...")
        if not connector.login():
            raise Exception("Failed to login to Garmin Connect")
        
        # Fetch activities
        logger.info(f"\n📊 Fetching activities (last {days} days)...")
        activities_df = connector.fetch_activities(days=days)
        
        if not activities_df.empty:
            logger.info(f"✅ Fetched {len(activities_df)} activities")
        else:
            logger.warning(f"⚠️  No activities found in last {days} days")
        
        # Fetch daily health
        logger.info(f"\n❤️  Fetching daily health (last {days} days)...")
        health_df = connector.fetch_daily_health(days=days)
        
        if not health_df.empty:
            logger.info(f"✅ Fetched health data for {len(health_df)} days")
        else:
            logger.warning(f"⚠️  No health data found in last {days} days")
        
        # Initialize DuckDB
        logger.info("\n💾 Initializing DuckDB...")
        db_manager = DuckDBManager()
        db_manager.initialize_database()
        
        # Insert activities
        if not activities_df.empty:
            logger.info(f"\n📥 Loading activities into DuckDB (mode: {mode})...")
            activities_count = db_manager.insert_activities(activities_df, mode=mode)
            stats['activities_count'] = activities_count
        
        # Insert health data
        if not health_df.empty:
            logger.info(f"\n📥 Loading health data into DuckDB (mode: {mode})...")
            health_count = db_manager.insert_daily_health(health_df, mode=mode)
            stats['health_count'] = health_count
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("📊 INGESTION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Activities loaded: {stats['activities_count']}")
        logger.info(f"Health records loaded: {stats['health_count']}")
        logger.info(f"Database: {db_manager.db_path}")
        logger.info("\n📈 Database Status:")
        logger.info(f"  Total activities: {db_manager.get_activities_count()}")
        logger.info(f"  Total health records: {db_manager.get_health_count()}")
        
        # Close connection
        db_manager.close()
        
        stats['success'] = True
        stats['end_time'] = datetime.now()
        stats['duration_seconds'] = (stats['end_time'] - stats['start_time']).total_seconds()
        
        logger.success("\n✅ INGESTION COMPLETED SUCCESSFULLY!")
        logger.info("=" * 70)
        
        return stats
        
    except Exception as e:
        logger.error(f"\n❌ INGESTION FAILED: {e}")
        stats['success'] = False
        stats['error'] = str(e)
        stats['end_time'] = datetime.now()
        raise


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Ingest Garmin data into DuckDB"
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Number of days to fetch (default: 7 for daily, 365 for initial)"
    )
    
    parser.add_argument(
        "--initial",
        action="store_true",
        help="Initial full sync (365 days)"
    )
    
    parser.add_argument(
        "--mode",
        type=str,
        choices=["append", "replace", "upsert"],
        default="upsert",
        help="Insert mode (default: upsert)"
    )
    
    args = parser.parse_args()
    
    # Determine days
    if args.initial:
        days = app_config.initial_sync_days  # Default: 365
        logger.info("🚀 Running INITIAL sync (full history)")
    else:
        days = args.days or app_config.daily_sync_days  # Default: 7
        logger.info("🔄 Running DAILY sync")
    
    # Run ingestion
    try:
        stats = ingest_garmin_data(days=days, mode=args.mode)
        
        # Print final summary
        print("\n" + "=" * 70)
        print("✅ SUCCESS")
        print("=" * 70)
        print(f"Duration: {stats['duration_seconds']:.1f} seconds")
        print(f"Activities: {stats['activities_count']}")
        print(f"Health records: {stats['health_count']}")
        print("=" * 70)
        
    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ FAILED")
        print("=" * 70)
        print(f"Error: {e}")
        print("=" * 70)
        exit(1)


if __name__ == "__main__":
    main()
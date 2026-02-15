"""
DuckDB Manager for Running Performance Analyzer.

This module handles all DuckDB operations including:
- Database initialization
- Table creation (bronze layer)
- Data insertion and updates
- Query execution

Usage:
    from ingestion.duckdb_manager import DuckDBManager
    
    manager = DuckDBManager()
    manager.initialize_database()
    manager.insert_activities(activities_df)
"""

from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd
from loguru import logger

from ingestion.config import database_config


class DuckDBManager:
    """
    Manage DuckDB database operations for running analytics.
    
    Handles connection, table creation, and data operations for the bronze layer
    (raw data from APIs).
    
    Attributes:
        db_path: Path to DuckDB database file
        connection: Active DuckDB connection
    
    Example:
        >>> manager = DuckDBManager()
        >>> manager.initialize_database()
        >>> activities = pd.DataFrame(...)
        >>> manager.insert_activities(activities)
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize DuckDB manager.
        
        Args:
            db_path: Path to DuckDB file (defaults to config)
        """
        self.db_path = db_path or database_config.path
        
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.connection: Optional[duckdb.DuckDBPyConnection] = None
        
        logger.info(f"Initialized DuckDBManager for {self.db_path}")
    
    def connect(self) -> duckdb.DuckDBPyConnection:
        """
        Create a connection to DuckDB.
        
        Returns:
            Active DuckDB connection
        
        Example:
            >>> manager = DuckDBManager()
            >>> conn = manager.connect()
        """
        if self.connection is None:
            self.connection = duckdb.connect(str(self.db_path))
            logger.info(f"Connected to DuckDB at {self.db_path}")
        
        return self.connection
    
    def close(self) -> None:
        """Close DuckDB connection."""
        if self.connection is not None:
            self.connection.close()
            self.connection = None
            logger.info("Closed DuckDB connection")
    
    def execute(self, query: str, params: Optional[tuple] = None) -> duckdb.DuckDBPyConnection:
        """
        Execute a SQL query.
        
        Args:
            query: SQL query to execute
            params: Optional query parameters
        
        Returns:
            DuckDB connection with query result
        
        Example:
            >>> manager.execute("SELECT COUNT(*) FROM raw_garmin_activities")
        """
        conn = self.connect()
        
        if params:
            return conn.execute(query, params)
        else:
            return conn.execute(query)
    
    def initialize_database(self) -> None:
        """
        Initialize database with bronze layer tables.
        
        Creates all necessary tables for raw data storage if they don't exist.
        This is idempotent - safe to run multiple times.
        
        Tables created:
        - raw_garmin_activities: Raw activity data from Garmin
        - raw_garmin_daily_health: Raw daily health metrics
        
        Example:
            >>> manager = DuckDBManager()
            >>> manager.initialize_database()
        """
        logger.info("Initializing DuckDB database...")
        
        # Create raw_garmin_activities table
        self.execute("""
            CREATE TABLE IF NOT EXISTS raw_garmin_activities (
                -- Identifiers
                activity_id VARCHAR PRIMARY KEY,
                activity_name VARCHAR,
                
                -- Date/Time
                activity_date TIMESTAMP,
                start_time_local TIMESTAMP,
                start_time_gmt TIMESTAMP,
                
                -- Activity Type
                activity_type VARCHAR,
                
                -- Distance & Duration
                distance_m DOUBLE,
                distance_km DOUBLE,
                duration_seconds DOUBLE,
                duration_minutes DOUBLE,
                moving_duration_seconds DOUBLE,
                
                -- Pace & Speed
                avg_speed_mps DOUBLE,
                max_speed_mps DOUBLE,
                avg_pace_min_km DOUBLE,
                
                -- Heart Rate
                avg_heart_rate INTEGER,
                max_heart_rate INTEGER,
                
                -- Elevation
                elevation_gain_m DOUBLE,
                elevation_loss_m DOUBLE,
                min_elevation_m DOUBLE,
                max_elevation_m DOUBLE,
                
                -- Calories & Training
                calories INTEGER,
                avg_cadence INTEGER,
                max_cadence INTEGER,
                aerobic_training_effect DOUBLE,
                anaerobic_training_effect DOUBLE,
                
                -- Metadata
                device_name VARCHAR,
                location_name VARCHAR,
                
                -- Audit fields
                inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        logger.success("✅ Created table: raw_garmin_activities")
        
        # Create raw_garmin_daily_health table
        self.execute("""
            CREATE TABLE IF NOT EXISTS raw_garmin_daily_health (
                -- Primary key
                date DATE PRIMARY KEY,
                
                -- Steps & Activity
                steps INTEGER,
                distance_m DOUBLE,
                active_calories INTEGER,
                bmr_calories INTEGER,
                
                -- Heart Rate
                resting_heart_rate INTEGER,
                min_heart_rate INTEGER,
                max_heart_rate INTEGER,
                
                -- HRV (Heart Rate Variability)
                hrv_avg DOUBLE,
                hrv_status VARCHAR,
                
                -- Sleep
                sleep_seconds INTEGER,
                deep_sleep_seconds INTEGER,
                light_sleep_seconds INTEGER,
                rem_sleep_seconds INTEGER,
                awake_seconds INTEGER,
                
                -- Stress & Recovery
                stress_avg INTEGER,
                body_battery_charged INTEGER,
                body_battery_drained INTEGER,
                body_battery_high INTEGER,
                body_battery_low INTEGER,
                
                -- Respiration
                avg_waking_respiration_rate DOUBLE,
                avg_sleep_respiration_rate DOUBLE,
                
                -- Audit fields
                inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        logger.success("✅ Created table: raw_garmin_daily_health")
        
        logger.success("✅ Database initialization complete!")
    
    def insert_activities(self, activities_df: pd.DataFrame, mode: str = "replace") -> int:
        """
        Insert activities into raw_garmin_activities table.
        
        Args:
            activities_df: DataFrame with activity data
            mode: Insert mode - 'append', 'replace', or 'upsert' (default: replace)
        
        Returns:
            Number of rows inserted
        
        Raises:
            ValueError: If mode is invalid or DataFrame is empty
        
        Example:
            >>> activities = connector.fetch_activities(days=7)
            >>> count = manager.insert_activities(activities, mode='append')
            >>> print(f"Inserted {count} activities")
        """
        if activities_df.empty:
            logger.warning("No activities to insert (empty DataFrame)")
            return 0
        
        conn = self.connect()
        
        # Prepare DataFrame
        df = activities_df.copy()
        
        # Ensure activity_date is datetime
        if 'activity_date' in df.columns:
            df['activity_date'] = pd.to_datetime(df['activity_date'])
        
        if mode == "replace":
            # Drop existing data and insert new
            logger.info("Replacing all activities in database...")
            conn.execute("DELETE FROM raw_garmin_activities")
            # Insert without audit fields (they have defaults)
            conn.execute("""
                INSERT INTO raw_garmin_activities 
                SELECT *, 
                       CURRENT_TIMESTAMP as inserted_at,
                       CURRENT_TIMESTAMP as updated_at
                FROM df
            """)
            
        elif mode == "append":
            # Simply append (may create duplicates)
            logger.info("Appending activities to database...")
            conn.execute("""
                INSERT INTO raw_garmin_activities 
                SELECT *, 
                       CURRENT_TIMESTAMP as inserted_at,
                       CURRENT_TIMESTAMP as updated_at
                FROM df
            """)
            
        elif mode == "upsert":
            # Insert or update based on activity_id
            logger.info("Upserting activities (insert or update)...")
            
            # Then, insert new records (those not in target)
            conn.execute("""
                INSERT INTO raw_garmin_activities
                SELECT *, 
                       CURRENT_TIMESTAMP as inserted_at,
                       CURRENT_TIMESTAMP as updated_at
                FROM df
                WHERE activity_id NOT IN (
                    SELECT activity_id FROM raw_garmin_activities
                )
            """)
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'append', 'replace', or 'upsert'")
        
        # Get count
        count = len(df)
        
        logger.success(f"✅ Inserted/updated {count} activities (mode: {mode})")
        
        return count
    
    def insert_daily_health(self, health_df: pd.DataFrame, mode: str = "replace") -> int:
        """
        Insert daily health data into raw_garmin_daily_health table.
        
        Args:
            health_df: DataFrame with daily health data
            mode: Insert mode - 'append', 'replace', or 'upsert' (default: replace)
        
        Returns:
            Number of rows inserted
        
        Example:
            >>> health = connector.fetch_daily_health(days=7)
            >>> count = manager.insert_daily_health(health, mode='upsert')
        """
        if health_df.empty:
            logger.warning("No health data to insert (empty DataFrame)")
            return 0
        
        conn = self.connect()
        
        # Prepare DataFrame
        df = health_df.copy()
        
        # Ensure date is date type (not datetime)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.date
        
        if mode == "replace":
            logger.info("Replacing all health data in database...")
            conn.execute("DELETE FROM raw_garmin_daily_health")
            conn.execute("""
                INSERT INTO raw_garmin_daily_health 
                SELECT *, 
                       CURRENT_TIMESTAMP as inserted_at,
                       CURRENT_TIMESTAMP as updated_at
                FROM df
            """)
            
        elif mode == "append":
            logger.info("Appending health data to database...")
            conn.execute("""
                INSERT INTO raw_garmin_daily_health 
                SELECT *, 
                       CURRENT_TIMESTAMP as inserted_at,
                       CURRENT_TIMESTAMP as updated_at
                FROM df
            """)
            
        elif mode == "upsert":
            logger.info("Upserting health data (insert or update)...")
            
            # Insert new records
            conn.execute("""
                INSERT INTO raw_garmin_daily_health
                SELECT *, 
                       CURRENT_TIMESTAMP as inserted_at,
                       CURRENT_TIMESTAMP as updated_at
                FROM df
                WHERE date NOT IN (
                    SELECT date FROM raw_garmin_daily_health
                )
            """)
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'append', 'replace', or 'upsert'")
        
        count = len(df)
        
        logger.success(f"✅ Inserted/updated {count} daily health records (mode: {mode})")
        
        return count
    
    def get_activities_count(self) -> int:
        """Get total count of activities in database."""
        result = self.execute("SELECT COUNT(*) FROM raw_garmin_activities").fetchone()
        return result[0] if result else 0
    
    def get_health_count(self) -> int:
        """Get total count of health records in database."""
        result = self.execute("SELECT COUNT(*) FROM raw_garmin_daily_health").fetchone()
        return result[0] if result else 0
    
    def get_activities(self, limit: Optional[int] = None) -> pd.DataFrame:
        """
        Fetch activities from database.
        
        Args:
            limit: Maximum number of records to return
        
        Returns:
            DataFrame with activities
        """
        query = "SELECT * FROM raw_garmin_activities ORDER BY activity_date DESC"
        if limit:
            query += f" LIMIT {limit}"
        
        return self.execute(query).df()
    
    def get_daily_health(self, limit: Optional[int] = None) -> pd.DataFrame:
        """
        Fetch daily health data from database.
        
        Args:
            limit: Maximum number of records to return
        
        Returns:
            DataFrame with health data
        """
        query = "SELECT * FROM raw_garmin_daily_health ORDER BY date DESC"
        if limit:
            query += f" LIMIT {limit}"
        
        return self.execute(query).df()
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


if __name__ == "__main__":
    # Test DuckDB manager
    print("=" * 60)
    print("DuckDB Manager Test")
    print("=" * 60)
    
    # Initialize manager
    manager = DuckDBManager()
    
    # Initialize database
    print("\n📦 Initializing database...")
    manager.initialize_database()
    
    # Check counts
    print("\n📊 Database Status:")
    print(f"  Activities: {manager.get_activities_count()}")
    print(f"  Health records: {manager.get_health_count()}")
    
    # Test with sample data
    print("\n🧪 Testing with sample data...")
    
    sample_activities = pd.DataFrame([
        {
            'activity_id': 'test_001',
            'activity_name': 'Morning Run',
            'activity_date': pd.Timestamp('2026-02-15'),
            'activity_type': 'running',
            'distance_km': 5.0,
            'duration_minutes': 25.0,
            'avg_pace_min_km': 5.0,
            'avg_heart_rate': 145,
        }
    ])
    
    manager.insert_activities(sample_activities, mode='replace')
    
    print(f"\n✅ Test complete! Database at: {manager.db_path}")
    print("=" * 60)
    
    manager.close()
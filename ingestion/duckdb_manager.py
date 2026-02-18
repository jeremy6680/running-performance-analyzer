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
                
                -- Event Type (Garmin's race tag in Connect UI)
                -- 'race' when user tags activity as a race, else NULL or 'training'
                event_type VARCHAR,
                
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
                
                -- Weather at time of activity (fetched via get_activity_weather)
                weather_temp_c DOUBLE,          -- Temperature in Celsius
                weather_feels_like_c DOUBLE,    -- Feels-like temperature in Celsius
                weather_humidity_pct INTEGER,   -- Humidity percentage (0-100)
                weather_wind_speed_ms DOUBLE,   -- Wind speed in metres per second
                weather_condition VARCHAR,      -- e.g. 'CLEAR', 'RAIN', 'CLOUDY'
                weather_precipitation_mm DOUBLE, -- Precipitation in mm
                
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
        
        # ── Resolve which DataFrame columns map to table columns ────────────
        # We use explicit column lists to avoid positional mismatch when the
        # DataFrame has more or fewer columns than the table definition.
        # Only columns that exist in BOTH the DataFrame and the table are inserted.
        table_cols_result = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'raw_garmin_activities' "
            "AND column_name NOT IN ('inserted_at', 'updated_at') "
            "ORDER BY ordinal_position"
        ).fetchall()
        table_cols = [row[0] for row in table_cols_result]

        # Keep only columns present in the DataFrame (handles schema evolution)
        insert_cols = [c for c in table_cols if c in df.columns]
        col_list = ", ".join(insert_cols)
        select_list = ", ".join([f'df."{c}"' for c in insert_cols])

        if mode == "replace":
            # Drop existing data and insert new
            logger.info("Replacing all activities in database...")
            conn.execute("DELETE FROM raw_garmin_activities")
            conn.execute(f"""
                INSERT INTO raw_garmin_activities ({col_list}, inserted_at, updated_at)
                SELECT {select_list},
                       CURRENT_TIMESTAMP,
                       CURRENT_TIMESTAMP
                FROM df
            """)

        elif mode == "append":
            # Simply append (may create duplicates)
            logger.info("Appending activities to database...")
            conn.execute(f"""
                INSERT INTO raw_garmin_activities ({col_list}, inserted_at, updated_at)
                SELECT {select_list},
                       CURRENT_TIMESTAMP,
                       CURRENT_TIMESTAMP
                FROM df
            """)

        elif mode == "upsert":
            # Two-phase upsert:
            #   Phase 1 — insert brand-new activity_ids
            #   Phase 2 — update weather columns on existing rows that still
            #             have NULL weather (happens when activities were first
            #             ingested before weather fetching was added, or when
            #             a previous run failed to fetch weather for some rows)
            logger.info("Upserting activities (insert new + refresh NULL weather)...")

            # Phase 1: insert rows whose activity_id is not yet in the table
            conn.execute(f"""
                INSERT INTO raw_garmin_activities ({col_list}, inserted_at, updated_at)
                SELECT {select_list},
                       CURRENT_TIMESTAMP,
                       CURRENT_TIMESTAMP
                FROM df
                WHERE df.activity_id NOT IN (
                    SELECT activity_id FROM raw_garmin_activities
                )
            """)

            # Phase 2: back-fill weather on existing rows that lack it.
            # Only touch rows where weather_temp_c is still NULL AND the
            # incoming DataFrame has a non-NULL value for that activity_id.
            # We iterate over the DataFrame rows so we can use parameterised
            # UPDATE statements (DuckDB doesn't support UPDATE … FROM df natively
            # in all versions, so we build per-row updates for the small subset
            # of rows that qualify).
            weather_cols = [
                "weather_temp_c", "weather_feels_like_c", "weather_humidity_pct",
                "weather_wind_speed_ms", "weather_condition", "weather_precipitation_mm",
            ]
            # Only look at rows that have at least one non-NULL weather field
            has_weather_mask = df[weather_cols].notna().any(axis=1)
            df_with_weather = df[has_weather_mask]

            if not df_with_weather.empty:
                # Fetch which existing rows still have NULL weather_temp_c
                existing_null_weather = conn.execute(
                    "SELECT activity_id FROM raw_garmin_activities "
                    "WHERE weather_temp_c IS NULL"
                ).df()["activity_id"].tolist()

                to_update = df_with_weather[
                    df_with_weather["activity_id"].isin(existing_null_weather)
                ]

                updated_count = 0
                for _, row in to_update.iterrows():
                    set_clauses = []
                    values = []
                    for col in weather_cols:
                        if col in row.index and row[col] is not None and not (
                            isinstance(row[col], float) and pd.isna(row[col])
                        ):
                            set_clauses.append(f"{col} = ?")
                            values.append(row[col])

                    if set_clauses:
                        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                        sql = (
                            "UPDATE raw_garmin_activities SET "
                            + ", ".join(set_clauses)
                            + " WHERE activity_id = ?"
                        )
                        values.append(row["activity_id"])
                        conn.execute(sql, values)
                        updated_count += 1

                if updated_count:
                    logger.info(
                        f"  ↳ Back-filled weather for {updated_count} existing activities"
                    )
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
    
    def migrate_add_event_type(self) -> None:
        """
        Migration: add event_type column to raw_garmin_activities if it doesn't exist.

        Safe to run multiple times — checks for column existence first.
        Needed for existing databases created before event_type was added.

        Example:
            >>> manager.migrate_add_event_type()
        """
        conn = self.connect()

        # Check if column already exists
        existing_cols = [
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'raw_garmin_activities'"
            ).fetchall()
        ]

        if "event_type" not in existing_cols:
            conn.execute(
                "ALTER TABLE raw_garmin_activities ADD COLUMN event_type VARCHAR"
            )
            logger.success("✅ Migration: added event_type column to raw_garmin_activities")
        else:
            logger.info("Migration not needed: event_type column already exists")

    def migrate_add_weather_columns(self) -> None:
        """
        Migration: add weather columns to raw_garmin_activities if they don't exist.

        Safe to run multiple times — checks for column existence first.
        Adds 6 columns capturing weather conditions at the time of each activity.

        Example:
            >>> manager.migrate_add_weather_columns()
        """
        conn = self.connect()

        # Fetch all existing column names for this table
        existing_cols = [
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'raw_garmin_activities'"
            ).fetchall()
        ]

        # Map: column_name -> SQL definition to add
        # We add all weather columns in one block for clarity
        weather_cols = {
            "weather_temp_c":         "DOUBLE",           # Air temperature in Celsius
            "weather_feels_like_c":   "DOUBLE",           # Apparent temperature in Celsius
            "weather_humidity_pct":   "INTEGER",          # Relative humidity 0-100
            "weather_wind_speed_ms":  "DOUBLE",           # Wind speed in metres per second
            "weather_condition":      "VARCHAR",          # e.g. 'CLEAR', 'RAIN', 'CLOUDY'
            "weather_precipitation_mm": "DOUBLE",        # Precipitation in mm
        }

        added = []
        for col_name, col_type in weather_cols.items():
            if col_name not in existing_cols:
                conn.execute(
                    f"ALTER TABLE raw_garmin_activities ADD COLUMN {col_name} {col_type}"
                )
                added.append(col_name)

        if added:
            logger.success(f"✅ Migration: added weather columns: {', '.join(added)}")
        else:
            logger.info("Migration not needed: all weather columns already exist")

    def create_calendar_events_table(self) -> None:
        """
        Create the raw_garmin_calendar_events bronze table if it doesn't exist.

        This table stores race events fetched from the Garmin Connect calendar.
        It is part of the bronze (raw) layer — data is stored as-is from the API.

        Grain: One row per unique calendar race event (keyed on event_uuid).
        Idempotent: safe to call multiple times.

        Example:
            >>> manager.create_calendar_events_table()
        """
        self.execute("""
            CREATE TABLE IF NOT EXISTS raw_garmin_calendar_events (
                -- Primary key: Garmin's shareable event UUID
                -- This UUID is stable across re-fetches of the same event
                event_uuid VARCHAR PRIMARY KEY,

                -- Event details
                title    VARCHAR,        -- Full event title from Garmin calendar
                event_date DATE,         -- Date of the race
                location VARCHAR,        -- City/country (e.g. 'Cannes, FR')

                -- Distance
                distance_m   DOUBLE,     -- Official distance in metres (from completionTarget)
                distance_km  DOUBLE,     -- Distance in kilometres (computed)

                -- Race classification — same categories as stg_garmin_activities
                -- '5K' | '10K' | 'Half Marathon' | 'Marathon' | 'Ultra' | NULL
                race_distance_category VARCHAR,

                -- Timing
                start_time VARCHAR,      -- HH:MM start time (e.g. '08:30')
                timezone   VARCHAR,      -- IANA timezone id (e.g. 'Europe/Paris')

                -- Flags
                is_race    BOOLEAN,      -- Always TRUE (we only store race events)
                subscribed BOOLEAN,      -- TRUE if user subscribed to this event

                -- External link to race page
                url VARCHAR,

                -- Audit fields
                inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.success("✅ Created table: raw_garmin_calendar_events")

    def insert_calendar_events(self, events_df: pd.DataFrame) -> int:
        """
        Upsert calendar race events into raw_garmin_calendar_events.

        Uses INSERT OR REPLACE semantics so that re-running ingestion
        refreshes event details (e.g. title edits, new subscriptions)
        without creating duplicates.

        Args:
            events_df: DataFrame returned by GarminConnector.fetch_calendar_events()

        Returns:
            Number of rows inserted/updated.

        Example:
            >>> events = connector.fetch_calendar_events()
            >>> count = manager.insert_calendar_events(events)
            >>> print(f"Upserted {count} calendar events")
        """
        if events_df.empty:
            logger.warning("No calendar events to insert (empty DataFrame)")
            return 0

        conn = self.connect()
        df = events_df.copy()

        # Ensure date column is the correct type (Python date, not datetime)
        if "event_date" in df.columns:
            df["event_date"] = pd.to_datetime(df["event_date"]).dt.date

        # Discover the columns that exist in both the DataFrame and the table,
        # excluding audit columns (those are set automatically).
        table_cols_result = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'raw_garmin_calendar_events' "
            "AND column_name NOT IN ('inserted_at', 'updated_at') "
            "ORDER BY ordinal_position"
        ).fetchall()
        table_cols = [row[0] for row in table_cols_result]
        insert_cols = [c for c in table_cols if c in df.columns]

        col_list    = ", ".join(insert_cols)
        select_list = ", ".join([f'df."{c}"' for c in insert_cols])

        # INSERT OR REPLACE: if event_uuid already exists, overwrite the row.
        # DuckDB uses INSERT OR REPLACE for upsert-by-primary-key.
        conn.execute(f"""
            INSERT OR REPLACE INTO raw_garmin_calendar_events
                ({col_list}, inserted_at, updated_at)
            SELECT
                {select_list},
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM df
        """)

        count = len(df)
        logger.success(f"✅ Upserted {count} calendar events into raw_garmin_calendar_events")
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
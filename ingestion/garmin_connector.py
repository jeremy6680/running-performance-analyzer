"""
Garmin Connect API Connector.

This module provides a robust interface to fetch data from Garmin Connect API,
including activities, daily health metrics, and sleep data.

Dependencies:
    - garminconnect: Python library for Garmin Connect API
    - pandas: Data manipulation
    - python-dotenv: Environment variable management

Usage:
    from ingestion.garmin_connector import GarminConnector
    
    connector = GarminConnector()
    activities = connector.fetch_activities(days=30)
    health = connector.fetch_daily_health(days=30)
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from garminconnect import Garmin, GarminConnectAuthenticationError, GarminConnectConnectionError
from loguru import logger

from ingestion.config import garmin_config
from ingestion.utils import (
    calculate_heart_rate_zone,
    calculate_pace,
    format_date,
    get_date_range,
    meters_to_kilometers,
    seconds_to_minutes,
)


class GarminConnector:
    """
    Connector for Garmin Connect API.
    
    Handles authentication, session management, and data fetching from Garmin Connect.
    Supports fetching activities, daily health metrics, and sleep data.
    
    Attributes:
        client: Garmin Connect API client
        email: Garmin account email
        save_session: Whether to save session for reuse
        session_file: Path to session file
    
    Example:
        >>> connector = GarminConnector()
        >>> connector.login()
        >>> activities = connector.fetch_activities(days=7)
        >>> print(f"Fetched {len(activities)} activities")
    """
    
    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        save_session: bool = True,
        session_file: Optional[Path] = None,
    ):
        """
        Initialize Garmin Connect connector.
        
        Args:
            email: Garmin account email (defaults to config)
            password: Garmin account password (defaults to config)
            save_session: Save session to file for reuse (default: True)
            session_file: Path to session file (defaults to config)
        """
        self.email = email or garmin_config.email
        self.password = password or garmin_config.password
        self.save_session = save_session
        self.session_file = session_file or garmin_config.session_file
        
        # Ensure session directory exists
        if self.save_session:
            self.session_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.client: Optional[Garmin] = None
        self._authenticated = False
        
        logger.info(f"Initialized GarminConnector for {self.email}")
    
    def login(self) -> bool:
        """
        Authenticate with Garmin Connect.
        
        Attempts to load a saved session first, falls back to login with credentials.
        
        Returns:
            True if authentication successful, False otherwise
        
        Raises:
            GarminConnectAuthenticationError: If login fails
        """
        try:
            # Try to load saved session
            if self.save_session and self.session_file.exists():
                logger.info("Attempting to load saved session...")
                self.client = Garmin()
                
                with open(self.session_file, "r") as f:
                    session_data = json.load(f)
                
                self.client.login(session_data)
                
                # Test if session is still valid
                try:
                    self.client.get_full_name()
                    logger.success("✅ Loaded session successfully")
                    self._authenticated = True
                    return True
                except Exception:
                    logger.warning("Saved session expired, logging in with credentials...")
            
            # Login with credentials
            logger.info("Logging in with credentials...")
            self.client = Garmin(self.email, self.password)
            self.client.login()
            
            # Save session if enabled
            if self.save_session:
                session_data = self.client.garth.dumps()
                with open(self.session_file, "w") as f:
                    json.dump(session_data, f)
                logger.info(f"Session saved to {self.session_file}")
            
            logger.success(f"✅ Logged in successfully as {self.client.get_full_name()}")
            self._authenticated = True
            return True
            
        except GarminConnectAuthenticationError as e:
            logger.error(f"❌ Authentication failed: {e}")
            logger.error("Please check your GARMIN_EMAIL and GARMIN_PASSWORD in .env")
            self._authenticated = False
            return False
        
        except Exception as e:
            logger.error(f"❌ Unexpected error during login: {e}")
            self._authenticated = False
            return False
    
    def _ensure_authenticated(self) -> None:
        """
        Ensure client is authenticated before API calls.
        
        Raises:
            RuntimeError: If not authenticated
        """
        if not self._authenticated or self.client is None:
            raise RuntimeError(
                "Not authenticated. Please call login() first."
            )
    
    def fetch_activities(
        self,
        days: int = 7,
        activity_type: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch activities from Garmin Connect.
        
        Args:
            days: Number of days to look back (default: 7)
            activity_type: Filter by activity type (e.g., 'running', 'cycling')
                          If None, fetch all activities
        
        Returns:
            DataFrame with activities data
        
        Raises:
            RuntimeError: If not authenticated
            GarminConnectConnectionError: If API request fails
        
        Example:
            >>> activities = connector.fetch_activities(days=30, activity_type='running')
            >>> print(activities[['activity_date', 'distance_km', 'duration_minutes']])
        """
        self._ensure_authenticated()
        
        start_date, end_date = get_date_range(days_back=days)
        
        logger.info(
            f"Fetching activities from {format_date(start_date)} to {format_date(end_date)}"
        )
        
        try:
            # Fetch activities from Garmin API
            # Format dates as YYYY-MM-DD strings
            start_date_str = format_date(start_date)
            end_date_str = format_date(end_date)
            
            activities = self.client.get_activities_by_date(
                start_date_str,
                end_date_str,
            )
            
            if not activities:
                logger.warning(f"No activities found in the last {days} days")
                return pd.DataFrame()
            
            logger.info(f"Fetched {len(activities)} raw activities")
            
            # Transform to DataFrame
            df = self._transform_activities(activities)
            
            # Filter by activity type if specified
            if activity_type:
                df = df[df["activity_type"].str.lower() == activity_type.lower()]
                logger.info(f"Filtered to {len(df)} {activity_type} activities")
            
            logger.success(f"✅ Successfully processed {len(df)} activities")
            return df
            
        except GarminConnectConnectionError as e:
            logger.error(f"❌ Connection error: {e}")
            raise
        
        except Exception as e:
            logger.error(f"❌ Error fetching activities: {e}")
            raise
    
    def _transform_activities(self, raw_activities: List[Dict]) -> pd.DataFrame:
        """
        Transform raw Garmin activities into clean DataFrame.
        
        Args:
            raw_activities: List of activity dictionaries from Garmin API
        
        Returns:
            Cleaned and standardized DataFrame
        """
        transformed = []
        
        for activity in raw_activities:
            # Extract and transform key fields
            record = {
                # Identifiers
                "activity_id": str(activity.get("activityId")),
                "activity_name": activity.get("activityName"),
                
                # Date/Time
                "activity_date": pd.to_datetime(activity.get("startTimeLocal")),
                "start_time_local": pd.to_datetime(activity.get("startTimeLocal")),
                "start_time_gmt": pd.to_datetime(activity.get("startTimeGMT")),
                
                # Activity Type
                "activity_type": activity.get("activityType", {}).get("typeKey", "unknown"),
                
                # Distance & Duration
                "distance_m": activity.get("distance", 0),
                "distance_km": meters_to_kilometers(activity.get("distance", 0)),
                "duration_seconds": activity.get("duration", 0),
                "duration_minutes": seconds_to_minutes(activity.get("duration", 0)),
                "moving_duration_seconds": activity.get("movingDuration", 0),
                
                # Pace & Speed
                "avg_speed_mps": activity.get("averageSpeed"),
                "max_speed_mps": activity.get("maxSpeed"),
                
                # Heart Rate
                "avg_heart_rate": activity.get("averageHR"),
                "max_heart_rate": activity.get("maxHR"),
                
                # Elevation
                "elevation_gain_m": activity.get("elevationGain"),
                "elevation_loss_m": activity.get("elevationLoss"),
                "min_elevation_m": activity.get("minElevation"),
                "max_elevation_m": activity.get("maxElevation"),
                
                # Calories & Training
                "calories": activity.get("calories"),
                "avg_cadence": activity.get("averageRunningCadenceInStepsPerMinute"),
                "max_cadence": activity.get("maxRunningCadenceInStepsPerMinute"),
                
                # Other metrics
                "aerobic_training_effect": activity.get("aerobicTrainingEffect"),
                "anaerobic_training_effect": activity.get("anaerobicTrainingEffect"),
                
                # Metadata
                "device_name": activity.get("deviceName"),
                "location_name": activity.get("locationName"),
            }
            
            # Calculate pace (min/km) if distance > 0
            if record["distance_km"] > 0 and record["duration_minutes"] > 0:
                record["avg_pace_min_km"] = calculate_pace(
                    record["distance_km"],
                    record["duration_minutes"]
                )
            else:
                record["avg_pace_min_km"] = None
            
            transformed.append(record)
        
        df = pd.DataFrame(transformed)
        
        # Sort by date (most recent first)
        df = df.sort_values("activity_date", ascending=False)
        df = df.reset_index(drop=True)
        
        return df
    
    def fetch_daily_health(self, days: int = 7) -> pd.DataFrame:
        """
        Fetch daily health metrics from Garmin Connect.
        
        Includes: steps, heart rate, sleep, stress, body battery, etc.
        
        Args:
            days: Number of days to look back (default: 7)
        
        Returns:
            DataFrame with daily health metrics
        
        Example:
            >>> health = connector.fetch_daily_health(days=30)
            >>> print(health[['date', 'resting_heart_rate', 'steps', 'sleep_score']])
        """
        self._ensure_authenticated()
        
        start_date, end_date = get_date_range(days_back=days)
        
        logger.info(
            f"Fetching daily health from {format_date(start_date)} to {format_date(end_date)}"
        )
        
        health_records = []
        
        # Iterate through each day
        current_date = start_date
        while current_date <= end_date:
            date_str = format_date(current_date)
            
            try:
                # Fetch various health metrics for the day
                stats = self.client.get_stats(date_str)
                hrv = self.client.get_hrv_data(date_str)
                sleep_data = self.client.get_sleep_data(date_str)
                
                # Combine into single record
                record = {
                    "date": current_date,
                    
                    # Steps & Activity
                    "steps": stats.get("totalSteps"),
                    "distance_m": stats.get("totalDistanceMeters"),
                    "active_calories": stats.get("activeKilocalories"),
                    "bmr_calories": stats.get("bmrKilocalories"),
                    
                    # Heart Rate
                    "resting_heart_rate": stats.get("restingHeartRate"),
                    "min_heart_rate": stats.get("minHeartRate"),
                    "max_heart_rate": stats.get("maxHeartRate"),
                    
                    # HRV (Heart Rate Variability)
                    "hrv_avg": hrv.get("lastNightAvg") if hrv else None,
                    "hrv_status": hrv.get("status") if hrv else None,
                    
                    # Sleep
                    "sleep_seconds": sleep_data.get("dailySleepDTO", {}).get("sleepTimeSeconds") if sleep_data else None,
                    "deep_sleep_seconds": sleep_data.get("dailySleepDTO", {}).get("deepSleepSeconds") if sleep_data else None,
                    "light_sleep_seconds": sleep_data.get("dailySleepDTO", {}).get("lightSleepSeconds") if sleep_data else None,
                    "rem_sleep_seconds": sleep_data.get("dailySleepDTO", {}).get("remSleepSeconds") if sleep_data else None,
                    "awake_seconds": sleep_data.get("dailySleepDTO", {}).get("awakeSleepSeconds") if sleep_data else None,
                    
                    # Stress & Recovery
                    "stress_avg": stats.get("averageStressLevel"),
                    "body_battery_charged": stats.get("bodyBatteryChargedValue"),
                    "body_battery_drained": stats.get("bodyBatteryDrainedValue"),
                    "body_battery_high": stats.get("bodyBatteryHighestValue"),
                    "body_battery_low": stats.get("bodyBatteryLowestValue"),
                    
                    # Respiration
                    "avg_waking_respiration_rate": stats.get("avgWakingRespirationValue"),
                    "avg_sleep_respiration_rate": stats.get("avgSleepRespirationValue"),
                }
                
                health_records.append(record)
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"Could not fetch health data for {date_str}: {e}")
            
            current_date += timedelta(days=1)
        
        df = pd.DataFrame(health_records)
        
        if df.empty:
            logger.warning(f"No health data found in the last {days} days")
            return df
        
        # Sort by date (most recent first)
        df = df.sort_values("date", ascending=False)
        df = df.reset_index(drop=True)
        
        logger.success(f"✅ Successfully fetched health data for {len(df)} days")
        return df
    
    def get_user_profile(self) -> Dict:
        """
        Fetch user profile information from Garmin Connect.
        
        Returns:
            Dictionary with user profile data
        
        Example:
            >>> profile = connector.get_user_profile()
            >>> print(f"Name: {profile['full_name']}")
        """
        self._ensure_authenticated()
        
        try:
            profile = {
                "full_name": self.client.get_full_name(),
                "display_name": self.client.display_name,
                "email": self.email,
            }
            
            logger.success(f"✅ Fetched profile for {profile['full_name']}")
            return profile
            
        except Exception as e:
            logger.error(f"❌ Error fetching user profile: {e}")
            raise


if __name__ == "__main__":
    # Test the connector
    print("=" * 60)
    print("Garmin Connector Test")
    print("=" * 60)
    
    # Initialize connector
    connector = GarminConnector()
    
    # Login
    if connector.login():
        print("\n🏃 Fetching activities (last 7 days)...")
        activities = connector.fetch_activities(days=7)
        
        if not activities.empty:
            print(f"\n✅ Found {len(activities)} activities:")
            print(activities[["activity_date", "activity_type", "distance_km", "duration_minutes", "avg_pace_min_km"]].head())
        
        print("\n❤️  Fetching daily health (last 7 days)...")
        health = connector.fetch_daily_health(days=7)
        
        if not health.empty:
            print(f"\n✅ Found health data for {len(health)} days:")
            print(health[["date", "steps", "resting_heart_rate", "sleep_seconds"]].head())
        
        print("\n👤 User Profile:")
        profile = connector.get_user_profile()
        print(f"  Name: {profile['full_name']}")
        print(f"  Email: {profile['email']}")
    
    print("\n" + "=" * 60)
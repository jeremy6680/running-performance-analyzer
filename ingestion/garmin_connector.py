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
    
    def _fetch_weather_for_activity(self, activity_id: str) -> Dict:
        """
        Fetch weather data for a single activity from Garmin Connect.

        Garmin stores weather conditions at the start of each GPS activity.
        Not all activities have weather data (e.g. treadmill runs).

        The Garmin weather API response shape (verified 2026-02-18):
        {
            "temp": 57,                          # Fahrenheit integer
            "apparentTemp": 57,                  # Fahrenheit integer
            "relativeHumidity": 44,              # percentage 0-100
            "windSpeed": 6,                      # km/h
            "weatherTypeDTO": {"desc": "Fair"},  # human-readable condition
        }

        Args:
            activity_id: Garmin activity ID (as string)

        Returns:
            Dictionary with normalised weather fields, all None if unavailable.
            Keys: weather_temp_c, weather_feels_like_c, weather_humidity_pct,
                  weather_wind_speed_ms, weather_condition, weather_precipitation_mm
        """
        # Default: all None (graceful fallback for activities without weather)
        empty = {
            "weather_temp_c": None,
            "weather_feels_like_c": None,
            "weather_humidity_pct": None,
            "weather_wind_speed_ms": None,
            "weather_condition": None,
            "weather_precipitation_mm": None,
        }

        try:
            raw = self.client.get_activity_weather(activity_id)

            # Garmin returns a list; take the first entry (start-of-activity snapshot)
            # Some activities return an empty list or None
            if not raw:
                return empty

            # Handle both list and dict responses
            weather = raw[0] if isinstance(raw, list) else raw

            def fahrenheit_to_celsius(f_val) -> Optional[float]:
                """
                Convert a Fahrenheit value to Celsius.
                Garmin's activity weather API always returns temperature in
                Fahrenheit regardless of the account's unit setting.
                Returns None if the value is None.
                """
                if f_val is None:
                    return None
                return round((float(f_val) - 32) / 1.8, 1)

            # Temperature: API uses "temp" and "apparentTemp" (both in Fahrenheit)
            temp_c       = fahrenheit_to_celsius(weather.get("temp"))
            feels_like_c = fahrenheit_to_celsius(weather.get("apparentTemp"))

            # Wind speed: Garmin returns km/h — convert to m/s for SI consistency
            wind_kmh = weather.get("windSpeed")
            wind_ms  = round(wind_kmh / 3.6, 2) if wind_kmh is not None else None

            # Weather condition: nested under weatherTypeDTO.desc
            # Fallback to top-level weatherType key for older API responses
            weather_type_dto = weather.get("weatherTypeDTO") or {}
            condition = (
                weather_type_dto.get("desc")
                or weather.get("weatherType")
                or weather.get("condition")
            )
            if condition:
                # Normalise to uppercase with underscores: "Partly Cloudy" → "PARTLY_CLOUDY"
                condition = str(condition).strip().upper().replace(" ", "_")

            return {
                "weather_temp_c":        temp_c,
                "weather_feels_like_c":  feels_like_c,
                "weather_humidity_pct":  weather.get("relativeHumidity"),
                "weather_wind_speed_ms": wind_ms,
                "weather_condition":     condition,
                "weather_precipitation_mm": weather.get("precipitation"),
            }

        except Exception as e:
            # Weather fetch is non-critical — log a warning but don't fail ingestion
            logger.warning(f"Could not fetch weather for activity {activity_id}: {e}")
            return empty

    def _transform_activities(self, raw_activities: List[Dict]) -> pd.DataFrame:
        """
        Transform raw Garmin activities into clean DataFrame.
        
        Args:
            raw_activities: List of activity dictionaries from Garmin API
        
        Returns:
            Cleaned and standardized DataFrame
        """
        transformed = []
        total = len(raw_activities)
        
        for idx, activity in enumerate(raw_activities, start=1):
            activity_id = str(activity.get("activityId"))
            logger.debug(f"Processing activity {idx}/{total}: {activity_id}")

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
                
                # Event Type — Garmin's "race" tag in Connect UI sets this field.
                # eventType.typeKey = 'race' when you tag an activity as a race.
                # Other values: 'training', 'recreation', 'transportation', etc.
                # This is separate from activityType (which is always 'running').
                "event_type": activity.get("eventType", {}).get("typeKey") if activity.get("eventType") else None,
                
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

            # Fetch weather for this activity.
            # One extra API call per activity — adds ~0.5s per activity.
            # Non-critical: failures are caught in _fetch_weather_for_activity
            # and return None values rather than breaking ingestion.
            logger.debug(f"Fetching weather for activity {idx}/{total}...")
            weather = self._fetch_weather_for_activity(activity_id)
            record.update(weather)

            # Small delay to avoid Garmin rate-limiting (especially for weather calls)
            time.sleep(0.3)

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
    
    def fetch_calendar_events(self, months_ahead: int = 6, months_back: int = 12) -> pd.DataFrame:
        """
        Fetch race events from the Garmin Connect calendar.

        The Garmin calendar stores upcoming races the user has registered for
        via the Garmin Connect app or website.  Each event has:
          - A title, date, and location
          - isRace: True for race events
          - completionTarget: distance in metres
          - itemType: 'event' for calendar events

        We fetch month-by-month because the calendar API works per-month,
        then filter to race events only (isRace=True).

        Args:
            months_ahead: How many future months to fetch (default: 6)
            months_back:  How many past months to fetch (default: 12)

        Returns:
            DataFrame of calendar race events.  One row per event.
            Columns: event_uuid, title, event_date, location, distance_m,
                     distance_km, race_distance_category, start_time,
                     timezone, is_race, subscribed, url

        Example:
            >>> events = connector.fetch_calendar_events(months_ahead=6)
            >>> print(events[['event_date', 'title', 'race_distance_category']])
        """
        self._ensure_authenticated()

        today = datetime.today()
        records = []
        seen_uuids: set = set()  # De-duplicate events that span month boundaries

        # Build list of (year, month) tuples to query
        # month offsets: -(months_back) … 0 … +(months_ahead)
        month_offsets = range(-months_back, months_ahead + 1)
        months_to_fetch = []
        for offset in month_offsets:
            # Add offset months to today's date
            m = today.month - 1 + offset          # 0-indexed month
            y = today.year + m // 12
            m = m % 12 + 1                        # back to 1-indexed
            months_to_fetch.append((y, m))

        logger.info(
            f"Fetching calendar events: {months_back} months back, "
            f"{months_ahead} months ahead ({len(months_to_fetch)} API calls)"
        )

        for year, month in months_to_fetch:
            try:
                # Garmin calendar REST endpoint.
                # garminconnect 0.2.x has no get_calendar() method — we call
                # the underlying connectapi() directly with the correct URL.
                # The endpoint returns a JSON object with a "calendarItems" list.
                url = f"/calendar-service/year/{year}/month/{month - 1}"  # month is 0-indexed
                raw = self.client.connectapi(url)
                items = raw.get("calendarItems", []) if raw else []

                # Log a summary of what the API returned for this month
                # so we can diagnose filter issues without spamming every item
                race_items = [i for i in items if i.get("isRace")]
                if race_items:
                    logger.info(
                        f"  {year}-{month:02d}: {len(items)} calendar items, "
                        f"{len(race_items)} with isRace=True — "
                        f"itemTypes: {list(set(i.get('itemType') for i in race_items))}"
                    )

                for item in items:
                    # Only process race events.
                    # We rely solely on isRace=True rather than also checking
                    # itemType == 'event', because Garmin returns different
                    # itemType values for race entries depending on the API
                    # version and event source ('event', 'race', 'workout', etc.).
                    # isRace is the authoritative flag.
                    if not item.get("isRace"):
                        continue

                    # De-duplicate: events registered in multiple months show up twice
                    uuid = item.get("shareableEventUuid") or item.get("id")
                    if uuid and uuid in seen_uuids:
                        continue
                    if uuid:
                        seen_uuids.add(uuid)

                    # --- Distance ---
                    # completionTarget holds distance in metres when unitType = 'distance'
                    target = item.get("completionTarget") or {}
                    distance_m = None
                    if target.get("unitType") == "distance" and target.get("unit") == "meter":
                        distance_m = target.get("value")
                    distance_km = round(distance_m / 1000, 3) if distance_m else None

                    # --- Race distance category ---
                    # Same tolerances used in stg_garmin_activities for consistency
                    def classify_distance(km):
                        if km is None:
                            return None
                        if 4.8 <= km <= 5.2:
                            return "5K"
                        if 9.8 <= km <= 10.3:
                            return "10K"
                        if 20.9 <= km <= 21.4:
                            return "Half Marathon"
                        if 41.9 <= km <= 43.0:
                            return "Marathon"
                        if km > 43.0:
                            return "Ultra"
                        return None  # Non-standard distance (e.g. 15K, trail)

                    # --- Start time ---
                    event_time = item.get("eventTimeLocal") or {}
                    start_time_str = event_time.get("startTimeHhMm")   # e.g. '08:30'
                    timezone      = event_time.get("timeZoneId")       # e.g. 'Europe/Paris'

                    records.append({
                        "event_uuid":             uuid,
                        "title":                  item.get("title"),
                        "event_date":             pd.to_datetime(item.get("date")).date(),
                        "location":               item.get("location"),
                        "distance_m":             distance_m,
                        "distance_km":            distance_km,
                        "race_distance_category": classify_distance(distance_km),
                        "start_time":             start_time_str,
                        "timezone":               timezone,
                        "is_race":                True,
                        "subscribed":             item.get("subscribed", False),
                        "url":                    item.get("url"),
                    })

                # Polite delay between API calls
                time.sleep(0.2)

            except Exception as e:
                logger.warning(f"Could not fetch calendar for {year}-{month:02d}: {e}")
                continue

        if not records:
            logger.warning("No race events found in calendar")
            return pd.DataFrame()

        df = pd.DataFrame(records)

        # Sort by event date ascending (soonest first)
        df = df.sort_values("event_date").reset_index(drop=True)

        past  = df[pd.to_datetime(df["event_date"]) <  pd.Timestamp.today()]
        future = df[pd.to_datetime(df["event_date"]) >= pd.Timestamp.today()]

        logger.success(
            f"✅ Fetched {len(df)} calendar race events "
            f"({len(past)} past, {len(future)} upcoming)"
        )
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
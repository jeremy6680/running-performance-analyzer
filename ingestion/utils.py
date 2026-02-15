"""
Utility functions for data ingestion.

This module provides helper functions for date handling, data transformation,
pace calculations, and other common operations used across ingestion scripts.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import pandas as pd
import pytz


def parse_date(date_str: str, date_format: str = "%Y-%m-%d") -> datetime:
    """
    Parse a date string into a datetime object.
    
    Args:
        date_str: Date string to parse
        date_format: Expected date format (default: YYYY-MM-DD)
    
    Returns:
        Parsed datetime object
    
    Raises:
        ValueError: If date string cannot be parsed
    
    Example:
        >>> parse_date("2025-02-14")
        datetime.datetime(2025, 2, 14, 0, 0)
    """
    try:
        return datetime.strptime(date_str, date_format)
    except ValueError as e:
        raise ValueError(f"Invalid date format: {date_str}. Expected format: {date_format}") from e


def format_date(date: datetime, date_format: str = "%Y-%m-%d") -> str:
    """
    Format a datetime object into a string.
    
    Args:
        date: Datetime object to format
        date_format: Desired output format (default: YYYY-MM-DD)
    
    Returns:
        Formatted date string
    
    Example:
        >>> format_date(datetime(2025, 2, 14))
        '2025-02-14'
    """
    return date.strftime(date_format)


def get_date_range(days_back: int = 7, end_date: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """
    Calculate a date range from a number of days back.
    
    Args:
        days_back: Number of days to look back (default: 7)
        end_date: End date (default: today)
    
    Returns:
        Tuple of (start_date, end_date)
    
    Example:
        >>> start, end = get_date_range(days_back=30)
        >>> # Returns dates for the last 30 days
    """
    if end_date is None:
        end_date = datetime.now()
    
    start_date = end_date - timedelta(days=days_back)
    return start_date, end_date


def convert_timezone(
    dt: datetime, 
    from_tz: str = "UTC", 
    to_tz: str = "Europe/Paris"
) -> datetime:
    """
    Convert datetime from one timezone to another.
    
    Args:
        dt: Datetime object to convert
        from_tz: Source timezone (default: UTC)
        to_tz: Target timezone (default: Europe/Paris)
    
    Returns:
        Datetime in target timezone
    
    Example:
        >>> utc_time = datetime(2025, 2, 14, 12, 0, 0)
        >>> paris_time = convert_timezone(utc_time, "UTC", "Europe/Paris")
    """
    if dt.tzinfo is None:
        # Naive datetime - assume it's in from_tz
        dt = pytz.timezone(from_tz).localize(dt)
    
    return dt.astimezone(pytz.timezone(to_tz))


def meters_to_kilometers(meters: Union[int, float]) -> float:
    """
    Convert meters to kilometers.
    
    Args:
        meters: Distance in meters
    
    Returns:
        Distance in kilometers (rounded to 2 decimals)
    
    Example:
        >>> meters_to_kilometers(5000)
        5.0
    """
    return round(meters / 1000, 2)


def seconds_to_minutes(seconds: Union[int, float]) -> float:
    """
    Convert seconds to minutes.
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Duration in minutes (rounded to 2 decimals)
    
    Example:
        >>> seconds_to_minutes(3600)
        60.0
    """
    return round(seconds / 60, 2)


def calculate_pace(distance_km: float, duration_minutes: float) -> Optional[float]:
    """
    Calculate pace in minutes per kilometer.
    
    Args:
        distance_km: Distance in kilometers
        duration_minutes: Duration in minutes
    
    Returns:
        Pace in min/km (rounded to 2 decimals), or None if distance is 0
    
    Example:
        >>> calculate_pace(5.0, 25.0)
        5.0  # 5:00 min/km
    """
    if distance_km == 0:
        return None
    
    return round(duration_minutes / distance_km, 2)


def format_pace(pace_min_km: float) -> str:
    """
    Format pace from decimal to MM:SS format.
    
    Args:
        pace_min_km: Pace in minutes per kilometer (decimal)
    
    Returns:
        Formatted pace string (MM:SS /km)
    
    Example:
        >>> format_pace(5.5)
        '5:30 /km'
    """
    minutes = int(pace_min_km)
    seconds = int((pace_min_km - minutes) * 60)
    return f"{minutes}:{seconds:02d} /km"


def calculate_heart_rate_zone(
    avg_hr: int, 
    max_hr: int, 
    zones: Optional[Dict[str, tuple]] = None
) -> str:
    """
    Determine heart rate zone based on percentage of max HR.
    
    Args:
        avg_hr: Average heart rate during activity
        max_hr: Maximum heart rate
        zones: Custom zone definitions (default: standard 5-zone model)
    
    Returns:
        Zone name (e.g., "Zone 2 - Aerobic")
    
    Example:
        >>> calculate_heart_rate_zone(140, 185)
        'Zone 2 - Aerobic'
    """
    if zones is None:
        # Standard 5-zone model
        zones = {
            "Zone 1 - Recovery": (0.50, 0.60),
            "Zone 2 - Aerobic": (0.60, 0.70),
            "Zone 3 - Tempo": (0.70, 0.80),
            "Zone 4 - Threshold": (0.80, 0.90),
            "Zone 5 - VO2max": (0.90, 1.00),
        }
    
    hr_percentage = avg_hr / max_hr
    
    for zone_name, (lower, upper) in zones.items():
        if lower <= hr_percentage < upper:
            return zone_name
    
    return "Unknown"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning a default value if denominator is zero.
    
    Args:
        numerator: Number to divide
        denominator: Number to divide by
        default: Value to return if denominator is 0 (default: 0.0)
    
    Returns:
        Result of division, or default if denominator is 0
    
    Example:
        >>> safe_divide(10, 2)
        5.0
        >>> safe_divide(10, 0)
        0.0
    """
    return numerator / denominator if denominator != 0 else default


def clean_activity_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and standardize activity data.
    
    Performs:
    - Remove duplicates
    - Handle missing values
    - Convert data types
    - Sort by date
    
    Args:
        df: Raw activity DataFrame
    
    Returns:
        Cleaned DataFrame
    """
    # Make a copy to avoid modifying original
    df = df.copy()
    
    # Remove duplicates based on activity_id
    if "activity_id" in df.columns:
        df = df.drop_duplicates(subset=["activity_id"], keep="last")
    
    # Convert date columns to datetime
    date_columns = ["activity_date", "start_time", "end_time"]
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    
    # Sort by date (most recent first)
    if "activity_date" in df.columns:
        df = df.sort_values("activity_date", ascending=False)
    
    # Reset index
    df = df.reset_index(drop=True)
    
    return df


def flatten_dict(data: Dict, parent_key: str = "", sep: str = "_") -> Dict:
    """
    Flatten a nested dictionary.
    
    Args:
        data: Dictionary to flatten
        parent_key: Key prefix for nested items
        sep: Separator between keys (default: _)
    
    Returns:
        Flattened dictionary
    
    Example:
        >>> flatten_dict({"user": {"name": "John", "age": 30}})
        {'user_name': 'John', 'user_age': 30}
    """
    items = []
    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        
        if isinstance(value, dict):
            items.extend(flatten_dict(value, new_key, sep=sep).items())
        else:
            items.append((new_key, value))
    
    return dict(items)


def batch_list(items: List, batch_size: int = 100) -> List[List]:
    """
    Split a list into batches of specified size.
    
    Args:
        items: List to split
        batch_size: Maximum size of each batch (default: 100)
    
    Returns:
        List of batches
    
    Example:
        >>> batch_list([1, 2, 3, 4, 5], batch_size=2)
        [[1, 2], [3, 4], [5]]
    """
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]


if __name__ == "__main__":
    # Test utility functions
    print("=" * 60)
    print("Utility Functions Test")
    print("=" * 60)
    
    # Date functions
    print("\n📅 Date Functions:")
    date = parse_date("2025-02-14")
    print(f"  Parsed date: {date}")
    print(f"  Formatted: {format_date(date)}")
    
    start, end = get_date_range(days_back=7)
    print(f"  Last 7 days: {format_date(start)} to {format_date(end)}")
    
    # Conversion functions
    print("\n🔢 Conversion Functions:")
    print(f"  5000m = {meters_to_kilometers(5000)} km")
    print(f"  3600s = {seconds_to_minutes(3600)} min")
    
    # Pace calculation
    print("\n⏱️  Pace Calculation:")
    pace = calculate_pace(10.0, 50.0)
    print(f"  10km in 50min = {pace} min/km ({format_pace(pace)})")
    
    # Heart rate zones
    print("\n❤️  Heart Rate Zones:")
    zone = calculate_heart_rate_zone(140, 185)
    print(f"  140 bpm (max 185) = {zone}")
    
    print("\n" + "=" * 60)

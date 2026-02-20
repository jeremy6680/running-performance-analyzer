"""
ai_engine/weather.py
---------------------
Weather data for the AI coaching context.

Two responsibilities:
1. Fetch 7-day weather forecast from Open-Meteo (free, no API key required)
   given a city name or lat/lon coordinates.
2. Compute a historical weather-pace correlation summary from DuckDB
   (how the athlete's pace varies with temperature, wind and precipitation).

The output of both functions is a plain string that gets injected into the
LLM prompt, so the coach can reference forecast conditions when planning
the week and historical pace adjustments when calibrating targets.

Design notes:
- Open-Meteo is called with a geocoding step (city name → lat/lon) then
  a forecast step (lat/lon → 7-day daily data). Both endpoints are free
  and require no authentication.
- All HTTP calls use a short timeout (10 s) with graceful fallback so the
  AI Coach page never crashes due to a weather API timeout.
- Historical correlation is computed from raw_garmin_activities which already
  stores weather_temp_c, weather_wind_speed_ms, etc. from ingestion time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import duckdb
import requests
from loguru import logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Open-Meteo endpoints (no API key needed)
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL  = "https://api.open-meteo.com/v1/forecast"

# HTTP timeout in seconds — short enough to not block the UI
REQUEST_TIMEOUT = 10

# WMO weather interpretation codes → human-readable labels
# Reference: https://open-meteo.com/en/docs#weathervariables
WMO_CONDITION_MAP = {
    0:  "Clear sky",
    1:  "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Light snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers", 81: "Moderate showers", 82: "Heavy showers",
    85: "Light snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DailyForecast:
    """Simplified daily weather forecast used in the LLM prompt."""
    day_name: str           # e.g. "Monday"
    date_str: str           # e.g. "2026-02-24"
    temp_min_c: float
    temp_max_c: float
    condition: str          # human-readable from WMO_CONDITION_MAP
    wind_kmh: float         # max daily wind speed
    precipitation_mm: float # total daily precipitation


@dataclass
class WeatherContext:
    """All weather info ready to be formatted into an LLM prompt string."""
    city_name: str
    forecast: list[DailyForecast]           # up to 7 days
    historical_summary: Optional[str]       # correlation text, or None if no data


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def geocode_city(city_name: str) -> Optional[tuple[float, float, str]]:
    """
    Convert a city name to (latitude, longitude, resolved_display_name).

    Uses the Open-Meteo geocoding API — free, no key required.
    Returns None if the city is not found or the request fails.

    Args:
        city_name: Free-text city name, e.g. "Nice, France" or "Paris".

    Returns:
        Tuple of (lat, lon, display_name) or None on failure.
    """
    try:
        response = requests.get(
            GEOCODING_URL,
            params={"name": city_name, "count": 1, "language": "en", "format": "json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("results"):
            logger.warning(f"Geocoding found no results for: {city_name!r}")
            return None

        result = data["results"][0]
        lat  = result["latitude"]
        lon  = result["longitude"]
        name = f"{result['name']}, {result.get('country', '')}"
        logger.info(f"Geocoded {city_name!r} → {name} ({lat}, {lon})")
        return lat, lon, name

    except Exception as e:
        logger.warning(f"Geocoding failed for {city_name!r}: {e}")
        return None


# ---------------------------------------------------------------------------
# Forecast fetching
# ---------------------------------------------------------------------------

def fetch_forecast(lat: float, lon: float) -> list[DailyForecast]:
    """
    Fetch a 7-day daily weather forecast from Open-Meteo.

    Requests daily aggregates (min/max temperature, precipitation sum,
    max wind speed, dominant weather code) which are compact and sufficient
    for a weekly training plan.

    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.

    Returns:
        List of DailyForecast objects. Empty list if the request fails.
    """
    try:
        response = requests.get(
            FORECAST_URL,
            params={
                "latitude":  lat,
                "longitude": lon,
                "daily": [
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "windspeed_10m_max",
                    "weathercode",
                ],
                "forecast_days": 7,
                "timezone": "auto",   # use the local timezone at the location
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()["daily"]

        from datetime import datetime

        forecasts = []
        for i, date_str in enumerate(data["time"]):
            wmo_code  = data["weathercode"][i]
            condition = WMO_CONDITION_MAP.get(wmo_code, f"Code {wmo_code}")
            day_name  = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")

            forecasts.append(DailyForecast(
                day_name         = day_name,
                date_str         = date_str,
                temp_min_c       = round(data["temperature_2m_min"][i] or 0, 1),
                temp_max_c       = round(data["temperature_2m_max"][i] or 0, 1),
                condition        = condition,
                wind_kmh         = round(data["windspeed_10m_max"][i] or 0, 1),
                precipitation_mm = round(data["precipitation_sum"][i] or 0, 1),
            ))

        logger.info(f"Fetched {len(forecasts)}-day forecast for ({lat:.3f}, {lon:.3f})")
        return forecasts

    except Exception as e:
        logger.warning(f"Forecast fetch failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Historical weather-pace correlation
# ---------------------------------------------------------------------------

def compute_historical_weather_summary(db_path: Path) -> Optional[str]:
    """
    Analyse the athlete's past activities to summarise how weather conditions
    affect their running pace.

    Queries raw_garmin_activities (bronze layer) directly because weather
    columns live there and are not propagated to the gold marts.

    Returns a compact, human-readable string for the LLM prompt, or None
    if there are fewer than 5 activities with weather data.

    Args:
        db_path: Path to the DuckDB database file.

    Returns:
        Multi-line text string, or None if data is insufficient.
    """
    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            df = conn.execute("""
                SELECT
                    ROUND(duration_minutes / distance_km, 2)   AS pace_min_per_km,
                    weather_temp_c,
                    weather_wind_speed_ms * 3.6                AS wind_kmh,
                    weather_precipitation_mm,
                    weather_condition
                FROM raw_garmin_activities
                WHERE distance_km        > 1.0
                  AND duration_minutes   > 5
                  AND distance_km        IS NOT NULL
                  AND weather_temp_c     IS NOT NULL
                  -- Keep only realistic running paces (2:30 to 20:00 min/km)
                  AND (duration_minutes / distance_km) BETWEEN 2.5 AND 20.0
                  AND activity_type ILIKE '%run%'
                ORDER BY activity_date DESC
                LIMIT 200
            """).df()

        if len(df) < 5:
            logger.info("Not enough weather-tagged activities for correlation (<5)")
            return None

        lines = [f"Historical weather impact (based on {len(df)} runs with weather data):"]

        # --- Temperature buckets ---
        temp_buckets = [
            ("Cold (< 5°C)",     df["weather_temp_c"] < 5),
            ("Cool (5–15°C)",   (df["weather_temp_c"] >= 5)  & (df["weather_temp_c"] < 15)),
            ("Mild (15–22°C)",  (df["weather_temp_c"] >= 15) & (df["weather_temp_c"] < 22)),
            ("Warm (> 22°C)",    df["weather_temp_c"] >= 22),
        ]
        temp_lines = []
        for label, mask in temp_buckets:
            subset = df[mask]
            if len(subset) >= 3:
                avg_pace = subset["pace_min_per_km"].mean()
                temp_lines.append(
                    f"  {label}: avg pace {_fmt_pace(avg_pace)}/km ({len(subset)} runs)"
                )
        if temp_lines:
            lines.append("Temperature vs pace:")
            lines.extend(temp_lines)

        # --- Wind impact ---
        calm  = df[df["wind_kmh"] < 15]["pace_min_per_km"]
        windy = df[df["wind_kmh"] >= 25]["pace_min_per_km"]
        if len(calm) >= 3 and len(windy) >= 3:
            diff_sec = (windy.mean() - calm.mean()) * 60
            direction = "slower" if diff_sec > 0 else "faster"
            lines.append(
                f"Wind impact: pace is {abs(diff_sec):.0f}s/km {direction} in strong "
                f"wind (>25 km/h) vs calm conditions (<15 km/h)"
            )

        # --- Rain impact ---
        dry   = df[df["weather_precipitation_mm"] < 0.5]["pace_min_per_km"]
        rainy = df[df["weather_precipitation_mm"] >= 2.0]["pace_min_per_km"]
        if len(dry) >= 3 and len(rainy) >= 3:
            diff_sec  = (rainy.mean() - dry.mean()) * 60
            direction = "slower" if diff_sec > 0 else "faster"
            lines.append(
                f"Rain impact: pace is {abs(diff_sec):.0f}s/km {direction} in rainy "
                f"conditions (≥2mm) vs dry runs"
            )

        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"Historical weather correlation failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def get_weather_context(city_name: str, db_path: Path) -> WeatherContext:
    """
    Build a complete WeatherContext for a given city.

    Combines geocoding, 7-day forecast, and historical weather-pace correlation.
    On any failure (network, geocoding), returns a WeatherContext with an
    empty forecast so the caller can gracefully skip weather in the prompt.

    Args:
        city_name: City to get forecast for, e.g. "Nice, France".
        db_path:   Path to the DuckDB database file.

    Returns:
        WeatherContext with forecast and optional historical summary.
    """
    # Step 1: convert city name to coordinates
    geo = geocode_city(city_name)
    if geo is None:
        return WeatherContext(city_name=city_name, forecast=[], historical_summary=None)

    lat, lon, resolved_name = geo

    # Step 2: fetch 7-day forecast
    forecast = fetch_forecast(lat, lon)

    # Step 3: historical correlation (independent — uses DuckDB, not the API)
    historical_summary = compute_historical_weather_summary(db_path)

    return WeatherContext(
        city_name          = resolved_name,
        forecast           = forecast,
        historical_summary = historical_summary,
    )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_weather_for_prompt(ctx: WeatherContext) -> str:
    """
    Convert a WeatherContext into a compact string for the LLM prompt.

    One line per forecast day, flags notable conditions (rain, strong wind,
    extreme temperature). Appends the historical correlation block below.

    Args:
        ctx: WeatherContext returned by get_weather_context().

    Returns:
        Multi-line string ready to inject into the prompt, or empty string
        if no forecast is available.
    """
    if not ctx.forecast:
        return ""

    lines = [f"WEATHER FORECAST — {ctx.city_name} (next 7 days)"]

    for day in ctx.forecast:
        # Flag conditions that meaningfully affect running performance
        flags = []
        if day.precipitation_mm >= 5:
            flags.append(f"rain {day.precipitation_mm}mm")
        elif day.precipitation_mm >= 1:
            flags.append(f"light rain {day.precipitation_mm}mm")
        if day.wind_kmh >= 30:
            flags.append(f"strong wind {day.wind_kmh}km/h")
        elif day.wind_kmh >= 20:
            flags.append(f"wind {day.wind_kmh}km/h")
        if day.temp_max_c >= 28:
            flags.append("⚠️ heat")
        elif day.temp_min_c <= 0:
            flags.append("⚠️ frost")

        flag_str = f" [{', '.join(flags)}]" if flags else ""
        lines.append(
            f"- {day.day_name} ({day.date_str}): "
            f"{day.temp_min_c}–{day.temp_max_c}°C, {day.condition}{flag_str}"
        )

    if ctx.historical_summary:
        lines.append("")
        lines.append(ctx.historical_summary)

    return "\n".join(lines)


def _fmt_pace(pace_min_per_km: float) -> str:
    """Format a decimal pace (e.g. 5.5) as M:SS string (e.g. '5:30')."""
    mins = int(pace_min_per_km)
    secs = int(round((pace_min_per_km - mins) * 60))
    return f"{mins}:{secs:02d}"

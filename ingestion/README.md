# Ingestion Module

This module handles data ingestion from various running/fitness APIs (Garmin Connect, Strava, etc.).

## 📁 Files

| File | Description |
|------|-------------|
| `config.py` | Configuration management (environment variables, settings) |
| `utils.py` | Utility functions (date handling, conversions, calculations) |
| `garmin_connector.py` | Garmin Connect API connector (main class) |
| `strava_connector.py` | Strava API connector (optional, future) |
| `test_connector.py` | Simple test script for Garmin connector |

## 🚀 Quick Start

### 1. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Garmin Connect credentials
GARMIN_EMAIL=your_email@example.com
GARMIN_PASSWORD=your_password

# Database
DUCKDB_PATH=data/duckdb/running_analytics.duckdb
```

### 2. Test the Connector

```bash
# Test with default (7 days)
python -m ingestion.test_connector

# Test with custom days
python -m ingestion.test_connector --days 30
```

### 3. Use in Your Code

```python
from ingestion.garmin_connector import GarminConnector

# Initialize and login
connector = GarminConnector()
connector.login()

# Fetch activities
activities = connector.fetch_activities(days=30)
print(f"Found {len(activities)} activities")

# Fetch daily health metrics
health = connector.fetch_daily_health(days=30)
print(f"Found health data for {len(health)} days")
```

## 📊 Data Schemas

### Activities DataFrame

Columns returned by `fetch_activities()`:

| Column | Type | Description |
|--------|------|-------------|
| `activity_id` | str | Unique activity identifier |
| `activity_name` | str | Name of the activity |
| `activity_date` | datetime | Date/time of the activity |
| `activity_type` | str | Type (running, cycling, etc.) |
| `distance_km` | float | Distance in kilometers |
| `duration_minutes` | float | Duration in minutes |
| `avg_pace_min_km` | float | Average pace (min/km) |
| `avg_heart_rate` | int | Average heart rate (bpm) |
| `max_heart_rate` | int | Maximum heart rate (bpm) |
| `elevation_gain_m` | float | Elevation gain in meters |
| `calories` | int | Calories burned |
| `avg_cadence` | int | Average cadence (steps/min) |

### Daily Health DataFrame

Columns returned by `fetch_daily_health()`:

| Column | Type | Description |
|--------|------|-------------|
| `date` | datetime | Date of the health data |
| `steps` | int | Total steps for the day |
| `resting_heart_rate` | int | Resting heart rate (bpm) |
| `hrv_avg` | float | Heart rate variability (ms) |
| `sleep_seconds` | int | Total sleep duration (seconds) |
| `deep_sleep_seconds` | int | Deep sleep duration (seconds) |
| `stress_avg` | int | Average stress level (0-100) |
| `body_battery_charged` | int | Body battery charged value |
| `active_calories` | int | Active calories burned |

## 🔧 Configuration

### GarminConfig

Environment variables for Garmin connector:

```python
GARMIN_EMAIL          # Required: Your Garmin account email
GARMIN_PASSWORD       # Required: Your Garmin account password
GARMIN_SAVE_SESSION   # Optional: Save session for reuse (default: true)
GARMIN_SESSION_FILE   # Optional: Path to session file
```

### AppConfig

General application settings:

```python
ENVIRONMENT           # Environment (development/production)
DEBUG                 # Enable debug logging
TIMEZONE             # Timezone for date conversion
INITIAL_SYNC_DAYS    # Days to fetch on initial sync (default: 365)
DAILY_SYNC_DAYS      # Days to look back on daily sync (default: 7)
```

## 🧪 Testing

### Test Configuration

```bash
python ingestion/config.py
```

Expected output:
```
====================================================================
Configuration Test
====================================================================

📧 Garmin Config:
  Email: your_email@example.com
  Password: **************
  Save session: True
  ...

✅ Configuration validated successfully
====================================================================
```

### Test Utilities

```bash
python ingestion/utils.py
```

Expected output:
```
====================================================================
Utility Functions Test
====================================================================

📅 Date Functions:
  Parsed date: 2025-02-14 00:00:00
  Formatted: 2025-02-14
  Last 7 days: 2025-02-07 to 2025-02-14

🔢 Conversion Functions:
  5000m = 5.0 km
  3600s = 60.0 min
  ...
====================================================================
```

### Test Garmin Connector

```bash
python ingestion/garmin_connector.py
```

Expected output:
```
====================================================================
Garmin Connector Test
====================================================================

✅ Logged in successfully as Your Name

🏃 Fetching activities (last 7 days)...
✅ Found 5 activities

❤️  Fetching daily health (last 7 days)...
✅ Found health data for 7 days
...
====================================================================
```

## 🔐 Security Best Practices

1. **Never commit `.env` file** - Contains credentials
2. **Use session file** - Avoids repeated logins (rate limiting)
3. **Session file is gitignored** - `data/garmin_session.json` not tracked
4. **Validate config** - Run `config.validate_config()` before use

## 🐛 Troubleshooting

### Authentication Failed

```
❌ Authentication failed: Invalid credentials
```

**Solution:**
- Check `GARMIN_EMAIL` and `GARMIN_PASSWORD` in `.env`
- Verify credentials by logging in at https://connect.garmin.com
- Ensure no typos or extra spaces in `.env`

### Connection Timeout

```
❌ Connection error: Timeout
```

**Solution:**
- Check internet connection
- Garmin servers may be down - try again later
- Add delay between requests: `time.sleep(1)`

### Rate Limiting

```
❌ Too many requests
```

**Solution:**
- Enable session saving: `GARMIN_SAVE_SESSION=true`
- Add delays between API calls
- Reduce number of days fetched

### No Data Returned

```
⚠️  No activities found in the last 7 days
```

**Solution:**
- Normal if you haven't recorded activities recently
- Increase `days` parameter: `fetch_activities(days=30)`
- Check Garmin Connect website to verify activities exist

## 📝 Logging

This module uses `loguru` for logging. Configure log level:

```python
from loguru import logger

# Debug level
logger.remove()
logger.add(sys.stderr, level="DEBUG")

# Info level (default)
logger.remove()
logger.add(sys.stderr, level="INFO")
```

## 🔄 Future Enhancements

- [ ] Strava API integration
- [ ] Apple Health data import
- [ ] Retry logic with exponential backoff
- [ ] Parallel fetching for multiple days
- [ ] Caching layer for API responses
- [ ] Data validation with Pydantic models

## 📚 References

- [Garmin Connect Python Library](https://github.com/cyberjunky/python-garminconnect)
- [Garmin Connect API Documentation](https://connect.garmin.com/modern/developer)
- [Pandas Documentation](https://pandas.pydata.org/docs/)

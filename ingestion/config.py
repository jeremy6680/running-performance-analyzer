"""
Configuration module for data ingestion.

This module handles loading environment variables and configuration settings
for API connections (Garmin, Strava, etc.) and database connections.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# Load environment variables from .env file
# Look for .env in project root (parent of ingestion folder)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class GarminConfig(BaseSettings):
    """Configuration for Garmin Connect API."""
    
    email: str = Field(..., validation_alias="GARMIN_EMAIL")
    password: str = Field(..., validation_alias="GARMIN_PASSWORD")
    save_session: bool = Field(
        default=True, 
        validation_alias="GARMIN_SAVE_SESSION"
    )
    session_file: Path = Field(
        default=Path("data/garmin_session.json"),
        validation_alias="GARMIN_SESSION_FILE"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class StravaConfig(BaseSettings):
    """Configuration for Strava API (optional)."""
    
    client_id: Optional[str] = Field(default=None, validation_alias="STRAVA_CLIENT_ID")
    client_secret: Optional[str] = Field(default=None, validation_alias="STRAVA_CLIENT_SECRET")
    refresh_token: Optional[str] = Field(default=None, validation_alias="STRAVA_REFRESH_TOKEN")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class DatabaseConfig(BaseSettings):
    """Configuration for DuckDB database."""
    
    path: Path = Field(
        default=Path("data/duckdb/running_analytics.duckdb"),
        validation_alias="DUCKDB_PATH"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
    
    def ensure_directory(self) -> None:
        """Create database directory if it doesn't exist."""
        self.path.parent.mkdir(parents=True, exist_ok=True)


class AppConfig(BaseSettings):
    """General application configuration."""
    
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    debug: bool = Field(default=True, validation_alias="DEBUG")
    timezone: str = Field(default="Europe/Paris", validation_alias="TIMEZONE")
    
    # Data sync settings
    initial_sync_days: int = Field(
        default=365, 
        validation_alias="INITIAL_SYNC_DAYS"
    )
    daily_sync_days: int = Field(
        default=7, 
        validation_alias="DAILY_SYNC_DAYS"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# ---------------------------------------------------------------------------
# Singleton instances
# ---------------------------------------------------------------------------
# GarminConfig and StravaConfig are instantiated lazily via module-level
# getters below. This avoids a Pydantic ValidationError on Streamlit Cloud
# (and any environment without GARMIN_EMAIL / GARMIN_PASSWORD) when other
# modules import only database_config or app_config.
#
# DatabaseConfig and AppConfig have no required fields so they are safe
# to instantiate eagerly.

database_config = DatabaseConfig()
app_config = AppConfig()

_garmin_config: Optional[GarminConfig] = None
_strava_config: Optional[StravaConfig] = None


def get_garmin_config() -> GarminConfig:
    """
    Return the GarminConfig singleton, instantiating it on first call.

    Raises:
        pydantic_core.ValidationError: if GARMIN_EMAIL or GARMIN_PASSWORD
            are not set in the environment.
    """
    global _garmin_config
    if _garmin_config is None:
        _garmin_config = GarminConfig()
    return _garmin_config


def get_strava_config() -> StravaConfig:
    """Return the StravaConfig singleton, instantiating it on first call."""
    global _strava_config
    if _strava_config is None:
        _strava_config = StravaConfig()
    return _strava_config


# Legacy aliases — kept for backwards compatibility with existing code that
# does `from ingestion.config import garmin_config`. They are now properties
# of a small proxy object so the ValidationError is deferred until access.
class _LazyConfig:
    """Proxy that instantiates GarminConfig / StravaConfig on first attribute access."""

    @property
    def garmin(self) -> GarminConfig:
        return get_garmin_config()

    @property
    def strava(self) -> StravaConfig:
        return get_strava_config()


# Direct module-level names for callers that do:
#   from ingestion.config import garmin_config
# The object is now a lazy wrapper — attribute access triggers instantiation.
garmin_config = _LazyConfig().garmin if False else type(
    "_LazyGarmin", (),
    {
        "__getattr__": lambda self, name: getattr(get_garmin_config(), name),
        "__repr__": lambda self: repr(get_garmin_config()),
    }
)()

strava_config = type(
    "_LazyStrava", (),
    {
        "__getattr__": lambda self, name: getattr(get_strava_config(), name),
        "__repr__": lambda self: repr(get_strava_config()),
    }
)()


def validate_config() -> bool:
    """
    Validate that all required configuration is present.
    
    Returns:
        True if configuration is valid, False otherwise
    """
    required_vars = {
        "GARMIN_EMAIL": garmin_config.email,
        "GARMIN_PASSWORD": garmin_config.password,
        "DUCKDB_PATH": str(database_config.path),
    }
    
    missing_vars = [key for key, value in required_vars.items() if not value]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("💡 Please check your .env file and ensure all required variables are set.")
        return False
    
    print("✅ Configuration validated successfully")
    return True


if __name__ == "__main__":
    # Test configuration loading
    print("=" * 60)
    print("Configuration Test")
    print("=" * 60)
    
    print("\n📧 Garmin Config:")
    print(f"  Email: {garmin_config.email}")
    print(f"  Password: {'*' * len(garmin_config.password) if garmin_config.password else 'NOT SET'}")
    print(f"  Save session: {garmin_config.save_session}")
    print(f"  Session file: {garmin_config.session_file}")
    
    print("\n💾 Database Config:")
    print(f"  Path: {database_config.path}")
    
    print("\n⚙️  App Config:")
    print(f"  Environment: {app_config.environment}")
    print(f"  Debug: {app_config.debug}")
    print(f"  Timezone: {app_config.timezone}")
    print(f"  Initial sync days: {app_config.initial_sync_days}")
    print(f"  Daily sync days: {app_config.daily_sync_days}")
    
    print("\n" + "=" * 60)
    validate_config()
    print("=" * 60)

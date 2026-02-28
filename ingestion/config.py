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


# Singleton instances for easy import
garmin_config = GarminConfig()
strava_config = StravaConfig()
database_config = DatabaseConfig()
app_config = AppConfig()


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

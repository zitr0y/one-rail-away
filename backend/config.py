"""
Configuration module for the train network visualization system.
Loads configuration from environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # Deutsche Bahn API Configuration
    DB_API_KEY: str = os.getenv("DB_API_KEY", "")
    DB_CLIENT_ID: str = os.getenv("DB_CLIENT_ID", "")
    DB_API_BASE_URL: str = os.getenv(
        "DB_API_BASE_URL",
        "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1",
    )

    # Data directory configuration
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", "./data"))

    @classmethod
    def validate(cls) -> None:
        """Validate that required configuration values are present."""
        # Note: DB_API_KEY is no longer required since we use bahnhof.de API
        # which doesn't require authentication

        # Ensure data directory exists
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)


# Create a singleton instance
config = Config()

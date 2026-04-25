"""
Centralized environment configuration loader.
Fails fast if required variables are missing.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ConfigError(Exception):
    """Raised when a required config variable is missing."""
    pass


def get_required_env(var_name: str) -> str:
    """
    Get a required environment variable.
    Raises ConfigError if not set.
    """
    value = os.getenv(var_name)
    if not value:
        raise ConfigError(f"Required environment variable missing: {var_name}")
    return value


def get_optional_env(var_name: str, default: str = None) -> str:
    """
    Get an optional environment variable with a default fallback.
    """
    return os.getenv(var_name, default)


# Required configuration variables
SUPABASE_URL = get_required_env("SUPABASE_URL")
SUPABASE_SERVICE_KEY = get_required_env("SUPABASE_SERVICE_KEY")

# Optional configuration variables
PORT = int(get_optional_env("PORT", "8010"))
ENVIRONMENT = get_optional_env("ENVIRONMENT", "development")


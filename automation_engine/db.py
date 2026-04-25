"""
Supabase database client factory.
Provides access to Supabase database for the automation engine.
"""

from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY


def get_supabase() -> Client:
    """
    Create and return a Supabase client using the service key.
    The service key allows full access to the database (used for backend operations).

    Returns:
        Client: Supabase client authenticated with the service key.

    Raises:
        ConfigError: If SUPABASE_URL or SUPABASE_SERVICE_KEY are not set.
    """
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    # Configure postgrest to use automation schema
    client.postgrest.session.headers['Accept-Profile'] = 'automation'
    client.postgrest.session.headers['Content-Profile'] = 'automation'
    return client

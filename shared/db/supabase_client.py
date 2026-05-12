"""
Shared Supabase Client.

Singleton client for Supabase database access.
Used for farmer registration and conversation logging.

Usage:
    from shared.db.supabase_client import get_supabase
    
    client = get_supabase()
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import supabase
try:
    from supabase import create_client, Client
except ImportError:
    Client = None
    create_client = None


class SupabaseClient:
    """Singleton Supabase client."""
    
    _instance: Optional[Client] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self) -> bool:
        """Initialize the Supabase client."""
        global Client
        
        if Client is None:
            logger.warning("supabase package not installed")
            return False
        
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            logger.warning("SUPABASE_URL or SUPABASE_KEY not set")
            return False
        
        try:
            self._instance = create_client(url, key)
            logger.info("Supabase client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            return False
    
    def get_client(self) -> Optional[Client]:
        """Get the Supabase client instance."""
        if self._instance is None:
            self.initialize()
        return self._instance
    
    def is_available(self) -> bool:
        """Check if Supabase client is available."""
        return self._instance is not None


def get_supabase() -> Optional[Client]:
    """Get the singleton Supabase client.
    
    Returns:
        Supabase client instance or None
    """
    client = SupabaseClient()
    return client.get_client()


def init_supabase() -> bool:
    """Initialize the Supabase client.
    
    Returns:
        Success status
    """
    client = SupabaseClient()
    return client.initialize()
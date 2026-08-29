"""
supabase_client.py — Supabase client initialization for ChimneyCare.

Provides two client factories:
  • get_supabase_client()  — uses the anon key + user's session JWT (respects RLS)
  • get_admin_client()     — uses the service_role key (bypasses RLS, admin-only ops)
"""

import os
from flask import session
from supabase import create_client, Client
from supabase.client import ClientOptions
from supabase_auth import SyncSupportedStorage
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


class FlaskSessionStorage(SyncSupportedStorage):
    """Persist Supabase auth tokens inside the Flask session cookie."""

    def get_item(self, key: str) -> str | None:
        try:
            return session.get(key)
        except Exception:
            return None

    def set_item(self, key: str, value: str) -> None:
        try:
            session[key] = value
        except Exception:
            pass

    def remove_item(self, key: str) -> None:
        try:
            session.pop(key, None)
        except Exception:
            pass


def get_supabase_client() -> Client:
    """
    Return a Supabase client that carries the logged-in user's JWT.
    All queries go through RLS — the database enforces row-level access.
    """
    options = ClientOptions(storage=FlaskSessionStorage())
    return create_client(
        SUPABASE_URL,
        SUPABASE_ANON_KEY,
        options=options,
    )


def get_admin_client() -> Client:
    """
    Return a Supabase client using the service_role key.
    This BYPASSES RLS — use only inside admin-protected routes.
    """
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

import os
import json
import requests
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from typing import Dict, Any, Optional

# Load environment variables from .env file
load_dotenv()

# Gmail API scopes (expanded for send + modify + read + label management)
READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
SEND_SCOPE     = "https://www.googleapis.com/auth/gmail.send"
MODIFY_SCOPE   = "https://www.googleapis.com/auth/gmail.modify"

SCOPES = [READONLY_SCOPE, SEND_SCOPE, MODIFY_SCOPE]

# Nango config (from .env when Nango Cloud, or override per-account)
NANGO_BASE_URL = os.environ.get("NANGO_BASE_URL", "https://api.nango.dev")
NANGO_SECRET_KEY = os.environ.get("NANGO_SECRET_KEY")


def _get_nango_credentials(connection_id: str, provider_config_key: str) -> Dict[str, Any]:
    """Fetch credentials from Nango for a specific connection."""
    if not NANGO_SECRET_KEY:
        raise ValueError("NANGO_SECRET_KEY not configured")

    url = f"{NANGO_BASE_URL}/connection/{connection_id}"
    params = {
        "provider_config_key": provider_config_key,
        "refresh_token": "true",
    }
    headers = {"Authorization": f"Bearer {NANGO_SECRET_KEY}"}

    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def _extract_tokens(nango_response: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Extract access_token / refresh_token from Nango response."""
    access_token = None
    refresh_token = None
    client_id = None
    client_secret = None

    # Try multiple possible response shapes
    if "credentials" in nango_response:
        creds = nango_response["credentials"]
        access_token  = creds.get("access_token")
        refresh_token = creds.get("refresh_token")
        client_id     = creds.get("client_id") or creds.get("oauth_client_id")
        client_secret = creds.get("client_secret") or creds.get("oauth_client_secret")
    else:
        access_token  = nango_response.get("access_token")
        refresh_token = nango_response.get("refresh_token")
        client_id     = nango_response.get("client_id")
        client_secret = nango_response.get("client_secret")

    return {
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "client_id":     client_id,
        "client_secret": client_secret,
    }


# Per-account service cache: account -> (service, credentials)
_service_cache: Dict[str, Any] = {}


def get_gmail_service(
    connection_id: str,
    provider_config_key: str = "google",
    account: Optional[str] = None,
) -> build:
    """Authenticate Gmail via Nango and return a Gmail API service object.

    Uses an in-memory cache per account alias to avoid re-authenticating
    on every tool call.
    """
    global _service_cache

    cache_key = f"{provider_config_key}:{connection_id}"
    if account:
        cache_key = f"{account}:{cache_key}"

    # Check cache
    cached = _service_cache.get(cache_key)
    if cached:
        service, creds = cached["service"], cached["creds"]
        if creds.valid or (creds.expired and creds.refresh_token):
            if creds.expired:
                creds.refresh(Request())
                _service_cache[cache_key]["creds"] = creds
            return service
        # Cache stale; drop and re-auth
        del _service_cache[cache_key]

    # Fetch from Nango
    nango_resp = _get_nango_credentials(connection_id, provider_config_key)
    tokens = _extract_tokens(nango_resp)

    access_token = tokens["access_token"]
    if not access_token:
        raise ValueError("No access_token in Nango response")

    creds = Credentials(
        token=access_token,
        refresh_token=tokens["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=tokens["client_id"] or "",
        client_secret=tokens["client_secret"] or "",
        scopes=SCOPES,
    )

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    service = build("gmail", "v1", credentials=creds)
    _service_cache[cache_key] = {"service": service, "creds": creds}
    return service


# Backward-compat convenience helpers
def authenticate_gmail_with_nango(
    connection_id: str,
    provider_config_key: str = "google",
) -> build:
    """Legacy single-account entry point (kept for compat)."""
    return get_gmail_service(connection_id, provider_config_key)


def authenticate_gmail_with_nango_v2(
    connection_id: str,
    provider_config_key: str = "google",
) -> build:
    """Legacy single-account entry point v2 (kept for compat)."""
    return get_gmail_service(connection_id, provider_config_key)


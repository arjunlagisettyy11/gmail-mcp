"""Multi-account Nango configuration for Gmail MCP Server.

Map account aliases to Nango connection IDs via:
1. An accounts config file (~/.gmail-mcp/accounts.json)
2. Environment variables (NANGO_CONNECTION_ID for default account)

Accounts config format:
{
  "default": "personal",
  "accounts": {
    "personal": {"connection_id": "my-gmail-conn", "provider_config_key": "google"},
    "work":     {"connection_id": "my-work-conn",  "provider_config_key": "google-work"}
  }
}
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional

ACCOUNTS_FILE = Path.home() / ".gmail-mcp" / "accounts.json"


def _load_accounts_config() -> dict:
    if ACCOUNTS_FILE.exists():
        return json.loads(ACCOUNTS_FILE.read_text())
    return {}


def list_accounts() -> Dict[str, Optional[str]]:
    """Return mapping of account alias -> email (or connection_id if email unknown)."""
    cfg = _load_accounts_config()
    accounts = cfg.get("accounts", {})
    # Also include legacy single-account env var as 'default' if present
    legacy_id = os.getenv("NANGO_CONNECTION_ID")
    if legacy_id and "default" not in accounts:
        accounts = {"default": {"connection_id": legacy_id, "provider_config_key": os.getenv("NANGO_INTEGRATION_ID", "google")}}
    return {name: info.get("email") or info.get("connection_id")
            for name, info in accounts.items()}


def get_account_config(account: Optional[str] = None) -> dict:
    """Resolve account alias to its Nango config. Raises if unknown."""
    cfg = _load_accounts_config()
    accounts = cfg.get("accounts", {})

    # Handle legacy single-account env fallback
    legacy_id = os.getenv("NANGO_CONNECTION_ID")
    if legacy_id and not accounts:
        accounts = {
            "default": {
                "connection_id": legacy_id,
                "provider_config_key": os.getenv("NANGO_INTEGRATION_ID", "google"),
                "email": os.getenv("NANGO_CONNECTION_EMAIL", "default@gmail.com"),
            }
        }

    account = account or cfg.get("default", "default")
    if account not in accounts:
        known = ", ".join(accounts.keys())
        raise ValueError(
            f"Unknown account '{account}'. Known: {known}. "
            f"Add to {ACCOUNTS_FILE} or set NANGO_CONNECTION_ID env var."
        )

    info = dict(accounts[account])
    info["name"] = account
    return info


def get_connection_id(account: Optional[str] = None) -> str:
    """Get the Nango connection_id for an account alias."""
    return get_account_config(account)["connection_id"]


def get_provider_config_key(account: Optional[str] = None) -> str:
    """Get the Nango provider_config_key for an account alias."""
    return get_account_config(account).get("provider_config_key", "google")

"""
Gmail MCP Server (multi-account via Nango)

All tools accept an optional `account` parameter — an alias from
~/.gmail-mcp/accounts.json. Omit to use the default account.
"""

import os
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from gmail_auth import get_gmail_service
from gmail_operations import GmailClient
from nango_accounts import get_account_config, list_accounts

load_dotenv()

mcp = FastMCP("Gmail MCP Server (Multi-Account)")

# Per-account client cache: account name -> GmailClient
_clients: Dict[str, GmailClient] = {}


def gmail(account: Optional[str] = None) -> GmailClient:
    """Resolve account alias → GmailClient (cached per session)."""
    cfg = get_account_config(account)
    name = cfg["name"]
    if name not in _clients:
        service = get_gmail_service(
            connection_id=cfg["connection_id"],
            provider_config_key=cfg["provider_config_key"],
            account=name,
        )
        _clients[name] = GmailClient(service, account_name=name)
    return _clients[name]


def _ok(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"success": True, **data}


def _err(msg: str) -> Dict[str, Any]:
    return {"success": False, "error": msg}


# ------------------------------------------------------------------
# Account management
# ------------------------------------------------------------------

@mcp.tool()
def gmail_accounts() -> Dict[str, Any]:
    """List configured Gmail account aliases."""
    return _ok({"accounts": list_accounts()})


# ------------------------------------------------------------------
# Read
# ------------------------------------------------------------------

@mcp.tool()
def gmail_list_messages(
    query: str = "",
    max_results: int = 10,
    account: Optional[str] = None,
) -> Dict[str, Any]:
    """List Gmail messages with optional search query. Use `account` to pick inbox (alias or email)."""
    if not (1 <= max_results <= 100):
        return _err("max_results must be between 1 and 100")
    try:
        client = gmail(account)
        msgs = client.list_messages(query=query, max_results=max_results)
        if not msgs:
            return _ok({"count": 0, "messages": [], "message": "No messages found"})

        detailed = []
        for m in msgs:
            full = client.get_message(m["id"])
            if full:
                h = client.get_message_headers(full)
                detailed.append({
                    "id": m["id"],
                    "from": h.get("From", "Unknown"),
                    "subject": h.get("Subject", "No Subject"),
                    "date": h.get("Date", "Unknown"),
                    "snippet": (full.get("snippet") or "")[:100],
                    "labels": full.get("labelIds", []),
                    "is_unread": "UNREAD" in full.get("labelIds", []),
                })
        return _ok({"count": len(detailed), "messages": detailed,
                    "account": client.account_name, "query": query or "all"})
    except Exception as e:
        return _err(f"Failed to list messages: {e}")


@mcp.tool()
def gmail_get_message(message_id: str, account: Optional[str] = None) -> Dict[str, Any]:
    """Get one message's full body (plain text) by ID."""
    if not message_id:
        return _err("message_id required")
    try:
        client = gmail(account)
        msg = client.get_message(message_id)
        if not msg:
            return _err(f"Message {message_id} not found")
        h = client.get_message_headers(msg)
        body = client.get_message_body(msg)
        return _ok({
            "account": client.account_name,
            "message": {
                "id": message_id,
                "thread_id": msg.get("threadId", ""),
                "from": h.get("From"), "to": h.get("To"),
                "subject": h.get("Subject"), "date": h.get("Date"),
                "body": body,
                "snippet": msg.get("snippet", ""),
                "labels": msg.get("labelIds", []),
                "is_unread": "UNREAD" in msg.get("labelIds", []),
            },
        })
    except Exception as e:
        return _err(f"Failed to get message: {e}")


@mcp.tool()
def gmail_search_messages(
    sender: Optional[str] = None,
    subject: Optional[str] = None,
    after_date: Optional[str] = None,
    has_attachment: bool = False,
    is_unread: bool = False,
    max_results: int = 20,
    account: Optional[str] = None,
) -> Dict[str, Any]:
    """Search Gmail messages."""
    if not (1 <= max_results <= 100):
        return _err("max_results must be between 1 and 100")
    try:
        client = gmail(account)
        msgs = client.search_messages(
            sender=sender, subject=subject, after_date=after_date,
            has_attachment=has_attachment, is_unread=is_unread,
        )[:max_results]
        detailed = []
        for m in msgs:
            full = client.get_message(m["id"])
            if full:
                h = client.get_message_headers(full)
                detailed.append({
                    "id": m["id"],
                    "from": h.get("From", "Unknown"),
                    "subject": h.get("Subject", "No Subject"),
                    "date": h.get("Date", "Unknown"),
                    "snippet": (full.get("snippet") or "")[:100],
                    "is_unread": "UNREAD" in full.get("labelIds", []),
                })
        return _ok({"count": len(detailed), "messages": detailed,
                    "account": client.account_name})
    except Exception as e:
        return _err(f"Failed to search messages: {e}")


# ------------------------------------------------------------------
# Mutations
# ------------------------------------------------------------------

@mcp.tool()
def gmail_send_message(
    to: str, subject: str, body: str,
    cc: str = "", bcc: str = "",
    account: Optional[str] = None,
) -> Dict[str, Any]:
    """Send an email. Confirm with user before calling."""
    if not (to and "@" in to):
        return _err("Invalid recipient email")
    if not subject.strip() or not body.strip():
        return _err("Subject and body cannot be empty")
    try:
        client = gmail(account)
        result = client.send_message(to=to, subject=subject, body=body)
        if not result:
            return _err("Send failed")
        return _ok({"message_id": result["id"], "to": to, "subject": subject,
                    "account": client.account_name})
    except Exception as e:
        return _err(f"Failed to send: {e}")


@mcp.tool()
def gmail_mark_as_read(message_ids: List[str], account: Optional[str] = None) -> Dict[str, Any]:
    """Mark one or more messages as read."""
    if not message_ids:
        return _err("No message IDs provided")
    try:
        client = gmail(account)
        ok, fail = 0, []
        for mid in message_ids:
            if client.mark_as_read(mid):
                ok += 1
            else:
                fail.append(mid)
        return _ok({"marked": ok, "failed": fail, "account": client.account_name})
    except Exception as e:
        return _err(f"Failed to mark read: {e}")


@mcp.tool()
def gmail_delete_messages(message_ids: List[str], account: Optional[str] = None) -> Dict[str, Any]:
    """Permanently delete messages. Confirm with the user first."""
    if not message_ids:
        return _err("No message IDs provided")
    try:
        client = gmail(account)
        ok, fail = 0, []
        for mid in message_ids:
            if client.delete_message(mid):
                ok += 1
            else:
                fail.append(mid)
        return _ok({"deleted": ok, "failed": fail, "account": client.account_name})
    except Exception as e:
        return _err(f"Failed to delete: {e}")


@mcp.tool()
def gmail_get_stats(account: Optional[str] = None) -> Dict[str, Any]:
    """Get inbox statistics for an account."""
    try:
        client = gmail(account)
        profile = client.service.users().getProfile(userId="me").execute()
        unread = len(client.list_messages(query="is:unread", max_results=100))
        return _ok({
            "account": client.account_name,
            "email": profile.get("emailAddress"),
            "total_messages": profile.get("messagesTotal", 0),
            "total_threads": profile.get("threadsTotal", 0),
            "unread_sample": unread,
        })
    except Exception as e:
        return _err(f"Failed to get stats: {e}")


def run():
    print("Starting Gmail MCP Server (multi-account)...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()

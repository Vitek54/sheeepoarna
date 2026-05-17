"""Validators and helper utilities for Cat Tool."""

import hashlib
import re
from datetime import datetime
from typing import Optional


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_steam_id(steam_input: str) -> dict:
    """Parse and validate various Steam ID formats.

    Supports:
    - SteamID64 (76561198xxxxxxxxx)
    - SteamID (STEAM_X:Y:Z)
    - SteamID3 ([U:1:XXXXXXXX])
    - Custom URL (vanity name)
    - Full profile URL
    """
    result = {
        "type": None,
        "value": steam_input.strip(),
        "steam_id64": None,
        "custom_url": None,
    }

    cleaned = steam_input.strip().rstrip("/")

    url_match = re.match(r'https?://steamcommunity\.com/profiles/(\d+)', cleaned)
    if url_match:
        result["type"] = "steamid64"
        result["steam_id64"] = url_match.group(1)
        return result

    url_match = re.match(r'https?://steamcommunity\.com/id/([^/]+)', cleaned)
    if url_match:
        result["type"] = "custom_url"
        result["custom_url"] = url_match.group(1)
        return result

    if re.match(r'^7656119\d{10}$', cleaned):
        result["type"] = "steamid64"
        result["steam_id64"] = cleaned
        return result

    steam_id_match = re.match(r'^STEAM_(\d):(\d):(\d+)$', cleaned, re.IGNORECASE)
    if steam_id_match:
        x, y, z = int(steam_id_match.group(1)), int(steam_id_match.group(2)), int(steam_id_match.group(3))
        steam_id64 = str(76561197960265728 + z * 2 + y)
        result["type"] = "steamid"
        result["steam_id64"] = steam_id64
        return result

    steam3_match = re.match(r'^\[U:1:(\d+)\]$', cleaned)
    if steam3_match:
        account_id = int(steam3_match.group(1))
        steam_id64 = str(76561197960265728 + account_id)
        result["type"] = "steamid3"
        result["steam_id64"] = steam_id64
        return result

    if re.match(r'^[a-zA-Z0-9_-]+$', cleaned) and len(cleaned) >= 2:
        result["type"] = "custom_url"
        result["custom_url"] = cleaned
        return result

    result["type"] = "unknown"
    return result


def steam_id64_to_steam_id(steam_id64: str) -> str:
    """Convert SteamID64 to SteamID format."""
    id64 = int(steam_id64)
    y = id64 % 2
    z = (id64 - 76561197960265728 - y) // 2
    return f"STEAM_0:{y}:{z}"


def steam_id64_to_steam_id3(steam_id64: str) -> str:
    """Convert SteamID64 to SteamID3 format."""
    id64 = int(steam_id64)
    account_id = id64 - 76561197960265728
    return f"[U:1:{account_id}]"


def steam_id64_to_account_id(steam_id64: str) -> int:
    """Convert SteamID64 to Account ID."""
    return int(steam_id64) - 76561197960265728


def email_to_gravatar_hash(email: str) -> str:
    """Convert email to Gravatar MD5 hash."""
    return hashlib.md5(email.strip().lower().encode()).hexdigest()


def format_timestamp(ts: Optional[int]) -> str:
    """Format a Unix timestamp to human-readable format."""
    if ts is None:
        return "N/A"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        return "N/A"


def truncate(text: str, max_len: int = 50) -> str:
    """Truncate text to max length."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    return re.sub(r'[^\w\-.]', '_', name)

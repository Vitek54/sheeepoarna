"""Discover messages owned by the current user across guilds / channels."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from .api import DiscordClient, Forbidden, NotFound

log = logging.getLogger(__name__)


# Discord message types that the user can delete normally. Other types
# (e.g. RECIPIENT_ADD = 1, CHANNEL_NAME_CHANGE = 4, ...) are system
# messages and DELETE returns 403 on them — we skip those proactively.
DELETABLE_TYPES = {
    0,   # DEFAULT
    6,   # CHANNEL_PINNED_MESSAGE (user-initiated, sometimes deletable)
    19,  # REPLY
    20,  # CHAT_INPUT_COMMAND (slash-command response by user)
    23,  # CONTEXT_MENU_COMMAND
}


def iter_guild_messages(
    client: DiscordClient, guild_id: str, author_id: str
) -> Iterator[dict]:
    """Yield messages authored by ``author_id`` inside ``guild_id``.

    Uses the elastic-search endpoint. Re-queries with offset=0 once the
    window of 5000 reachable results is exhausted, on the assumption
    that callers delete messages as they iterate (so the window slides).
    """
    seen: set[str] = set()
    while True:
        offset = 0
        any_new = False
        while offset < 5000:
            try:
                page = client.search_guild(guild_id, author_id, offset=offset)
            except (Forbidden, NotFound):
                return
            messages = _flatten_search_hits(page)
            if not messages:
                break
            for m in messages:
                if m["id"] in seen:
                    continue
                seen.add(m["id"])
                any_new = True
                yield m
            offset += 25
            if len(messages) < 25:
                break
        if not any_new:
            return


def iter_channel_messages(
    client: DiscordClient,
    channel_id: str,
    author_id: str,
    *,
    use_search: bool = False,
) -> Iterator[dict]:
    """Yield messages authored by ``author_id`` inside ``channel_id``.

    ``use_search=True`` tries the channel search endpoint (only works in
    guild channels and some private channels). Otherwise it falls back
    to paginating ``/channels/{id}/messages``.
    """
    if use_search:
        seen: set[str] = set()
        while True:
            offset = 0
            any_new = False
            while offset < 5000:
                try:
                    page = client.search_channel(
                        channel_id, author_id, offset=offset
                    )
                except (Forbidden, NotFound):
                    return
                messages = _flatten_search_hits(page)
                if not messages:
                    break
                for m in messages:
                    if m["id"] in seen:
                        continue
                    seen.add(m["id"])
                    any_new = True
                    yield m
                offset += 25
                if len(messages) < 25:
                    break
            if not any_new:
                return
        return

    # Pagination fallback (used for DMs / group DMs).
    before: str | None = None
    while True:
        try:
            batch = client.channel_messages(channel_id, before=before, limit=100)
        except (Forbidden, NotFound):
            return
        if not batch:
            return
        for m in batch:
            if m.get("author", {}).get("id") == author_id:
                yield m
        before = batch[-1]["id"]


def _flatten_search_hits(page: dict) -> list[dict]:
    """Extract message dicts from Discord's nested search response."""
    out: list[dict] = []
    for cluster in page.get("messages", []) or []:
        for msg in cluster:
            # ``hit: true`` marks the actual match; surrounding messages
            # are context and we don't want to attempt to delete them.
            if msg.get("hit"):
                out.append(msg)
    return out


def is_deletable(message: dict) -> bool:
    """Return True if we should attempt to DELETE this message.

    Filters out system messages and messages flagged as ephemeral.
    Pinned messages are still deletable; we just unpin implicitly.
    """
    mtype = message.get("type", 0)
    if mtype not in DELETABLE_TYPES:
        return False
    # MESSAGE_FLAGS.EPHEMERAL = 1<<6 = 64 — can't delete via REST
    flags = message.get("flags", 0) or 0
    if flags & 64:
        return False
    return True


def list_dm_channels(client: DiscordClient) -> list[dict]:
    """Private channel types: 1=DM, 3=GROUP_DM."""
    return [c for c in client.my_private_channels() if c.get("type") in (1, 3)]


def list_guilds(client: DiscordClient) -> list[dict]:
    return client.my_guilds()


def dm_label(channel: dict) -> str:
    if channel.get("type") == 3:
        name = channel.get("name") or "group dm"
        recipients = channel.get("recipients") or []
        if not channel.get("name") and recipients:
            name = ", ".join(
                r.get("global_name") or r.get("username", "?") for r in recipients
            )
        return f"[group] {name}"
    recipients = channel.get("recipients") or []
    if recipients:
        r = recipients[0]
        return r.get("global_name") or r.get("username", "?")
    return f"dm {channel.get('id')}"


def guild_text_channel_ids(client: DiscordClient, guild_id: str) -> list[str]:
    """Used when guild search is unavailable (very rare)."""
    try:
        channels: list[dict[str, Any]] = client.guild_channels(guild_id)
    except (Forbidden, NotFound):
        return []
    # Type 0 = GUILD_TEXT, 5 = ANNOUNCEMENT, 11/12 = threads.
    return [
        c["id"]
        for c in channels
        if c.get("type") in (0, 5, 10, 11, 12, 15, 16)
    ]

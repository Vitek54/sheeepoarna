"""Discover messages owned by the current user across guilds / channels."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from .api import DiscordClient, Forbidden, NotFound

log = logging.getLogger(__name__)


# Message types Discord refuses to DELETE via the REST API. They are
# typically "system" events (joined, boosted, pinned-message marker,
# thread created, etc.) — the user appears as ``author`` but the message
# is owned by the system and only goes away when the thing it represents
# goes away (e.g. unpinning, unbosting, deleting the thread).
#
# Reference: https://discord.com/developers/docs/resources/channel#message-object-message-types
NON_DELETABLE_TYPES = frozenset(
    {
        1,   # RECIPIENT_ADD
        2,   # RECIPIENT_REMOVE
        3,   # CALL
        4,   # CHANNEL_NAME_CHANGE
        5,   # CHANNEL_ICON_CHANGE
        6,   # CHANNEL_PINNED_MESSAGE (the pin notification, not the pin itself)
        7,   # USER_JOIN
        8,   # GUILD_BOOST
        9,   # GUILD_BOOST_TIER_1
        10,  # GUILD_BOOST_TIER_2
        11,  # GUILD_BOOST_TIER_3
        12,  # CHANNEL_FOLLOW_ADD
        14,  # GUILD_DISCOVERY_DISQUALIFIED
        15,  # GUILD_DISCOVERY_REQUALIFIED
        16,  # GUILD_DISCOVERY_GRACE_PERIOD_INITIAL_WARNING
        17,  # GUILD_DISCOVERY_GRACE_PERIOD_FINAL_WARNING
        18,  # THREAD_CREATED
        21,  # THREAD_STARTER_MESSAGE (cross-post stub — delete the thread)
        22,  # GUILD_INVITE_REMINDER
        24,  # AUTO_MODERATION_ACTION
        25,  # ROLE_SUBSCRIPTION_PURCHASE
        26,  # INTERACTION_PREMIUM_UPSELL
        27,  # STAGE_START
        28,  # STAGE_END
        29,  # STAGE_SPEAKER
        31,  # STAGE_TOPIC
        32,  # GUILD_APPLICATION_PREMIUM_SUBSCRIPTION
        36,  # GUILD_INCIDENT_ALERT_MODE_ENABLED
        37,  # GUILD_INCIDENT_ALERT_MODE_DISABLED
        38,  # GUILD_INCIDENT_REPORT_RAID
        39,  # GUILD_INCIDENT_REPORT_FALSE_ALARM
        44,  # PURCHASE_NOTIFICATION
        46,  # POLL_RESULT
    }
)

# Ephemeral flag (1 << 6) — only the recipient sees the message and
# DELETE always returns an error.
MESSAGE_FLAG_EPHEMERAL = 1 << 6

# Search result clusters can be huge for active guilds; cap pagination
# at this offset (Discord's hard ceiling is 5000).
SEARCH_MAX_OFFSET = 5000


def iter_guild_messages(
    client: DiscordClient, guild_id: str, author_id: str
) -> Iterator[dict]:
    """Yield messages authored by ``author_id`` inside ``guild_id``.

    Uses the elasticsearch endpoint. Re-queries with ``offset=0`` once
    the window of 5000 reachable results is exhausted, assuming callers
    delete messages as they iterate (so the window slides).
    """
    seen: set[str] = set()
    while True:
        offset = 0
        any_new = False
        while offset < SEARCH_MAX_OFFSET:
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
            while offset < SEARCH_MAX_OFFSET:
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


def is_deletable(message: dict, *, author_id: str | None = None) -> tuple[bool, str]:
    """Decide whether DELETE is even worth attempting.

    Returns ``(ok, reason)``. ``reason`` is an empty string when ok=True,
    otherwise a short tag explaining the skip — used in the failures
    log and the progress UI.
    """
    if author_id is not None:
        msg_author = (message.get("author") or {}).get("id")
        if msg_author and msg_author != author_id:
            return False, "not-mine"

    mtype = message.get("type", 0)
    if mtype in NON_DELETABLE_TYPES:
        return False, f"system-type-{mtype}"

    flags = message.get("flags", 0) or 0
    if flags & MESSAGE_FLAG_EPHEMERAL:
        return False, "ephemeral"

    # Thread starter — message.id == channel.id and DELETE requires
    # deleting the entire thread, which we won't do silently.
    if message.get("id") and message.get("channel_id"):
        if message["id"] == message["channel_id"]:
            return False, "thread-starter"

    # Webhook messages (author has "bot": true / discriminator "0000")
    # can technically be deleted but only by the webhook owner; selfbot
    # is not the owner. Bail out — no point hammering.
    author = message.get("author") or {}
    if author.get("bot") and author_id and author.get("id") != author_id:
        return False, "bot-author"

    return True, ""


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


def parse_user_ids_by_role(
    client: DiscordClient, guild_id: str, role_id: str
) -> list[str]:
    """Return Discord user IDs of all members who have ``role_id``.

    Paginates through ``GET /guilds/{guild_id}/members`` (up to 1000 per
    page) and collects every member whose ``roles`` list contains
    ``role_id``.
    """
    user_ids: list[str] = []
    after = "0"
    while True:
        try:
            batch = client.guild_members(guild_id, after=after)
        except (Forbidden, NotFound):
            log.warning(
                "cannot list members for guild %s (forbidden/not found)",
                guild_id,
            )
            break
        if not batch:
            break
        for member in batch:
            roles: list[str] = member.get("roles", [])
            if role_id in roles:
                user = member.get("user") or {}
                uid = user.get("id")
                if uid:
                    user_ids.append(uid)
        after = (batch[-1].get("user") or {}).get("id", "0")
        if len(batch) < 1000:
            break
    return user_ids


def guild_text_channel_ids(client: DiscordClient, guild_id: str) -> list[str]:
    """Used when guild search is unavailable (very rare)."""
    try:
        channels: list[dict[str, Any]] = client.guild_channels(guild_id)
    except (Forbidden, NotFound):
        return []
    # Type 0 = GUILD_TEXT, 5 = ANNOUNCEMENT, 10/11/12 = threads,
    # 15 = forum, 16 = media.
    return [
        c["id"]
        for c in channels
        if c.get("type") in (0, 5, 10, 11, 12, 15, 16)
    ]

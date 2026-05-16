"""Утилитарные функции."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from discord_tool.core.config import SNOWFLAKE_EPOCH


def snowflake_time(snowflake_id: int) -> datetime:
    """Извлечь дату создания из Discord Snowflake ID."""
    ts = ((snowflake_id >> 22) + SNOWFLAKE_EPOCH) / 1000
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def format_permissions(perms: int) -> list[str]:
    perm_names = {
        0: "CREATE_INSTANT_INVITE",
        1: "KICK_MEMBERS",
        2: "BAN_MEMBERS",
        3: "ADMINISTRATOR",
        4: "MANAGE_CHANNELS",
        5: "MANAGE_GUILD",
        6: "ADD_REACTIONS",
        7: "VIEW_AUDIT_LOG",
        8: "PRIORITY_SPEAKER",
        9: "STREAM",
        10: "VIEW_CHANNEL",
        11: "SEND_MESSAGES",
        13: "SEND_TTS_MESSAGES",
        14: "MANAGE_MESSAGES",
        15: "EMBED_LINKS",
        16: "ATTACH_FILES",
        17: "READ_MESSAGE_HISTORY",
        18: "MENTION_EVERYONE",
        19: "USE_EXTERNAL_EMOJIS",
        20: "VIEW_GUILD_INSIGHTS",
        21: "CONNECT",
        22: "SPEAK",
        23: "MUTE_MEMBERS",
        24: "DEAFEN_MEMBERS",
        25: "MOVE_MEMBERS",
        26: "USE_VAD",
        27: "CHANGE_NICKNAME",
        28: "MANAGE_NICKNAMES",
        29: "MANAGE_ROLES",
        30: "MANAGE_WEBHOOKS",
        31: "MANAGE_GUILD_EXPRESSIONS",
        37: "MANAGE_THREADS",
        38: "CREATE_PUBLIC_THREADS",
        39: "CREATE_PRIVATE_THREADS",
        40: "USE_EXTERNAL_STICKERS",
        41: "SEND_MESSAGES_IN_THREADS",
    }
    result = []
    for bit, name in perm_names.items():
        if perms & (1 << bit):
            result.append(name)
    return result

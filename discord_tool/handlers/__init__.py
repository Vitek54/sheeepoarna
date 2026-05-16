"""Маппинг номеров меню → обработчики."""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from discord_tool.handlers.account import (
    handle_active_sessions,
    handle_boosts,
    handle_change_avatar,
    handle_change_bio,
    handle_change_display_name,
    handle_change_locale,
    handle_change_theme,
    handle_connections,
    handle_custom_status,
    handle_full_account_info,
    handle_hypesquad,
    handle_set_status,
    handle_subscriptions,
)
from discord_tool.handlers.deletion import (
    handle_purge_all_servers,
    handle_purge_channel,
    handle_purge_everywhere,
    handle_purge_server,
    handle_remove_reactions,
)
from discord_tool.handlers.friends import (
    handle_accept_all,
    handle_block,
    handle_friend_list,
    handle_mass_unfriend,
    handle_pending_requests,
    handle_send_request,
    handle_unblock,
)
from discord_tool.handlers.guilds import (
    handle_change_nickname,
    handle_download_emojis,
    handle_export_channel,
    handle_guild_info,
    handle_guild_list,
    handle_guild_roles,
    handle_mass_leave,
)
from discord_tool.handlers.parsing import (
    handle_invite_info,
    handle_mutual_friends,
    handle_mutual_guilds,
    handle_parse_role,
    handle_search_messages,
    handle_user_lookup,
)
from discord_tool.handlers.utilities import (
    handle_close_all_dms,
    handle_send_message,
    handle_webhooks,
)

HandlerFunc = Callable[..., Coroutine[Any, Any, None]]

HANDLERS: dict[str, HandlerFunc] = {
    "1": handle_purge_everywhere,
    "2": handle_purge_channel,
    "3": handle_purge_all_servers,
    "4": handle_purge_server,
    "5": handle_remove_reactions,
    "6": handle_parse_role,
    "7": handle_search_messages,
    "8": handle_user_lookup,
    "9": handle_mutual_guilds,
    "10": handle_mutual_friends,
    "11": handle_invite_info,
    "12": handle_full_account_info,
    "13": handle_change_bio,
    "14": handle_change_display_name,
    "15": handle_change_avatar,
    "16": handle_hypesquad,
    "17": handle_set_status,
    "18": handle_custom_status,
    "19": handle_change_locale,
    "20": handle_change_theme,
    "21": handle_connections,
    "22": handle_active_sessions,
    "23": handle_subscriptions,
    "24": handle_boosts,
    "25": handle_guild_info,
    "26": handle_guild_list,
    "27": handle_guild_roles,
    "28": handle_download_emojis,
    "29": handle_export_channel,
    "30": handle_change_nickname,
    "31": handle_mass_leave,
    "32": handle_friend_list,
    "33": handle_pending_requests,
    "34": handle_accept_all,
    "35": handle_block,
    "36": handle_unblock,
    "37": handle_send_request,
    "38": handle_mass_unfriend,
    "39": handle_close_all_dms,
    "40": handle_send_message,
    "41": handle_webhooks,
}

__all__ = ["HANDLERS"]

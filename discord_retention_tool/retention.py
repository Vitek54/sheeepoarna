"""Retention workflows that coordinate Discord API and local log cleanup."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .discord_api import DiscordClient
from .logs import RetentionStats, export_jsonl, prune_jsonl
from .ui import SlateUI


@dataclass(slots=True)
class CleanupStats:
    scanned: int = 0
    matched: int = 0
    deleted: int = 0
    queued_second_pass: int = 0
    unresolved: int = 0
    channels: int = 0


@dataclass(slots=True)
class RoleMemberParseStats:
    guild_id: str
    role_id: str
    scanned: int = 0
    matched: int = 0
    output_path: str = ""


@dataclass(slots=True)
class RetentionManager:
    client: DiscordClient | None = None
    ui: SlateUI = field(default_factory=SlateUI)

    def cleanup_bot_messages(self, channel_ids: Iterable[str], *, dry_run: bool = True) -> CleanupStats:
        """Delete messages authored by the authenticated bot in selected channels."""

        if self.client is None:
            raise ValueError("Discord client is required for API cleanup.")
        bot_user = self.client.get_current_bot_user()
        bot_id = str(bot_user["id"])
        stats = CleanupStats()
        for channel_id in channel_ids:
            stats.channels += 1
            self.ui.info(f"Indexing channel {channel_id} with before-pagination")
            for message in self.client.iter_channel_messages(str(channel_id)):
                stats.scanned += 1
                author = message.get("author") or {}
                if str(author.get("id")) != bot_id:
                    continue
                stats.matched += 1
                message_id = str(message["id"])
                if dry_run:
                    self.ui.info(f"dry-run: would delete {message_id} in {channel_id}")
                    continue
                if self.client.delete_message(str(channel_id), message_id):
                    stats.deleted += 1
            stats.queued_second_pass = len(self.client.second_pass)
        if not dry_run and self.client.second_pass:
            self.ui.warn("Running second pass for non-rate-limit failures")
            unresolved = self.client.second_pass_retry()
            stats.unresolved = len(unresolved)
        return stats

    def cleanup_guild(self, guild_id: str, *, dry_run: bool = True) -> CleanupStats:
        if self.client is None:
            raise ValueError("Discord client is required for API cleanup.")
        channels = self.client.text_channel_ids_for_guild(guild_id)
        return self.cleanup_bot_messages(channels, dry_run=dry_run)

    def parse_role_member_ids(
        self,
        guild_id: str,
        role_id: str,
        *,
        output_path: Path | None = None,
        validate_role: bool = True,
    ) -> RoleMemberParseStats:
        """Collect visible Discord user IDs assigned to a specific role ID.

        This uses Discord's bot REST API and cannot bypass missing guild access,
        missing privileged member intent, or Discord API limits.
        """

        if self.client is None:
            raise ValueError("Discord client is required for role member parsing.")
        stats = RoleMemberParseStats(guild_id=str(guild_id), role_id=str(role_id))
        handle = output_path.open("w", encoding="utf-8") if output_path is not None else None
        try:
            if validate_role and not self.client.guild_has_role(guild_id, role_id):
                self.ui.warn(f"Role {role_id} was not found in guild {guild_id}")
                return stats
            self.ui.info(f"Parsing visible members in guild {guild_id} for role {role_id}")
            for member in self.client.iter_guild_members(guild_id):
                stats.scanned += 1
                roles = {str(role) for role in member.get("roles", [])}
                if str(role_id) not in roles:
                    continue
                user = member.get("user") or {}
                user_id = user.get("id")
                if user_id is None:
                    continue
                stats.matched += 1
                if handle is not None:
                    handle.write(f"{user_id}\n")
                else:
                    self.ui.info(str(user_id))
        finally:
            if handle is not None:
                handle.close()
                stats.output_path = str(output_path)
        return stats

    def prune_local_log(self, path: Path, *, days: int, timestamp_field: str = "timestamp") -> RetentionStats:
        self.ui.info(f"Applying {days}-day retention to {path}")
        return prune_jsonl(path, days=days, timestamp_field=timestamp_field)

    def export_local_log(self, path: Path, output_path: Path) -> RetentionStats:
        self.ui.info(f"Exporting normalized copy from {path} to {output_path}")
        return export_jsonl(path, output_path)

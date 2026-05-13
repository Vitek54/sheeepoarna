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

    def prune_local_log(self, path: Path, *, days: int, timestamp_field: str = "timestamp") -> RetentionStats:
        self.ui.info(f"Applying {days}-day retention to {path}")
        return prune_jsonl(path, days=days, timestamp_field=timestamp_field)

    def export_local_log(self, path: Path, output_path: Path) -> RetentionStats:
        self.ui.info(f"Exporting normalized copy from {path} to {output_path}")
        return export_jsonl(path, output_path)

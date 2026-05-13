"""Command-line entry point for Discord retention workflows."""

from __future__ import annotations

import argparse
import os
from dataclasses import asdict
from pathlib import Path

from .discord_api import DiscordClient, RateLimitConfig
from .reporting import report_v3_research_note
from .retention import RetentionManager
from .ui import SlateUI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="discord-retention",
        description="Compliant retention utility for local logs and bot-authored Discord messages.",
    )
    parser.add_argument("--quiet", action="store_true", help="Reduce TUI output.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    prune = subcommands.add_parser("prune-log", help="Apply retention to a local JSONL log file.")
    prune.add_argument("path", type=Path)
    prune.add_argument("--days", type=int, required=True, help="Keep rows newer than this many days.")
    prune.add_argument("--timestamp-field", default="timestamp")

    export = subcommands.add_parser("export-log", help="Normalize a local JSONL log into another file.")
    export.add_argument("path", type=Path)
    export.add_argument("output", type=Path)

    cleanup = subcommands.add_parser("cleanup", help="Delete bot-authored messages from selected Discord contexts.")
    cleanup.add_argument("--bot-token", default=os.getenv("DISCORD_BOT_TOKEN"), help="Bot token or DISCORD_BOT_TOKEN.")
    cleanup.add_argument("--channel-id", action="append", default=[], help="Channel ID to process; repeatable.")
    cleanup.add_argument("--guild-id", help="Guild ID whose text channels should be processed.")
    cleanup.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    cleanup.add_argument("--max-retries", type=int, default=8)
    cleanup.add_argument("--base-delay", type=float, default=1.0)
    cleanup.add_argument("--max-delay", type=float, default=120.0)

    role_members = subcommands.add_parser(
        "role-members",
        help="Export visible user IDs assigned to a role ID using the bot API.",
    )
    role_members.add_argument("--bot-token", default=os.getenv("DISCORD_BOT_TOKEN"), help="Bot token or DISCORD_BOT_TOKEN.")
    role_members.add_argument("--guild-id", required=True, help="Guild/server ID to scan.")
    role_members.add_argument("--role-id", required=True, help="Role ID to match.")
    role_members.add_argument("--output", type=Path, help="Write one user ID per line to this file.")
    role_members.add_argument(
        "--no-validate-role",
        action="store_true",
        help="Skip the initial guild role existence check and scan members directly.",
    )
    role_members.add_argument("--max-retries", type=int, default=8)
    role_members.add_argument("--base-delay", type=float, default=1.0)
    role_members.add_argument("--max-delay", type=float, default=120.0)

    subcommands.add_parser("reporting-note", help="Explain why automated Report V3 is not implemented.")
    return parser


def _client_from_args(args: argparse.Namespace) -> DiscordClient:
    if not args.bot_token:
        raise SystemExit("A Discord bot token is required via --bot-token or DISCORD_BOT_TOKEN.")
    return DiscordClient(
        args.bot_token,
        RateLimitConfig(max_retries=args.max_retries, base_delay=args.base_delay, max_delay=args.max_delay),
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ui = SlateUI(quiet=args.quiet)
    ui.banner("Discord Retention", "Monochrome/Slate · bot-token compliant · retention-first")

    if args.command == "prune-log":
        manager = RetentionManager(ui=ui)
        stats = manager.prune_local_log(args.path, days=args.days, timestamp_field=args.timestamp_field)
        ui.summary(asdict(stats))
        return 0

    if args.command == "export-log":
        manager = RetentionManager(ui=ui)
        stats = manager.export_local_log(args.path, args.output)
        ui.summary(asdict(stats))
        return 0

    if args.command == "cleanup":
        client = _client_from_args(args)
        manager = RetentionManager(client=client, ui=ui)
        if args.guild_id and args.channel_id:
            raise SystemExit("Choose either --guild-id or --channel-id, not both.")
        if args.guild_id:
            stats = manager.cleanup_guild(args.guild_id, dry_run=args.dry_run)
        elif args.channel_id:
            stats = manager.cleanup_bot_messages(args.channel_id, dry_run=args.dry_run)
        else:
            raise SystemExit("Provide --channel-id at least once or --guild-id.")
        ui.summary(asdict(stats))
        return 0

    if args.command == "role-members":
        client = _client_from_args(args)
        manager = RetentionManager(client=client, ui=ui)
        stats = manager.parse_role_member_ids(
            args.guild_id,
            args.role_id,
            output_path=args.output,
            validate_role=not args.no_validate_role,
        )
        ui.summary(asdict(stats))
        return 0

    if args.command == "reporting-note":
        ui.warn(report_v3_research_note())
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

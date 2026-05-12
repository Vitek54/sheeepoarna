"""discord-cleaner — entry point.

Usage:
    python main.py

A minimalist black-and-white TUI: paste your token, pick a scope, watch
your messages disappear. State persists across Ctrl+C to ``state.json``.

This tool automates a USER account, which violates Discord's Terms of
Service. Use it on accounts you can afford to lose.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from cleaner import deleter, ui
from cleaner.api import DiscordClient, Unauthorized
from cleaner.discovery import (
    dm_label,
    guild_text_channel_ids,  # noqa: F401 — exported for future use
    list_dm_channels,
    list_guilds,
)
from cleaner.state import RunState


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        filename="cleaner.log",
        filemode="a",
    )


def login_loop() -> tuple[DiscordClient, str, str]:
    while True:
        token = ui.ask_token()
        if not token:
            ui.error("empty token")
            continue
        client = DiscordClient(token)
        try:
            me = client.me()
        except Unauthorized:
            ui.error("invalid token — try again")
            continue
        except Exception as e:  # noqa: BLE001
            ui.error(f"login failed: {e}")
            continue
        username = (
            me.get("global_name")
            or me.get("username")
            or me.get("id", "?")
        )
        return client, me["id"], f"{username} ({me['id']})"


def maybe_resume(state_path: Path, user_id: str, op: str, target: str = "") -> RunState:
    state = RunState.load(state_path)
    if state.matches(user_id, op, target) and state.completed_scopes:
        ui.info(
            f"found unfinished run with {len(state.completed_scopes)} scopes "
            f"already complete ({state.deleted} deleted so far)"
        )
        if ui.confirm("resume?", default=True):
            return state
    state.reset(user_id, op, target)
    state.save(state_path)
    return state


def run_everywhere(client: DiscordClient, user_id: str) -> None:
    if not ui.confirm(
        "this will delete every message you authored on every server and dm. continue?",
        default=False,
    ):
        return
    state_path = Path("state.json")
    state = maybe_resume(state_path, user_id, "everywhere")
    scopes = deleter.build_scopes_everywhere(client, user_id)
    with ui.progress_display() as progress:
        deleter.run(client, state, scopes, progress=progress)
    ui.info(
        f"done: deleted={state.deleted} skipped={state.skipped} failed={state.failed}"
    )


def run_servers(client: DiscordClient, user_id: str) -> None:
    if not ui.confirm(
        "this will delete every message you authored across all servers. continue?",
        default=False,
    ):
        return
    state_path = Path("state.json")
    state = maybe_resume(state_path, user_id, "servers")
    scopes = deleter.build_scopes_servers(client, user_id)
    with ui.progress_display() as progress:
        deleter.run(client, state, scopes, progress=progress)
    ui.info(
        f"done: deleted={state.deleted} skipped={state.skipped} failed={state.failed}"
    )


def run_specific_server(client: DiscordClient, user_id: str) -> None:
    guilds = list_guilds(client)
    if not guilds:
        ui.warn("you are not in any servers")
        return
    chosen = ui.pick(guilds, title="pick a server", label_key="name")
    if not chosen:
        return
    if not ui.confirm(
        f"delete every message you authored in '{chosen.get('name')}'?",
        default=False,
    ):
        return
    state_path = Path("state.json")
    state = maybe_resume(state_path, user_id, "server", chosen["id"])
    scope = deleter.build_scope_single_guild(client, user_id, chosen)
    with ui.progress_display() as progress:
        deleter.run(client, state, [scope], progress=progress)
    ui.info(
        f"done: deleted={state.deleted} skipped={state.skipped} failed={state.failed}"
    )


def run_specific_channel(client: DiscordClient, user_id: str) -> None:
    ui.section("pick channel source")
    ui.info("1. dm or group dm")
    ui.info("2. channel inside a server")
    ui.info("3. paste channel id directly")
    src = ui.ask_text("choice", default="1")

    if src == "1":
        dms = list_dm_channels(client)
        items = [{"id": c["id"], "name": dm_label(c)} for c in dms]
        chosen = ui.pick(items, title="pick a dm")
        if not chosen:
            return
        label = chosen["name"]
        is_guild_channel = False
        channel_id = chosen["id"]
    elif src == "2":
        guilds = list_guilds(client)
        chosen_g = ui.pick(guilds, title="pick a server")
        if not chosen_g:
            return
        channels = client.guild_channels(chosen_g["id"])
        text_channels = [
            c for c in channels if c.get("type") in (0, 5, 10, 11, 12, 15, 16)
        ]
        if not text_channels:
            ui.warn("no text channels in this server")
            return
        chosen_c = ui.pick(
            [{"id": c["id"], "name": "#" + c.get("name", c["id"])} for c in text_channels],
            title="pick a channel",
        )
        if not chosen_c:
            return
        label = f"{chosen_g.get('name')} {chosen_c['name']}"
        is_guild_channel = True
        channel_id = chosen_c["id"]
    elif src == "3":
        channel_id = ui.ask_text("channel id")
        if not channel_id.isdigit():
            ui.error("channel id must be a numeric snowflake")
            return
        label = f"channel {channel_id}"
        is_guild_channel = ui.confirm("is this a server channel?", default=True)
    else:
        ui.error("invalid choice")
        return

    if not ui.confirm(
        f"delete every message you authored in '{label}'?", default=False
    ):
        return

    state_path = Path("state.json")
    state = maybe_resume(state_path, user_id, "channel", channel_id)
    scope = deleter.build_scope_single_channel(
        client,
        user_id,
        channel_id,
        label=label,
        is_guild_channel=is_guild_channel,
    )
    with ui.progress_display() as progress:
        deleter.run(client, state, [scope], progress=progress)
    ui.info(
        f"done: deleted={state.deleted} skipped={state.skipped} failed={state.failed}"
    )


def main() -> int:
    setup_logging()
    ui.clear()
    ui.banner()

    client, user_id, account_label = login_loop()

    while True:
        ui.console.print()
        choice = ui.main_menu(account_label)
        try:
            if choice == "1":
                run_everywhere(client, user_id)
            elif choice == "2":
                run_specific_channel(client, user_id)
            elif choice == "3":
                run_servers(client, user_id)
            elif choice == "4":
                run_specific_server(client, user_id)
            elif choice == "0":
                ui.goodbye()
                return 0
        except KeyboardInterrupt:
            ui.console.print()
            ui.warn("interrupted — state saved to state.json")
            if not ui.confirm("back to main menu?", default=True):
                return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(130)

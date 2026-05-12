"""Orchestrates discovery + deletion across the chosen scope.

Design points:

* Streams messages from the discovery iterator and deletes one-by-one
  using the bucket-aware client. We never bulk-delete because a user
  account cannot use the bot bulk-delete endpoint.
* Re-queries search after each pass so newly-revealed older messages
  (past the 5000-result window) become reachable on subsequent passes.
* Updates a ``RunState`` after every deletion so the user can Ctrl+C
  at any moment without losing progress accounting.
* Reports progress through a callback so the UI layer stays decoupled
  from API logic.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from .api import DiscordClient, DiscordError, Forbidden, NotFound
from .discovery import (
    dm_label,
    is_deletable,
    iter_channel_messages,
    iter_guild_messages,
    list_dm_channels,
    list_guilds,
)
from .state import RunState

log = logging.getLogger(__name__)


@dataclass
class Scope:
    """A single (label, iterator-factory) unit of work."""

    kind: str                                            # "guild" | "dm" | "channel"
    target_id: str
    label: str
    iter_factory: Callable[[], Iterator[dict]]


ProgressCb = Callable[[str, RunState], None]


def build_scopes_everywhere(
    client: DiscordClient, user_id: str
) -> list[Scope]:
    scopes: list[Scope] = []
    for g in list_guilds(client):
        gid = g["id"]
        scopes.append(
            Scope(
                kind="guild",
                target_id=gid,
                label=f"[server] {g.get('name', gid)}",
                iter_factory=lambda gid=gid: iter_guild_messages(
                    client, gid, user_id
                ),
            )
        )
    for c in list_dm_channels(client):
        cid = c["id"]
        scopes.append(
            Scope(
                kind="dm",
                target_id=cid,
                label=dm_label(c),
                iter_factory=lambda cid=cid: iter_channel_messages(
                    client, cid, user_id, use_search=False
                ),
            )
        )
    return scopes


def build_scopes_servers(
    client: DiscordClient, user_id: str
) -> list[Scope]:
    scopes: list[Scope] = []
    for g in list_guilds(client):
        gid = g["id"]
        scopes.append(
            Scope(
                kind="guild",
                target_id=gid,
                label=f"[server] {g.get('name', gid)}",
                iter_factory=lambda gid=gid: iter_guild_messages(
                    client, gid, user_id
                ),
            )
        )
    return scopes


def build_scope_single_guild(
    client: DiscordClient, user_id: str, guild: dict
) -> Scope:
    gid = guild["id"]
    return Scope(
        kind="guild",
        target_id=gid,
        label=f"[server] {guild.get('name', gid)}",
        iter_factory=lambda: iter_guild_messages(client, gid, user_id),
    )


def build_scope_single_channel(
    client: DiscordClient,
    user_id: str,
    channel_id: str,
    *,
    label: str,
    is_guild_channel: bool,
) -> Scope:
    kind = "channel" if is_guild_channel else "dm"
    return Scope(
        kind=kind,
        target_id=channel_id,
        label=label,
        iter_factory=lambda: iter_channel_messages(
            client, channel_id, user_id, use_search=is_guild_channel
        ),
    )


def run(
    client: DiscordClient,
    state: RunState,
    scopes: list[Scope],
    *,
    progress: ProgressCb | None = None,
) -> RunState:
    """Execute deletions for every scope, persisting state continuously."""

    for scope in scopes:
        scope_key = f"{scope.kind}:{scope.target_id}"
        if scope_key in state.completed_scopes:
            if progress:
                progress(f"skip (already done): {scope.label}", state)
            continue

        if progress:
            progress(f"scanning {scope.label}", state)

        finished = _drain_scope(client, scope, state, progress)
        if finished:
            state.completed_scopes.append(scope_key)
            state.save()
            if progress:
                progress(f"done: {scope.label}", state)
        else:
            state.save()
            if progress:
                progress(f"stopped: {scope.label}", state)

    state.save()
    return state


def _drain_scope(
    client: DiscordClient,
    scope: Scope,
    state: RunState,
    progress: ProgressCb | None,
) -> bool:
    """Iterate + delete until the scope is empty.

    Returns True on natural completion, False if it aborted (the caller
    has already persisted state, so this is non-fatal).
    """
    while True:
        any_found = False
        try:
            iterator = scope.iter_factory()
            for message in iterator:
                any_found = True
                if not is_deletable(message):
                    state.skipped += 1
                    state.save()
                    if progress:
                        progress(
                            f"skip non-deletable in {scope.label}", state
                        )
                    continue

                channel_id = message.get("channel_id") or scope.target_id
                msg_id = message["id"]
                try:
                    client.delete_message(channel_id, msg_id)
                    state.deleted += 1
                    state.save()
                    if progress:
                        progress(
                            f"deleted {msg_id} in {scope.label}", state
                        )
                except (Forbidden, NotFound):
                    state.skipped += 1
                    state.save()
                    if progress:
                        progress(
                            f"skip protected {msg_id} in {scope.label}",
                            state,
                        )
                except DiscordError as e:
                    state.failed += 1
                    state.save()
                    log.warning(
                        "delete failed %s in %s: %s", msg_id, scope.label, e
                    )
                    if progress:
                        progress(
                            f"fail {msg_id} in {scope.label} ({e.status})",
                            state,
                        )
        except KeyboardInterrupt:
            raise
        except DiscordError as e:
            log.warning("scope error in %s: %s", scope.label, e)
            if progress:
                progress(
                    f"scope error in {scope.label} ({e.status}) — moving on",
                    state,
                )
            return False

        if not any_found:
            return True
        # Loop again — guild search window may have hidden older results.

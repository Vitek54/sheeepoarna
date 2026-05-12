"""Orchestrates discovery + deletion across the chosen scope.

Design points:

* Streams messages from the discovery iterator and deletes one-by-one
  using the bucket-aware client. We never bulk-delete because a user
  account cannot use the bot bulk-delete endpoint.
* Pre-filters messages via :func:`discovery.is_deletable` so we never
  hit the API for things Discord will reject (system events, ephemeral,
  thread starters, etc).
* Parses Discord error codes from 400 / 403 bodies and classifies the
  failure: known "expected" codes become *skipped*, the rest become
  *failed* and are dumped to ``failures.json`` for inspection.
* Auto-unarchives threads on error 50083 and retries DELETE once.
* Persists ``RunState`` after every action so Ctrl+C is safe.
* Caches per-run "permanently un-deletable" message IDs so search-driven
  iteration can't loop forever on the same uncullable message.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .api import DiscordClient, DiscordError, Forbidden, NotFound, Unauthorized
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


# Discord JSON error codes (sent as ``code`` in the response body).
# Mapped to short tags so the UI/log can show what actually went wrong.
#
# Reference: https://discord.com/developers/docs/topics/opcodes-and-status-codes#json
KNOWN_SKIP_CODES = {
    10003: "unknown-channel",
    10008: "unknown-message",       # already deleted by something else
    10013: "unknown-user",
    50001: "missing-access",
    50013: "missing-permissions",
    50021: "system-message",        # "cannot execute action on a system message"
    50068: "invalid-message-type",
    160005: "thread-locked",
}

# Thread archive — recoverable: unarchive then retry.
ERROR_THREAD_ARCHIVED = 50083

FAILURES_PATH = Path("failures.json")


@dataclass
class Scope:
    """A single (label, iterator-factory) unit of work."""

    kind: str                                            # "guild" | "dm" | "channel"
    target_id: str
    label: str
    iter_factory: Callable[[], Iterator[dict]]


ProgressCb = Callable[[str, RunState], None]


# ----------------------------------------------------------------------
# Scope construction


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


# ----------------------------------------------------------------------
# Failure logging


def _record_failure(entry: dict) -> None:
    """Append a single failure entry to ``failures.json``.

    File format: a JSON array — we read, append, write atomically so
    that the user can ``cat failures.json`` and pipe through jq.
    """
    try:
        if FAILURES_PATH.exists():
            with FAILURES_PATH.open(encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = []
        else:
            data = []
    except (OSError, json.JSONDecodeError):
        data = []
    data.append(entry)
    tmp = FAILURES_PATH.with_suffix(".json.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(FAILURES_PATH)
    except OSError as e:
        log.warning("could not write failures.json: %s", e)


def _err_code(err: DiscordError) -> int | None:
    """Pull Discord's JSON error code out of a DiscordError body."""
    body = err.body
    if isinstance(body, dict):
        try:
            return int(body.get("code", 0)) or None
        except (TypeError, ValueError):
            return None
    return None


def _err_message(err: DiscordError) -> str:
    body = err.body
    if isinstance(body, dict):
        msg = body.get("message")
        if isinstance(msg, str):
            return msg
    return str(body)[:200]


# ----------------------------------------------------------------------
# Main entry point


def run(
    client: DiscordClient,
    state: RunState,
    scopes: list[Scope],
    user_id: str,
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

        finished = _drain_scope(client, scope, state, user_id, progress)
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
    user_id: str,
    progress: ProgressCb | None,
) -> bool:
    """Iterate + delete until the scope is empty.

    Returns True on natural completion, False if it aborted (the caller
    has already persisted state).
    """
    # Track ids we've already determined we cannot delete — otherwise
    # the search-driven iterator will keep handing us the same message
    # forever (the index still contains it).
    permanently_skipped: set[str] = set()
    unarchived_threads: set[str] = set()

    while True:
        any_found = False
        any_progress = False  # did we delete OR newly-skip anything?
        try:
            iterator = scope.iter_factory()
            for message in iterator:
                msg_id = message["id"]
                if msg_id in permanently_skipped:
                    continue
                any_found = True

                # Client-side pre-filter — these never reach the API.
                ok, reason = is_deletable(message, author_id=user_id)
                if not ok:
                    permanently_skipped.add(msg_id)
                    state.skipped += 1
                    state.save()
                    any_progress = True
                    _record_failure(
                        {
                            "ts": _now(),
                            "scope": scope.label,
                            "channel_id": message.get("channel_id"),
                            "message_id": msg_id,
                            "outcome": "skipped",
                            "reason": reason,
                            "type": message.get("type"),
                        }
                    )
                    if progress:
                        progress(
                            f"skip ({reason}) {msg_id} in {scope.label}",
                            state,
                        )
                    continue

                channel_id = message.get("channel_id") or scope.target_id
                outcome = _attempt_delete(
                    client, channel_id, msg_id, unarchived_threads
                )

                if outcome.kind == "deleted":
                    state.deleted += 1
                    state.save()
                    any_progress = True
                    if progress:
                        progress(
                            f"deleted {msg_id} in {scope.label}", state
                        )
                elif outcome.kind == "skipped":
                    permanently_skipped.add(msg_id)
                    state.skipped += 1
                    state.save()
                    any_progress = True
                    _record_failure(
                        {
                            "ts": _now(),
                            "scope": scope.label,
                            "channel_id": channel_id,
                            "message_id": msg_id,
                            "outcome": "skipped",
                            "reason": outcome.reason,
                            "discord_code": outcome.code,
                            "discord_message": outcome.discord_message,
                        }
                    )
                    if progress:
                        progress(
                            f"skip ({outcome.reason}) {msg_id} in {scope.label}",
                            state,
                        )
                else:  # "failed"
                    permanently_skipped.add(msg_id)
                    state.failed += 1
                    state.save()
                    any_progress = True
                    _record_failure(
                        {
                            "ts": _now(),
                            "scope": scope.label,
                            "channel_id": channel_id,
                            "message_id": msg_id,
                            "outcome": "failed",
                            "reason": outcome.reason,
                            "discord_code": outcome.code,
                            "discord_message": outcome.discord_message,
                        }
                    )
                    if progress:
                        code_tag = (
                            f"code={outcome.code}"
                            if outcome.code
                            else f"http={outcome.reason}"
                        )
                        progress(
                            f"fail ({code_tag}) {msg_id} in {scope.label}",
                            state,
                        )

        except KeyboardInterrupt:
            raise
        except Unauthorized:
            # Bad token mid-run — bail loudly.
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
        if not any_progress:
            # All discovered messages were already in the skip cache —
            # nothing left to do for this scope.
            return True


# ----------------------------------------------------------------------
# Single-message delete with thread-unarchive recovery


@dataclass
class _DeleteOutcome:
    kind: str                    # "deleted" | "skipped" | "failed"
    reason: str = ""
    code: int | None = None
    discord_message: str = ""


def _attempt_delete(
    client: DiscordClient,
    channel_id: str,
    message_id: str,
    unarchived_threads: set[str],
) -> _DeleteOutcome:
    try:
        client.delete_message(channel_id, message_id)
        return _DeleteOutcome("deleted")
    except NotFound as e:
        return _DeleteOutcome(
            "skipped",
            reason="unknown-message",
            code=_err_code(e),
            discord_message=_err_message(e),
        )
    except Forbidden as e:
        code = _err_code(e)
        return _DeleteOutcome(
            "skipped",
            reason=KNOWN_SKIP_CODES.get(code or 0, f"forbidden-{code}"),
            code=code,
            discord_message=_err_message(e),
        )
    except DiscordError as e:
        code = _err_code(e)

        # Thread archived — try to unarchive once, then retry DELETE.
        if (
            code == ERROR_THREAD_ARCHIVED
            and channel_id not in unarchived_threads
        ):
            log.info("unarchiving %s to delete %s", channel_id, message_id)
            try:
                client.edit_channel(channel_id, archived=False)
                unarchived_threads.add(channel_id)
                time.sleep(0.5)
                client.delete_message(channel_id, message_id)
                return _DeleteOutcome("deleted")
            except DiscordError as e2:
                return _DeleteOutcome(
                    "skipped",
                    reason="thread-archived-unrecoverable",
                    code=_err_code(e2),
                    discord_message=_err_message(e2),
                )

        if code in KNOWN_SKIP_CODES:
            return _DeleteOutcome(
                "skipped",
                reason=KNOWN_SKIP_CODES[code],
                code=code,
                discord_message=_err_message(e),
            )

        return _DeleteOutcome(
            "failed",
            reason=str(e.status),
            code=code,
            discord_message=_err_message(e),
        )


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

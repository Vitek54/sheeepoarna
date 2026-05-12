"""Smoke tests for parsing + state + deletion logic — no network access."""

from __future__ import annotations

import json
import time
import types
from unittest.mock import MagicMock

import pytest

from cleaner.api import DiscordClient, DiscordError, Forbidden, NotFound
from cleaner.deleter import _attempt_delete, _err_code, _err_message
from cleaner.discovery import _flatten_search_hits, is_deletable, parse_user_ids_by_role
from cleaner.state import RunState


# ----------------------------------------------------------------------
# DiscordClient routing


def test_route_key_keeps_major_params_and_masks_others() -> None:
    """Discord buckets are scoped per major param (channel/guild/webhook),
    so we keep those literal but mask any further snowflake ids."""
    c = DiscordClient("x" * 30)
    assert (
        c._route_key("DELETE", "/channels/123456789012345678/messages/9876543210987654321")
        == "DELETE /channels/123456789012345678/messages/:id"
    )
    assert c._route_key("GET", "/users/@me/guilds") == "GET /users/@me/guilds"
    assert (
        c._route_key("GET", "/guilds/123456789012345678/messages/search")
        == "GET /guilds/123456789012345678/messages/search"
    )


def test_rate_limit_bucket_update() -> None:
    c = DiscordClient("x" * 30)
    resp = types.SimpleNamespace(
        headers={
            "X-RateLimit-Bucket": "abc",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset-After": "1.5",
        }
    )
    route = "DELETE /channels/:id/messages/:id"
    c._update_buckets(route, resp)
    assert c._route_to_bucket[route] == "abc"
    bucket = c._buckets["abc"]
    assert bucket.remaining == 0
    assert bucket.reset_at > time.monotonic()


def test_token_strip() -> None:
    c = DiscordClient('  "mytoken"  ')
    assert c.token == '"mytoken"'
    c2 = DiscordClient("rawtoken\n")
    assert c2.token == "rawtoken"


def test_empty_token_rejected() -> None:
    with pytest.raises(ValueError):
        DiscordClient("")


# ----------------------------------------------------------------------
# Search-response parsing


def test_flatten_search_hits_only_returns_hit_messages() -> None:
    page = {
        "total_results": 2,
        "messages": [
            [
                {"id": "1", "hit": False, "content": "context"},
                {"id": "2", "hit": True, "content": "match"},
                {"id": "3", "hit": False, "content": "context"},
            ],
            [
                {"id": "4", "hit": True, "content": "match2"},
            ],
        ],
    }
    out = _flatten_search_hits(page)
    assert [m["id"] for m in out] == ["2", "4"]


def test_flatten_search_hits_empty() -> None:
    assert _flatten_search_hits({"messages": []}) == []
    assert _flatten_search_hits({}) == []


# ----------------------------------------------------------------------
# is_deletable filter


def test_is_deletable_accepts_user_messages() -> None:
    ok, reason = is_deletable(
        {"type": 0, "author": {"id": "u1"}, "id": "1", "channel_id": "c1"},
        author_id="u1",
    )
    assert ok and reason == ""

    ok, _ = is_deletable(
        {"type": 19, "author": {"id": "u1"}, "id": "2", "channel_id": "c1"},
        author_id="u1",
    )
    assert ok


def test_is_deletable_rejects_system_message_types() -> None:
    # User-join system message — author=user but undeletable.
    ok, reason = is_deletable(
        {"type": 7, "author": {"id": "u1"}, "id": "1", "channel_id": "c1"},
        author_id="u1",
    )
    assert not ok and "system-type-7" in reason

    # Thread created
    ok, _ = is_deletable(
        {"type": 18, "author": {"id": "u1"}, "id": "1", "channel_id": "c1"},
        author_id="u1",
    )
    assert not ok

    # Guild boost
    ok, _ = is_deletable(
        {"type": 8, "author": {"id": "u1"}, "id": "1", "channel_id": "c1"},
        author_id="u1",
    )
    assert not ok


def test_is_deletable_rejects_ephemeral() -> None:
    ok, reason = is_deletable(
        {
            "type": 0,
            "flags": 64,
            "author": {"id": "u1"},
            "id": "1",
            "channel_id": "c1",
        },
        author_id="u1",
    )
    assert not ok and reason == "ephemeral"


def test_is_deletable_rejects_thread_starter() -> None:
    # Thread starter: message.id == channel.id
    ok, reason = is_deletable(
        {
            "type": 0,
            "author": {"id": "u1"},
            "id": "111",
            "channel_id": "111",
        },
        author_id="u1",
    )
    assert not ok and reason == "thread-starter"


def test_is_deletable_rejects_wrong_author() -> None:
    ok, reason = is_deletable(
        {
            "type": 0,
            "author": {"id": "other-user"},
            "id": "1",
            "channel_id": "c1",
        },
        author_id="u1",
    )
    assert not ok and reason == "not-mine"


# ----------------------------------------------------------------------
# State persistence


def test_state_round_trip(tmp_path) -> None:
    p = tmp_path / "state.json"
    s = RunState()
    s.reset("u1", "everywhere")
    s.completed_scopes.append("guild:1")
    s.deleted = 42
    s.save(p)

    loaded = RunState.load(p)
    assert loaded.user_id == "u1"
    assert loaded.operation == "everywhere"
    assert loaded.deleted == 42
    assert loaded.completed_scopes == ["guild:1"]
    assert loaded.matches("u1", "everywhere")
    assert not loaded.matches("u1", "servers")


def test_state_load_missing(tmp_path) -> None:
    p = tmp_path / "missing.json"
    s = RunState.load(p)
    assert s.user_id == ""
    assert s.deleted == 0


def test_state_load_corrupt(tmp_path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("not json {", encoding="utf-8")
    s = RunState.load(p)
    assert s.user_id == ""


# ----------------------------------------------------------------------
# Error parsing


def test_err_code_extracts_discord_code() -> None:
    err = DiscordError(400, {"code": 50083, "message": "Thread is archived"})
    assert _err_code(err) == 50083
    assert _err_message(err) == "Thread is archived"


def test_err_code_handles_non_dict_body() -> None:
    err = DiscordError(500, "<html>oops</html>")
    assert _err_code(err) is None
    assert "html" in _err_message(err)


# ----------------------------------------------------------------------
# _attempt_delete error classification


def _client_with_delete(side_effect) -> MagicMock:
    client = MagicMock()
    client.delete_message.side_effect = side_effect
    return client


def test_attempt_delete_success() -> None:
    client = _client_with_delete(None)
    out = _attempt_delete(client, "c1", "m1", set())
    assert out.kind == "deleted"


def test_attempt_delete_unknown_message_is_skipped() -> None:
    client = _client_with_delete(NotFound(404, {"code": 10008, "message": "Unknown Message"}))
    out = _attempt_delete(client, "c1", "m1", set())
    assert out.kind == "skipped"
    assert out.reason == "unknown-message"
    assert out.code == 10008


def test_attempt_delete_missing_permissions_is_skipped() -> None:
    client = _client_with_delete(
        Forbidden(403, {"code": 50013, "message": "Missing Permissions"})
    )
    out = _attempt_delete(client, "c1", "m1", set())
    assert out.kind == "skipped"
    assert out.reason == "missing-permissions"


def test_attempt_delete_unknown_400_is_failed() -> None:
    client = _client_with_delete(DiscordError(400, {"code": 99999, "message": "Mystery"}))
    out = _attempt_delete(client, "c1", "m1", set())
    assert out.kind == "failed"
    assert out.code == 99999


def test_attempt_delete_thread_archived_recovers() -> None:
    """On 50083 we unarchive the thread and retry DELETE once."""
    client = MagicMock()
    call_count = {"n": 0}

    def delete_side_effect(channel_id, message_id):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise DiscordError(400, {"code": 50083, "message": "Thread is archived"})
        return None  # second call succeeds

    client.delete_message.side_effect = delete_side_effect
    client.edit_channel.return_value = {"id": "c1", "archived": False}

    unarchived: set[str] = set()
    out = _attempt_delete(client, "c1", "m1", unarchived)
    assert out.kind == "deleted"
    assert "c1" in unarchived
    client.edit_channel.assert_called_once_with("c1", archived=False)


def test_attempt_delete_thread_archived_no_double_unarchive() -> None:
    """If we already tried to unarchive the same thread, don't loop."""
    client = MagicMock()
    client.delete_message.side_effect = DiscordError(
        400, {"code": 50083, "message": "Thread is archived"}
    )

    out = _attempt_delete(client, "c1", "m1", {"c1"})  # already attempted
    assert out.kind == "failed"
    assert out.code == 50083
    client.edit_channel.assert_not_called()


# ----------------------------------------------------------------------
# parse_user_ids_by_role


def test_parse_user_ids_by_role_filters_by_role() -> None:
    client = MagicMock()
    client.guild_members.return_value = [
        {"user": {"id": "u1"}, "roles": ["r1", "r2"]},
        {"user": {"id": "u2"}, "roles": ["r3"]},
        {"user": {"id": "u3"}, "roles": ["r1"]},
    ]
    result = parse_user_ids_by_role(client, "g1", "r1")
    assert result == ["u1", "u3"]


def test_parse_user_ids_by_role_empty_when_no_match() -> None:
    client = MagicMock()
    client.guild_members.return_value = [
        {"user": {"id": "u1"}, "roles": ["r2"]},
    ]
    result = parse_user_ids_by_role(client, "g1", "r999")
    assert result == []


def test_parse_user_ids_by_role_paginates() -> None:
    client = MagicMock()
    page1 = [{"user": {"id": f"u{i}"}, "roles": ["target"]} for i in range(1000)]
    page2 = [{"user": {"id": "u_last"}, "roles": ["target"]}]
    client.guild_members.side_effect = [page1, page2]
    result = parse_user_ids_by_role(client, "g1", "target")
    assert len(result) == 1001
    assert result[-1] == "u_last"
    assert client.guild_members.call_count == 2


def test_parse_user_ids_by_role_handles_forbidden() -> None:
    client = MagicMock()
    client.guild_members.side_effect = Forbidden(403, {"message": "Missing Access"})
    result = parse_user_ids_by_role(client, "g1", "r1")
    assert result == []


def test_parse_user_ids_by_role_handles_not_found() -> None:
    client = MagicMock()
    client.guild_members.side_effect = NotFound(404, {"message": "Unknown Guild"})
    result = parse_user_ids_by_role(client, "g1", "r1")
    assert result == []


def test_parse_user_ids_by_role_skips_member_without_user() -> None:
    client = MagicMock()
    client.guild_members.return_value = [
        {"roles": ["r1"]},
        {"user": {"id": "u2"}, "roles": ["r1"]},
    ]
    result = parse_user_ids_by_role(client, "g1", "r1")
    assert result == ["u2"]

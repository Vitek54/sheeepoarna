"""Smoke tests for parsing + state — no network access."""

from __future__ import annotations

import json
import time
import types

import pytest

from cleaner.api import DiscordClient
from cleaner.discovery import _flatten_search_hits, is_deletable
from cleaner.state import RunState


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


def test_is_deletable_filters_system_messages() -> None:
    assert is_deletable({"type": 0})
    assert is_deletable({"type": 19})
    assert not is_deletable({"type": 1})   # RECIPIENT_ADD
    assert not is_deletable({"type": 7})   # USER_JOIN
    # Ephemeral flag (1<<6 = 64)
    assert not is_deletable({"type": 0, "flags": 64})


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
    assert c.token == '"mytoken"'  # strip whitespace only
    c2 = DiscordClient("rawtoken\n")
    assert c2.token == "rawtoken"


def test_empty_token_rejected() -> None:
    with pytest.raises(ValueError):
        DiscordClient("")

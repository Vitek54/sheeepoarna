# Discord Retention Tool

A Python utility for privacy-oriented retention workflows around Discord data.
It is intentionally scoped to compliant operations:

- local JSONL log pruning/export;
- Discord **bot-token** cleanup of messages authored by the authenticated bot;
- before-pagination for deep channel history traversal;
- rate-limit handling that respects Discord `Retry-After` / `retry_after` values;
- second-pass retry queues for non-rate-limit failures;
- a minimal monochrome/slate TUI with optional `rich` styling.

## Explicit safety and compliance boundaries

This project does **not** accept Discord user tokens and does not implement
self-bot automation. Discord requires automation to use OAuth2/bot accounts, so
normal account tokens are rejected before any API request is made.

This project also does **not** automate Report V3 or mass reporting. Reporting
should remain contextual and user-driven through Discord's official in-app flow;
this tool can retain/export local evidence for human review but will not spam
trust-and-safety systems.

## Install

```bash
python -m pip install -e .
# Optional richer monochrome TUI
python -m pip install -e '.[tui]'
```

## Local log retention

The log commands operate on newline-delimited JSON files. Rows older than the
retention window are removed, malformed rows are kept for safety, and a `.bak`
backup is written before pruning.

```bash
discord-retention prune-log ./discord-events.jsonl --days 30
```

Normalize/export a portable copy:

```bash
discord-retention export-log ./discord-events.jsonl ./export.jsonl
```

## Bot-authored Discord message cleanup

Set a bot token from the Discord Developer Portal:

```bash
export DISCORD_BOT_TOKEN='YOUR_BOT_TOKEN'
```

Dry-run a specific channel first:

```bash
discord-retention cleanup --channel-id 123456789012345678 --dry-run
```

Execute deletion of messages authored by that bot:

```bash
discord-retention cleanup --channel-id 123456789012345678 --no-dry-run
```

Process all supported text-like channels in a guild visible to the bot:

```bash
discord-retention cleanup --guild-id 123456789012345678 --dry-run
```


## Parse user IDs by role ID

You can export IDs of members that are visible to your bot and currently have a
specific role. This is not a permission bypass: the bot must be in the guild and
Discord must allow it to list members. For complete results in larger guilds,
enable the privileged Server Members Intent for the application in the Discord
Developer Portal. Discord caps the REST member-list endpoint at 1,000 members
per page, so the command uses the fastest supported page size and walks pages
with `after`; it cannot be truly instant for very large servers.

```bash
discord-retention role-members \
  --guild-id 123456789012345678 \
  --role-id 987654321098765432 \
  --output role-member-ids.txt
```

If the role check says no members were found, first verify that you copied the
role ID, not a channel/user ID, and that the bot has member-list access. Use
`--no-validate-role` only when you know the role exists but the initial role
metadata request is unavailable.

## Rate limits and reliability

The client reads `Retry-After` response headers and JSON `retry_after` fields,
then combines them with capped exponential backoff and jitter. HTTP 429 responses
are retried in-place. Other HTTP/network failures are added to a second-pass
queue so the workflow can retry transient issues without silently dropping IDs.

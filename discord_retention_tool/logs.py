"""Local log retention helpers."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


@dataclass(slots=True)
class RetentionStats:
    scanned: int = 0
    retained: int = 0
    pruned: int = 0
    malformed: int = 0


def parse_timestamp(value: str) -> datetime | None:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                yield {"_malformed": line}
                continue
            if isinstance(value, dict):
                yield value
            else:
                yield {"_malformed": line}


def prune_jsonl(path: Path, *, days: int, timestamp_field: str = "timestamp", backup: bool = True) -> RetentionStats:
    """Remove JSONL rows older than `days`, keeping malformed rows for safety."""

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    tmp = path.with_suffix(path.suffix + ".tmp")
    stats = RetentionStats()
    if backup:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    with tmp.open("w", encoding="utf-8") as output:
        for row in iter_jsonl(path):
            stats.scanned += 1
            if "_malformed" in row:
                stats.malformed += 1
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
                stats.retained += 1
                continue
            timestamp = parse_timestamp(str(row.get(timestamp_field, "")))
            if timestamp is None or timestamp >= cutoff:
                output.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                stats.retained += 1
            else:
                stats.pruned += 1
    tmp.replace(path)
    return stats


def export_jsonl(path: Path, output_path: Path) -> RetentionStats:
    """Normalize a JSONL log into another JSONL file for portability."""

    stats = RetentionStats()
    with output_path.open("w", encoding="utf-8") as output:
        for row in iter_jsonl(path):
            stats.scanned += 1
            if "_malformed" in row:
                stats.malformed += 1
                continue
            output.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            stats.retained += 1
    return stats

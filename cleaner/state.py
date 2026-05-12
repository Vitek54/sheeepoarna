"""Persisted run state — lets the user resume after Ctrl+C / crash."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_PATH = Path.cwd() / "state.json"


@dataclass
class RunState:
    user_id: str = ""
    operation: str = ""           # everywhere | channel | servers | server
    target_id: str = ""           # specific channel/guild for those modes
    completed_scopes: list[str] = field(default_factory=list)
    deleted: int = 0
    skipped: int = 0
    failed: int = 0

    def save(self, path: Path = DEFAULT_PATH) -> None:
        data = asdict(self)
        # Atomic write to avoid corruption on Ctrl+C.
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".state.", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> "RunState":
        if not path.exists():
            return cls()
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return cls()
        state = cls()
        for k, v in data.items():
            if hasattr(state, k):
                setattr(state, k, v)
        return state

    def matches(self, user_id: str, operation: str, target_id: str = "") -> bool:
        return (
            self.user_id == user_id
            and self.operation == operation
            and self.target_id == target_id
        )

    def reset(self, user_id: str, operation: str, target_id: str = "") -> None:
        self.user_id = user_id
        self.operation = operation
        self.target_id = target_id
        self.completed_scopes = []
        self.deleted = 0
        self.skipped = 0
        self.failed = 0

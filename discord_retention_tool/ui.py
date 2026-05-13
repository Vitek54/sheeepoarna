"""Minimal monochrome/slate terminal UI helpers."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
except ImportError:  # pragma: no cover - exercised when rich is absent
    Console = None  # type: ignore[assignment]
    Panel = None  # type: ignore[assignment]
    Progress = None  # type: ignore[assignment]
    SpinnerColumn = None  # type: ignore[assignment]
    TextColumn = None  # type: ignore[assignment]
    TimeElapsedColumn = None  # type: ignore[assignment]
    Table = None  # type: ignore[assignment]


@dataclass(slots=True)
class SlateUI:
    """Small facade that keeps output strict, readable, and dependency-light."""

    quiet: bool = False
    _console: object | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        self._console = Console(color_system="standard", highlight=False) if Console else None

    def banner(self, title: str, subtitle: str) -> None:
        if self.quiet:
            return
        text = f"{title}\n{subtitle}"
        if self._console and Panel:
            self._console.print(Panel(text, border_style="white", style="white"))
        else:
            print(f"\n== {title} ==\n{subtitle}\n", file=sys.stderr)

    def info(self, message: str) -> None:
        if not self.quiet:
            self._write("[·]", message)

    def success(self, message: str) -> None:
        if not self.quiet:
            self._write("[✓]", message)

    def warn(self, message: str) -> None:
        if not self.quiet:
            self._write("[!]", message)

    def error(self, message: str) -> None:
        self._write("[x]", message)

    def _write(self, prefix: str, message: str) -> None:
        if self._console:
            self._console.print(f"[white]{prefix} {message}[/white]")
        else:
            print(f"{prefix} {message}", file=sys.stderr)

    def summary(self, rows: dict[str, int | str]) -> None:
        if self.quiet:
            return
        if self._console and Table:
            table = Table(show_header=False, box=None, style="white")
            table.add_column("Key", style="white")
            table.add_column("Value", justify="right", style="white")
            for key, value in rows.items():
                table.add_row(key, str(value))
            self._console.print(table)
            return
        for key, value in rows.items():
            print(f"{key}: {value}", file=sys.stderr)

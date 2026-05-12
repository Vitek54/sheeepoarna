"""Minimalist black-and-white TUI built on rich.

No colours — only bold / dim / inverse for emphasis. The goal is a
terminal that looks clean on any background.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

console = Console(highlight=False, soft_wrap=True)


BANNER = r"""
    ____  _                       __   _________                            
   / __ \(_)_____________  _________/ /  / ____/ /__  ____ _____  ___  _____
  / / / / / ___/ ___/ __ \/ ___/ __  /  / /   / / _ \/ __ `/ __ \/ _ \/ ___/
 / /_/ / (__  ) /__/ /_/ / /  / /_/ /  / /___/ /  __/ /_/ / / / /  __/ /    
/_____/_/____/\___/\____/_/   \__,_/   \____/_/\___/\__,_/_/ /_/\___/_/     
"""


def clear() -> None:
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")


def banner() -> None:
    text = Text(BANNER, style="bold")
    console.print(Align.center(text))
    console.print(
        Align.center(
            Text("selectively delete your own messages\n", style="dim italic")
        )
    )


def section(title: str) -> None:
    console.rule(Text(title, style="bold"), style="dim")


def hint(msg: str) -> None:
    console.print(Text(f"  {msg}", style="dim"))


def info(msg: str) -> None:
    console.print(Text(f"  {msg}"))


def warn(msg: str) -> None:
    console.print(Text(f"  ! {msg}", style="bold"))


def error(msg: str) -> None:
    console.print(Text(f"  x {msg}", style="bold reverse"))


def ask_token() -> str:
    section("authentication")
    hint("paste your discord user token (input is hidden)")
    token = Prompt.ask(Text("  >", style="bold"), password=True, console=console)
    return (token or "").strip().strip('"').strip("'")


def confirm(prompt: str, *, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    ans = Prompt.ask(
        Text(f"  {prompt} {suffix}", style="bold"),
        console=console,
        default="y" if default else "n",
        show_default=False,
    )
    return ans.strip().lower() in ("y", "yes")


def main_menu(account_label: str) -> str:
    section("main menu")
    info(f"signed in as {account_label}")
    console.print()
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold", justify="right")
    table.add_column()
    options = [
        ("1", "delete messages everywhere (servers + dms)"),
        ("2", "delete messages in a specific channel / dm"),
        ("3", "delete messages on all servers only"),
        ("4", "delete messages on a specific server"),
        ("0", "exit"),
    ]
    for k, v in options:
        table.add_row(k, v)
    console.print(Padding(table))
    console.print()
    choice = Prompt.ask(
        Text("  >", style="bold"),
        choices=[k for k, _ in options],
        console=console,
        show_choices=False,
    )
    return choice


def pick(items: Sequence[dict], *, title: str, label_key: str = "name") -> dict | None:
    """Render a numbered list of dicts and return the selected one."""
    section(title)
    if not items:
        warn("nothing to pick from")
        return None

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold", justify="right")
    table.add_column()
    for i, item in enumerate(items, 1):
        table.add_row(str(i), item.get(label_key) or item.get("id", "?"))
    console.print(Padding(table))
    console.print()

    while True:
        raw = Prompt.ask(
            Text("  number (or 'q' to go back) >", style="bold"),
            console=console,
        )
        raw = raw.strip().lower()
        if raw in ("q", "quit", "back", ""):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(items):
            return items[int(raw) - 1]
        error("invalid selection")


def ask_text(prompt: str, *, default: str | None = None) -> str:
    return Prompt.ask(
        Text(f"  {prompt}", style="bold"),
        console=console,
        default=default,
    ).strip()


@contextmanager
def progress_display():
    """Live status panel that the deleter calls into via a callback."""
    stats = {"line": "starting up...", "deleted": 0, "skipped": 0, "failed": 0}

    def render() -> Any:
        body = Text()
        body.append(stats["line"] + "\n", style="bold")
        body.append("\n")
        body.append(f"  deleted  {stats['deleted']:>6}\n", style="bold")
        body.append(f"  skipped  {stats['skipped']:>6}\n", style="dim")
        body.append(f"  failed   {stats['failed']:>6}\n", style="dim")
        body.append("\n")
        body.append("  ctrl+c to pause — state is saved continuously", style="dim italic")
        return Panel(body, border_style="dim", title="cleaning", title_align="left")

    with Live(render(), console=console, refresh_per_second=8, transient=False) as live:
        def cb(line: str, state: Any) -> None:
            stats["line"] = line
            stats["deleted"] = state.deleted
            stats["skipped"] = state.skipped
            stats["failed"] = state.failed
            live.update(render())

        yield cb


def goodbye() -> None:
    console.print()
    console.print(Text("  bye.", style="dim italic"))
    console.print()


def Padding(renderable, pad: int = 2):  # noqa: N802 — helper alias
    from rich.padding import Padding as _Padding

    return _Padding(renderable, (0, pad))

"""Report generation for Cat Tool."""

import json
import os
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich.columns import Columns
from rich import box

console = Console()


class Report:
    """Collects and displays OSINT findings."""

    def __init__(self, target: str, scan_type: str):
        self.target = target
        self.scan_type = scan_type
        self.start_time = datetime.now()
        self.sections: list[dict[str, Any]] = []
        self.summary_stats: dict[str, int] = {}

    def add_section(self, title: str, data: dict[str, Any]):
        """Add a section to the report."""
        self.sections.append({"title": title, "data": data})

    def set_stats(self, stats: dict[str, int]):
        """Set summary statistics."""
        self.summary_stats = stats

    def display_section_table(self, title: str, rows: list[list[str]], headers: list[str], style: str = "bright_cyan"):
        """Display a section as a Rich table."""
        table = Table(
            title=f"[bold {style}]{title}[/bold {style}]",
            box=box.ROUNDED,
            border_style=style,
            show_lines=True,
            padding=(0, 1),
        )
        for header in headers:
            table.add_column(header, style="bold white", overflow="fold")

        for row in rows:
            styled_row = []
            for cell in row:
                if cell in ("Found", "Yes", "True", "FOUND", "Exists"):
                    styled_row.append(f"[bold green]{cell}[/bold green]")
                elif cell in ("Not Found", "No", "False", "N/A", "Not Exists"):
                    styled_row.append(f"[dim]{cell}[/dim]")
                elif cell.startswith("http"):
                    styled_row.append(f"[underline blue]{cell}[/underline blue]")
                else:
                    styled_row.append(cell)
            table.add_row(*styled_row)

        console.print(table)
        console.print()

    def display_key_value(self, title: str, data: dict[str, str], style: str = "bright_cyan"):
        """Display key-value pairs in a panel."""
        text = Text()
        for key, value in data.items():
            text.append(f"  {key}: ", style="bold white")
            if value and str(value).startswith("http"):
                text.append(f"{value}\n", style="underline blue")
            elif value in ("Found", "Yes", "True"):
                text.append(f"{value}\n", style="bold green")
            elif value in ("Not Found", "No", "False", "N/A"):
                text.append(f"{value}\n", style="dim")
            else:
                text.append(f"{value}\n", style="bright_white")

        console.print(Panel(text, title=f"[bold {style}]{title}[/bold {style}]", border_style=style, padding=(1, 2)))
        console.print()

    def display_tree(self, title: str, data: dict, style: str = "bright_cyan"):
        """Display hierarchical data as a tree."""
        tree = Tree(f"[bold {style}]{title}[/bold {style}]")
        self._build_tree(tree, data)
        console.print(Panel(tree, border_style=style, padding=(1, 2)))
        console.print()

    def _build_tree(self, tree: Tree, data: dict):
        """Recursively build a tree from dict data."""
        for key, value in data.items():
            if isinstance(value, dict):
                branch = tree.add(f"[bold yellow]{key}[/bold yellow]")
                self._build_tree(branch, value)
            elif isinstance(value, list):
                branch = tree.add(f"[bold yellow]{key}[/bold yellow]")
                for item in value:
                    if isinstance(item, dict):
                        sub = branch.add(f"[dim]---[/dim]")
                        self._build_tree(sub, item)
                    else:
                        branch.add(f"[white]{item}[/white]")
            else:
                if str(value).startswith("http"):
                    tree.add(f"[bold]{key}:[/bold] [underline blue]{value}[/underline blue]")
                elif str(value) in ("Found", "Yes", "True"):
                    tree.add(f"[bold]{key}:[/bold] [bold green]{value}[/bold green]")
                else:
                    tree.add(f"[bold]{key}:[/bold] [white]{value}[/white]")

    def display_found_accounts(self, title: str, accounts: list[dict], style: str = "bright_green"):
        """Display found accounts in a compact table."""
        if not accounts:
            console.print(f"[dim]No accounts found for {title}[/dim]")
            return

        table = Table(
            title=f"[bold {style}]{title} ({len(accounts)} found)[/bold {style}]",
            box=box.DOUBLE_EDGE,
            border_style=style,
            show_lines=False,
            padding=(0, 1),
        )
        table.add_column("#", style="dim", width=4, justify="right")
        table.add_column("Platform", style="bold cyan", min_width=15)
        table.add_column("URL", style="underline blue", overflow="fold")
        table.add_column("Status", justify="center", width=10)

        for i, acc in enumerate(accounts, 1):
            status = "[bold green]FOUND[/bold green]" if acc.get("exists") else "[dim]---[/dim]"
            table.add_row(str(i), acc.get("name", ""), acc.get("url", ""), status)

        console.print(table)
        console.print()

    def display_summary(self):
        """Display final summary panel."""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        summary = Text()
        summary.append("\n")
        summary.append("  /\\_/\\\n", style="bold yellow")
        summary.append(" ( ^.^ )  ", style="bold yellow")
        summary.append("Scan Complete!\n\n", style="bold bright_green")

        summary.append(f"  Target: ", style="bold")
        summary.append(f"{self.target}\n", style="bright_cyan")
        summary.append(f"  Type: ", style="bold")
        summary.append(f"{self.scan_type}\n", style="bright_magenta")
        summary.append(f"  Duration: ", style="bold")
        summary.append(f"{elapsed:.1f}s\n", style="bright_yellow")
        summary.append(f"  Time: ", style="bold")
        summary.append(f"{self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n", style="dim")

        if self.summary_stats:
            for key, value in self.summary_stats.items():
                summary.append(f"  {key}: ", style="bold")
                color = "bright_green" if value > 0 else "dim"
                summary.append(f"{value}\n", style=color)

        console.print(Panel(
            summary,
            title="[bold bright_cyan]Scan Summary[/bold bright_cyan]",
            border_style="bright_cyan",
            padding=(0, 2),
        ))

    def export_json(self, filename: str = ""):
        """Export report to JSON file."""
        if not filename:
            safe_target = self.target.replace("@", "_at_").replace(".", "_")
            filename = f"cat_tool_report_{safe_target}_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json"

        report_data = {
            "tool": "Cat Tool v1.0.0",
            "target": self.target,
            "scan_type": self.scan_type,
            "timestamp": self.start_time.isoformat(),
            "sections": self.sections,
            "stats": self.summary_stats,
        }

        reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        filepath = os.path.join(reports_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)

        console.print(f"\n[bold green]Report saved:[/bold green] [underline]{filepath}[/underline]")
        return filepath

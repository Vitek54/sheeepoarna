"""Interactive menu system for Cat Tool."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()


def show_main_menu() -> str:
    """Display the main menu and get user choice."""
    menu_table = Table(
        box=box.ROUNDED,
        border_style="bright_cyan",
        show_header=False,
        padding=(0, 3),
        min_width=60,
    )
    menu_table.add_column("Option", style="bold bright_cyan", width=8, justify="center")
    menu_table.add_column("Description", style="white")
    menu_table.add_column("Details", style="dim")

    menu_table.add_row("[1]", "Email Intelligence", "Validate, providers, breaches, registrations")
    menu_table.add_row("[2]", "Username Hunt", "Search across 100+ platforms")
    menu_table.add_row("[3]", "Social Media Scan", "Deep social media profiling")
    menu_table.add_row("[4]", "Steam OSINT", "Full Steam account intelligence")
    menu_table.add_row("[5]", "Full Dossier", "All modules combined scan")
    menu_table.add_row("", "", "")
    menu_table.add_row("[0]", "Exit", "")

    console.print(Panel(
        menu_table,
        title="[bold bright_cyan]/\\_/\\  Main Menu[/bold bright_cyan]",
        subtitle="[dim]Select an option[/dim]",
        border_style="bright_cyan",
        padding=(1, 2),
    ))

    console.print()
    choice = console.input("[bold bright_cyan]  > Select option [0-5]: [/bold bright_cyan]")
    return choice.strip()


def get_input(prompt: str, required: bool = True) -> str:
    """Get input from user with styled prompt."""
    while True:
        value = console.input(f"[bold bright_cyan]  > {prompt}: [/bold bright_cyan]")
        value = value.strip()
        if value or not required:
            return value
        console.print("[bold red]  Input cannot be empty![/bold red]")


def confirm(prompt: str) -> bool:
    """Ask for confirmation."""
    choice = console.input(f"[bold bright_yellow]  > {prompt} [Y/n]: [/bold bright_yellow]")
    return choice.strip().lower() in ("", "y", "yes", "da")


def show_separator():
    """Show a visual separator."""
    console.print("[dim]" + "=" * 70 + "[/dim]")


def show_error(message: str):
    """Display an error message."""
    console.print(f"\n[bold red]  Error: {message}[/bold red]\n")


def show_info(message: str):
    """Display an info message."""
    console.print(f"\n[bold bright_cyan]  Info: {message}[/bold bright_cyan]\n")


def press_enter():
    """Wait for user to press Enter."""
    console.input("\n[dim]  Press Enter to continue...[/dim]")

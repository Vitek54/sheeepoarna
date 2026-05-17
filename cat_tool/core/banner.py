"""ASCII art banner and branding for Cat Tool."""

from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.align import Align

console = Console()

CAT_LOGO = r"""
      /\_/\    ╔═══════════════════════════════════════╗
     ( o.o )   ║     ██████╗ █████╗ ████████╗          ║
      > ^ <    ║    ██╔════╝██╔══██╗╚══██╔══╝          ║
     /|   |\   ║    ██║     ███████║   ██║              ║
    (_|   |_)  ║    ██║     ██╔══██║   ██║              ║
               ║    ╚██████╗██║  ██║   ██║              ║
   /\_/\_/\    ║     ╚═════╝╚═╝  ╚═╝   ╚═╝              ║
  ( = o_o= )   ║        ████████╗ ██████╗  ██████╗ ██╗   ║
   )  (Y)  (   ║        ╚══██╔══╝██╔═══██╗██╔═══██╗██║   ║
  /    |    \  ║           ██║   ██║   ██║██║   ██║██║   ║
 ( /|  |  |\ ) ║           ██║   ██║   ██║██║   ██║██║   ║
  \| |_|_| |/  ║           ██║   ╚██████╔╝╚██████╔╝███████╗║
   '"'"'"'"'   ║           ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝║
               ╚═══════════════════════════════════════╝
"""

CAT_SMALL = r"""
    /\_/\
   ( o.o )   C A T   T O O L
    > ^ <    Advanced OSINT Utility
"""

MAIN_BANNER = """[bold cyan]
   ██████╗  █████╗ ████████╗  ████████╗ ██████╗  ██████╗ ██╗
  ██╔════╝ ██╔══██╗╚══██╔══╝  ╚══██╔══╝██╔═══██╗██╔═══██╗██║
  ██║      ███████║   ██║        ██║   ██║   ██║██║   ██║██║
  ██║      ██╔══██║   ██║        ██║   ██║   ██║██║   ██║██║
  ╚██████╗ ██║  ██║   ██║        ██║   ╚██████╔╝╚██████╔╝███████╗
   ╚═════╝ ╚═╝  ╚═╝   ╚═╝        ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝[/bold cyan]
"""

CAT_FACE = """[bold yellow]
         /\\_/\\
        ( o.o )
         > ^ <
        /|   |\\
       (_|   |_)[/bold yellow]"""


def show_banner():
    """Display the main Cat Tool banner."""
    console.clear()
    banner_text = Text()
    banner_text.append("\n")
    banner_text.append("   ██████╗  █████╗ ████████╗", style="bold bright_cyan")
    banner_text.append("  ████████╗ ██████╗  ██████╗ ██╗\n", style="bold bright_magenta")
    banner_text.append("  ██╔════╝ ██╔══██╗╚══██╔══╝", style="bold bright_cyan")
    banner_text.append("  ╚══██╔══╝██╔═══██╗██╔═══██╗██║\n", style="bold bright_magenta")
    banner_text.append("  ██║      ███████║   ██║   ", style="bold bright_cyan")
    banner_text.append("     ██║   ██║   ██║██║   ██║██║\n", style="bold bright_magenta")
    banner_text.append("  ██║      ██╔══██║   ██║   ", style="bold bright_cyan")
    banner_text.append("     ██║   ██║   ██║██║   ██║██║\n", style="bold bright_magenta")
    banner_text.append("  ╚██████╗ ██║  ██║   ██║   ", style="bold bright_cyan")
    banner_text.append("     ██║   ╚██████╔╝╚██████╔╝███████╗\n", style="bold bright_magenta")
    banner_text.append("   ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ", style="bold bright_cyan")
    banner_text.append("     ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝\n", style="bold bright_magenta")

    console.print(banner_text)

    info_text = Text()
    info_text.append("         /\\_/\\\n", style="bold yellow")
    info_text.append("        ( o.o )  ", style="bold yellow")
    info_text.append("Advanced OSINT Intelligence Platform\n", style="bold white")
    info_text.append("         > ^ <   ", style="bold yellow")
    info_text.append("v1.0.0 ", style="dim white")
    info_text.append("| ", style="dim")
    info_text.append("No API Keys Required\n", style="bold green")

    console.print(Align.center(info_text))
    console.print()
    console.print(
        Panel(
            "[dim]Email Recon[/dim] [bold cyan]|[/bold cyan] "
            "[dim]Username Hunt[/dim] [bold cyan]|[/bold cyan] "
            "[dim]Social Media[/dim] [bold cyan]|[/bold cyan] "
            "[dim]Steam OSINT[/dim] [bold cyan]|[/bold cyan] "
            "[dim]Full Dossier[/dim]",
            border_style="bright_cyan",
            padding=(0, 2),
        )
    )
    console.print()


def show_module_header(module_name: str, icon: str = ""):
    """Display a module header."""
    console.print()
    console.print(
        Panel(
            f"[bold bright_cyan]{icon} {module_name}[/bold bright_cyan]",
            border_style="bright_magenta",
            padding=(0, 2),
        )
    )
    console.print()


def show_cat_thinking():
    """Show a thinking cat animation."""
    cat = Text()
    cat.append("    /\\_/\\\n", style="yellow")
    cat.append("   ( -.- )  ", style="yellow")
    cat.append("Analyzing...\n", style="dim italic")
    cat.append("    > ^ <\n", style="yellow")
    console.print(cat)

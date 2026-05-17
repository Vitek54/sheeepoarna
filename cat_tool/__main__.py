"""Cat Tool - Advanced OSINT Intelligence Platform.

Main entry point for the application.
Usage: python -m cat_tool
"""

import sys

from rich.console import Console

from cat_tool.core.banner import show_banner
from cat_tool.core.menu import (
    show_main_menu,
    get_input,
    confirm,
    press_enter,
    show_error,
    show_info,
    show_separator,
)
from cat_tool.modules.email_osint import run_email_scan
from cat_tool.modules.username_osint import run_username_scan
from cat_tool.modules.social_osint import run_social_scan
from cat_tool.modules.steam_osint import run_steam_scan
from cat_tool.modules.phone_osint import run_phone_scan

console = Console()


def run_full_dossier():
    """Run all OSINT modules in sequence."""
    console.print("\n[bold bright_cyan]Full Dossier Mode[/bold bright_cyan]")
    console.print("[dim]This will run all available OSINT modules.[/dim]\n")

    target = get_input("Enter target (email, username, or Steam ID)")

    if "@" in target:
        console.print("\n[bold]Detected: Email address[/bold]")
        show_separator()
        run_email_scan(target)

        local_part = target.split("@")[0]
        console.print(f"\n[bold]Auto-scanning username: {local_part}[/bold]")
        show_separator()
        run_username_scan(local_part)

        show_separator()
        run_social_scan(local_part)
    elif target.startswith("+7") or target.startswith("87") or target.startswith("89") or (target.startswith("7") and len(target) == 11) or (target.startswith("8") and len(target) == 11):
        console.print("\n[bold]Detected: Phone number[/bold]")
        show_separator()
        run_phone_scan(target)
    elif target.startswith("STEAM_") or target.startswith("[U:") or target.startswith("7656119") or "steamcommunity.com" in target:
        console.print("\n[bold]Detected: Steam ID[/bold]")
        show_separator()
        run_steam_scan(target)
    else:
        console.print(f"\n[bold]Scanning username: {target}[/bold]")
        show_separator()
        run_username_scan(target)

        show_separator()
        run_social_scan(target)

        if confirm("Also check Steam?"):
            show_separator()
            run_steam_scan(target)


def main():
    """Main application loop."""
    try:
        show_banner()

        while True:
            choice = show_main_menu()

            if choice == "0":
                cat_bye = """
[bold yellow]    /\\_/\\
   ( ^.^ )  [/bold yellow][bold bright_cyan]Thanks for using Cat Tool![/bold bright_cyan]
[bold yellow]    > ^ <
   /|   |\\[/bold yellow]  [dim]Stay curious, stay safe.[/dim]
"""
                console.print(cat_bye)
                sys.exit(0)

            elif choice == "1":
                email = get_input("Enter email address")
                run_email_scan(email)
                press_enter()

            elif choice == "2":
                username = get_input("Enter username / nickname")
                run_username_scan(username)
                press_enter()

            elif choice == "3":
                username = get_input("Enter username / nickname")
                run_social_scan(username)
                press_enter()

            elif choice == "4":
                steam_input = get_input("Enter Steam ID / Custom URL / Profile URL")
                run_steam_scan(steam_input)
                press_enter()

            elif choice == "5":
                phone_input = get_input("Enter phone number (Russian: +7/8...)")
                run_phone_scan(phone_input)
                press_enter()

            elif choice == "6":
                run_full_dossier()
                press_enter()

            else:
                show_error("Invalid option. Please select 0-6.")

            show_banner()

    except KeyboardInterrupt:
        console.print("\n\n[bold yellow]  /\\_/\\[/bold yellow]")
        console.print("[bold yellow] ( -.-)  [/bold yellow][dim]Interrupted. Goodbye![/dim]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()

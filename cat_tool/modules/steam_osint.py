"""Steam OSINT module for Cat Tool.

Comprehensive Steam account intelligence:
- SteamID conversion (all formats)
- Profile scraping
- Game library analysis
- Friends list extraction
- Historical nicknames
- VAC/trade ban status
- Community activity
- Links to external OSINT tools
"""

import re
import json
from typing import Optional
from urllib.parse import quote

from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree
from rich import box

from cat_tool.core.banner import show_module_header
from cat_tool.core.report import Report
from cat_tool.utils.http_client import get, DEFAULT_HEADERS
from cat_tool.utils.helpers import (
    validate_steam_id,
    steam_id64_to_steam_id,
    steam_id64_to_steam_id3,
    steam_id64_to_account_id,
    format_timestamp,
)

console = Console()


def resolve_vanity_url(custom_url: str) -> Optional[str]:
    """Resolve a custom Steam URL to SteamID64 by scraping the profile page."""
    url = f"https://steamcommunity.com/id/{custom_url}"
    resp = get(url)
    if resp and resp.status_code == 200:
        body = resp.text
        match = re.search(r'"steamid":"(\d+)"', body)
        if match:
            return match.group(1)
        match = re.search(r'g_rgProfileData\s*=\s*({[^}]+})', body)
        if match:
            try:
                data = json.loads(match.group(1))
                return data.get("steamid")
            except (json.JSONDecodeError, KeyError):
                pass
    return None


def scrape_steam_profile(steam_id64: str) -> dict:
    """Scrape Steam community profile page for detailed info."""
    profile = {
        "steam_id64": steam_id64,
        "persona_name": "N/A",
        "real_name": "N/A",
        "location": "N/A",
        "summary": "N/A",
        "avatar_url": "N/A",
        "custom_url": "N/A",
        "member_since": "N/A",
        "level": "N/A",
        "status": "N/A",
        "visibility": "N/A",
        "vac_banned": "N/A",
        "trade_ban": "N/A",
        "limited_account": "N/A",
        "profile_url": f"https://steamcommunity.com/profiles/{steam_id64}",
    }

    resp = get(f"https://steamcommunity.com/profiles/{steam_id64}")
    if not resp or resp.status_code != 200:
        return profile

    soup = BeautifulSoup(resp.text, "lxml")
    body = resp.text

    name_el = soup.find("span", class_="actual_persona_name")
    if name_el:
        profile["persona_name"] = name_el.text.strip()

    real_name_el = soup.find("div", class_="header_real_name")
    if real_name_el:
        bdi = real_name_el.find("bdi")
        if bdi:
            profile["real_name"] = bdi.text.strip()

    loc_el = soup.find("div", class_="header_real_name")
    if loc_el:
        loc_img = loc_el.find("img", class_="profile_flag")
        if loc_img:
            loc_text = loc_el.get_text(strip=True)
            loc_text = loc_text.replace(profile["real_name"], "").strip()
            if loc_text:
                profile["location"] = loc_text

    avatar = soup.find("div", class_="playerAvatarAutoSizeInner")
    if avatar:
        img = avatar.find("img")
        if img and img.get("src"):
            profile["avatar_url"] = img["src"]

    summary_el = soup.find("div", class_="profile_summary")
    if summary_el:
        profile["summary"] = summary_el.get_text(strip=True)[:300]

    custom_match = re.search(r'steamcommunity\.com/id/([^/"]+)', body)
    if custom_match:
        profile["custom_url"] = custom_match.group(1)

    member_el = soup.find("div", class_="profile_in_game_header")
    years_badge = soup.find("div", class_="badge_description")
    if years_badge:
        years_text = years_badge.get_text(strip=True)
        years_match = re.search(r'Member since (\w+ \d+, \d{4})', years_text)
        if years_match:
            profile["member_since"] = years_match.group(1)

    level_el = soup.find("span", class_="friendPlayerLevelNum")
    if level_el:
        profile["level"] = level_el.text.strip()

    if "Currently Online" in body:
        profile["status"] = "Online"
    elif "Currently In-Game" in body:
        profile["status"] = "In-Game"
        game_el = soup.find("div", class_="profile_in_game_name")
        if game_el:
            profile["status"] = f"In-Game: {game_el.text.strip()}"
    elif "Last Online" in body:
        profile["status"] = "Offline"
    else:
        profile["status"] = "Offline"

    if "This profile is private" in body:
        profile["visibility"] = "Private"
    elif "Friends Only" in body:
        profile["visibility"] = "Friends Only"
    else:
        profile["visibility"] = "Public"

    if "1 VAC ban" in body or "VAC ban" in body.lower():
        profile["vac_banned"] = "Yes"
        vac_match = re.search(r'(\d+)\s+day\(s\)\s+since\s+last\s+ban', body)
        if vac_match:
            profile["vac_banned"] = f"Yes ({vac_match.group(1)} days ago)"
    else:
        profile["vac_banned"] = "No"

    if "trade ban" in body.lower():
        profile["trade_ban"] = "Yes"
    else:
        profile["trade_ban"] = "No"

    if "Limited Account" in body:
        profile["limited_account"] = "Yes"
    else:
        profile["limited_account"] = "No"

    match = re.search(r'g_rgProfileData\s*=\s*({.*?});', body, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if data.get("personaname"):
                profile["persona_name"] = data["personaname"]
            if data.get("url"):
                profile["profile_url"] = data["url"]
        except (json.JSONDecodeError, KeyError):
            pass

    return profile


def scrape_steam_games(steam_id64: str) -> list[dict]:
    """Scrape public game list from Steam profile."""
    games = []
    resp = get(f"https://steamcommunity.com/profiles/{steam_id64}/games/?tab=all&sort=playtime")
    if not resp or resp.status_code != 200:
        return games

    body = resp.text
    match = re.search(r'var rgGames = (\[.*?\]);', body, re.DOTALL)
    if match:
        try:
            game_data = json.loads(match.group(1))
            for g in game_data:
                games.append({
                    "appid": g.get("appid", ""),
                    "name": g.get("name", "Unknown"),
                    "hours": round(g.get("hours_forever", 0), 1),
                    "hours_2weeks": round(g.get("hours", 0), 1),
                    "logo": g.get("logo", ""),
                })
        except (json.JSONDecodeError, KeyError):
            pass

    games.sort(key=lambda x: x.get("hours", 0), reverse=True)
    return games


def scrape_steam_friends(steam_id64: str) -> list[dict]:
    """Scrape public friends list from Steam profile."""
    friends = []
    resp = get(f"https://steamcommunity.com/profiles/{steam_id64}/friends/")
    if not resp or resp.status_code != 200:
        return friends

    soup = BeautifulSoup(resp.text, "lxml")
    friend_blocks = soup.find_all("div", class_="friend_block_v2")

    for block in friend_blocks[:50]:
        friend = {"name": "N/A", "steam_id64": "N/A", "profile_url": "N/A", "status": "Offline"}

        name_el = block.find("div", class_="friend_block_content")
        if name_el:
            friend["name"] = name_el.get_text(strip=True).split("\n")[0].strip()

        link = block.get("data-steamid")
        if link:
            friend["steam_id64"] = link
            friend["profile_url"] = f"https://steamcommunity.com/profiles/{link}"

        classes = block.get("class", [])
        if "in-game" in " ".join(classes):
            friend["status"] = "In-Game"
        elif "online" in " ".join(classes):
            friend["status"] = "Online"
        else:
            friend["status"] = "Offline"

        friends.append(friend)

    return friends


def scrape_steam_groups(steam_id64: str) -> list[dict]:
    """Scrape public groups from Steam profile."""
    groups = []
    resp = get(f"https://steamcommunity.com/profiles/{steam_id64}/groups/")
    if not resp or resp.status_code != 200:
        return groups

    soup = BeautifulSoup(resp.text, "lxml")
    group_blocks = soup.find_all("div", class_="group_block")

    for block in group_blocks[:30]:
        group = {"name": "N/A", "url": "N/A", "members": "N/A"}

        link = block.find("a", class_="linkTitle")
        if link:
            group["name"] = link.text.strip()
            group["url"] = link.get("href", "N/A")

        member_el = block.find("span", class_="groupMemberStat")
        if member_el:
            group["members"] = member_el.text.strip()

        groups.append(group)

    return groups


def get_nickname_history(steam_id64: str) -> list[str]:
    """Get nickname history from Steam profile page."""
    nicknames = []
    resp = get(f"https://steamcommunity.com/profiles/{steam_id64}/ajaxaliases/")
    if resp and resp.status_code == 200:
        try:
            data = resp.json()
            for entry in data:
                name = entry.get("newname", "")
                time = entry.get("timechanged", "")
                if name:
                    nicknames.append(f"{name} ({time})" if time else name)
        except (ValueError, KeyError):
            pass
    return nicknames


def get_steam_level(steam_id64: str) -> Optional[str]:
    """Get Steam level from profile badge page."""
    resp = get(f"https://steamcommunity.com/profiles/{steam_id64}/badges/")
    if resp and resp.status_code == 200:
        match = re.search(r'"friendPlayerLevelNum">(\d+)', resp.text)
        if match:
            return match.group(1)
    return None


def generate_osint_links(steam_id64: str, custom_url: str = "") -> dict:
    """Generate links to external OSINT tools based on the steam-osint repo."""
    links = {}
    sid = steam_id64
    vanity = custom_url or sid

    links["Steam Community Profile"] = f"https://steamcommunity.com/profiles/{sid}"
    links["Steam Community (Custom)"] = f"https://steamcommunity.com/id/{vanity}" if custom_url else "N/A"

    links["steamid.uk"] = f"https://steamid.uk/profile/{sid}"
    links["steamid.io"] = f"https://steamid.io/lookup/{sid}"
    links["steamidfinder.com"] = f"https://steamidfinder.com/lookup/{sid}/"
    links["findsteamid.com"] = f"https://findsteamid.com/?search={sid}"
    links["steamdb.info"] = f"https://steamdb.info/calculator/{sid}/"
    links["rep.tf"] = f"https://rep.tf/{sid}"
    links["steamhistory.net"] = f"https://steamhistory.net/id/{sid}"

    links["Web Archive Search"] = f"https://web.archive.org/web/*/steamcommunity.com/profiles/{sid}*"
    links["Cache Search (cipher387)"] = f"https://cipher387.github.io/quickcacheandarchivesearch/"

    links["Videos"] = f"https://steamcommunity.com/profiles/{sid}/videos"
    links["Screenshots"] = f"https://steamcommunity.com/profiles/{sid}/screenshots"
    links["Reviews"] = f"https://steamcommunity.com/profiles/{sid}/recommended"
    links["Workshop"] = f"https://steamcommunity.com/profiles/{sid}/myworkshopfiles/"
    links["Guides"] = f"https://steamcommunity.com/profiles/{sid}/myworkshopfiles/?section=guides"
    links["Artwork"] = f"https://steamcommunity.com/profiles/{sid}/images/"
    links["Inventory"] = f"https://steamcommunity.com/profiles/{sid}/inventory/"
    links["Wishlist"] = f"https://store.steampowered.com/wishlist/profiles/{sid}/"

    links["csstats.gg"] = f"https://csstats.gg/player/{sid}"
    links["faceitfinder.com"] = f"https://faceitfinder.com/profile/{sid}"
    links["faceittracker.net"] = f"https://faceittracker.net/profile/{sid}"
    links["opendota.com"] = f"https://www.opendota.com/players/{steam_id64_to_account_id(sid)}"
    links["stratz.com"] = f"https://stratz.com/players/{steam_id64_to_account_id(sid)}"
    links["logs.tf"] = f"https://logs.tf/profile/{sid}"
    links["trends.tf"] = f"https://trends.tf/player/{sid}/"
    links["rgl.gg"] = f"https://rgl.gg/Public/PlayerProfile.aspx?p={sid}"

    return links


def run_steam_scan(steam_input: str):
    """Run comprehensive Steam OSINT scan."""
    show_module_header("Steam Intelligence", "")

    parsed = validate_steam_id(steam_input)
    report = Report(steam_input, "Steam OSINT")

    with Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn("[bold white]{task.description}"),
        BarColumn(bar_width=30, style="cyan", complete_style="bright_cyan"),
        console=console,
    ) as progress:
        main_task = progress.add_task("Steam Intelligence Scan", total=8)

        progress.update(main_task, description="Resolving Steam ID...")
        steam_id64 = parsed.get("steam_id64")
        custom_url = parsed.get("custom_url", "")

        if not steam_id64 and custom_url:
            steam_id64 = resolve_vanity_url(custom_url)
            if not steam_id64:
                console.print(f"[bold red]Could not resolve custom URL: {custom_url}[/bold red]")
                return
        elif not steam_id64:
            console.print("[bold red]Invalid Steam ID format![/bold red]")
            return
        progress.advance(main_task)

        progress.update(main_task, description="Scraping profile...")
        profile = scrape_steam_profile(steam_id64)
        if not custom_url and profile.get("custom_url") and profile["custom_url"] != "N/A":
            custom_url = profile["custom_url"]
        progress.advance(main_task)

        progress.update(main_task, description="Fetching nickname history...")
        nicknames = get_nickname_history(steam_id64)
        progress.advance(main_task)

        progress.update(main_task, description="Scanning game library...")
        games = scrape_steam_games(steam_id64)
        progress.advance(main_task)

        progress.update(main_task, description="Scanning friends list...")
        friends = scrape_steam_friends(steam_id64)
        progress.advance(main_task)

        progress.update(main_task, description="Scanning groups...")
        groups = scrape_steam_groups(steam_id64)
        progress.advance(main_task)

        progress.update(main_task, description="Generating OSINT links...")
        osint_links = generate_osint_links(steam_id64, custom_url)
        progress.advance(main_task)

        progress.update(main_task, description="Building report...")
        progress.advance(main_task)

    steam_id = steam_id64_to_steam_id(steam_id64)
    steam_id3 = steam_id64_to_steam_id3(steam_id64)
    account_id = steam_id64_to_account_id(steam_id64)

    id_table = Table(
        title="[bold bright_cyan]Steam ID Conversion[/bold bright_cyan]",
        box=box.ROUNDED,
        border_style="bright_cyan",
        padding=(0, 1),
    )
    id_table.add_column("Format", style="bold white", min_width=18)
    id_table.add_column("Value", style="bright_cyan", overflow="fold")
    id_table.add_row("SteamID64", steam_id64)
    id_table.add_row("SteamID", steam_id)
    id_table.add_row("SteamID3", steam_id3)
    id_table.add_row("Account ID", str(account_id))
    id_table.add_row("Custom URL", custom_url if custom_url else "N/A")
    id_table.add_row("Profile URL", f"https://steamcommunity.com/profiles/{steam_id64}")
    console.print(id_table)
    console.print()

    profile_data = {
        "Persona Name": profile["persona_name"],
        "Real Name": profile["real_name"],
        "Location": profile["location"],
        "Level": profile.get("level", "N/A"),
        "Status": profile["status"],
        "Visibility": profile["visibility"],
        "Member Since": profile["member_since"],
        "VAC Banned": profile["vac_banned"],
        "Trade Ban": profile["trade_ban"],
        "Limited Account": profile["limited_account"],
        "Avatar URL": profile["avatar_url"],
    }
    report.display_key_value("Profile Information", profile_data, "bright_cyan")

    if profile["summary"] and profile["summary"] != "N/A":
        console.print(Panel(
            f"[white]{profile['summary']}[/white]",
            title="[bold bright_cyan]Profile Summary[/bold bright_cyan]",
            border_style="dim cyan",
            padding=(1, 2),
        ))
        console.print()

    if nicknames:
        nick_table = Table(
            title=f"[bold bright_yellow]Nickname History ({len(nicknames)} entries)[/bold bright_yellow]",
            box=box.ROUNDED,
            border_style="bright_yellow",
            show_lines=False,
        )
        nick_table.add_column("#", style="dim", width=4, justify="right")
        nick_table.add_column("Nickname", style="bold white", overflow="fold")
        for i, nick in enumerate(nicknames, 1):
            nick_table.add_row(str(i), nick)
        console.print(nick_table)
        console.print()
    else:
        console.print("[dim]No nickname history available[/dim]\n")

    if games:
        total_hours = sum(g.get("hours", 0) for g in games)
        game_table = Table(
            title=f"[bold bright_green]Game Library ({len(games)} games, {total_hours:.0f}h total)[/bold bright_green]",
            box=box.ROUNDED,
            border_style="bright_green",
            show_lines=False,
        )
        game_table.add_column("#", style="dim", width=4, justify="right")
        game_table.add_column("Game", style="bold white", min_width=30, overflow="fold")
        game_table.add_column("Total Hours", justify="right", style="bright_cyan")
        game_table.add_column("Last 2 Weeks", justify="right", style="bright_yellow")

        for i, g in enumerate(games[:25], 1):
            game_table.add_row(
                str(i),
                g["name"],
                f"{g['hours']}h",
                f"{g['hours_2weeks']}h" if g['hours_2weeks'] > 0 else "-",
            )

        if len(games) > 25:
            game_table.add_row("...", f"[dim]+{len(games) - 25} more games[/dim]", "", "")

        console.print(game_table)
        console.print()
    else:
        console.print("[dim]Game library is private or empty[/dim]\n")

    if friends:
        online_count = sum(1 for f in friends if f["status"] != "Offline")
        friend_table = Table(
            title=f"[bold bright_magenta]Friends List ({len(friends)} shown, {online_count} online)[/bold bright_magenta]",
            box=box.ROUNDED,
            border_style="bright_magenta",
            show_lines=False,
        )
        friend_table.add_column("#", style="dim", width=4, justify="right")
        friend_table.add_column("Name", style="bold white", min_width=20, overflow="fold")
        friend_table.add_column("SteamID64", style="bright_cyan")
        friend_table.add_column("Status", justify="center")

        for i, f in enumerate(friends[:20], 1):
            status_style = "bold green" if f["status"] == "Online" else ("bold yellow" if f["status"] == "In-Game" else "dim")
            friend_table.add_row(
                str(i),
                f["name"],
                f["steam_id64"],
                f"[{status_style}]{f['status']}[/{status_style}]",
            )

        if len(friends) > 20:
            friend_table.add_row("...", f"[dim]+{len(friends) - 20} more friends[/dim]", "", "")

        console.print(friend_table)
        console.print()
    else:
        console.print("[dim]Friends list is private or empty[/dim]\n")

    if groups:
        group_table = Table(
            title=f"[bold bright_yellow]Groups ({len(groups)})[/bold bright_yellow]",
            box=box.ROUNDED,
            border_style="bright_yellow",
            show_lines=False,
        )
        group_table.add_column("#", style="dim", width=4, justify="right")
        group_table.add_column("Name", style="bold white", min_width=25, overflow="fold")
        group_table.add_column("Members", style="bright_cyan", justify="right")

        for i, g in enumerate(groups[:15], 1):
            group_table.add_row(str(i), g["name"], g["members"])
        console.print(group_table)
        console.print()

    osint_tree = Tree("[bold bright_cyan]External OSINT Tools[/bold bright_cyan]")

    categories = {
        "ID & Profile Lookup": ["steamid.uk", "steamid.io", "steamidfinder.com", "findsteamid.com", "steamdb.info", "rep.tf", "steamhistory.net"],
        "Profile Content": ["Videos", "Screenshots", "Reviews", "Workshop", "Guides", "Artwork", "Inventory", "Wishlist"],
        "Game Statistics": ["csstats.gg", "faceitfinder.com", "faceittracker.net", "opendota.com", "stratz.com", "logs.tf", "trends.tf", "rgl.gg"],
        "Archive & Cache": ["Web Archive Search", "Cache Search (cipher387)"],
    }

    for cat_name, keys in categories.items():
        branch = osint_tree.add(f"[bold yellow]{cat_name}[/bold yellow]")
        for key in keys:
            url = osint_links.get(key, "N/A")
            if url and url != "N/A":
                branch.add(f"[bold]{key}:[/bold] [underline blue]{url}[/underline blue]")

    console.print(Panel(osint_tree, border_style="bright_cyan", padding=(1, 2)))
    console.print()

    stats = {
        "SteamID64": steam_id64,
        "Persona Name": profile["persona_name"],
        "Nickname History": len(nicknames),
        "Games Owned": len(games),
        "Total Playtime": f"{sum(g.get('hours', 0) for g in games):.0f}h" if games else "N/A",
        "Friends Visible": len(friends),
        "Groups": len(groups),
        "VAC Status": profile["vac_banned"],
    }

    report.add_section("steam_ids", {
        "steam_id64": steam_id64,
        "steam_id": steam_id,
        "steam_id3": steam_id3,
        "account_id": account_id,
        "custom_url": custom_url,
    })
    report.add_section("profile", profile)
    report.add_section("nicknames", nicknames)
    report.add_section("games", games[:25])
    report.add_section("friends", friends[:20])
    report.add_section("groups", groups)
    report.add_section("osint_links", osint_links)
    report.set_stats(stats)
    report.display_summary()

    try:
        report.export_json()
    except Exception:
        pass

    return report

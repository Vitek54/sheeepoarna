"""Social Media OSINT module for Cat Tool.

Deep social media profiling across major platforms.
Extracts public profile data, metadata, and cross-references.
"""

import asyncio
import re
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from cat_tool.core.banner import show_module_header
from cat_tool.core.report import Report
from cat_tool.utils.http_client import get, DEFAULT_HEADERS, run_async

console = Console()


SOCIAL_PLATFORMS = {
    "instagram": {
        "name": "Instagram",
        "url": "https://www.instagram.com/{}/",
        "icon": "IG",
        "profile_api": "https://www.instagram.com/api/v1/users/web_profile_info/?username={}",
    },
    "twitter": {
        "name": "Twitter / X",
        "url": "https://x.com/{}",
        "icon": "X",
    },
    "tiktok": {
        "name": "TikTok",
        "url": "https://www.tiktok.com/@{}",
        "icon": "TT",
    },
    "github": {
        "name": "GitHub",
        "url": "https://github.com/{}",
        "api": "https://api.github.com/users/{}",
        "icon": "GH",
    },
    "reddit": {
        "name": "Reddit",
        "url": "https://www.reddit.com/user/{}/",
        "api": "https://www.reddit.com/user/{}/about.json",
        "icon": "RD",
    },
    "telegram": {
        "name": "Telegram",
        "url": "https://t.me/{}",
        "icon": "TG",
    },
    "youtube": {
        "name": "YouTube",
        "url": "https://www.youtube.com/@{}",
        "icon": "YT",
    },
    "twitch": {
        "name": "Twitch",
        "url": "https://www.twitch.tv/{}",
        "icon": "TW",
    },
    "vk": {
        "name": "VKontakte",
        "url": "https://vk.com/{}",
        "icon": "VK",
    },
    "linkedin": {
        "name": "LinkedIn",
        "url": "https://www.linkedin.com/in/{}/",
        "icon": "LI",
    },
    "pinterest": {
        "name": "Pinterest",
        "url": "https://www.pinterest.com/{}/",
        "icon": "PN",
    },
    "snapchat": {
        "name": "Snapchat",
        "url": "https://www.snapchat.com/add/{}",
        "icon": "SC",
    },
    "discord": {
        "name": "Discord (lookup)",
        "url": "https://discord.com",
        "icon": "DC",
    },
    "facebook": {
        "name": "Facebook",
        "url": "https://www.facebook.com/{}",
        "icon": "FB",
    },
    "soundcloud": {
        "name": "SoundCloud",
        "url": "https://soundcloud.com/{}",
        "icon": "SC",
    },
    "spotify": {
        "name": "Spotify",
        "url": "https://open.spotify.com/user/{}",
        "icon": "SP",
    },
    "medium": {
        "name": "Medium",
        "url": "https://medium.com/@{}",
        "icon": "MD",
    },
    "devto": {
        "name": "Dev.to",
        "url": "https://dev.to/{}",
        "icon": "DV",
    },
}


def check_github_profile(username: str) -> dict:
    """Deep check GitHub profile via public API."""
    result = {"exists": False, "data": {}}
    resp = get(f"https://api.github.com/users/{username}")
    if resp and resp.status_code == 200:
        try:
            data = resp.json()
            result["exists"] = True
            result["data"] = {
                "Username": data.get("login", "N/A"),
                "Display Name": data.get("name") or "N/A",
                "Bio": data.get("bio") or "N/A",
                "Location": data.get("location") or "N/A",
                "Company": data.get("company") or "N/A",
                "Blog": data.get("blog") or "N/A",
                "Public Repos": str(data.get("public_repos", 0)),
                "Public Gists": str(data.get("public_gists", 0)),
                "Followers": str(data.get("followers", 0)),
                "Following": str(data.get("following", 0)),
                "Created": data.get("created_at", "N/A")[:10],
                "Avatar": data.get("avatar_url", "N/A"),
                "Profile URL": data.get("html_url", "N/A"),
                "Twitter": data.get("twitter_username") or "N/A",
                "Hireable": str(data.get("hireable") or "N/A"),
            }
        except (ValueError, KeyError):
            pass
    return result


def check_reddit_profile(username: str) -> dict:
    """Deep check Reddit profile."""
    result = {"exists": False, "data": {}}
    headers = {**DEFAULT_HEADERS, "Accept": "application/json"}
    resp = get(f"https://www.reddit.com/user/{username}/about.json", headers=headers)
    if resp and resp.status_code == 200:
        try:
            data = resp.json().get("data", {})
            if data.get("name"):
                result["exists"] = True
                result["data"] = {
                    "Username": data.get("name", "N/A"),
                    "Display Name": data.get("subreddit", {}).get("title") or "N/A",
                    "Comment Karma": str(data.get("comment_karma", 0)),
                    "Link Karma": str(data.get("link_karma", 0)),
                    "Total Karma": str(data.get("total_karma", 0)),
                    "Created": data.get("created_utc", "N/A"),
                    "Is Gold": str(data.get("is_gold", False)),
                    "Verified": str(data.get("verified", False)),
                    "Has Verified Email": str(data.get("has_verified_email", False)),
                    "Profile URL": f"https://www.reddit.com/user/{username}",
                }
        except (ValueError, KeyError):
            pass
    return result


async def check_social_profile(session: aiohttp.ClientSession, platform_key: str, username: str) -> dict:
    """Check if username exists on a social platform."""
    platform = SOCIAL_PLATFORMS[platform_key]
    url = platform["url"].format(username)
    result = {
        "platform": platform["name"],
        "icon": platform.get("icon", ""),
        "url": url,
        "exists": False,
        "status": 0,
    }

    try:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=12),
            allow_redirects=True,
            ssl=False,
        ) as resp:
            result["status"] = resp.status

            if resp.status == 200:
                body = await resp.text()
                if platform_key == "telegram":
                    if "tgme_page_title" in body or 'class="tgme_page_photo_image"' in body:
                        result["exists"] = True
                    elif "If you have <strong>Telegram</strong>" in body:
                        result["exists"] = False
                    else:
                        result["exists"] = False
                elif "page not found" in body.lower() or "404" in body[:500].lower() or "not found" in body[:500].lower():
                    result["exists"] = False
                else:
                    result["exists"] = True
            elif resp.status in (301, 302, 303, 307):
                result["exists"] = True
            else:
                result["exists"] = False

    except Exception:
        result["exists"] = False

    return result


async def scan_social_async(username: str, progress=None, task_id=None) -> list[dict]:
    """Scan all social platforms asynchronously."""
    connector = aiohttp.TCPConnector(limit=20, ssl=False)
    results = []

    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS, connector=connector) as session:
        semaphore = asyncio.Semaphore(20)

        async def limited_check(key):
            async with semaphore:
                r = await check_social_profile(session, key, username)
                if progress and task_id is not None:
                    progress.advance(task_id)
                return r

        tasks = [limited_check(k) for k in SOCIAL_PLATFORMS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    return [r for r in results if isinstance(r, dict)]


def run_social_scan(username: str):
    """Run comprehensive social media OSINT scan."""
    show_module_header("Social Media Intelligence", "")

    if not username or len(username) < 2:
        console.print("[bold red]Username too short![/bold red]")
        return

    report = Report(username, "Social Media OSINT")
    console.print(f"[bold]Target:[/bold] [bright_cyan]{username}[/bright_cyan]")
    console.print(f"[bold]Platforms:[/bold] [bright_cyan]{len(SOCIAL_PLATFORMS)}[/bright_cyan]")
    console.print()

    with Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn("[bold white]{task.description}"),
        BarColumn(bar_width=40, style="cyan", complete_style="bright_green"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning social platforms...", total=len(SOCIAL_PLATFORMS) + 2)

        social_results = run_async(scan_social_async(username, progress, task))

        progress.update(task, description="Deep profiling GitHub...")
        github_deep = check_github_profile(username)
        progress.advance(task)

        progress.update(task, description="Deep profiling Reddit...")
        reddit_deep = check_reddit_profile(username)
        progress.advance(task)

    found = [r for r in social_results if r.get("exists")]
    not_found = [r for r in social_results if not r.get("exists")]

    if found:
        table = Table(
            title=f"[bold bright_green]Social Profiles Found ({len(found)})[/bold bright_green]",
            box=box.DOUBLE_EDGE,
            border_style="bright_green",
            show_lines=False,
            padding=(0, 1),
        )
        table.add_column("#", style="dim", width=4, justify="right")
        table.add_column("Platform", style="bold cyan", min_width=15)
        table.add_column("URL", style="underline blue", overflow="fold")
        table.add_column("Status", justify="center", width=10)

        for i, r in enumerate(found, 1):
            table.add_row(
                str(i),
                f"[{r['icon']}] {r['platform']}",
                r["url"],
                f"[bold green]{r['status']}[/bold green]",
            )
        console.print(table)
        console.print()

    if not_found:
        names = ", ".join(r["platform"] for r in not_found)
        console.print(f"[dim]Not found on: {names}[/dim]\n")

    if github_deep["exists"]:
        report.display_key_value("GitHub Deep Profile", github_deep["data"], "bright_green")

    if reddit_deep["exists"]:
        report.display_key_value("Reddit Deep Profile", reddit_deep["data"], "bright_yellow")

    additional_links = {
        "Google Search": f"https://www.google.com/search?q=%22{username}%22",
        "Yandex Search": f"https://yandex.ru/search/?text=%22{username}%22",
        "Wayback Machine": f"https://web.archive.org/web/*/{username}*",
        "Google Images": f"https://www.google.com/search?tbm=isch&q=%22{username}%22",
        "DuckDuckGo": f"https://duckduckgo.com/?q=%22{username}%22",
    }
    report.display_key_value("Additional Research Links", additional_links, "bright_yellow")

    stats = {
        "Total Platforms": len(SOCIAL_PLATFORMS),
        "Profiles Found": len(found),
        "Not Found": len(not_found),
        "GitHub Deep Profile": "Yes" if github_deep["exists"] else "No",
        "Reddit Deep Profile": "Yes" if reddit_deep["exists"] else "No",
    }

    report.add_section("social_profiles", {"found": [{"platform": r["platform"], "url": r["url"]} for r in found]})
    if github_deep["exists"]:
        report.add_section("github_deep", github_deep["data"])
    if reddit_deep["exists"]:
        report.add_section("reddit_deep", reddit_deep["data"])
    report.set_stats(stats)
    report.display_summary()

    try:
        report.export_json()
    except Exception:
        pass

    return report

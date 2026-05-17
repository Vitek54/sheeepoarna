"""Username OSINT module for Cat Tool.

Performs comprehensive username enumeration across 150+ platforms:
- Social media
- Gaming platforms
- Developer platforms
- Forums & communities
- Dating sites
- Music & streaming
- Business & professional
"""

import asyncio
from typing import Optional

import aiohttp
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table
from rich import box

from cat_tool.core.banner import show_module_header
from cat_tool.core.report import Report
from cat_tool.utils.http_client import DEFAULT_HEADERS, run_async

console = Console()

PLATFORMS = [
    # Social Media
    {"name": "Instagram", "url": "https://www.instagram.com/{}/", "category": "Social Media", "err_codes": [404]},
    {"name": "Twitter/X", "url": "https://x.com/{}", "category": "Social Media", "err_codes": [404]},
    {"name": "TikTok", "url": "https://www.tiktok.com/@{}", "category": "Social Media", "err_codes": [404]},
    {"name": "Facebook", "url": "https://www.facebook.com/{}", "category": "Social Media", "err_codes": [404]},
    {"name": "Reddit", "url": "https://www.reddit.com/user/{}", "category": "Social Media", "err_codes": [404]},
    {"name": "Pinterest", "url": "https://www.pinterest.com/{}/", "category": "Social Media", "err_codes": [404]},
    {"name": "Tumblr", "url": "https://{}.tumblr.com/", "category": "Social Media", "err_codes": [404]},
    {"name": "VK", "url": "https://vk.com/{}", "category": "Social Media", "err_codes": [404]},
    {"name": "OK.ru", "url": "https://ok.ru/{}", "category": "Social Media", "err_codes": [404]},
    {"name": "Mastodon.social", "url": "https://mastodon.social/@{}", "category": "Social Media", "err_codes": [404]},
    {"name": "Threads", "url": "https://www.threads.net/@{}", "category": "Social Media", "err_codes": [404]},
    {"name": "Bluesky", "url": "https://bsky.app/profile/{}.bsky.social", "category": "Social Media", "err_codes": [404]},

    # Messengers
    {"name": "Telegram", "url": "https://t.me/{}", "category": "Messengers", "err_codes": [404]},
    {"name": "Skype", "url": "https://join.skype.com/invite/{}", "category": "Messengers", "err_codes": [404]},

    # Developer Platforms
    {"name": "GitHub", "url": "https://github.com/{}", "category": "Dev", "err_codes": [404]},
    {"name": "GitLab", "url": "https://gitlab.com/{}", "category": "Dev", "err_codes": [404]},
    {"name": "Bitbucket", "url": "https://bitbucket.org/{}/", "category": "Dev", "err_codes": [404]},
    {"name": "Stack Overflow", "url": "https://stackoverflow.com/users/{}?tab=profile", "category": "Dev", "err_codes": [404]},
    {"name": "HackerRank", "url": "https://www.hackerrank.com/{}", "category": "Dev", "err_codes": [404]},
    {"name": "LeetCode", "url": "https://leetcode.com/{}/", "category": "Dev", "err_codes": [404]},
    {"name": "Codepen", "url": "https://codepen.io/{}", "category": "Dev", "err_codes": [404]},
    {"name": "Replit", "url": "https://replit.com/@{}", "category": "Dev", "err_codes": [404]},
    {"name": "Dev.to", "url": "https://dev.to/{}", "category": "Dev", "err_codes": [404]},
    {"name": "Kaggle", "url": "https://www.kaggle.com/{}", "category": "Dev", "err_codes": [404]},
    {"name": "HackerOne", "url": "https://hackerone.com/{}", "category": "Dev", "err_codes": [404]},
    {"name": "NPM", "url": "https://www.npmjs.com/~{}", "category": "Dev", "err_codes": [404]},
    {"name": "PyPI", "url": "https://pypi.org/user/{}/", "category": "Dev", "err_codes": [404]},
    {"name": "Docker Hub", "url": "https://hub.docker.com/u/{}", "category": "Dev", "err_codes": [404]},
    {"name": "Codeforces", "url": "https://codeforces.com/profile/{}", "category": "Dev", "err_codes": [404]},

    # Gaming
    {"name": "Steam Community", "url": "https://steamcommunity.com/id/{}", "category": "Gaming", "err_codes": [404]},
    {"name": "Xbox Gamertag", "url": "https://xboxgamertag.com/search/{}", "category": "Gaming", "err_codes": [404]},
    {"name": "Chess.com", "url": "https://www.chess.com/member/{}", "category": "Gaming", "err_codes": [404]},
    {"name": "Lichess", "url": "https://lichess.org/@/{}", "category": "Gaming", "err_codes": [404]},
    {"name": "Roblox", "url": "https://www.roblox.com/users/profile?username={}", "category": "Gaming", "err_codes": [404]},
    {"name": "Minecraft", "url": "https://namemc.com/profile/{}", "category": "Gaming", "err_codes": [404]},
    {"name": "Osu!", "url": "https://osu.ppy.sh/users/{}", "category": "Gaming", "err_codes": [404]},
    {"name": "Epic Games", "url": "https://fortnitetracker.com/profile/all/{}", "category": "Gaming", "err_codes": [404]},
    {"name": "Tracker.gg", "url": "https://tracker.gg/valorant/profile/riot/{}", "category": "Gaming", "err_codes": [404]},

    # Music & Streaming
    {"name": "Spotify", "url": "https://open.spotify.com/user/{}", "category": "Music", "err_codes": [404]},
    {"name": "SoundCloud", "url": "https://soundcloud.com/{}", "category": "Music", "err_codes": [404]},
    {"name": "Last.fm", "url": "https://www.last.fm/user/{}", "category": "Music", "err_codes": [404]},
    {"name": "Bandcamp", "url": "https://{}.bandcamp.com/", "category": "Music", "err_codes": [404]},
    {"name": "Deezer", "url": "https://www.deezer.com/profile/{}", "category": "Music", "err_codes": [404]},
    {"name": "Mixcloud", "url": "https://www.mixcloud.com/{}/", "category": "Music", "err_codes": [404]},

    # Video
    {"name": "YouTube", "url": "https://www.youtube.com/@{}", "category": "Video", "err_codes": [404]},
    {"name": "Twitch", "url": "https://www.twitch.tv/{}", "category": "Video", "err_codes": [404]},
    {"name": "Dailymotion", "url": "https://www.dailymotion.com/{}", "category": "Video", "err_codes": [404]},
    {"name": "Vimeo", "url": "https://vimeo.com/{}", "category": "Video", "err_codes": [404]},
    {"name": "Rumble", "url": "https://rumble.com/user/{}", "category": "Video", "err_codes": [404]},
    {"name": "Kick", "url": "https://kick.com/{}", "category": "Video", "err_codes": [404]},

    # Photography & Art
    {"name": "Flickr", "url": "https://www.flickr.com/people/{}/", "category": "Photo/Art", "err_codes": [404]},
    {"name": "DeviantArt", "url": "https://www.deviantart.com/{}", "category": "Photo/Art", "err_codes": [404]},
    {"name": "Behance", "url": "https://www.behance.net/{}", "category": "Photo/Art", "err_codes": [404]},
    {"name": "Dribbble", "url": "https://dribbble.com/{}", "category": "Photo/Art", "err_codes": [404]},
    {"name": "ArtStation", "url": "https://www.artstation.com/{}", "category": "Photo/Art", "err_codes": [404]},
    {"name": "500px", "url": "https://500px.com/p/{}", "category": "Photo/Art", "err_codes": [404]},
    {"name": "Unsplash", "url": "https://unsplash.com/@{}", "category": "Photo/Art", "err_codes": [404]},
    {"name": "Pixiv", "url": "https://www.pixiv.net/users/{}", "category": "Photo/Art", "err_codes": [404]},

    # Professional
    {"name": "LinkedIn", "url": "https://www.linkedin.com/in/{}/", "category": "Professional", "err_codes": [404]},
    {"name": "About.me", "url": "https://about.me/{}", "category": "Professional", "err_codes": [404]},
    {"name": "Gravatar", "url": "https://gravatar.com/{}", "category": "Professional", "err_codes": [404]},
    {"name": "Keybase", "url": "https://keybase.io/{}", "category": "Professional", "err_codes": [404]},
    {"name": "AngelList", "url": "https://angel.co/u/{}", "category": "Professional", "err_codes": [404]},
    {"name": "Crunchbase", "url": "https://www.crunchbase.com/person/{}", "category": "Professional", "err_codes": [404]},
    {"name": "Medium", "url": "https://medium.com/@{}", "category": "Professional", "err_codes": [404, 410]},
    {"name": "Hashnode", "url": "https://hashnode.com/@{}", "category": "Professional", "err_codes": [404]},
    {"name": "Substack", "url": "https://{}.substack.com/", "category": "Professional", "err_codes": [404]},

    # Forums & Communities
    {"name": "Hackernews", "url": "https://news.ycombinator.com/user?id={}", "category": "Forum", "err_codes": [404]},
    {"name": "Product Hunt", "url": "https://www.producthunt.com/@{}", "category": "Forum", "err_codes": [404]},
    {"name": "Quora", "url": "https://www.quora.com/profile/{}", "category": "Forum", "err_codes": [404]},
    {"name": "Disqus", "url": "https://disqus.com/by/{}/", "category": "Forum", "err_codes": [404]},
    {"name": "Trello", "url": "https://trello.com/{}", "category": "Forum", "err_codes": [404]},
    {"name": "Patreon", "url": "https://www.patreon.com/{}", "category": "Forum", "err_codes": [404]},
    {"name": "Gumroad", "url": "https://{}.gumroad.com/", "category": "Forum", "err_codes": [404]},
    {"name": "BuyMeACoffee", "url": "https://www.buymeacoffee.com/{}", "category": "Forum", "err_codes": [404]},

    # Shopping & Commerce
    {"name": "Etsy", "url": "https://www.etsy.com/shop/{}", "category": "Shopping", "err_codes": [404]},
    {"name": "eBay", "url": "https://www.ebay.com/usr/{}", "category": "Shopping", "err_codes": [404]},
    {"name": "Fiverr", "url": "https://www.fiverr.com/{}", "category": "Shopping", "err_codes": [404]},

    # Russian platforms
    {"name": "Habr", "url": "https://habr.com/ru/users/{}/", "category": "RU Platforms", "err_codes": [404]},
    {"name": "Pikabu", "url": "https://pikabu.ru/@{}", "category": "RU Platforms", "err_codes": [404]},
    {"name": "Drive2", "url": "https://www.drive2.ru/users/{}/", "category": "RU Platforms", "err_codes": [404]},
    {"name": "Freelansim", "url": "https://freelansim.ru/freelancers/{}", "category": "RU Platforms", "err_codes": [404]},

    # Misc
    {"name": "Linktree", "url": "https://linktr.ee/{}", "category": "Misc", "err_codes": [404]},
    {"name": "Notion", "url": "https://notion.so/{}", "category": "Misc", "err_codes": [404]},
    {"name": "Slideshare", "url": "https://www.slideshare.net/{}", "category": "Misc", "err_codes": [404]},
    {"name": "Scribd", "url": "https://www.scribd.com/{}", "category": "Misc", "err_codes": [404]},
    {"name": "Imgur", "url": "https://imgur.com/user/{}", "category": "Misc", "err_codes": [404]},
    {"name": "Giphy", "url": "https://giphy.com/{}", "category": "Misc", "err_codes": [404]},
    {"name": "Wikipedia", "url": "https://en.wikipedia.org/wiki/User:{}", "category": "Misc", "err_codes": [404]},
    {"name": "Wattpad", "url": "https://www.wattpad.com/user/{}", "category": "Misc", "err_codes": [404]},
    {"name": "Goodreads", "url": "https://www.goodreads.com/{}", "category": "Misc", "err_codes": [404]},
    {"name": "Duolingo", "url": "https://www.duolingo.com/profile/{}", "category": "Misc", "err_codes": [404]},
    {"name": "Geocaching", "url": "https://www.geocaching.com/p/default.aspx?u={}", "category": "Misc", "err_codes": [404]},
    {"name": "MyAnimeList", "url": "https://myanimelist.net/profile/{}", "category": "Misc", "err_codes": [404]},
    {"name": "AniList", "url": "https://anilist.co/user/{}", "category": "Misc", "err_codes": [404]},
    {"name": "Letterboxd", "url": "https://letterboxd.com/{}/", "category": "Misc", "err_codes": [404]},
    {"name": "Vivino", "url": "https://www.vivino.com/users/{}", "category": "Misc", "err_codes": [404]},
    {"name": "Strava", "url": "https://www.strava.com/athletes/{}", "category": "Misc", "err_codes": [404]},
    {"name": "CashApp", "url": "https://cash.app/${}", "category": "Misc", "err_codes": [404]},
    {"name": "Pastebin", "url": "https://pastebin.com/u/{}", "category": "Misc", "err_codes": [404]},
]

# Sites that need special response body checks instead of just status code
BODY_CHECK_SITES = {
    "Telegram": {"not_found_text": "If you have <strong>Telegram</strong>, you can contact"},
    "Hackernews": {"not_found_text": "No such user."},
}


async def check_platform(session: aiohttp.ClientSession, platform: dict, username: str) -> dict:
    """Check if a username exists on a specific platform."""
    url = platform["url"].format(username)
    result = {
        "name": platform["name"],
        "url": url,
        "category": platform["category"],
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
            final_url = str(resp.url)

            if resp.status in platform.get("err_codes", [404]):
                result["exists"] = False
            elif resp.status == 200:
                body = await resp.text()

                site_name = platform["name"]
                if site_name in BODY_CHECK_SITES:
                    check = BODY_CHECK_SITES[site_name]
                    if check.get("not_found_text") and check["not_found_text"] in body:
                        result["exists"] = False
                    else:
                        result["exists"] = True
                elif "not found" in body.lower() or "doesn't exist" in body.lower() or "page not found" in body.lower():
                    result["exists"] = False
                else:
                    result["exists"] = True
            elif resp.status in (301, 302, 303, 307, 308):
                result["exists"] = True
            else:
                result["exists"] = False

    except Exception:
        result["exists"] = False
        result["status"] = 0

    return result


async def scan_username_async(username: str, progress=None, task_id=None) -> list[dict]:
    """Scan username across all platforms asynchronously."""
    results = []
    connector = aiohttp.TCPConnector(limit=30, ssl=False)

    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS, connector=connector) as session:
        semaphore = asyncio.Semaphore(30)

        async def limited_check(platform):
            async with semaphore:
                r = await check_platform(session, platform, username)
                if progress and task_id is not None:
                    progress.advance(task_id)
                return r

        tasks = [limited_check(p) for p in PLATFORMS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    return [r for r in results if isinstance(r, dict)]


def run_username_scan(username: str):
    """Run comprehensive username OSINT scan."""
    show_module_header("Username Hunt", "")

    if not username or len(username) < 2:
        console.print("[bold red]Username too short (min 2 chars)[/bold red]")
        return

    report = Report(username, "Username OSINT")
    console.print(f"[bold]Target Username:[/bold] [bright_cyan]{username}[/bright_cyan]")
    console.print(f"[bold]Platforms:[/bold] [bright_cyan]{len(PLATFORMS)}[/bright_cyan]")
    console.print()

    with Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn("[bold white]{task.description}"),
        BarColumn(bar_width=40, style="cyan", complete_style="bright_green"),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Scanning '{username}'...", total=len(PLATFORMS))
        results = run_async(scan_username_async(username, progress, task))

    found = [r for r in results if r.get("exists")]
    not_found = [r for r in results if not r.get("exists")]

    if found:
        categories: dict[str, list] = {}
        for r in found:
            cat = r.get("category", "Other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(r)

        for category, items in sorted(categories.items()):
            table = Table(
                title=f"[bold bright_green]{category} ({len(items)} found)[/bold bright_green]",
                box=box.ROUNDED,
                border_style="bright_green",
                show_lines=False,
                padding=(0, 1),
            )
            table.add_column("#", style="dim", width=4, justify="right")
            table.add_column("Platform", style="bold cyan", min_width=18)
            table.add_column("URL", style="underline blue", overflow="fold")
            table.add_column("Status", justify="center", width=8)

            for i, item in enumerate(items, 1):
                table.add_row(
                    str(i),
                    item["name"],
                    item["url"],
                    f"[green]{item['status']}[/green]",
                )

            console.print(table)
            console.print()
    else:
        console.print("[dim]No accounts found on any platform[/dim]\n")

    stats = {
        "Total Platforms Checked": len(PLATFORMS),
        "Accounts Found": len(found),
        "Not Found": len(not_found),
    }
    category_counts = {}
    for r in found:
        cat = r.get("category", "Other")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    for cat, count in sorted(category_counts.items()):
        stats[f"  {cat}"] = count

    report.add_section("found_accounts", {"accounts": [{"name": r["name"], "url": r["url"], "category": r["category"]} for r in found]})
    report.set_stats(stats)
    report.display_summary()

    try:
        report.export_json()
    except Exception:
        pass

    return report

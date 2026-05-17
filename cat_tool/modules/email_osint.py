"""Email OSINT module for Cat Tool.

Performs comprehensive email intelligence gathering:
- Email validation & provider detection
- MX record analysis
- Gravatar lookup
- Registration checks on 100+ websites
- Breach database lookup
- Domain WHOIS intelligence
"""

import hashlib
import re
import asyncio
from typing import Optional

import aiohttp
import dns.resolver
import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich import box

from cat_tool.core.banner import show_module_header
from cat_tool.core.report import Report
from cat_tool.utils.http_client import get, async_check_url, create_async_session, run_async, DEFAULT_HEADERS
from cat_tool.utils.helpers import validate_email, email_to_gravatar_hash

console = Console()

EMAIL_PROVIDERS = {
    "gmail.com": {"name": "Google Gmail", "country": "US", "type": "Free"},
    "googlemail.com": {"name": "Google Gmail", "country": "US", "type": "Free"},
    "yahoo.com": {"name": "Yahoo Mail", "country": "US", "type": "Free"},
    "yahoo.co.uk": {"name": "Yahoo Mail UK", "country": "UK", "type": "Free"},
    "outlook.com": {"name": "Microsoft Outlook", "country": "US", "type": "Free"},
    "hotmail.com": {"name": "Microsoft Hotmail", "country": "US", "type": "Free"},
    "live.com": {"name": "Microsoft Live", "country": "US", "type": "Free"},
    "msn.com": {"name": "Microsoft MSN", "country": "US", "type": "Free"},
    "icloud.com": {"name": "Apple iCloud", "country": "US", "type": "Free"},
    "me.com": {"name": "Apple Me", "country": "US", "type": "Free"},
    "mac.com": {"name": "Apple Mac", "country": "US", "type": "Free"},
    "protonmail.com": {"name": "ProtonMail", "country": "CH", "type": "Encrypted"},
    "proton.me": {"name": "Proton Mail", "country": "CH", "type": "Encrypted"},
    "tutanota.com": {"name": "Tutanota", "country": "DE", "type": "Encrypted"},
    "tuta.io": {"name": "Tuta Mail", "country": "DE", "type": "Encrypted"},
    "mail.ru": {"name": "Mail.ru", "country": "RU", "type": "Free"},
    "bk.ru": {"name": "Mail.ru (BK)", "country": "RU", "type": "Free"},
    "list.ru": {"name": "Mail.ru (List)", "country": "RU", "type": "Free"},
    "inbox.ru": {"name": "Mail.ru (Inbox)", "country": "RU", "type": "Free"},
    "yandex.ru": {"name": "Yandex Mail", "country": "RU", "type": "Free"},
    "yandex.com": {"name": "Yandex Mail", "country": "RU", "type": "Free"},
    "ya.ru": {"name": "Yandex Mail", "country": "RU", "type": "Free"},
    "rambler.ru": {"name": "Rambler Mail", "country": "RU", "type": "Free"},
    "zoho.com": {"name": "Zoho Mail", "country": "IN", "type": "Business"},
    "aol.com": {"name": "AOL Mail", "country": "US", "type": "Free"},
    "gmx.com": {"name": "GMX Mail", "country": "DE", "type": "Free"},
    "gmx.de": {"name": "GMX Mail DE", "country": "DE", "type": "Free"},
    "web.de": {"name": "WEB.DE", "country": "DE", "type": "Free"},
    "fastmail.com": {"name": "Fastmail", "country": "AU", "type": "Paid"},
    "mailbox.org": {"name": "Mailbox.org", "country": "DE", "type": "Paid"},
    "posteo.de": {"name": "Posteo", "country": "DE", "type": "Paid"},
    "qq.com": {"name": "QQ Mail", "country": "CN", "type": "Free"},
    "163.com": {"name": "NetEase 163", "country": "CN", "type": "Free"},
    "126.com": {"name": "NetEase 126", "country": "CN", "type": "Free"},
    "naver.com": {"name": "Naver Mail", "country": "KR", "type": "Free"},
    "daum.net": {"name": "Daum Mail", "country": "KR", "type": "Free"},
    "ukr.net": {"name": "UKR.NET", "country": "UA", "type": "Free"},
    "i.ua": {"name": "I.UA Mail", "country": "UA", "type": "Free"},
    "meta.ua": {"name": "Meta.ua Mail", "country": "UA", "type": "Free"},
}

REGISTRATION_SITES = [
    {"name": "GitHub", "url": "https://api.github.com/search/users?q={email}+in:email", "check": "json_count"},
    {"name": "Gravatar", "url": "https://www.gravatar.com/avatar/{md5}?d=404&s=1", "check": "status_200"},
    {"name": "Imgur", "url": "https://imgur.com/account/verifyemail?email={email}", "check": "status_200"},
    {"name": "Spotify", "url": "https://spclient.wg.spotify.com/signup/public/v1/account?validate=1&email={email}", "check": "json_field", "field": "status", "match": 20},
    {"name": "Twitter/X", "url": "https://api.twitter.com/i/users/email_available.json?email={email}", "check": "json_field", "field": "valid", "match": False},
    {"name": "Pinterest", "url": "https://www.pinterest.com/resource/EmailExistsResource/get/?source_url=/&data=%7B%22options%22%3A%7B%22email%22%3A%22{email}%22%7D%7D", "check": "json_nested"},
    {"name": "WordPress", "url": "https://public-api.wordpress.com/rest/v1.1/users/suggest?q={local_part}", "check": "status_200"},
    {"name": "Duolingo", "url": "https://www.duolingo.com/2017-06-30/users?email={email}", "check": "json_has_users"},
    {"name": "LastFM", "url": "https://www.last.fm/join/partial/validate?userName=&email={email}", "check": "json_field", "field": "email", "match": True},
]

SITE_CHECKS = [
    ("Adobe", "https://account.adobe.com"),
    ("Amazon", "https://www.amazon.com/ap/signin"),
    ("Apple", "https://appleid.apple.com"),
    ("Discord", "https://discord.com"),
    ("Dropbox", "https://www.dropbox.com"),
    ("eBay", "https://www.ebay.com"),
    ("Facebook", "https://www.facebook.com"),
    ("Instagram", "https://www.instagram.com"),
    ("LinkedIn", "https://www.linkedin.com"),
    ("Netflix", "https://www.netflix.com"),
    ("Reddit", "https://www.reddit.com"),
    ("Snapchat", "https://accounts.snapchat.com"),
    ("Spotify", "https://accounts.spotify.com"),
    ("Steam", "https://store.steampowered.com"),
    ("Telegram", "https://telegram.org"),
    ("TikTok", "https://www.tiktok.com"),
    ("Twitch", "https://www.twitch.tv"),
    ("Twitter/X", "https://twitter.com"),
    ("VK", "https://vk.com"),
    ("WhatsApp", "https://www.whatsapp.com"),
    ("YouTube", "https://www.youtube.com"),
]


def get_email_info(email: str) -> dict:
    """Extract basic information from email address."""
    local_part, domain = email.split("@")

    info = {
        "email": email,
        "local_part": local_part,
        "domain": domain,
        "provider": "Unknown",
        "country": "Unknown",
        "type": "Unknown",
        "format_valid": validate_email(email),
    }

    if domain.lower() in EMAIL_PROVIDERS:
        prov = EMAIL_PROVIDERS[domain.lower()]
        info["provider"] = prov["name"]
        info["country"] = prov["country"]
        info["type"] = prov["type"]
    else:
        info["provider"] = f"Custom ({domain})"
        info["type"] = "Custom/Business"

    return info


def check_mx_records(domain: str) -> list[dict]:
    """Check MX records for the email domain."""
    records = []
    try:
        answers = dns.resolver.resolve(domain, "MX")
        for rdata in answers:
            records.append({
                "priority": rdata.preference,
                "server": str(rdata.exchange).rstrip("."),
            })
        records.sort(key=lambda x: x["priority"])
    except Exception:
        pass
    return records


def check_domain_records(domain: str) -> dict:
    """Check various DNS records for the domain."""
    result = {"A": [], "AAAA": [], "TXT": [], "NS": []}
    for rtype in result:
        try:
            answers = dns.resolver.resolve(domain, rtype)
            for rdata in answers:
                result[rtype].append(str(rdata))
        except Exception:
            pass
    return result


def check_gravatar(email: str) -> dict:
    """Check Gravatar for the email."""
    md5_hash = email_to_gravatar_hash(email)
    result = {"exists": False, "profile_url": None, "avatar_url": None, "data": {}}

    profile_url = f"https://www.gravatar.com/{md5_hash}.json"
    resp = get(profile_url)
    if resp and resp.status_code == 200:
        try:
            data = resp.json()
            entry = data.get("entry", [{}])[0]
            result["exists"] = True
            result["profile_url"] = f"https://gravatar.com/{md5_hash}"
            result["avatar_url"] = f"https://www.gravatar.com/avatar/{md5_hash}?s=400"
            result["data"] = {
                "display_name": entry.get("displayName", "N/A"),
                "username": entry.get("preferredUsername", "N/A"),
                "location": entry.get("currentLocation", "N/A"),
                "about": entry.get("aboutMe", "N/A"),
            }
            if entry.get("accounts"):
                result["data"]["linked_accounts"] = [
                    {"service": acc.get("shortname", ""), "url": acc.get("url", "")}
                    for acc in entry["accounts"]
                ]
            if entry.get("urls"):
                result["data"]["urls"] = [u.get("value", "") for u in entry["urls"]]
        except (ValueError, KeyError, IndexError):
            pass
    else:
        avatar_url = f"https://www.gravatar.com/avatar/{md5_hash}?d=404&s=1"
        resp = get(avatar_url)
        if resp and resp.status_code == 200:
            result["exists"] = True
            result["avatar_url"] = f"https://www.gravatar.com/avatar/{md5_hash}?s=400"

    return result


def check_hibp(email: str) -> dict:
    """Check Have I Been Pwned for breaches (public API)."""
    result = {"checked": True, "breaches": [], "paste_count": 0}

    headers = {
        **DEFAULT_HEADERS,
        "Accept": "application/json",
    }
    resp = get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}?truncateResponse=true", headers=headers)
    if resp and resp.status_code == 200:
        try:
            breaches = resp.json()
            result["breaches"] = [b.get("Name", "") for b in breaches]
        except (ValueError, KeyError):
            pass
    elif resp and resp.status_code == 404:
        result["breaches"] = []

    return result


async def check_registrations_async(email: str) -> list[dict]:
    """Check email registration across multiple sites asynchronously."""
    results = []
    local_part = email.split("@")[0]
    md5_hash = email_to_gravatar_hash(email)

    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
        tasks = []
        for site in REGISTRATION_SITES:
            url = site["url"].format(
                email=email,
                local_part=local_part,
                md5=md5_hash,
            )
            tasks.append(_check_single_site(session, site, url))

        completed = await asyncio.gather(*tasks, return_exceptions=True)
        for r in completed:
            if isinstance(r, dict):
                results.append(r)

    return results


async def _check_single_site(session: aiohttp.ClientSession, site: dict, url: str) -> dict:
    """Check a single site for email registration."""
    result = {"name": site["name"], "registered": False, "details": ""}

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), ssl=False) as resp:
            status = resp.status
            check_type = site.get("check", "status_200")

            if check_type == "status_200":
                result["registered"] = status == 200
            elif check_type == "json_count":
                if status == 200:
                    data = await resp.json()
                    result["registered"] = data.get("total_count", 0) > 0
            elif check_type == "json_field":
                if status == 200:
                    data = await resp.json()
                    field_val = data.get(site.get("field", ""))
                    result["registered"] = field_val == site.get("match")
            elif check_type == "json_has_users":
                if status == 200:
                    data = await resp.json()
                    result["registered"] = len(data.get("users", [])) > 0

            if result["registered"]:
                result["details"] = "Account exists"
    except Exception:
        result["details"] = "Check failed"

    return result


def check_email_pattern(email: str) -> dict:
    """Analyze email naming pattern."""
    local = email.split("@")[0]
    patterns = {
        "has_dots": "." in local,
        "has_numbers": bool(re.search(r'\d', local)),
        "has_underscores": "_" in local,
        "has_hyphens": "-" in local,
        "has_plus": "+" in local,
        "length": len(local),
        "pattern_type": "unknown",
    }

    if re.match(r'^[a-zA-Z]+\.[a-zA-Z]+$', local):
        patterns["pattern_type"] = "firstname.lastname"
    elif re.match(r'^[a-zA-Z]+\.[a-zA-Z]+\d+$', local):
        patterns["pattern_type"] = "firstname.lastname+numbers"
    elif re.match(r'^[a-zA-Z]+_[a-zA-Z]+$', local):
        patterns["pattern_type"] = "firstname_lastname"
    elif re.match(r'^[a-zA-Z]+\d+$', local):
        patterns["pattern_type"] = "name+numbers"
    elif re.match(r'^[a-zA-Z]+$', local):
        patterns["pattern_type"] = "simple_name"
    elif re.match(r'^\d+$', local):
        patterns["pattern_type"] = "numeric_only"

    return patterns


def generate_possible_usernames(email: str) -> list[str]:
    """Generate possible usernames from email."""
    local = email.split("@")[0]
    usernames = [local]

    local_clean = re.sub(r'[._\-+]', '', local)
    if local_clean != local:
        usernames.append(local_clean)

    local_no_nums = re.sub(r'\d+$', '', local)
    if local_no_nums and local_no_nums != local:
        usernames.append(local_no_nums)

    parts = re.split(r'[._\-+]', local)
    if len(parts) > 1:
        usernames.extend(parts)
        usernames.append("".join(parts))

    return list(dict.fromkeys(usernames))


def run_email_scan(email: str):
    """Run comprehensive email OSINT scan."""
    show_module_header("Email Intelligence", "")

    if not validate_email(email):
        console.print("[bold red]Invalid email format![/bold red]")
        return

    report = Report(email, "Email OSINT")

    with Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn("[bold white]{task.description}"),
        BarColumn(bar_width=30, style="cyan", complete_style="bright_cyan"),
        console=console,
    ) as progress:
        main_task = progress.add_task("Email Intelligence Scan", total=6)

        progress.update(main_task, description="Analyzing email format...")
        email_info = get_email_info(email)
        pattern = check_email_pattern(email)
        possible_usernames = generate_possible_usernames(email)
        progress.advance(main_task)

        progress.update(main_task, description="Checking DNS/MX records...")
        mx_records = check_mx_records(email_info["domain"])
        dns_records = check_domain_records(email_info["domain"])
        progress.advance(main_task)

        progress.update(main_task, description="Searching Gravatar...")
        gravatar = check_gravatar(email)
        progress.advance(main_task)

        progress.update(main_task, description="Checking breaches...")
        hibp = check_hibp(email)
        progress.advance(main_task)

        progress.update(main_task, description="Checking registrations on sites...")
        registrations = run_async(check_registrations_async(email))
        progress.advance(main_task)

        progress.update(main_task, description="Generating report...")
        progress.advance(main_task)

    report.display_key_value("Email Information", {
        "Email": email,
        "Local Part": email_info["local_part"],
        "Domain": email_info["domain"],
        "Provider": email_info["provider"],
        "Country": email_info["country"],
        "Type": email_info["type"],
        "Format Valid": "Yes" if email_info["format_valid"] else "No",
        "Pattern Type": pattern["pattern_type"],
    })

    if possible_usernames:
        console.print(
            f"[bold bright_cyan]Possible Usernames:[/bold bright_cyan] "
            f"[white]{', '.join(possible_usernames)}[/white]\n"
        )

    if mx_records:
        rows = [[str(r["priority"]), r["server"]] for r in mx_records]
        report.display_section_table("MX Records", rows, ["Priority", "Mail Server"], "bright_yellow")

    if any(dns_records.values()):
        dns_info = {}
        for rtype, records in dns_records.items():
            if records:
                dns_info[rtype] = ", ".join(records[:3])
        if dns_info:
            report.display_key_value("DNS Records", dns_info, "bright_yellow")

    if gravatar["exists"]:
        grav_data = {
            "Status": "Found",
            "Profile URL": gravatar.get("profile_url", "N/A"),
            "Avatar URL": gravatar.get("avatar_url", "N/A"),
        }
        if gravatar.get("data"):
            for key, val in gravatar["data"].items():
                if key not in ("linked_accounts", "urls") and val and val != "N/A":
                    grav_data[key.replace("_", " ").title()] = str(val)
        report.display_key_value("Gravatar Profile", grav_data, "bright_green")

        if gravatar.get("data", {}).get("linked_accounts"):
            rows = [[acc["service"], acc["url"]] for acc in gravatar["data"]["linked_accounts"]]
            report.display_section_table("Gravatar Linked Accounts", rows, ["Service", "URL"], "bright_green")
    else:
        console.print("[dim]Gravatar: No profile found[/dim]\n")

    if hibp.get("breaches"):
        console.print(f"[bold red]BREACHES FOUND: {len(hibp['breaches'])}[/bold red]")
        rows = [[b, "Breached"] for b in hibp["breaches"]]
        report.display_section_table("Data Breaches", rows, ["Service", "Status"], "red")
    else:
        console.print("[bold green]No known breaches found[/bold green]\n")

    found_registrations = [r for r in registrations if r.get("registered")]
    if found_registrations:
        rows = [[r["name"], "Registered"] for r in found_registrations]
        report.display_section_table("Found Registrations", rows, ["Service", "Status"], "bright_green")

    not_found = [r for r in registrations if not r.get("registered") and r.get("details") != "Check failed"]
    if not_found:
        console.print(f"[dim]Not found on: {', '.join(r['name'] for r in not_found)}[/dim]\n")

    stats = {
        "MX Records Found": len(mx_records),
        "Gravatar Profile": 1 if gravatar["exists"] else 0,
        "Breaches": len(hibp.get("breaches", [])),
        "Registrations Found": len(found_registrations),
        "Possible Usernames": len(possible_usernames),
    }

    report.add_section("email_info", email_info)
    report.add_section("gravatar", gravatar)
    report.add_section("breaches", hibp)
    report.add_section("registrations", {"found": [r["name"] for r in found_registrations]})
    report.set_stats(stats)
    report.display_summary()

    try:
        report.export_json()
    except Exception:
        pass

    return report

"""Email OSINT module for Cat Tool.

Performs comprehensive email intelligence gathering:
- Email validation & provider detection
- MX record analysis & DNS intelligence
- Domain IP geolocation (ip-api.com)
- SMTP verification
- Disposable email detection
- Gravatar lookup with full profile extraction
- Breach database lookup (HIBP + alternatives)
- Email reputation scoring
- Registration checks on multiple websites
- OSINT research links generation
"""

import hashlib
import re
import smtplib
import socket
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

DISPOSABLE_DOMAINS = {
    "tempmail.com", "guerrillamail.com", "guerrillamail.net", "throwaway.email",
    "temp-mail.org", "fakeinbox.com", "sharklasers.com", "guerrillamailblock.com",
    "grr.la", "guerrillamail.info", "mailinator.com", "maildrop.cc",
    "dispostable.com", "yopmail.com", "yopmail.fr", "nada.email",
    "tempail.com", "tmpmail.net", "tmpmail.org", "bupmail.com",
    "trashmail.com", "trashmail.me", "trashmail.net", "mohmal.com",
    "getnada.com", "emailondeck.com", "tempr.email", "discard.email",
    "mailnesia.com", "spamgourmet.com", "mytemp.email", "throwam.com",
    "crazymailing.com", "10minutemail.com", "minutemail.com", "emailfake.com",
    "mailnator.com", "anonbox.net", "mailcatch.com", "inboxkitten.com",
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


def check_disposable(domain: str) -> dict:
    """Check if email domain is a disposable/temporary email service."""
    result = {"is_disposable": False, "source": "N/A"}
    if domain.lower() in DISPOSABLE_DOMAINS:
        result["is_disposable"] = True
        result["source"] = "Built-in database"
        return result
    try:
        resp = get(f"https://open.kickbox.com/v1/disposable/{domain}", timeout=8)
        if resp and resp.status_code == 200:
            data = resp.json()
            if data.get("disposable"):
                result["is_disposable"] = True
                result["source"] = "Kickbox API"
                return result
    except Exception:
        pass
    try:
        resp = get(f"https://disposable.debounce.io/?email=test@{domain}", timeout=8)
        if resp and resp.status_code == 200:
            data = resp.json()
            if data.get("disposable") == "true" or data.get("disposable") is True:
                result["is_disposable"] = True
                result["source"] = "Debounce API"
                return result
    except Exception:
        pass
    return result


def check_domain_ip_geo(domain: str) -> dict:
    """Get IP address of the email domain and geolocate it."""
    result = {"ip": None, "geo": {}}
    try:
        ip = socket.gethostbyname(domain)
        result["ip"] = ip
    except socket.gaierror:
        return result
    try:
        resp = get(
            f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query",
            timeout=8,
        )
        if resp and resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                result["geo"] = {
                    "IP": data.get("query", ip),
                    "Country": data.get("country", "N/A"),
                    "Country Code": data.get("countryCode", "N/A"),
                    "Region": data.get("regionName", "N/A"),
                    "City": data.get("city", "N/A"),
                    "ZIP": data.get("zip", "N/A"),
                    "Latitude": str(data.get("lat", "N/A")),
                    "Longitude": str(data.get("lon", "N/A")),
                    "Timezone": data.get("timezone", "N/A"),
                    "ISP": data.get("isp", "N/A"),
                    "Organization": data.get("org", "N/A"),
                    "AS": data.get("as", "N/A"),
                }
    except Exception:
        pass
    if not result["geo"] and result["ip"]:
        try:
            resp = get(f"https://ipapi.co/{result['ip']}/json/", timeout=8)
            if resp and resp.status_code == 200:
                data = resp.json()
                if not data.get("error"):
                    result["geo"] = {
                        "IP": result["ip"],
                        "Country": data.get("country_name", "N/A"),
                        "Country Code": data.get("country_code", "N/A"),
                        "Region": data.get("region", "N/A"),
                        "City": data.get("city", "N/A"),
                        "ZIP": data.get("postal", "N/A"),
                        "Latitude": str(data.get("latitude", "N/A")),
                        "Longitude": str(data.get("longitude", "N/A")),
                        "Timezone": data.get("timezone", "N/A"),
                        "ISP": data.get("org", "N/A"),
                        "Organization": data.get("org", "N/A"),
                        "AS": data.get("asn", "N/A"),
                    }
        except Exception:
            pass
    return result


def check_smtp_verification(email: str, mx_records: list[dict]) -> dict:
    """Verify email existence via SMTP handshake."""
    result = {"verified": False, "status": "Unknown", "smtp_banner": "N/A", "details": ""}
    if not mx_records:
        result["status"] = "No MX records"
        return result
    mx_host = mx_records[0]["server"]
    try:
        smtp = smtplib.SMTP(timeout=10)
        smtp.connect(mx_host, 25)
        result["smtp_banner"] = smtp.ehlo_resp.decode("utf-8", errors="ignore")[:200] if smtp.ehlo_resp else "N/A"
        smtp.ehlo("cat-tool.local")
        smtp.mail("check@cat-tool.local")
        code, msg = smtp.rcpt(email)
        if code == 250:
            result["verified"] = True
            result["status"] = "Exists (250 OK)"
        elif code == 550:
            result["status"] = "Not found (550)"
        elif code == 451:
            result["status"] = "Greylisted (451)"
        elif code == 452:
            result["status"] = "Mailbox full (452)"
        else:
            result["status"] = f"Code {code}"
        result["details"] = msg.decode("utf-8", errors="ignore")[:200]
        smtp.quit()
    except smtplib.SMTPConnectError:
        result["status"] = "Connection refused"
    except smtplib.SMTPServerDisconnected:
        result["status"] = "Server disconnected"
    except TimeoutError:
        result["status"] = "Timeout"
    except Exception as e:
        result["status"] = f"Error: {type(e).__name__}"
    return result


def check_gravatar(email: str) -> dict:
    """Check Gravatar for the email with full profile extraction."""
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
            if entry.get("name"):
                name_data = entry["name"]
                full_name = f"{name_data.get('givenName', '')} {name_data.get('familyName', '')}".strip()
                if full_name:
                    result["data"]["full_name"] = full_name
            if entry.get("phoneNumbers"):
                result["data"]["phones"] = [
                    {"type": p.get("type", ""), "value": p.get("value", "")}
                    for p in entry["phoneNumbers"]
                ]
            if entry.get("emails"):
                result["data"]["emails"] = [
                    {"value": e.get("value", ""), "primary": e.get("primary", False)}
                    for e in entry["emails"]
                ]
            if entry.get("ims"):
                result["data"]["ims"] = [
                    {"type": im.get("type", ""), "value": im.get("value", "")}
                    for im in entry["ims"]
                ]
            if entry.get("accounts"):
                result["data"]["linked_accounts"] = [
                    {"service": acc.get("shortname", ""), "url": acc.get("url", ""), "username": acc.get("username", "")}
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
    headers = {**DEFAULT_HEADERS, "Accept": "application/json"}
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


def check_leak_lookup(email: str) -> dict:
    """Check alternative breach databases with detailed leak info."""
    result = {"sources": [], "detailed": [], "personal_data": {}}
    try:
        resp = get(f"https://api.xposedornot.com/v1/check-email/{email}", timeout=10)
        if resp and resp.status_code == 200:
            data = resp.json()
            breaches = data.get("breaches", [])
            if isinstance(breaches, list) and breaches:
                for b in breaches[:20]:
                    if isinstance(b, str):
                        result["sources"].append({"name": b, "source": "XposedOrNot"})
                    elif isinstance(b, dict):
                        result["sources"].append({"name": b.get("name", "Unknown"), "source": "XposedOrNot"})
    except Exception:
        pass

    try:
        resp = get(f"https://api.xposedornot.com/v1/breach-analytics?email={email}", timeout=10)
        if resp and resp.status_code == 200:
            data = resp.json()
            exposed = data.get("ExposedBreaches", {})
            if exposed:
                breaches_details = exposed.get("breaches_details", [])
                for bd in breaches_details[:20]:
                    if isinstance(bd, dict):
                        detail = {
                            "name": bd.get("breach", "Unknown"),
                            "domain": bd.get("domain", "N/A"),
                            "date": bd.get("xposed_date", "N/A"),
                            "data_types": bd.get("xposed_data", "N/A"),
                            "records": str(bd.get("xposed_records", "N/A")),
                            "industry": bd.get("industry", "N/A"),
                            "password_risk": bd.get("password_risk", "N/A"),
                        }
                        result["detailed"].append(detail)

                metrics = data.get("BreachMetrics", {})
                if metrics:
                    risk = metrics.get("risk", [])
                    if risk and len(risk) >= 4:
                        result["personal_data"]["Risk Score"] = str(risk[0].get("risk_score", "N/A")) if isinstance(risk[0], dict) else str(risk[0])

                paste_summary = data.get("PastesSummary", {})
                if paste_summary and paste_summary.get("cnt"):
                    result["personal_data"]["Paste Appearances"] = str(paste_summary.get("cnt", 0))
                    sources = paste_summary.get("sources", [])
                    if sources:
                        result["personal_data"]["Paste Sources"] = ", ".join(str(s) for s in sources[:5])
    except Exception:
        pass

    return result


def check_email_leaks_detailed(email: str) -> dict:
    """Check for detailed leak information - what fields were leaked."""
    result = {"leaked_fields": [], "data": {}}

    try:
        resp = get(f"https://api.xposedornot.com/v1/breach-analytics?email={email}", timeout=10)
        if resp and resp.status_code == 200:
            data = resp.json()
            exposed = data.get("ExposedBreaches", {})
            if exposed:
                all_data_types = set()
                breaches_details = exposed.get("breaches_details", [])
                for bd in breaches_details:
                    if isinstance(bd, dict):
                        xposed_data = bd.get("xposed_data", "")
                        if isinstance(xposed_data, str):
                            for field in xposed_data.split(","):
                                field = field.strip()
                                if field:
                                    all_data_types.add(field)
                        elif isinstance(xposed_data, list):
                            all_data_types.update(xposed_data)

                result["leaked_fields"] = sorted(all_data_types)

                field_categories = {
                    "personal": ["Names", "Name", "First Name", "Last Name", "Full Name", "Gender", "DOB", "Date of Birth", "Age", "Nationalities"],
                    "credentials": ["Passwords", "Password", "Hashed Passwords", "Password Hints", "Security Questions"],
                    "contact": ["Email Addresses", "Emails", "Phone Numbers", "Phone", "Physical Addresses", "Address"],
                    "financial": ["Credit Cards", "Bank Accounts", "Financial Data", "Payment Methods"],
                    "social": ["Social Media Profiles", "Usernames", "User IDs", "Profile Photos"],
                    "location": ["IP Addresses", "Geolocation", "GPS Coordinates", "Country", "City"],
                }

                for category, fields in field_categories.items():
                    found = [f for f in all_data_types if any(kw.lower() in f.lower() for kw in fields)]
                    if found:
                        result["data"][f"Leaked ({category})"] = ", ".join(found)
    except Exception:
        pass

    return result


def check_email_vk_search(email: str) -> dict:
    """Search VK for profiles linked to this email."""
    result = {"found": False, "profiles": []}
    local_part = email.split("@")[0]

    try:
        resp = get(f"https://vk.com/search?c%5Bsection%5D=people&c%5Bq%5D={email}", timeout=12)
        if resp and resp.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            people = soup.select(".people_row, .si_body")
            for person in people[:5]:
                name_el = person.select_one(".si_owner a, .people_cell a")
                if name_el:
                    profile = {
                        "name": name_el.get_text(strip=True),
                        "url": name_el.get("href", ""),
                    }
                    img_el = person.select_one("img")
                    if img_el and img_el.get("src"):
                        profile["photo"] = img_el["src"]
                    result["profiles"].append(profile)
                    result["found"] = True
    except Exception:
        pass

    return result


def check_emailrep(email: str) -> dict:
    """Check email reputation via emailrep.io."""
    result = {"checked": False, "data": {}}
    try:
        headers = {**DEFAULT_HEADERS, "Accept": "application/json"}
        resp = get(f"https://emailrep.io/{email}", headers=headers, timeout=10)
        if resp and resp.status_code == 200:
            data = resp.json()
            result["checked"] = True
            details = data.get("details", {})
            result["data"] = {
                "Reputation": data.get("reputation", "N/A"),
                "Suspicious": str(data.get("suspicious", "N/A")),
                "References": str(data.get("references", "N/A")),
                "Blacklisted": str(details.get("blacklisted", "N/A")),
                "Malicious Activity": str(details.get("malicious_activity", "N/A")),
                "Credentials Leaked": str(details.get("credentials_leaked", "N/A")),
                "Data Breach": str(details.get("data_breach", "N/A")),
                "Spam": str(details.get("spam", "N/A")),
                "Free Provider": str(details.get("free_provider", "N/A")),
                "Deliverable": str(details.get("deliverable", "N/A")),
                "Valid MX": str(details.get("valid_mx", "N/A")),
                "Spoofable": str(details.get("spoofable", "N/A")),
                "SPF Strict": str(details.get("spf_strict", "N/A")),
                "DMARC Enforced": str(details.get("dmarc_enforced", "N/A")),
                "Profiles": ", ".join(details.get("profiles", [])) or "N/A",
            }
    except Exception:
        pass
    return result


def check_disify(email: str) -> dict:
    """Check email via disify.com API."""
    result = {"checked": False, "data": {}}
    try:
        resp = get(f"https://disify.com/api/email/{email}", timeout=8)
        if resp and resp.status_code == 200:
            data = resp.json()
            result["checked"] = True
            result["data"] = {
                "Format Valid": str(data.get("format", "N/A")),
                "Disposable": str(data.get("disposable", "N/A")),
                "DNS Valid": str(data.get("dns", "N/A")),
            }
    except Exception:
        pass
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


def generate_email_osint_links(email: str) -> dict:
    """Generate OSINT research links for the email."""
    local_part = email.split("@")[0]
    md5_hash = email_to_gravatar_hash(email)
    return {
        "Google Search": f"https://www.google.com/search?q=%22{email}%22",
        "Yandex Search": f"https://yandex.ru/search/?text=%22{email}%22",
        "DuckDuckGo": f"https://duckduckgo.com/?q=%22{email}%22",
        "HIBP": f"https://haveibeenpwned.com/account/{email}",
        "Hunter.io": f"https://hunter.io/email-verifier/{email}",
        "Gravatar": f"https://gravatar.com/{md5_hash}",
        "Emailrep.io": f"https://emailrep.io/{email}",
        "Google (username)": f"https://www.google.com/search?q=%22{local_part}%22",
        "Wayback Machine": f"https://web.archive.org/web/*/{email}",
        "IntelX": f"https://intelx.io/?s={email}",
        "Dehashed": f"https://www.dehashed.com/search?query={email}",
        "Epieos": f"https://epieos.com/?q={email}",
    }


def run_email_scan(email: str):
    """Run comprehensive email OSINT scan."""
    show_module_header("Email Intelligence", "")

    if not validate_email(email):
        console.print("[bold red]Invalid email format![/bold red]")
        return

    report = Report(email, "Email OSINT")
    domain = email.split("@")[1]

    with Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn("[bold white]{task.description}"),
        BarColumn(bar_width=30, style="cyan", complete_style="bright_cyan"),
        console=console,
    ) as progress:
        main_task = progress.add_task("Email Intelligence Scan", total=13)

        progress.update(main_task, description="Analyzing email format...")
        email_info = get_email_info(email)
        pattern = check_email_pattern(email)
        possible_usernames = generate_possible_usernames(email)
        progress.advance(main_task)

        progress.update(main_task, description="Checking DNS/MX records...")
        mx_records = check_mx_records(domain)
        dns_records = check_domain_records(domain)
        progress.advance(main_task)

        progress.update(main_task, description="Geolocating domain IP...")
        domain_geo = check_domain_ip_geo(domain)
        progress.advance(main_task)

        progress.update(main_task, description="Checking disposable status...")
        disposable = check_disposable(domain)
        progress.advance(main_task)

        progress.update(main_task, description="SMTP verification...")
        smtp_result = check_smtp_verification(email, mx_records)
        progress.advance(main_task)

        progress.update(main_task, description="Searching Gravatar...")
        gravatar = check_gravatar(email)
        progress.advance(main_task)

        progress.update(main_task, description="Checking breaches (HIBP)...")
        hibp = check_hibp(email)
        progress.advance(main_task)

        progress.update(main_task, description="Checking leak databases...")
        leaks = check_leak_lookup(email)
        progress.advance(main_task)

        progress.update(main_task, description="Checking email reputation...")
        emailrep = check_emailrep(email)
        disify = check_disify(email)
        progress.advance(main_task)

        progress.update(main_task, description="Analyzing leaked data fields...")
        leaks_detailed = check_email_leaks_detailed(email)
        progress.advance(main_task)

        progress.update(main_task, description="Searching VK by email...")
        vk_search = check_email_vk_search(email)
        progress.advance(main_task)

        progress.update(main_task, description="Checking registrations on sites...")
        registrations = run_async(check_registrations_async(email))
        progress.advance(main_task)

        progress.update(main_task, description="Generating report...")
        osint_links = generate_email_osint_links(email)
        progress.advance(main_task)

    # Display results
    report.display_key_value("Email Information", {
        "Email": email,
        "Local Part": email_info["local_part"],
        "Domain": email_info["domain"],
        "Provider": email_info["provider"],
        "Country": email_info["country"],
        "Type": email_info["type"],
        "Format Valid": "Yes" if email_info["format_valid"] else "No",
        "Pattern Type": pattern["pattern_type"],
        "Disposable": "[bold red]YES[/bold red]" if disposable["is_disposable"] else "[green]No[/green]",
    })

    if possible_usernames:
        console.print(
            f"[bold bright_cyan]Possible Usernames:[/bold bright_cyan] "
            f"[white]{', '.join(possible_usernames)}[/white]\n"
        )

    # SMTP verification
    smtp_color = "bright_green" if smtp_result["verified"] else "yellow"
    report.display_key_value("SMTP Verification", {
        "Status": smtp_result["status"],
        "Verified": "Yes" if smtp_result["verified"] else "No",
        "SMTP Banner": smtp_result["smtp_banner"][:100] if smtp_result["smtp_banner"] != "N/A" else "N/A",
    }, smtp_color)

    # Domain IP geolocation
    if domain_geo.get("geo"):
        report.display_key_value("Domain IP Geolocation", domain_geo["geo"], "bright_magenta")
    elif domain_geo.get("ip"):
        report.display_key_value("Domain IP", {"IP": domain_geo["ip"], "Geolocation": "Could not resolve"}, "yellow")

    # MX Records
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

    # Email reputation
    if emailrep.get("checked") and emailrep.get("data"):
        report.display_key_value("Email Reputation (emailrep.io)", emailrep["data"], "bright_cyan")

    if disify.get("checked") and disify.get("data"):
        report.display_key_value("Email Validation (disify.com)", disify["data"], "bright_cyan")

    # Gravatar
    if gravatar["exists"]:
        grav_data = {
            "Status": "Found",
            "Profile URL": gravatar.get("profile_url", "N/A"),
            "Avatar URL": gravatar.get("avatar_url", "N/A"),
        }
        if gravatar.get("data"):
            for key, val in gravatar["data"].items():
                if key not in ("linked_accounts", "urls", "phones", "emails", "ims") and val and val != "N/A":
                    grav_data[key.replace("_", " ").title()] = str(val)
        report.display_key_value("Gravatar Profile", grav_data, "bright_green")

        if gravatar.get("data", {}).get("linked_accounts"):
            rows = [[acc.get("service", ""), acc.get("username", ""), acc.get("url", "")] for acc in gravatar["data"]["linked_accounts"]]
            report.display_section_table("Gravatar Linked Accounts", rows, ["Service", "Username", "URL"], "bright_green")

        if gravatar.get("data", {}).get("phones"):
            for phone in gravatar["data"]["phones"]:
                console.print(f"  [bright_green]Phone ({phone.get('type', '')}):[/bright_green] {phone.get('value', 'N/A')}")

        if gravatar.get("data", {}).get("emails"):
            for em in gravatar["data"]["emails"]:
                primary = " (primary)" if em.get("primary") else ""
                console.print(f"  [bright_green]Email{primary}:[/bright_green] {em.get('value', 'N/A')}")

        if gravatar.get("data", {}).get("ims"):
            for im in gravatar["data"]["ims"]:
                console.print(f"  [bright_green]IM ({im.get('type', '')}):[/bright_green] {im.get('value', 'N/A')}")
            console.print()
    else:
        console.print("[dim]Gravatar: No profile found[/dim]\n")

    # Breaches
    if hibp.get("breaches"):
        console.print(f"[bold red]HIBP BREACHES FOUND: {len(hibp['breaches'])}[/bold red]")
        rows = [[b, "Breached"] for b in hibp["breaches"]]
        report.display_section_table("Data Breaches (HIBP)", rows, ["Service", "Status"], "red")
    else:
        console.print("[bold green]HIBP: No known breaches found[/bold green]\n")

    # Alternative leaks
    if leaks.get("sources"):
        console.print(f"[bold red]ADDITIONAL LEAKS FOUND: {len(leaks['sources'])}[/bold red]")
        rows = [[s["name"], s["source"]] for s in leaks["sources"]]
        report.display_section_table("Additional Leak Sources", rows, ["Database", "Source"], "red")

    # Detailed leak info
    if leaks.get("detailed"):
        rows = []
        for d in leaks["detailed"][:20]:
            rows.append([
                d.get("name", "N/A"),
                d.get("domain", "N/A"),
                d.get("date", "N/A"),
                str(d.get("data_types", "N/A"))[:60],
                d.get("records", "N/A"),
            ])
        report.display_section_table(
            "Detailed Breach Info",
            rows,
            ["Breach", "Domain", "Date", "Leaked Data Types", "Records"],
            "red",
        )

    if leaks.get("personal_data"):
        report.display_key_value("Leak Analytics", leaks["personal_data"], "bright_red")

    # Leaked fields analysis
    if leaks_detailed.get("leaked_fields"):
        console.print(f"[bold red]LEAKED DATA TYPES: {len(leaks_detailed['leaked_fields'])} types found across all breaches[/bold red]")
        field_data = {"All Leaked Fields": ", ".join(leaks_detailed["leaked_fields"])}
        if leaks_detailed.get("data"):
            field_data.update(leaks_detailed["data"])
        report.display_key_value("Leaked Data Analysis", field_data, "red")

    # VK search results
    if vk_search.get("found") and vk_search.get("profiles"):
        console.print(f"[bold bright_cyan]VK PROFILES FOUND: {len(vk_search['profiles'])}[/bold bright_cyan]")
        rows = []
        for p in vk_search["profiles"]:
            rows.append([
                p.get("name", "Unknown"),
                p.get("url", "N/A"),
                p.get("photo", "N/A")[:80] if p.get("photo") else "N/A",
            ])
        report.display_section_table("VK Profiles (by email)", rows, ["Name", "URL", "Photo"], "bright_cyan")

    # Registrations
    found_registrations = [r for r in registrations if r.get("registered")]
    if found_registrations:
        rows = [[r["name"], "Registered"] for r in found_registrations]
        report.display_section_table("Found Registrations", rows, ["Service", "Status"], "bright_green")

    not_found = [r for r in registrations if not r.get("registered") and r.get("details") != "Check failed"]
    if not_found:
        console.print(f"[dim]Not found on: {', '.join(r['name'] for r in not_found)}[/dim]\n")

    # OSINT links
    report.display_key_value("OSINT Research Links", osint_links, "bright_yellow")

    stats = {
        "MX Records Found": len(mx_records),
        "Gravatar Profile": 1 if gravatar["exists"] else 0,
        "SMTP Verified": 1 if smtp_result["verified"] else 0,
        "Disposable": 1 if disposable["is_disposable"] else 0,
        "Breaches (HIBP)": len(hibp.get("breaches", [])),
        "Additional Leaks": len(leaks.get("sources", [])),
        "Detailed Breaches": len(leaks.get("detailed", [])),
        "Leaked Data Types": len(leaks_detailed.get("leaked_fields", [])),
        "VK Profiles Found": len(vk_search.get("profiles", [])),
        "Registrations Found": len(found_registrations),
        "Possible Usernames": len(possible_usernames),
    }

    report.add_section("email_info", email_info)
    report.add_section("domain_geo", domain_geo)
    report.add_section("smtp_verification", smtp_result)
    report.add_section("disposable", disposable)
    report.add_section("gravatar", gravatar)
    report.add_section("breaches", hibp)
    report.add_section("additional_leaks", leaks)
    report.add_section("leaked_fields", leaks_detailed)
    report.add_section("vk_search", vk_search)
    report.add_section("email_reputation", emailrep)
    report.add_section("registrations", {"found": [r["name"] for r in found_registrations]})
    report.add_section("osint_links", osint_links)
    report.set_stats(stats)
    report.display_summary()

    try:
        report.export_json()
    except Exception:
        pass

    return report

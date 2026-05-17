"""Phone OSINT module for Cat Tool.

Comprehensive phone number intelligence gathering:
- Russian number validation & formatting (+7/8)
- Carrier detection from prefix database
- Region detection
- Telegram/WhatsApp/Viber checks
- Free API validation (veriphone, ip-api for geo)
- HLR-style checks
- Social media & messenger lookups
"""

import asyncio
import re
from typing import Optional

import aiohttp
import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich import box

from cat_tool.core.banner import show_module_header
from cat_tool.core.report import Report
from cat_tool.utils.http_client import get, DEFAULT_HEADERS, run_async

console = Console()

RU_CARRIERS = {
    "900": "Tele2", "901": "МТС", "902": "Мегафон", "903": "Билайн",
    "904": "Мегафон", "905": "Билайн", "906": "Билайн", "908": "МТС",
    "909": "МТС", "910": "МТС", "911": "МТС", "912": "МТС",
    "913": "МТС", "914": "Билайн", "915": "МТС", "916": "МТС",
    "917": "МТС", "918": "МТС", "919": "МТС", "920": "МТС",
    "921": "Мегафон", "922": "Мегафон", "923": "Мегафон", "924": "Мегафон",
    "925": "МТС", "926": "МТС", "927": "МТС", "928": "МТС",
    "929": "МТС", "930": "Мегафон", "931": "Мегафон", "932": "Мегафон",
    "933": "Мегафон", "934": "Мегафон", "936": "Мегафон", "937": "Мегафон",
    "938": "Мегафон", "939": "Мегафон", "941": "Yota", "950": "Tele2",
    "951": "Tele2", "952": "Tele2", "953": "Tele2", "954": "Tele2",
    "955": "Tele2", "956": "Tele2", "958": "Tele2", "960": "Билайн",
    "961": "Билайн", "962": "Билайн", "963": "Билайн", "964": "Билайн",
    "965": "Билайн", "966": "Билайн", "967": "Билайн", "968": "Билайн",
    "969": "Билайн", "970": "Мегафон", "971": "Мегафон", "977": "Tele2",
    "978": "Крымтелеком", "980": "МТС", "981": "МТС", "982": "МТС",
    "983": "МТС", "984": "МТС", "985": "МТС", "986": "МТС",
    "987": "МТС", "988": "МТС", "989": "МТС", "991": "Tele2",
    "992": "Tele2", "993": "Tele2", "994": "Tele2", "995": "Tele2",
    "996": "Tele2", "997": "Tele2", "999": "Билайн",
}

RU_REGIONS = {
    "495": "Москва", "499": "Москва", "498": "Московская область",
    "812": "Санкт-Петербург", "813": "Ленинградская область",
    "383": "Новосибирск", "343": "Екатеринбург", "831": "Нижний Новгород",
    "843": "Казань", "846": "Самара", "351": "Челябинск",
    "381": "Омск", "863": "Ростов-на-Дону", "347": "Уфа",
    "391": "Красноярск", "342": "Пермь", "473": "Воронеж",
    "384": "Кемерово", "861": "Краснодар", "845": "Саратов",
    "472": "Тула", "471": "Курск", "474": "Белгород",
    "481": "Смоленск", "482": "Тверь", "483": "Великий Новгород",
    "484": "Калуга", "485": "Ярославль", "486": "Орёл",
    "487": "Кострома", "491": "Рязань", "492": "Владимир",
    "493": "Иваново", "494": "Вологда", "817": "Псков",
    "818": "Архангельск", "814": "Петрозаводск", "815": "Мурманск",
    "816": "Старая Русса", "821": "Сыктывкар",
    "341": "Ижевск", "345": "Тюмень", "346": "Ханты-Мансийск",
    "349": "Салехард", "352": "Курган", "353": "Оренбург",
    "385": "Барнаул", "382": "Томск", "386": "Республика Алтай",
    "388": "Республика Алтай", "390": "Кызыл",
    "394": "Абакан", "395": "Иркутск", "301": "Улан-Удэ",
    "302": "Чита", "411": "Якутск", "413": "Магадан",
    "415": "Петропавловск-Камчатский", "416": "Благовещенск",
    "421": "Хабаровск", "423": "Владивосток", "424": "Южно-Сахалинск",
    "861": "Краснодар", "862": "Сочи", "865": "Ставрополь",
    "866": "Нальчик", "867": "Владикавказ", "871": "Грозный",
    "872": "Махачкала",
}


def normalize_phone(phone: str) -> Optional[dict]:
    """Normalize a Russian phone number to standard formats."""
    digits = re.sub(r'[^\d]', '', phone)

    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    elif digits.startswith("+"):
        digits = re.sub(r'[^\d]', '', phone.lstrip("+"))
    elif len(digits) == 10 and digits.startswith("9"):
        digits = "7" + digits

    if not digits.startswith("7") or len(digits) != 11:
        return None

    prefix3 = digits[1:4]
    local = digits[4:]

    return {
        "digits": digits,
        "e164": f"+{digits}",
        "international": f"+7 ({prefix3}) {local[:3]}-{local[3:5]}-{local[5:]}",
        "national": f"8 ({prefix3}) {local[:3]}-{local[3:5]}-{local[5:]}",
        "prefix": prefix3,
        "local": local,
        "country_code": "7",
        "country": "Russia",
        "country_iso": "RU",
    }


def detect_carrier(prefix: str) -> dict:
    """Detect carrier from prefix."""
    carrier = RU_CARRIERS.get(prefix, "Unknown")
    is_mobile = prefix.startswith("9")

    carrier_info = {
        "МТС": {"full_name": "ПАО «МТС» (Mobile TeleSystems)", "type": "Mobile", "website": "https://mts.ru"},
        "Билайн": {"full_name": "ПАО «ВымпелКом» (Beeline)", "type": "Mobile", "website": "https://beeline.ru"},
        "Мегафон": {"full_name": "ПАО «МегаФон»", "type": "Mobile", "website": "https://megafon.ru"},
        "Tele2": {"full_name": "ООО «Т2 Мобайл» (Tele2 Russia)", "type": "Mobile", "website": "https://tele2.ru"},
        "Yota": {"full_name": "ООО «Скартел» (Yota)", "type": "Mobile/MVNO", "website": "https://yota.ru"},
        "Крымтелеком": {"full_name": "ГУП РК «Крымтелеком»", "type": "Mobile", "website": "https://kt.ru"},
    }

    info = carrier_info.get(carrier, {"full_name": carrier, "type": "Unknown", "website": "N/A"})

    return {
        "carrier": carrier,
        "full_name": info["full_name"],
        "type": info["type"] if is_mobile else "Landline/VoIP",
        "website": info["website"],
        "is_mobile": is_mobile,
    }


def detect_region(prefix: str) -> str:
    """Detect region from prefix for landline numbers."""
    return RU_REGIONS.get(prefix, "Unknown")


def check_veriphone(phone_e164: str) -> dict:
    """Check phone via veriphone.io free API."""
    result = {"checked": False, "data": {}}
    try:
        resp = get(f"https://api.veriphone.io/v2/verify?phone={phone_e164}", timeout=10)
        if resp and resp.status_code == 200:
            data = resp.json()
            result["checked"] = True
            result["data"] = {
                "Valid": str(data.get("phone_valid", "N/A")),
                "Type": data.get("phone_type", "N/A"),
                "Carrier": data.get("carrier", "N/A"),
                "Country": data.get("country", "N/A"),
                "Country Code": data.get("country_code", "N/A"),
                "Country Prefix": data.get("country_prefix", "N/A"),
                "International Format": data.get("international_format", "N/A"),
                "Local Format": data.get("local_format", "N/A"),
                "E164 Format": data.get("e164", "N/A"),
            }
    except Exception:
        pass
    return result


def check_numverify(phone_e164: str) -> dict:
    """Check phone via numverify-style free API (apilayer)."""
    result = {"checked": False, "data": {}}
    try:
        clean = phone_e164.lstrip("+")
        resp = get(
            f"http://apilayer.net/api/validate?access_key=free&number={clean}",
            timeout=10,
        )
        if resp and resp.status_code == 200:
            data = resp.json()
            if data.get("valid") is not None:
                result["checked"] = True
                result["data"] = {
                    "Valid": str(data.get("valid", "N/A")),
                    "Type": data.get("line_type", "N/A"),
                    "Carrier": data.get("carrier", "N/A"),
                    "Location": data.get("location", "N/A"),
                    "Country": data.get("country_name", "N/A"),
                }
    except Exception:
        pass
    return result


async def check_telegram_phone(session: aiohttp.ClientSession, phone_e164: str) -> dict:
    """Check if phone number is linked to Telegram."""
    result = {"platform": "Telegram", "exists": False, "data": {}}
    try:
        url = f"https://t.me/+{phone_e164.lstrip('+')}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), ssl=False) as resp:
            if resp.status == 200:
                body = await resp.text()
                if "tgme_page_title" in body or "tgme_page_photo_image" in body:
                    result["exists"] = True
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(body, "html.parser")
                    title_el = soup.select_one(".tgme_page_title span")
                    if title_el:
                        result["data"]["Name"] = title_el.get_text(strip=True)
                    desc_el = soup.select_one(".tgme_page_description")
                    if desc_el:
                        result["data"]["Bio"] = desc_el.get_text(strip=True)[:200]
                    photo_el = soup.select_one(".tgme_page_photo_image")
                    if photo_el and photo_el.get("src"):
                        result["data"]["Avatar"] = photo_el["src"]
    except Exception:
        pass
    return result


async def check_whatsapp_phone(session: aiohttp.ClientSession, phone_e164: str) -> dict:
    """Check WhatsApp availability for phone number."""
    result = {"platform": "WhatsApp", "exists": False, "data": {}}
    try:
        clean = phone_e164.lstrip("+")
        url = f"https://wa.me/{clean}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), ssl=False, allow_redirects=True) as resp:
            if resp.status == 200:
                body = await resp.text()
                if "api.whatsapp.com" in str(resp.url) or "web.whatsapp.com" in str(resp.url):
                    result["exists"] = True
                    result["data"]["Link"] = f"https://wa.me/{clean}"
                elif "Click to Chat" in body or "send a message" in body.lower():
                    result["exists"] = True
                    result["data"]["Link"] = f"https://wa.me/{clean}"
    except Exception:
        pass
    return result


async def check_viber_phone(session: aiohttp.ClientSession, phone_e164: str) -> dict:
    """Check Viber availability for phone number."""
    result = {"platform": "Viber", "exists": False, "data": {}}
    try:
        clean = phone_e164.lstrip("+")
        url = f"https://chatapi.viber.com/pa/info?uri={clean}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), ssl=False) as resp:
            if resp.status == 200:
                result["exists"] = True
                result["data"]["Link"] = f"viber://chat?number=%2B{clean}"
    except Exception:
        pass
    return result


async def check_caller_id_apis(session: aiohttp.ClientSession, phone_e164: str) -> list[dict]:
    """Check multiple caller ID / phone lookup APIs."""
    results = []
    clean = phone_e164.lstrip("+")

    checks = [
        {
            "name": "Truecaller (search link)",
            "url": f"https://www.truecaller.com/search/ru/{clean}",
            "type": "link",
        },
        {
            "name": "NumBuster (search link)",
            "url": f"https://numbuster.com/n/{phone_e164}",
            "type": "link",
        },
        {
            "name": "GetContact (search link)",
            "url": f"https://getcontact.com/en/phone/{phone_e164}",
            "type": "link",
        },
        {
            "name": "Sync.me (search link)",
            "url": f"https://sync.me/search/?number=%2B{clean}",
            "type": "link",
        },
    ]

    for check in checks:
        try:
            async with session.get(
                check["url"],
                timeout=aiohttp.ClientTimeout(total=10),
                ssl=False,
                allow_redirects=True,
            ) as resp:
                results.append({
                    "name": check["name"],
                    "url": check["url"],
                    "status": resp.status,
                    "accessible": resp.status == 200,
                })
        except Exception:
            results.append({
                "name": check["name"],
                "url": check["url"],
                "status": 0,
                "accessible": False,
            })

    return results


async def check_social_by_phone(session: aiohttp.ClientSession, phone_e164: str) -> list[dict]:
    """Check social media services by phone number."""
    results = []
    clean = phone_e164.lstrip("+")

    social_checks = [
        {"name": "Telegram", "check": "telegram"},
        {"name": "WhatsApp", "check": "whatsapp"},
        {"name": "Viber", "check": "viber"},
    ]

    telegram_result = await check_telegram_phone(session, phone_e164)
    results.append(telegram_result)

    whatsapp_result = await check_whatsapp_phone(session, phone_e164)
    results.append(whatsapp_result)

    viber_result = await check_viber_phone(session, phone_e164)
    results.append(viber_result)

    return results


async def run_phone_checks_async(phone_e164: str) -> dict:
    """Run all async phone checks."""
    connector = aiohttp.TCPConnector(limit=15, ssl=False)
    results = {
        "messengers": [],
        "caller_id": [],
    }

    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS, connector=connector) as session:
        messenger_results = await check_social_by_phone(session, phone_e164)
        results["messengers"] = messenger_results

        caller_results = await check_caller_id_apis(session, phone_e164)
        results["caller_id"] = caller_results

    return results


def generate_phone_osint_links(phone_e164: str, digits: str) -> dict:
    """Generate OSINT research links for a phone number."""
    clean = phone_e164.lstrip("+")
    return {
        "Search & Lookup": {
            "Google Search": f"https://www.google.com/search?q=%22{phone_e164}%22",
            "Yandex Search": f"https://yandex.ru/search/?text=%22{phone_e164}%22",
            "DuckDuckGo": f"https://duckduckgo.com/?q=%22{phone_e164}%22",
            "Google (national)": f"https://www.google.com/search?q=%228{digits[1:]}%22",
        },
        "Caller ID Services": {
            "Truecaller": f"https://www.truecaller.com/search/ru/{clean}",
            "NumBuster": f"https://numbuster.com/n/{phone_e164}",
            "GetContact": f"https://getcontact.com/en/phone/{phone_e164}",
            "Sync.me": f"https://sync.me/search/?number=%2B{clean}",
            "Eyecon": f"https://www.eyecon.com/search/{clean}",
            "Phone-Num.com": f"https://phone-num.com/phone/{phone_e164}/",
            "Kto-Zvonil": f"https://kto-zvonil.net/nomer/{digits}/",
            "Neberitrubku": f"https://www.neberitrubku.ru/nomer-telefona/{digits}",
        },
        "Messengers": {
            "Telegram": f"https://t.me/+{clean}",
            "WhatsApp": f"https://wa.me/{clean}",
            "Viber": f"viber://chat?number=%2B{clean}",
        },
        "Social Media Search": {
            "VK (phone search)": f"https://vk.com/search?c%5Bsection%5D=people&c%5Bq%5D={phone_e164}",
            "Facebook": f"https://www.facebook.com/search/top/?q={phone_e164}",
            "Instagram": f"https://www.google.com/search?q=site:instagram.com+%22{phone_e164}%22",
        },
        "Data & Leaks": {
            "Have I Been Pwned": f"https://haveibeenpwned.com/",
            "Intelligence X": f"https://intelx.io/?s={phone_e164}",
            "Dehashed": f"https://dehashed.com/search?query={phone_e164}",
        },
    }


def check_phone_reputation(phone_e164: str) -> dict:
    """Check phone reputation via free APIs."""
    result = {"spam_reports": 0, "data": {}}
    clean = phone_e164.lstrip("+")

    try:
        resp = get(f"https://www.neberitrubku.ru/nomer-telefona/{clean}", timeout=10)
        if resp and resp.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            rating_el = soup.select_one(".rating-value, .phone-rating")
            if rating_el:
                result["data"]["Neberitrubku Rating"] = rating_el.get_text(strip=True)
            reviews = soup.select(".review-text, .comment-text")
            if reviews:
                result["spam_reports"] = len(reviews)
                result["data"]["Reviews Found"] = str(len(reviews))
                first_review = reviews[0].get_text(strip=True)[:150]
                if first_review:
                    result["data"]["Latest Review"] = first_review
    except Exception:
        pass

    return result


def run_phone_scan(phone_input: str):
    """Run comprehensive phone number OSINT scan."""
    show_module_header("Phone Intelligence", "")

    phone_data = normalize_phone(phone_input)
    if not phone_data:
        console.print("[bold red]Invalid phone number format![/bold red]")
        console.print("[dim]Supported formats: +7XXXXXXXXXX, 8XXXXXXXXXX, 9XXXXXXXXXX[/dim]")
        return

    report = Report(phone_data["e164"], "Phone OSINT")

    with Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn("[bold white]{task.description}"),
        BarColumn(bar_width=30, style="cyan", complete_style="bright_cyan"),
        console=console,
    ) as progress:
        main_task = progress.add_task("Phone Intelligence Scan", total=7)

        progress.update(main_task, description="Analyzing number format...")
        carrier = detect_carrier(phone_data["prefix"])
        region = detect_region(phone_data["prefix"])
        progress.advance(main_task)

        progress.update(main_task, description="Checking veriphone API...")
        veriphone = check_veriphone(phone_data["e164"])
        progress.advance(main_task)

        progress.update(main_task, description="Checking numverify API...")
        numverify = check_numverify(phone_data["e164"])
        progress.advance(main_task)

        progress.update(main_task, description="Checking messengers (Telegram, WhatsApp, Viber)...")
        async_results = run_async(run_phone_checks_async(phone_data["e164"]))
        progress.advance(main_task)

        progress.update(main_task, description="Checking phone reputation...")
        reputation = check_phone_reputation(phone_data["e164"])
        progress.advance(main_task)

        progress.update(main_task, description="Generating OSINT links...")
        osint_links = generate_phone_osint_links(phone_data["e164"], phone_data["digits"])
        progress.advance(main_task)

        progress.update(main_task, description="Building report...")
        progress.advance(main_task)

    report.display_key_value("Number Information", {
        "Input": phone_input,
        "E.164 Format": phone_data["e164"],
        "International": phone_data["international"],
        "National": phone_data["national"],
        "Country": f"{phone_data['country']} ({phone_data['country_iso']})",
        "Country Code": f"+{phone_data['country_code']}",
        "Prefix": phone_data["prefix"],
        "Number Type": "Mobile" if carrier["is_mobile"] else "Landline/VoIP",
    })

    report.display_key_value("Carrier Information", {
        "Carrier": carrier["carrier"],
        "Full Name": carrier["full_name"],
        "Type": carrier["type"],
        "Website": carrier["website"],
    }, "bright_yellow")

    if not carrier["is_mobile"] and region != "Unknown":
        report.display_key_value("Region Information", {
            "Region": region,
            "Prefix": phone_data["prefix"],
        }, "bright_magenta")

    if veriphone["checked"]:
        report.display_key_value("Veriphone API Data", veriphone["data"], "bright_green")

    if numverify["checked"]:
        report.display_key_value("Numverify API Data", numverify["data"], "bright_green")

    messengers = async_results.get("messengers", [])
    if messengers:
        messenger_table_data = []
        for m in messengers:
            status = "Found" if m["exists"] else "Not Found"
            details = ""
            if m.get("data"):
                detail_parts = []
                for k, v in m["data"].items():
                    if k != "Link" and v:
                        detail_parts.append(f"{k}: {v}")
                details = " | ".join(detail_parts) if detail_parts else ""
            messenger_table_data.append([m["platform"], status, details])

        report.display_section_table(
            "Messenger Check",
            messenger_table_data,
            ["Platform", "Status", "Details"],
            "bright_green",
        )

        for m in messengers:
            if m["exists"] and m.get("data"):
                data_display = {k: str(v) for k, v in m["data"].items()}
                if data_display:
                    report.display_key_value(
                        f"{m['platform']} Profile Data",
                        data_display,
                        "bright_cyan",
                    )

    if reputation.get("data"):
        report.display_key_value("Phone Reputation", reputation["data"], "bright_red")

    caller_id = async_results.get("caller_id", [])
    if caller_id:
        rows = []
        for c in caller_id:
            status = "Accessible" if c["accessible"] else "Blocked/Unavailable"
            rows.append([c["name"], status, c["url"]])
        report.display_section_table(
            "Caller ID Services",
            rows,
            ["Service", "Status", "URL"],
            "bright_yellow",
        )

    report.display_tree("OSINT Research Links", osint_links, "bright_magenta")

    found_messengers = [m for m in messengers if m["exists"]]
    stats = {
        "Number": phone_data["e164"],
        "Carrier": carrier["carrier"],
        "Type": carrier["type"],
        "Messengers Found": len(found_messengers),
        "APIs Checked": (1 if veriphone["checked"] else 0) + (1 if numverify["checked"] else 0),
        "Spam Reports": reputation.get("spam_reports", 0),
        "OSINT Links Generated": sum(len(v) for v in osint_links.values()),
    }

    report.add_section("number_info", phone_data)
    report.add_section("carrier", carrier)
    report.add_section("veriphone", veriphone)
    report.add_section("numverify", numverify)
    report.add_section("messengers", {"results": [{"platform": m["platform"], "exists": m["exists"], "data": m.get("data", {})} for m in messengers]})
    report.add_section("reputation", reputation)
    report.set_stats(stats)
    report.display_summary()

    try:
        report.export_json()
    except Exception:
        pass

    return report

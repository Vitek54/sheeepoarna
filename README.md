```
      /\_/\
     ( o.o )   C A T   T O O L
      > ^ <    Advanced OSINT Intelligence Platform
     /|   |\
    (_|   |_)  v1.0.0 | No API Keys Required
```

# Cat Tool - Advanced OSINT Utility

**Cat Tool** is a powerful, beautiful terminal-based OSINT (Open Source Intelligence) platform that automates intelligence gathering across multiple vectors — all without requiring any API keys.

## Features

### Email Intelligence
- Email format validation & provider detection (40+ providers)
- **Domain IP geolocation** (ip-api.com / ipapi.co) — country, city, ISP, timezone
- **SMTP verification** — mailbox existence check via SMTP handshake
- **Disposable email detection** — built-in database (40+ domains) + Kickbox & Debounce APIs
- MX/DNS record analysis (A, AAAA, TXT, NS, MX)
- **Email reputation** scoring (emailrep.io) — spam, blacklist, breach, deliverability
- **Email validation** (disify.com) — format, DNS, disposable checks
- Gravatar profile lookup (full extraction: name, phones, emails, IMs, linked accounts)
- Data breach checking (Have I Been Pwned + XposedOrNot)
- Registration checks across multiple services (GitHub, Spotify, Twitter, Duolingo, etc.)
- Email pattern analysis & username generation
- **12 OSINT research links** (Google, Yandex, HIBP, Hunter.io, IntelX, Dehashed, Epieos, etc.)

### Username Hunt
- Scans **100+ platforms** simultaneously
- Categories: Social Media, Gaming, Dev, Music, Video, Photo/Art, Professional, Forums, Shopping, RU Platforms
- Async parallel scanning with 30 concurrent connections
- **Profile data extraction** via free APIs for found accounts:
  - GitHub (name, bio, location, company, repos, followers, created date)
  - Reddit (karma, verified email, account age)
  - GitLab (name, bio, location, website, created date)
  - Lichess (ratings, games played, wins/losses)
  - Chess.com (name, location, followers, status)
  - Keybase (name, bio, location, linked accounts/proofs)
  - Hacker News (karma, about, created date)
  - Dev.to (name, bio, location, GitHub/Twitter links)
- Improved false positive detection (body content checks for Spotify, Threads, Bluesky, CashApp, Notion)
- **9 OSINT research links** (Google, Yandex, IntelX, WhatsMyName, NameCheckr, etc.)

### Social Media Intelligence
- Deep profiling across 18+ social platforms
- **GitHub** deep profile (repos, followers, bio, company, linked accounts)
- **Reddit** deep profile (karma, verification, account age)
- **GitLab** deep profile (name, bio, location, website, created date)
- **Dev.to** deep profile (name, bio, GitHub/Twitter links)
- **Keybase** deep profile (name, bio, linked cryptographic proofs)
- Cross-platform presence mapping
- **8 OSINT research links** (Google, Yandex, IntelX, WhatsMyName, NameCheckr, etc.)

### Phone OSINT (Russian Numbers)
- **Russian phone number validation** (+7 / 8 prefixes, 10-digit format)
- **Carrier detection** from prefix database (100+ carriers: МТС, Билайн, Мегафон, Tele2, etc.)
- **Region detection** for landline numbers (Moscow, SPb, Novosibirsk, etc.)
- **Messenger availability checks**: Telegram, WhatsApp, Viber
- **Free API validation**: veriphone.io, numverify (apilayer.net)
- **Caller ID service links**: Truecaller, NumBuster, GetContact, Sync.me
- **Phone reputation check**: neberitrubku.ru spam reports
- **10+ OSINT research links** (Google, Yandex, Truecaller, numbuster, phone-num.ru, etc.)

### Steam OSINT
- **SteamID conversion** (SteamID64, SteamID, SteamID3, Account ID)
- Profile scraping (name, real name, location, level, status, VAC bans)
- **Nickname history** extraction
- **Game library** analysis (titles, playtime, recent activity)
- **Friends list** extraction with online status
- **Groups** membership
- **20+ external OSINT tool links** (steamid.uk, steamdb.info, csstats.gg, FACEIT, OpenDota, etc.)
- Based on [steam-osint](https://github.com/olegakanom/steam-osint) reference

### Full Dossier Mode
- Combines all modules for comprehensive target analysis
- Auto-detects input type (email / username / phone number / Steam ID)
- Cross-references findings across platforms

## Installation

```bash
# Clone the repository
git clone https://github.com/Vitek54/sheeepoarna.git
cd sheeepoarna

# Install dependencies
pip install -r requirements.txt

# Run Cat Tool
python -m cat_tool
```

## Requirements

- Python 3.10+
- No API keys needed

## Dependencies

- `rich` - Beautiful terminal UI
- `requests` - HTTP client
- `beautifulsoup4` + `lxml` - HTML parsing
- `dnspython` - DNS lookups
- `aiohttp` - Async HTTP for parallel scanning

## Usage

```bash
# Interactive mode
python -m cat_tool

# The tool presents a menu:
# [1] Email Intelligence
# [2] Username Hunt
# [3] Social Media Scan
# [4] Steam OSINT
# [5] Phone OSINT
# [6] Full Dossier (all modules)
# [0] Exit
```

## Output

- Beautiful Rich terminal tables, panels, and trees
- Color-coded results (green = found, dim = not found)
- JSON reports auto-saved to `reports/` directory
- Summary statistics after each scan

## Legal Disclaimer

This tool is intended for **legitimate OSINT research**, **penetration testing**, and **educational purposes only**. Users are responsible for ensuring compliance with applicable laws and regulations. Do not use this tool for unauthorized surveillance or harassment.

## Credits

- Steam OSINT reference: [olegakanom/steam-osint](https://github.com/olegakanom/steam-osint)
- Built with [Rich](https://github.com/Textualize/rich) for terminal UI

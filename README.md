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
- MX/DNS record analysis
- Gravatar profile lookup (with linked accounts extraction)
- Data breach checking (Have I Been Pwned)
- Registration checks across multiple services
- Email pattern analysis & username generation

### Username Hunt
- Scans **100+ platforms** simultaneously
- Categories: Social Media, Gaming, Dev, Music, Video, Photo/Art, Professional, Forums, Shopping, RU Platforms
- Async parallel scanning for speed
- Categorized results with direct URLs

### Social Media Intelligence
- Deep profiling across 18+ social platforms
- GitHub deep profile (repos, followers, bio, company, linked accounts)
- Reddit deep profile (karma, verification, account age)
- Cross-platform presence mapping
- Auto-generated research links (Google, Yandex, Wayback Machine)

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
- Auto-detects input type (email/username/Steam ID)
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
- `pyfiglet` - ASCII art

## Usage

```bash
# Interactive mode
python -m cat_tool

# The tool presents a menu:
# [1] Email Intelligence
# [2] Username Hunt
# [3] Social Media Scan
# [4] Steam OSINT
# [5] Full Dossier (all modules)
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

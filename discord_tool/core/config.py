"""Константы, тема и глобальный console."""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

THEME = Theme(
    {
        "title": "bold white",
        "accent": "bright_white",
        "dim": "dim white",
        "err": "bold red",
        "ok": "bold green",
        "warn": "yellow",
        "info": "bright_white",
    }
)

console = Console(theme=THEME)

API_BASE = "https://discord.com/api/v10"
SNOWFLAKE_EPOCH = 1420070400000

HYPESQUAD_HOUSES = {
    "1": ("Bravery", 1),
    "2": ("Brilliance", 2),
    "3": ("Balance", 3),
}

LOCALE_MAP = {
    "en-US": "English (US)",
    "en-GB": "English (UK)",
    "ru": "Русский",
    "uk": "Українська",
    "de": "Deutsch",
    "fr": "Français",
    "es-ES": "Español",
    "pt-BR": "Português (BR)",
    "ja": "日本語",
    "ko": "한국어",
    "zh-CN": "中文 (简体)",
    "zh-TW": "中文 (繁體)",
    "tr": "Türkçe",
    "pl": "Polski",
    "it": "Italiano",
    "nl": "Nederlands",
    "ar": "العربية",
}

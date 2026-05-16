"""TUI компоненты — логотип, меню, заголовок."""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from discord_tool.core.config import console

LOGO = r"""
 ____  _                       _   _____           _
|  _ \(_)___  ___ ___  _ __ __| | |_   _|__   ___ | |
| | | | / __|/ __/ _ \| '__/ _` |   | |/ _ \ / _ \| |
| |_| | \__ \ (_| (_) | | | (_| |   | | (_) | (_) | |
|____/|_|___/\___\___/|_|  \__,_|   |_|\___/ \___/|_|
"""

MENU_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "УДАЛЕНИЕ",
        [
            ("1", "Удалить сообщения ВЕЗДЕ"),
            ("2", "Удалить в канале/ЛС"),
            ("3", "Удалить на ВСЕХ серверах"),
            ("4", "Удалить на конкретном сервере"),
            ("5", "Удалить мои реакции в канале"),
        ],
    ),
    (
        "ПАРСИНГ И ПОИСК",
        [
            ("6", "Парсинг участников по роли"),
            ("7", "Поиск сообщений на сервере"),
            ("8", "Lookup пользователя по ID"),
            ("9", "Общие серверы с юзером"),
            ("10", "Общие друзья с юзером"),
            ("11", "Информация об инвайте"),
        ],
    ),
    (
        "АККАУНТ",
        [
            ("12", "Полная информация об аккаунте"),
            ("13", "Изменить био"),
            ("14", "Изменить display name"),
            ("15", "Изменить/удалить аватар"),
            ("16", "Сменить HypeSquad"),
            ("17", "Изменить статус (online/idle/dnd/invisible)"),
            ("18", "Кастомный статус"),
            ("19", "Изменить язык"),
            ("20", "Изменить тему (dark/light)"),
            ("21", "Привязанные аккаунты (connections)"),
            ("22", "Активные сессии"),
            ("23", "Подписки Nitro"),
            ("24", "Бусты серверов"),
        ],
    ),
    (
        "СЕРВЕРЫ",
        [
            ("25", "Информация о сервере"),
            ("26", "Список серверов"),
            ("27", "Роли сервера"),
            ("28", "Скачать эмодзи сервера"),
            ("29", "Экспорт канала в JSON"),
            ("30", "Изменить ник на сервере"),
            ("31", "Mass leave серверов"),
        ],
    ),
    (
        "ДРУЗЬЯ",
        [
            ("32", "Список друзей"),
            ("33", "Входящие/исходящие запросы"),
            ("34", "Принять все входящие запросы"),
            ("35", "Заблокировать пользователя"),
            ("36", "Разблокировать пользователя"),
            ("37", "Отправить запрос в друзья"),
            ("38", "Mass unfriend"),
        ],
    ),
    (
        "УТИЛИТЫ",
        [
            ("39", "Закрыть все ЛС"),
            ("40", "Отправить сообщение в канал"),
            ("41", "Вебхуки канала"),
        ],
    ),
]


def draw_header(username: str) -> None:
    """Отрисовать заголовок с логотипом."""
    logo_text = Text(LOGO, style="bold white")
    console.print(
        Panel(
            logo_text,
            border_style="bright_white",
            subtitle=f"[dim]{username}[/]",
            subtitle_align="right",
        )
    )


def draw_menu() -> None:
    """Отрисовать таблицу меню."""
    table = Table(
        show_header=False,
        border_style="bright_white",
        pad_edge=False,
        expand=True,
    )
    table.add_column("", width=4, style="bright_white")
    table.add_column("", style="white")
    table.add_column("", width=4, style="bright_white")
    table.add_column("", style="white")

    for section_name, items in MENU_SECTIONS:
        table.add_row("", f"[bold white]─── {section_name} ───[/]", "", "")
        for idx in range(0, len(items), 2):
            left_num, left_label = items[idx]
            if idx + 1 < len(items):
                right_num, right_label = items[idx + 1]
            else:
                right_num, right_label = "", ""
            table.add_row(
                f"[bright_white]{left_num}[/]",
                left_label,
                f"[bright_white]{right_num}[/]",
                right_label,
            )

    console.print(table)
    console.print("[dim]0 — Выход[/]\n")

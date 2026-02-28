from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pygame

WINDOW_TITLE = "Bit Life Survival"
DEFAULT_RESOLUTION = (1280, 720)
VIRTUAL_RESOLUTION = (1280, 720)
DEFAULT_UI_SCALE = 1.0


@dataclass(frozen=True)
class Palette:
    bg: tuple[int, int, int]
    panel: tuple[int, int, int]
    panel_alt: tuple[int, int, int]
    text: tuple[int, int, int]
    text_muted: tuple[int, int, int]
    accent: tuple[int, int, int]
    accent_soft: tuple[int, int, int]
    success: tuple[int, int, int]
    warning: tuple[int, int, int]
    danger: tuple[int, int, int]
    border: tuple[int, int, int]
    border_highlight: tuple[int, int, int]
    border_shade: tuple[int, int, int]
    border_inner: tuple[int, int, int]
    progress_bg: tuple[int, int, int]
    button_top: tuple[int, int, int]
    button_top_hover: tuple[int, int, int]
    button_bottom: tuple[int, int, int]
    button_disabled: tuple[int, int, int]
    button_flat: tuple[int, int, int]


THEMES: dict[str, Palette] = {
    "amethyst": Palette(
        bg=(18, 12, 28),
        panel=(48, 28, 74),
        panel_alt=(58, 36, 90),
        text=(248, 240, 226),
        text_muted=(216, 200, 216),
        accent=(118, 198, 164),
        accent_soft=(78, 132, 114),
        success=(122, 214, 154),
        warning=(244, 198, 112),
        danger=(226, 98, 116),
        border=(96, 72, 58),
        border_highlight=(186, 148, 108),
        border_shade=(44, 30, 26),
        border_inner=(132, 98, 74),
        progress_bg=(36, 24, 56),
        button_top=(154, 176, 146),
        button_top_hover=(170, 194, 162),
        button_bottom=(74, 104, 92),
        button_disabled=(74, 64, 84),
        button_flat=(140, 164, 132),
    ),
    "ember": Palette(
        bg=(24, 14, 14),
        panel=(72, 34, 32),
        panel_alt=(92, 44, 40),
        text=(248, 236, 220),
        text_muted=(220, 194, 172),
        accent=(208, 154, 90),
        accent_soft=(146, 94, 62),
        success=(136, 204, 136),
        warning=(246, 186, 86),
        danger=(236, 102, 96),
        border=(122, 82, 54),
        border_highlight=(214, 154, 98),
        border_shade=(54, 32, 24),
        border_inner=(156, 110, 74),
        progress_bg=(44, 24, 22),
        button_top=(188, 142, 94),
        button_top_hover=(212, 162, 110),
        button_bottom=(96, 62, 46),
        button_disabled=(82, 56, 56),
        button_flat=(176, 130, 88),
    ),
    "verdant": Palette(
        bg=(12, 20, 18),
        panel=(28, 54, 50),
        panel_alt=(40, 76, 68),
        text=(240, 246, 228),
        text_muted=(194, 214, 194),
        accent=(124, 202, 136),
        accent_soft=(76, 142, 102),
        success=(136, 218, 144),
        warning=(236, 202, 110),
        danger=(214, 92, 98),
        border=(70, 104, 80),
        border_highlight=(136, 178, 136),
        border_shade=(30, 50, 38),
        border_inner=(98, 136, 102),
        progress_bg=(16, 42, 34),
        button_top=(150, 184, 140),
        button_top_hover=(176, 206, 162),
        button_bottom=(58, 112, 86),
        button_disabled=(62, 82, 74),
        button_flat=(136, 168, 124),
    ),
    "slate": Palette(
        bg=(14, 18, 24),
        panel=(34, 40, 58),
        panel_alt=(44, 52, 74),
        text=(238, 242, 248),
        text_muted=(188, 198, 214),
        accent=(120, 172, 220),
        accent_soft=(82, 118, 158),
        success=(126, 202, 154),
        warning=(228, 198, 118),
        danger=(220, 106, 122),
        border=(84, 96, 116),
        border_highlight=(150, 168, 196),
        border_shade=(36, 46, 60),
        border_inner=(114, 132, 158),
        progress_bg=(22, 30, 44),
        button_top=(148, 162, 182),
        button_top_hover=(172, 188, 208),
        button_bottom=(74, 92, 118),
        button_disabled=(72, 76, 96),
        button_flat=(136, 150, 172),
    ),
    "duststorm": Palette(
        bg=(31, 24, 20),
        panel=(78, 58, 44),
        panel_alt=(96, 72, 54),
        text=(244, 232, 214),
        text_muted=(212, 190, 166),
        accent=(205, 158, 103),
        accent_soft=(140, 104, 74),
        success=(152, 202, 142),
        warning=(240, 188, 98),
        danger=(222, 112, 104),
        border=(122, 90, 62),
        border_highlight=(198, 154, 112),
        border_shade=(56, 40, 30),
        border_inner=(152, 116, 82),
        progress_bg=(58, 44, 34),
        button_top=(194, 152, 108),
        button_top_hover=(216, 170, 122),
        button_bottom=(106, 80, 56),
        button_disabled=(92, 72, 60),
        button_flat=(184, 140, 98),
    ),
    "oxidized": Palette(
        bg=(18, 26, 24),
        panel=(34, 64, 58),
        panel_alt=(46, 82, 74),
        text=(236, 242, 232),
        text_muted=(186, 208, 196),
        accent=(146, 194, 146),
        accent_soft=(90, 136, 104),
        success=(140, 214, 152),
        warning=(230, 196, 116),
        danger=(220, 104, 102),
        border=(78, 118, 98),
        border_highlight=(146, 184, 154),
        border_shade=(36, 60, 52),
        border_inner=(108, 146, 124),
        progress_bg=(26, 48, 44),
        button_top=(150, 186, 150),
        button_top_hover=(172, 206, 170),
        button_bottom=(64, 110, 88),
        button_disabled=(66, 88, 78),
        button_flat=(136, 170, 136),
    ),
    "relic_blue": Palette(
        bg=(14, 20, 34),
        panel=(28, 48, 82),
        panel_alt=(40, 62, 102),
        text=(236, 242, 252),
        text_muted=(184, 202, 232),
        accent=(134, 182, 236),
        accent_soft=(78, 124, 176),
        success=(134, 208, 166),
        warning=(230, 196, 116),
        danger=(226, 104, 120),
        border=(74, 106, 146),
        border_highlight=(142, 172, 210),
        border_shade=(34, 50, 74),
        border_inner=(104, 138, 176),
        progress_bg=(22, 36, 62),
        button_top=(146, 174, 206),
        button_top_hover=(166, 194, 224),
        button_bottom=(66, 96, 136),
        button_disabled=(66, 80, 108),
        button_flat=(132, 162, 198),
    ),
    "terminal_green": Palette(
        bg=(10, 18, 14),
        panel=(20, 44, 30),
        panel_alt=(30, 60, 42),
        text=(226, 244, 226),
        text_muted=(164, 208, 168),
        accent=(122, 210, 124),
        accent_soft=(62, 132, 72),
        success=(132, 222, 144),
        warning=(226, 198, 98),
        danger=(214, 102, 108),
        border=(64, 126, 74),
        border_highlight=(128, 188, 130),
        border_shade=(28, 62, 36),
        border_inner=(94, 154, 96),
        progress_bg=(16, 34, 24),
        button_top=(134, 194, 128),
        button_top_hover=(154, 214, 146),
        button_bottom=(52, 108, 66),
        button_disabled=(58, 84, 62),
        button_flat=(124, 178, 118),
    ),
    "sandstone": Palette(
        bg=(30, 24, 18),
        panel=(84, 64, 44),
        panel_alt=(104, 78, 54),
        text=(246, 236, 216),
        text_muted=(214, 194, 162),
        accent=(212, 164, 106),
        accent_soft=(152, 110, 74),
        success=(152, 204, 142),
        warning=(238, 186, 94),
        danger=(224, 108, 102),
        border=(132, 98, 62),
        border_highlight=(208, 162, 112),
        border_shade=(58, 42, 28),
        border_inner=(166, 126, 86),
        progress_bg=(62, 46, 32),
        button_top=(204, 162, 114),
        button_top_hover=(226, 178, 126),
        button_bottom=(114, 84, 56),
        button_disabled=(98, 76, 60),
        button_flat=(190, 148, 104),
    ),
    "gunmetal": Palette(
        bg=(14, 16, 20),
        panel=(36, 42, 50),
        panel_alt=(46, 56, 66),
        text=(234, 238, 244),
        text_muted=(186, 196, 210),
        accent=(136, 164, 198),
        accent_soft=(82, 106, 132),
        success=(132, 198, 156),
        warning=(226, 190, 116),
        danger=(218, 106, 118),
        border=(84, 96, 112),
        border_highlight=(150, 166, 186),
        border_shade=(36, 44, 54),
        border_inner=(114, 130, 150),
        progress_bg=(24, 30, 38),
        button_top=(152, 166, 182),
        button_top_hover=(172, 186, 204),
        button_bottom=(74, 90, 110),
        button_disabled=(70, 76, 88),
        button_flat=(138, 154, 170),
    ),
    "arctic": Palette(
        bg=(18, 26, 34),
        panel=(38, 58, 74),
        panel_alt=(52, 76, 94),
        text=(236, 246, 252),
        text_muted=(184, 212, 226),
        accent=(126, 194, 228),
        accent_soft=(72, 134, 162),
        success=(134, 214, 184),
        warning=(228, 198, 122),
        danger=(220, 112, 126),
        border=(84, 124, 146),
        border_highlight=(152, 188, 210),
        border_shade=(38, 64, 80),
        border_inner=(116, 154, 174),
        progress_bg=(24, 42, 56),
        button_top=(148, 190, 212),
        button_top_hover=(168, 208, 228),
        button_bottom=(68, 116, 142),
        button_disabled=(70, 92, 108),
        button_flat=(136, 178, 202),
    ),
    "emberlight": Palette(
        bg=(30, 16, 16),
        panel=(88, 44, 40),
        panel_alt=(112, 56, 50),
        text=(250, 236, 220),
        text_muted=(224, 194, 176),
        accent=(226, 158, 92),
        accent_soft=(170, 102, 62),
        success=(154, 214, 152),
        warning=(248, 190, 90),
        danger=(236, 102, 98),
        border=(142, 90, 62),
        border_highlight=(226, 164, 108),
        border_shade=(62, 36, 30),
        border_inner=(176, 118, 82),
        progress_bg=(58, 30, 28),
        button_top=(210, 152, 98),
        button_top_hover=(230, 168, 112),
        button_bottom=(120, 72, 50),
        button_disabled=(98, 66, 58),
        button_flat=(196, 140, 90),
    ),
    "copperline": Palette(
        bg=(24, 18, 18),
        panel=(74, 46, 40),
        panel_alt=(92, 58, 50),
        text=(244, 232, 220),
        text_muted=(212, 188, 170),
        accent=(198, 138, 88),
        accent_soft=(136, 92, 62),
        success=(146, 202, 150),
        warning=(236, 186, 102),
        danger=(222, 108, 106),
        border=(126, 84, 60),
        border_highlight=(202, 146, 104),
        border_shade=(54, 34, 28),
        border_inner=(160, 112, 78),
        progress_bg=(48, 30, 28),
        button_top=(190, 136, 92),
        button_top_hover=(212, 154, 106),
        button_bottom=(102, 68, 50),
        button_disabled=(88, 64, 58),
        button_flat=(178, 124, 84),
    ),
    "wasteland_olive": Palette(
        bg=(20, 22, 16),
        panel=(52, 62, 38),
        panel_alt=(66, 78, 48),
        text=(236, 236, 214),
        text_muted=(188, 202, 162),
        accent=(178, 186, 108),
        accent_soft=(122, 132, 74),
        success=(150, 206, 140),
        warning=(228, 190, 104),
        danger=(216, 108, 100),
        border=(102, 118, 70),
        border_highlight=(164, 180, 114),
        border_shade=(44, 56, 30),
        border_inner=(132, 150, 90),
        progress_bg=(32, 42, 24),
        button_top=(172, 180, 112),
        button_top_hover=(190, 198, 126),
        button_bottom=(84, 100, 56),
        button_disabled=(76, 84, 62),
        button_flat=(158, 166, 98),
    ),
    "midnight_teal": Palette(
        bg=(10, 20, 22),
        panel=(20, 54, 56),
        panel_alt=(30, 72, 74),
        text=(228, 246, 242),
        text_muted=(168, 210, 204),
        accent=(112, 194, 184),
        accent_soft=(62, 130, 124),
        success=(136, 212, 166),
        warning=(224, 194, 116),
        danger=(216, 106, 120),
        border=(66, 126, 122),
        border_highlight=(132, 182, 176),
        border_shade=(28, 62, 62),
        border_inner=(94, 150, 146),
        progress_bg=(16, 40, 42),
        button_top=(136, 194, 186),
        button_top_hover=(156, 212, 202),
        button_bottom=(54, 106, 106),
        button_disabled=(60, 86, 88),
        button_flat=(122, 178, 170),
    ),
    "concrete_rose": Palette(
        bg=(24, 20, 24),
        panel=(62, 52, 62),
        panel_alt=(80, 66, 80),
        text=(242, 234, 240),
        text_muted=(206, 184, 202),
        accent=(198, 148, 182),
        accent_soft=(136, 96, 126),
        success=(150, 204, 156),
        warning=(232, 190, 114),
        danger=(224, 106, 126),
        border=(112, 92, 110),
        border_highlight=(182, 148, 176),
        border_shade=(50, 42, 52),
        border_inner=(146, 118, 142),
        progress_bg=(42, 36, 44),
        button_top=(190, 152, 182),
        button_top_hover=(208, 170, 198),
        button_bottom=(96, 78, 98),
        button_disabled=(84, 72, 86),
        button_flat=(176, 138, 168),
    ),
    "solar_flare": Palette(
        bg=(34, 18, 10),
        panel=(96, 52, 30),
        panel_alt=(120, 66, 38),
        text=(252, 236, 206),
        text_muted=(230, 194, 150),
        accent=(244, 164, 72),
        accent_soft=(182, 102, 48),
        success=(162, 208, 138),
        warning=(252, 198, 88),
        danger=(238, 108, 92),
        border=(154, 94, 52),
        border_highlight=(238, 168, 94),
        border_shade=(66, 38, 24),
        border_inner=(188, 122, 72),
        progress_bg=(66, 34, 20),
        button_top=(230, 164, 88),
        button_top_hover=(244, 180, 102),
        button_bottom=(126, 76, 44),
        button_disabled=(106, 70, 56),
        button_flat=(214, 150, 78),
    ),
    "storm_ash": Palette(
        bg=(18, 20, 22),
        panel=(44, 48, 52),
        panel_alt=(58, 64, 68),
        text=(236, 238, 240),
        text_muted=(192, 198, 204),
        accent=(150, 168, 184),
        accent_soft=(94, 110, 126),
        success=(136, 194, 162),
        warning=(224, 188, 120),
        danger=(216, 114, 122),
        border=(90, 102, 112),
        border_highlight=(156, 170, 180),
        border_shade=(42, 50, 58),
        border_inner=(120, 136, 146),
        progress_bg=(28, 34, 38),
        button_top=(164, 176, 188),
        button_top_hover=(184, 196, 208),
        button_bottom=(82, 96, 108),
        button_disabled=(74, 80, 90),
        button_flat=(150, 162, 174),
    ),
    "synth_orange": Palette(
        bg=(20, 16, 18),
        panel=(72, 44, 38),
        panel_alt=(92, 56, 48),
        text=(248, 236, 224),
        text_muted=(218, 190, 170),
        accent=(232, 146, 78),
        accent_soft=(166, 94, 54),
        success=(152, 204, 148),
        warning=(246, 190, 96),
        danger=(232, 102, 106),
        border=(130, 82, 60),
        border_highlight=(212, 150, 102),
        border_shade=(56, 34, 28),
        border_inner=(164, 108, 78),
        progress_bg=(48, 30, 28),
        button_top=(214, 148, 88),
        button_top_hover=(234, 166, 104),
        button_bottom=(110, 70, 50),
        button_disabled=(92, 66, 58),
        button_flat=(198, 136, 80),
    ),
}

DEFAULT_THEME = "ember"
CURRENT_THEME = DEFAULT_THEME

COLOR_BG: tuple[int, int, int]
COLOR_PANEL: tuple[int, int, int]
COLOR_PANEL_ALT: tuple[int, int, int]
COLOR_TEXT: tuple[int, int, int]
COLOR_TEXT_MUTED: tuple[int, int, int]
COLOR_ACCENT: tuple[int, int, int]
COLOR_ACCENT_SOFT: tuple[int, int, int]
COLOR_SUCCESS: tuple[int, int, int]
COLOR_WARNING: tuple[int, int, int]
COLOR_DANGER: tuple[int, int, int]
COLOR_BORDER: tuple[int, int, int]
COLOR_BORDER_HIGHLIGHT: tuple[int, int, int]
COLOR_BORDER_SHADE: tuple[int, int, int]
COLOR_BORDER_INNER: tuple[int, int, int]
COLOR_PROGRESS_BG: tuple[int, int, int]
COLOR_BUTTON_TOP: tuple[int, int, int]
COLOR_BUTTON_TOP_HOVER: tuple[int, int, int]
COLOR_BUTTON_BOTTOM: tuple[int, int, int]
COLOR_BUTTON_DISABLED: tuple[int, int, int]
COLOR_BUTTON_FLAT: tuple[int, int, int]

PADDING = 10
MARGIN = 12
BORDER_RADIUS = 2
BORDER_WIDTH = 2
BORDER_INNER_WIDTH = 1

FONT_SIZE_TITLE = 24
FONT_SIZE_SECTION = 17
FONT_SIZE_BODY = 15
FONT_SIZE_META = 13

FontKind = Literal["body", "display"]
FontRole = Literal["title", "section", "body", "meta"]
_FONT_SCALE = 1.0
_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
_FONT_FILES: dict[str, dict[str, str]] = {
    "body": {
        "regular": "PixelOperatorMono8.ttf",
        "bold": "PixelOperatorMonoHB8.ttf",
    },
    "display": {
        "regular": "PixelOperatorMonoHB8.ttf",
        "bold": "PixelOperatorMonoHB8.ttf",
    },
}
_SYS_FALLBACK: dict[str, list[str]] = {
    "body": ["Consolas", "Lucida Console", "Cascadia Mono", "DejaVu Sans Mono", "Courier New"],
    "display": ["Cascadia Mono", "Consolas", "Lucida Console", "Segoe UI Semibold"],
}


def available_themes() -> tuple[str, ...]:
    return tuple(THEMES.keys())


def apply_theme(theme_name: str | None) -> str:
    global CURRENT_THEME
    palette = THEMES.get(theme_name or "")
    if palette is None:
        theme_name = DEFAULT_THEME
        palette = THEMES[theme_name]
    CURRENT_THEME = theme_name
    globals().update(
        {
            "COLOR_BG": palette.bg,
            "COLOR_PANEL": palette.panel,
            "COLOR_PANEL_ALT": palette.panel_alt,
            "COLOR_TEXT": palette.text,
            "COLOR_TEXT_MUTED": palette.text_muted,
            "COLOR_ACCENT": palette.accent,
            "COLOR_ACCENT_SOFT": palette.accent_soft,
            "COLOR_SUCCESS": palette.success,
            "COLOR_WARNING": palette.warning,
            "COLOR_DANGER": palette.danger,
            "COLOR_BORDER": palette.border,
            "COLOR_BORDER_HIGHLIGHT": palette.border_highlight,
            "COLOR_BORDER_SHADE": palette.border_shade,
            "COLOR_BORDER_INNER": palette.border_inner,
            "COLOR_PROGRESS_BG": palette.progress_bg,
            "COLOR_BUTTON_TOP": palette.button_top,
            "COLOR_BUTTON_TOP_HOVER": palette.button_top_hover,
            "COLOR_BUTTON_BOTTOM": palette.button_bottom,
            "COLOR_BUTTON_DISABLED": palette.button_disabled,
            "COLOR_BUTTON_FLAT": palette.button_flat,
        }
    )
    return CURRENT_THEME


def set_font_scale(scale: float) -> None:
    global _FONT_SCALE
    _FONT_SCALE = max(0.75, min(1.6, float(scale)))
    _load_font.cache_clear()


@lru_cache(maxsize=256)
def _load_font(kind: FontKind, size: int, bold: bool) -> pygame.font.Font:
    weight = "bold" if bold else "regular"
    filename = _FONT_FILES.get(kind, {}).get(weight)
    if filename:
        path = _FONT_DIR / filename
        if path.exists():
            try:
                return pygame.font.Font(str(path), size)
            except OSError:
                pass
    for fallback in _SYS_FALLBACK.get(kind, _SYS_FALLBACK["body"]):
        font = pygame.font.SysFont(fallback, size, bold=bold)
        if font:
            return font
    return pygame.font.Font(None, size)


def get_font(size: int, bold: bool = False, kind: FontKind = "body") -> pygame.font.Font:
    scaled = max(10, int(round(float(size) * _FONT_SCALE)))
    return _load_font(kind, scaled, bold)


def get_role_font(role: FontRole, bold: bool = False, kind: FontKind = "body") -> pygame.font.Font:
    role_sizes = {
        "title": FONT_SIZE_TITLE,
        "section": FONT_SIZE_SECTION,
        "body": FONT_SIZE_BODY,
        "meta": FONT_SIZE_META,
    }
    return get_font(role_sizes[role], bold=bold, kind=kind)


apply_theme(DEFAULT_THEME)

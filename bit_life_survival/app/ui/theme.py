from __future__ import annotations

from dataclasses import dataclass

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


THEMES: dict[str, Palette] = {
    "amethyst": Palette(
        bg=(18, 12, 28),
        panel=(48, 28, 74),
        panel_alt=(58, 36, 90),
        text=(244, 238, 226),
        text_muted=(204, 192, 210),
        accent=(110, 190, 156),
        accent_soft=(80, 130, 116),
        success=(118, 208, 150),
        warning=(236, 196, 110),
        danger=(214, 92, 108),
        border=(102, 76, 58),
        border_highlight=(162, 130, 100),
        border_shade=(52, 36, 30),
        border_inner=(126, 98, 76),
        progress_bg=(38, 24, 56),
        button_top=(134, 160, 128),
        button_top_hover=(154, 184, 146),
        button_bottom=(66, 96, 86),
        button_disabled=(76, 68, 84),
    ),
    "ember": Palette(
        bg=(24, 14, 16),
        panel=(70, 34, 34),
        panel_alt=(88, 44, 42),
        text=(246, 234, 216),
        text_muted=(214, 186, 168),
        accent=(196, 146, 86),
        accent_soft=(134, 90, 64),
        success=(130, 196, 132),
        warning=(242, 182, 86),
        danger=(228, 98, 96),
        border=(122, 82, 54),
        border_highlight=(188, 130, 86),
        border_shade=(58, 36, 28),
        border_inner=(142, 102, 70),
        progress_bg=(44, 24, 24),
        button_top=(174, 130, 88),
        button_top_hover=(198, 154, 102),
        button_bottom=(96, 62, 48),
        button_disabled=(86, 62, 62),
    ),
    "verdant": Palette(
        bg=(12, 20, 18),
        panel=(28, 54, 50),
        panel_alt=(38, 72, 66),
        text=(236, 242, 224),
        text_muted=(184, 206, 186),
        accent=(120, 196, 132),
        accent_soft=(72, 136, 96),
        success=(132, 212, 140),
        warning=(232, 198, 102),
        danger=(210, 90, 96),
        border=(70, 104, 80),
        border_highlight=(122, 166, 128),
        border_shade=(34, 56, 42),
        border_inner=(92, 132, 100),
        progress_bg=(18, 42, 36),
        button_top=(136, 172, 130),
        button_top_hover=(164, 198, 150),
        button_bottom=(56, 106, 82),
        button_disabled=(62, 82, 74),
    ),
    "slate": Palette(
        bg=(16, 18, 24),
        panel=(34, 40, 58),
        panel_alt=(44, 52, 74),
        text=(236, 240, 246),
        text_muted=(182, 192, 208),
        accent=(118, 168, 214),
        accent_soft=(78, 114, 152),
        success=(124, 198, 152),
        warning=(224, 194, 112),
        danger=(214, 102, 118),
        border=(84, 96, 116),
        border_highlight=(136, 154, 182),
        border_shade=(38, 48, 62),
        border_inner=(108, 126, 150),
        progress_bg=(24, 30, 44),
        button_top=(136, 150, 170),
        button_top_hover=(160, 176, 196),
        button_bottom=(72, 90, 116),
        button_disabled=(74, 78, 96),
    ),
}

DEFAULT_THEME = "amethyst"
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

PADDING = 10
MARGIN = 12
BORDER_RADIUS = 2
BORDER_WIDTH = 2
BORDER_INNER_WIDTH = 1


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
        }
    )
    return CURRENT_THEME


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    preferred = ["Consolas", "Lucida Console", "DejaVu Sans Mono", "Courier New"]
    for name in preferred:
        font = pygame.font.SysFont(name, size, bold=bold)
        if font:
            return font
    return pygame.font.Font(None, size)


apply_theme(DEFAULT_THEME)

from __future__ import annotations

import pygame

WINDOW_TITLE = "Bit Life Survival"
DEFAULT_RESOLUTION = (1280, 720)
DEFAULT_UI_SCALE = 1.0

COLOR_BG = (18, 20, 26)
COLOR_PANEL = (30, 34, 44)
COLOR_PANEL_ALT = (36, 41, 54)
COLOR_TEXT = (232, 236, 245)
COLOR_TEXT_MUTED = (162, 170, 188)
COLOR_ACCENT = (74, 177, 255)
COLOR_ACCENT_SOFT = (48, 118, 165)
COLOR_SUCCESS = (90, 200, 130)
COLOR_WARNING = (236, 188, 84)
COLOR_DANGER = (224, 92, 92)
COLOR_BORDER = (82, 92, 112)
COLOR_PROGRESS_BG = (46, 52, 68)

PADDING = 10
MARGIN = 12
BORDER_RADIUS = 8


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    # Cross-platform fallback: Consolas -> DejaVu Sans Mono -> default.
    preferred = ["Consolas", "DejaVu Sans Mono", "Monaco", "Courier New"]
    for name in preferred:
        font = pygame.font.SysFont(name, size, bold=bold)
        if font:
            return font
    return pygame.font.Font(None, size)

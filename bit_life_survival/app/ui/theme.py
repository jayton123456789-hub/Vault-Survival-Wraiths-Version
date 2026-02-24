from __future__ import annotations

import pygame

WINDOW_TITLE = "Bit Life Survival"
DEFAULT_RESOLUTION = (1280, 720)
VIRTUAL_RESOLUTION = (1280, 720)
DEFAULT_UI_SCALE = 1.0

COLOR_BG = (17, 12, 28)
COLOR_PANEL = (51, 26, 76)
COLOR_PANEL_ALT = (62, 35, 92)
COLOR_TEXT = (242, 236, 226)
COLOR_TEXT_MUTED = (196, 180, 206)
COLOR_ACCENT = (98, 176, 148)
COLOR_ACCENT_SOFT = (74, 128, 116)
COLOR_SUCCESS = (112, 202, 144)
COLOR_WARNING = (232, 194, 102)
COLOR_DANGER = (214, 92, 108)
COLOR_BORDER = (130, 96, 70)
COLOR_BORDER_INNER = (216, 181, 136)
COLOR_PROGRESS_BG = (42, 27, 60)
COLOR_BUTTON_TOP = (130, 151, 124)
COLOR_BUTTON_TOP_HOVER = (148, 176, 140)
COLOR_BUTTON_BOTTOM = (69, 94, 83)
COLOR_BUTTON_DISABLED = (76, 68, 84)

PADDING = 10
MARGIN = 12
BORDER_RADIUS = 2
BORDER_WIDTH = 2
BORDER_INNER_WIDTH = 1


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    preferred = ["Consolas", "Lucida Console", "DejaVu Sans Mono", "Courier New"]
    for name in preferred:
        font = pygame.font.SysFont(name, size, bold=bold)
        if font:
            return font
    return pygame.font.Font(None, size)

from __future__ import annotations

import hashlib
import math

import pygame

from . import theme
from .widgets import draw_text


def palette_from_key(key: str) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    base = (80 + digest[0] % 90, 70 + digest[1] % 90, 95 + digest[2] % 90)
    shirt = (70 + digest[3] % 120, 80 + digest[4] % 90, 80 + digest[5] % 90)
    hair = (45 + digest[6] % 80, 35 + digest[7] % 60, 25 + digest[8] % 50)
    return base, shirt, hair


def draw_citizen_sprite(
    surface: pygame.Surface,
    x: int,
    y: int,
    citizen_id: str,
    scale: int = 2,
    selected: bool = False,
    walk_phase: float = 0.0,
) -> pygame.Rect:
    skin, shirt, hair = palette_from_key(citizen_id)
    pants = (max(20, shirt[0] - 35), max(20, shirt[1] - 38), max(20, shirt[2] - 35))
    shoulder = (min(255, shirt[0] + 24), min(255, shirt[1] + 20), min(255, shirt[2] + 20))
    outline = (28, 18, 36)

    width = 9 * scale
    height = 15 * scale
    bob = int(round(math.sin(walk_phase * 2.7) * 1.2)) if selected else 0
    rect = pygame.Rect(x, y + bob, width, height)

    def px(ix: int, iy: int, w: int, h: int, color: tuple[int, int, int]) -> None:
        pygame.draw.rect(
            surface,
            color,
            pygame.Rect(rect.left + ix * scale, rect.top + iy * scale, w * scale, h * scale),
        )

    leg_offset = 1 if math.sin(walk_phase * 8.0) > 0 else 0

    # Hair + head
    px(2, 0, 5, 1, hair)
    px(1, 1, 7, 1, hair)
    px(2, 2, 5, 3, skin)
    px(2, 2, 1, 1, hair)
    px(6, 2, 1, 1, hair)

    # Torso + arms
    px(2, 5, 5, 1, shoulder)
    px(2, 6, 5, 4, shirt)
    px(1, 5, 1, 4, shirt)
    px(7, 5, 1, 4, shirt)
    px(3, 7, 3, 1, shoulder)

    # Belt + legs
    px(2, 10, 5, 1, pants)
    px(2, 11 + leg_offset, 2, 3, pants)
    px(5, 11 + (1 - leg_offset), 2, 3, pants)
    px(2, 14, 2, 1, (52, 44, 48))
    px(5, 14, 2, 1, (52, 44, 48))

    # Outline accents
    pygame.draw.rect(surface, outline, rect, width=max(1, scale // 2))
    if selected:
        glow = rect.inflate(2, 2)
        pygame.draw.rect(surface, (210, 178, 132), glow, width=1)
    return rect


def draw_citizen_avatar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    citizen_id: str,
    name: str,
    selected: bool = False,
    time_s: float = 0.0,
) -> None:
    bob = int(round(math.sin(time_s * 5.0) * 2.0)) if selected else 0
    x = rect.left + 3
    y = rect.top + 3 + bob
    w = max(18, rect.width - 6)
    h = max(18, rect.height - 6)

    card = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surface, theme.COLOR_BORDER, card, border_radius=2)
    inner = card.inflate(-2, -2)
    pygame.draw.rect(surface, (52, 34, 74), inner, border_radius=2)

    if selected:
        glow = pygame.Rect(card.left - 1, card.top - 1, card.width + 2, card.height + 2)
        pygame.draw.rect(surface, (220, 188, 136), glow, width=1, border_radius=2)

    sprite_x = inner.left + inner.width // 2 - 8
    sprite_y = inner.top + 2
    draw_citizen_sprite(surface, sprite_x, sprite_y, citizen_id, scale=2, selected=selected, walk_phase=time_s)

    initials = "".join([part[0] for part in name.split()[:2]]).upper() or "?"
    draw_text(surface, initials[:2], theme.get_font(11, bold=True), theme.COLOR_TEXT_MUTED, (inner.centerx, inner.bottom - 4), "midbottom")

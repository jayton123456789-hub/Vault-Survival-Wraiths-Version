from __future__ import annotations

import hashlib
import math

import pygame

from . import theme
from .widgets import draw_text


def _palette_from_key(key: str) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    base = (80 + digest[0] % 90, 70 + digest[1] % 90, 95 + digest[2] % 90)
    shirt = (70 + digest[3] % 120, 80 + digest[4] % 90, 80 + digest[5] % 90)
    hair = (45 + digest[6] % 80, 35 + digest[7] % 60, 25 + digest[8] % 50)
    return base, shirt, hair


def draw_citizen_avatar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    citizen_id: str,
    name: str,
    selected: bool = False,
    time_s: float = 0.0,
) -> None:
    base, shirt, hair = _palette_from_key(citizen_id)
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

    torso = pygame.Rect(inner.left + inner.width // 2 - 4, inner.top + 9, 8, 8)
    head = pygame.Rect(inner.left + inner.width // 2 - 3, inner.top + 3, 6, 6)
    hair_band = pygame.Rect(head.left, head.top, head.width, 2)
    pygame.draw.rect(surface, shirt, torso)
    pygame.draw.rect(surface, base, head)
    pygame.draw.rect(surface, hair, hair_band)

    initials = "".join([part[0] for part in name.split()[:2]]).upper() or "?"
    draw_text(surface, initials[:2], theme.get_font(11, bold=True), theme.COLOR_TEXT_MUTED, (inner.centerx, inner.bottom - 4), "midbottom")

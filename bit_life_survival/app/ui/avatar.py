from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

import pygame

from . import theme
from .widgets import draw_text


def palette_from_key(key: str) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    skin = (148 + digest[0] % 58, 116 + digest[1] % 44, 96 + digest[2] % 42)
    shirt = (70 + digest[3] % 120, 72 + digest[4] % 110, 84 + digest[5] % 116)
    hair = (40 + digest[6] % 90, 28 + digest[7] % 70, 18 + digest[8] % 60)
    return skin, shirt, hair


@dataclass(slots=True)
class CitizenPalette:
    outline: tuple[int, int, int]
    skin: tuple[int, int, int]
    skin_shadow: tuple[int, int, int]
    shirt: tuple[int, int, int]
    shirt_shadow: tuple[int, int, int]
    shirt_highlight: tuple[int, int, int]
    pants: tuple[int, int, int]
    pants_shadow: tuple[int, int, int]
    hair: tuple[int, int, int]
    hair_shadow: tuple[int, int, int]
    shoe: tuple[int, int, int]


def _build_palette(citizen_id: str) -> CitizenPalette:
    skin, shirt, hair = palette_from_key(citizen_id)
    return CitizenPalette(
        outline=(26, 18, 34),
        skin=skin,
        skin_shadow=(max(24, skin[0] - 28), max(20, skin[1] - 26), max(18, skin[2] - 24)),
        shirt=shirt,
        shirt_shadow=(max(18, shirt[0] - 34), max(18, shirt[1] - 30), max(18, shirt[2] - 30)),
        shirt_highlight=(min(255, shirt[0] + 34), min(255, shirt[1] + 30), min(255, shirt[2] + 28)),
        pants=(max(20, shirt[0] - 24), max(20, shirt[1] - 28), max(20, shirt[2] - 22)),
        pants_shadow=(max(14, shirt[0] - 48), max(14, shirt[1] - 50), max(14, shirt[2] - 46)),
        hair=hair,
        hair_shadow=(max(10, hair[0] - 28), max(8, hair[1] - 24), max(6, hair[2] - 18)),
        shoe=(40, 36, 44),
    )


def _draw_px(
    surface: pygame.Surface,
    x: int,
    y: int,
    scale: int,
    color: tuple[int, int, int],
    blocks: list[tuple[int, int, int, int]],
) -> None:
    for bx, by, bw, bh in blocks:
        pygame.draw.rect(surface, color, pygame.Rect(x + bx * scale, y + by * scale, bw * scale, bh * scale))


def draw_citizen_sprite(
    surface: pygame.Surface,
    x: int,
    y: int,
    citizen_id: str,
    scale: int = 2,
    selected: bool = False,
    walk_phase: float = 0.0,
) -> pygame.Rect:
    palette = _build_palette(citizen_id)
    width = 16 * scale
    height = 16 * scale
    bob = int(round(math.sin(walk_phase * 3.0) * 1.4)) if selected else 0
    base_x = x
    base_y = y + bob
    rect = pygame.Rect(base_x, base_y, width, height)
    foot_swing = 1 if math.sin(walk_phase * 9.0) > 0 else 0

    # Body shadow
    _draw_px(
        surface,
        base_x,
        base_y,
        scale,
        (0, 0, 0, 0),
        [],
    )
    shadow = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 70), pygame.Rect(3 * scale, 13 * scale, 10 * scale, 3 * scale))
    surface.blit(shadow, (base_x, base_y))

    # Hair and head
    _draw_px(surface, base_x, base_y, scale, palette.hair_shadow, [(4, 2, 8, 1), (3, 3, 9, 1)])
    _draw_px(surface, base_x, base_y, scale, palette.hair, [(4, 1, 8, 1), (3, 2, 9, 1), (3, 4, 2, 1), (10, 4, 2, 1)])
    _draw_px(surface, base_x, base_y, scale, palette.skin_shadow, [(4, 4, 8, 2)])
    _draw_px(surface, base_x, base_y, scale, palette.skin, [(4, 3, 8, 1), (5, 5, 6, 2)])

    # Torso and arms
    _draw_px(surface, base_x, base_y, scale, palette.shirt_shadow, [(4, 8, 8, 3), (3, 8, 1, 3), (12, 8, 1, 3)])
    _draw_px(surface, base_x, base_y, scale, palette.shirt, [(4, 7, 8, 3), (3, 7, 1, 3), (12, 7, 1, 3)])
    _draw_px(surface, base_x, base_y, scale, palette.shirt_highlight, [(5, 7, 6, 1), (6, 8, 3, 1)])

    # Pants and legs
    _draw_px(surface, base_x, base_y, scale, palette.pants_shadow, [(4, 11, 8, 2)])
    _draw_px(surface, base_x, base_y, scale, palette.pants, [(4, 10, 8, 2)])
    if foot_swing:
        _draw_px(surface, base_x, base_y, scale, palette.pants, [(4, 12, 3, 3), (9, 13, 3, 2)])
    else:
        _draw_px(surface, base_x, base_y, scale, palette.pants, [(4, 13, 3, 2), (9, 12, 3, 3)])
    _draw_px(surface, base_x, base_y, scale, palette.shoe, [(4, 15, 3, 1), (9, 15, 3, 1)])

    # Per-pixel silhouette edges (not a hard box)
    _draw_px(surface, base_x, base_y, scale, palette.outline, [(3, 7, 1, 4), (12, 7, 1, 4), (4, 1, 8, 1), (4, 15, 8, 1)])

    if selected:
        glow = pygame.Surface((width + 8, height + 8), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (230, 202, 156, 62), glow.get_rect())
        surface.blit(glow, (base_x - 4, base_y - 4))
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

    sprite_x = inner.left + inner.width // 2 - 16
    sprite_y = inner.top + 2
    draw_citizen_sprite(surface, sprite_x, sprite_y, citizen_id, scale=2, selected=selected, walk_phase=time_s)

    initials = "".join([part[0] for part in name.split()[:2]]).upper() or "?"
    draw_text(surface, initials[:2], theme.get_font(11, bold=True), theme.COLOR_TEXT_MUTED, (inner.centerx, inner.bottom - 4), "midbottom")

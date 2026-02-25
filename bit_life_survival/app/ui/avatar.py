from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from functools import lru_cache

import pygame

from . import theme
from .widgets import draw_text


def _shade(color: tuple[int, int, int], delta: int) -> tuple[int, int, int]:
    return (
        max(0, min(255, color[0] + delta)),
        max(0, min(255, color[1] + delta)),
        max(0, min(255, color[2] + delta)),
    )


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
    gear: tuple[int, int, int]


def _build_palette(citizen_id: str) -> CitizenPalette:
    digest = hashlib.sha256(citizen_id.encode("utf-8")).digest()
    skin = (148 + digest[0] % 56, 114 + digest[1] % 42, 96 + digest[2] % 36)
    shirt = (74 + digest[3] % 110, 72 + digest[4] % 96, 84 + digest[5] % 100)
    hair = (28 + digest[6] % 90, 22 + digest[7] % 74, 16 + digest[8] % 58)
    gear = (96 + digest[9] % 80, 114 + digest[10] % 88, 86 + digest[11] % 74)
    return CitizenPalette(
        outline=(22, 14, 30),
        skin=skin,
        skin_shadow=_shade(skin, -30),
        shirt=shirt,
        shirt_shadow=_shade(shirt, -34),
        shirt_highlight=_shade(shirt, +28),
        pants=_shade(shirt, -18),
        pants_shadow=_shade(shirt, -44),
        hair=hair,
        hair_shadow=_shade(hair, -24),
        gear=gear,
    )


def _px(surface: pygame.Surface, color: tuple[int, int, int], blocks: list[tuple[int, int, int, int]]) -> None:
    for x, y, w, h in blocks:
        surface.fill(color, pygame.Rect(x, y, w, h))


def _pose_offsets(frame: int, pose: str) -> tuple[int, int, int]:
    if pose == "crouch":
        return (2, 1, 1)
    if pose == "jump":
        return (-4, 1, 0)
    if frame % 4 == 1:
        return (0, 1, 0)
    if frame % 4 == 3:
        return (1, -1, 0)
    return (0, 0, 0)


@lru_cache(maxsize=512)
def _render_sprite_64(citizen_id: str, frame: int, pose: str) -> pygame.Surface:
    palette = _build_palette(citizen_id)
    surf = pygame.Surface((64, 64), pygame.SRCALPHA)
    y_bob, arm_shift, leg_shift = _pose_offsets(frame, pose)

    # Ground shadow
    pygame.draw.ellipse(surf, (0, 0, 0, 72), pygame.Rect(16, 52 + max(0, y_bob), 32, 8))

    # Head + hair
    _px(surf, palette.hair_shadow, [(20, 10 + y_bob, 24, 7)])
    _px(surf, palette.hair, [(20, 8 + y_bob, 24, 5), (18, 11 + y_bob, 28, 4)])
    _px(surf, palette.skin_shadow, [(21, 16 + y_bob, 22, 10)])
    _px(surf, palette.skin, [(22, 15 + y_bob, 20, 10)])
    _px(surf, (30, 20, 30), [(27, 20 + y_bob, 3, 2), (34, 20 + y_bob, 3, 2)])

    # Torso
    torso_top = 25 + y_bob
    _px(surf, palette.shirt_shadow, [(19, torso_top + 2, 26, 16)])
    _px(surf, palette.shirt, [(20, torso_top, 24, 16)])
    _px(surf, palette.shirt_highlight, [(22, torso_top + 1, 20, 5), (24, torso_top + 7, 10, 2)])

    # Arms
    _px(surf, palette.shirt_shadow, [(14, torso_top + 4 + arm_shift, 6, 10), (44, torso_top + 4 - arm_shift, 6, 10)])
    _px(surf, palette.shirt, [(15, torso_top + 3 + arm_shift, 5, 9), (44, torso_top + 3 - arm_shift, 5, 9)])
    _px(surf, palette.skin, [(15, torso_top + 12 + arm_shift, 5, 3), (44, torso_top + 12 - arm_shift, 5, 3)])

    # Belt / gear
    _px(surf, palette.gear, [(21, torso_top + 15, 22, 3)])
    _px(surf, _shade(palette.gear, -22), [(23, torso_top + 16, 18, 1)])

    # Legs
    leg_top = torso_top + 18
    left_leg_x = 23 - leg_shift
    right_leg_x = 34 + leg_shift
    _px(surf, palette.pants_shadow, [(left_leg_x, leg_top + 2, 8, 12), (right_leg_x, leg_top + 2, 8, 12)])
    _px(surf, palette.pants, [(left_leg_x + 1, leg_top, 6, 12), (right_leg_x + 1, leg_top, 6, 12)])
    _px(surf, (44, 38, 48), [(left_leg_x + 1, leg_top + 12, 7, 3), (right_leg_x + 1, leg_top + 12, 7, 3)])

    if pose == "jump":
        _px(surf, palette.shirt_highlight, [(20, torso_top + 5, 6, 3), (38, torso_top + 5, 6, 3)])
    if pose == "crouch":
        _px(surf, palette.shirt_shadow, [(20, torso_top + 14, 24, 3)])

    # Outline silhouette
    pygame.draw.rect(surf, palette.outline, pygame.Rect(18, 8 + y_bob, 28, 44), 1)
    return surf


def draw_citizen_sprite(
    surface: pygame.Surface,
    x: int,
    y: int,
    citizen_id: str,
    scale: int = 2,
    selected: bool = False,
    walk_phase: float = 0.0,
    pose: str = "walk",
) -> pygame.Rect:
    frame = int(abs(walk_phase * 6.0)) % 4
    base = _render_sprite_64(citizen_id, frame=frame, pose=pose)
    target_size = max(24, 16 * max(1, int(scale)))
    sprite = pygame.transform.scale(base, (target_size, target_size))
    rect = pygame.Rect(x, y, target_size, target_size)

    if selected:
        glow = pygame.Surface((target_size + 10, target_size + 10), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (230, 208, 154, 68), glow.get_rect())
        surface.blit(glow, (x - 5, y - 4))
    surface.blit(sprite, rect)
    return rect


def draw_citizen_avatar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    citizen_id: str,
    name: str,
    selected: bool = False,
    time_s: float = 0.0,
) -> None:
    card = rect.inflate(-2, -2)
    pygame.draw.rect(surface, theme.COLOR_BORDER, card, border_radius=2)
    inner = card.inflate(-2, -2)
    pygame.draw.rect(surface, (52, 34, 74), inner, border_radius=2)
    if selected:
        glow = card.inflate(2, 2)
        pygame.draw.rect(surface, (220, 188, 136), glow, width=1, border_radius=2)
    size = min(inner.width - 4, inner.height - 14)
    sprite_scale = max(2, int(size / 16))
    sprite_size = 16 * sprite_scale
    draw_x = inner.centerx - sprite_size // 2
    draw_y = inner.top + 2 + (0 if not selected else int(math.sin(time_s * 4.0) * 1.5))
    draw_citizen_sprite(surface, draw_x, draw_y, citizen_id, scale=sprite_scale, selected=selected, walk_phase=time_s)
    initials = "".join(part[0] for part in name.split()[:2]).upper() or "?"
    draw_text(surface, initials[:2], theme.get_font(11, bold=True), theme.COLOR_TEXT_MUTED, (inner.centerx, inner.bottom - 3), "midbottom")

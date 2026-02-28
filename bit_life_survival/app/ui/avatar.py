from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from functools import lru_cache

import pygame

from . import theme
from .widgets import draw_text

GAMEPLAY_SOURCE_SIZE = 128
PORTRAIT_SOURCE_SIZE = 256


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
    hair: tuple[int, int, int]
    hair_shadow: tuple[int, int, int]
    jacket: tuple[int, int, int]
    jacket_shadow: tuple[int, int, int]
    jacket_highlight: tuple[int, int, int]
    pants: tuple[int, int, int]
    pants_shadow: tuple[int, int, int]
    boot: tuple[int, int, int]
    strap: tuple[int, int, int]
    gear: tuple[int, int, int]
    glow: tuple[int, int, int]


def _digest(citizen_id: str) -> bytes:
    return hashlib.sha256(citizen_id.encode("utf-8")).digest()


def _build_palette(citizen_id: str) -> CitizenPalette:
    seed = _digest(citizen_id)
    skin = (178 + seed[0] % 44, 138 + seed[1] % 42, 116 + seed[2] % 34)
    hair = (42 + seed[3] % 92, 28 + seed[4] % 68, 24 + seed[5] % 58)
    jacket = (66 + seed[6] % 86, 84 + seed[7] % 92, 110 + seed[8] % 96)
    pants = (56 + seed[9] % 72, 70 + seed[10] % 78, 92 + seed[11] % 88)
    gear = (82 + seed[12] % 76, 74 + seed[13] % 66, 60 + seed[14] % 54)
    glow = (230, 194 + seed[15] % 40, 124 + seed[16] % 44)
    return CitizenPalette(
        outline=(18, 14, 18),
        skin=skin,
        skin_shadow=_shade(skin, -28),
        hair=hair,
        hair_shadow=_shade(hair, -24),
        jacket=jacket,
        jacket_shadow=_shade(jacket, -34),
        jacket_highlight=_shade(jacket, 30),
        pants=pants,
        pants_shadow=_shade(pants, -30),
        boot=(58, 44, 38),
        strap=(108, 84, 62),
        gear=gear,
        glow=glow,
    )


def _px(surface: pygame.Surface, color: tuple[int, int, int], blocks: list[tuple[int, int, int, int]]) -> None:
    for x, y, w, h in blocks:
        surface.fill(color, pygame.Rect(x, y, w, h))


def _pose_offsets(frame: int, pose: str) -> tuple[int, int, int]:
    if pose == "jump":
        return (-8, 2, 2)
    if pose == "crouch":
        return (4, 1, 1)
    cycle = frame % 4
    if cycle == 0:
        return (0, 1, 0)
    if cycle == 1:
        return (0, 2, 1)
    if cycle == 2:
        return (1, -1, 0)
    return (1, -2, -1)


@lru_cache(maxsize=4096)
def _render_gameplay_sprite(citizen_id: str, frame: int, pose: str, blink_step: int) -> pygame.Surface:
    pal = _build_palette(citizen_id)
    seed = _digest(citizen_id)
    surf = pygame.Surface((GAMEPLAY_SOURCE_SIZE, GAMEPLAY_SOURCE_SIZE), pygame.SRCALPHA)
    y_bob, arm_shift, leg_shift = _pose_offsets(frame, pose)

    shadow_y = 105 + max(0, y_bob)
    pygame.draw.ellipse(surf, (0, 0, 0, 78), pygame.Rect(28, shadow_y, 72, 14))

    # Legs and boots
    leg_top = 72 + y_bob
    left_leg = 47 - leg_shift
    right_leg = 65 + leg_shift
    _px(surf, pal.pants_shadow, [(left_leg, leg_top + 3, 17, 27), (right_leg, leg_top + 3, 17, 27)])
    _px(surf, pal.pants, [(left_leg + 2, leg_top, 13, 26), (right_leg + 2, leg_top, 13, 26)])
    _px(surf, _shade(pal.pants, 18), [(left_leg + 3, leg_top + 1, 11, 5), (right_leg + 3, leg_top + 1, 11, 5)])
    _px(surf, pal.boot, [(left_leg + 1, leg_top + 27, 17, 9), (right_leg + 1, leg_top + 27, 17, 9)])
    _px(surf, _shade(pal.boot, 18), [(left_leg + 2, leg_top + 27, 14, 2), (right_leg + 2, leg_top + 27, 14, 2)])

    torso_top = 40 + y_bob

    # Backpack and straps
    _px(surf, _shade(pal.gear, -20), [(26, torso_top + 9, 14, 30), (24, torso_top + 16, 4, 12)])
    _px(surf, pal.gear, [(27, torso_top + 7, 11, 30), (24, torso_top + 15, 3, 10)])
    _px(surf, pal.strap, [(29, torso_top + 12, 7, 4), (29, torso_top + 23, 7, 4), (42, torso_top + 6, 9, 34), (77, torso_top + 6, 8, 34)])

    # Torso + vest
    _px(surf, pal.jacket_shadow, [(40, torso_top + 2, 48, 33)])
    _px(surf, pal.jacket, [(42, torso_top, 44, 31)])
    _px(surf, pal.jacket_highlight, [(45, torso_top + 2, 36, 6), (48, torso_top + 13, 24, 3)])
    _px(surf, pal.gear, [(50, torso_top + 10, 26, 18), (54, torso_top + 12, 18, 12)])
    _px(surf, _shade(pal.gear, -24), [(52, torso_top + 14, 22, 8), (58, torso_top + 24, 10, 2)])
    _px(surf, _shade(pal.gear, 20), [(54, torso_top + 12, 18, 3)])

    # Left arm (upper + forearm + hand)
    left_arm_top = torso_top + 8 + arm_shift
    _px(surf, pal.jacket_shadow, [(32, left_arm_top, 10, 11), (31, left_arm_top + 10, 10, 12)])
    _px(surf, pal.jacket, [(33, left_arm_top, 8, 10), (32, left_arm_top + 10, 8, 10)])
    _px(surf, pal.skin_shadow, [(32, left_arm_top + 20, 10, 5)])
    _px(surf, pal.skin, [(33, left_arm_top + 19, 8, 5)])

    # Right arm (upper + forearm + hand)
    right_arm_top = torso_top + 9 - arm_shift
    _px(surf, pal.jacket_shadow, [(86, right_arm_top, 10, 10), (87, right_arm_top + 9, 9, 11)])
    _px(surf, pal.jacket, [(86, right_arm_top, 8, 9), (87, right_arm_top + 9, 7, 9)])
    _px(surf, pal.skin_shadow, [(87, right_arm_top + 18, 9, 5)])
    _px(surf, pal.skin, [(88, right_arm_top + 17, 7, 5)])

    # Head + hair shape
    head_top = 16 + y_bob
    _px(surf, pal.skin_shadow, [(46, head_top + 6, 36, 28)])
    _px(surf, pal.skin, [(48, head_top + 4, 32, 28)])
    _px(surf, pal.hair_shadow, [(40, head_top + 2, 48, 18), (39, head_top + 12, 10, 8), (79, head_top + 12, 10, 8)])
    _px(
        surf,
        pal.hair,
        [
            (40, head_top, 48, 14),
            (36, head_top + 8, 16, 10),
            (79, head_top + 8, 12, 9),
            (56, head_top + 2, 14, 18),
            (50, head_top + 10, 6, 6),
            (71, head_top + 10, 6, 6),
        ],
    )

    # Eyebrows, eyes, pupils, and mouth
    brow = _shade(pal.hair_shadow, -20)
    _px(surf, brow, [(56, head_top + 15, 7, 2), (68, head_top + 15, 7, 2)])
    blink_on = ((blink_step + seed[21]) % 13) == 0
    if blink_on:
        _px(surf, pal.outline, [(57, head_top + 19, 6, 1), (69, head_top + 19, 6, 1)])
    else:
        _px(surf, (236, 236, 232), [(57, head_top + 18, 6, 4), (69, head_top + 18, 6, 4)])
        _px(surf, pal.outline, [(59, head_top + 18, 2, 4), (71, head_top + 18, 2, 4)])

    mouth_variant = (blink_step + frame + seed[22]) % 3
    if mouth_variant == 0:
        _px(surf, pal.outline, [(63, head_top + 26, 4, 1), (67, head_top + 26, 4, 1)])
    elif mouth_variant == 1:
        _px(surf, pal.outline, [(64, head_top + 26, 4, 1), (63, head_top + 27, 2, 1), (68, head_top + 27, 2, 1)])
    else:
        _px(surf, pal.outline, [(63, head_top + 27, 4, 1), (67, head_top + 27, 4, 1)])

    # Belt and pouches
    _px(surf, pal.strap, [(44, torso_top + 30, 40, 4), (56, torso_top + 30, 16, 6), (47, torso_top + 29, 6, 7), (74, torso_top + 29, 6, 7)])
    _px(surf, _shade(pal.strap, 20), [(44, torso_top + 30, 40, 1)])

    # Flashlight
    light_x = 92
    light_y = torso_top + 27 - arm_shift
    pygame.draw.circle(surf, (*pal.glow, 84), (light_x + 2, light_y + 2), 8)
    _px(surf, (84, 76, 64), [(light_x - 2, light_y - 2, 8, 8)])
    _px(surf, pal.glow, [(light_x + 1, light_y + 1, 3, 3)])

    # Outline cleanup
    _px(
        surf,
        pal.outline,
        [
            (47, head_top + 31, 34, 1),
            (42, torso_top + 31, 44, 1),
            (47, leg_top + 35, 16, 1),
            (65, leg_top + 35, 16, 1),
        ],
    )

    if pose == "jump":
        _px(surf, pal.jacket_highlight, [(44, torso_top + 18, 8, 4), (78, torso_top + 18, 6, 4)])
    elif pose == "crouch":
        _px(surf, pal.pants_shadow, [(48, leg_top + 18, 30, 7)])
        _px(surf, pal.skin_shadow, [(56, head_top + 29, 16, 2)])

    return surf


@lru_cache(maxsize=1024)
def _render_portrait_sprite(citizen_id: str, frame: int, pose: str) -> pygame.Surface:
    base = _render_gameplay_sprite(citizen_id, frame, pose, blink_step=frame)
    portrait = pygame.transform.scale(base, (PORTRAIT_SOURCE_SIZE, PORTRAIT_SOURCE_SIZE))
    vignette = pygame.Surface((PORTRAIT_SOURCE_SIZE, PORTRAIT_SOURCE_SIZE), pygame.SRCALPHA)
    pygame.draw.ellipse(
        vignette,
        (0, 0, 0, 56),
        pygame.Rect(14, PORTRAIT_SOURCE_SIZE - 60, PORTRAIT_SOURCE_SIZE - 28, 36),
    )
    portrait.blit(vignette, (0, 0))
    return portrait


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
    frame = int(abs(walk_phase * 7.0)) % 4
    blink_step = int(abs(walk_phase * 1.5)) % 20
    base = _render_gameplay_sprite(citizen_id, frame=frame, pose=pose, blink_step=blink_step)
    target_size = max(24, int(16 * max(1, scale)))
    sprite = pygame.transform.scale(base, (target_size, target_size))
    rect = pygame.Rect(int(x), int(y), target_size, target_size)

    if selected:
        glow = pygame.Surface((target_size + 12, target_size + 12), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (236, 210, 140, 82), glow.get_rect())
        surface.blit(glow, (rect.left - 6, rect.top - 4))
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
    pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, inner, border_radius=2)
    if selected:
        pygame.draw.rect(surface, (226, 198, 132), card.inflate(2, 2), width=1, border_radius=2)

    hero_size = min(inner.width - 4, inner.height - 14)
    hero_size = max(24, hero_size)
    frame = int(abs(time_s * 6.0)) % 4
    portrait = _render_portrait_sprite(citizen_id, frame=frame, pose="walk")
    hero = pygame.transform.scale(portrait, (hero_size, hero_size))
    bob = 0 if not selected else int(math.sin(time_s * 4.2) * 2)
    hero_rect = hero.get_rect(midtop=(inner.centerx, inner.top + 2 + bob))
    surface.blit(hero, hero_rect)

    initials = "".join(part[0] for part in name.split()[:2]).upper() or "?"
    draw_text(
        surface,
        initials[:2],
        theme.get_font(11, bold=True, kind="display"),
        theme.COLOR_TEXT_MUTED,
        (inner.centerx, inner.bottom - 3),
        "midbottom",
    )

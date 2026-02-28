from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import pygame

from . import theme

BUTTON_DIR = Path(__file__).resolve().parents[2] / "assets" / "ui" / "buttons"

SEMANTIC_FILES: dict[str, str] = {
    "new_game": "new_game_256x64.png",
    "continue": "continue_256x64.png",
    "options": "options_256x64.png",
    "exit": "exit_256x64.png",
    "loadout": "loadout_256x64.png",
    "deploy": "deploy_256x64.png",
    "settings": "settings_256x64.png",
    "main_menu": "main_menu_256x64.png",
    "draft_selected": "draft_selected_256x64.png",
    "use_the_claw": "use_the_claw_256x64.png",
    "storage": "storage_256x64.png",
    "crafting": "crafting_256x64.png",
    "drone_bay": "drone_bay_256x64.png",
    "back": "main_menu_256x64.png",
    "help": "options_256x64.png",
    "craft": "crafting_256x64.png",
    "equip_best": "loadout_256x64.png",
    "equip_all": "loadout_256x64.png",
    "mission": "continue_256x64.png",
    "vault": "storage_256x64.png",
    "show_log": "options_256x64.png",
    "retreat": "main_menu_256x64.png",
    "extract": "deploy_256x64.png",
    "use_aid": "crafting_256x64.png",
    "quit": "exit_256x64.png",
}

TEXT_TO_KEY: dict[str, str] = {
    "new game": "new_game",
    "continue": "continue",
    "options": "options",
    "exit": "exit",
    "loadout": "loadout",
    "deploy": "deploy",
    "settings": "settings",
    "main menu": "main_menu",
    "draft selected": "draft_selected",
    "use the claw": "use_the_claw",
    "storage": "storage",
    "crafting": "crafting",
    "drone bay": "drone_bay",
    "back": "back",
    "help": "help",
    "craft": "craft",
    "equip best": "equip_best",
    "equip all": "equip_all",
    "mission": "mission",
    "vault": "vault",
    "show log": "show_log",
    "retreat": "retreat",
    "extract": "extract",
    "use aid": "use_aid",
    "quit": "quit",
}

FILE_EMBEDDED_LABELS: dict[str, str] = {
    "new_game_256x64.png": "New Game",
    "continue_256x64.png": "Continue",
    "options_256x64.png": "Options",
    "exit_256x64.png": "Exit",
    "loadout_256x64.png": "Loadout",
    "deploy_256x64.png": "Deploy",
    "settings_256x64.png": "Settings",
    "main_menu_256x64.png": "Main Menu",
    "draft_selected_256x64.png": "Draft Selected",
    "use_the_claw_256x64.png": "Use The Claw",
    "storage_256x64.png": "Storage",
    "crafting_256x64.png": "Crafting",
    "drone_bay_256x64.png": "Drone Bay",
}

RenderMode = Literal["frame_text", "embedded_label", "procedural_fallback"]


def available_skin_keys() -> tuple[str, ...]:
    return tuple(SEMANTIC_FILES.keys())


def infer_skin_key(text: str) -> str | None:
    key = TEXT_TO_KEY.get(text.strip().lower())
    if key in SEMANTIC_FILES:
        return key
    return None


def _normalize_label(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _embedded_label_for_key(skin_key: str | None) -> str | None:
    if not skin_key:
        return None
    filename = SEMANTIC_FILES.get(skin_key)
    if not filename:
        return None
    return FILE_EMBEDDED_LABELS.get(filename)


def skin_has_embedded_label(skin_key: str | None) -> bool:
    return _embedded_label_for_key(skin_key) is not None


def skin_matches_label(skin_key: str | None, text: str) -> bool:
    if not skin_key:
        return False
    embedded = _embedded_label_for_key(skin_key)
    if embedded is None:
        return True
    return _normalize_label(text) == _normalize_label(embedded)


def clear_cache() -> None:
    _load_raw.cache_clear()
    _render_tinted.cache_clear()


@lru_cache(maxsize=128)
def _load_raw(skin_key: str) -> pygame.Surface | None:
    filename = SEMANTIC_FILES.get(skin_key)
    if not filename:
        return None
    path = BUTTON_DIR / filename
    if not path.exists():
        return None
    try:
        surf = pygame.image.load(str(path))
        if pygame.display.get_surface() is not None:
            return surf.convert_alpha()
        return surf
    except (pygame.error, OSError):
        return None


def _brighten(color: tuple[int, int, int], delta: int) -> tuple[int, int, int]:
    return (
        max(0, min(255, color[0] + delta)),
        max(0, min(255, color[1] + delta)),
        max(0, min(255, color[2] + delta)),
    )


def _single_hue_tint(raw: pygame.Surface, tone: tuple[int, int, int]) -> pygame.Surface:
    width, height = raw.get_size()
    tinted = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(height):
        for x in range(width):
            pixel = raw.get_at((x, y))
            alpha = pixel.a
            if alpha:
                # Preserve luminance from source art so frame details survive tinting.
                luma = (0.2126 * pixel.r + 0.7152 * pixel.g + 0.0722 * pixel.b) / 255.0
                strength = 0.35 + (0.65 * luma)
                tinted.set_at(
                    (x, y),
                    (
                        int(max(0, min(255, tone[0] * strength))),
                        int(max(0, min(255, tone[1] * strength))),
                        int(max(0, min(255, tone[2] * strength))),
                        alpha,
                    ),
                )
    return tinted


def _scrub_embedded_label_band(surface: pygame.Surface, tone: tuple[int, int, int]) -> None:
    width, height = surface.get_size()
    if width < 32 or height < 16:
        return
    # Wipe most embedded lettering so frame_text mode can render clean runtime labels.
    band_h = max(10, int(height * 0.58))
    band_w = max(18, int(width * 0.94))
    band_rect = pygame.Rect((width - band_w) // 2, (height - band_h) // 2, band_w, band_h)
    scrub = pygame.Surface((band_rect.width, band_rect.height), pygame.SRCALPHA)
    scrub.fill((tone[0], tone[1], tone[2], 255))
    pygame.draw.rect(
        scrub,
        (max(0, tone[0] - 10), max(0, tone[1] - 10), max(0, tone[2] - 10), 255),
        scrub.get_rect(),
        width=1,
        border_radius=4,
    )
    surface.blit(scrub, band_rect.topleft)


@lru_cache(maxsize=1024)
def _render_tinted(
    skin_key: str,
    width: int,
    height: int,
    tone_r: int,
    tone_g: int,
    tone_b: int,
    enabled: bool,
    render_mode: str,
) -> pygame.Surface | None:
    raw = _load_raw(skin_key)
    if raw is None:
        return None
    tone = (tone_r, tone_g, tone_b)
    if not enabled:
        tone = (
            (tone[0] + theme.COLOR_BUTTON_DISABLED[0]) // 2,
            (tone[1] + theme.COLOR_BUTTON_DISABLED[1]) // 2,
            (tone[2] + theme.COLOR_BUTTON_DISABLED[2]) // 2,
        )
    tinted = _single_hue_tint(raw, tone)
    if render_mode == "frame_text":
        _scrub_embedded_label_band(tinted, tone)
    if (width, height) != raw.get_size():
        return pygame.transform.scale(tinted, (width, height))
    return tinted


def get_button_surface(
    skin_key: str | None,
    size: tuple[int, int],
    hovered: bool,
    enabled: bool,
    render_mode: RenderMode = "frame_text",
) -> pygame.Surface | None:
    if not skin_key:
        return None
    if render_mode == "procedural_fallback":
        return None
    width = max(8, int(size[0]))
    height = max(8, int(size[1]))
    tone = theme.COLOR_BUTTON_FLAT
    if hovered and enabled:
        tone = _brighten(tone, 18)
    return _render_tinted(
        skin_key,
        width,
        height,
        tone[0],
        tone[1],
        tone[2],
        enabled,
        render_mode,
    )

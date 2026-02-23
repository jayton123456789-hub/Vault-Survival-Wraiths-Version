from __future__ import annotations

import json
import os
from pathlib import Path

import pygame

from .intro import play_intro

WINDOW_SIZE = (1280, 720)
WINDOW_TITLE = "Bit Life Survival"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_settings() -> dict:
    default_settings = {
        "disable_intro": False,
        "intro_use_cinematic_audio": True,
    }

    settings_path = _repo_root() / "settings.json"
    if settings_path.exists():
        try:
            loaded = json.loads(settings_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                default_settings.update(loaded)
        except json.JSONDecodeError:
            # Invalid settings should not block startup.
            pass

    disable_env = os.getenv("BLS_DISABLE_INTRO", "").strip().lower()
    if disable_env in {"1", "true", "yes", "on"}:
        default_settings["disable_intro"] = True

    return default_settings


def _run_main_menu(screen: pygame.Surface, clock: pygame.time.Clock) -> None:
    font_title = pygame.font.SysFont(None, 64)
    font_hint = pygame.font.SysFont(None, 30)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        screen.fill((12, 12, 16))
        title = font_title.render("Bit Life Survival", True, (230, 230, 240))
        subtitle = font_hint.render("Main menu/base shell placeholder - press ESC to quit", True, (170, 170, 185))
        screen.blit(title, title.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2 - 24)))
        screen.blit(subtitle, subtitle.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2 + 24)))
        pygame.display.flip()
        clock.tick(60)


def main() -> None:
    settings = _load_settings()
    assets_dir = _repo_root() / "bit_life_survival" / "assets" / "bbwg_intro"

    pygame.init()
    pygame.mixer.init()
    pygame.display.set_caption(WINDOW_TITLE)
    screen = pygame.display.set_mode(WINDOW_SIZE)
    clock = pygame.time.Clock()

    try:
        if not settings.get("disable_intro", False):
            play_intro(
                screen=screen,
                clock=clock,
                assets_dir=assets_dir,
                allow_skip=True,
                enable_cinematic_audio=bool(settings.get("intro_use_cinematic_audio", True)),
            )

        _run_main_menu(screen, clock)
    finally:
        pygame.mixer.quit()
        pygame.quit()


if __name__ == "__main__":
    main()

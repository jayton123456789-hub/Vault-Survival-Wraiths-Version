from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

import pygame


INTRO_TOTAL_SECONDS = 6.0
BLACK_SCREEN_END = 0.5
CALM_PHASE_END = 2.0
IMPACT_PHASE_END = 2.3
HOLD_PHASE_END = 4.5

WHOOSH_DELAY = 2.0
CINEMATIC_DELAY = 2.15


def _load_required_assets(assets_dir: Path) -> tuple[pygame.Surface, pygame.Surface, pygame.mixer.Sound, pygame.mixer.Sound | None]:
    frame1_path = assets_dir / "LOGOframe1.png"
    frame2_path = assets_dir / "LOGOframe2.png"
    whoosh_path = assets_dir / "dragon-studio-quick-whoosh-405448.mp3"
    cinematic_path = assets_dir / "dragon-studio-cinematic-intro-463216.mp3"

    for path in (frame1_path, frame2_path, whoosh_path):
        if not path.exists():
            raise FileNotFoundError(f"Missing BBWG intro asset: {path}")

    frame1 = pygame.image.load(str(frame1_path)).convert_alpha()
    frame2 = pygame.image.load(str(frame2_path)).convert_alpha()
    if frame1.get_size() != frame2.get_size():
        raise ValueError("LOGOframe1.png and LOGOframe2.png must have identical dimensions.")

    whoosh = pygame.mixer.Sound(str(whoosh_path))
    cinematic = pygame.mixer.Sound(str(cinematic_path)) if cinematic_path.exists() else None
    return frame1, frame2, whoosh, cinematic


def _draw_logo_centered(
    screen: pygame.Surface,
    source: pygame.Surface,
    scale: float,
    offset_x: int = 0,
    offset_y: int = 0,
    red_glow_alpha: int = 0,
) -> None:
    width = max(1, int(source.get_width() * scale))
    height = max(1, int(source.get_height() * scale))
    logo = pygame.transform.smoothscale(source, (width, height))

    rect = logo.get_rect(center=(screen.get_width() // 2 + offset_x, screen.get_height() // 2 + offset_y))
    screen.blit(logo, rect)

    if red_glow_alpha > 0:
        glow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        glow.fill((255, 35, 35, max(0, min(255, red_glow_alpha))))
        screen.blit(glow, rect.topleft, special_flags=pygame.BLEND_RGBA_ADD)


def _is_skip_event(event: pygame.event.Event) -> bool:
    return event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN)


def play_intro(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    assets_dir: Path,
    allow_skip: bool = True,
    enable_cinematic_audio: bool = True,
) -> bool:
    """
    Play the BBWG startup intro.

    Returns True if the intro was skipped by user input, False otherwise.
    """
    frame1, frame2, whoosh, cinematic = _load_required_assets(assets_dir)

    whoosh_played = False
    cinematic_played = False
    skipped = False

    intro_start_ms = pygame.time.get_ticks()
    while True:
        elapsed = (pygame.time.get_ticks() - intro_start_ms) / 1000.0
        if elapsed >= INTRO_TOTAL_SECONDS:
            break

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
            if allow_skip and _is_skip_event(event):
                whoosh.stop()
                if cinematic:
                    cinematic.stop()
                skipped = True
                return skipped

        screen.fill((0, 0, 0))

        if elapsed < BLACK_SCREEN_END:
            pass
        elif elapsed < CALM_PHASE_END:
            # 0.5s -> 2.0s: dormant logo with slow 2% scale-in.
            progress = (elapsed - BLACK_SCREEN_END) / (CALM_PHASE_END - BLACK_SCREEN_END)
            scale = 1.0 + 0.02 * progress
            _draw_logo_centered(screen, frame1, scale=scale)
        else:
            # Hard cut at 2.0s from frame1 to frame2.
            if not whoosh_played and elapsed >= WHOOSH_DELAY:
                whoosh.play()
                whoosh_played = True
            if enable_cinematic_audio and cinematic and (not cinematic_played) and elapsed >= CINEMATIC_DELAY:
                cinematic.play()
                cinematic_played = True

            if elapsed < IMPACT_PHASE_END:
                impact_progress = (elapsed - CALM_PHASE_END) / (IMPACT_PHASE_END - CALM_PHASE_END)
                shake_mag = max(0.0, 4.0 * (1.0 - impact_progress))
                shake_x = int(math.sin(elapsed * 130.0) * shake_mag)
                shake_y = int(math.cos(elapsed * 115.0) * shake_mag)
                glow_alpha = int(100 * (1.0 - impact_progress) + 30)
                _draw_logo_centered(
                    screen,
                    frame2,
                    scale=1.0,
                    offset_x=shake_x,
                    offset_y=shake_y,
                    red_glow_alpha=glow_alpha,
                )

                # Optional 1-2 frame subtle flash.
                if elapsed <= CALM_PHASE_END + (2.0 / 60.0):
                    flash = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
                    flash.fill((255, 255, 255, 28))
                    screen.blit(flash, (0, 0))
            elif elapsed < HOLD_PHASE_END:
                hold_progress = elapsed - IMPACT_PHASE_END
                breathe_scale = 1.0 + 0.006 * math.sin(hold_progress * 2.4)
                glow_alpha = int(18 + 10 * (1.0 + math.sin(hold_progress * 2.2)) * 0.5)
                _draw_logo_centered(screen, frame2, scale=breathe_scale, red_glow_alpha=glow_alpha)
            else:
                # 4.5s -> 6.0s: smooth fade out to black.
                _draw_logo_centered(screen, frame2, scale=1.0, red_glow_alpha=12)
                fade_progress = (elapsed - HOLD_PHASE_END) / (INTRO_TOTAL_SECONDS - HOLD_PHASE_END)
                fade_overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
                fade_overlay.fill((0, 0, 0, int(max(0, min(255, fade_progress * 255)))))
                screen.blit(fade_overlay, (0, 0))

        pygame.display.flip()
        clock.tick(60)

    return skipped


def play_startup_intro(
    assets_dir: Path,
    skip_intro: bool,
    use_cinematic_audio: bool,
    logger: Callable[[str], None] | None = None,
) -> bool:
    """
    Play intro with graceful fallback.

    Returns:
    - True if user skipped intro.
    - False if intro completed normally or was bypassed due to failure/settings.
    """
    if skip_intro:
        return False

    def _log(message: str) -> None:
        if logger:
            logger(message)

    try:
        pygame.init()
        try:
            pygame.mixer.init()
        except pygame.error:
            _log("Warning: intro audio unavailable (mixer init failed).")

        pygame.display.set_caption("Bit Life Survival - Studio Intro")
        screen = pygame.display.set_mode((1280, 720))
        clock = pygame.time.Clock()
        skipped = play_intro(
            screen=screen,
            clock=clock,
            assets_dir=assets_dir,
            allow_skip=True,
            enable_cinematic_audio=use_cinematic_audio and pygame.mixer.get_init() is not None,
        )
        return skipped
    except Exception as exc:  # noqa: BLE001
        _log(f"Warning: BBWG intro failed ({exc}). Continuing to base screen.")
        return False
    finally:
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
        except Exception:
            pass
        pygame.quit()

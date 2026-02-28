from __future__ import annotations

from pathlib import Path

import pygame


ROOT = Path(__file__).resolve().parents[1]
SPRITES_DIR = ROOT / "bit_life_survival" / "assets" / "sprites" / "citizens"


def _draw_runner(path: Path, flip: bool = False, crouch: bool = False) -> None:
    surf = pygame.Surface((128, 128), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    y = 6 if not crouch else 12
    pygame.draw.ellipse(surf, (0, 0, 0, 82), pygame.Rect(34, 104, 60, 14))
    pygame.draw.rect(surf, (24, 18, 22), pygame.Rect(42, 20 + y, 44, 54))
    pygame.draw.rect(surf, (206, 166, 132), pygame.Rect(47, 26 + y, 34, 28))
    pygame.draw.rect(surf, (82, 108, 136), pygame.Rect(44, 54 + y, 40, 30))
    pygame.draw.rect(surf, (110, 88, 66), pygame.Rect(38, 57 + y, 8, 28))
    pygame.draw.rect(surf, (110, 88, 66), pygame.Rect(82, 58 + y, 8, 26))
    pygame.draw.rect(surf, (70, 56, 44), pygame.Rect(48, 84 + y, 14, 24 if not crouch else 20))
    pygame.draw.rect(surf, (70, 56, 44), pygame.Rect(66, 84 + y, 14, 24 if not crouch else 20))
    pygame.draw.rect(surf, (36, 28, 22), pygame.Rect(44, 18 + y, 44, 18))
    pygame.draw.rect(surf, (44, 36, 28), pygame.Rect(32, 48 + y, 12, 36))
    pygame.draw.rect(surf, (118, 124, 130), pygame.Rect(32, 72 + y, 8, 10))
    pygame.draw.rect(surf, (252, 220, 148), pygame.Rect(88, 80 + y, 6, 6))
    if flip:
        surf = pygame.transform.flip(surf, True, False)
    pygame.image.save(surf, path)


def main() -> None:
    pygame.init()
    SPRITES_DIR.mkdir(parents=True, exist_ok=True)
    _draw_runner(SPRITES_DIR / "runner_idle.png", flip=False, crouch=False)
    _draw_runner(SPRITES_DIR / "runner_walk.png", flip=True, crouch=False)
    _draw_runner(SPRITES_DIR / "runner_crouch.png", flip=False, crouch=True)
    pygame.quit()


if __name__ == "__main__":
    main()

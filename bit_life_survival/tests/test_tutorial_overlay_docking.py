from __future__ import annotations

import pygame

from bit_life_survival.app.ui.overlays.tutorial import TutorialOverlay, TutorialStep


def test_tutorial_overlay_avoids_target_and_avoid_rects() -> None:
    pygame.init()
    surface = pygame.Surface((1280, 720))
    target = pygame.Rect(420, 560, 420, 120)
    avoid = pygame.Rect(0, 620, 1280, 100)
    overlay = TutorialOverlay(
        [TutorialStep(title="Dock", body="Move around blockers.", target_rect_getter=lambda: target)],
        avoid_rect_getters=[lambda: avoid],
    )
    overlay.draw(surface)
    assert overlay.last_panel_rect is not None
    assert not overlay.last_panel_rect.colliderect(target.inflate(8, 8))
    assert not overlay.last_panel_rect.colliderect(avoid.inflate(8, 8))

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.widgets import draw_text, wrap_text


@dataclass(slots=True)
class TutorialStep:
    title: str
    body: str
    target_rect_getter: Callable[[], pygame.Rect]


class TutorialOverlay:
    def __init__(self, steps: list[TutorialStep]) -> None:
        self.steps = steps
        self.index = 0
        self.visible = bool(steps)

    @property
    def complete(self) -> bool:
        return self.index >= len(self.steps)

    def handle_event(self, event: pygame.event.Event) -> str | None:
        if not self.visible or self.complete:
            return None
        if event.type == pygame.KEYDOWN:
            if event.key in {pygame.K_ESCAPE, pygame.K_s}:
                self.visible = False
                self.index = len(self.steps)
                return "skip"
            if event.key in {pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE, pygame.K_n}:
                self.index += 1
                if self.complete:
                    self.visible = False
                    return "done"
                return "next"
            if event.key in {pygame.K_LEFT, pygame.K_b}:
                self.index = max(0, self.index - 1)
                return "back"
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.index += 1
            if self.complete:
                self.visible = False
                return "done"
            return "next"
        return None

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible or self.complete:
            return
        step = self.steps[self.index]
        target = step.target_rect_getter()

        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        pygame.draw.rect(surface, (244, 220, 128), target.inflate(8, 8), width=3, border_radius=8)

        panel = pygame.Rect(surface.get_width() // 2 - 410, surface.get_height() - 210, 820, 180)
        pygame.draw.rect(surface, (26, 30, 40), panel, border_radius=10)
        pygame.draw.rect(surface, theme.COLOR_BORDER, panel, width=1, border_radius=10)

        y = panel.top + 14
        draw_text(surface, f"Tutorial {self.index + 1}/{len(self.steps)} - {step.title}", theme.get_font(22, bold=True), theme.COLOR_TEXT, (panel.left + 14, y))
        y += 34
        for line in wrap_text(step.body, theme.get_font(17), panel.width - 28):
            draw_text(surface, line, theme.get_font(17), theme.COLOR_TEXT_MUTED, (panel.left + 14, y))
            y += 22
        hint = "Next: Enter/Click | Back: Left Arrow | Skip: Esc"
        draw_text(surface, hint, theme.get_font(15), theme.COLOR_TEXT_MUTED, (panel.left + 14, panel.bottom - 18), "midleft")

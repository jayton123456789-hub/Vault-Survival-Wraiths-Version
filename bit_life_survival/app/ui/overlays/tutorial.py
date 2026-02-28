from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.widgets import clamp_wrapped_lines, draw_text, wrap_text


@dataclass(slots=True)
class TutorialStep:
    title: str
    body: str
    target_rect_getter: Callable[[], pygame.Rect]


class TutorialOverlay:
    def __init__(
        self,
        steps: list[TutorialStep],
        *,
        series_label: str = "Tutorial",
        avoid_rect_getters: list[Callable[[], pygame.Rect]] | None = None,
    ) -> None:
        self.steps = steps
        self.index = 0
        self.visible = bool(steps)
        self.series_label = series_label
        self.avoid_rect_getters = avoid_rect_getters or []
        self.last_panel_rect: pygame.Rect | None = None

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

    def _candidate_panel_rects(self, target: pygame.Rect, panel_size: tuple[int, int], bounds: pygame.Rect) -> list[pygame.Rect]:
        width, height = panel_size
        gap = 14
        cx, cy = target.centerx, target.centery
        return [
            pygame.Rect(cx - (width // 2), target.bottom + gap, width, height),  # bottom
            pygame.Rect(cx - (width // 2), target.top - gap - height, width, height),  # top
            pygame.Rect(target.right + gap, cy - (height // 2), width, height),  # right
            pygame.Rect(target.left - gap - width, cy - (height // 2), width, height),  # left
            pygame.Rect(bounds.centerx - (width // 2), bounds.bottom - height - 12, width, height),  # fallback
        ]

    def _clamp_to_bounds(self, rect: pygame.Rect, bounds: pygame.Rect) -> pygame.Rect:
        clamped = rect.copy()
        clamped.x = max(bounds.left, min(clamped.x, bounds.right - clamped.width))
        clamped.y = max(bounds.top, min(clamped.y, bounds.bottom - clamped.height))
        return clamped

    def _resolve_panel_rect(self, surface: pygame.Surface, target: pygame.Rect, panel_size: tuple[int, int]) -> pygame.Rect:
        bounds = surface.get_rect().inflate(-10, -10)
        avoids = [getter().inflate(8, 8) for getter in self.avoid_rect_getters]
        target_safe = target.inflate(10, 10)
        for candidate in self._candidate_panel_rects(target, panel_size, bounds):
            candidate = self._clamp_to_bounds(candidate, bounds)
            if candidate.colliderect(target_safe):
                continue
            if any(candidate.colliderect(rect) for rect in avoids):
                continue
            return candidate
        return self._clamp_to_bounds(self._candidate_panel_rects(target, panel_size, bounds)[-1], bounds)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible or self.complete:
            return
        step = self.steps[self.index]
        target = step.target_rect_getter()

        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        pygame.draw.rect(surface, (244, 220, 128), target.inflate(8, 8), width=3, border_radius=8)

        panel_w = max(460, min(surface.get_width() - 24, 860))
        body_font = theme.get_font(17)
        raw_lines = wrap_text(step.body, body_font, panel_w - 28)
        clamped_lines = raw_lines[:6]
        panel_h = 108 + (len(clamped_lines) * 22)
        panel_h = max(160, min(panel_h, surface.get_height() - 24))
        panel = self._resolve_panel_rect(surface, target, (panel_w, panel_h))
        self.last_panel_rect = panel.copy()

        pygame.draw.rect(surface, (26, 30, 40), panel, border_radius=10)
        pygame.draw.rect(surface, theme.COLOR_BORDER, panel, width=1, border_radius=10)

        y = panel.top + 14
        step_label = f"{self.series_label} {self.index + 1}/{len(self.steps)} - {step.title}"
        draw_text(surface, step_label, theme.get_font(22, bold=True), theme.COLOR_TEXT, (panel.left + 14, y))
        y += 34
        body_rect = pygame.Rect(panel.left + 14, y, panel.width - 28, panel.height - 74)
        lines, _ = clamp_wrapped_lines(step.body, body_font, body_rect.width, body_rect.height - 26, line_spacing=4)
        for line in lines:
            draw_text(surface, line, body_font, theme.COLOR_TEXT_MUTED, (body_rect.left, y))
            y += body_font.get_linesize() + 4
        hint = "Next: Enter/Click | Back: Left Arrow | Skip: Esc"
        draw_text(surface, hint, theme.get_font(15), theme.COLOR_TEXT_MUTED, (panel.left + 14, panel.bottom - 18), "midleft")

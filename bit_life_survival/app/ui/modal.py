from __future__ import annotations

from dataclasses import dataclass

import pygame

from . import theme
from .layout import anchored_rect, split_columns
from .widgets import Button, Panel, draw_text, wrap_text


@dataclass(slots=True)
class ModalButton:
    id: str
    label: str
    hotkey: int | None = None


class Modal:
    def __init__(
        self,
        title: str,
        body_lines: list[str],
        buttons: list[ModalButton],
    ) -> None:
        self.title = title
        self.body_lines = body_lines
        self.buttons = buttons
        self._button_widgets: list[tuple[Button, str]] = []

    def _build_buttons(self, content_rect: pygame.Rect) -> None:
        self._button_widgets.clear()
        buttons_rect = pygame.Rect(content_rect.left + 12, content_rect.bottom - 64, content_rect.width - 24, 44)
        cols = split_columns(buttons_rect, [1.0] * max(1, len(self.buttons)), gap=10)
        for col, button_def in zip(cols, self.buttons):
            self._button_widgets.append((Button(col, button_def.label, hotkey=button_def.hotkey), button_def.id))

    def handle_event(self, event: pygame.event.Event) -> str | None:
        for button, button_id in self._button_widgets:
            if button.handle_event(event):
                return button_id
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "cancel"
        return None

    def draw(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        container = anchored_rect(surface.get_rect(), (min(820, surface.get_width() - 60), min(520, surface.get_height() - 60)))
        panel = Panel(container, title=self.title, bg=(28, 32, 42))
        panel.draw(surface)

        body_rect = pygame.Rect(container.left + 18, container.top + 52, container.width - 36, container.height - 128)
        font = theme.get_font(20)
        y = body_rect.top
        for raw_line in self.body_lines:
            lines = wrap_text(raw_line, font, body_rect.width)
            for line in lines:
                draw_text(surface, line, font, theme.COLOR_TEXT, (body_rect.left, y))
                y += 24
            y += 4

        self._build_buttons(container)
        mouse_pos = pygame.mouse.get_pos()
        for button, _ in self._button_widgets:
            button.draw(surface, mouse_pos)

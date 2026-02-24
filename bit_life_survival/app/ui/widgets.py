from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pygame

from . import theme


def draw_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    pos: tuple[int, int],
    anchor: str = "topleft",
) -> pygame.Rect:
    rendered = font.render(text, True, color)
    rect = rendered.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(rendered, rect)
    return rect


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    if max_width <= 0:
        return [text]
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


@dataclass(slots=True)
class Label:
    text: str
    rect: pygame.Rect
    color: tuple[int, int, int] = theme.COLOR_TEXT
    size: int = 20
    bold: bool = False
    align: str = "topleft"

    def draw(self, surface: pygame.Surface) -> None:
        draw_text(surface, self.text, theme.get_font(self.size, bold=self.bold), self.color, getattr(self.rect, self.align), self.align)


@dataclass(slots=True)
class Panel:
    rect: pygame.Rect
    title: str | None = None
    bg: tuple[int, int, int] = theme.COLOR_PANEL
    border: tuple[int, int, int] = theme.COLOR_BORDER

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, self.bg, self.rect, border_radius=theme.BORDER_RADIUS)
        pygame.draw.rect(surface, self.border, self.rect, width=1, border_radius=theme.BORDER_RADIUS)
        if self.title:
            draw_text(
                surface,
                self.title,
                theme.get_font(18, bold=True),
                theme.COLOR_TEXT,
                (self.rect.left + theme.PADDING, self.rect.top + theme.PADDING),
            )


@dataclass(slots=True)
class Button:
    rect: pygame.Rect
    text: str
    on_click: Callable[[], None] | None = None
    hotkey: int | None = None
    tooltip: str | None = None
    enabled: bool = True
    hovered: bool = False
    bg: tuple[int, int, int] = theme.COLOR_PANEL_ALT
    bg_hover: tuple[int, int, int] = theme.COLOR_ACCENT_SOFT
    bg_disabled: tuple[int, int, int] = (48, 50, 58)
    fg: tuple[int, int, int] = theme.COLOR_TEXT

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled:
            return False
        if self.hotkey is not None and event.type == pygame.KEYDOWN and event.key == self.hotkey:
            if self.on_click:
                self.on_click()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            if self.on_click:
                self.on_click()
            return True
        return False

    def draw(self, surface: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
        self.hovered = self.enabled and self.rect.collidepoint(mouse_pos)
        if not self.enabled:
            bg = self.bg_disabled
            fg = theme.COLOR_TEXT_MUTED
        elif self.hovered:
            bg = self.bg_hover
            fg = self.fg
        else:
            bg = self.bg
            fg = self.fg
        pygame.draw.rect(surface, bg, self.rect, border_radius=theme.BORDER_RADIUS)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self.rect, width=1, border_radius=theme.BORDER_RADIUS)
        draw_text(surface, self.text, theme.get_font(20, bold=True), fg, self.rect.center, "center")


@dataclass(slots=True)
class ProgressBar:
    rect: pygame.Rect
    value: float
    max_value: float
    label: str = ""
    color: tuple[int, int, int] = theme.COLOR_ACCENT

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, theme.COLOR_PROGRESS_BG, self.rect, border_radius=theme.BORDER_RADIUS)
        ratio = 0.0 if self.max_value <= 0 else max(0.0, min(1.0, self.value / self.max_value))
        fill = pygame.Rect(self.rect.left, self.rect.top, int(self.rect.width * ratio), self.rect.height)
        pygame.draw.rect(surface, self.color, fill, border_radius=theme.BORDER_RADIUS)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self.rect, width=1, border_radius=theme.BORDER_RADIUS)
        if self.label:
            draw_text(surface, self.label, theme.get_font(16, bold=True), theme.COLOR_TEXT, self.rect.center, "center")


@dataclass(slots=True)
class ScrollList:
    rect: pygame.Rect
    row_height: int = 28
    items: list[str] = field(default_factory=list)
    selected_index: int | None = None
    offset: int = 0
    on_select: Callable[[int], None] | None = None

    def set_items(self, items: list[str]) -> None:
        self.items = items
        if self.selected_index is not None and self.selected_index >= len(items):
            self.selected_index = None
        self.offset = max(0, min(self.offset, max(0, len(self.items) - self.visible_rows())))

    def visible_rows(self) -> int:
        return max(1, self.rect.height // self.row_height)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEWHEEL:
            self.offset = max(0, self.offset - event.y)
            self.offset = min(self.offset, max(0, len(self.items) - self.visible_rows()))
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            rel_y = event.pos[1] - self.rect.top
            row = rel_y // self.row_height
            index = self.offset + row
            if 0 <= index < len(self.items):
                self.selected_index = index
                if self.on_select:
                    self.on_select(index)
                return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP and self.items:
                self.selected_index = 0 if self.selected_index is None else max(0, self.selected_index - 1)
                if self.selected_index < self.offset:
                    self.offset = self.selected_index
                if self.on_select:
                    self.on_select(self.selected_index)
                return True
            if event.key == pygame.K_DOWN and self.items:
                self.selected_index = 0 if self.selected_index is None else min(len(self.items) - 1, self.selected_index + 1)
                limit = self.offset + self.visible_rows() - 1
                if self.selected_index > limit:
                    self.offset = self.selected_index - self.visible_rows() + 1
                if self.on_select:
                    self.on_select(self.selected_index)
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, self.rect, border_radius=theme.BORDER_RADIUS)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self.rect, width=1, border_radius=theme.BORDER_RADIUS)

        start = self.offset
        end = min(len(self.items), start + self.visible_rows())
        y = self.rect.top
        font = theme.get_font(16)
        for index in range(start, end):
            row_rect = pygame.Rect(self.rect.left + 2, y + 2, self.rect.width - 4, self.row_height - 4)
            if self.selected_index == index:
                pygame.draw.rect(surface, theme.COLOR_ACCENT_SOFT, row_rect, border_radius=6)
            draw_text(surface, self.items[index], font, theme.COLOR_TEXT, (row_rect.left + 8, row_rect.centery), "midleft")
            y += self.row_height

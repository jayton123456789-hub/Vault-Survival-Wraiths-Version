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
    rendered = font.render(text, False, color)
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
        _draw_pixel_frame(surface, self.rect, self.bg, self.border)
        if self.title:
            title_rect = pygame.Rect(
                self.rect.left + theme.BORDER_WIDTH + 2,
                self.rect.top + theme.BORDER_WIDTH + 2,
                self.rect.width - (theme.BORDER_WIDTH * 2) - 4,
                26,
            )
            pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, title_rect, border_radius=theme.BORDER_RADIUS)
            pygame.draw.line(
                surface,
                theme.COLOR_BORDER_INNER,
                (title_rect.left, title_rect.bottom),
                (title_rect.right, title_rect.bottom),
                1,
            )
            draw_text(
                surface,
                self.title,
                theme.get_font(17, bold=True),
                theme.COLOR_TEXT,
                (title_rect.left + 6, title_rect.centery),
                "midleft",
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
    bg_disabled: tuple[int, int, int] = theme.COLOR_BUTTON_DISABLED
    fg: tuple[int, int, int] = theme.COLOR_TEXT
    tooltip_delay_ms: int = 250
    _hover_start_ms: int | None = None

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
        now_ms = pygame.time.get_ticks()
        if self.hovered:
            if self._hover_start_ms is None:
                self._hover_start_ms = now_ms
        else:
            self._hover_start_ms = None

        if not self.enabled:
            top = self.bg_disabled
            bottom = self.bg_disabled
            fg = theme.COLOR_TEXT_MUTED
        elif self.hovered:
            top = theme.COLOR_BUTTON_TOP_HOVER
            bottom = self.bg_hover
            fg = self.fg
        else:
            top = theme.COLOR_BUTTON_TOP
            bottom = theme.COLOR_BUTTON_BOTTOM
            fg = self.fg
        _draw_pixel_button(surface, self.rect, top, bottom, theme.COLOR_BORDER)
        font_size = max(12, min(20, int(self.rect.height * 0.48)))
        draw_text(surface, self.text, theme.get_font(font_size, bold=True), fg, self.rect.center, "center")

    def tooltip_visible(self) -> bool:
        if not self.hovered or not self.tooltip:
            return False
        if self._hover_start_ms is None:
            return False
        return (pygame.time.get_ticks() - self._hover_start_ms) >= self.tooltip_delay_ms


@dataclass(slots=True)
class ProgressBar:
    rect: pygame.Rect
    value: float
    max_value: float
    label: str = ""
    color: tuple[int, int, int] = theme.COLOR_ACCENT

    def draw(self, surface: pygame.Surface) -> None:
        _draw_pixel_frame(surface, self.rect, theme.COLOR_PROGRESS_BG, theme.COLOR_BORDER)
        ratio = 0.0 if self.max_value <= 0 else max(0.0, min(1.0, self.value / self.max_value))
        fill = pygame.Rect(
            self.rect.left + theme.BORDER_WIDTH,
            self.rect.top + theme.BORDER_WIDTH,
            max(0, int((self.rect.width - theme.BORDER_WIDTH * 2) * ratio)),
            max(0, self.rect.height - theme.BORDER_WIDTH * 2),
        )
        pygame.draw.rect(surface, self.color, fill, border_radius=theme.BORDER_RADIUS)
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
        _draw_pixel_frame(surface, self.rect, theme.COLOR_PANEL_ALT, theme.COLOR_BORDER)

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


def hovered_tooltip(buttons: list[Button]) -> str | None:
    for button in buttons:
        if button.tooltip_visible():
            return button.tooltip
    return None


def draw_tooltip_bar(surface: pygame.Surface, rect: pygame.Rect, text: str) -> None:
    _draw_pixel_frame(surface, rect, theme.COLOR_PANEL_ALT, theme.COLOR_BORDER)
    draw_text(surface, text, theme.get_font(15), theme.COLOR_TEXT_MUTED, (rect.left + 10, rect.centery), "midleft")


def _draw_pixel_frame(
    surface: pygame.Surface,
    rect: pygame.Rect,
    fill_color: tuple[int, int, int],
    border_color: tuple[int, int, int],
) -> None:
    pygame.draw.rect(surface, border_color, rect, border_radius=theme.BORDER_RADIUS)
    inner = rect.inflate(-theme.BORDER_WIDTH * 2, -theme.BORDER_WIDTH * 2)
    if inner.width <= 0 or inner.height <= 0:
        return
    pygame.draw.rect(surface, fill_color, inner, border_radius=theme.BORDER_RADIUS)
    if inner.width > 4 and inner.height > 4:
        highlight_rect = inner.inflate(-2, -2)
        pygame.draw.rect(
            surface,
            theme.COLOR_BORDER_INNER,
            highlight_rect,
            width=theme.BORDER_INNER_WIDTH,
            border_radius=theme.BORDER_RADIUS,
        )


def _draw_pixel_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    top_color: tuple[int, int, int],
    bottom_color: tuple[int, int, int],
    border_color: tuple[int, int, int],
) -> None:
    _draw_pixel_frame(surface, rect, bottom_color, border_color)
    top_rect = pygame.Rect(
        rect.left + theme.BORDER_WIDTH + 1,
        rect.top + theme.BORDER_WIDTH + 1,
        rect.width - (theme.BORDER_WIDTH * 2) - 2,
        max(0, rect.height // 2 - 1),
    )
    if top_rect.width > 0 and top_rect.height > 0:
        pygame.draw.rect(surface, top_color, top_rect, border_radius=theme.BORDER_RADIUS)

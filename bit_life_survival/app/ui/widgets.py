from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

import pygame

from . import button_skins, theme
from .layout import split_columns


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


def clamp_wrapped_lines(
    text: str,
    font: pygame.font.Font,
    max_width: int,
    max_height: int,
    line_spacing: int = 2,
) -> tuple[list[str], bool]:
    if max_height <= 0:
        return [], bool(text)
    lines = wrap_text(text, font, max_width)
    line_height = max(1, font.get_linesize())
    visible = max(1, (max_height + line_spacing) // (line_height + line_spacing))
    clipped = len(lines) > visible
    if not clipped:
        return lines, False
    kept = lines[:visible]
    if kept:
        kept[-1] = "..."
    return kept, True


def draw_wrapped_text_clamped(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    rect: pygame.Rect,
    line_spacing: int = 2,
) -> tuple[int, bool]:
    lines, clipped = clamp_wrapped_lines(text, font, rect.width, rect.height, line_spacing=line_spacing)
    y = rect.top
    for line in lines:
        draw_text(surface, line, font, color, (rect.left, y))
        y += font.get_linesize() + line_spacing
    return y, clipped


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
        _draw_pixel_frame(surface, self.rect, self.bg, self.border, draw_shadow=True, shadow_alpha=56, shadow_offset=(2, 2))
        if self.title:
            title_rect = pygame.Rect(
                self.rect.left + theme.BORDER_WIDTH + 2,
                self.rect.top + theme.BORDER_WIDTH + 2,
                self.rect.width - (theme.BORDER_WIDTH * 2) - 4,
                26,
            )
            pygame.draw.rect(surface, _mix_color(theme.COLOR_PANEL_ALT, theme.COLOR_ACCENT_SOFT, 0.18), title_rect, border_radius=theme.BORDER_RADIUS)
            pygame.draw.line(
                surface,
                theme.COLOR_BORDER_INNER,
                (title_rect.left, title_rect.bottom),
                (title_rect.right, title_rect.bottom),
                1,
            )
            accent_rect = pygame.Rect(title_rect.left + 2, title_rect.top + 3, 4, max(1, title_rect.height - 6))
            pygame.draw.rect(surface, theme.COLOR_ACCENT, accent_rect, border_radius=1)
            draw_text(
                surface,
                self.title,
                theme.get_font(theme.FONT_SIZE_SECTION, bold=True, kind="display"),
                theme.COLOR_TEXT,
                (title_rect.left + 10, title_rect.centery),
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
    skin_key: str | None = None
    allow_skin: bool = True
    text_override_color: tuple[int, int, int] | None = None
    skin_embeds_label: bool | None = None
    skin_render_mode: button_skins.RenderMode = "frame_text"
    text_align: Literal["center", "left"] = "center"
    text_fit_mode: Literal["ellipsis", "clip", "none"] = "ellipsis"
    max_font_role: theme.FontRole = "title"
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
            tone = _mix_color(theme.COLOR_BUTTON_FLAT, theme.COLOR_BUTTON_DISABLED, 0.55)
        elif self.hovered:
            tone = _brighten_color(theme.COLOR_BUTTON_FLAT, 18)
        else:
            tone = theme.COLOR_BUTTON_FLAT
        fg = _best_contrast_text(tone, preferred=self.fg)
        if self.text_override_color is not None:
            fg = self.text_override_color if self.enabled else theme.COLOR_TEXT_MUTED

        resolved_skin = self.skin_key or button_skins.infer_skin_key(self.text)
        skin = None
        if self.allow_skin and self.skin_render_mode != "procedural_fallback":
            can_use_skin = True
            if self.skin_render_mode == "embedded_label":
                can_use_skin = button_skins.skin_matches_label(resolved_skin, self.text)
            if can_use_skin:
                skin = button_skins.get_button_surface(
                    resolved_skin,
                    self.rect.size,
                    hovered=self.hovered,
                    enabled=self.enabled,
                    render_mode=self.skin_render_mode,
                )
        if skin is not None:
            surface.blit(skin, self.rect)
            pygame.draw.rect(surface, theme.COLOR_BORDER, self.rect, width=1, border_radius=theme.BORDER_RADIUS)
        else:
            _draw_pixel_button(surface, self.rect, tone, tone, theme.COLOR_BORDER)
        if self.enabled and self.hovered:
            pygame.draw.rect(surface, _mix_color(theme.COLOR_ACCENT, (255, 255, 255), 0.18), self.rect, width=1, border_radius=theme.BORDER_RADIUS)
        if not self.enabled:
            disabled_overlay = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            disabled_overlay.fill((18, 14, 14, 46))
            surface.blit(disabled_overlay, self.rect.topleft)

        draw_overlay_label = True
        if skin is not None and self.skin_render_mode == "embedded_label":
            embeds_label = self.skin_embeds_label
            if embeds_label is None:
                embeds_label = button_skins.skin_has_embedded_label(resolved_skin)
            draw_overlay_label = not embeds_label
        if draw_overlay_label:
            role_caps = {
                "title": theme.FONT_SIZE_TITLE,
                "section": theme.FONT_SIZE_SECTION,
                "body": theme.FONT_SIZE_BODY,
                "meta": theme.FONT_SIZE_META,
            }
            role_cap = role_caps.get(self.max_font_role, theme.FONT_SIZE_TITLE)
            font_size = max(theme.FONT_SIZE_META, min(role_cap, int(self.rect.height * 0.44)))
            use_bold = self.max_font_role == "title"
            font_kind = "display" if self.max_font_role in {"title", "section"} else "body"
            font = theme.get_font(font_size, bold=use_bold, kind=font_kind)
            text_rect = self.rect.inflate(-12, -8)
            text = self.text
            if self.text_fit_mode == "ellipsis":
                text = _fit_text_ellipsis(font, text, max(8, text_rect.width))
            old_clip = surface.get_clip()
            surface.set_clip(text_rect)
            shadow = (max(0, fg[0] - 72), max(0, fg[1] - 72), max(0, fg[2] - 72))
            if self.text_align == "left":
                draw_text(surface, text, font, shadow, (text_rect.left + 1, text_rect.centery + 1), "midleft")
                draw_text(surface, text, font, fg, (text_rect.left, text_rect.centery), "midleft")
            else:
                draw_text(surface, text, font, shadow, (text_rect.centerx + 1, text_rect.centery + 1), "center")
                draw_text(surface, text, font, fg, text_rect.center, "center")
            surface.set_clip(old_clip)

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
    row_renderer: Callable[[pygame.Surface, pygame.Rect, int, str, bool, float], None] | None = None

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
        font = theme.get_font(theme.FONT_SIZE_BODY)
        now_s = pygame.time.get_ticks() / 1000.0
        has_scrollbar = len(self.items) > self.visible_rows()
        scrollbar_w = 8 if has_scrollbar else 0
        for index in range(start, end):
            row_rect = pygame.Rect(self.rect.left + 2, y + 2, self.rect.width - 4 - scrollbar_w, self.row_height - 4)
            selected = self.selected_index == index
            if index % 2 == 1:
                pygame.draw.rect(surface, _mix_color(theme.COLOR_PANEL_ALT, theme.COLOR_PROGRESS_BG, 0.38), row_rect, border_radius=4)
            if selected:
                pygame.draw.rect(surface, theme.COLOR_ACCENT_SOFT, row_rect, border_radius=6)
                pygame.draw.rect(surface, theme.COLOR_ACCENT, row_rect, width=1, border_radius=6)
            if self.row_renderer is not None:
                self.row_renderer(surface, row_rect, index, self.items[index], selected, now_s)
            else:
                text = _fit_text_ellipsis(font, self.items[index], max(8, row_rect.width - 12))
                draw_text(surface, text, font, theme.COLOR_TEXT, (row_rect.left + 8, row_rect.centery), "midleft")
            y += self.row_height
        if has_scrollbar:
            track = pygame.Rect(self.rect.right - 7, self.rect.top + 3, 4, self.rect.height - 6)
            pygame.draw.rect(surface, theme.COLOR_PROGRESS_BG, track, border_radius=2)
            visible = self.visible_rows()
            total = max(1, len(self.items))
            thumb_h = max(12, int(track.height * (visible / total)))
            range_max = max(1, total - visible)
            t = self.offset / range_max
            thumb_y = track.top + int((track.height - thumb_h) * t)
            thumb = pygame.Rect(track.left, thumb_y, track.width, thumb_h)
            pygame.draw.rect(surface, theme.COLOR_ACCENT_SOFT, thumb, border_radius=2)
            pygame.draw.rect(surface, theme.COLOR_BORDER, thumb, width=1, border_radius=2)


@dataclass(slots=True)
class SectionCard:
    rect: pygame.Rect
    title: str
    muted: bool = False

    def draw(self, surface: pygame.Surface) -> pygame.Rect:
        bg = theme.COLOR_PANEL_ALT if not self.muted else theme.COLOR_PROGRESS_BG
        _draw_pixel_frame(surface, self.rect, bg, theme.COLOR_BORDER, draw_shadow=True, shadow_alpha=36, shadow_offset=(1, 2))
        title_rect = pygame.Rect(self.rect.left + 2, self.rect.top + 2, self.rect.width - 4, 22)
        pygame.draw.rect(surface, _mix_color(theme.COLOR_PANEL, theme.COLOR_ACCENT_SOFT, 0.12), title_rect, border_radius=2)
        pygame.draw.line(surface, theme.COLOR_BORDER_INNER, (title_rect.left, title_rect.bottom), (title_rect.right, title_rect.bottom), 1)
        accent = pygame.Rect(title_rect.left + 2, title_rect.top + 2, 3, max(1, title_rect.height - 4))
        pygame.draw.rect(surface, theme.COLOR_ACCENT_SOFT, accent, border_radius=1)
        draw_text(surface, self.title, theme.get_font(theme.FONT_SIZE_META, bold=True, kind="display"), theme.COLOR_TEXT, (title_rect.left + 6, title_rect.centery), "midleft")
        return pygame.Rect(self.rect.left + 8, self.rect.top + 28, self.rect.width - 16, self.rect.height - 36)


@dataclass(slots=True)
class StatChip:
    rect: pygame.Rect
    label: str
    value: str
    tone: tuple[int, int, int] | None = None

    def draw(self, surface: pygame.Surface) -> None:
        fill = self.tone if self.tone else theme.COLOR_PANEL_ALT
        _draw_pixel_frame(surface, self.rect, fill, theme.COLOR_BORDER)
        draw_text(surface, self.label, theme.get_font(theme.FONT_SIZE_META, bold=True), theme.COLOR_TEXT_MUTED, (self.rect.left + 6, self.rect.centery), "midleft")
        draw_text(surface, self.value, theme.get_font(theme.FONT_SIZE_META, bold=True, kind="display"), theme.COLOR_TEXT, (self.rect.right - 6, self.rect.centery), "midright")


@dataclass(slots=True)
class EmptyState:
    rect: pygame.Rect
    title: str
    body: str

    def draw(self, surface: pygame.Surface) -> None:
        _draw_pixel_frame(surface, self.rect, theme.COLOR_PANEL_ALT, theme.COLOR_BORDER)
        draw_text(surface, self.title, theme.get_font(theme.FONT_SIZE_SECTION, bold=True, kind="display"), theme.COLOR_TEXT_MUTED, (self.rect.centerx, self.rect.top + 20), "center")
        y = self.rect.top + 42
        for line in wrap_text(self.body, theme.get_font(theme.FONT_SIZE_BODY), self.rect.width - 20):
            draw_text(surface, line, theme.get_font(theme.FONT_SIZE_BODY), theme.COLOR_TEXT_MUTED, (self.rect.centerx, y), "center")
            y += theme.FONT_SIZE_BODY + 2


@dataclass(slots=True)
class InspectorBlock:
    rect: pygame.Rect
    title: str
    lines: list[str]

    def draw(self, surface: pygame.Surface) -> None:
        body_rect = SectionCard(self.rect, self.title).draw(surface)
        y = body_rect.top
        for line in self.lines:
            draw_text(surface, line, theme.get_font(theme.FONT_SIZE_BODY), theme.COLOR_TEXT, (body_rect.left, y))
            y += theme.FONT_SIZE_BODY + 2


@dataclass(slots=True)
class SegmentedToggle:
    rect: pygame.Rect
    options: list[str]
    selected: str
    on_change: Callable[[str], None] | None = None
    buttons: list[Button] = field(default_factory=list)

    def build(self) -> None:
        self.buttons.clear()
        cols = split_columns(self.rect, [1.0 for _ in self.options], gap=6)
        for col, option in zip(cols, self.options):
            self.buttons.append(Button(col, option, on_click=lambda o=option: self._trigger(o), allow_skin=False))

    def _trigger(self, option: str) -> None:
        self.selected = option
        if self.on_change:
            self.on_change(option)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.buttons:
            self.build()
        for button in self.buttons:
            if button.handle_event(event):
                return True
        return False

    def draw(self, surface: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
        if not self.buttons:
            self.build()
        for button in self.buttons:
            if button.text == self.selected:
                button.bg = theme.COLOR_ACCENT_SOFT
                button.bg_hover = theme.COLOR_ACCENT
            else:
                button.bg = theme.COLOR_PANEL_ALT
                button.bg_hover = theme.COLOR_ACCENT_SOFT
            button.draw(surface, mouse_pos)


@dataclass(slots=True)
class CommandStrip:
    rect: pygame.Rect
    buttons: list[Button]

    def draw(self, surface: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
        _draw_pixel_frame(surface, self.rect, theme.COLOR_PANEL, theme.COLOR_BORDER, draw_shadow=True, shadow_alpha=44, shadow_offset=(1, 2))
        top_line = pygame.Rect(self.rect.left + 2, self.rect.top + 2, self.rect.width - 4, 3)
        pygame.draw.rect(surface, _mix_color(theme.COLOR_BORDER_HIGHLIGHT, theme.COLOR_ACCENT_SOFT, 0.35), top_line, border_radius=1)
        for button in self.buttons:
            button.draw(surface, mouse_pos)


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
    draw_shadow: bool = False,
    shadow_alpha: int = 38,
    shadow_offset: tuple[int, int] = (1, 1),
) -> None:
    if draw_shadow:
        shadow_rect = rect.move(shadow_offset[0], shadow_offset[1])
        shadow = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, max(0, min(255, shadow_alpha))), shadow.get_rect(), border_radius=theme.BORDER_RADIUS + 1)
        surface.blit(shadow, shadow_rect.topleft)
    pygame.draw.rect(surface, border_color, rect, border_radius=theme.BORDER_RADIUS)
    inner = rect.inflate(-theme.BORDER_WIDTH * 2, -theme.BORDER_WIDTH * 2)
    if inner.width <= 0 or inner.height <= 0:
        return
    pygame.draw.rect(surface, fill_color, inner, border_radius=theme.BORDER_RADIUS)
    sheen_h = max(2, int(inner.height * 0.34))
    sheen = pygame.Surface((inner.width, sheen_h), pygame.SRCALPHA)
    sheen.fill((255, 255, 255, 12))
    surface.blit(sheen, (inner.left, inner.top))
    shade_h = max(2, int(inner.height * 0.28))
    shade = pygame.Surface((inner.width, shade_h), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 14))
    surface.blit(shade, (inner.left, inner.bottom - shade_h))
    if inner.width > 6 and inner.height > 6:
        inset = inner.inflate(-2, -2)
        pygame.draw.line(surface, theme.COLOR_BORDER_HIGHLIGHT, (inset.left, inset.top), (inset.right, inset.top), 1)
        pygame.draw.line(surface, theme.COLOR_BORDER_HIGHLIGHT, (inset.left, inset.top), (inset.left, inset.bottom), 1)
        pygame.draw.line(surface, theme.COLOR_BORDER_SHADE, (inset.left, inset.bottom), (inset.right, inset.bottom), 1)
        pygame.draw.line(surface, theme.COLOR_BORDER_SHADE, (inset.right, inset.top), (inset.right, inset.bottom), 1)


def _draw_pixel_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    top_color: tuple[int, int, int],
    bottom_color: tuple[int, int, int],
    border_color: tuple[int, int, int],
) -> None:
    _draw_pixel_frame(surface, rect, bottom_color, border_color)
    inner = rect.inflate(-theme.BORDER_WIDTH * 2, -theme.BORDER_WIDTH * 2)
    if inner.width <= 0 or inner.height <= 0:
        return
    top_rect = pygame.Rect(
        rect.left + theme.BORDER_WIDTH + 1,
        rect.top + theme.BORDER_WIDTH + 1,
        rect.width - (theme.BORDER_WIDTH * 2) - 2,
        max(0, int(rect.height * 0.44)),
    )
    if top_rect.width > 0 and top_rect.height > 0:
        pygame.draw.rect(surface, top_color, top_rect, border_radius=theme.BORDER_RADIUS)
    # Keep beveling subtle to avoid a "strikethrough" look on labels.
    if rect.height > 8:
        pygame.draw.line(surface, theme.COLOR_BORDER_HIGHLIGHT, (rect.left + 3, rect.top + 3), (rect.right - 4, rect.top + 3), 1)
        pygame.draw.line(surface, theme.COLOR_BORDER_SHADE, (rect.left + 3, rect.bottom - 3), (rect.right - 4, rect.bottom - 3), 1)


def _mix_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(a[0] * (1.0 - t) + b[0] * t),
        int(a[1] * (1.0 - t) + b[1] * t),
        int(a[2] * (1.0 - t) + b[2] * t),
    )


def _brighten_color(color: tuple[int, int, int], delta: int) -> tuple[int, int, int]:
    return (
        max(0, min(255, color[0] + delta)),
        max(0, min(255, color[1] + delta)),
        max(0, min(255, color[2] + delta)),
    )


def _channel_luminance(channel: int) -> float:
    value = float(channel) / 255.0
    if value <= 0.03928:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _relative_luminance(color: tuple[int, int, int]) -> float:
    return (
        0.2126 * _channel_luminance(color[0])
        + 0.7152 * _channel_luminance(color[1])
        + 0.0722 * _channel_luminance(color[2])
    )


def _contrast_ratio(foreground: tuple[int, int, int], background: tuple[int, int, int]) -> float:
    lum_fg = _relative_luminance(foreground)
    lum_bg = _relative_luminance(background)
    bright = max(lum_fg, lum_bg)
    dark = min(lum_fg, lum_bg)
    return (bright + 0.05) / (dark + 0.05)


def _best_contrast_text(
    background: tuple[int, int, int],
    preferred: tuple[int, int, int] | None = None,
) -> tuple[int, int, int]:
    candidates = [theme.COLOR_TEXT, theme.COLOR_BG, (250, 250, 250), (12, 12, 12)]
    if preferred is not None:
        candidates.insert(0, preferred)
    best = candidates[0]
    best_ratio = _contrast_ratio(best, background)
    for candidate in candidates[1:]:
        ratio = _contrast_ratio(candidate, background)
        if ratio > best_ratio:
            best = candidate
            best_ratio = ratio
    return best


def _fit_text_ellipsis(font: pygame.font.Font, text: str, max_width: int) -> str:
    if max_width <= 0:
        return ""
    if font.size(text)[0] <= max_width:
        return text
    ellipsis = "..."
    if font.size(ellipsis)[0] > max_width:
        return ""
    clipped = text
    while clipped and font.size(f"{clipped}{ellipsis}")[0] > max_width:
        clipped = clipped[:-1]
    return f"{clipped}{ellipsis}"

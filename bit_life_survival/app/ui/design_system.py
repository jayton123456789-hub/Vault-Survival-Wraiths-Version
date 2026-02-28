from __future__ import annotations

import pygame


GRID = 8
CARD_PADDING = 10
CARD_GAP = 8
SECTION_GAP = 12
TITLE_BAR_HEIGHT = 26
PANEL_INSET = 10


def inset(rect: pygame.Rect, px: int) -> pygame.Rect:
    return pygame.Rect(rect.left + px, rect.top + px, max(0, rect.width - px * 2), max(0, rect.height - px * 2))


def clamp_rect(
    container: pygame.Rect,
    min_w: int,
    min_h: int,
    max_w: int,
    max_h: int,
) -> pygame.Rect:
    width = max(min_w, min(max_w, container.width - 24))
    height = max(min_h, min(max_h, container.height - 24))
    rect = pygame.Rect(0, 0, width, height)
    rect.center = container.center
    return rect


def scene_shell(rect: pygame.Rect, top_ratio: float = 0.11, footer_ratio: float = 0.14, gap: int = CARD_GAP) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
    inner = inset(rect, GRID)
    top_h = max(42, int(round(inner.height * top_ratio)))
    footer_h = max(56, int(round(inner.height * footer_ratio)))
    body_h = max(0, inner.height - top_h - footer_h - (gap * 2))
    top = pygame.Rect(inner.left, inner.top, inner.width, top_h)
    body = pygame.Rect(inner.left, top.bottom + gap, inner.width, body_h)
    footer = pygame.Rect(inner.left, body.bottom + gap, inner.width, footer_h)
    return top, body, footer


def stack_rows(container: pygame.Rect, heights: list[int], gap: int = CARD_GAP) -> list[pygame.Rect]:
    rects: list[pygame.Rect] = []
    y = container.top
    for idx, height in enumerate(heights):
        rects.append(pygame.Rect(container.left, y, container.width, max(0, height)))
        y += height
        if idx < len(heights) - 1:
            y += gap
    return rects


def pad_bottom(container: pygame.Rect, height: int) -> tuple[pygame.Rect, pygame.Rect]:
    body = pygame.Rect(container.left, container.top, container.width, max(0, container.height - height))
    footer = pygame.Rect(container.left, body.bottom, container.width, max(0, height))
    return body, footer


def card_grid(container: pygame.Rect, rows: int, cols: int, gap: int = CARD_GAP) -> list[pygame.Rect]:
    if rows <= 0 or cols <= 0:
        return []
    cell_w = max(1, (container.width - gap * (cols - 1)) // cols)
    cell_h = max(1, (container.height - gap * (rows - 1)) // rows)
    grid: list[pygame.Rect] = []
    for r in range(rows):
        for c in range(cols):
            x = container.left + c * (cell_w + gap)
            y = container.top + r * (cell_h + gap)
            grid.append(pygame.Rect(x, y, cell_w, cell_h))
    return grid


def clamp_lines(lines: list[str], max_lines: int) -> list[str]:
    if len(lines) <= max_lines:
        return lines
    if max_lines <= 0:
        return []
    return lines[: max_lines - 1] + ["..."]

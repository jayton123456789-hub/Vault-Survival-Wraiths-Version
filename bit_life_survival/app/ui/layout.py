from __future__ import annotations

import pygame


def anchored_rect(
    container: pygame.Rect,
    size: tuple[int, int],
    anchor: str = "center",
    margin: tuple[int, int] = (0, 0),
) -> pygame.Rect:
    width, height = size
    rect = pygame.Rect(0, 0, width, height)
    mx, my = margin

    if anchor == "topleft":
        rect.topleft = (container.left + mx, container.top + my)
    elif anchor == "topright":
        rect.topright = (container.right - mx, container.top + my)
    elif anchor == "bottomleft":
        rect.bottomleft = (container.left + mx, container.bottom - my)
    elif anchor == "bottomright":
        rect.bottomright = (container.right - mx, container.bottom - my)
    elif anchor == "topcenter":
        rect.midtop = (container.centerx + mx, container.top + my)
    elif anchor == "bottomcenter":
        rect.midbottom = (container.centerx + mx, container.bottom - my)
    elif anchor == "midleft":
        rect.midleft = (container.left + mx, container.centery + my)
    elif anchor == "midright":
        rect.midright = (container.right - mx, container.centery + my)
    else:
        rect.center = (container.centerx + mx, container.centery + my)

    return rect


def split_columns(container: pygame.Rect, widths: list[float], gap: int = 0) -> list[pygame.Rect]:
    if not widths:
        return []
    total_weight = sum(widths)
    usable = container.width - gap * (len(widths) - 1)
    x = container.left
    rects: list[pygame.Rect] = []
    for index, weight in enumerate(widths):
        if index == len(widths) - 1:
            width = container.right - x
        else:
            width = int(usable * (weight / total_weight))
        rects.append(pygame.Rect(x, container.top, width, container.height))
        x += width + gap
    return rects


def split_rows(container: pygame.Rect, heights: list[float], gap: int = 0) -> list[pygame.Rect]:
    if not heights:
        return []
    total_weight = sum(heights)
    usable = container.height - gap * (len(heights) - 1)
    y = container.top
    rects: list[pygame.Rect] = []
    for index, weight in enumerate(heights):
        if index == len(heights) - 1:
            height = container.bottom - y
        else:
            height = int(usable * (weight / total_weight))
        rects.append(pygame.Rect(container.left, y, container.width, height))
        y += height + gap
    return rects

from __future__ import annotations

from dataclasses import dataclass, field

import pygame


@dataclass(slots=True)
class PixelRenderer:
    virtual_width: int = 640
    virtual_height: int = 360
    clear_color: tuple[int, int, int] = (22, 14, 30)
    _window_size: tuple[int, int] = field(init=False, repr=False)
    _scaled_size: tuple[int, int] = field(init=False, repr=False)
    _offset: tuple[int, int] = field(init=False, repr=False)
    _scale: float = field(init=False, repr=False)
    _cached_scaled: pygame.Surface | None = field(init=False, default=None, repr=False)
    _cached_source_size: tuple[int, int] | None = field(init=False, default=None, repr=False)
    _cached_target_size: tuple[int, int] | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        self._window_size: tuple[int, int] = (self.virtual_width * 2, self.virtual_height * 2)
        self._scaled_size: tuple[int, int] = self._window_size
        self._offset: tuple[int, int] = (0, 0)
        self._scale: int = 2
        self._cached_scaled: pygame.Surface | None = None
        self._cached_source_size: tuple[int, int] | None = None
        self._cached_target_size: tuple[int, int] | None = None

    @property
    def virtual_size(self) -> tuple[int, int]:
        return (self.virtual_width, self.virtual_height)

    def create_canvas(self) -> pygame.Surface:
        return pygame.Surface(self.virtual_size).convert()

    def set_window_size(self, size: tuple[int, int]) -> None:
        self._window_size = (max(1, int(size[0])), max(1, int(size[1])))
        scale_x = self._window_size[0] / float(self.virtual_width)
        scale_y = self._window_size[1] / float(self.virtual_height)
        self._scale = max(0.1, min(scale_x, scale_y))
        self._scaled_size = (
            max(1, int(self.virtual_width * self._scale)),
            max(1, int(self.virtual_height * self._scale)),
        )
        self._offset = (
            (self._window_size[0] - self._scaled_size[0]) // 2,
            (self._window_size[1] - self._scaled_size[1]) // 2,
        )
        self._cached_scaled = None
        self._cached_source_size = None
        self._cached_target_size = None

    def window_to_virtual(self, pos: tuple[int, int]) -> tuple[int, int]:
        if self._scale <= 0.0:
            return 0, 0
        x = (int(pos[0]) - self._offset[0]) / float(self._scale)
        y = (int(pos[1]) - self._offset[1]) / float(self._scale)
        x = max(0, min(self.virtual_width - 1, int(x)))
        y = max(0, min(self.virtual_height - 1, int(y)))
        return x, y

    def transform_event(self, event: pygame.event.Event) -> pygame.event.Event:
        if event.type in {pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP}:
            payload = event.dict.copy()
            if "pos" in payload:
                payload["pos"] = self.window_to_virtual(payload["pos"])
            if event.type == pygame.MOUSEMOTION and "rel" in payload:
                rel_x = int(round(payload["rel"][0] / max(0.1, self._scale)))
                rel_y = int(round(payload["rel"][1] / max(0.1, self._scale)))
                payload["rel"] = (rel_x, rel_y)
            return pygame.event.Event(event.type, payload)
        return event

    def present(self, window_surface: pygame.Surface, canvas_surface: pygame.Surface) -> None:
        if window_surface.get_size() != self._window_size:
            self.set_window_size(window_surface.get_size())

        source_size = canvas_surface.get_size()
        if (
            self._cached_scaled is None
            or self._cached_source_size != source_size
            or self._cached_target_size != self._scaled_size
        ):
            self._cached_scaled = pygame.transform.scale(canvas_surface, self._scaled_size)
            self._cached_source_size = source_size
            self._cached_target_size = self._scaled_size
        else:
            pygame.transform.scale(canvas_surface, self._scaled_size, self._cached_scaled)

        window_surface.fill(self.clear_color)
        window_surface.blit(self._cached_scaled, self._offset)

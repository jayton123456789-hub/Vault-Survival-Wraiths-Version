from __future__ import annotations

import math
import random

import pygame

from . import theme


class BackgroundRenderer:
    def __init__(self, seed: int = 1337) -> None:
        self.t = 0.0
        rng = random.Random(seed)
        self.ash_particles = [(rng.random(), rng.random(), rng.uniform(0.25, 1.0)) for _ in range(90)]
        self.fog_particles = [(rng.random(), rng.random(), rng.uniform(0.6, 1.4)) for _ in range(36)]
        self.steam_particles = [(rng.random(), rng.random(), rng.uniform(0.3, 1.1)) for _ in range(40)]

    def update(self, dt: float) -> None:
        self.t += dt

    def draw(self, surface: pygame.Surface, biome_id: str) -> None:
        if biome_id == "vault":
            self._draw_vault(surface)
        elif biome_id == "forest":
            self._draw_forest(surface)
        elif biome_id == "industrial":
            self._draw_industrial(surface)
        else:
            self._draw_suburbs(surface)

    @staticmethod
    def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
        return (
            int(a[0] * (1.0 - t) + b[0] * t),
            int(a[1] * (1.0 - t) + b[1] * t),
            int(a[2] * (1.0 - t) + b[2] * t),
        )

    def _shift(self, color: tuple[int, int, int], delta: int) -> tuple[int, int, int]:
        return (
            max(0, min(255, color[0] + delta)),
            max(0, min(255, color[1] + delta)),
            max(0, min(255, color[2] + delta)),
        )

    def _draw_vault(self, surface: pygame.Surface) -> None:
        top = self._mix(theme.COLOR_BG, theme.COLOR_PANEL, 0.30)
        bottom = self._mix(theme.COLOR_PANEL, theme.COLOR_PANEL_ALT, 0.62)
        self._draw_gradient(surface, top, bottom)
        w, h = surface.get_size()
        brick_w = 34
        brick_h = 14
        brick_base = self._mix(theme.COLOR_PANEL_ALT, theme.COLOR_BG, 0.20)
        for row in range((h // brick_h) + 2):
            y = row * brick_h
            offset = 0 if row % 2 == 0 else brick_w // 2
            for col in range((w // brick_w) + 3):
                x = col * brick_w - offset
                shade_shift = ((row + col) % 3) * 4
                color = self._shift(brick_base, shade_shift - 3)
                brick = pygame.Rect(x, y, brick_w - 1, brick_h - 1)
                pygame.draw.rect(surface, color, brick)
        haze = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(0, h, 3):
            haze_color = (*self._mix(theme.COLOR_BG, theme.COLOR_PANEL_ALT, 0.35), 16)
            pygame.draw.line(haze, haze_color, (0, i), (w, i), 1)
        surface.blit(haze, (0, 0))
        vignette = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(vignette, (0, 0, 0, 48), vignette.get_rect(), width=44)
        surface.blit(vignette, (0, 0))

    def _draw_gradient(self, surface: pygame.Surface, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
        w, h = surface.get_size()
        for y in range(h):
            blend = y / max(1, h - 1)
            color = (
                int(top[0] + (bottom[0] - top[0]) * blend),
                int(top[1] + (bottom[1] - top[1]) * blend),
                int(top[2] + (bottom[2] - top[2]) * blend),
            )
            pygame.draw.line(surface, color, (0, y), (w, y))

    def _draw_forest(self, surface: pygame.Surface) -> None:
        self._draw_gradient(surface, (16, 24, 20), (30, 42, 34))
        w, h = surface.get_size()
        for i in range(18):
            x = int((i / 18.0) * w)
            sway = int(math.sin(self.t * 0.4 + i * 0.7) * 6)
            tree = pygame.Rect(x + sway, h - 260 + (i % 4) * 12, 26, 240)
            pygame.draw.rect(surface, (22, 30, 24), tree)
            crown = pygame.Rect(tree.left - 30, tree.top - 44, 86, 58)
            pygame.draw.ellipse(surface, (34, 54, 38), crown)
        for px, py, speed in self.fog_particles:
            drift = (self.t * speed * 12.0) % (w + 160)
            x = int((px * w + drift) % (w + 160) - 80)
            y = int(py * h)
            fog = pygame.Surface((160, 70), pygame.SRCALPHA)
            fog.fill((180, 196, 186, 18))
            surface.blit(fog, (x, y))

    def _draw_suburbs(self, surface: pygame.Surface) -> None:
        top = self._mix(theme.COLOR_BG, theme.COLOR_PANEL, 0.42)
        bottom = self._mix(theme.COLOR_PANEL, theme.COLOR_PANEL_ALT, 0.48)
        self._draw_gradient(surface, top, bottom)
        w, h = surface.get_size()
        flicker = int(90 + 45 * (0.5 + 0.5 * math.sin(self.t * 5.5)))
        for i in range(6):
            x = int((i + 1) * w / 7)
            pole = self._mix(theme.COLOR_PANEL_ALT, theme.COLOR_BG, 0.42)
            pygame.draw.line(surface, pole, (x, h - 280), (x, h - 30), 4)
            spark = self._mix(theme.COLOR_WARNING, theme.COLOR_ACCENT, 0.25)
            spark = self._shift(spark, flicker - 120)
            pygame.draw.line(surface, spark, (x - 60, h - 220), (x + 60, h - 220), 2)
        for px, py, speed in self.ash_particles:
            x = int(px * w + math.sin(self.t * speed + px * 6.0) * 18)
            y = int((py * h + self.t * speed * 34.0) % (h + 20))
            shade = int(120 + 80 * speed)
            pygame.draw.circle(surface, (shade, shade, shade, 255), (x, y), 1)

    def _draw_industrial(self, surface: pygame.Surface) -> None:
        top = self._mix(theme.COLOR_BG, theme.COLOR_PANEL, 0.35)
        bottom = self._mix(theme.COLOR_PANEL, theme.COLOR_PANEL_ALT, 0.52)
        self._draw_gradient(surface, top, bottom)
        w, h = surface.get_size()
        for i in range(10):
            x = int((i / 10.0) * w)
            y = h - 170 - (i % 3) * 22
            building = self._mix(theme.COLOR_PANEL_ALT, theme.COLOR_BG, 0.45)
            pygame.draw.rect(surface, building, pygame.Rect(x, y, 120, 180))
        for px, py, speed in self.steam_particles:
            x = int(px * w + math.sin(self.t * speed * 2.1 + px * 8.0) * 20)
            y = int((h - py * h * 0.7 - self.t * speed * 26.0) % h)
            radius = int(6 + speed * 6)
            smoke = self._mix(theme.COLOR_TEXT_MUTED, theme.COLOR_PANEL_ALT, 0.55)
            color = (smoke[0], smoke[1], smoke[2], 42)
            puff = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(puff, color, (radius, radius), radius)
            surface.blit(puff, (x - radius, y - radius))
        for i in range(8):
            lx = int((i + 0.5) * w / 8)
            glow = int(45 + 40 * (0.5 + 0.5 * math.sin(self.t * 3.0 + i)))
            lamp = self._shift(theme.COLOR_ACCENT, glow - 65)
            pygame.draw.circle(surface, lamp, (lx, h - 190), 3)

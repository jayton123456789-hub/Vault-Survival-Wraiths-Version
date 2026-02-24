from __future__ import annotations

import math
import random

import pygame


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
        if biome_id == "forest":
            self._draw_forest(surface)
        elif biome_id == "industrial":
            self._draw_industrial(surface)
        else:
            self._draw_suburbs(surface)

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
        self._draw_gradient(surface, (24, 22, 22), (52, 46, 42))
        w, h = surface.get_size()
        flicker = int(90 + 45 * (0.5 + 0.5 * math.sin(self.t * 5.5)))
        for i in range(6):
            x = int((i + 1) * w / 7)
            pygame.draw.line(surface, (40, 38, 42), (x, h - 280), (x, h - 30), 4)
            pygame.draw.line(surface, (flicker, flicker // 2, 40), (x - 60, h - 220), (x + 60, h - 220), 2)
        for px, py, speed in self.ash_particles:
            x = int(px * w + math.sin(self.t * speed + px * 6.0) * 18)
            y = int((py * h + self.t * speed * 34.0) % (h + 20))
            shade = int(120 + 80 * speed)
            pygame.draw.circle(surface, (shade, shade, shade, 255), (x, y), 1)

    def _draw_industrial(self, surface: pygame.Surface) -> None:
        self._draw_gradient(surface, (18, 20, 26), (36, 34, 40))
        w, h = surface.get_size()
        for i in range(10):
            x = int((i / 10.0) * w)
            y = h - 170 - (i % 3) * 22
            pygame.draw.rect(surface, (30, 32, 38), pygame.Rect(x, y, 120, 180))
        for px, py, speed in self.steam_particles:
            x = int(px * w + math.sin(self.t * speed * 2.1 + px * 8.0) * 20)
            y = int((h - py * h * 0.7 - self.t * speed * 26.0) % h)
            radius = int(6 + speed * 6)
            color = (148, 156, 172, 42)
            puff = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(puff, color, (radius, radius), radius)
            surface.blit(puff, (x - radius, y - radius))
        for i in range(8):
            lx = int((i + 0.5) * w / 8)
            glow = int(55 + 45 * (0.5 + 0.5 * math.sin(self.t * 3.0 + i)))
            pygame.draw.circle(surface, (glow, glow + 20, 80), (lx, h - 190), 3)

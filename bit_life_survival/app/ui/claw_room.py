from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

import pygame

from bit_life_survival.core.models import Citizen

from . import theme
from .avatar import draw_citizen_sprite
from .widgets import draw_text


@dataclass(slots=True)
class RoomActor:
    citizen_id: str
    x_norm: float
    vx_norm: float
    lane: int
    hop_phase: float
    walk_phase: float


class ClawRoom:
    def __init__(self) -> None:
        self.actors: dict[str, RoomActor] = {}
        self.selected_id: str | None = None
        self.claw_x_norm: float = 0.5
        self.claw_depth_norm: float = 0.0
        self.claw_phase: str = "idle"
        self.claw_target_id: str | None = None
        self.claw_target_x_norm: float = 0.5
        self.claw_holding: bool = False
        self._finished_target_id: str | None = None
        self._last_hitboxes: dict[str, pygame.Rect] = {}
        self._time_s: float = 0.0

    @property
    def is_animating(self) -> bool:
        return self.claw_phase != "idle"

    def _actor_seed(self, citizen_id: str) -> bytes:
        return hashlib.sha256(citizen_id.encode("utf-8")).digest()

    def _spawn_actor(self, citizen_id: str, index: int, total: int) -> RoomActor:
        seed = self._actor_seed(citizen_id)
        spread = (index + 1) / max(2, total + 1)
        jitter = (seed[0] / 255.0 - 0.5) * 0.1
        x_norm = min(0.95, max(0.05, spread + jitter))
        speed = 0.06 + (seed[1] / 255.0) * 0.08
        direction = -1.0 if seed[2] % 2 else 1.0
        lane = seed[3] % 2
        hop_phase = (seed[4] / 255.0) * math.tau
        walk_phase = (seed[5] / 255.0) * math.tau
        return RoomActor(
            citizen_id=citizen_id,
            x_norm=x_norm,
            vx_norm=speed * direction,
            lane=lane,
            hop_phase=hop_phase,
            walk_phase=walk_phase,
        )

    def sync(self, citizens: list[Citizen]) -> None:
        ids = [citizen.id for citizen in citizens]
        keep = set(ids)
        for actor_id in list(self.actors.keys()):
            if actor_id not in keep:
                self.actors.pop(actor_id, None)
        for index, citizen in enumerate(citizens):
            if citizen.id not in self.actors:
                self.actors[citizen.id] = self._spawn_actor(citizen.id, index, len(citizens))
        if self.selected_id not in keep:
            self.selected_id = None

    def _target_x_for(self, actor_id: str) -> float:
        actor = self.actors.get(actor_id)
        if not actor:
            return 0.5
        return actor.x_norm

    def start_grab(self, target_id: str) -> bool:
        if self.is_animating:
            return False
        if target_id not in self.actors:
            return False
        self.claw_target_id = target_id
        self.claw_target_x_norm = self._target_x_for(target_id)
        self.claw_phase = "move"
        self.claw_holding = False
        return True

    def consume_finished_target(self) -> str | None:
        target = self._finished_target_id
        self._finished_target_id = None
        return target

    def update(self, dt: float) -> None:
        self._time_s += dt

        for actor in self.actors.values():
            if self.claw_holding and actor.citizen_id == self.claw_target_id:
                continue
            actor.x_norm += actor.vx_norm * dt
            if actor.x_norm < 0.05:
                actor.x_norm = 0.05
                actor.vx_norm = abs(actor.vx_norm)
            elif actor.x_norm > 0.95:
                actor.x_norm = 0.95
                actor.vx_norm = -abs(actor.vx_norm)
            actor.walk_phase += dt * 5.0

        if self.claw_phase == "idle":
            self.claw_x_norm = 0.5 + math.sin(self._time_s * 0.5) * 0.04
            self.claw_depth_norm = 0.0
            return

        if self.claw_phase == "move":
            delta = self.claw_target_x_norm - self.claw_x_norm
            step = max(-1.0, min(1.0, delta)) * dt * 1.2
            self.claw_x_norm += step
            if abs(delta) < 0.01:
                self.claw_x_norm = self.claw_target_x_norm
                self.claw_phase = "drop"
        elif self.claw_phase == "drop":
            self.claw_depth_norm = min(1.0, self.claw_depth_norm + dt * 1.8)
            if self.claw_depth_norm >= 1.0:
                self.claw_holding = True
                self.claw_phase = "lift"
        elif self.claw_phase == "lift":
            self.claw_depth_norm = max(0.0, self.claw_depth_norm - dt * 1.8)
            if self.claw_depth_norm <= 0.0:
                self.claw_depth_norm = 0.0
                self.claw_phase = "return"
        elif self.claw_phase == "return":
            delta = 0.5 - self.claw_x_norm
            step = max(-1.0, min(1.0, delta)) * dt * 1.4
            self.claw_x_norm += step
            if abs(delta) < 0.01:
                self.claw_x_norm = 0.5
                self.claw_phase = "idle"
                self.claw_holding = False
                self._finished_target_id = self.claw_target_id

    def _room_rect_from_panel(self, panel_rect: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(panel_rect.left + 8, panel_rect.top + 8, panel_rect.width - 16, panel_rect.height - 16)

    def _actor_position(self, room_rect: pygame.Rect, actor: RoomActor, selected: bool) -> tuple[int, int, float]:
        walk = actor.walk_phase
        if selected:
            walk += 0.4
        x = room_rect.left + int(actor.x_norm * room_rect.width)
        lane_ground = room_rect.bottom - 20 - actor.lane * 12
        hop = abs(math.sin(self._time_s * 3.2 + actor.hop_phase)) * (3 + actor.lane)
        y = lane_ground - int(hop)
        return x, y, walk

    def pick_actor(self, pos: tuple[int, int]) -> str | None:
        for actor_id, hitbox in reversed(list(self._last_hitboxes.items())):
            if hitbox.collidepoint(pos):
                self.selected_id = actor_id
                return actor_id
        return None

    def draw(self, surface: pygame.Surface, panel_rect: pygame.Rect, citizens: list[Citizen]) -> None:
        room_rect = self._room_rect_from_panel(panel_rect)
        self._last_hitboxes.clear()

        # Room background
        pygame.draw.rect(surface, (44, 30, 68), room_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, room_rect, width=2, border_radius=2)
        glass = room_rect.inflate(-4, -4)
        pygame.draw.rect(surface, (56, 38, 84), glass, border_radius=2)
        floor = pygame.Rect(glass.left, glass.bottom - 24, glass.width, 24)
        pygame.draw.rect(surface, (70, 52, 92), floor)
        pygame.draw.line(surface, (112, 86, 124), (glass.left, floor.top), (glass.right, floor.top), 1)

        draw_text(surface, "Claw Room", theme.get_font(14, bold=True), theme.COLOR_TEXT, (glass.left + 6, glass.top + 4))
        draw_text(surface, "Click a citizen to inspect", theme.get_font(12), theme.COLOR_TEXT_MUTED, (glass.left + 6, glass.top + 20))

        # Rail and claw body
        rail_y = glass.top + 30
        pygame.draw.line(surface, (138, 118, 92), (glass.left + 12, rail_y), (glass.right - 12, rail_y), 2)
        claw_x = glass.left + int(self.claw_x_norm * (glass.width - 1))
        claw_top = rail_y + 2
        claw_bottom = claw_top + int(self.claw_depth_norm * (glass.height - 56))
        pygame.draw.line(surface, (204, 186, 152), (claw_x, claw_top), (claw_x, claw_bottom), 1)
        head = pygame.Rect(claw_x - 7, claw_bottom - 2, 14, 8)
        pygame.draw.rect(surface, (122, 102, 84), head, border_radius=1)
        pygame.draw.rect(surface, theme.COLOR_BORDER, head, width=1, border_radius=1)
        pygame.draw.line(surface, (194, 176, 142), (head.left + 1, head.bottom), (head.left - 3, head.bottom + 6), 1)
        pygame.draw.line(surface, (194, 176, 142), (head.right - 1, head.bottom), (head.right + 3, head.bottom + 6), 1)

        citizens_by_id = {citizen.id: citizen for citizen in citizens}
        draw_order = sorted(self.actors.values(), key=lambda actor: actor.lane)
        for actor in draw_order:
            citizen = citizens_by_id.get(actor.citizen_id)
            if citizen is None:
                continue

            selected = self.selected_id == actor.citizen_id
            if self.claw_holding and actor.citizen_id == self.claw_target_id:
                draw_x = claw_x - 9
                draw_y = claw_bottom + 8
                walk_phase = self._time_s * 2.0
            else:
                x, y, walk_phase = self._actor_position(glass, actor, selected)
                draw_x = x - 9
                draw_y = y - 24

            sprite_rect = draw_citizen_sprite(
                surface,
                draw_x,
                draw_y,
                citizen_id=actor.citizen_id,
                scale=2,
                selected=selected,
                walk_phase=walk_phase,
            )
            self._last_hitboxes[actor.citizen_id] = sprite_rect.inflate(4, 4)

            if selected:
                label = citizen.name
                draw_text(surface, label, theme.get_font(12, bold=True), theme.COLOR_TEXT, (sprite_rect.centerx, sprite_rect.top - 6), "midbottom")

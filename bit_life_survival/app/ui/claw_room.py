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
    lane: int
    vx_norm: float
    walk_phase: float
    reaction: str = "wander"
    reaction_time: float = 0.0
    blocked_time: float = 0.0
    jump_phase: float = 0.0


class ClawRoom:
    def __init__(self) -> None:
        self.intake_actors: dict[str, RoomActor] = {}
        self.roster_actors: dict[str, RoomActor] = {}
        self.selected_intake_id: str | None = None
        self.selected_roster_id: str | None = None

        self._time_s: float = 0.0
        self._last_hitboxes: list[tuple[str, str, pygame.Rect]] = []

        self.claw_phase: str = "idle"
        self.claw_target_id: str | None = None
        self.claw_depth_norm: float = 0.0
        self.claw_world_x: float = 0.22
        self._claw_pick_world_x: float = 0.22
        self._claw_release_world_x: float = 0.78
        self._finished_target_id: str | None = None
        self.claw_holding: bool = False

    @property
    def is_animating(self) -> bool:
        return self.claw_phase != "idle"

    def _actor_seed(self, citizen_id: str) -> bytes:
        return hashlib.sha256(citizen_id.encode("utf-8")).digest()

    def _spawn_actor(self, citizen_id: str, index: int, total: int, room: str) -> RoomActor:
        seed = self._actor_seed(f"{room}:{citizen_id}")
        spread = (index + 1) / max(2, total + 1)
        jitter = (seed[0] / 255.0 - 0.5) * 0.18
        x_norm = min(0.93, max(0.07, spread + jitter))
        speed = 0.16 + (seed[1] / 255.0) * 0.24
        direction = -1.0 if seed[2] % 2 else 1.0
        return RoomActor(
            citizen_id=citizen_id,
            x_norm=x_norm,
            lane=int(seed[3] % 2),
            vx_norm=speed * direction,
            walk_phase=(seed[4] / 255.0) * math.tau,
            jump_phase=(seed[5] / 255.0) * math.tau,
        )

    def sync(self, intake_citizens: list[Citizen], roster_citizens: list[Citizen]) -> None:
        self._sync_room(self.intake_actors, intake_citizens, "intake")
        self._sync_room(self.roster_actors, roster_citizens, "roster")
        if self.selected_intake_id and self.selected_intake_id not in self.intake_actors:
            self.selected_intake_id = None
        if self.selected_roster_id and self.selected_roster_id not in self.roster_actors:
            self.selected_roster_id = None

    def _sync_room(self, actors: dict[str, RoomActor], citizens: list[Citizen], room: str) -> None:
        ids = [citizen.id for citizen in citizens]
        keep = set(ids)
        for actor_id in list(actors.keys()):
            if actor_id not in keep:
                actors.pop(actor_id, None)
        for idx, citizen in enumerate(citizens):
            if citizen.id not in actors:
                actors[citizen.id] = self._spawn_actor(citizen.id, idx, len(citizens), room)

    def start_grab(self, target_id: str) -> bool:
        if self.is_animating:
            return False
        actor = self.intake_actors.get(target_id)
        if actor is None:
            return False
        self.claw_target_id = target_id
        self.claw_holding = False
        self.claw_depth_norm = 0.0
        self._claw_pick_world_x = self._room_world_x("intake", actor.x_norm)
        self._claw_release_world_x = 0.80
        self.claw_phase = "move_to_pick"
        return True

    def consume_finished_target(self) -> str | None:
        target = self._finished_target_id
        self._finished_target_id = None
        return target

    def pick_actor(self, pos: tuple[int, int]) -> tuple[str, str] | None:
        for room, actor_id, hitbox in reversed(self._last_hitboxes):
            if hitbox.collidepoint(pos):
                if room == "intake":
                    self.selected_intake_id = actor_id
                else:
                    self.selected_roster_id = actor_id
                return room, actor_id
        return None

    def _room_world_x(self, room: str, x_norm: float) -> float:
        if room == "roster":
            return 0.55 + (x_norm * 0.40)
        return 0.05 + (x_norm * 0.40)

    def update(self, dt: float) -> None:
        self._time_s += dt
        self._update_room(self.intake_actors, dt, skip_id=self.claw_target_id if self.claw_holding else None)
        self._update_room(self.roster_actors, dt, skip_id=None)

        if self.claw_phase == "idle":
            self.claw_world_x = 0.22 + math.sin(self._time_s * 0.45) * 0.015
            self.claw_depth_norm = 0.0
            return

        if self.claw_phase == "move_to_pick":
            self.claw_world_x = self._move_toward(self.claw_world_x, self._claw_pick_world_x, dt * 0.9)
            if abs(self.claw_world_x - self._claw_pick_world_x) < 0.006:
                self.claw_phase = "drop_pick"
        elif self.claw_phase == "drop_pick":
            self.claw_depth_norm = min(1.0, self.claw_depth_norm + dt * 2.0)
            if self.claw_depth_norm >= 1.0:
                self.claw_holding = True
                self.claw_phase = "lift_pick"
        elif self.claw_phase == "lift_pick":
            self.claw_depth_norm = max(0.0, self.claw_depth_norm - dt * 2.2)
            if self.claw_depth_norm <= 0.0:
                self.claw_phase = "move_to_deploy"
        elif self.claw_phase == "move_to_deploy":
            self.claw_world_x = self._move_toward(self.claw_world_x, self._claw_release_world_x, dt * 1.0)
            if abs(self.claw_world_x - self._claw_release_world_x) < 0.006:
                self.claw_phase = "drop_release"
        elif self.claw_phase == "drop_release":
            self.claw_depth_norm = min(1.0, self.claw_depth_norm + dt * 2.0)
            if self.claw_depth_norm >= 1.0:
                self.claw_holding = False
                self._finished_target_id = self.claw_target_id
                self.claw_phase = "lift_release"
        elif self.claw_phase == "lift_release":
            self.claw_depth_norm = max(0.0, self.claw_depth_norm - dt * 2.4)
            if self.claw_depth_norm <= 0.0:
                self.claw_phase = "return_home"
        elif self.claw_phase == "return_home":
            self.claw_world_x = self._move_toward(self.claw_world_x, 0.22, dt * 1.2)
            if abs(self.claw_world_x - 0.22) < 0.006:
                self.claw_world_x = 0.22
                self.claw_phase = "idle"
                self.claw_target_id = None

    def _update_room(self, actors: dict[str, RoomActor], dt: float, skip_id: str | None) -> None:
        left, right = 0.06, 0.94
        min_gap_same_lane = 0.10
        min_gap_other_lane = 0.05

        for actor in actors.values():
            if actor.citizen_id == skip_id:
                continue
            if actor.reaction_time > 0.0:
                actor.reaction_time = max(0.0, actor.reaction_time - dt)
                if actor.reaction_time <= 0.0:
                    actor.reaction = "wander"

            speed_mul = 0.5 if actor.reaction == "crouch" else 1.0
            actor.x_norm += actor.vx_norm * dt * speed_mul
            if actor.x_norm < left:
                actor.x_norm = left
                actor.vx_norm = abs(actor.vx_norm)
            elif actor.x_norm > right:
                actor.x_norm = right
                actor.vx_norm = -abs(actor.vx_norm)
            actor.walk_phase += dt * (4.0 + abs(actor.vx_norm) * 9.0)
            actor.jump_phase += dt * 3.2
            actor.blocked_time = max(0.0, actor.blocked_time - (dt * 0.45))

        # Collision response and lane reaction.
        actor_list = list(actors.values())
        for i, actor in enumerate(actor_list):
            if actor.citizen_id == skip_id:
                continue
            for other in actor_list[i + 1 :]:
                if other.citizen_id == skip_id:
                    continue
                gap = other.x_norm - actor.x_norm
                needed = min_gap_same_lane if actor.lane == other.lane else min_gap_other_lane
                if abs(gap) >= needed:
                    continue
                push = (needed - abs(gap)) * 0.5
                direction = -1.0 if gap < 0 else 1.0
                actor.x_norm = max(left, min(right, actor.x_norm - push * direction))
                other.x_norm = max(left, min(right, other.x_norm + push * direction))
                actor.blocked_time += 0.12
                other.blocked_time += 0.12

                # Deterministic lane-swap/jump/crouch decision.
                if actor.lane == other.lane:
                    self._react_to_block(actor, actors, min_gap_same_lane)
                    self._react_to_block(other, actors, min_gap_same_lane)

    def _react_to_block(self, actor: RoomActor, actors: dict[str, RoomActor], min_gap: float) -> None:
        if actor.blocked_time < 0.45:
            return
        seed = self._actor_seed(actor.citizen_id)
        choice = seed[(int(self._time_s * 10) + actor.lane) % len(seed)] % 3
        next_lane = 1 - actor.lane
        if self._lane_is_clear(actor, actors, next_lane, min_gap):
            actor.lane = next_lane
            actor.reaction = "avoid"
            actor.reaction_time = 0.35
        elif choice == 0:
            actor.reaction = "jump"
            actor.reaction_time = 0.45
        elif choice == 1:
            actor.reaction = "crouch"
            actor.reaction_time = 0.65
        else:
            actor.vx_norm *= -1.0
            actor.reaction = "idle"
            actor.reaction_time = 0.30
        actor.blocked_time = 0.0

    def _lane_is_clear(self, actor: RoomActor, actors: dict[str, RoomActor], lane: int, min_gap: float) -> bool:
        for other in actors.values():
            if other.citizen_id == actor.citizen_id:
                continue
            if other.lane != lane:
                continue
            if abs(other.x_norm - actor.x_norm) < min_gap:
                return False
        return True

    @staticmethod
    def _move_toward(current: float, target: float, step: float) -> float:
        if current < target:
            return min(target, current + step)
        return max(target, current - step)

    def _draw_room_background(self, surface: pygame.Surface, rect: pygame.Rect, title: str, subtitle: str) -> pygame.Rect:
        pygame.draw.rect(surface, (44, 30, 68), rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, rect, width=2, border_radius=2)
        inner = rect.inflate(-4, -4)
        pygame.draw.rect(surface, (56, 38, 84), inner, border_radius=2)
        floor = pygame.Rect(inner.left, inner.bottom - 24, inner.width, 24)
        pygame.draw.rect(surface, (70, 52, 92), floor)
        pygame.draw.line(surface, (112, 86, 124), (inner.left, floor.top), (inner.right, floor.top), 1)
        draw_text(surface, title, theme.get_font(14, bold=True), theme.COLOR_TEXT, (inner.left + 6, inner.top + 4))
        draw_text(surface, subtitle, theme.get_font(12), theme.COLOR_TEXT_MUTED, (inner.left + 6, inner.top + 20))
        return inner

    def _draw_actors(
        self,
        surface: pygame.Surface,
        room_inner: pygame.Rect,
        actors: dict[str, RoomActor],
        selected_id: str | None,
        citizens_by_id: dict[str, Citizen],
        room_name: str,
    ) -> None:
        draw_order = sorted(actors.values(), key=lambda actor: (actor.lane, actor.x_norm))
        for actor in draw_order:
            citizen = citizens_by_id.get(actor.citizen_id)
            if citizen is None:
                continue
            lane_offset = -10 if actor.lane == 0 else 0
            reaction_offset = 0
            pose = "walk"
            if actor.reaction == "jump":
                pose = "jump"
                reaction_offset = -int(abs(math.sin(actor.jump_phase * 2.6)) * 10)
            elif actor.reaction == "crouch":
                pose = "crouch"
                reaction_offset = 5

            x = room_inner.left + int(actor.x_norm * room_inner.width) - 16
            y = room_inner.bottom - 34 + lane_offset + reaction_offset
            selected = actor.citizen_id == selected_id
            sprite_rect = draw_citizen_sprite(
                surface,
                x,
                y,
                citizen_id=actor.citizen_id,
                scale=2,
                selected=selected,
                walk_phase=actor.walk_phase,
                pose=pose,
            )
            self._last_hitboxes.append((room_name, actor.citizen_id, sprite_rect.inflate(4, 4)))
            if selected:
                draw_text(
                    surface,
                    citizen.name,
                    theme.get_font(12, bold=True),
                    theme.COLOR_TEXT,
                    (sprite_rect.centerx, sprite_rect.top - 5),
                    "midbottom",
                )

    def _draw_claw(self, surface: pygame.Surface, intake_inner: pygame.Rect, roster_inner: pygame.Rect) -> None:
        rail_y = min(intake_inner.top + 30, roster_inner.top + 30)
        rail_left = intake_inner.left + 10
        rail_right = roster_inner.right - 10
        pygame.draw.line(surface, (162, 142, 112), (rail_left, rail_y), (rail_right, rail_y), 2)

        claw_x = int(rail_left + (rail_right - rail_left) * self.claw_world_x)
        claw_top = rail_y + 2
        depth_px = int(self.claw_depth_norm * (intake_inner.height - 54))
        claw_bottom = claw_top + depth_px
        carriage = pygame.Rect(claw_x - 12, rail_y - 7, 24, 9)
        pygame.draw.rect(surface, (100, 84, 62), carriage, border_radius=1)
        pygame.draw.rect(surface, theme.COLOR_BORDER, carriage, width=1, border_radius=1)
        pygame.draw.line(surface, (216, 198, 162), (claw_x, claw_top), (claw_x, claw_bottom), 1)
        head = pygame.Rect(claw_x - 8, claw_bottom - 2, 16, 8)
        pygame.draw.rect(surface, (132, 112, 86), head, border_radius=1)
        pygame.draw.rect(surface, theme.COLOR_BORDER, head, width=1, border_radius=1)
        pygame.draw.line(surface, (198, 178, 142), (head.centerx, head.bottom), (head.centerx, head.bottom + 6), 1)
        pygame.draw.line(surface, (198, 178, 142), (head.left + 2, head.bottom), (head.left - 3, head.bottom + 6), 1)
        pygame.draw.line(surface, (198, 178, 142), (head.right - 2, head.bottom), (head.right + 3, head.bottom + 6), 1)

        if self.claw_holding and self.claw_target_id:
            held_y = claw_bottom + 10
            draw_citizen_sprite(
                surface,
                claw_x - 16,
                held_y,
                citizen_id=self.claw_target_id,
                scale=2,
                selected=True,
                walk_phase=self._time_s * 2.4,
                pose="jump",
            )

    def draw(
        self,
        surface: pygame.Surface,
        intake_rect: pygame.Rect,
        roster_rect: pygame.Rect,
        intake_citizens: list[Citizen],
        roster_citizens: list[Citizen],
    ) -> None:
        self._last_hitboxes.clear()
        intake_inner = self._draw_room_background(surface, intake_rect, "Intake Claw Room", "Citizens waiting for pickup")
        roster_inner = self._draw_room_background(surface, roster_rect, "Deploy Room", "Citizens ready to deploy")
        self._draw_claw(surface, intake_inner, roster_inner)

        intake_by_id = {citizen.id: citizen for citizen in intake_citizens}
        roster_by_id = {citizen.id: citizen for citizen in roster_citizens}
        self._draw_actors(surface, intake_inner, self.intake_actors, self.selected_intake_id, intake_by_id, "intake")
        self._draw_actors(surface, roster_inner, self.roster_actors, self.selected_roster_id, roster_by_id, "roster")

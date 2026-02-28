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
    lane_target: int
    lane_blend: float
    lane_blend_velocity: float
    vx_norm: float
    pass_bias: float
    walk_phase: float
    reaction: str = "wander"
    reaction_time: float = 0.0
    blocked_time: float = 0.0
    lane_change_cooldown: float = 0.0
    jump_phase: float = 0.0


class ClawRoom:
    def __init__(self) -> None:
        self.intake_actors: dict[str, RoomActor] = {}
        self.roster_actors: dict[str, RoomActor] = {}
        self.selected_intake_id: str | None = None
        self.selected_roster_id: str | None = None

        self._time_s: float = 0.0
        self._last_hitboxes: list[tuple[str, str, pygame.Rect]] = []
        self._finished_target_id: str | None = None

        self.claw_phase: str = "idle"
        self.claw_target_id: str | None = None
        self.claw_depth_norm: float = 0.0
        self.claw_world_x: float = 0.22
        self._claw_pick_world_x: float = 0.22
        self._claw_release_world_x: float = 0.78
        self.claw_holding: bool = False

    @property
    def is_animating(self) -> bool:
        return self.claw_phase != "idle"

    def _actor_seed(self, citizen_id: str) -> bytes:
        return hashlib.sha256(citizen_id.encode("utf-8")).digest()

    def _spawn_actor(self, citizen_id: str, index: int, total: int, room: str) -> RoomActor:
        seed = self._actor_seed(f"{room}:{citizen_id}")
        spread = (index + 1) / max(2, total + 1)
        jitter = (seed[0] / 255.0 - 0.5) * 0.15
        x_norm = min(0.93, max(0.07, spread + jitter))
        speed = 0.14 + (seed[1] / 255.0) * 0.22
        direction = -1.0 if seed[2] % 2 else 1.0
        lane = int(seed[3] % 2)
        pass_bias = 0.92 + (seed[6] / 255.0) * 0.16
        return RoomActor(
            citizen_id=citizen_id,
            x_norm=x_norm,
            lane=lane,
            lane_target=lane,
            lane_blend=float(lane),
            lane_blend_velocity=0.0,
            vx_norm=speed * direction,
            pass_bias=pass_bias,
            walk_phase=(seed[4] / 255.0) * math.tau,
            jump_phase=(seed[5] / 255.0) * math.tau,
            lane_change_cooldown=(seed[7] / 255.0) * 0.24,
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
        self._claw_release_world_x = 0.79
        self.claw_phase = "move_to_pick"
        return True

    def consume_finished_target(self) -> str | None:
        target = self._finished_target_id
        self._finished_target_id = None
        return target

    def pick_actor(self, pos: tuple[int, int]) -> tuple[str, str] | None:
        candidates: list[tuple[float, int, str, str]] = []
        px, py = pos
        for draw_index, (room, actor_id, hitbox) in enumerate(self._last_hitboxes):
            if not hitbox.collidepoint(pos):
                continue
            dx = hitbox.centerx - px
            dy = hitbox.centery - py
            dist = float(dx * dx + dy * dy)
            # Favor nearest hitbox first, then most recently drawn sprite for stable overlap handling.
            candidates.append((dist, -draw_index, room, actor_id))
        if candidates:
            _, _, room, actor_id = min(candidates, key=lambda item: (item[0], item[1]))
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
        skip_id = self.claw_target_id if self.claw_phase != "idle" else None
        self._update_room(self.intake_actors, dt, skip_id=skip_id)
        self._update_room(self.roster_actors, dt, skip_id=None)

        if self.claw_phase == "idle":
            self.claw_world_x = 0.22 + math.sin(self._time_s * 0.45) * 0.012
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
            self.claw_depth_norm = max(0.0, self.claw_depth_norm - dt * 2.4)
            if self.claw_depth_norm <= 0.0:
                self.claw_phase = "move_to_deploy"
        elif self.claw_phase == "move_to_deploy":
            self.claw_world_x = self._move_toward(self.claw_world_x, self._claw_release_world_x, dt * 1.1)
            if abs(self.claw_world_x - self._claw_release_world_x) < 0.006:
                self.claw_phase = "drop_release"
        elif self.claw_phase == "drop_release":
            self.claw_depth_norm = min(1.0, self.claw_depth_norm + dt * 2.0)
            if self.claw_depth_norm >= 1.0:
                self.claw_holding = False
                self._finished_target_id = self.claw_target_id
                self.claw_phase = "lift_release"
        elif self.claw_phase == "lift_release":
            self.claw_depth_norm = max(0.0, self.claw_depth_norm - dt * 2.6)
            if self.claw_depth_norm <= 0.0:
                self.claw_phase = "return_home"
        elif self.claw_phase == "return_home":
            self.claw_world_x = self._move_toward(self.claw_world_x, 0.22, dt * 1.2)
            if abs(self.claw_world_x - 0.22) < 0.006:
                self.claw_world_x = 0.22
                self.claw_phase = "idle"
                self.claw_target_id = None

    def _update_room(self, actors: dict[str, RoomActor], dt: float, skip_id: str | None) -> None:
        left, right = 0.07, 0.93
        lane_gap = 0.12
        actor_list = list(actors.values())
        for actor in actor_list:
            if actor.citizen_id == skip_id:
                continue
            actor.lane_change_cooldown = max(0.0, actor.lane_change_cooldown - dt)
            if actor.reaction_time > 0.0:
                actor.reaction_time = max(0.0, actor.reaction_time - dt)
                if actor.reaction_time <= 0.0:
                    actor.reaction = "wander"
            speed_mul = 1.0
            if actor.reaction == "crouch":
                speed_mul = 0.45
            elif actor.reaction == "jump":
                speed_mul = 0.85
            elif actor.reaction == "lane_swap":
                speed_mul = 1.06
            actor.x_norm += actor.vx_norm * dt * speed_mul * actor.pass_bias
            if actor.x_norm < left:
                actor.x_norm = left
                actor.vx_norm = abs(actor.vx_norm)
            elif actor.x_norm > right:
                actor.x_norm = right
                actor.vx_norm = -abs(actor.vx_norm)
            actor.walk_phase += dt * (3.2 + abs(actor.vx_norm) * 8.0)
            actor.jump_phase += dt * 3.2
            actor.blocked_time = max(0.0, actor.blocked_time - dt * 0.25)

        # Same-lane spacing solver (forward/backward pass) so actors can queue, not stack.
        for lane in (0, 1):
            lane_actors = sorted((a for a in actor_list if a.lane == lane and a.citizen_id != skip_id), key=lambda a: a.x_norm)
            for i in range(1, len(lane_actors)):
                prev = lane_actors[i - 1]
                curr = lane_actors[i]
                min_x = prev.x_norm + lane_gap
                if curr.x_norm < min_x:
                    overlap = min_x - curr.x_norm
                    curr_push = min(overlap * 0.5, 0.014)
                    prev_push = min(overlap * 0.3, 0.010)
                    curr.x_norm += curr_push
                    prev.x_norm -= prev_push
                    curr.blocked_time += overlap * 4.0
                    prev.blocked_time += overlap * 2.8
            for i in range(len(lane_actors) - 2, -1, -1):
                curr = lane_actors[i]
                nxt = lane_actors[i + 1]
                max_x = nxt.x_norm - lane_gap
                if curr.x_norm > max_x:
                    curr.x_norm -= min(curr.x_norm - max_x, 0.014)
            for actor in lane_actors:
                actor.x_norm = max(left, min(right, actor.x_norm))

        # Blocked-time accumulation is lane-aware; actors in separate lanes can pass through.
        for i, actor in enumerate(actor_list):
            if actor.citizen_id == skip_id:
                continue
            for other in actor_list[i + 1 :]:
                if other.citizen_id == skip_id:
                    continue
                if actor.lane != other.lane:
                    continue
                if abs(actor.x_norm - other.x_norm) >= lane_gap:
                    continue
                actor.blocked_time += 0.16
                other.blocked_time += 0.16

        for actor in actor_list:
            if actor.citizen_id == skip_id:
                continue
            if actor.blocked_time < 0.46:
                continue
            self._react_to_block(actor, actors, lane_gap)
            actor.blocked_time = 0.0

        # Smooth visual lane transition with damped velocity to avoid micro-jitter.
        stiffness = 42.0
        damping = 11.0
        for actor in actor_list:
            target = float(actor.lane_target)
            delta = target - actor.lane_blend
            actor.lane_blend_velocity += delta * stiffness * dt
            actor.lane_blend_velocity *= max(0.0, 1.0 - damping * dt)
            actor.lane_blend += actor.lane_blend_velocity * dt
            actor.lane_blend = max(0.0, min(1.0, actor.lane_blend))
            if abs(actor.lane_blend - target) < 0.008 and abs(actor.lane_blend_velocity) < 0.01:
                actor.lane_blend = target
                actor.lane_blend_velocity = 0.0

    def _react_to_block(self, actor: RoomActor, actors: dict[str, RoomActor], lane_gap: float) -> None:
        if abs(actor.lane_blend - float(actor.lane_target)) > 0.06:
            return
        seed = self._actor_seed(actor.citizen_id)
        tick = int(self._time_s * 10)
        roll = seed[(tick + actor.lane) % len(seed)] % 4
        other_lane = 1 - actor.lane
        if actor.lane_change_cooldown <= 0.0 and self._lane_is_clear(actor, actors, other_lane, lane_gap) and self._lane_projected_clear(actor, actors, other_lane, lane_gap):
            actor.lane_target = other_lane
            actor.lane = other_lane
            actor.reaction = "lane_swap"
            actor.reaction_time = 0.32
            actor.lane_change_cooldown = 0.95
            actor.blocked_time = 0.0
            return
        if roll in {0, 1}:
            actor.reaction = "jump"
            actor.reaction_time = 0.34
            return
        if roll == 2:
            actor.reaction = "crouch"
            actor.reaction_time = 0.48
            return
        actor.vx_norm *= -1.0
        actor.reaction = "avoid"
        actor.reaction_time = 0.26

    def _lane_is_clear(self, actor: RoomActor, actors: dict[str, RoomActor], lane: int, lane_gap: float) -> bool:
        for other in actors.values():
            if other.citizen_id == actor.citizen_id:
                continue
            if other.lane != lane:
                continue
            if abs(other.x_norm - actor.x_norm) < lane_gap:
                return False
        return True

    def _lane_projected_clear(self, actor: RoomActor, actors: dict[str, RoomActor], lane: int, lane_gap: float) -> bool:
        horizon = 0.34
        actor_future_x = actor.x_norm + actor.vx_norm * horizon * actor.pass_bias
        for other in actors.values():
            if other.citizen_id == actor.citizen_id:
                continue
            if other.lane != lane:
                continue
            other_future_x = other.x_norm + other.vx_norm * horizon * other.pass_bias
            if abs(other_future_x - actor_future_x) < lane_gap * 0.92:
                return False
        return True

    @staticmethod
    def _move_toward(current: float, target: float, step: float) -> float:
        if current < target:
            return min(target, current + step)
        return max(target, current - step)

    def _draw_room_background(self, surface: pygame.Surface, rect: pygame.Rect, title: str, subtitle: str) -> pygame.Rect:
        pygame.draw.rect(surface, theme.COLOR_PANEL, rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, rect, width=2, border_radius=2)
        inner = rect.inflate(-4, -4)
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, inner, border_radius=2)
        floor = pygame.Rect(inner.left, inner.bottom - 26, inner.width, 26)
        pygame.draw.rect(surface, _mix(theme.COLOR_PANEL_ALT, theme.COLOR_BORDER, 0.24), floor)
        pygame.draw.line(surface, _mix(theme.COLOR_BORDER_HIGHLIGHT, theme.COLOR_PANEL_ALT, 0.42), (inner.left, floor.top), (inner.right, floor.top), 2)
        draw_text(surface, title, theme.get_font(16, bold=True, kind="display"), theme.COLOR_TEXT, (inner.left + 8, inner.top + 4))
        draw_text(surface, subtitle, theme.get_font(13), theme.COLOR_TEXT_MUTED, (inner.left + 8, inner.top + 22))
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
        hide_target = self.claw_target_id if (room_name == "intake" and self.claw_phase in {"drop_pick", "lift_pick", "move_to_deploy", "drop_release", "lift_release", "return_home"}) else None
        draw_order = sorted(actors.values(), key=lambda actor: (actor.lane, actor.x_norm))
        for actor in draw_order:
            if hide_target and actor.citizen_id == hide_target:
                continue
            citizen = citizens_by_id.get(actor.citizen_id)
            if citizen is None:
                continue
            lane_offset = int(round(-14 + (actor.lane_blend * 12.0)))
            pose = "walk"
            reaction_offset = 0
            if actor.reaction == "jump":
                pose = "jump"
                reaction_offset = -int(abs(math.sin(actor.jump_phase * 2.7)) * 10)
            elif actor.reaction == "crouch":
                pose = "crouch"
                reaction_offset = 4

            x = room_inner.left + int(actor.x_norm * room_inner.width) - 16
            y = room_inner.bottom - 35 + lane_offset + reaction_offset
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
                    theme.get_font(12, bold=True, kind="display"),
                    theme.COLOR_TEXT,
                    (sprite_rect.centerx, sprite_rect.top - 4),
                    "midbottom",
                )

    def _draw_claw(self, surface: pygame.Surface, intake_inner: pygame.Rect, roster_inner: pygame.Rect) -> None:
        rail_y = min(intake_inner.top + 34, roster_inner.top + 34)
        rail_left = intake_inner.left + 10
        rail_right = roster_inner.right - 10
        pygame.draw.line(surface, _mix(theme.COLOR_BORDER_HIGHLIGHT, theme.COLOR_TEXT, 0.45), (rail_left, rail_y), (rail_right, rail_y), 2)
        pygame.draw.line(surface, theme.COLOR_BORDER_SHADE, (rail_left, rail_y + 2), (rail_right, rail_y + 2), 1)

        claw_x = int(rail_left + (rail_right - rail_left) * self.claw_world_x)
        claw_top = rail_y + 2
        depth_px = int(self.claw_depth_norm * (intake_inner.height - 54))
        claw_bottom = claw_top + depth_px

        carriage = pygame.Rect(claw_x - 13, rail_y - 9, 26, 10)
        pygame.draw.rect(surface, (108, 90, 68), carriage, border_radius=1)
        pygame.draw.rect(surface, theme.COLOR_BORDER, carriage, width=1, border_radius=1)
        pygame.draw.line(surface, (222, 202, 164), (claw_x, claw_top), (claw_x, claw_bottom), 1)

        head = pygame.Rect(claw_x - 9, claw_bottom - 2, 18, 9)
        pygame.draw.rect(surface, (132, 110, 82), head, border_radius=1)
        pygame.draw.rect(surface, theme.COLOR_BORDER, head, width=1, border_radius=1)
        pygame.draw.line(surface, (210, 188, 146), (head.left + 3, head.bottom), (head.left - 3, head.bottom + 7), 1)
        pygame.draw.line(surface, (210, 188, 146), (head.centerx, head.bottom), (head.centerx, head.bottom + 7), 1)
        pygame.draw.line(surface, (210, 188, 146), (head.right - 3, head.bottom), (head.right + 3, head.bottom + 7), 1)

        if self.claw_holding and self.claw_target_id:
            held_y = claw_bottom + 10
            draw_citizen_sprite(
                surface,
                claw_x - 16,
                held_y,
                citizen_id=self.claw_target_id,
                scale=2,
                selected=True,
                walk_phase=self._time_s * 2.2,
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


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(a[0] * (1 - t) + b[0] * t),
        int(a[1] * (1 - t) + b[1] * t),
        int(a[2] * (1 - t) + b[2] * t),
    )

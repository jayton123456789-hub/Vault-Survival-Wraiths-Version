from __future__ import annotations

import pygame

from bit_life_survival.app.ui.claw_room import ClawRoom
from bit_life_survival.core.models import Citizen, EquippedSlots


def _citizens(count: int) -> list[Citizen]:
    return [
        Citizen(
            id=f"cit_{idx}",
            name=f"Citizen {idx}",
            quirk="Test quirk",
            kit={},
            loadout=EquippedSlots(),
            kit_seed=idx,
        )
        for idx in range(count)
    ]


def _simulate_snapshot(steps: int = 160) -> list[tuple[str, float, int, str]]:
    room = ClawRoom()
    citizens = _citizens(8)
    room.sync(citizens, [])
    for _ in range(steps):
        room.update(1 / 30.0)
    return sorted(
        [
            (actor.citizen_id, round(actor.x_norm, 4), actor.lane, actor.reaction)
            for actor in room.intake_actors.values()
        ],
        key=lambda item: item[0],
    )


def test_claw_room_motion_is_deterministic() -> None:
    first = _simulate_snapshot()
    second = _simulate_snapshot()
    assert first == second


def test_claw_room_prevents_same_lane_pileup() -> None:
    room = ClawRoom()
    citizens = _citizens(10)
    room.sync(citizens, [])
    for _ in range(220):
        room.update(1 / 30.0)

    lane_groups: dict[int, list[float]] = {0: [], 1: []}
    for actor in room.intake_actors.values():
        lane_groups[actor.lane].append(actor.x_norm)

    for lane_values in lane_groups.values():
        lane_values.sort()
        for left, right in zip(lane_values, lane_values[1:]):
            assert (right - left) >= 0.05


def test_claw_room_allows_cross_lane_pass_through() -> None:
    room = ClawRoom()
    citizens = _citizens(2)
    room.sync(citizens, [])
    first = room.intake_actors[citizens[0].id]
    second = room.intake_actors[citizens[1].id]
    first.lane = 0
    second.lane = 1
    first.x_norm = 0.40
    second.x_norm = 0.60
    first.vx_norm = 0.28
    second.vx_norm = -0.28

    initial_order = first.x_norm < second.x_norm
    crossed = False
    for _ in range(100):
        room.update(1 / 30.0)
        if (first.x_norm < second.x_norm) != initial_order:
            crossed = True
            break
    assert crossed is True


def test_lane_transition_is_smoothed_over_multiple_frames() -> None:
    room = ClawRoom()
    citizens = _citizens(1)
    room.sync(citizens, [])
    actor = room.intake_actors[citizens[0].id]
    actor.lane = 0
    actor.lane_target = 1
    actor.lane_blend = 0.0
    actor.lane_blend_velocity = 0.0

    room.update(1 / 30.0)
    assert 0.0 < actor.lane_blend < 1.0
    assert actor.lane_blend_velocity > 0.0

    for _ in range(60):
        room.update(1 / 30.0)
    assert actor.lane_blend > 0.98
    assert abs(actor.lane_blend_velocity) < 0.08


def test_lane_swap_cooldown_blocks_immediate_ping_pong() -> None:
    room = ClawRoom()
    citizens = _citizens(2)
    room.sync(citizens, [])
    actor = room.intake_actors[citizens[0].id]
    other = room.intake_actors[citizens[1].id]
    actor.lane = 0
    actor.lane_target = 0
    actor.lane_blend = 0.0
    actor.lane_change_cooldown = 0.0
    actor.blocked_time = 1.0
    other.lane = 0
    other.lane_target = 0
    other.lane_blend = 0.0
    other.x_norm = actor.x_norm + 0.01

    room._react_to_block(actor, room.intake_actors, lane_gap=0.12)
    first_lane = actor.lane
    assert first_lane in {0, 1}
    actor.lane_blend = float(actor.lane_target)
    assert actor.lane_change_cooldown > 0.0

    room._react_to_block(actor, room.intake_actors, lane_gap=0.12)
    assert actor.lane == first_lane


def test_pick_actor_prefers_nearest_hitbox() -> None:
    room = ClawRoom()
    room._last_hitboxes = [
        ("intake", "a", pygame.Rect(100, 100, 30, 30)),
        ("intake", "b", pygame.Rect(105, 105, 30, 30)),
    ]
    picked = room.pick_actor((126, 126))
    assert picked == ("intake", "b")

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MeterName = Literal["stamina", "hydration", "morale"]
RunnerStatus = Literal["ready", "deployed", "dead"]
ItemSlot = Literal["pack", "armor", "vehicle", "utility", "faction", "consumable"]
ItemRarity = Literal["common", "uncommon", "rare", "legendary"]
MaterialName = Literal["scrap", "cloth", "plastic", "metal"]
BodyPart = Literal["head", "torso", "left_arm", "right_arm", "left_leg", "right_leg"]
RunLogCategory = Literal["TRAVEL", "EVENT", "CHOICE", "OUTCOME", "LOOT", "INJURY", "HEAL", "SYSTEM"]

SAVE_VERSION = 4

RUNNER_EQUIP_SLOTS = ("pack", "armor", "vehicle", "utility1", "utility2", "faction")
METER_NAMES: tuple[MeterName, MeterName, MeterName] = ("stamina", "hydration", "morale")
MATERIAL_ITEM_IDS: tuple[MaterialName, MaterialName, MaterialName, MaterialName] = ("scrap", "cloth", "plastic", "metal")
BODY_PARTS: tuple[BodyPart, BodyPart, BodyPart, BodyPart, BodyPart, BodyPart] = (
    "head",
    "torso",
    "left_arm",
    "right_arm",
    "left_leg",
    "right_leg",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ItemModifiers(StrictModel):
    speed: float | None = None
    carry: float | None = None
    injuryResist: float | None = None
    staminaDrainMul: float | None = None
    hydrationDrainMul: float | None = None
    moraleMul: float | None = None
    noise: float | None = None


class ItemDurability(StrictModel):
    max: int = Field(ge=1)
    current: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_current(self) -> "ItemDurability":
        if self.current is not None and self.current > self.max:
            raise ValueError("Item durability current cannot exceed max.")
        return self


class Item(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    slot: ItemSlot
    tags: list[str] = Field(default_factory=list)
    rarity: ItemRarity
    modifiers: ItemModifiers = Field(default_factory=ItemModifiers)
    durability: ItemDurability | None = None
    value: float | None = Field(default=None, ge=0)


class LootTableEntry(StrictModel):
    item_id: str = Field(alias="itemId", min_length=1)
    weight: float = Field(gt=0)
    min_qty: int | None = Field(default=None, alias="min", ge=1)
    max_qty: int | None = Field(default=None, alias="max", ge=1)

    @model_validator(mode="after")
    def validate_min_max(self) -> "LootTableEntry":
        min_qty = self.min_qty or 1
        max_qty = self.max_qty or min_qty
        if max_qty < min_qty:
            raise ValueError("LootTableEntry.max must be greater than or equal to min.")
        return self


class GuaranteedLoot(StrictModel):
    item_id: str = Field(alias="itemId", min_length=1)
    qty: int = Field(ge=1)


class LootTable(StrictModel):
    id: str = Field(min_length=1)
    entries: list[LootTableEntry] = Field(min_length=1)
    rolls: int = Field(default=1, ge=1)
    guaranteed: list[GuaranteedLoot] = Field(default_factory=list)


class Recipe(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    category: str | None = None
    unlock_tav: int | None = Field(default=None, alias="unlockTav", ge=0)
    purpose: str | None = None
    tutorial_use: str | None = Field(default=None, alias="tutorialUse")
    inputs: dict[str, int] = Field(default_factory=dict)
    output_item: str = Field(alias="outputItem", min_length=1)
    output_qty: int = Field(default=1, alias="outputQty", ge=1)


class MeterDrainMultipliers(StrictModel):
    stamina: float = Field(gt=0)
    hydration: float = Field(gt=0)
    morale: float = Field(gt=0)


class Biome(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    meter_drain_mul: MeterDrainMultipliers = Field(alias="meterDrainMul")
    event_weight_mul_by_tag: dict[str, float] = Field(default_factory=dict, alias="eventWeightMulByTag")
    loot_table_ids: list[str] = Field(default_factory=list, alias="lootTableIds")


class EventTrigger(StrictModel):
    biome_ids: list[str] | None = Field(default=None, alias="biomeIds")
    min_distance: float | None = Field(default=None, alias="minDistance")
    max_distance: float | None = Field(default=None, alias="maxDistance")
    required_flags_all: list[str] | None = Field(default=None, alias="requiredFlagsAll")
    forbidden_flags_any: list[str] | None = Field(default=None, alias="forbiddenFlagsAny")
    cooldown_steps: int | None = Field(default=None, alias="cooldownSteps", ge=0)


class EventOption(StrictModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    requirements: dict[str, Any] | None = None
    costs: list[dict[str, Any]] = Field(default_factory=list)
    outcomes: list[dict[str, Any]] = Field(min_length=1)
    log_line: str = Field(alias="logLine", min_length=1)


class Event(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    trigger: EventTrigger = Field(default_factory=EventTrigger)
    weight: float = Field(gt=0)
    options: list[EventOption] = Field(min_length=1)


class MeterValues(StrictModel):
    stamina: float = Field(default=100.0, ge=0, le=100)
    hydration: float = Field(default=100.0, ge=0, le=100)
    morale: float = Field(default=100.0, ge=0, le=100)


class EquippedSlots(StrictModel):
    pack: str | None = None
    armor: str | None = None
    vehicle: str | None = None
    utility1: str | None = None
    utility2: str | None = None
    faction: str | None = None

    def as_values(self) -> list[str]:
        values = self.model_dump(mode="python")
        return [item_id for item_id in values.values() if item_id]


class RunLogEntry(StrictModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    step: int = Field(default=0, ge=0)
    category: RunLogCategory
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class GameState(StrictModel):
    seed: int | str
    step: int = Field(default=0, ge=0)
    distance: float = Field(default=0.0, ge=0)
    time: int = Field(default=0, ge=0)
    biome_id: str = Field(min_length=1)
    mission_name: str = "Bootstrap Salvage Sweep"
    meters: MeterValues = Field(default_factory=MeterValues)
    hunger: float = Field(default=100.0, ge=0, le=100)
    hunger_drain_mul: float = Field(default=1.0, gt=0)
    hydration_drain_mul: float = Field(default=1.0, gt=0)
    travel_speed_bonus: float = 0.0
    medical_efficiency: float = Field(default=0.0, ge=0, le=1.0)
    injury: float = Field(default=0.0, ge=0, le=100)
    injuries: dict[str, float] = Field(default_factory=lambda: {part: 0.0 for part in BODY_PARTS})
    flags: set[str] = Field(default_factory=set)
    death_flags: set[str] = Field(default_factory=set)
    inventory: dict[str, int] = Field(default_factory=dict)
    equipped: EquippedSlots = Field(default_factory=EquippedSlots)
    dead: bool = False
    death_reason: str | None = None
    last_event_id: str | None = None
    recent_event_ids: list[str] = Field(default_factory=list)
    event_cooldowns: dict[str, int] = Field(default_factory=dict)
    rng_state: int = Field(gt=0)
    rng_calls: int = Field(default=0, ge=0)
    run_log: list[RunLogEntry] = Field(default_factory=list)
    run_log_max: int = Field(default=300, ge=50, le=1000)

    @field_validator("inventory")
    @classmethod
    def validate_inventory(cls, inventory: dict[str, int]) -> dict[str, int]:
        for item_id, qty in inventory.items():
            if qty < 0:
                raise ValueError(f"Inventory quantity for '{item_id}' cannot be negative.")
        return inventory

    @field_validator("event_cooldowns")
    @classmethod
    def validate_cooldowns(cls, cooldowns: dict[str, int]) -> dict[str, int]:
        for event_id, remaining in cooldowns.items():
            if remaining < 0:
                raise ValueError(f"Cooldown for '{event_id}' cannot be negative.")
        return cooldowns

    @field_validator("injuries")
    @classmethod
    def validate_injuries(cls, injuries: dict[str, float]) -> dict[str, float]:
        hydrated = {part: 0.0 for part in BODY_PARTS}
        for part, value in injuries.items():
            if value < 0:
                raise ValueError(f"Injury value for '{part}' cannot be negative.")
            hydrated[part] = float(value)
        return hydrated

    @model_validator(mode="after")
    def sync_injury_fields(self) -> "GameState":
        total = sum(max(0.0, float(v)) for v in self.injuries.values())
        if total <= 0 and self.injury > 0:
            self.injuries["torso"] = float(self.injury)
            total = float(self.injury)
        self.injury = max(0.0, min(100.0, total))
        return self

    def append_run_log(
        self,
        category: RunLogCategory,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.run_log.append(
            RunLogEntry(
                step=self.step,
                category=category,
                message=message,
                details=details or {},
            )
        )
        overflow = len(self.run_log) - int(self.run_log_max)
        if overflow > 0:
            del self.run_log[:overflow]


class Citizen(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    quirk: str = Field(min_length=1)
    kit: dict[str, int] = Field(default_factory=dict)
    loadout: EquippedSlots = Field(default_factory=EquippedSlots)
    kit_seed: int | None = None
    status: RunnerStatus = "ready"
    completed_runs: int = Field(default=0, ge=0)
    death_count: int = Field(default=0, ge=0)


def default_materials() -> dict[str, int]:
    return {material: 0 for material in MATERIAL_ITEM_IDS}


class SettingsState(StrictModel):
    skip_intro: bool = False
    intro_use_cinematic_audio: bool = True
    seeded_mode: bool = True
    base_seed: int = 1337
    seen_run_help: bool = False
    theme_preset: str = "ember"
    font_scale: float = Field(default=1.0, ge=0.75, le=1.6)
    show_tooltips: bool = True


class VaultState(StrictModel):
    materials: dict[str, int] = Field(default_factory=default_materials)
    storage: dict[str, int] = Field(default_factory=dict)
    blueprints: set[str] = Field(default_factory=set)
    upgrades: dict[str, int] = Field(default_factory=dict)
    tav: int = 0
    vault_level: int = Field(default=1, alias="vaultLevel")
    citizen_queue: list[Citizen] = Field(default_factory=list)
    deploy_roster: list[Citizen] = Field(default_factory=list)
    citizen_reserve: list[Citizen] = Field(default_factory=list)
    current_citizen: Citizen | None = None
    active_deploy_citizen_id: str | None = None
    fallen_citizens: list[Citizen] = Field(default_factory=list)
    citizen_queue_capacity: int = Field(default=4, ge=1, le=24)
    deploy_roster_capacity: int = Field(default=1, ge=1, le=24)
    milestones: set[str] = Field(default_factory=set)
    research_levels: dict[str, int] = Field(default_factory=dict)
    campaign_goal_unlocked: bool = False
    campaign_won: bool = False
    run_counter: int = 0
    last_run_seed: int | str | None = None
    last_run_distance: float = 0.0
    last_run_time: int = 0
    claw_rng_state: int = 1
    claw_rng_calls: int = 0
    settings: SettingsState = Field(default_factory=SettingsState)

    @field_validator("storage")
    @classmethod
    def validate_storage(cls, storage: dict[str, int]) -> dict[str, int]:
        for item_id, qty in storage.items():
            if qty < 0:
                raise ValueError(f"Vault storage quantity for '{item_id}' cannot be negative.")
        return storage

    @field_validator("materials")
    @classmethod
    def validate_materials(cls, materials: dict[str, int]) -> dict[str, int]:
        hydrated = default_materials()
        for item_id, qty in materials.items():
            if qty < 0:
                raise ValueError(f"Vault material quantity for '{item_id}' cannot be negative.")
            hydrated[item_id] = int(qty)
        return hydrated


class SaveData(StrictModel):
    save_version: int = Field(default=SAVE_VERSION, ge=1)
    vault: VaultState


def clamp_meter(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def clamp_injury(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def sync_total_injury(state: GameState) -> float:
    state.injury = clamp_injury(sum(max(0.0, float(v)) for v in state.injuries.values()))
    return state.injury


def has_owned_item(state: GameState, item_id: str) -> bool:
    if state.inventory.get(item_id, 0) > 0:
        return True
    return item_id in state.equipped.as_values()


def owned_item_ids(state: GameState) -> set[str]:
    owned: set[str] = {item_id for item_id, qty in state.inventory.items() if qty > 0}
    owned.update(state.equipped.as_values())
    return owned


@dataclass(slots=True)
class LogEntry:
    step: int
    time: int
    distance: float
    type: str
    line: str
    data: dict[str, Any] | None = None

    def format(self) -> str:
        return f"[s={self.step:03d} t={self.time:03d} d={self.distance:8.2f}] [{self.type.upper()}] {self.line}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "time": self.time,
            "distance": round(self.distance, 6),
            "type": self.type,
            "line": self.line,
            "data": self.data or {},
        }


def make_log_entry(state: GameState, entry_type: str, line: str, data: dict[str, Any] | None = None) -> LogEntry:
    return LogEntry(
        step=state.step,
        time=state.time,
        distance=state.distance,
        type=entry_type,
        line=line,
        data=data,
    )

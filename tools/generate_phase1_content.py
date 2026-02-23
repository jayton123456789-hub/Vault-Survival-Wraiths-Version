from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "bit_life_survival" / "content"


def item(
    item_id: str,
    name: str,
    slot: str,
    tags: list[str],
    rarity: str,
    modifiers: dict[str, float] | None = None,
    value: int | None = None,
    durability_max: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": item_id,
        "name": name,
        "slot": slot,
        "tags": tags,
        "rarity": rarity,
        "modifiers": modifiers or {},
    }
    if value is not None:
        payload["value"] = value
    if durability_max is not None:
        payload["durability"] = {"max": durability_max}
    return payload


def option(
    option_id: str,
    label: str,
    log_line: str,
    outcomes: list[dict[str, Any]],
    requirements: dict[str, Any] | None = None,
    costs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": option_id,
        "label": label,
        "outcomes": outcomes,
        "logLine": log_line,
    }
    if requirements is not None:
        payload["requirements"] = requirements
    if costs:
        payload["costs"] = costs
    return payload


def event(
    event_id: str,
    title: str,
    text: str,
    tags: list[str],
    weight: float,
    options: list[dict[str, Any]],
    trigger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": event_id,
        "title": title,
        "text": text,
        "tags": tags,
        "trigger": trigger or {"biomeIds": ["suburbs"]},
        "weight": weight,
        "options": options,
    }


def build_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = [
        # Packs
        item("backpack_basic", "Basic Backpack", "pack", ["Storage"], "common", {"carry": 12}, 18, 95),
        item("sling_pack", "Sling Pack", "pack", ["Storage", "Stealth"], "common", {"carry": 8, "speed": 0.04}, 22, 80),
        item("courier_pack", "Courier Pack", "pack", ["Storage", "Trade"], "uncommon", {"carry": 14, "speed": 0.05}, 35, 100),
        item("field_pack", "Field Pack", "pack", ["Storage", "Medical"], "uncommon", {"carry": 18, "staminaDrainMul": 0.96}, 48, 115),
        item("expedition_pack", "Expedition Pack", "pack", ["Storage", "Hazard"], "rare", {"carry": 24, "hydrationDrainMul": 0.95}, 78, 130),
        item("tactical_pack", "Tactical Pack", "pack", ["Storage", "Combat"], "rare", {"carry": 20, "injuryResist": 0.05}, 86, 125),
        item("sealed_pack", "Sealed Pack", "pack", ["Storage", "Toxic"], "rare", {"carry": 16, "hydrationDrainMul": 0.9}, 92, 120),
        item("hazard_pack", "Hazard Pack", "pack", ["Storage", "Toxic"], "rare", {"carry": 15, "staminaDrainMul": 0.95, "hydrationDrainMul": 0.94}, 88, 120),
        item("smuggler_pack", "Smuggler Pack", "pack", ["Storage", "Trade", "Stealth"], "uncommon", {"carry": 17, "noise": -0.06}, 60, 105),
        item("vault_relic_pack", "Vault Relic Pack", "pack", ["Storage", "Tech"], "legendary", {"carry": 30, "staminaDrainMul": 0.9, "moraleMul": 0.95}, 180, 180),
        # Armor
        item("armor_scrap", "Scrap Plate Vest", "armor", ["Armor", "Combat"], "uncommon", {"injuryResist": 0.12, "noise": 0.06}, 36, 90),
        item("rain_poncho", "Rain Poncho", "armor", ["Weather"], "common", {"hydrationDrainMul": 0.93}, 20, 75),
        item("patchwork_armor", "Patchwork Armor", "armor", ["Armor"], "uncommon", {"injuryResist": 0.15, "staminaDrainMul": 1.02}, 52, 115),
        item("riot_vest", "Riot Vest", "armor", ["Armor", "Authority"], "rare", {"injuryResist": 0.2, "noise": 0.08}, 95, 140),
        item("padded_jacket", "Padded Jacket", "armor", ["Weather", "Stealth"], "common", {"injuryResist": 0.06, "noise": -0.03}, 28, 85),
        item("hazmat_shell", "Hazmat Shell", "armor", ["Toxic", "Medical"], "rare", {"hydrationDrainMul": 0.92, "injuryResist": 0.1}, 110, 130),
        item("ceramic_plate", "Ceramic Plate Carrier", "armor", ["Armor", "Combat"], "rare", {"injuryResist": 0.25, "speed": -0.05}, 122, 160),
        item("stealth_weave", "Stealth Weave Coat", "armor", ["Stealth"], "rare", {"noise": -0.14, "speed": 0.04}, 104, 110),
        item("fireproof_coat", "Fireproof Coat", "armor", ["Hazard"], "rare", {"injuryResist": 0.12, "hydrationDrainMul": 0.97}, 90, 115),
        item("sentinel_armor", "Sentinel Armor", "armor", ["Armor", "Authority"], "legendary", {"injuryResist": 0.34, "staminaDrainMul": 1.03}, 210, 190),
        # Vehicles
        item("bike_rusty", "Rusty Bike", "vehicle", ["Vehicle"], "uncommon", {"speed": 0.38, "noise": 0.22, "staminaDrainMul": 0.92}, 50, 110),
        item("scooter_electric", "Electric Scooter", "vehicle", ["Vehicle", "Tech"], "uncommon", {"speed": 0.33, "noise": 0.08, "hydrationDrainMul": 0.98}, 62, 120),
        item("cart_puller", "Pull Cart", "vehicle", ["Vehicle", "Storage"], "common", {"speed": 0.12, "carry": 10, "staminaDrainMul": 0.93}, 30, 100),
        item("dirt_bike", "Dirt Bike", "vehicle", ["Vehicle", "Combat"], "rare", {"speed": 0.47, "noise": 0.3, "hydrationDrainMul": 1.03}, 120, 140),
        item("courier_board", "Courier Board", "vehicle", ["Vehicle", "Trade"], "uncommon", {"speed": 0.24, "staminaDrainMul": 0.95}, 58, 95),
        item("fold_bike", "Fold Bike", "vehicle", ["Vehicle", "Stealth"], "common", {"speed": 0.26, "carry": 4, "noise": 0.05}, 42, 100),
        item("atv_salvaged", "Salvaged ATV", "vehicle", ["Vehicle", "Combat"], "rare", {"speed": 0.5, "noise": 0.36, "injuryResist": 0.03}, 132, 150),
        item("silent_glider", "Silent Glider", "vehicle", ["Vehicle", "Stealth"], "rare", {"speed": 0.35, "noise": -0.06, "staminaDrainMul": 0.9}, 146, 125),
        item("armored_buggy", "Armored Buggy", "vehicle", ["Vehicle", "Authority"], "legendary", {"speed": 0.42, "injuryResist": 0.1, "noise": 0.42}, 220, 200),
        item("scout_drone_bike", "Scout Drone Bike", "vehicle", ["Vehicle", "Tech"], "legendary", {"speed": 0.56, "staminaDrainMul": 0.88, "noise": 0.1}, 245, 210),
        # Utility
        item("medkit_small", "Small Medkit", "utility", ["Medical", "Consumable"], "uncommon", {"carry": 1}, 40),
        item("filter_mask", "Filter Mask", "utility", ["Toxic", "Safety"], "rare", {"hydrationDrainMul": 0.95, "staminaDrainMul": 0.96}, 60, 80),
        item("lockpick_set", "Lockpick Set", "utility", ["Stealth", "Access", "Tool"], "uncommon", {"noise": -0.05}, 54, 70),
        item("radio_parts", "Radio Parts", "utility", ["Tech", "Signal"], "uncommon", {"moraleMul": 0.97}, 52, 65),
        item("med_armband", "Medical Armband", "utility", ["Medical"], "uncommon", {"injuryResist": 0.05, "moraleMul": 0.98}, 45),
        item("noise_dampener", "Noise Dampener", "utility", ["Stealth", "Tech"], "uncommon", {"noise": -0.15}, 62, 80),
        item("repair_kit", "Repair Kit", "utility", ["Tool", "Tech"], "common", {"carry": 1}, 30),
        item("canteen_dented", "Dented Canteen", "utility", ["Water"], "common", {"hydrationDrainMul": 0.9}, 22),
        item("energy_gel", "Energy Gel Pack", "utility", ["Food", "Stamina"], "common", {"staminaDrainMul": 0.88}, 14),
        item("water_purifier", "Water Purifier", "utility", ["Toxic", "Medical"], "rare", {"hydrationDrainMul": 0.89}, 74, 95),
        item("signal_flare", "Signal Flare", "utility", ["Signal", "Trade"], "common", {"moraleMul": 0.99, "noise": 0.2}, 16),
        item("flashlight_crank", "Crank Flashlight", "utility", ["Tool", "Tech"], "common", {"moraleMul": 0.99}, 18, 90),
        item("toxin_kit", "Toxin Neutralizer Kit", "utility", ["Toxic", "Medical"], "rare", {"injuryResist": 0.07}, 85),
        item("rope_grapple", "Rope Grapple", "utility", ["Access", "Stealth", "Tool"], "uncommon", {"speed": 0.03}, 42, 85),
        item("trade_manifest", "Trade Manifest", "utility", ["Trade", "Authority"], "uncommon", {"moraleMul": 0.97}, 50),
        item("hacking_rig", "Portable Hacking Rig", "utility", ["Tech"], "rare", {"speed": 0.04, "noise": 0.05}, 120, 100),
        item("stealth_cloak", "Stealth Cloak", "utility", ["Stealth"], "rare", {"noise": -0.2, "moraleMul": 0.97}, 130, 100),
        item("stim_patch", "Stim Patch", "utility", ["Medical", "Stamina"], "rare", {"staminaDrainMul": 0.85}, 88),
        item("morale_cards", "Morale Cards", "utility", ["Social"], "common", {"moraleMul": 0.94}, 20),
        item("battery_bank", "Battery Bank", "utility", ["Tech"], "common", {"hydrationDrainMul": 0.98}, 24),
        # Faction
        item("badge_police", "Police Badge", "faction", ["Authority", "Trade"], "rare", {"moraleMul": 0.95}, 95),
        item("clinic_pass", "Clinic Access Pass", "faction", ["Medical", "Authority"], "rare", {"moraleMul": 0.96}, 90),
        item("guild_token", "Guild Token", "faction", ["Trade"], "uncommon", {"moraleMul": 0.97}, 58),
        item("scavenger_crest", "Scavenger Crest", "faction", ["Stealth", "Trade"], "uncommon", {"noise": -0.08}, 64),
        item("militia_band", "Militia Armband", "faction", ["Combat", "Authority"], "rare", {"injuryResist": 0.08}, 88),
        item("trade_stamp", "Trade Permit Stamp", "faction", ["Trade", "Authority"], "uncommon", {"moraleMul": 0.97}, 52),
        # Consumables / materials
        item("scrap", "Scrap Bundle", "consumable", ["Resource"], "common", {}, 4),
        item("cloth", "Cloth Roll", "consumable", ["Resource"], "common", {}, 4),
        item("plastic", "Plastic Shards", "consumable", ["Resource"], "common", {}, 4),
        item("metal", "Metal Fragments", "consumable", ["Resource"], "common", {}, 5),
        item("water_pouch", "Water Pouch", "consumable", ["Water", "Resource"], "common", {}, 6),
        item("ration_pack", "Ration Pack", "consumable", ["Food", "Resource"], "common", {}, 6),
        item("med_supplies", "Medical Supplies", "consumable", ["Medical", "Resource"], "common", {}, 8),
        item("circuit_board", "Circuit Board", "consumable", ["Tech", "Resource"], "uncommon", {}, 11),
        item("fuel_cell", "Fuel Cell", "consumable", ["Resource", "Hazard"], "uncommon", {}, 13),
        item("antiseptic", "Antiseptic Vial", "consumable", ["Medical", "Resource"], "common", {}, 8),
    ]
    return items


def build_loot_tables() -> list[dict[str, Any]]:
    return [
        {
            "id": "suburbs_common",
            "rolls": 1,
            "entries": [
                {"itemId": "scrap", "weight": 8, "min": 1, "max": 3},
                {"itemId": "cloth", "weight": 7, "min": 1, "max": 3},
                {"itemId": "plastic", "weight": 7, "min": 1, "max": 3},
                {"itemId": "metal", "weight": 6, "min": 1, "max": 2},
                {"itemId": "water_pouch", "weight": 5, "min": 1, "max": 2},
                {"itemId": "ration_pack", "weight": 5, "min": 1, "max": 2},
                {"itemId": "canteen_dented", "weight": 3, "min": 1, "max": 1},
                {"itemId": "energy_gel", "weight": 4, "min": 1, "max": 2},
                {"itemId": "backpack_basic", "weight": 1, "min": 1, "max": 1},
                {"itemId": "sling_pack", "weight": 1, "min": 1, "max": 1},
            ],
        },
        {
            "id": "suburbs_medical",
            "rolls": 1,
            "guaranteed": [{"itemId": "antiseptic", "qty": 1}],
            "entries": [
                {"itemId": "med_supplies", "weight": 8, "min": 1, "max": 2},
                {"itemId": "medkit_small", "weight": 6, "min": 1, "max": 1},
                {"itemId": "med_armband", "weight": 3, "min": 1, "max": 1},
                {"itemId": "stim_patch", "weight": 2, "min": 1, "max": 1},
                {"itemId": "filter_mask", "weight": 2, "min": 1, "max": 1},
                {"itemId": "toxin_kit", "weight": 1, "min": 1, "max": 1},
            ],
        },
        {
            "id": "suburbs_trade",
            "rolls": 1,
            "entries": [
                {"itemId": "trade_manifest", "weight": 5, "min": 1, "max": 1},
                {"itemId": "guild_token", "weight": 4, "min": 1, "max": 1},
                {"itemId": "trade_stamp", "weight": 4, "min": 1, "max": 1},
                {"itemId": "courier_pack", "weight": 2, "min": 1, "max": 1},
                {"itemId": "morale_cards", "weight": 5, "min": 1, "max": 1},
                {"itemId": "signal_flare", "weight": 3, "min": 1, "max": 2},
                {"itemId": "radio_parts", "weight": 3, "min": 1, "max": 1},
            ],
        },
        {
            "id": "suburbs_toxic",
            "rolls": 1,
            "entries": [
                {"itemId": "filter_mask", "weight": 5, "min": 1, "max": 1},
                {"itemId": "water_purifier", "weight": 4, "min": 1, "max": 1},
                {"itemId": "toxin_kit", "weight": 4, "min": 1, "max": 1},
                {"itemId": "hazmat_shell", "weight": 2, "min": 1, "max": 1},
                {"itemId": "hazard_pack", "weight": 2, "min": 1, "max": 1},
                {"itemId": "fuel_cell", "weight": 3, "min": 1, "max": 2},
            ],
        },
        {
            "id": "suburbs_hazard",
            "rolls": 1,
            "entries": [
                {"itemId": "repair_kit", "weight": 5, "min": 1, "max": 1},
                {"itemId": "rope_grapple", "weight": 3, "min": 1, "max": 1},
                {"itemId": "rain_poncho", "weight": 3, "min": 1, "max": 1},
                {"itemId": "padded_jacket", "weight": 3, "min": 1, "max": 1},
                {"itemId": "fuel_cell", "weight": 4, "min": 1, "max": 2},
                {"itemId": "metal", "weight": 5, "min": 1, "max": 2},
            ],
        },
        {
            "id": "suburbs_combat",
            "rolls": 1,
            "entries": [
                {"itemId": "armor_scrap", "weight": 5, "min": 1, "max": 1},
                {"itemId": "riot_vest", "weight": 3, "min": 1, "max": 1},
                {"itemId": "lockpick_set", "weight": 3, "min": 1, "max": 1},
                {"itemId": "militia_band", "weight": 2, "min": 1, "max": 1},
                {"itemId": "energy_gel", "weight": 3, "min": 1, "max": 2},
                {"itemId": "repair_kit", "weight": 2, "min": 1, "max": 1},
            ],
        },
        {
            "id": "suburbs_rare",
            "rolls": 1,
            "entries": [
                {"itemId": "expedition_pack", "weight": 3, "min": 1, "max": 1},
                {"itemId": "stealth_cloak", "weight": 2, "min": 1, "max": 1},
                {"itemId": "hacking_rig", "weight": 2, "min": 1, "max": 1},
                {"itemId": "sentinel_armor", "weight": 1, "min": 1, "max": 1},
                {"itemId": "scout_drone_bike", "weight": 1, "min": 1, "max": 1},
                {"itemId": "badge_police", "weight": 2, "min": 1, "max": 1},
                {"itemId": "vault_relic_pack", "weight": 1, "min": 1, "max": 1},
            ],
        },
        {
            "id": "suburbs_materials",
            "rolls": 2,
            "entries": [
                {"itemId": "scrap", "weight": 9, "min": 1, "max": 4},
                {"itemId": "cloth", "weight": 9, "min": 1, "max": 4},
                {"itemId": "plastic", "weight": 9, "min": 1, "max": 4},
                {"itemId": "metal", "weight": 8, "min": 1, "max": 3},
                {"itemId": "circuit_board", "weight": 4, "min": 1, "max": 2},
                {"itemId": "med_supplies", "weight": 3, "min": 1, "max": 2},
                {"itemId": "fuel_cell", "weight": 2, "min": 1, "max": 2},
            ],
        },
    ]


def _make_hazard_event(
    event_id: str,
    title: str,
    text: str,
    death_flag: str,
    gate_tag: str,
    weight: float,
    trigger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return event(
        event_id,
        title,
        text,
        tags=["hazard"],
        weight=weight,
        trigger=trigger or {"biomeIds": ["suburbs"], "cooldownSteps": 2},
        options=[
            option(
                "push_through",
                "Push through fast",
                "You force your way through the hazard.",
                outcomes=[
                    {"metersDelta": {"stamina": -8, "hydration": -6, "morale": -2}},
                    {"addInjury": 6},
                    {"setFlags": [death_flag]},
                    {"setDeathChance": 0.06},
                ],
            ),
            option(
                "specialist_plan",
                f"Use {gate_tag} approach",
                f"Your {gate_tag.lower()} tools let you cross with fewer losses.",
                requirements={"hasTag": gate_tag},
                outcomes=[
                    {"metersDelta": {"stamina": -3, "hydration": -2, "morale": 1}},
                    {"addInjury": 1},
                ],
            ),
            option(
                "wait_it_out",
                "Wait for a safer window",
                "You wait for a better moment and lose some momentum.",
                outcomes=[{"metersDelta": {"hydration": -5, "morale": -3}}],
            ),
        ],
    )


def _make_loot_event(
    event_id: str,
    title: str,
    text: str,
    table_id: str,
    gate_tag: str,
    trigger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return event(
        event_id,
        title,
        text,
        tags=["loot"],
        weight=6.0,
        trigger=trigger or {"biomeIds": ["suburbs"], "cooldownSteps": 2},
        options=[
            option(
                "search",
                "Search carefully",
                "You clear each room and gather whatever still works.",
                outcomes=[
                    {"metersDelta": {"stamina": -4}},
                    {"lootRoll": {"lootTableId": table_id, "rolls": 2}},
                ],
            ),
            option(
                "special_entry",
                f"Use {gate_tag} approach",
                f"Your {gate_tag.lower()} edge opens sealed stashes.",
                requirements={"hasTag": gate_tag},
                outcomes=[
                    {"metersDelta": {"stamina": -2, "morale": 2}},
                    {"lootRoll": {"lootTableId": table_id, "rolls": 3}},
                ],
            ),
            option(
                "skip",
                "Skip this location",
                "You avoid the risk and keep moving.",
                outcomes=[{"metersDelta": {"morale": -1}}],
            ),
        ],
    )


def _make_trade_event(
    event_id: str,
    title: str,
    text: str,
    trade_table: str,
    gate_tag: str,
    trigger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return event(
        event_id,
        title,
        text,
        tags=["trade", "social"],
        weight=5.0,
        trigger=trigger or {"biomeIds": ["suburbs"], "minDistance": 2, "cooldownSteps": 3},
        options=[
            option(
                "barter",
                "Barter fairly",
                "You make a measured trade and both sides leave steady.",
                costs=[{"removeItems": [{"itemId": "scrap", "qty": 1}]}],
                outcomes=[
                    {"lootRoll": {"lootTableId": trade_table, "rolls": 1}},
                    {"metersDelta": {"morale": 2}},
                ],
            ),
            option(
                "leverage",
                f"Leverage your {gate_tag} standing",
                "Your reputation gives you better terms.",
                requirements={"hasTag": gate_tag},
                outcomes=[
                    {"lootRoll": {"lootTableId": trade_table, "rolls": 2}},
                    {"setFlags": ["trade_favor"]},
                    {"metersDelta": {"morale": 3}},
                ],
            ),
            option(
                "walk",
                "Walk away",
                "You keep resources but lose opportunity.",
                outcomes=[{"metersDelta": {"morale": -2}}],
            ),
        ],
    )


def _make_ambush_event(
    event_id: str,
    title: str,
    text: str,
    trigger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return event(
        event_id,
        title,
        text,
        tags=["combat", "hazard"],
        weight=6.0,
        trigger=trigger or {"biomeIds": ["suburbs"], "minDistance": 5, "cooldownSteps": 2},
        options=[
            option(
                "fight",
                "Fight back",
                "You stand your ground and scrape out a win.",
                requirements={"any": [{"hasTag": "Combat"}, {"hasTag": "Authority"}]},
                outcomes=[
                    {"addInjury": 7},
                    {"lootRoll": {"lootTableId": "suburbs_combat", "rolls": 2}},
                    {"metersDelta": {"morale": 3}},
                ],
            ),
            option(
                "evade",
                "Evade and break line of sight",
                "You sprint through side routes to escape.",
                costs=[{"metersDelta": {"stamina": -10}}],
                outcomes=[
                    {"metersDelta": {"morale": -2}},
                    {"setFlags": ["narrow_escape"]},
                    {"setDeathChance": 0.03},
                ],
            ),
            option(
                "drop_supplies",
                "Drop supplies and retreat",
                "You trade supplies for survival.",
                outcomes=[
                    {"removeItems": [{"itemId": "water_pouch", "qty": 1}, {"itemId": "ration_pack", "qty": 1}]},
                    {"metersDelta": {"morale": -8}},
                ],
            ),
        ],
    )


def build_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    # 1-8: hazards
    events.extend(
        [
            _make_hazard_event("thirsty_choice", "Thirsty Choice", "Your lips crack and nearby water looks unsafe.", "toxic_exposure", "Toxic", 7.0),
            _make_hazard_event("heatwave_wave", "Heatwave Front", "A brutal wave of heat rolls through cracked streets.", "burned", "Medical", 6.0),
            _make_hazard_event("toxic_fog_bank", "Toxic Fog Bank", "A chemical fog blankets the next block.", "toxic_exposure", "Toxic", 6.5),
            _make_hazard_event("acid_rain_front", "Acid Rain Front", "Corrosive rain starts hissing against metal.", "burned", "Toxic", 5.5),
            _make_hazard_event("unstable_rooftop", "Unstable Rooftop", "The rooftop crossing shifts under your weight.", "fell", "Stealth", 5.5),
            _make_hazard_event("flooded_underpass", "Flooded Underpass", "Dark water fills the only fast route forward.", "submerged", "Toxic", 5.0),
            _make_hazard_event("electrical_fire_lane", "Electrical Fire Lane", "Live wires dance across a fire-lit lane.", "burned", "Tech", 5.5),
            _make_hazard_event("collapse_aftershock", "Aftershock Collapse", "A distant blast buckles the structures around you.", "fell", "Access", 5.0),
        ]
    )

    # 9-16: loot POIs
    events.extend(
        [
            _make_loot_event("abandoned_house_loot", "Abandoned House", "A boarded house still hides untouched drawers.", "suburbs_common", "Stealth"),
            _make_loot_event("pharmacy_stockroom", "Pharmacy Stockroom", "A locked stockroom might still hold medical crates.", "suburbs_medical", "Medical"),
            _make_loot_event("hardware_mart", "Hardware Mart", "The hardware mart is stripped, but back rooms remain.", "suburbs_materials", "Access"),
            _make_loot_event("school_locker_hall", "School Locker Hall", "Rows of lockers line the dark hallway.", "suburbs_common", "Stealth"),
            _make_loot_event("bus_depot_cache", "Bus Depot Cache", "A depot office sits above parked husks.", "suburbs_hazard", "Tech"),
            _make_loot_event("rooftop_garden", "Rooftop Garden", "Planter beds and water tanks sit untouched on a roof.", "suburbs_common", "Medical"),
            _make_loot_event("pawn_shop_vault", "Pawn Shop Vault", "A compact vault door waits behind broken glass.", "suburbs_rare", "Access"),
            _make_loot_event("police_locker_room", "Police Locker Room", "A locker room survived behind armored shutters.", "suburbs_combat", "Authority"),
        ]
    )

    # 17-24: trade/social
    events.extend(
        [
            _make_trade_event("trader_encounter", "Roadside Trader", "A scavenger sets up a tarp full of mixed gear.", "suburbs_trade", "Trade"),
            _make_trade_event("convoy_haggle", "Convoy Haggle", "A convoy scout offers a quick roadside exchange.", "suburbs_trade", "Authority"),
            _make_trade_event("street_clinic_exchange", "Street Clinic", "A field medic offers treatment for materials.", "suburbs_medical", "Medical"),
            _make_trade_event("signal_exchange", "Signal Exchange", "A radio operator offers encrypted channel keys.", "suburbs_trade", "Tech"),
            _make_trade_event("refugee_camp_social", "Refugee Camp", "Camp volunteers ask for practical support.", "suburbs_common", "Medical"),
            _make_trade_event("rumor_broker", "Rumor Broker", "A broker sells route intel for the right favor.", "suburbs_trade", "Trade"),
            _make_trade_event("barter_busker", "Barter Busker", "A performer trades morale stories for supplies.", "suburbs_common", "Social"),
            _make_trade_event("salvage_union_checkpoint", "Salvage Union Checkpoint", "Union lookouts control this crossing.", "suburbs_trade", "Authority"),
        ]
    )

    # 25-32: ambush/combat-lite
    events.extend(
        [
            _make_ambush_event("alley_ambush", "Alley Ambush", "Movement in both alley exits closes around you."),
            _make_ambush_event("rooftop_sniper", "Rooftop Sniper", "A distant scope glints from a rooftop."),
            _make_ambush_event("pack_raiders", "Pack Raiders", "A raider team tracks your route from behind."),
            _make_ambush_event("toll_bridge_thugs", "Toll Bridge Thugs", "Armed scavs demand payment at a bottleneck."),
            _make_ambush_event("night_pursuit", "Night Pursuit", "Flashlights sweep over fences in pursuit."),
            _make_ambush_event("rival_scavengers", "Rival Scavengers", "A rival crew claims the block ahead."),
            _make_ambush_event("drone_trap", "Drone Trap", "Decoy pings draw you into an ambush pocket."),
            _make_ambush_event("mob_blockade", "Mob Blockade", "A desperate crowd blocks the route and tensions spike."),
        ]
    )

    # 33-40: mixed progression events
    events.extend(
        [
            event(
                "broken_bridge_fork",
                "Broken Bridge Fork",
                "A fractured bridge offers a risky jump or long detour.",
                tags=["hazard"],
                weight=4.0,
                trigger={"biomeIds": ["suburbs"], "minDistance": 8, "cooldownSteps": 4},
                options=[
                    option(
                        "risky_jump",
                        "Risk the jump",
                        "You commit to the broken span and barely clear it.",
                        outcomes=[{"metersDelta": {"stamina": -10}}, {"addInjury": 5}, {"setFlags": ["fell"]}],
                    ),
                    option(
                        "steady_detour",
                        "Take the long detour",
                        "You avoid the jump and preserve your body.",
                        outcomes=[{"metersDelta": {"hydration": -6, "morale": -2}}, {"setFlags": ["detour_taken"]}],
                    ),
                    option(
                        "grapple_crossing",
                        "Use grappling route",
                        "The rope route gets you across safely.",
                        requirements={"hasTag": "Access"},
                        outcomes=[{"metersDelta": {"stamina": -3}}, {"metersDelta": {"morale": 2}}],
                    ),
                ],
            ),
            event(
                "quarantine_gate",
                "Quarantine Gate",
                "An old quarantine gate blocks the fastest route.",
                tags=["hazard", "social"],
                weight=4.5,
                trigger={"biomeIds": ["suburbs"], "minDistance": 6},
                options=[
                    option(
                        "force_gate",
                        "Force through",
                        "You force the gate and inhale foul air.",
                        outcomes=[
                            {"addInjury": 4},
                            {"setFlags": ["toxic_exposure"]},
                            {"metersDelta": {"stamina": -6}},
                        ],
                    ),
                    option(
                        "show_credentials",
                        "Show credentials",
                        "Old authority tags still open one side entrance.",
                        requirements={"hasTag": "Authority"},
                        outcomes=[{"metersDelta": {"morale": 4}}, {"lootRoll": {"lootTableId": "suburbs_medical", "rolls": 1}}],
                    ),
                    option(
                        "decon_route",
                        "Take decontamination route",
                        "You follow marked arrows through a slower but cleaner lane.",
                        requirements={"hasTag": "Medical"},
                        outcomes=[{"metersDelta": {"hydration": -2, "morale": 1}}],
                    ),
                ],
            ),
            event(
                "locked_substation",
                "Locked Substation",
                "A power substation hums with backup charge.",
                tags=["tech", "loot"],
                weight=4.0,
                trigger={"biomeIds": ["suburbs"], "minDistance": 10, "cooldownSteps": 4},
                options=[
                    option(
                        "force_panel",
                        "Force the panel",
                        "You wrench open the panel and pocket spare cells.",
                        outcomes=[{"addInjury": 3}, {"lootRoll": {"lootTableId": "suburbs_materials", "rolls": 2}}],
                    ),
                    option(
                        "hack_panel",
                        "Hack maintenance access",
                        "Your tech setup opens a clean maintenance path.",
                        requirements={"hasTag": "Tech"},
                        outcomes=[{"lootRoll": {"lootTableId": "suburbs_rare", "rolls": 1}}, {"metersDelta": {"morale": 3}}],
                    ),
                    option(
                        "leave_power",
                        "Leave it untouched",
                        "You avoid the risk and keep moving.",
                        outcomes=[{"metersDelta": {"morale": -1}}],
                    ),
                ],
            ),
            event(
                "hidden_tunnel",
                "Hidden Tunnel",
                "A tunnel entrance appears behind collapsed signage.",
                tags=["stealth", "hazard"],
                weight=4.3,
                trigger={"biomeIds": ["suburbs"], "minDistance": 9},
                options=[
                    option(
                        "take_tunnel",
                        "Take the tunnel",
                        "The tunnel is tight and exhausting.",
                        outcomes=[{"metersDelta": {"stamina": -7, "hydration": -4}}, {"setDeathChance": 0.02}],
                    ),
                    option(
                        "silent_route",
                        "Take silent side tunnel",
                        "Your stealth gear helps you bypass threats below ground.",
                        requirements={"hasTag": "Stealth"},
                        outcomes=[{"metersDelta": {"stamina": -3}}, {"lootRoll": {"lootTableId": "suburbs_common", "rolls": 1}}],
                    ),
                    option(
                        "surface_route",
                        "Stay on the surface",
                        "You skip the tunnel and endure open exposure.",
                        outcomes=[{"metersDelta": {"hydration": -5, "morale": -2}}],
                    ),
                ],
            ),
            event(
                "supply_drop_signal",
                "Supply Drop Signal",
                "An emergency beacon hints at a nearby drop cache.",
                tags=["loot", "tech", "trade"],
                weight=4.0,
                trigger={"biomeIds": ["suburbs"], "minDistance": 12, "requiredFlagsAll": ["trade_favor"]},
                options=[
                    option(
                        "rush_drop",
                        "Rush to the drop",
                        "You push hard to reach the crate before others.",
                        costs=[{"metersDelta": {"stamina": -8}}],
                        outcomes=[{"lootRoll": {"lootTableId": "suburbs_trade", "rolls": 2}}],
                    ),
                    option(
                        "decode_beacon",
                        "Decode beacon metadata",
                        "The decoded path leads to a higher-value cache.",
                        requirements={"hasTag": "Tech"},
                        outcomes=[{"lootRoll": {"lootTableId": "suburbs_rare", "rolls": 1}}, {"metersDelta": {"morale": 4}}],
                    ),
                    option(
                        "ignore_signal",
                        "Ignore the signal",
                        "You choose certainty over a contested cache.",
                        outcomes=[{"metersDelta": {"morale": -1}}],
                    ),
                ],
            ),
            event(
                "stray_dog_social",
                "Stray Dog",
                "A wary stray shadows your route from a distance.",
                tags=["social"],
                weight=4.2,
                trigger={"biomeIds": ["suburbs"], "cooldownSteps": 4},
                options=[
                    option(
                        "befriend",
                        "Offer scraps and befriend",
                        "The dog settles in and boosts your spirits.",
                        costs=[{"removeItems": [{"itemId": "ration_pack", "qty": 1}]}],
                        outcomes=[{"setFlags": ["dog_friend"]}, {"metersDelta": {"morale": 7}}],
                    ),
                    option(
                        "medic_check",
                        "Treat its wounds",
                        "Medical care earns instant trust.",
                        requirements={"hasTag": "Medical"},
                        outcomes=[{"metersDelta": {"morale": 9}}, {"lootRoll": {"lootTableId": "suburbs_common", "rolls": 1}}],
                    ),
                    option(
                        "chase_off",
                        "Chase it away",
                        "The dog flees and the moment passes.",
                        outcomes=[{"metersDelta": {"morale": -3}}],
                    ),
                ],
            ),
            event(
                "memorial_square",
                "Memorial Square",
                "A quiet square offers a rare pause from danger.",
                tags=["social"],
                weight=3.5,
                trigger={"biomeIds": ["suburbs"], "minDistance": 14},
                options=[
                    option(
                        "rest_briefly",
                        "Rest briefly",
                        "A short rest steadies your breathing.",
                        outcomes=[{"metersDelta": {"stamina": 6, "morale": 4}}],
                    ),
                    option(
                        "tech_scan",
                        "Scan old terminals",
                        "The terminals reveal supply markers.",
                        requirements={"hasTag": "Tech"},
                        outcomes=[{"lootRoll": {"lootTableId": "suburbs_materials", "rolls": 2}}, {"metersDelta": {"morale": 2}}],
                    ),
                    option(
                        "keep_moving",
                        "Keep moving",
                        "You ignore the stop and stay on route.",
                        outcomes=[{"metersDelta": {"morale": -1}}],
                    ),
                ],
            ),
            event(
                "final_mile_push",
                "Final Mile Push",
                "You feel the run grinding you down as distance grows.",
                tags=["hazard"],
                weight=3.0,
                trigger={"biomeIds": ["suburbs"], "minDistance": 20, "cooldownSteps": 5},
                options=[
                    option(
                        "all_out",
                        "Push all out",
                        "You force one more surge forward.",
                        outcomes=[
                            {"metersDelta": {"stamina": -12, "hydration": -8}},
                            {"metersDelta": {"morale": 5}},
                            {"setDeathChance": 0.05},
                        ],
                    ),
                    option(
                        "disciplined_stride",
                        "Use disciplined stride",
                        "A steady pace keeps your systems stable.",
                        requirements={"hasTag": "Trade"},
                        outcomes=[{"metersDelta": {"stamina": -4, "hydration": -3, "morale": 2}}],
                    ),
                    option(
                        "slow_and_safe",
                        "Slow and safe",
                        "You avoid collapse by sacrificing pace.",
                        outcomes=[{"metersDelta": {"stamina": -3, "morale": -1}}],
                    ),
                ],
            ),
        ]
    )

    if len(events) != 40:
        raise ValueError(f"Expected 40 events, got {len(events)}")
    return events


def build_biomes() -> list[dict[str, Any]]:
    return [
        {
            "id": "suburbs",
            "name": "Ruined Suburbs",
            "meterDrainMul": {"stamina": 1.0, "hydration": 1.15, "morale": 1.0},
            "eventWeightMulByTag": {
                "hazard": 1.15,
                "combat": 1.2,
                "loot": 1.0,
                "trade": 0.95,
                "social": 1.05,
                "tech": 1.0,
            },
            "lootTableIds": [
                "suburbs_common",
                "suburbs_medical",
                "suburbs_trade",
                "suburbs_toxic",
                "suburbs_hazard",
                "suburbs_combat",
                "suburbs_rare",
                "suburbs_materials",
            ],
        }
    ]


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    items = build_items()
    loottables = build_loot_tables()
    biomes = build_biomes()
    events = build_events()

    write_json(CONTENT_DIR / "items.json", items)
    write_json(CONTENT_DIR / "loottables.json", loottables)
    write_json(CONTENT_DIR / "biomes.json", biomes)
    write_json(CONTENT_DIR / "events.json", events)

    print(f"Wrote {len(items)} items, {len(events)} events, {len(biomes)} biome, {len(loottables)} loot tables.")


if __name__ == "__main__":
    main()

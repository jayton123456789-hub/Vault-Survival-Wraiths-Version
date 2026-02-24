from __future__ import annotations

import json
from pathlib import Path


def hazard_event(event_id: str, title: str, text: str, danger_flag: str, specialist_tag: str, min_distance: float = 0.0):
    return {
        "id": event_id,
        "title": title,
        "text": text,
        "tags": ["hazard"],
        "trigger": {"biomeIds": ["suburbs"], "minDistance": min_distance, "cooldownSteps": 2},
        "weight": 5.8,
        "options": [
            {
                "id": "push",
                "label": "Push straight through",
                "costs": [{"metersDelta": {"stamina": -4}}],
                "outcomes": [
                    {"metersDelta": {"hydration": -5, "morale": -2}},
                    {"addInjury": {"amount": 6}},
                    {"setFlags": [danger_flag]},
                    {"setDeathChance": 0.04},
                ],
                "logLine": "You accept the risk and force your way through.",
            },
            {
                "id": "specialist",
                "label": f"Use your {specialist_tag} approach",
                "requirements": {"hasTag": specialist_tag},
                "outcomes": [
                    {"metersDelta": {"stamina": -2, "hydration": -2, "morale": 1}},
                    {"addInjury": {"amount": 1}},
                ],
                "logLine": f"Your {specialist_tag.lower()} gear keeps the damage manageable.",
            },
            {
                "id": "detour",
                "label": "Take the long detour",
                "outcomes": [
                    {"metersDelta": {"stamina": -3, "hydration": -4, "morale": -1}},
                    {"setFlags": ["detour_taken"]},
                ],
                "logLine": "You lose time but avoid the worst of it.",
            },
        ],
    }


def loot_event(event_id: str, title: str, text: str, table_id: str, gate_tag: str, min_distance: float = 0.0):
    return {
        "id": event_id,
        "title": title,
        "text": text,
        "tags": ["loot"],
        "trigger": {"biomeIds": ["suburbs"], "minDistance": min_distance, "cooldownSteps": 2},
        "weight": 6.2,
        "options": [
            {
                "id": "sweep",
                "label": "Sweep the site carefully",
                "costs": [{"metersDelta": {"stamina": -3}}],
                "outcomes": [{"lootRoll": {"lootTableId": table_id, "rolls": 2}}],
                "logLine": "You methodically clear the site and salvage what still has value.",
            },
            {
                "id": "special_access",
                "label": f"Open sealed cache ({gate_tag})",
                "requirements": {"hasTag": gate_tag},
                "outcomes": [
                    {"lootRoll": {"lootTableId": table_id, "rolls": 3}},
                    {"metersDelta": {"morale": 2}},
                ],
                "logLine": f"Your {gate_tag.lower()} edge opens storage most scavengers miss.",
            },
            {
                "id": "skip",
                "label": "Skip and preserve pace",
                "outcomes": [{"metersDelta": {"morale": -1}}],
                "logLine": "You leave the location untouched and keep moving.",
            },
        ],
    }


def social_event(event_id: str, title: str, text: str, helpful_tag: str, table_id: str, min_distance: float = 0.0):
    return {
        "id": event_id,
        "title": title,
        "text": text,
        "tags": ["social", "trade"],
        "trigger": {"biomeIds": ["suburbs"], "minDistance": min_distance, "cooldownSteps": 3},
        "weight": 4.8,
        "options": [
            {
                "id": "parley",
                "label": "Talk and negotiate",
                "outcomes": [
                    {"metersDelta": {"morale": 3}},
                    {"setFlags": ["trade_favor"]},
                    {"lootRoll": {"lootTableId": table_id, "rolls": 1}},
                ],
                "logLine": "You strike a fragile deal and leave with a small advantage.",
            },
            {
                "id": "tag_play",
                "label": f"Leverage {helpful_tag} standing",
                "requirements": {"hasTag": helpful_tag},
                "outcomes": [
                    {"metersDelta": {"morale": 5}},
                    {"lootRoll": {"lootTableId": table_id, "rolls": 2}},
                ],
                "logLine": f"Your {helpful_tag.lower()} credibility shifts the exchange in your favor.",
            },
            {
                "id": "withdraw",
                "label": "Back out quietly",
                "outcomes": [{"metersDelta": {"morale": -2, "stamina": -1}}],
                "logLine": "You disengage before the situation turns ugly.",
            },
        ],
    }


def combat_event(event_id: str, title: str, text: str, min_distance: float):
    return {
        "id": event_id,
        "title": title,
        "text": text,
        "tags": ["combat", "hazard"],
        "trigger": {"biomeIds": ["suburbs"], "minDistance": min_distance, "cooldownSteps": 2},
        "weight": 5.6,
        "options": [
            {
                "id": "counter",
                "label": "Counter-ambush",
                "requirements": {"any": [{"hasTag": "Combat"}, {"hasTag": "Authority"}]},
                "outcomes": [
                    {"addInjury": {"amount": 5}},
                    {"lootRoll": {"lootTableId": "suburbs_combat", "rolls": 2}},
                    {"metersDelta": {"morale": 3}},
                ],
                "logLine": "You hit first and break contact on your terms.",
            },
            {
                "id": "evade",
                "label": "Break line of sight",
                "costs": [{"metersDelta": {"stamina": -9}}],
                "outcomes": [
                    {"metersDelta": {"morale": -2}},
                    {"setFlags": ["narrow_escape"]},
                    {"setDeathChance": 0.02},
                ],
                "logLine": "You run hard, lose ground, and survive by inches.",
            },
            {
                "id": "pay_toll",
                "label": "Pay a supply toll",
                "outcomes": [
                    {"removeItems": [{"itemId": "water_pouch", "qty": 1}, {"itemId": "ration_pack", "qty": 1}]},
                    {"metersDelta": {"morale": -6}},
                ],
                "logLine": "You buy your way out and keep your body intact.",
            },
        ],
    }


def build_events() -> list[dict]:
    events: list[dict] = []

    hazard_specs = [
        ("heat_gutter_lane", "Heat Gutter Lane", "A concrete channel radiates oven-like heat.", "burned", "Medical", 0),
        ("chlorine_pool_break", "Chlorine Pool Break", "A shattered treatment pool leaks corrosive mist.", "toxic_exposure", "Toxic", 2),
        ("glassfall_crosswalk", "Glassfall Crosswalk", "An upper facade keeps shedding razor glass.", "fell", "Stealth", 4),
        ("live_wire_storm", "Live Wire Storm", "Stormwind whips live wires across the street.", "burned", "Tech", 5),
        ("sinkhole_row", "Sinkhole Row", "Collapsed asphalt leaves deep hidden voids.", "fell", "Access", 6),
        ("flood_surge_tunnel", "Flood Surge Tunnel", "Tunnel water surges with every distant tremor.", "submerged", "Toxic", 7),
        ("rad_dust_front", "Rad Dust Front", "A pale dust front rolls in from industrial ruins.", "toxic_exposure", "Toxic", 8),
        ("boiler_blast_zone", "Boiler Blast Zone", "Burst steam lines scream across the lane.", "burned", "Tech", 10),
        ("dogpack_corridor", "Dogpack Corridor", "Starving dogs stalk the narrow passage.", "fell", "Stealth", 10),
        ("night_frost_snap", "Night Frost Snap", "Temperature crashes and your gear starts locking up.", "fell", "Medical", 11),
        ("acid_rain_residue", "Acid Rain Residue", "Yesterday's rainfall left burning puddles everywhere.", "burned", "Toxic", 12),
        ("smoke_chokepoint", "Smoke Chokepoint", "A black smoke wall blocks the shortest route.", "toxic_exposure", "Medical", 13),
    ]
    for spec in hazard_specs:
        events.append(hazard_event(*spec))

    loot_specs = [
        ("abandoned_house_loot", "Abandoned House", "Boarded rooms still hide untouched drawers.", "suburbs_common", "Stealth", 0),
        ("clinic_supply_room", "Clinic Supply Room", "A clinic backroom might still hold sterile packs.", "suburbs_medical", "Medical", 2),
        ("hardware_back_cage", "Hardware Back Cage", "The back cage is intact behind bent steel.", "suburbs_materials", "Access", 3),
        ("bus_depot_parts", "Bus Depot Parts Bay", "Beneath the depot office: boxed salvage.", "suburbs_hazard", "Tech", 4),
        ("rooftop_planters", "Rooftop Planters", "Irrigation tanks and planters survived on the roof.", "suburbs_common", "Medical", 5),
        ("pawn_vault_locker", "Pawn Vault Locker", "The pawn vault lock is old but stubborn.", "suburbs_rare", "Access", 6),
        ("cinema_projection_room", "Projection Room", "Old cinema reels hide locked utility crates.", "suburbs_trade", "Trade", 7),
        ("school_lab_storage", "School Lab Storage", "Science wing cabinets are mostly untouched.", "suburbs_materials", "Tech", 8),
        ("substation_lot", "Substation Lot", "Transformer crates litter the fenced lot.", "suburbs_hazard", "Tech", 9),
        ("storm_shelter_bin", "Storm Shelter Bin", "Emergency bins line the shelter hall.", "suburbs_common", "Authority", 10),
        ("warehouse_pallet_line", "Warehouse Pallet Line", "Stacked pallets hide marked supply drums.", "suburbs_materials", "Trade", 11),
        ("signal_cache_drop", "Signal Cache Drop", "A coded beacon points to a sealed drop canister.", "suburbs_rare", "Tech", 12),
    ]
    for spec in loot_specs:
        events.append(loot_event(*spec))

    social_specs = [
        ("market_stand_off", "Market Standoff", "Two traders argue over medicine near a burned kiosk.", "Trade", "suburbs_trade", 2),
        ("street_clinic_line", "Street Clinic Line", "A volunteer medic asks for escort help.", "Medical", "suburbs_medical", 3),
        ("checkpoint_remnant", "Checkpoint Remnant", "A checkpoint crew still honors old insignia.", "Authority", "suburbs_trade", 4),
        ("radio_hub_hush", "Radio Hub Hush", "A whisper-net operator offers route intel.", "Tech", "suburbs_trade", 5),
        ("sewer_guide_offer", "Sewer Guide Offer", "A local runner offers hidden-route guidance.", "Stealth", "suburbs_common", 6),
        ("ration_dispute", "Ration Dispute", "A crowd fights over a ration crate split.", "Authority", "suburbs_common", 7),
        ("lost_child_signal", "Lost Child Signal", "A crackly call begs for a family escort.", "Medical", "suburbs_medical", 8),
        ("water_barrel_auction", "Water Barrel Auction", "A barrel lot opens to whoever negotiates best.", "Trade", "suburbs_trade", 9),
        ("neutral_zone_truce", "Neutral Zone Truce", "A no-fire square offers temporary shelter.", "Authority", "suburbs_common", 10),
        ("radio_relay_help", "Relay Repair Plea", "Operators need one more set of hands.", "Tech", "suburbs_materials", 11),
    ]
    for spec in social_specs:
        events.append(social_event(*spec))

    combat_specs = [
        ("toll_bridge_thugs", "Toll Bridge Thugs", "Armed scavs demand payment at a chokepoint.", 5),
        ("night_pursuit", "Night Pursuit", "Flashlights sweep alleys while boots close in.", 6),
        ("rival_scavenger_push", "Rival Scavenger Push", "Another crew claims this block as theirs.", 7),
        ("drone_decoy_trap", "Drone Decoy Trap", "Decoy pings draw you into a boxed lane.", 8),
        ("mob_blockade", "Mob Blockade", "A desperate crowd hard-blocks the street.", 9),
        ("rooftop_sniper_glint", "Rooftop Glint", "Someone tracks movement from upper balconies.", 10),
        ("collapsed_rail_ambush", "Collapsed Rail Ambush", "Ambushers use freight cars as cover.", 11),
        ("fuel_yard_crossfire", "Fuel Yard Crossfire", "Two groups exchange fire across fuel tanks.", 12),
    ]
    for spec in combat_specs:
        events.append(combat_event(*spec))

    specials = [
        {
            "id": "broken_bridge_fork",
            "title": "Broken Bridge Fork",
            "text": "A fractured bridge offers a risky jump or a long low route.",
            "tags": ["hazard"],
            "trigger": {"biomeIds": ["suburbs"], "minDistance": 8, "cooldownSteps": 4},
            "weight": 3.8,
            "options": [
                {
                    "id": "risky_jump",
                    "label": "Commit to the jump",
                    "outcomes": [{"metersDelta": {"stamina": -9}}, {"addInjury": {"amount": 5, "part": "left_leg"}}, {"setFlags": ["fell"]}],
                    "logLine": "You leap the gap and land hard, but keep momentum.",
                },
                {
                    "id": "slow_detour",
                    "label": "Take the lower detour",
                    "outcomes": [{"metersDelta": {"hydration": -5, "morale": -1}}, {"setFlags": ["detour_taken"]}],
                    "logLine": "You choose the safe route and pay in time.",
                },
                {
                    "id": "grapple_line",
                    "label": "Anchor a grapple line",
                    "requirements": {"hasTag": "Access"},
                    "outcomes": [{"metersDelta": {"stamina": -3, "morale": 2}}],
                    "logLine": "Your gear turns the crossing into a controlled descent.",
                },
            ],
        },
        {
            "id": "quarantine_gate",
            "title": "Quarantine Gate",
            "text": "Old quarantine barriers still block the fastest corridor.",
            "tags": ["hazard", "social"],
            "trigger": {"biomeIds": ["suburbs"], "minDistance": 6, "cooldownSteps": 4},
            "weight": 3.9,
            "options": [
                {
                    "id": "force_gate",
                    "label": "Force through the gate",
                    "outcomes": [{"addInjury": {"amount": 4, "part": "right_arm"}}, {"setFlags": ["toxic_exposure"]}, {"metersDelta": {"stamina": -6}}],
                    "logLine": "You wrench the gate open and eat a cloud of bad air.",
                },
                {
                    "id": "show_badge",
                    "label": "Flash old credentials",
                    "requirements": {"hasTag": "Authority"},
                    "outcomes": [{"metersDelta": {"morale": 4}}, {"lootRoll": {"lootTableId": "suburbs_medical", "rolls": 1}}],
                    "logLine": "Authority markings still open one side lane.",
                },
                {
                    "id": "decon_route",
                    "label": "Follow decon arrows",
                    "requirements": {"hasTag": "Medical"},
                    "outcomes": [{"metersDelta": {"hydration": -2, "morale": 1}}],
                    "logLine": "You choose the slower, cleaner route and avoid contamination.",
                },
            ],
        },
        {
            "id": "hidden_tunnel",
            "title": "Hidden Tunnel",
            "text": "A tunnel mouth appears behind collapsed signage.",
            "tags": ["hazard", "stealth"],
            "trigger": {"biomeIds": ["suburbs"], "minDistance": 9, "cooldownSteps": 3},
            "weight": 3.7,
            "options": [
                {
                    "id": "take_tunnel",
                    "label": "Take the tunnel",
                    "outcomes": [{"metersDelta": {"stamina": -7, "hydration": -4}}, {"setDeathChance": 0.02}],
                    "logLine": "You push through darkness and stale air to save distance.",
                },
                {
                    "id": "silent_branch",
                    "label": "Use the silent branch",
                    "requirements": {"hasTag": "Stealth"},
                    "outcomes": [{"metersDelta": {"stamina": -3}}, {"lootRoll": {"lootTableId": "suburbs_common", "rolls": 1}}],
                    "logLine": "You find a service branch and bypass the worst choke points.",
                },
                {
                    "id": "surface",
                    "label": "Stay topside",
                    "outcomes": [{"metersDelta": {"hydration": -5, "morale": -2}}],
                    "logLine": "You avoid confined space and absorb weather exposure instead.",
                },
            ],
        },
        {
            "id": "final_mile_push",
            "title": "Final Mile Push",
            "text": "Distance and fatigue collide as your route stretches out.",
            "tags": ["hazard"],
            "trigger": {"biomeIds": ["suburbs"], "minDistance": 18, "cooldownSteps": 5},
            "weight": 3.0,
            "options": [
                {
                    "id": "all_out",
                    "label": "Commit to an all-out surge",
                    "outcomes": [{"metersDelta": {"stamina": -11, "hydration": -7}}, {"metersDelta": {"morale": 4}}, {"setDeathChance": 0.05}],
                    "logLine": "You dig deep and force momentum at real risk.",
                },
                {
                    "id": "cadence",
                    "label": "Hold disciplined cadence",
                    "requirements": {"hasTag": "Trade"},
                    "outcomes": [{"metersDelta": {"stamina": -4, "hydration": -3, "morale": 2}}],
                    "logLine": "You keep rhythm and stretch the run without imploding.",
                },
                {
                    "id": "slow_safe",
                    "label": "Slow down to preserve reserves",
                    "outcomes": [{"metersDelta": {"stamina": -3, "morale": -1}}],
                    "logLine": "You trade speed for control and avoid collapse.",
                },
            ],
        },
    ]
    events.extend(specials)
    return events


def main() -> None:
    events = build_events()
    output = Path(__file__).resolve().parents[1] / "bit_life_survival" / "content" / "events.json"
    output.write_text(json.dumps(events, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(events)} events -> {output}")


if __name__ == "__main__":
    main()

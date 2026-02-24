from __future__ import annotations

import hashlib


BIOME_LINES = {
    "suburbs": [
        "Rows of cracked homes and leaning poles frame the route ahead.",
        "The suburb is quiet enough to hear debris shift two blocks away.",
        "Ash drifts over silent intersections and looted storefronts.",
        "Power lines sway above empty streets as distant alarms pulse.",
    ],
    "forest": [
        "Wet branches swallow sound as visibility narrows.",
        "Fog hangs low between trunks and dead underbrush.",
        "Mud and roots force every step to stay deliberate.",
    ],
    "industrial": [
        "Steam hisses through ruptured pipes and cracked valves.",
        "Moving lights flicker across metal catwalk shadows.",
        "The air tastes of rust and old chemical runoff.",
    ],
}

TAG_LINES = {
    "hazard": [
        "Danger builds before you can fully route around it.",
        "The environment itself is trying to break your rhythm.",
        "Every wrong step here has a cost.",
    ],
    "loot": [
        "There might still be value here if you move carefully.",
        "This spot rewards patience more than speed.",
        "Salvage is possible, but noise will attract attention.",
    ],
    "social": [
        "People are still the least predictable variable out here.",
        "A conversation could save time or create a new threat.",
        "Reading intent matters more than force in this moment.",
    ],
    "trade": [
        "Everything has a price, and prices change by the minute.",
        "Leverage is more useful than supplies if you have both.",
    ],
    "combat": [
        "Violence is close enough to smell in the air.",
        "Initiative decides whether this is a loss or a narrow win.",
    ],
    "tech": [
        "A small systems edge could reshape this whole encounter.",
        "Signals and circuitry matter as much as stamina right now.",
    ],
}


def _pick(options: list[str], seed: int | str, step: int, event_id: str, channel: str) -> str:
    if not options:
        return ""
    token = f"{seed}:{step}:{event_id}:{channel}".encode("utf-8")
    digest = hashlib.sha256(token).hexdigest()
    idx = int(digest[:8], 16) % len(options)
    return options[idx]


def event_flavor_line(seed: int | str, step: int, event_id: str, biome_id: str, tags: list[str]) -> str:
    biome_line = _pick(BIOME_LINES.get(biome_id, BIOME_LINES["suburbs"]), seed, step, event_id, "biome")
    tag = tags[0] if tags else "hazard"
    tag_line = _pick(TAG_LINES.get(tag, TAG_LINES["hazard"]), seed, step, event_id, "tag")
    if biome_line and tag_line:
        return f"{biome_line} {tag_line}"
    return biome_line or tag_line


def citizen_quip(quirk: str | None) -> str:
    if not quirk:
        return ""
    return f"Your drafted runner mutters: \"{quirk}\""

from __future__ import annotations

from collections import defaultdict

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from bit_life_survival.core.loader import ContentBundle
from bit_life_survival.core.models import EquippedSlots, GameState, LogEntry


def meters_widget(state: GameState) -> Panel:
    table = Table.grid(expand=True)
    table.add_column(justify="left")
    table.add_column(justify="left")
    table.add_row("Stamina", f"{state.meters.stamina:6.2f}")
    table.add_row("Hydration", f"{state.meters.hydration:6.2f}")
    table.add_row("Morale", f"{state.meters.morale:6.2f}")
    table.add_row("Injury", f"{state.injury:6.2f}")
    return Panel(table, title="Meters", border_style="cyan")


def inventory_widget(
    inventory: dict[str, int],
    content: ContentBundle,
    title: str = "Inventory",
    max_rows: int = 16,
) -> Panel:
    table = Table(expand=True)
    table.add_column("Item")
    table.add_column("Qty", justify="right")
    table.add_column("Rarity")

    rows = sorted(((item_id, qty) for item_id, qty in inventory.items() if qty > 0), key=lambda pair: pair[0])[:max_rows]
    if not rows:
        table.add_row("-", "0", "-")
    else:
        for item_id, qty in rows:
            item = content.item_by_id.get(item_id)
            table.add_row(item.name if item else item_id, str(qty), item.rarity if item else "?")
    return Panel(table, title=title, border_style="green")


def log_widget(log_entries: list[LogEntry], tail: int = 14) -> Panel:
    lines = [entry.format() for entry in log_entries[-tail:]]
    if not lines:
        lines = ["(no log entries yet)"]
    text = Text("\n".join(lines))
    return Panel(text, title="Timeline", border_style="magenta")


def loadout_summary_widget(equipped: EquippedSlots, content: ContentBundle) -> Panel:
    tags: set[str] = set()
    modifiers = defaultdict(float)

    rows: list[tuple[str, str]] = []
    for slot_name, item_id in equipped.model_dump(mode="python").items():
        if not item_id:
            rows.append((slot_name, "-"))
            continue
        item = content.item_by_id.get(item_id)
        rows.append((slot_name, item.name if item else item_id))
        if not item:
            continue
        tags.update(item.tags)
        for key in ("speed", "carry", "injuryResist", "noise"):
            modifiers[key] += float(getattr(item.modifiers, key) or 0.0)
        for key in ("staminaDrainMul", "hydrationDrainMul", "moraleMul"):
            value = float(getattr(item.modifiers, key) or 1.0)
            if key not in modifiers:
                modifiers[key] = 1.0
            modifiers[key] *= value

    table = Table.grid(expand=True)
    table.add_column()
    table.add_column()
    for slot_name, item_name in rows:
        table.add_row(slot_name, item_name)
    table.add_row("tags", ", ".join(sorted(tags)) if tags else "-")
    table.add_row("speed", f"{modifiers['speed']:.2f}")
    table.add_row("carry", f"{modifiers['carry']:.2f}")
    table.add_row("injuryResist", f"{modifiers['injuryResist']:.2f}")
    table.add_row("staminaDrainMul", f"{modifiers['staminaDrainMul'] if 'staminaDrainMul' in modifiers else 1.0:.2f}")
    table.add_row("hydrationDrainMul", f"{modifiers['hydrationDrainMul'] if 'hydrationDrainMul' in modifiers else 1.0:.2f}")
    table.add_row("moraleMul", f"{modifiers['moraleMul'] if 'moraleMul' in modifiers else 1.0:.2f}")
    table.add_row("noise", f"{modifiers['noise']:.2f}")
    return Panel(table, title="Loadout", border_style="yellow")

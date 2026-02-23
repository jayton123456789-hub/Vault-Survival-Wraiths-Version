from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from bit_life_survival.app.widgets import inventory_widget, loadout_summary_widget, log_widget, meters_widget
from bit_life_survival.core.drone import DroneRecoveryReport
from bit_life_survival.core.engine import EventInstance, advance_to_next_event, apply_choice_with_state_rng, create_initial_state
from bit_life_survival.core.loader import ContentBundle
from bit_life_survival.core.models import EquippedSlots, GameState, LogEntry, VaultState, make_log_entry
from bit_life_survival.core.persistence import draft_citizen_from_claw, refill_citizen_queue, store_item, take_item

SaveCallback = Callable[[], None]


@dataclass(slots=True)
class Recipe:
    id: str
    name: str
    inputs: dict[str, int]
    output_item: str
    output_qty: int = 1


RECIPES: list[Recipe] = [
    Recipe("field_pack", "Field Pack", {"scrap": 4, "cloth": 3, "plastic": 2}, "field_pack"),
    Recipe("patchwork_armor", "Patchwork Armor", {"scrap": 3, "metal": 4, "cloth": 2}, "patchwork_armor"),
    Recipe("filter_mask", "Filter Mask", {"plastic": 4, "cloth": 2, "metal": 1}, "filter_mask"),
    Recipe("lockpick_set", "Lockpick Set", {"metal": 3, "plastic": 1}, "lockpick_set"),
    Recipe("radio_parts", "Radio Parts", {"metal": 3, "plastic": 3}, "radio_parts"),
    Recipe("med_armband", "Medical Armband", {"cloth": 4, "plastic": 1}, "med_armband"),
    Recipe("noise_dampener", "Noise Dampener", {"cloth": 3, "plastic": 2, "scrap": 1}, "noise_dampener"),
    Recipe("repair_kit", "Repair Kit", {"metal": 2, "plastic": 2, "scrap": 2}, "repair_kit"),
]


class BaseScreen:
    def __init__(self, console: Console, content: ContentBundle, vault: VaultState, save_cb: SaveCallback) -> None:
        self.console = console
        self.content = content
        self.vault = vault
        self.save_cb = save_cb

    def _print_header(self) -> None:
        drone_level = int(self.vault.upgrades.get("drone_bay_level", 0))
        self.console.rule("[bold cyan]Vault Base[/bold cyan]")
        self.console.print(
            f"Vault Level: [bold]{self.vault.vault_level}[/bold] | "
            f"TAV: [bold]{self.vault.tav}[/bold] | "
            f"Drone Bay Level: [bold]{drone_level}[/bold]"
        )
        self.console.print(
            f"Citizen queue: [bold]{len(self.vault.citizen_queue)}[/bold] | "
            f"Current citizen: [bold]{self.vault.current_citizen.name if self.vault.current_citizen else 'None'}[/bold]"
        )

    def _storage_table(self, slot_filter: str | None = None, rarity_filter: str | None = None) -> Table:
        rows: list[tuple[str, int, str, str]] = []
        for item_id, qty in sorted(self.vault.storage.items()):
            if qty <= 0:
                continue
            item = self.content.item_by_id.get(item_id)
            slot = item.slot if item else "unknown"
            rarity = item.rarity if item else "unknown"
            if slot_filter and slot != slot_filter:
                continue
            if rarity_filter and rarity != rarity_filter:
                continue
            rows.append((item.name if item else item_id, qty, slot, rarity))

        table = Table(title="Vault Storage", expand=True)
        table.add_column("Item")
        table.add_column("Qty", justify="right")
        table.add_column("Slot")
        table.add_column("Rarity")
        if not rows:
            table.add_row("-", "0", "-", "-")
        else:
            for name, qty, slot, rarity in rows:
                table.add_row(name, str(qty), slot, rarity)
        return table

    def show_storage(self) -> None:
        slot_filter = Prompt.ask(
            "Filter slot (blank for all)",
            default="",
        ).strip()
        rarity_filter = Prompt.ask(
            "Filter rarity (blank for all)",
            default="",
        ).strip()
        self.console.print(
            self._storage_table(
                slot_filter=slot_filter if slot_filter else None,
                rarity_filter=rarity_filter if rarity_filter else None,
            )
        )

    def use_the_claw(self) -> None:
        drafted = draft_citizen_from_claw(self.vault, preview_count=5)
        self.console.print(
            f"[bold green]Claw selected:[/bold green] {drafted.name} "
            f"(quirk: {drafted.quirk})"
        )
        self.save_cb()

    def settings_menu(self) -> None:
        settings = self.vault.settings
        self.console.rule("[bold yellow]Settings[/bold yellow]")
        self.console.print(
            f"skip_intro={settings.skip_intro}, "
            f"intro_use_cinematic_audio={settings.intro_use_cinematic_audio}, "
            f"seeded_mode={settings.seeded_mode}, "
            f"base_seed={settings.base_seed}"
        )
        settings.skip_intro = Confirm.ask("Toggle skip intro?", default=settings.skip_intro)
        settings.intro_use_cinematic_audio = Confirm.ask(
            "Use cinematic intro audio?",
            default=settings.intro_use_cinematic_audio,
        )
        settings.seeded_mode = Confirm.ask("Use deterministic seeded runs?", default=settings.seeded_mode)
        seed_raw = Prompt.ask("Base seed (integer)", default=str(settings.base_seed))
        try:
            settings.base_seed = int(seed_raw)
        except ValueError:
            self.console.print("[yellow]Invalid seed input. Keeping previous value.[/yellow]")
        self.save_cb()

    def craft_menu(self) -> None:
        self.console.rule("[bold green]Crafting[/bold green]")
        recipe_table = Table(expand=True)
        recipe_table.add_column("#", justify="right")
        recipe_table.add_column("Recipe")
        recipe_table.add_column("Inputs")
        recipe_table.add_column("Output")
        for idx, recipe in enumerate(RECIPES, start=1):
            inputs = ", ".join(f"{k}x{v}" for k, v in recipe.inputs.items())
            recipe_table.add_row(str(idx), recipe.name, inputs, f"{recipe.output_item} x{recipe.output_qty}")
        self.console.print(recipe_table)

        choice = Prompt.ask("Craft recipe # (blank to cancel)", default="").strip()
        if not choice:
            return
        if not choice.isdigit():
            self.console.print("[red]Invalid recipe choice.[/red]")
            return
        index = int(choice) - 1
        if index < 0 or index >= len(RECIPES):
            self.console.print("[red]Recipe out of range.[/red]")
            return
        recipe = RECIPES[index]

        for item_id, qty in recipe.inputs.items():
            if self.vault.storage.get(item_id, 0) < qty:
                self.console.print(
                    f"[red]Missing materials:[/red] requires {qty}x {item_id}, "
                    f"have {self.vault.storage.get(item_id, 0)}"
                )
                return
        for item_id, qty in recipe.inputs.items():
            take_item(self.vault, item_id, qty)
        store_item(self.vault, recipe.output_item, recipe.output_qty)
        self.console.print(
            f"[bold green]Crafted[/bold green] {recipe.output_qty}x {recipe.output_item}."
        )
        self.save_cb()

    def compute_run_seed(self) -> int:
        settings = self.vault.settings
        if settings.seeded_mode:
            return settings.base_seed + self.vault.run_counter
        return int(time.time_ns() & 0xFFFFFFFF)

    def prompt_action(self, loadout: EquippedSlots) -> str:
        self._print_header()
        self.console.print(loadout_summary_widget(loadout, self.content))
        self.console.print(self._storage_table())
        self.console.print(
            "\n[bold]Actions:[/bold] "
            "[1] Use The Claw  [2] Loadout  [3] Deploy  [4] Craft  [5] Settings  [6] Storage Filter  [Q] Quit"
        )
        return Prompt.ask("Select action", default="1").strip().lower()


class LoadoutScreen:
    SLOT_CHOICES = {
        "1": "pack",
        "2": "armor",
        "3": "vehicle",
        "4": "utility1",
        "5": "utility2",
        "6": "faction",
    }

    def __init__(self, console: Console, content: ContentBundle, vault: VaultState, save_cb: SaveCallback) -> None:
        self.console = console
        self.content = content
        self.vault = vault
        self.save_cb = save_cb

    def _allowed_item_slot(self, run_slot: str) -> str:
        if run_slot in {"utility1", "utility2"}:
            return "utility"
        return run_slot

    def _candidates(self, run_slot: str) -> list[tuple[str, int]]:
        allowed = self._allowed_item_slot(run_slot)
        rows: list[tuple[str, int]] = []
        for item_id, qty in sorted(self.vault.storage.items()):
            if qty <= 0:
                continue
            item = self.content.item_by_id.get(item_id)
            if item and item.slot == allowed:
                rows.append((item_id, qty))
        return rows

    def _equip_slot(self, loadout: EquippedSlots, run_slot: str) -> None:
        candidates = self._candidates(run_slot)
        if not candidates:
            self.console.print(f"[yellow]No items in storage for slot '{run_slot}'.[/yellow]")
            return

        table = Table(title=f"Equip {run_slot}", expand=True)
        table.add_column("#", justify="right")
        table.add_column("Item")
        table.add_column("Qty", justify="right")
        table.add_column("Rarity")
        for idx, (item_id, qty) in enumerate(candidates, start=1):
            item = self.content.item_by_id[item_id]
            table.add_row(str(idx), item.name, str(qty), item.rarity)
        self.console.print(table)

        pick = Prompt.ask("Choose item # (blank to cancel)", default="").strip()
        if not pick:
            return
        if not pick.isdigit():
            self.console.print("[red]Invalid selection.[/red]")
            return
        index = int(pick) - 1
        if index < 0 or index >= len(candidates):
            self.console.print("[red]Selection out of range.[/red]")
            return

        new_item_id = candidates[index][0]
        old_item_id = getattr(loadout, run_slot)
        if not take_item(self.vault, new_item_id, 1):
            self.console.print("[red]Failed to reserve item from storage.[/red]")
            return
        if old_item_id:
            store_item(self.vault, old_item_id, 1)
        setattr(loadout, run_slot, new_item_id)
        self.console.print(f"[green]Equipped[/green] {new_item_id} to {run_slot}.")
        self.save_cb()

    def _clear_slot(self, loadout: EquippedSlots, run_slot: str) -> None:
        current = getattr(loadout, run_slot)
        if not current:
            self.console.print(f"[yellow]{run_slot} is already empty.[/yellow]")
            return
        store_item(self.vault, current, 1)
        setattr(loadout, run_slot, None)
        self.console.print(f"[green]Cleared[/green] {run_slot}. Returned {current} to storage.")
        self.save_cb()

    def run(self, loadout: EquippedSlots) -> EquippedSlots:
        while True:
            self.console.rule("[bold cyan]Loadout[/bold cyan]")
            self.console.print(loadout_summary_widget(loadout, self.content))
            self.console.print(
                "[1] pack  [2] armor  [3] vehicle  [4] utility1  [5] utility2  [6] faction  "
                "[c] clear slot  [b] back"
            )
            action = Prompt.ask("Select slot/action", default="b").strip().lower()
            if action == "b":
                return loadout
            if action == "c":
                slot = Prompt.ask("Which slot to clear?", choices=list(self.SLOT_CHOICES.values()), default="utility1")
                self._clear_slot(loadout, slot)
                continue
            if action in self.SLOT_CHOICES:
                self._equip_slot(loadout, self.SLOT_CHOICES[action])
                continue
            self.console.print("[red]Unknown action.[/red]")


class RunScreen:
    def __init__(self, console: Console, content: ContentBundle, state: GameState) -> None:
        self.console = console
        self.content = content
        self.state = state
        self.logs: list[LogEntry] = []

    def _render_hud(self) -> None:
        self.console.rule("[bold red]Run[/bold red]")
        self.console.print(
            f"Distance: [bold]{self.state.distance:.2f}[/bold] | "
            f"Time: [bold]{self.state.time}[/bold] | "
            f"Biome: [bold]{self.state.biome_id}[/bold]"
        )
        self.console.print(meters_widget(self.state))
        self.console.print(inventory_widget(self.state.inventory, self.content, title="Run Inventory"))
        self.console.print(loadout_summary_widget(self.state.equipped, self.content))
        self.console.print(log_widget(self.logs))

    def _prompt_event_choice(self, event_instance: EventInstance) -> str | None:
        self.console.rule(f"[bold yellow]{event_instance.title}[/bold yellow]")
        self.console.print(event_instance.text)

        unlocked_ids: list[str] = []
        for idx, option in enumerate(event_instance.options, start=1):
            status = "LOCKED" if option.locked else "OPEN"
            reasons = f" ({'; '.join(option.lock_reasons)})" if option.locked and option.lock_reasons else ""
            self.console.print(f"[{idx}] {option.label} [{status}]{reasons}")
            if not option.locked:
                unlocked_ids.append(option.id)

        if not unlocked_ids:
            self.console.print("[yellow]No unlocked options; event is skipped.[/yellow]")
            return None

        while True:
            choice_raw = Prompt.ask("Choose option #").strip()
            if not choice_raw.isdigit():
                self.console.print("[red]Enter a numeric option index.[/red]")
                continue
            index = int(choice_raw) - 1
            if index < 0 or index >= len(event_instance.options):
                self.console.print("[red]Option out of range.[/red]")
                continue
            chosen = event_instance.options[index]
            if chosen.locked:
                self.console.print("[red]That option is locked.[/red]")
                continue
            return chosen.id

    def run(self) -> tuple[GameState, list[LogEntry]]:
        while not self.state.dead:
            self._render_hud()
            action = Prompt.ask(
                "Continue Until Next Event [c], show full log [l], retreat [q]",
                choices=["c", "l", "q"],
                default="c",
            )
            if action == "l":
                self.console.print(log_widget(self.logs, tail=200))
                continue
            if action == "q":
                self.state.dead = True
                self.state.death_reason = "Retreated"
                retreat_log = make_log_entry(self.state, "system", "Run ended by retreat command.")
                self.logs.append(retreat_log)
                break

            _, event_instance, step_logs = advance_to_next_event(self.state, self.content)
            self.logs.extend(step_logs)
            if self.state.dead:
                break
            if event_instance is None:
                continue
            option_id = self._prompt_event_choice(event_instance)
            if option_id is None:
                continue
            choice_logs = apply_choice_with_state_rng(self.state, event_instance, option_id, self.content)
            self.logs.extend(choice_logs)

        return self.state, self.logs


class DeathScreen:
    def __init__(self, console: Console, content: ContentBundle) -> None:
        self.console = console
        self.content = content

    def show(self, state: GameState, report: DroneRecoveryReport, logs: list[LogEntry]) -> None:
        self.console.rule("[bold red]Death Report[/bold red]")
        self.console.print(
            f"Reason: [bold]{state.death_reason or 'Unknown'}[/bold] | "
            f"Distance: [bold]{state.distance:.2f}[/bold] | "
            f"Time: [bold]{state.time}[/bold]"
        )
        self.console.print(
            f"Drone Recovery: [bold]{report.status}[/bold] "
            f"(chance={report.recovery_chance:.2f}, TAV +{report.tav_gain})"
        )
        if report.recovered:
            self.console.print("Recovered: " + ", ".join(f"{item_id}x{qty}" for item_id, qty in sorted(report.recovered.items())))
        if report.lost:
            self.console.print("Lost: " + ", ".join(f"{item_id}x{qty}" for item_id, qty in sorted(report.lost.items())))
        if report.milestone_awards:
            self.console.print("Milestones: " + ", ".join(report.milestone_awards))
        self.console.print(log_widget(logs))
        Prompt.ask("Press Enter to return to base", default="")


def create_run_state_with_loadout(seed: int | str, biome_id: str, loadout: EquippedSlots) -> GameState:
    state = create_initial_state(seed=seed, biome_id=biome_id)
    state.equipped = loadout.model_copy(deep=True)
    return state


def reset_loadout_after_run(vault: VaultState, loadout: EquippedSlots) -> EquippedSlots:
    # Equipped items are considered "in the field". Keep them equipped on the run state and clear staged loadout.
    return EquippedSlots()


def ensure_queue_filled(vault: VaultState, target_size: int = 12) -> None:
    refill_citizen_queue(vault, target_size=target_size)

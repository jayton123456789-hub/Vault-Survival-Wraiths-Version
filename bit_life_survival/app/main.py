from __future__ import annotations

import json
import os
from pathlib import Path

from rich.console import Console

from bit_life_survival.app.intro import play_startup_intro
from bit_life_survival.app.screens import (
    BaseScreen,
    DeathScreen,
    LoadoutScreen,
    RunScreen,
    create_run_state_with_loadout,
    ensure_queue_filled,
    reset_loadout_after_run,
)
from bit_life_survival.core.drone import run_drone_recovery
from bit_life_survival.core.loader import ContentValidationError, load_content
from bit_life_survival.core.models import EquippedSlots
from bit_life_survival.core.persistence import load_save_data, save_save_data, store_item


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _return_staged_loadout_to_storage(loadout: EquippedSlots, save_data) -> None:
    for item_id in loadout.as_values():
        store_item(save_data.vault, item_id, 1)


def _apply_optional_settings_file(save_data, settings_path: Path) -> None:
    if not settings_path.exists():
        return
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(payload, dict):
        return

    settings = save_data.vault.settings
    if "skip_intro" in payload and isinstance(payload["skip_intro"], bool):
        settings.skip_intro = payload["skip_intro"]
    if "intro_use_cinematic_audio" in payload and isinstance(payload["intro_use_cinematic_audio"], bool):
        settings.intro_use_cinematic_audio = payload["intro_use_cinematic_audio"]
    if "seeded_mode" in payload and isinstance(payload["seeded_mode"], bool):
        settings.seeded_mode = payload["seeded_mode"]
    if "base_seed" in payload:
        try:
            settings.base_seed = int(payload["base_seed"])
        except (TypeError, ValueError):
            pass


def main() -> None:
    console = Console()
    repo_root = _repo_root()
    content_dir = repo_root / "bit_life_survival" / "content"
    assets_dir = repo_root / "bit_life_survival" / "assets" / "bbwg_intro"
    save_path = repo_root / "save.json"
    settings_path = repo_root / "settings.json"

    try:
        content = load_content(content_dir)
    except ContentValidationError as exc:
        console.print(f"[bold red]Failed to load game content:[/bold red]\n{exc}")
        raise SystemExit(1) from exc

    save_data = load_save_data(save_path=save_path)
    _apply_optional_settings_file(save_data, settings_path=settings_path)
    ensure_queue_filled(save_data.vault)

    def save_now() -> None:
        save_save_data(save_data, save_path=save_path)

    save_now()

    skip_intro_from_env = os.environ.get("BLS_SKIP_INTRO", "").strip().lower() in {"1", "true", "yes", "on"}

    play_startup_intro(
        assets_dir=assets_dir,
        skip_intro=skip_intro_from_env or save_data.vault.settings.skip_intro,
        use_cinematic_audio=save_data.vault.settings.intro_use_cinematic_audio,
        logger=lambda line: console.print(f"[yellow]{line}[/yellow]"),
    )

    loadout = EquippedSlots()
    death_screen = DeathScreen(console=console, content=content)

    try:
        while True:
            base = BaseScreen(console=console, content=content, vault=save_data.vault, save_cb=save_now)
            action = base.prompt_action(loadout)

            if action in {"q", "quit", "exit"}:
                _return_staged_loadout_to_storage(loadout, save_data)
                loadout = EquippedSlots()
                save_now()
                console.print("[bold]Goodbye.[/bold]")
                return

            if action == "1":
                base.use_the_claw()
                continue
            if action == "2":
                loadout = LoadoutScreen(console=console, content=content, vault=save_data.vault, save_cb=save_now).run(loadout)
                continue
            if action == "4":
                base.craft_menu()
                continue
            if action == "5":
                base.settings_menu()
                continue
            if action == "6":
                base.show_storage()
                continue
            if action != "3":
                console.print("[red]Unknown action.[/red]")
                continue

            # Deploy
            if save_data.vault.current_citizen is None:
                console.print("[yellow]No drafted citizen. Use The Claw first.[/yellow]")
                continue

            run_seed = base.compute_run_seed()
            save_data.vault.last_run_seed = run_seed
            save_data.vault.run_counter += 1
            save_now()

            run_state = create_run_state_with_loadout(seed=run_seed, biome_id="suburbs", loadout=loadout)
            run_screen = RunScreen(console=console, content=content, state=run_state)
            final_state, run_logs = run_screen.run()

            recovery = run_drone_recovery(save_data.vault, final_state, content)
            save_data.vault.current_citizen = None
            loadout = reset_loadout_after_run(save_data.vault, loadout)
            ensure_queue_filled(save_data.vault)
            save_now()

            death_screen.show(final_state, recovery, run_logs)
    finally:
        # Return staged loadout items if app exits unexpectedly before deploy.
        if loadout.as_values():
            _return_staged_loadout_to_storage(loadout, save_data)
            save_now()


if __name__ == "__main__":
    main()

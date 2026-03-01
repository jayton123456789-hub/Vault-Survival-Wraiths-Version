from __future__ import annotations

import logging
from pathlib import Path

import pygame

from bit_life_survival.app.scenes.base import BaseScene
from bit_life_survival.app.scenes.briefing import BriefingScene
from bit_life_survival.app.scenes.load_game import LoadGameScene
from bit_life_survival.app.scenes.menu import MainMenuScene
from bit_life_survival.app.scenes.operations import OperationsScene
from bit_life_survival.app.scenes.research import ResearchScene
from bit_life_survival.app.scenes.run import RunScene
from bit_life_survival.app.services.saves import SaveService
from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.backgrounds import BackgroundRenderer
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.models import EquippedSlots
from bit_life_survival.core.persistence import create_default_save_data, transfer_selected_citizen_to_roster
from bit_life_survival.core.research import buy_research
from bit_life_survival.core.settings import default_settings


class AppStub:
    def __init__(self, repo_root: Path) -> None:
        pygame.init()
        self.screen = pygame.Surface((1920, 1080))
        self.content = load_content(repo_root / "bit_life_survival" / "content")
        self.save_data = create_default_save_data(base_seed=2042)
        self.current_loadout = EquippedSlots()
        self.settings = default_settings()
        self.settings["gameplay"]["tutorial_completed"] = True
        self.settings["gameplay"]["replay_tutorial"] = False
        self.backgrounds = BackgroundRenderer()
        self.current_slot = 1
        self.gameplay_logger = logging.getLogger("readme_screenshots")

        saves_dir = repo_root / ".tmp_readme_saves"
        saves_dir.mkdir(parents=True, exist_ok=True)
        self.save_service = SaveService(saves_dir, slot_count=3)

        slot1 = self.save_service.create_new_game(slot=1, base_seed=2042)
        slot1.vault.tav = 48
        slot1.vault.vault_level = 3
        slot1.vault.upgrades["drone_bay_level"] = 2
        slot1.vault.last_run_distance = 19.4
        slot1.vault.last_run_time = 31
        slot1.vault.materials["scrap"] = 420
        slot1.vault.settings.seen_run_help = True
        self.save_service.save_slot(1, slot1)

        slot2 = self.save_service.create_new_game(slot=2, base_seed=3001)
        slot2.vault.tav = 11
        slot2.vault.last_run_distance = 6.7
        slot2.vault.last_run_time = 14
        self.save_service.save_slot(2, slot2)

        self.save_data = slot1

    def save_current_slot(self) -> None:
        if self.current_slot is not None and self.save_data is not None:
            self.save_service.save_slot(self.current_slot, self.save_data)

    def save_settings(self) -> None:
        return

    def virtual_mouse_pos(self) -> tuple[int, int]:
        return (0, 0)

    def compute_run_seed(self) -> int:
        return int(self.save_data.vault.settings.base_seed) + int(self.save_data.vault.run_counter)

    def change_scene(self, _scene) -> None:
        return

    def return_staged_loadout(self) -> None:
        return

    def quit(self) -> None:
        return


def _save(surface: pygame.Surface, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surface, str(path))


def _prime_research(vault) -> None:
    vault.materials["scrap"] = 2400
    progression = [
        ("rationing", 2),
        ("water_recycling", 1),
        ("field_medicine", 1),
        ("salvage_tools", 2),
        ("route_caching", 1),
        ("deep_contracts", 1),
        ("intake_protocols", 2),
        ("team_doctrine", 1),
        ("drone_recovery_suite", 2),
        ("drone_pathing", 1),
        ("ops_planning", 2),
        ("forward_command", 1),
    ]
    for node_id, target_level in progression:
        for _ in range(target_level):
            try:
                buy_research(vault, node_id)
            except ValueError:
                break
    vault.materials["scrap"] = max(160, int(vault.materials.get("scrap", 0)))


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    theme.apply_theme("ember")
    app = AppStub(repo_root)

    screenshots_dir = repo_root / "docs" / "screenshots"

    # Main menu
    menu = MainMenuScene()
    menu.render(app, app.screen)
    _save(app.screen, screenshots_dir / "main-menu.png")

    # Prep a drafted citizen for base + operations + run screenshots.
    drafted = transfer_selected_citizen_to_roster(app.save_data.vault, app.save_data.vault.citizen_queue[0].id)
    drafted.loadout.pack = "backpack_basic"
    drafted.loadout.armor = "armor_scrap"
    drafted.loadout.utility1 = "water_pouch"
    drafted.loadout.utility2 = "ration_pack"
    drafted.kit = {
        "water_pouch": 3,
        "ration_pack": 2,
        "medkit_small": 1,
    }
    app.current_loadout = drafted.loadout.model_copy(deep=True)
    app.save_data.vault.current_citizen = drafted
    app.save_data.vault.active_deploy_citizen_id = drafted.id

    # Base command
    base = BaseScene()
    base.on_enter(app)
    base.render(app, app.screen)
    _save(app.screen, screenshots_dir / "base-command.png")

    # Operations loadout
    operations = OperationsScene(initial_tab="loadout")
    operations.on_enter(app)
    operations.render(app, app.screen)
    _save(app.screen, screenshots_dir / "operations-loadout.png")

    # Mission briefing
    briefing = BriefingScene(run_seed=app.compute_run_seed(), biome_id="suburbs")
    briefing.render(app, app.screen)
    _save(app.screen, screenshots_dir / "mission-briefing.png")

    # Research command
    _prime_research(app.save_data.vault)
    research = ResearchScene()
    research.render(app, app.screen)
    _save(app.screen, screenshots_dir / "research-command.png")

    # Run with inventory open (new UX)
    run_scene = RunScene(run_seed=app.compute_run_seed(), biome_id="suburbs")
    run_scene.on_enter(app)
    run_scene.state.meters.stamina = 67.0
    run_scene.state.meters.hydration = 54.0
    run_scene.state.meters.morale = 71.0
    run_scene.state.hunger = 58.0
    run_scene.state.inventory["water_pouch"] = max(2, int(run_scene.state.inventory.get("water_pouch", 0)))
    run_scene.state.inventory["ration_pack"] = max(2, int(run_scene.state.inventory.get("ration_pack", 0)))
    run_scene.state.inventory["medkit_small"] = max(1, int(run_scene.state.inventory.get("medkit_small", 0)))
    run_scene.inventory_overlay = True
    run_scene.inventory_tab = "stats"
    run_scene.render(app, app.screen)
    _save(app.screen, screenshots_dir / "run-inventory.png")

    # Load game manager
    load_game = LoadGameScene()
    load_game.render(app, app.screen)
    _save(app.screen, screenshots_dir / "load-game.png")

    print(f"Saved screenshots to {screenshots_dir}")


if __name__ == "__main__":
    main()
